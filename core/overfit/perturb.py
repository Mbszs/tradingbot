"""Monte Carlo robustness: trade reshuffling, random deletion, slippage stress.

Each run reshuffles trade order (stresses any path-dependence in the equity
curve), deletes 20% of trades at random (stresses dependence on a handful of
outliers), and perturbs each trade by an extra random slippage cost. The
component score is the fraction of perturbed runs that keep positive
expectancy, blended with the p5 expectancy retention vs the original.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np


@dataclass(frozen=True)
class PerturbResult:
    p_positive: float  # fraction of perturbed runs with expectancy > 0
    exp_p5: float  # 5th percentile perturbed expectancy (R)
    exp_original: float
    dd_p95_r: np.ndarray  # 95th percentile of max drawdown (R) across runs
    score: float

    def to_dict(self) -> dict:
        return {
            "p_positive": self.p_positive,
            "exp_p5": self.exp_p5,
            "exp_original": self.exp_original,
            "dd_p95_r": float(self.dd_p95_r),
            "score": self.score,
        }


def _max_drawdown(cum: np.ndarray) -> float:
    return float(np.max(np.maximum.accumulate(cum) - cum))


def mc_perturbation(
    r: np.ndarray,
    n_runs: int = 1000,
    delete_frac: float = 0.20,
    slippage_r: float = 0.05,
    seed: int = 42,
) -> PerturbResult:
    r = np.asarray(r, dtype=np.float64)
    rng = np.random.default_rng(seed)
    n = len(r)
    keep = n - int(n * delete_frac)

    exps = np.empty(n_runs)
    dds = np.empty(n_runs)
    for i in range(n_runs):
        idx = rng.permutation(n)[:keep]
        sample = r[idx] - rng.uniform(0.0, 2.0 * slippage_r, keep)  # mean extra cost = slippage_r
        exps[i] = sample.mean()
        dds[i] = _max_drawdown(np.cumsum(sample))

    exp_orig = float(r.mean())
    p_pos = float((exps > 0).mean())
    exp_p5 = float(np.percentile(exps, 5))
    retention = float(np.clip(exp_p5 / exp_orig, 0.0, 1.0)) if exp_orig > 0 else 0.0
    score = 0.5 * p_pos + 0.5 * retention
    return PerturbResult(
        p_positive=p_pos,
        exp_p5=exp_p5,
        exp_original=exp_orig,
        dd_p95_r=np.percentile(dds, 95),
        score=float(score),
    )
