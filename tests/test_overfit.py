"""Module 2 (overfit) tests."""
from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from core.overfit.cpcv import cpcv, make_groups, purged_train_indices
from core.overfit.deflated_sharpe import deflated_sharpe, expected_max_sharpe
from core.overfit.perturb import mc_perturbation
from core.overfit.plateau import plateau_analysis
from core.overfit.score import robustness_battery
from core.overfit.walkforward import walk_forward
from core.survival.sample import generate_sample_trades


def _edge_stream(n: int, mu: float, seed: int = 0) -> np.ndarray:
    rng = np.random.default_rng(seed)
    return rng.normal(mu, 1.0, n)


# ---------------------------------------------------------------- walk-forward
def test_wfe_near_one_for_stationary_edge():
    r = _edge_stream(2000, 0.5, seed=1)
    res = walk_forward(r)
    assert len(res.windows) >= 6
    assert res.wfe == pytest.approx(1.0, abs=0.25)
    assert res.score > 0.7


def test_wfe_collapses_for_decaying_edge():
    r = np.concatenate([_edge_stream(1000, 0.8, seed=2), _edge_stream(1000, -0.2, seed=3)])
    res = walk_forward(r)
    assert res.wfe < 0.6


def test_wfe_zero_when_is_negative():
    r = _edge_stream(500, -0.5, seed=4)
    assert walk_forward(r).wfe == 0.0


# ---------------------------------------------------------------- cpcv
def test_cpcv_combo_count_and_groups():
    r = _edge_stream(500, 0.3, seed=5)
    res = cpcv(r, n_groups=10, n_test_groups=2)
    assert len(res.combo_sharpes) == 45  # C(10,2)
    groups = make_groups(500, 10)
    assert sum(len(g) for g in groups) == 500
    assert all(len(g) == 50 for g in groups)


def test_purge_and_embargo_indices():
    test_idx = np.arange(20, 30)
    train = purged_train_indices(100, test_idx, purge_gap=3, embargo=5)
    # purged before: 17-19; test: 20-29; purged+embargo after: 30-37
    assert not np.intersect1d(train, np.arange(17, 38)).size
    assert 16 in train and 38 in train


def test_cpcv_p5_positive_for_strong_edge():
    res = cpcv(_edge_stream(1000, 0.5, seed=6))
    assert res.p5_sharpe > 0
    assert res.frac_negative == 0.0


def test_cpcv_detects_fragile_edge():
    # edge concentrated in the first 10% of history
    r = np.concatenate([_edge_stream(100, 3.0, seed=7), _edge_stream(900, 0.0, seed=8)])
    res = cpcv(r)
    assert res.frac_negative > 0.2
    assert res.score < 0.3


# ---------------------------------------------------------------- perturbation
def test_mc_perturbation_deterministic_and_sane():
    r = _edge_stream(600, 0.5, seed=9)
    a = mc_perturbation(r, seed=42)
    b = mc_perturbation(r, seed=42)
    assert a.to_dict() == b.to_dict()
    assert a.p_positive > 0.95
    assert a.score > 0.5


def test_mc_perturbation_zero_edge():
    r = _edge_stream(600, 0.0, seed=10)
    res = mc_perturbation(r, seed=42)
    assert res.p_positive < 0.5  # slippage pushes zero edge negative
    assert res.score < 0.4


# ---------------------------------------------------------------- plateau
def _grid(metric_fn) -> pd.DataFrame:
    rows = [{"fast": f, "slow": s, "metric": metric_fn(f, s)}
            for f in range(8, 13) for s in range(40, 65, 5)]
    return pd.DataFrame(rows)


def test_plateau_flat_beats_needle():
    flat = _grid(lambda f, s: 0.5)
    needle = _grid(lambda f, s: 1.0 if (f, s) == (10, 50) else -0.2)
    assert plateau_analysis(flat).score == pytest.approx(1.0)
    assert plateau_analysis(needle).score < 0.5


def test_plateau_negative_peak_scores_zero():
    df = _grid(lambda f, s: -0.1)
    assert plateau_analysis(df).score == 0.0


# ---------------------------------------------------------------- deflated sharpe
def test_expected_max_sharpe_grows_with_trials():
    v = 0.01
    assert expected_max_sharpe(1, v) == 0.0
    assert expected_max_sharpe(100, v) > expected_max_sharpe(10, v) > 0


def test_dsr_single_trial_strong_edge():
    res = deflated_sharpe(_edge_stream(1000, 0.5, seed=11), n_trials=1)
    assert res.sr_excess > 0
    assert res.dsr > 0.99


def test_dsr_many_trials_rejects_weak_edge():
    r = _edge_stream(200, 0.05, seed=12)
    res = deflated_sharpe(r, n_trials=5000, trial_sr_var=0.05)
    assert res.sr_excess < 0
    assert res.dsr < 0.5


# ---------------------------------------------------------------- composite
def test_composite_score_good_strategy():
    df = generate_sample_trades(n=600, win_rate=0.5, reward_r=2.0, mae_r=1.5, seed=42)
    grid = _grid(lambda f, s: 0.4 + 0.01 * (f == 10))
    report = robustness_battery(df, param_results=grid, n_trials=3,
                                pnl_share_by_regime={"trend": 0.4, "chop": 0.3, "quiet": 0.3})
    assert report.verdict == "PASS"
    assert report.score >= 70
    assert set(report.components) == {"wfe", "cpcv", "mc", "plateau", "cost_stress", "regime_div", "trade_count"}


def test_composite_low_trade_count_caps_at_40():
    df = generate_sample_trades(n=90, seed=1)
    report = robustness_battery(df)
    assert report.score <= 40
    assert any("capped" in g for g in report.gates)


def test_composite_negative_dsr_rejects():
    rng = np.random.default_rng(13)
    df = pd.DataFrame({"r_multiple": rng.normal(0.02, 1.0, 400)})
    report = robustness_battery(df, n_trials=10_000)
    assert report.verdict == "REJECT"
