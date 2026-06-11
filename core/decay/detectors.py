"""Per-strategy decay detectors.

- CUSUM control chart on trade R vs the historical mean (alert when the
  cumulative drift exceeds 3*sigma*sqrt(n)).
- Drawdown-envelope check vs the strategy's own Monte Carlo drawdown
  distribution (p95 -> REDUCED, p99 -> SUSPENDED).
- Kolmogorov-Smirnov distribution-shift test on the last 30 trades.
- Regime-mismatch detector: suppresses decay alerts when current
  underperformance is expected for the active regime mix.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd
from scipy import stats


@dataclass(frozen=True)
class CusumResult:
    drift: float  # most negative cumulative deviation sum (R)
    threshold: float  # 3 * sigma * sqrt(n)
    z: float  # |drift| / (sigma * sqrt(n))
    triggered: bool

    def to_dict(self) -> dict:
        return {k: getattr(self, k) for k in ("drift", "threshold", "z", "triggered")}


def cusum_check(live_r: np.ndarray, hist_mean: float, hist_std: float,
                z_alert: float = 3.0) -> CusumResult:
    """One-sided (downside) CUSUM of live trade R against the historical mean."""
    live_r = np.asarray(live_r, dtype=np.float64)
    n = len(live_r)
    if n == 0 or hist_std <= 0:
        return CusumResult(0.0, 0.0, 0.0, False)
    dev = live_r - hist_mean
    cusum = np.cumsum(dev)
    drift = float(min(cusum.min(), 0.0))  # worst downside cumulative drift
    scale = hist_std * np.sqrt(n)
    z = abs(drift) / scale
    return CusumResult(drift=drift, threshold=z_alert * scale, z=float(z),
                       triggered=bool(z >= z_alert))


@dataclass(frozen=True)
class DDEnvelopeResult:
    live_dd_r: float
    p95_dd_r: float
    p99_dd_r: float
    level: str  # OK / P95 / P99

    def to_dict(self) -> dict:
        return {k: getattr(self, k) for k in ("live_dd_r", "p95_dd_r", "p99_dd_r", "level")}


def mc_dd_distribution(hist_r: np.ndarray, n_trades: int, n_paths: int = 5000,
                       seed: int = 42) -> np.ndarray:
    """Bootstrap max-drawdown (R) distribution for sequences of n_trades."""
    rng = np.random.default_rng(seed)
    idx = rng.integers(0, len(hist_r), size=(n_paths, n_trades))
    cum = np.cumsum(hist_r[idx], axis=1)
    dd = (np.maximum.accumulate(cum, axis=1) - cum).max(axis=1)
    return dd


def current_drawdown_r(live_r: np.ndarray) -> float:
    cum = np.cumsum(live_r)
    peak = np.maximum.accumulate(np.concatenate(([0.0], cum)))[1:]
    return float((peak - cum).max()) if len(cum) else 0.0


def dd_envelope_check(live_r: np.ndarray, hist_r: np.ndarray,
                      n_paths: int = 5000, seed: int = 42) -> DDEnvelopeResult:
    """Compare the live drawdown to the strategy's own MC DD envelope."""
    live_r = np.asarray(live_r, dtype=np.float64)
    hist_r = np.asarray(hist_r, dtype=np.float64)
    live_dd = current_drawdown_r(live_r)
    dist = mc_dd_distribution(hist_r, max(len(live_r), 1), n_paths=n_paths, seed=seed)
    p95, p99 = float(np.percentile(dist, 95)), float(np.percentile(dist, 99))
    level = "OK"
    if live_dd >= p99:
        level = "P99"
    elif live_dd >= p95:
        level = "P95"
    return DDEnvelopeResult(live_dd_r=live_dd, p95_dd_r=p95, p99_dd_r=p99, level=level)


@dataclass(frozen=True)
class KSResult:
    statistic: float
    p_value: float
    n_recent: int
    shifted: bool

    def to_dict(self) -> dict:
        return {k: getattr(self, k) for k in ("statistic", "p_value", "n_recent", "shifted")}


def ks_shift_check(live_r: np.ndarray, hist_r: np.ndarray, window: int = 30,
                   alpha: float = 0.05) -> KSResult:
    """Two-sample KS test: last `window` live trades vs the historical R distribution."""
    recent = np.asarray(live_r, dtype=np.float64)[-window:]
    if len(recent) < 10:
        return KSResult(0.0, 1.0, len(recent), False)
    stat, p = stats.ks_2samp(recent, np.asarray(hist_r, dtype=np.float64))
    return KSResult(float(stat), float(p), len(recent), bool(p < alpha))


@dataclass(frozen=True)
class RegimeMismatchResult:
    expected_r: float  # regime-weighted expected expectancy for live trades
    observed_r: float
    hist_mean: float
    regime_expected: bool  # underperformance explained by adverse regime mix

    def to_dict(self) -> dict:
        return {k: getattr(self, k) for k in
                ("expected_r", "observed_r", "hist_mean", "regime_expected")}


def regime_mismatch_check(
    live_trades: pd.DataFrame,
    regime_expectancy: dict[str, float],
    hist_mean: float,
    tolerance_r: float = 0.10,
) -> RegimeMismatchResult:
    """If live trades happened in regimes where the strategy historically earns
    less, the regime-conditional expectation explains the dip and decay alerts
    should be suppressed.

    live_trades needs columns regime, r_multiple."""
    if "regime" not in live_trades.columns or live_trades.empty:
        return RegimeMismatchResult(hist_mean, float(live_trades["r_multiple"].mean())
                                    if len(live_trades) else 0.0, hist_mean, False)
    expected = float(np.mean([regime_expectancy.get(reg, hist_mean)
                              for reg in live_trades["regime"]]))
    observed = float(live_trades["r_multiple"].mean())
    # regime-expected if observed is within tolerance of the regime-conditional
    # expectation AND that expectation is materially below the full-sample mean
    regime_expected = (expected < hist_mean - 1e-9) and (observed >= expected - tolerance_r)
    return RegimeMismatchResult(expected_r=expected, observed_r=observed,
                                hist_mean=hist_mean, regime_expected=regime_expected)
