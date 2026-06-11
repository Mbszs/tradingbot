"""Portfolio weighting schemes with risk caps.

Weights are risk budgets (fractions of the portfolio's per-trade risk unit).
Caps: max 30% risk per strategy, 50% per edge source, 40% per instrument.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd
from scipy.optimize import linprog, minimize


@dataclass(frozen=True)
class PortfolioCaps:
    per_strategy: float = 0.30
    per_edge_source: float = 0.50
    per_instrument: float = 0.40


@dataclass(frozen=True)
class StrategyMeta:
    edge_source: str
    instrument: str


def _group_indices(names: list[str], meta: dict[str, StrategyMeta], attr: str) -> dict[str, np.ndarray]:
    groups: dict[str, list[int]] = {}
    for i, n in enumerate(names):
        key = getattr(meta[n], attr) if n in meta else f"_unknown_{n}"
        groups.setdefault(key, []).append(i)
    return {k: np.array(v) for k, v in groups.items()}


def _group_cap_matrix(names: list[str], meta: dict[str, StrategyMeta] | None,
                      caps: PortfolioCaps) -> tuple[np.ndarray, np.ndarray]:
    """(A_ub, b_ub) rows for the edge-source and instrument group caps."""
    n = len(names)
    rows, ubs = [], []
    if meta:
        for attr, cap in (("edge_source", caps.per_edge_source), ("instrument", caps.per_instrument)):
            for idx in _group_indices(names, meta, attr).values():
                row = np.zeros(n)
                row[idx] = 1.0
                rows.append(row)
                ubs.append(cap)
    if not rows:
        return np.zeros((0, n)), np.zeros(0)
    return np.vstack(rows), np.asarray(ubs)


def _feasible_start(names: list[str], meta: dict[str, StrategyMeta] | None,
                    caps: PortfolioCaps, mu: np.ndarray | None = None) -> np.ndarray:
    """LP-feasible weight vector under all caps (tilted toward mu if given)."""
    n = len(names)
    A_ub, b_ub = _group_cap_matrix(names, meta, caps)
    c = -(mu if mu is not None else np.zeros(n))
    res = linprog(c, A_ub=A_ub if len(A_ub) else None, b_ub=b_ub if len(b_ub) else None,
                  A_eq=np.ones((1, n)), b_eq=np.array([1.0]),
                  bounds=[(0.0, caps.per_strategy)] * n, method="highs")
    if not res.success:
        raise ValueError(f"caps are infeasible for {n} strategies: {res.message}")
    return np.clip(res.x, 0.0, caps.per_strategy)


def _cap_constraints(names: list[str], meta: dict[str, StrategyMeta] | None, caps: PortfolioCaps) -> list[dict]:
    cons: list[dict] = [{"type": "eq", "fun": lambda w: w.sum() - 1.0}]
    if meta:
        for idx in _group_indices(names, meta, "edge_source").values():
            cons.append({"type": "ineq", "fun": lambda w, i=idx: caps.per_edge_source - w[i].sum()})
        for idx in _group_indices(names, meta, "instrument").values():
            cons.append({"type": "ineq", "fun": lambda w, i=idx: caps.per_instrument - w[i].sum()})
    return cons


def _check_caps_feasible(n: int, caps: PortfolioCaps) -> None:
    if n * caps.per_strategy < 1.0 - 1e-9:
        raise ValueError(f"{n} strategies cannot sum to 1.0 under a {caps.per_strategy:.0%} per-strategy cap")


def inverse_vol_weights(vols: pd.Series, caps: PortfolioCaps = PortfolioCaps()) -> pd.Series:
    """1/vol weights with the per-strategy cap enforced by iterative clipping."""
    _check_caps_feasible(len(vols), caps)
    w = (1.0 / vols.clip(lower=1e-12)).to_numpy(dtype=np.float64)
    w = w / w.sum()
    for _ in range(100):
        over = w > caps.per_strategy + 1e-12
        if not over.any():
            break
        excess = (w[over] - caps.per_strategy).sum()
        w[over] = caps.per_strategy
        free = ~over
        w[free] += excess * w[free] / w[free].sum()
    return pd.Series(w, index=vols.index, name="inverse_vol")


def risk_contributions(w: np.ndarray, cov: np.ndarray) -> np.ndarray:
    sigma = float(np.sqrt(w @ cov @ w))
    return w * (cov @ w) / sigma if sigma > 0 else np.zeros_like(w)


def erc_weights(cov: pd.DataFrame, caps: PortfolioCaps = PortfolioCaps(),
                meta: dict[str, StrategyMeta] | None = None) -> pd.Series:
    """Equal-risk-contribution weights (SLSQP on squared RC dispersion)."""
    names = list(cov.index)
    n = len(names)
    _check_caps_feasible(n, caps)
    C = cov.to_numpy(dtype=np.float64)

    def objective(w: np.ndarray) -> float:
        rc = risk_contributions(w, C)
        return float(((rc[:, None] - rc[None, :]) ** 2).sum())

    res = minimize(objective, np.full(n, 1.0 / n), method="SLSQP",
                   bounds=[(0.0, caps.per_strategy)] * n,
                   constraints=_cap_constraints(names, meta, caps),
                   options={"maxiter": 500, "ftol": 1e-14})
    w = np.clip(res.x, 0, None)
    return pd.Series(w / w.sum(), index=names, name="erc")


def max_sharpe_weights(mu: pd.Series, cov: pd.DataFrame,
                       caps: PortfolioCaps = PortfolioCaps(),
                       meta: dict[str, StrategyMeta] | None = None) -> pd.Series:
    """Constrained maximum-Sharpe weights (SLSQP, long-only, capped)."""
    names = list(cov.index)
    n = len(names)
    _check_caps_feasible(n, caps)
    m = mu.reindex(names).to_numpy(dtype=np.float64)
    C = cov.to_numpy(dtype=np.float64)

    def neg_sharpe(w: np.ndarray) -> float:
        var = float(w @ C @ w)
        if var <= 1e-18:
            return 0.0
        return -float(w @ m) / np.sqrt(var)

    cons = _cap_constraints(names, meta, caps)

    def _feasible(w: np.ndarray) -> bool:
        if abs(w.sum() - 1.0) > 1e-6 or (w < -1e-9).any() or (w > caps.per_strategy + 1e-6).any():
            return False
        return all(c["fun"](w) >= -1e-6 for c in cons if c["type"] == "ineq")

    # LP-feasible starts: flat, and tilted toward the best mean return
    starts = (_feasible_start(names, meta, caps), _feasible_start(names, meta, caps, mu=m))
    best_w = min(starts, key=neg_sharpe)
    best_v = neg_sharpe(best_w)
    for x0 in starts:
        res = minimize(neg_sharpe, x0, method="SLSQP",
                       bounds=[(0.0, caps.per_strategy)] * n,
                       constraints=cons,
                       options={"maxiter": 500, "ftol": 1e-12})
        w = np.clip(res.x, 0.0, caps.per_strategy)
        if _feasible(w) and neg_sharpe(w) < best_v:
            best_w, best_v = w, neg_sharpe(w)
    return pd.Series(best_w / best_w.sum(), index=names, name="max_sharpe")
