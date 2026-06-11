"""Efficient frontier via random weight vectors: CAGR vs max drawdown.

10,000 Dirichlet-sampled weight vectors over the strategies' joint daily
R-streams, evaluated at a base per-R risk fraction; the Pareto-efficient set
(max CAGR for given max DD) is flagged.
"""
from __future__ import annotations

import numpy as np
import pandas as pd


def portfolio_equity_stats(daily_port_r: np.ndarray, risk_frac: float, periods_per_year: int = 252) -> tuple[float, float]:
    """(CAGR, max drawdown) of a compounded equity path from a daily R stream."""
    equity = np.cumprod(1.0 + daily_port_r * risk_frac)
    years = len(equity) / periods_per_year
    cagr = float(equity[-1] ** (1 / years) - 1) if years > 0 and equity[-1] > 0 else -1.0
    peak = np.maximum.accumulate(equity)
    max_dd = float(np.max(1.0 - equity / peak))
    return cagr, max_dd


def random_weight_frontier(
    daily_streams: pd.DataFrame,
    n_portfolios: int = 10_000,
    risk_frac: float = 0.01,
    max_weight: float = 1.0,
    seed: int = 42,
) -> pd.DataFrame:
    """Columns: one weight column per strategy + cagr, max_dd, pareto."""
    rng = np.random.default_rng(seed)
    R = daily_streams.fillna(0.0).to_numpy(dtype=np.float64)  # days x strategies
    n_strats = R.shape[1]

    W = rng.dirichlet(np.ones(n_strats), size=n_portfolios)
    if max_weight < 1.0:
        keep = (W <= max_weight + 1e-12).all(axis=1)
        W = W[keep]

    port_daily = R @ W.T  # days x portfolios
    growth = 1.0 + port_daily * risk_frac
    equity = np.cumprod(growth, axis=0)
    years = R.shape[0] / 252.0
    cagr = equity[-1] ** (1 / years) - 1
    peak = np.maximum.accumulate(equity, axis=0)
    max_dd = (1.0 - equity / peak).max(axis=0)

    df = pd.DataFrame(W, columns=daily_streams.columns)
    df["cagr"] = cagr
    df["max_dd"] = max_dd
    df["pareto"] = _pareto_mask(cagr, max_dd)
    return df


def _pareto_mask(cagr: np.ndarray, max_dd: np.ndarray) -> np.ndarray:
    """True where no other portfolio has both lower DD and higher CAGR."""
    order = np.argsort(max_dd, kind="stable")
    mask = np.zeros(len(cagr), dtype=bool)
    best = -np.inf
    for i in order:
        if cagr[i] > best:
            mask[i] = True
            best = cagr[i]
    return mask
