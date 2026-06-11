"""Survival-verified portfolio optimization.

Objective: maximize E[monthly return] / max(MC p95 max-DD, 4%) subject to
P(breach 10% total loss within 6 months) < 5% and P(daily 5% breach) < 2%.
Every candidate (inverse-vol, ERC, constrained max-Sharpe, top Pareto
portfolios) is fed back through the Module-1 survival simulator at a sweep of
portfolio risk scales; the best feasible (weights, risk) pair wins.
"""
from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import pandas as pd

from core.portfolio.corr import build_cov, worse_of_correlations
from core.portfolio.frontier import random_weight_frontier
from core.portfolio.weights import (
    PortfolioCaps,
    StrategyMeta,
    erc_weights,
    inverse_vol_weights,
    max_sharpe_weights,
)
from core.survival.firm import FirmConfig, PhaseRule
from core.survival.mc import run_prop_sim
from core.survival.trades_io import group_trades_by_day


@dataclass(frozen=True)
class CandidateEval:
    name: str
    weights: dict[str, float]
    risk_pct: float  # portfolio per-R risk unit, % of balance
    monthly_return_pct: float
    dd_p95_pct: float
    p_breach_total_6mo: float
    p_breach_daily: float
    objective: float
    feasible: bool


@dataclass(frozen=True)
class PortfolioOptimizationResult:
    best: CandidateEval | None
    candidates: list[CandidateEval]
    frontier: pd.DataFrame = field(repr=False, default_factory=pd.DataFrame)

    def to_dict(self) -> dict:
        return {
            "best": vars(self.best) if self.best else None,
            "candidates": [vars(c) for c in self.candidates],
            "n_frontier": int(len(self.frontier)),
        }


def _horizon_firm(firm: FirmConfig, horizon_days: int) -> FirmConfig:
    """Firm variant measuring only breach probabilities over a fixed horizon."""
    return firm.model_copy(update={
        "phases": [PhaseRule(name="horizon", profit_target_pct=1e9,
                             min_trading_days=0, max_days=horizon_days)],
        "sim_max_days_per_phase": horizon_days,
        "funded": firm.funded.model_copy(update={"horizon_days": 0}),
    })


def combine_portfolio_trades(
    trades_by_strategy: dict[str, pd.DataFrame],
    weights: dict[str, float],
) -> pd.DataFrame:
    """Merge strategies' trades into one chronological portfolio stream with
    r/mae scaled by each strategy's risk weight (1R of the portfolio's risk
    unit = weight 1.0)."""
    parts = []
    for name, w in weights.items():
        if w <= 1e-9:
            continue
        t = trades_by_strategy[name].copy()
        t["r_multiple"] = t["r_multiple"] * w
        if "mae_r" in t.columns:
            t["mae_r"] = t["mae_r"] * w
        parts.append(t[["entry_time", "r_multiple"] + (["mae_r"] if "mae_r" in t.columns else [])])
    if not parts:
        raise ValueError("no strategies with positive weight")
    return pd.concat(parts).sort_values("entry_time").reset_index(drop=True)


def evaluate_candidate(
    name: str,
    weights: pd.Series,
    trades_by_strategy: dict[str, pd.DataFrame],
    firm: FirmConfig,
    risk_pct: float,
    horizon_days: int = 126,
    n_paths: int = 5000,
    seed: int = 42,
    max_breach_total: float = 0.05,
    max_breach_daily: float = 0.02,
    dd_floor_pct: float = 4.0,
) -> CandidateEval:
    """Feed one (weights, risk) candidate through the survival simulator."""
    w = {k: float(v) for k, v in weights.items()}
    port_trades = combine_portfolio_trades(trades_by_strategy, w)
    days = group_trades_by_day(port_trades, tz=firm.timezone)

    sim = run_prop_sim(days, _horizon_firm(firm, horizon_days), risk_pct,
                       n_paths=n_paths, seed=seed, simulate_funded=False)
    p_total = sim.p_bust_total
    p_daily = sim.p_bust_daily

    # equity stats from the realized stream at this risk
    daily = port_trades.set_index(pd.to_datetime(port_trades["entry_time"], utc=True)) \
                       .resample("1D")["r_multiple"].sum()
    daily = daily[daily != 0.0]
    dd_p95, monthly = _bootstrap_dd_and_monthly(daily.to_numpy(), risk_pct / 100.0,
                                                horizon_days, seed=seed)

    objective = monthly / max(dd_p95, dd_floor_pct)
    feasible = (p_total < max_breach_total) and (p_daily < max_breach_daily)
    return CandidateEval(
        name=name, weights=w, risk_pct=risk_pct,
        monthly_return_pct=monthly, dd_p95_pct=dd_p95,
        p_breach_total_6mo=p_total, p_breach_daily=p_daily,
        objective=float(objective), feasible=feasible,
    )


def _bootstrap_dd_and_monthly(
    daily_r: np.ndarray, risk_frac: float, horizon_days: int,
    n_paths: int = 2000, seed: int = 42,
) -> tuple[float, float]:
    """(p95 max drawdown %, mean monthly return %) over bootstrapped horizons."""
    rng = np.random.default_rng(seed)
    idx = rng.integers(0, len(daily_r), size=(horizon_days, n_paths))
    growth = 1.0 + daily_r[idx] * risk_frac
    equity = np.cumprod(growth, axis=0)
    peak = np.maximum.accumulate(equity, axis=0)
    dd_p95 = float(np.percentile((1.0 - equity / peak).max(axis=0), 95)) * 100
    monthly = float(np.mean(equity[-1] ** (21.0 / horizon_days) - 1.0)) * 100
    return dd_p95, monthly


def optimize_portfolio(
    daily_streams: pd.DataFrame,
    trades_by_strategy: dict[str, pd.DataFrame],
    firm: FirmConfig,
    meta: dict[str, StrategyMeta] | None = None,
    crisis_days: pd.DatetimeIndex | None = None,
    caps: PortfolioCaps = PortfolioCaps(),
    risk_grid: tuple[float, ...] = (0.5, 0.75, 1.0, 1.25, 1.5, 2.0),
    n_frontier: int = 10_000,
    n_frontier_candidates: int = 3,
    n_paths: int = 5000,
    seed: int = 42,
) -> PortfolioOptimizationResult:
    """Full Module-5 pipeline: worse-of correlations -> candidate weights ->
    frontier -> survival-verified objective maximization."""
    filled = daily_streams.fillna(0.0)
    vols = filled.std()
    mu = filled.mean()
    corr_full = filled.corr()
    corr_crisis = None
    if crisis_days is not None and len(crisis_days) >= 10:
        sub = filled.loc[filled.index.isin(crisis_days)]
        if len(sub) >= 10:
            corr_crisis = sub.corr()
    corr = worse_of_correlations(corr_full, corr_crisis)
    cov = build_cov(vols, corr)

    candidates: dict[str, pd.Series] = {
        "inverse_vol": inverse_vol_weights(vols, caps),
        "erc": erc_weights(cov, caps, meta),
        "max_sharpe": max_sharpe_weights(mu, cov, caps, meta),
    }

    frontier = random_weight_frontier(filled, n_portfolios=n_frontier,
                                      max_weight=caps.per_strategy, seed=seed)
    pareto = frontier[frontier["pareto"]].sort_values("cagr", ascending=False)
    for i, (_, row) in enumerate(pareto.head(n_frontier_candidates).iterrows()):
        candidates[f"pareto_{i}"] = row[daily_streams.columns]

    evals: list[CandidateEval] = []
    for name, w in candidates.items():
        for risk in risk_grid:
            evals.append(evaluate_candidate(name, w, trades_by_strategy, firm, risk,
                                            n_paths=n_paths, seed=seed))
    feasible = [e for e in evals if e.feasible]
    best = max(feasible, key=lambda e: e.objective) if feasible else None
    return PortfolioOptimizationResult(best=best, candidates=evals, frontier=frontier)
