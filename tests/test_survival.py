"""Module 1 (survival) tests: schema, firm engine, day grouping, MC correctness."""
from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from core.db import Alert, Strategy, Trade, get_engine, get_session_factory, init_db
from core.survival.firm import FirmConfig, PhaseRule, load_firm
from core.survival.mc import BUST_DAILY, BUST_TOTAL, PASS, run_prop_sim
from core.survival.sample import generate_sample_trades
from core.survival.sweep import sweep_risks
from core.survival.trades_io import DayGroupedTrades, group_trades_by_day


# ---------------------------------------------------------------- helpers
def _firm(**overrides) -> FirmConfig:
    """Single-phase test firm: 10% target, 10% total loss, no daily, no min days."""
    base = dict(
        name="test", account_size=100_000, challenge_fee=0.0,
        daily_loss_pct=None, max_total_loss_pct=10.0,
        phases=[PhaseRule(name="p1", profit_target_pct=10.0, min_trading_days=0)],
        sim_max_days_per_phase=20_000,
    )
    base.update(overrides)
    return FirmConfig.model_validate(base)


def _iid_days(r_values: list[float], mae_values: list[float]) -> DayGroupedTrades:
    """One trade per day -> block bootstrap with block=1 gives iid sampling."""
    n = len(r_values)
    return DayGroupedTrades(
        day_ptr=np.arange(n + 1, dtype=np.int64),
        r=np.asarray(r_values, dtype=np.float64),
        mae=np.asarray(mae_values, dtype=np.float64),
    )


def _no_funded(firm: FirmConfig) -> FirmConfig:
    return firm.model_copy(update={"funded": firm.funded.model_copy(update={"horizon_days": 0})})


# ---------------------------------------------------------------- schema
def test_schema_init_and_roundtrip(tmp_path):
    engine = get_engine(tmp_path / "t.db")
    init_db(engine)
    with get_session_factory(engine)() as s:
        strat = Strategy(name="s1", edge_source="trend", instrument="EURUSD", timeframe="H1")
        s.add(strat)
        s.flush()
        s.add(Trade(strategy_id=strat.id, entry_time=pd.Timestamp("2026-01-05 10:00", tz="UTC").to_pydatetime(),
                    r_multiple=2.0, mae_r=0.4, mfe_r=2.2))
        s.add(Alert(source="decay", severity="warning", message="test", evidence={"z": 3.1}))
        s.commit()
    with get_session_factory(engine)() as s:
        assert s.query(Strategy).count() == 1
        assert s.query(Trade).one().r_multiple == 2.0
        assert s.query(Alert).one().evidence["z"] == 3.1


# ---------------------------------------------------------------- firm config
def test_ftmo_yaml_loads_expected_rules():
    firm = load_firm("ftmo_100k_2step")
    assert firm.account_size == 100_000
    assert firm.daily_loss_pct == 5.0
    assert firm.max_total_loss_pct == 10.0
    assert firm.timezone == "Europe/Prague"
    assert [ph.profit_target_pct for ph in firm.phases] == [10.0, 5.0]
    assert all(ph.min_trading_days == 4 for ph in firm.phases)
    assert all(ph.max_days is None for ph in firm.phases)
    assert firm.funded.profit_split == 0.80


# ---------------------------------------------------------------- midnight CET
def test_midnight_cet_boundary_grouping():
    """22:30 UTC in summer is 00:30 CEST next day -> new trading day (daily reset)."""
    df = pd.DataFrame({
        "entry_time": pd.to_datetime([
            "2026-06-09 21:30:00+00:00",  # 23:30 CEST June 9 -> day 1
            "2026-06-09 22:30:00+00:00",  # 00:30 CEST June 10 -> day 2
            "2026-06-10 08:00:00+00:00",  # 10:00 CEST June 10 -> day 2
        ]),
        "r_multiple": [1.0, 1.0, 1.0],
        "mae_r": [0.5, 0.5, 0.5],
    })
    days = group_trades_by_day(df, tz="Europe/Prague")
    assert days.n_days == 2
    assert list(np.diff(days.day_ptr)) == [1, 2]

    # winter (CET = UTC+1): 23:30 UTC is 00:30 CET next day
    df_w = pd.DataFrame({
        "entry_time": pd.to_datetime(["2026-01-05 22:30:00+00:00", "2026-01-05 23:30:00+00:00"]),
        "r_multiple": [1.0, 1.0],
        "mae_r": [0.0, 0.0],
    })
    days_w = group_trades_by_day(df_w, tz="Europe/Prague")
    assert days_w.n_days == 2


# ---------------------------------------------------------------- mid-trade floating breach
def test_floating_loss_breaches_daily_mid_trade():
    """Trade closes +2R but floats to -6R intraday: at 1% risk the -6% trough
    must breach the 5% daily limit even though the close (+2%) would not."""
    firm = _no_funded(_firm(daily_loss_pct=5.0))
    days = _iid_days([2.0], [6.0])
    res = run_prop_sim(days, firm, risk_pct=1.0, n_paths=500, seed=7, block_size=1)
    assert res.p_bust_daily == 1.0
    assert res.p_pass == 0.0


def test_no_breach_when_checked_only_at_close():
    """Same trade with small MAE passes — confirms the breach above was the trough."""
    firm = _no_funded(_firm(daily_loss_pct=5.0))
    days = _iid_days([2.0], [0.5])
    res = run_prop_sim(days, firm, risk_pct=1.0, n_paths=500, seed=7, block_size=1)
    assert res.p_bust_daily == 0.0
    assert res.p_pass == 1.0


def test_floating_loss_breaches_total_mid_trade():
    firm = _no_funded(_firm(daily_loss_pct=None, max_total_loss_pct=10.0))
    days = _iid_days([1.0], [11.0])  # winner that floats -11R first
    res = run_prop_sim(days, firm, risk_pct=1.0, n_paths=200, seed=3, block_size=1)
    assert res.p_bust_total == 1.0


def test_daily_anchor_resets_each_day():
    """-3R every day at 1% risk: never hits the 5% *daily* limit because the
    anchor resets at midnight, but eventually hits the 10% static total floor."""
    firm = _no_funded(_firm(daily_loss_pct=5.0, max_total_loss_pct=10.0))
    days = _iid_days([-3.0], [3.0])
    res = run_prop_sim(days, firm, risk_pct=1.0, n_paths=200, seed=11, block_size=1)
    assert res.p_bust_daily == 0.0
    assert res.p_bust_total == 1.0


# ---------------------------------------------------------------- min trading days
def test_min_days_gate():
    """Huge winners hit both targets on day 1; the 4-trading-day minimum per
    phase floors total days-to-pass at 8."""
    firm = _no_funded(FirmConfig.model_validate(dict(
        name="gate", account_size=100_000, challenge_fee=0.0,
        daily_loss_pct=None, max_total_loss_pct=10.0,
        phases=[
            PhaseRule(name="p1", profit_target_pct=10.0, min_trading_days=4),
            PhaseRule(name="p2", profit_target_pct=5.0, min_trading_days=4),
        ],
    )))
    days = _iid_days([20.0], [0.1])  # +20R at 1% risk = +20% in one trade
    res = run_prop_sim(days, firm, risk_pct=1.0, n_paths=300, seed=5, block_size=1)
    assert res.p_pass == 1.0
    assert res.days_to_pass_median == 8
    assert res.days_to_pass_p10 == 8 and res.days_to_pass_p90 == 8


# ---------------------------------------------------------------- analytic cases
def test_zero_edge_symmetric_gamblers_ruin():
    """Symmetric +/-1R walk, barriers at +10R (target) and -10R (total loss):
    P(pass) = L/(L+T) = 0.5 exactly."""
    firm = _no_funded(_firm())
    days = _iid_days([1.0, -1.0], [0.0, 1.0])
    res = run_prop_sim(days, firm, risk_pct=1.0, n_paths=20_000, seed=42, block_size=1)
    assert res.p_timeout == 0.0
    assert res.p_pass == pytest.approx(0.5, abs=0.02)
    assert res.p_bust_total == pytest.approx(0.5, abs=0.02)


def test_biased_gamblers_ruin_matches_analytic():
    """p=0.6 win +1R / lose -1R, barriers T=L=10R:
    P(pass) = (1-(q/p)^L) / (1-(q/p)^(L+T)) ~= 0.98292."""
    p_win, L, T = 0.6, 10, 10
    qp = (1 - p_win) / p_win
    analytic = (1 - qp**L) / (1 - qp ** (L + T))
    firm = _no_funded(_firm())
    # iid sampling with the right win probability: 3 winners, 2 losers
    days = _iid_days([1.0, 1.0, 1.0, -1.0, -1.0], [0.0, 0.0, 0.0, 1.0, 1.0])
    res = run_prop_sim(days, firm, risk_pct=1.0, n_paths=20_000, seed=123, block_size=1)
    assert res.p_pass == pytest.approx(analytic, abs=0.01)


# ---------------------------------------------------------------- determinism & sweep
def test_deterministic_given_seed():
    firm = _no_funded(_firm(daily_loss_pct=5.0))
    df = generate_sample_trades(n=300, seed=1)
    days = group_trades_by_day(df, tz=firm.timezone)
    a = run_prop_sim(days, firm, 1.0, n_paths=2000, seed=99)
    b = run_prop_sim(days, firm, 1.0, n_paths=2000, seed=99)
    assert a.to_dict() == b.to_dict()


def test_sweep_risk_levels():
    assert sweep_risks(0.25, 2.0, 0.25) == [0.25, 0.5, 0.75, 1.0, 1.25, 1.5, 1.75, 2.0]


def test_higher_risk_increases_bust_probability():
    firm = load_firm("ftmo_100k_2step")
    df = generate_sample_trades(n=600, win_rate=0.45, reward_r=1.8, mae_r=1.5, seed=2)
    days = group_trades_by_day(df, tz=firm.timezone)
    lo = run_prop_sim(days, firm, 0.5, n_paths=4000, seed=10, simulate_funded=False)
    hi = run_prop_sim(days, firm, 2.0, n_paths=4000, seed=10, simulate_funded=False)
    assert hi.p_bust_daily + hi.p_bust_total > lo.p_bust_daily + lo.p_bust_total


def test_sample_generator_properties():
    df = generate_sample_trades(n=1000, win_rate=0.5, reward_r=2.0, mae_r=1.5, seed=42)
    assert len(df) == 1000
    assert (df["r_multiple"] > 0).mean() == pytest.approx(0.5, abs=0.05)
    losers = df[df["r_multiple"] < 0]
    assert (losers["mae_r"] >= -losers["r_multiple"] - 1e-9).all()
    assert df["mae_r"].max() <= 1.5 + 0.6  # bounded by mae_r param (+|r| jitter guard)
    assert df["entry_time"].dt.tz is not None
