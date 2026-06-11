"""Module 4 (DNA) tests."""
from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from core.dna.analyzer import (
    analyze_strategy,
    convexity_metrics,
    correlation_vector,
    cost_sensitivity,
    daily_r_stream,
    infer_session,
    session_dependency,
    vol_exposure_beta,
)


def _trades(rs: list[float], start: str = "2024-01-01", per_day: int = 2,
            sessions: list[str] | None = None) -> pd.DataFrame:
    days = pd.bdate_range(start, periods=(len(rs) + per_day - 1) // per_day, tz="UTC")
    entry = [days[i // per_day] + pd.Timedelta(hours=8 + 4 * (i % per_day)) for i in range(len(rs))]
    df = pd.DataFrame({"entry_time": entry, "r_multiple": rs})
    if sessions:
        df["session"] = sessions
    return df


def test_daily_r_stream_sums_per_day():
    df = _trades([1.0, -0.5, 2.0, 1.0], per_day=2)
    s = daily_r_stream(df)
    assert len(s) == 2
    assert s.iloc[0] == pytest.approx(0.5)
    assert s.iloc[1] == pytest.approx(3.0)


def test_convexity_signs():
    rng = np.random.default_rng(1)
    convex = np.concatenate([np.full(80, -0.5), rng.uniform(2, 6, 20)])  # small losses, big wins
    concave = -convex
    c1, c2 = convexity_metrics(convex), convexity_metrics(concave)
    assert c1["skew"] > 0 > c2["skew"]
    assert c1["tail_ratio"] > 1 > c2["tail_ratio"]


def test_vol_exposure_beta_sign():
    idx = pd.date_range("2024-01-01", periods=200, freq="D", tz="UTC")
    rng = np.random.default_rng(2)
    atr = pd.Series(np.exp(np.cumsum(rng.normal(0, 0.05, 200))), index=idx)
    daily_r = pd.Series(atr.pct_change().fillna(0) * 10 + rng.normal(0, 0.01, 200), index=idx)
    beta = vol_exposure_beta(daily_r, atr)
    assert beta is not None and beta > 5


def test_correlation_full_vs_crisis():
    idx = pd.date_range("2024-01-01", periods=300, freq="D", tz="UTC")
    rng = np.random.default_rng(3)
    base = rng.normal(0, 1, 300)
    a = pd.Series(base + rng.normal(0, 0.1, 300), index=idx)
    # b is uncorrelated normally but tracks a during the crisis window
    b_vals = rng.normal(0, 1, 300)
    crisis = idx[200:260]
    b_vals[200:260] = base[200:260] + rng.normal(0, 0.1, 60)
    b = pd.Series(b_vals, index=idx)

    full = correlation_vector(a, {"b": b})
    cond = correlation_vector(a, {"b": b}, days_filter=crisis)
    assert cond["b"] > 0.9
    assert full["b"] < cond["b"]


def test_cost_sensitivity_monotone():
    r = np.array([0.3, 0.2, 0.25, 0.15] * 30)
    cs = cost_sensitivity(r, cost_r_1x=0.1)
    assert cs["1.0x"] > cs["1.5x"] > cs["2.0x"]
    assert cs["1.0x"] == pytest.approx(r.mean())
    assert cs["2.0x"] == pytest.approx(r.mean() - 0.1)


def test_session_inference_and_dependency():
    df = _trades([1.0] * 30 + [-1.0] * 30,
                 sessions=["london"] * 30 + ["newyork"] * 30)
    dep = session_dependency(df)
    assert dep["london"]["expectancy_r"] == 1.0
    assert dep["newyork"]["expectancy_r"] == -1.0

    hours = pd.Series(pd.to_datetime(["2024-01-01 03:00+00:00", "2024-01-01 09:00+00:00",
                                      "2024-01-01 15:00+00:00", "2024-01-01 23:00+00:00"]))
    assert infer_session(hours).tolist() == ["asia", "london", "newyork", "asia"]


def test_analyze_strategy_full_profile():
    rng = np.random.default_rng(4)
    rs_a = list(rng.choice([2.0, -1.0], 200, p=[0.5, 0.5]))
    rs_b = list(rng.choice([1.5, -1.0], 200, p=[0.5, 0.5]))
    ta, tb = _trades(rs_a), _trades(rs_b)
    streams = {"alpha": daily_r_stream(ta), "beta": daily_r_stream(tb)}

    matrix = pd.DataFrame([
        {"strategy": "alpha", "regime": "LOW_VOL_TREND", "n_trades": 120, "expectancy_r": 0.6},
        {"strategy": "alpha", "regime": "SIDEWAYS_CHOP", "n_trades": 60, "expectancy_r": -0.3},
    ])
    dna = analyze_strategy("alpha", ta, streams, regime_matrix=matrix,
                           edge_source="trend", cost_r_1x=0.1)
    assert dna.n_trades == 200
    assert dna.trades_per_week > 5
    assert "beta" in dna.correlations_full
    assert dna.best_regimes[0] == "LOW_VOL_TREND"
    assert dna.worst_regimes[0] == "SIDEWAYS_CHOP"
    assert any("SIDEWAYS_CHOP" in c for c in dna.failure_conditions)
    assert dna.to_dict()["edge_source"] == "trend"
