"""Module 3 (regime) tests."""
from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from core.regime.features import adx, compute_features, hurst_rs, kaufman_er, rolling_linreg
from core.regime.hmm import fit_hmm
from core.regime.matrix import (
    label_trades_with_regime,
    pnl_share_by_regime,
    recommendations,
    regime_strategy_matrix,
)
from core.regime.rules import classify_rules
from core.regime.sample_data import generate_sample_ohlc


@pytest.fixture(scope="module")
def ohlc() -> pd.DataFrame:
    return generate_sample_ohlc(seed=42)


@pytest.fixture(scope="module")
def features(ohlc) -> pd.DataFrame:
    return compute_features(ohlc)


# ---------------------------------------------------------------- features
def test_adx_higher_in_trend_than_noise():
    trend = generate_sample_ohlc([("trend_up_quiet", 400)], seed=1)
    chop = generate_sample_ohlc([("mean_revert", 400)], seed=1)
    assert adx(trend).iloc[-100:].mean() > adx(chop).iloc[-100:].mean()


def test_rolling_linreg_perfect_line():
    y = pd.Series(np.linspace(0, 10, 200))
    slope, r2 = rolling_linreg(y, 50)
    assert slope.iloc[-1] == pytest.approx(10 / 199, rel=1e-6)
    assert r2.iloc[-1] == pytest.approx(1.0, abs=1e-9)


def test_kaufman_er_extremes():
    line = pd.Series(np.arange(100, dtype=float) + 1000)
    assert kaufman_er(line).iloc[-1] == pytest.approx(1.0)
    rng = np.random.default_rng(3)
    noise = pd.Series(1000 + np.where(np.arange(300) % 2 == 0, 1.0, 0.0) + rng.normal(0, 0.01, 300))
    assert kaufman_er(noise).iloc[-50:].mean() < 0.3


def test_hurst_separates_persistence():
    rng = np.random.default_rng(4)
    trending = pd.Series(rng.normal(0.3, 1.0, 800))  # strong drift -> persistent cum path
    x, prev = [], 0.0
    for _ in range(800):  # AR(1) with negative coefficient -> anti-persistent
        prev = -0.6 * prev + rng.normal(0, 1)
        x.append(prev)
    antipersistent = pd.Series(x)
    h_trend = hurst_rs(trending, 100).dropna().mean()
    h_anti = hurst_rs(antipersistent, 100).dropna().mean()
    assert h_trend > h_anti
    assert h_anti < 0.5


def test_compute_features_columns(features):
    expected = {"adx", "slope", "r2", "atr", "atr_pctile", "volvol",
                "volvol_pctile", "hurst", "efficiency_ratio", "ret_1"}
    assert expected <= set(features.columns)
    assert features["atr_pctile"].dropna().between(0, 1).all()


# ---------------------------------------------------------------- rules
def test_rule_classifier_finds_crisis_and_trend(ohlc, features):
    labels = classify_rules(features)
    df = pd.concat([labels, ohlc["segment"]], axis=1)

    crisis = df[df["segment"] == "crisis"]["regime"]
    assert (crisis == "CRISIS").mean() > 0.5

    trend = df[df["segment"] == "trend_up_quiet"]["regime"].iloc[100:]
    assert trend.isin(["LOW_VOL_TREND", "HIGH_VOL_TREND"]).mean() > 0.4

    quiet_dirs = df[df["segment"] == "trend_up_quiet"]["direction"].iloc[100:]
    assert (quiet_dirs == "BULL").mean() > 0.8


def test_rule_classifier_quiet_vs_chop(features, ohlc):
    labels = classify_rules(features)
    df = pd.concat([labels, ohlc["segment"]], axis=1)
    quiet = df[df["segment"] == "quiet"]["regime"].iloc[60:]
    assert quiet.isin(["SIDEWAYS_QUIET", "MEAN_REVERT", "LOW_VOL_TREND"]).mean() > 0.6
    assert (quiet == "SIDEWAYS_QUIET").sum() > 0


# ---------------------------------------------------------------- hmm
def test_hmm_fit_deterministic_and_valid(features):
    labels = classify_rules(features)["regime"]
    a = fit_hmm(features, labels, n_states=3, n_restarts=4, seed=7)
    b = fit_hmm(features, labels, n_states=3, n_restarts=4, seed=7)
    assert a.log_likelihood == pytest.approx(b.log_likelihood)
    assert a.transition_matrix.shape == (3, 3)
    np.testing.assert_allclose(a.transition_matrix.sum(axis=1), 1.0, atol=1e-8)
    assert set(a.states.unique()) <= {0, 1, 2}
    assert len(a.state_names) == 3


def test_hmm_restarts_improve_or_match(features):
    one = fit_hmm(features, None, n_states=3, n_restarts=1, seed=7)
    many = fit_hmm(features, None, n_states=3, n_restarts=6, seed=7)
    assert many.log_likelihood >= one.log_likelihood - 1e-6


# ---------------------------------------------------------------- matrix
def _toy_trades_and_regimes():
    idx = pd.date_range("2024-01-01", periods=100, freq="D", tz="UTC")
    regimes = pd.Series(["LOW_VOL_TREND"] * 50 + ["SIDEWAYS_CHOP"] * 50, index=idx)
    entry = list(idx[5:45]) + list(idx[55:95])
    r = [1.0] * 40 + [-0.5] * 40  # wins in trend, losses in chop
    trades = pd.DataFrame({"strategy": "trendy", "entry_time": entry, "r_multiple": r})
    return trades, regimes


def test_regime_matrix_and_recommendations():
    trades, regimes = _toy_trades_and_regimes()
    m = regime_strategy_matrix(trades, regimes)
    trend_row = m[(m["regime"] == "LOW_VOL_TREND")].iloc[0]
    chop_row = m[(m["regime"] == "SIDEWAYS_CHOP")].iloc[0]
    assert trend_row["expectancy_r"] == pytest.approx(1.0)
    assert chop_row["expectancy_r"] == pytest.approx(-0.5)
    assert trend_row["win_pct"] == 1.0 and chop_row["win_pct"] == 0.0

    recs = {r.regime: r.action for r in recommendations(m)}
    assert recs["LOW_VOL_TREND"] == "enable"
    assert recs["SIDEWAYS_CHOP"] == "disable"

    shares = pnl_share_by_regime(m, "trendy")
    assert shares["LOW_VOL_TREND"] > 0
    assert shares["SIDEWAYS_CHOP"] == 0.0


def test_label_trades_before_first_bar_unknown():
    trades, regimes = _toy_trades_and_regimes()
    early = pd.DataFrame({"strategy": "s", "entry_time": [pd.Timestamp("2023-12-01", tz="UTC")],
                          "r_multiple": [1.0]})
    labeled = label_trades_with_regime(early, regimes)
    assert labeled["regime"].iloc[0] == "UNKNOWN"
