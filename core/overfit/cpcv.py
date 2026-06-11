"""Combinatorial purged cross-validation (López de Prado) on trade streams.

The chronological trade series is split into N contiguous groups; every
combination of `n_test` groups (C(10,2) = 45 for the defaults) forms one
hold-out path. Training indices within `purge_gap` trades of a test block are
purged, and an embargo of `embargo_frac` of the sample after each test block
is dropped, to kill leakage through serial correlation.

For pure R-stream evaluation the "model" is the recorded edge itself, so the
battery reports the distribution of hold-out Sharpe ratios across all combos —
a temporally fragile edge shows a fat left tail. A custom `fit_score_fn`
(train, test) -> float can plug in real re-fitting.
"""
from __future__ import annotations

from dataclasses import dataclass
from itertools import combinations
from typing import Callable

import numpy as np


@dataclass(frozen=True)
class CPCVResult:
    combo_sharpes: np.ndarray  # one annualized Sharpe per test combo
    p5_sharpe: float
    median_sharpe: float
    frac_negative: float
    score: float  # 0..1

    def to_dict(self) -> dict:
        return {
            "p5_sharpe": self.p5_sharpe,
            "median_sharpe": self.median_sharpe,
            "frac_negative": self.frac_negative,
            "n_combos": int(len(self.combo_sharpes)),
            "score": self.score,
        }


def make_groups(n: int, n_groups: int) -> list[np.ndarray]:
    """Contiguous, near-equal index groups."""
    bounds = np.linspace(0, n, n_groups + 1).astype(int)
    return [np.arange(bounds[i], bounds[i + 1]) for i in range(n_groups)]


def purged_train_indices(
    n: int,
    test_idx: np.ndarray,
    purge_gap: int,
    embargo: int,
) -> np.ndarray:
    """All indices not in test, purged within purge_gap before/after each test
    block and embargoed for `embargo` indices after each block end."""
    mask = np.ones(n, dtype=bool)
    mask[test_idx] = False
    # contiguous runs of the test set
    splits = np.flatnonzero(np.diff(test_idx) > 1) + 1
    for run in np.split(test_idx, splits):
        lo, hi = int(run[0]), int(run[-1])
        mask[max(0, lo - purge_gap) : lo] = False
        mask[hi + 1 : min(n, hi + 1 + purge_gap + embargo)] = False
    return np.flatnonzero(mask)


def _annualized_sharpe(r: np.ndarray, trades_per_year: float) -> float:
    sd = float(np.std(r, ddof=1)) if len(r) > 2 else 0.0
    if sd == 0:
        return 0.0
    return float(np.mean(r)) / sd * float(np.sqrt(trades_per_year))


def cpcv(
    r: np.ndarray,
    n_groups: int = 10,
    n_test_groups: int = 2,
    purge_gap: int = 5,
    embargo_frac: float = 0.01,
    trades_per_year: float = 750.0,
    fit_score_fn: Callable[[np.ndarray, np.ndarray], float] | None = None,
) -> CPCVResult:
    r = np.asarray(r, dtype=np.float64)
    n = len(r)
    if n < n_groups * 3:
        raise ValueError(f"need at least {n_groups * 3} trades for {n_groups} groups")
    groups = make_groups(n, n_groups)
    embargo = int(np.ceil(n * embargo_frac))

    sharpes = []
    for combo in combinations(range(n_groups), n_test_groups):
        test_idx = np.concatenate([groups[g] for g in combo])
        if fit_score_fn is not None:
            train_idx = purged_train_indices(n, test_idx, purge_gap, embargo)
            sharpes.append(fit_score_fn(r[train_idx], r[test_idx]))
        else:
            sharpes.append(_annualized_sharpe(r[test_idx], trades_per_year))
    arr = np.asarray(sharpes, dtype=np.float64)

    p5 = float(np.percentile(arr, 5))
    # score: p5 of hold-out Sharpe mapped linearly, 0 at <=0 and 1 at >=1.5
    score = float(np.clip(p5 / 1.5, 0.0, 1.0))
    return CPCVResult(
        combo_sharpes=arr,
        p5_sharpe=p5,
        median_sharpe=float(np.median(arr)),
        frac_negative=float((arr < 0).mean()),
        score=score,
    )
