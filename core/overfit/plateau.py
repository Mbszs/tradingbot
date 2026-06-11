"""Parameter plateau analysis.

Given a parameter-grid result table (one row per backtested parameter combo,
with an expectancy/metric column), the plateau score compares the mean metric
in the ±20% neighborhood of the best combo against the peak. A genuine edge
sits on a plateau (score near 1); an overfit edge sits on a needle (score
near 0).
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd


@dataclass(frozen=True)
class PlateauResult:
    peak_metric: float
    neighborhood_mean: float
    n_neighbors: int
    best_params: dict
    score: float

    def to_dict(self) -> dict:
        return {
            "peak_metric": self.peak_metric,
            "neighborhood_mean": self.neighborhood_mean,
            "n_neighbors": self.n_neighbors,
            "best_params": self.best_params,
            "score": self.score,
        }


def plateau_analysis(
    param_results: pd.DataFrame,
    metric_col: str = "metric",
    neighborhood: float = 0.20,
) -> PlateauResult:
    """`param_results`: numeric parameter columns + a metric column."""
    if metric_col not in param_results.columns:
        raise ValueError(f"missing metric column '{metric_col}'")
    params = [c for c in param_results.columns if c != metric_col]
    if not params:
        raise ValueError("no parameter columns")

    df = param_results.dropna(subset=[metric_col]).reset_index(drop=True)
    best = df.loc[df[metric_col].idxmax()]
    peak = float(best[metric_col])

    mask = np.ones(len(df), dtype=bool)
    for p in params:
        center = float(best[p])
        tol = abs(center) * neighborhood
        if tol == 0:  # parameter at zero: use the grid's own scale
            tol = float(df[p].abs().max()) * neighborhood
        mask &= (df[p] - center).abs().to_numpy() <= tol + 1e-12
    neighbors = df.loc[mask, metric_col]

    if peak <= 0:
        score = 0.0
    elif len(neighbors) < 2:  # isolated point: no plateau evidence
        score = 0.0
    else:
        score = float(np.clip(neighbors.mean() / peak, 0.0, 1.0))
    return PlateauResult(
        peak_metric=peak,
        neighborhood_mean=float(neighbors.mean()) if len(neighbors) else float("nan"),
        n_neighbors=int(len(neighbors)),
        best_params={p: float(best[p]) for p in params},
        score=score,
    )
