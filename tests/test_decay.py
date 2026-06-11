"""Module 6 (decay) tests."""
from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from core.db import Alert, LiveState, Strategy, get_engine, get_session_factory, init_db
from core.decay.detectors import (
    cusum_check,
    current_drawdown_r,
    dd_envelope_check,
    ks_shift_check,
    regime_mismatch_check,
)
from core.decay.state_machine import apply_evaluation, evaluate_decay, retire

RNG = np.random.default_rng(42)
HIST = RNG.choice([2.0, -1.0], 1000, p=[0.5, 0.5])  # +0.5R edge


def _trades(rs, regimes=None) -> pd.DataFrame:
    df = pd.DataFrame({"r_multiple": rs})
    if regimes is not None:
        df["regime"] = regimes
    return df


# ---------------------------------------------------------------- detectors
def test_cusum_quiet_on_healthy_stream():
    live = RNG.choice([2.0, -1.0], 60, p=[0.5, 0.5])
    res = cusum_check(live, HIST.mean(), HIST.std(ddof=1))
    assert not res.triggered


def test_cusum_triggers_on_collapsed_edge():
    live = np.full(80, -1.0)  # strategy now loses every trade
    res = cusum_check(live, HIST.mean(), HIST.std(ddof=1))
    assert res.triggered
    assert res.z >= 3.0
    assert res.drift < 0


def test_current_drawdown_from_first_trade():
    assert current_drawdown_r(np.array([-1.0, -1.0, 2.0])) == pytest.approx(2.0)
    assert current_drawdown_r(np.array([2.0, -1.0])) == pytest.approx(1.0)


def test_dd_envelope_levels():
    ok = dd_envelope_check(RNG.choice([2.0, -1.0], 40, p=[0.5, 0.5]), HIST, seed=1)
    assert ok.level == "OK"
    bust = dd_envelope_check(np.full(40, -1.0), HIST, seed=1)  # -40R is beyond p99
    assert bust.level == "P99"
    assert bust.p99_dd_r > bust.p95_dd_r > 0


def test_ks_detects_distribution_shift():
    shifted = ks_shift_check(np.full(30, -0.2), HIST)
    assert shifted.shifted
    same = ks_shift_check(RNG.choice([2.0, -1.0], 30, p=[0.5, 0.5]), HIST, alpha=0.01)
    assert not same.shifted


def test_regime_mismatch_suppression_logic():
    live = _trades([-0.5] * 20, regimes=["SIDEWAYS_CHOP"] * 20)
    regime_exp = {"SIDEWAYS_CHOP": -0.45, "LOW_VOL_TREND": 0.8}
    res = regime_mismatch_check(live, regime_exp, hist_mean=0.5)
    assert res.regime_expected  # losing in a regime where it always loses

    live_good_regime = _trades([-0.5] * 20, regimes=["LOW_VOL_TREND"] * 20)
    res2 = regime_mismatch_check(live_good_regime, regime_exp, hist_mean=0.5)
    assert not res2.regime_expected  # losing where it should win = real decay


# ---------------------------------------------------------------- state machine
def test_healthy_stays_healthy():
    live = _trades(RNG.choice([2.0, -1.0], 50, p=[0.5, 0.5]))
    ev = evaluate_decay("s", "HEALTHY", live, HIST)
    assert ev.new_state == "HEALTHY"
    assert ev.risk_multiplier == 1.0
    assert not ev.triggers


def test_p95_dd_reduces_and_halves_risk():
    rng = np.random.default_rng(7)
    base = rng.choice([2.0, -1.0], 40, p=[0.5, 0.5])
    dd = dd_envelope_check(base, HIST, seed=42)
    # craft a live stream sitting between p95 and p99
    n_loss = int(np.ceil(dd.p95_dd_r)) + 1
    live = _trades([2.0] * 5 + [-1.0] * n_loss)
    ev = evaluate_decay("s", "HEALTHY", live, HIST)
    assert ev.new_state in ("REDUCED", "SUSPENDED")
    if ev.new_state == "REDUCED":
        assert ev.risk_multiplier == 0.5


def test_p99_dd_suspends():
    live = _trades([-1.0] * 60)
    ev = evaluate_decay("s", "HEALTHY", live, HIST)
    assert ev.new_state == "SUSPENDED"
    assert ev.risk_multiplier == 0.0
    assert any("p99" in t for t in ev.triggers)


def test_soft_triggers_escalate_one_step_and_recover():
    # mild underperformance: CUSUM/KS fire but DD stays inside the envelope
    live = _trades([0.0] * 35)
    ev = evaluate_decay("s", "HEALTHY", live, HIST)
    assert ev.new_state == "WATCH"
    ev2 = evaluate_decay("s", "WATCH", live, HIST)
    assert ev2.new_state == "REDUCED"  # capped at REDUCED for soft evidence

    healthy = _trades(list(RNG.choice([2.0, -1.0], 50, p=[0.55, 0.45])))
    ev3 = evaluate_decay("s", "REDUCED", healthy, HIST)
    assert ev3.new_state == "WATCH"  # de-escalates one step when clean


def test_regime_mismatch_suppresses_soft_triggers():
    # mild drift: CUSUM z > 3 but the -6R drawdown stays inside the MC envelope
    live = _trades([-0.1] * 60, regimes=["SIDEWAYS_CHOP"] * 60)
    regime_exp = {"SIDEWAYS_CHOP": -0.1}
    ev = evaluate_decay("s", "HEALTHY", live, HIST, regime_expectancy=regime_exp)
    assert ev.suppressed  # CUSUM/KS fired but were suppressed
    assert ev.new_state == "HEALTHY"


def test_retired_is_terminal():
    live = _trades([2.0] * 50)
    ev = evaluate_decay("s", "RETIRED", live, HIST)
    assert ev.new_state == "RETIRED"


def test_transitions_logged_with_evidence(tmp_path):
    engine = get_engine(tmp_path / "t.db")
    init_db(engine)
    Session = get_session_factory(engine)
    with Session() as s:
        strat = Strategy(name="decayer")
        s.add(strat)
        s.commit()
        sid = strat.id

        live = _trades([-1.0] * 60)
        ev = evaluate_decay("decayer", "HEALTHY", live, HIST)
        apply_evaluation(s, sid, ev, base_risk_pct=1.0)

        state = s.query(LiveState).filter_by(strategy_id=sid).one()
        assert state.state == "SUSPENDED"
        assert state.risk_pct == 0.0
        assert not state.enabled

        alert = s.query(Alert).filter_by(kind="state_transition").one()
        assert "HEALTHY -> SUSPENDED" in alert.message
        assert "dd_envelope" in alert.evidence

        retire(s, sid, "decayer", "manual retirement after review")
        assert s.query(LiveState).filter_by(strategy_id=sid).one().state == "RETIRED"
        assert s.query(Alert).filter_by(kind="state_transition").count() == 2
