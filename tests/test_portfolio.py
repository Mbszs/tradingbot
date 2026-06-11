"""Module 5 (portfolio) tests."""
from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from core.portfolio.corr import build_cov, nearest_psd, worse_of_correlations
from core.portfolio.frontier import random_weight_frontier
from core.portfolio.objective import combine_portfolio_trades, optimize_portfolio
from core.portfolio.weights import (
    PortfolioCaps,
    StrategyMeta,
    erc_weights,
    inverse_vol_weights,
    max_sharpe_weights,
    risk_contributions,
)
from core.survival.firm import load_firm
from core.survival.sample import generate_sample_trades

NAMES = ["a", "b", "c", "d"]


def _corr(vals: np.ndarray) -> pd.DataFrame:
    return pd.DataFrame(vals, index=NAMES, columns=NAMES)


# ---------------------------------------------------------------- corr
def test_worse_of_correlations_takes_max():
    full = _corr(np.eye(4) * 0.8 + 0.2)
    crisis_vals = np.full((4, 4), 0.9)
    np.fill_diagonal(crisis_vals, 1.0)
    crisis = _corr(crisis_vals)
    worse = worse_of_correlations(full, crisis)
    off_diag = worse.to_numpy()[~np.eye(4, dtype=bool)]
    assert (off_diag >= 0.2 - 1e-9).all()
    assert off_diag.max() >= 0.85  # crisis dominates
    assert np.allclose(np.diag(worse), 1.0)


def test_nearest_psd_repairs():
    bad = np.array([[1.0, 0.9, -0.9], [0.9, 1.0, 0.9], [-0.9, 0.9, 1.0]])
    fixed = nearest_psd(bad)
    assert np.linalg.eigvalsh(fixed).min() >= -1e-10
    assert np.allclose(np.diag(fixed), 1.0)


# ---------------------------------------------------------------- weights
def test_inverse_vol_with_cap():
    vols = pd.Series([0.05, 0.5, 0.5, 0.5], index=NAMES)  # 'a' would get ~77% uncapped
    w = inverse_vol_weights(vols, PortfolioCaps(per_strategy=0.30))
    assert w.sum() == pytest.approx(1.0)
    assert w["a"] == pytest.approx(0.30, abs=1e-9)
    assert (w <= 0.30 + 1e-9).all()


def test_erc_equalizes_risk_contributions():
    vols = pd.Series([0.1, 0.2, 0.3, 0.4], index=NAMES)
    cov = build_cov(vols, _corr(np.eye(4)))
    w = erc_weights(cov, PortfolioCaps(per_strategy=0.6))
    rc = risk_contributions(w.to_numpy(), cov.to_numpy())
    assert rc.max() - rc.min() < 1e-4
    # uncorrelated ERC = inverse vol
    iv = (1 / vols) / (1 / vols).sum()
    assert np.allclose(w.to_numpy(), iv.to_numpy(), atol=0.01)


def test_max_sharpe_caps_and_groups():
    mu = pd.Series([0.5, 0.1, 0.1, 0.1], index=NAMES)
    cov = build_cov(pd.Series([0.2] * 4, index=NAMES), _corr(np.eye(4)))
    meta = {
        "a": StrategyMeta("trend", "EURUSD"), "b": StrategyMeta("trend", "GBPUSD"),
        "c": StrategyMeta("mr", "GBPUSD"), "d": StrategyMeta("mr", "XAUUSD"),
    }
    caps = PortfolioCaps(per_strategy=0.30, per_edge_source=0.50, per_instrument=0.40)
    w = max_sharpe_weights(mu, cov, caps, meta)
    assert w.sum() == pytest.approx(1.0)
    assert (w <= 0.30 + 1e-6).all()
    assert w["a"] + w["b"] <= 0.50 + 1e-6  # edge-source cap (trend)
    assert w["b"] + w["c"] <= 0.40 + 1e-6  # instrument cap (GBPUSD)
    assert w["a"] == w.max()  # highest mu gets the most


def test_max_sharpe_infeasible_caps_raise():
    mu = pd.Series([0.5, 0.1, 0.1, 0.1], index=NAMES)
    cov = build_cov(pd.Series([0.2] * 4, index=NAMES), _corr(np.eye(4)))
    meta = {  # EURUSD cap 0.4 + mr edge cap 0.5 < 1.0 -> infeasible
        "a": StrategyMeta("trend", "EURUSD"), "b": StrategyMeta("trend", "EURUSD"),
        "c": StrategyMeta("mr", "GBPUSD"), "d": StrategyMeta("mr", "XAUUSD"),
    }
    with pytest.raises(ValueError, match="infeasible"):
        max_sharpe_weights(mu, cov, PortfolioCaps(0.30, 0.50, 0.40), meta)


# ---------------------------------------------------------------- frontier
@pytest.fixture(scope="module")
def streams() -> pd.DataFrame:
    rng = np.random.default_rng(5)
    idx = pd.date_range("2024-01-01", periods=400, freq="B", tz="UTC")
    return pd.DataFrame({
        "a": rng.normal(0.5, 1.5, 400),
        "b": rng.normal(0.3, 1.0, 400),
        "c": rng.normal(0.2, 0.8, 400),
    }, index=idx)


def test_frontier_shape_and_pareto(streams):
    f = random_weight_frontier(streams, n_portfolios=2000, seed=42)
    assert len(f) == 2000
    assert np.allclose(f[["a", "b", "c"]].sum(axis=1), 1.0)
    pareto = f[f["pareto"]].sort_values("max_dd")
    assert len(pareto) >= 1
    assert pareto["cagr"].is_monotonic_increasing  # frontier is monotone in DD


# ---------------------------------------------------------------- objective
def _three_strategies() -> dict[str, pd.DataFrame]:
    return {
        "alpha": generate_sample_trades(n=500, win_rate=0.50, reward_r=2.0, mae_r=1.5, seed=11),
        "beta": generate_sample_trades(n=500, win_rate=0.55, reward_r=1.5, mae_r=1.2, seed=22),
        "gamma": generate_sample_trades(n=500, win_rate=0.45, reward_r=2.2, mae_r=1.4, seed=33),
    }


def test_combine_portfolio_trades_scales_r():
    tbs = _three_strategies()
    combined = combine_portfolio_trades(tbs, {"alpha": 0.5, "beta": 0.5, "gamma": 0.0})
    assert len(combined) == 1000  # gamma excluded
    assert combined["r_multiple"].abs().max() <= tbs["alpha"]["r_multiple"].abs().max() * 0.5 + 1e-9


def test_optimize_portfolio_end_to_end():
    tbs = _three_strategies()
    from core.dna.analyzer import daily_r_stream
    streams = pd.DataFrame({k: daily_r_stream(v) for k, v in tbs.items()})
    firm = load_firm("ftmo_100k_2step")
    caps = PortfolioCaps(per_strategy=0.40)  # 3 strategies need >= 1/3 each
    res = optimize_portfolio(streams, tbs, firm, caps=caps,
                             risk_grid=(0.5, 1.0, 2.0), n_frontier=1000,
                             n_paths=2000, seed=42)
    assert res.best is not None
    assert res.best.feasible
    assert res.best.p_breach_total_6mo < 0.05
    assert res.best.p_breach_daily < 0.02
    assert res.best.objective > 0
    assert abs(sum(res.best.weights.values()) - 1.0) < 1e-6
    # all (candidate, risk) pairs evaluated
    assert len(res.candidates) == 6 * 3  # 3 schemes + 3 pareto, x 3 risks
    # infeasible candidates are excluded from best
    infeasible = [c for c in res.candidates if not c.feasible]
    if infeasible:
        assert res.best.objective >= max((c.objective for c in res.candidates if c.feasible))
