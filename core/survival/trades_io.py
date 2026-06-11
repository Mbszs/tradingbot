"""Trade list loading and trading-day grouping for the survival simulator.

Trades are grouped into trading days using the firm's reset timezone
(Europe/Prague for FTMO = midnight CET/CEST). The Monte Carlo block-bootstrap
resamples whole trading days so intra-day sequencing and day-level
autocorrelation are preserved, and the daily-loss check resets exactly at the
midnight snapshot boundary.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd

REQUIRED_COLS = ("r_multiple",)


@dataclass(frozen=True)
class DayGroupedTrades:
    """Trades flattened into contiguous per-day segments.

    day_ptr[i]:day_ptr[i+1] slices r/mae for source trading day i.
    r is the realized R-multiple; mae is the max adverse excursion in positive
    R units (the intra-trade floating-loss trough used for mid-trade
    daily-breach detection).
    """

    day_ptr: np.ndarray  # int64, len n_days+1
    r: np.ndarray  # float64, len n_trades
    mae: np.ndarray  # float64, len n_trades, >= 0

    @property
    def n_days(self) -> int:
        return len(self.day_ptr) - 1

    @property
    def n_trades(self) -> int:
        return len(self.r)


def load_trades_csv(path: str | Path) -> pd.DataFrame:
    """Load a trades CSV. Requires r_multiple; mae_r, mfe_r, entry_time optional."""
    df = pd.read_csv(path)
    missing = [c for c in REQUIRED_COLS if c not in df.columns]
    if missing:
        raise ValueError(f"trades csv missing columns: {missing}")
    if "entry_time" in df.columns:
        df["entry_time"] = pd.to_datetime(df["entry_time"], utc=True, format="mixed")
    if "exit_time" in df.columns:
        df["exit_time"] = pd.to_datetime(df["exit_time"], utc=True, format="mixed")
    return df


def _normalized_mae(df: pd.DataFrame) -> np.ndarray:
    """MAE in positive R units; at least the realized loss for losers."""
    r = df["r_multiple"].to_numpy(dtype=np.float64)
    if "mae_r" in df.columns:
        mae = np.abs(df["mae_r"].fillna(0.0).to_numpy(dtype=np.float64))
    else:
        mae = np.zeros_like(r)
    # A trade that closed at -X R must have floated at least -X R.
    return np.maximum(mae, np.maximum(-r, 0.0))


def group_trades_by_day(
    df: pd.DataFrame,
    tz: str = "Europe/Prague",
    trades_per_day: int = 3,
) -> DayGroupedTrades:
    """Group trades into firm-timezone trading days.

    Uses entry_time converted to the firm timezone (midnight there is the
    daily-loss reset). Without timestamps, falls back to synthetic days of
    `trades_per_day` consecutive trades.
    """
    mae = _normalized_mae(df)
    r = df["r_multiple"].to_numpy(dtype=np.float64)

    if "entry_time" in df.columns and df["entry_time"].notna().all():
        ts = pd.DatetimeIndex(df["entry_time"])
        if ts.tz is None:
            ts = ts.tz_localize("UTC")
        local_day = ts.tz_convert(tz).normalize()
        order = np.argsort(ts.values, kind="stable")
        r, mae = r[order], mae[order]
        day_keys = local_day.values[order]
        # contiguous run-length encode the sorted day keys
        boundaries = np.flatnonzero(day_keys[1:] != day_keys[:-1]) + 1
        day_ptr = np.concatenate(([0], boundaries, [len(r)])).astype(np.int64)
    else:
        n = len(r)
        starts = np.arange(0, n, trades_per_day, dtype=np.int64)
        day_ptr = np.concatenate((starts, [n]))

    return DayGroupedTrades(day_ptr=day_ptr, r=r, mae=mae)
