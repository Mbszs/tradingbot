"""Regime features per instrument/timeframe.

Computed on an OHLC DataFrame (columns open/high/low/close, DatetimeIndex):
ADX(14), 50-bar regression R^2 and slope, ATR percentile vs a trailing window
(252 daily bars by default), vol-of-vol, Hurst exponent (rescaled range, 100
bars), and Kaufman efficiency ratio.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

OHLC_COLS = ("open", "high", "low", "close")


def true_range(df: pd.DataFrame) -> pd.Series:
    prev_close = df["close"].shift(1)
    tr = pd.concat([
        df["high"] - df["low"],
        (df["high"] - prev_close).abs(),
        (df["low"] - prev_close).abs(),
    ], axis=1).max(axis=1)
    return tr


def atr(df: pd.DataFrame, period: int = 14) -> pd.Series:
    return true_range(df).ewm(alpha=1 / period, adjust=False, min_periods=period).mean()


def adx(df: pd.DataFrame, period: int = 14) -> pd.Series:
    """Wilder's ADX."""
    up = df["high"].diff()
    down = -df["low"].diff()
    plus_dm = pd.Series(np.where((up > down) & (up > 0), up, 0.0), index=df.index)
    minus_dm = pd.Series(np.where((down > up) & (down > 0), down, 0.0), index=df.index)
    tr_smooth = true_range(df).ewm(alpha=1 / period, adjust=False, min_periods=period).mean()
    plus_di = 100 * plus_dm.ewm(alpha=1 / period, adjust=False, min_periods=period).mean() / tr_smooth
    minus_di = 100 * minus_dm.ewm(alpha=1 / period, adjust=False, min_periods=period).mean() / tr_smooth
    dx = 100 * (plus_di - minus_di).abs() / (plus_di + minus_di).replace(0, np.nan)
    return dx.ewm(alpha=1 / period, adjust=False, min_periods=period).mean()


def rolling_linreg(y: pd.Series, window: int = 50) -> tuple[pd.Series, pd.Series]:
    """O(n) rolling least-squares of y on bar index: (slope per bar, R^2)."""
    x = np.arange(window, dtype=np.float64)
    x_mean = x.mean()
    x_var = ((x - x_mean) ** 2).sum()

    y_arr = y.to_numpy(dtype=np.float64)
    s_y = y.rolling(window).sum().to_numpy()
    s_y2 = (y**2).rolling(window).sum().to_numpy()
    # rolling sum of x_k * y_{t-window+1+k} via convolution
    s_xy = np.convolve(y_arr, x[::-1], mode="full")[window - 1 : len(y_arr)]
    s_xy = np.concatenate([np.full(window - 1, np.nan), s_xy])

    n = window
    cov = s_xy - x_mean * s_y
    slope = cov / x_var
    y_var = s_y2 - s_y**2 / n
    with np.errstate(invalid="ignore", divide="ignore"):
        r2 = np.where(y_var > 1e-18, cov**2 / (x_var * y_var), 0.0)
    return (pd.Series(slope, index=y.index, name="slope"),
            pd.Series(np.clip(r2, 0, 1), index=y.index, name="r2"))


def rolling_percentile_rank(s: pd.Series, window: int = 252) -> pd.Series:
    """Percentile rank of the latest value within the trailing window (0..1)."""
    def _rank(a: np.ndarray) -> float:
        return float((a[:-1] <= a[-1]).mean())
    return s.rolling(window, min_periods=max(window // 4, 10)).apply(_rank, raw=True)


def hurst_rs(returns: pd.Series, window: int = 100) -> pd.Series:
    """Rolling Hurst exponent via the rescaled-range statistic."""
    def _hurst(a: np.ndarray) -> float:
        sd = a.std()
        if sd < 1e-12:
            return 0.5
        dev = np.cumsum(a - a.mean())
        rs = (dev.max() - dev.min()) / sd
        if rs <= 0:
            return 0.5
        return float(np.log(rs) / np.log(len(a)))
    return returns.rolling(window).apply(_hurst, raw=True)


def kaufman_er(close: pd.Series, period: int = 10) -> pd.Series:
    """Kaufman efficiency ratio: |net change| / sum of |bar changes| (0..1)."""
    change = (close - close.shift(period)).abs()
    volatility = close.diff().abs().rolling(period).sum()
    return (change / volatility.replace(0, np.nan)).clip(0, 1)


def compute_features(
    df: pd.DataFrame,
    adx_period: int = 14,
    linreg_window: int = 50,
    atr_pct_window: int = 252,
    hurst_window: int = 100,
    er_period: int = 10,
    volvol_window: int = 20,
) -> pd.DataFrame:
    """Full regime feature frame, indexed like the input bars."""
    missing = [c for c in OHLC_COLS if c not in df.columns]
    if missing:
        raise ValueError(f"OHLC frame missing columns: {missing}")

    log_close = np.log(df["close"])
    returns = log_close.diff()
    atr_s = atr(df, adx_period)
    slope, r2 = rolling_linreg(log_close, linreg_window)
    atr_rel = atr_s / df["close"]
    volvol = atr_rel.pct_change().rolling(volvol_window).std()

    feats = pd.DataFrame({
        "adx": adx(df, adx_period),
        "slope": slope,
        "r2": r2,
        "atr": atr_s,
        "atr_pctile": rolling_percentile_rank(atr_rel, atr_pct_window),
        "volvol": volvol,
        "volvol_pctile": rolling_percentile_rank(volvol, atr_pct_window),
        "hurst": hurst_rs(returns, hurst_window),
        "efficiency_ratio": kaufman_er(df["close"], er_period),
        "ret_1": returns,
    }, index=df.index)
    return feats
