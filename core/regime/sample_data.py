"""Synthetic OHLC generator with engineered regime segments (for tests/demos)."""
from __future__ import annotations

import numpy as np
import pandas as pd

SEGMENT_PRESETS = {
    "trend_up_quiet": dict(drift=0.0008, vol=0.004, mr=0.0),
    "trend_down_quiet": dict(drift=-0.0008, vol=0.004, mr=0.0),
    "trend_up_vol": dict(drift=0.0012, vol=0.012, mr=0.0),
    "chop": dict(drift=0.0, vol=0.010, mr=0.0),
    "quiet": dict(drift=0.0, vol=0.002, mr=0.0),
    "mean_revert": dict(drift=0.0, vol=0.008, mr=0.35),
    "crisis": dict(drift=-0.004, vol=0.035, mr=0.0),
}


def generate_sample_ohlc(
    segments: list[tuple[str, int]] | None = None,
    start: str = "2022-01-03",
    freq: str = "B",
    s0: float = 100.0,
    seed: int = 42,
) -> pd.DataFrame:
    """Generate OHLC bars from named (segment, n_bars) presets.

    Adds a 'segment' column with the generating preset for ground-truth checks.
    """
    if segments is None:
        segments = [("trend_up_quiet", 300), ("chop", 250), ("crisis", 60),
                    ("mean_revert", 250), ("quiet", 200), ("trend_up_vol", 250)]
    rng = np.random.default_rng(seed)

    log_p = np.log(s0)
    closes, names = [], []
    for name, n in segments:
        cfg = SEGMENT_PRESETS[name]
        level = log_p
        for _ in range(n):
            shock = rng.normal(cfg["drift"], cfg["vol"])
            log_p += shock - cfg["mr"] * (log_p - level)
            closes.append(log_p)
            names.append(name)
    close = np.exp(np.array(closes))

    n_total = len(close)
    idx = pd.date_range(start=start, periods=n_total, freq=freq, tz="UTC")
    intrabar = np.abs(rng.normal(0, 0.004, n_total)) + 0.001
    open_ = np.concatenate([[close[0]], close[:-1]])
    high = np.maximum(open_, close) * (1 + intrabar)
    low = np.minimum(open_, close) * (1 - intrabar)
    return pd.DataFrame({"open": open_, "high": high, "low": low, "close": close,
                         "segment": names}, index=idx)
