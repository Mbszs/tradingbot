"""Walk-forward engine: rolling IS/OOS windows and walk-forward efficiency.

Operates on a chronological per-trade R stream. Walk-forward efficiency (WFE)
is the ratio of out-of-sample to in-sample expectancy aggregated across
windows — a stationary edge gives WFE near 1, a curve-fit edge collapses
out-of-sample.

For parameterized re-optimization per window, pass `reoptimize_fn`: it
receives the IS slice and returns the OOS slice to evaluate (e.g. re-run the
backtest with re-fit parameters); by default the recorded trades are used.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

import numpy as np


@dataclass(frozen=True)
class WalkForwardWindow:
    is_start: int
    is_end: int  # exclusive; OOS = [is_end, oos_end)
    oos_end: int
    is_expectancy: float
    oos_expectancy: float


@dataclass(frozen=True)
class WalkForwardResult:
    windows: list[WalkForwardWindow]
    wfe: float  # aggregate OOS expectancy / aggregate IS expectancy
    score: float  # 0..1 component score

    def to_dict(self) -> dict:
        return {
            "wfe": self.wfe,
            "score": self.score,
            "n_windows": len(self.windows),
            "windows": [vars(w) for w in self.windows],
        }


def walk_forward(
    r: np.ndarray,
    n_windows: int = 8,
    oos_frac: float = 0.25,
    reoptimize_fn: Callable[[np.ndarray, np.ndarray], np.ndarray] | None = None,
) -> WalkForwardResult:
    """Rolling anchored-window walk-forward over a chronological R stream.

    The stream is cut into `n_windows` steps; each step's IS window is the
    preceding (1-oos_frac) span and the OOS window the following oos_frac span,
    rolled forward by the OOS length.
    """
    r = np.asarray(r, dtype=np.float64)
    n = len(r)
    if n < n_windows * 4:
        raise ValueError(f"need at least {n_windows * 4} trades for {n_windows} windows")

    oos_len = max(int(n / (n_windows + (1 - oos_frac) / oos_frac)), 2)
    is_len = max(int(oos_len * (1 - oos_frac) / oos_frac), 2)

    windows: list[WalkForwardWindow] = []
    start = 0
    while start + is_len + oos_len <= n and len(windows) < n_windows:
        is_slice = r[start : start + is_len]
        oos_slice = r[start + is_len : start + is_len + oos_len]
        if reoptimize_fn is not None:
            oos_slice = reoptimize_fn(is_slice, oos_slice)
        windows.append(WalkForwardWindow(
            is_start=start, is_end=start + is_len, oos_end=start + is_len + oos_len,
            is_expectancy=float(is_slice.mean()), oos_expectancy=float(oos_slice.mean()),
        ))
        start += oos_len

    is_total = float(np.mean([w.is_expectancy for w in windows]))
    oos_total = float(np.mean([w.oos_expectancy for w in windows]))
    if is_total <= 0:
        wfe = 0.0
    else:
        wfe = oos_total / is_total
    score = float(np.clip(wfe, 0.0, 1.0))
    return WalkForwardResult(windows=windows, wfe=wfe, score=score)
