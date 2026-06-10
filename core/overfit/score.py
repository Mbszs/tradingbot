"""Composite robustness score (0-100).

Weights: 25 walk-forward efficiency, 20 CPCV, 15 MC perturbation, 15 parameter
plateau, 10 cost stress (re-run at 2x spread), 10 regime diversification,
5 trade count.

Hard gates: fewer than 100 trades caps the score at 40; deflated Sharpe
excess < 0 is a REJECT regardless of score.
"""
from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import pandas as pd

from core.overfit.cpcv import cpcv
from core.overfit.deflated_sharpe import deflated_sharpe
from core.overfit.perturb import mc_perturbation
from core.overfit.plateau import plateau_analysis
from core.overfit.walkforward import walk_forward

WEIGHTS = {
    "wfe": 25.0,
    "cpcv": 20.0,
    "mc": 15.0,
    "plateau": 15.0,
    "cost_stress": 10.0,
    "regime_div": 10.0,
    "trade_count": 5.0,
}
MIN_TRADES_GATE = 100
MIN_TRADES_CAP = 40.0


@dataclass(frozen=True)
class RobustnessReport:
    score: float  # 0..100
    verdict: str  # PASS / WARN / REJECT
    components: dict[str, float]  # each 0..1
    details: dict = field(default_factory=dict)
    gates: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "score": self.score,
            "verdict": self.verdict,
            "components": self.components,
            "gates": self.gates,
            "details": self.details,
        }


def cost_stress_score(r: np.ndarray, cost_r_per_trade: float) -> tuple[float, dict]:
    """Edge retention when spread cost doubles (one extra 1x cost per trade)."""
    exp = float(np.mean(r))
    stressed = exp - cost_r_per_trade
    score = float(np.clip(stressed / exp, 0.0, 1.0)) if exp > 0 else 0.0
    return score, {"expectancy": exp, "expectancy_2x_spread": stressed, "cost_r_1x": cost_r_per_trade}


def regime_diversification_score(pnl_share_by_regime: dict[str, float] | None) -> float:
    """Normalized entropy of positive PnL share across regimes; neutral 0.5
    when regime attribution is unavailable."""
    if not pnl_share_by_regime:
        return 0.5
    shares = np.array([max(v, 0.0) for v in pnl_share_by_regime.values()], dtype=np.float64)
    if shares.sum() <= 0 or len(shares) < 2:
        return 0.0
    p = shares / shares.sum()
    p = p[p > 0]
    entropy = float(-(p * np.log(p)).sum())
    return float(np.clip(entropy / np.log(len(shares)), 0.0, 1.0))


def trade_count_score(n: int, full_at: int = 300) -> float:
    return float(np.clip(n / full_at, 0.0, 1.0))


def robustness_battery(
    trades: pd.DataFrame,
    param_results: pd.DataFrame | None = None,
    n_trials: int = 1,
    cost_r_per_trade: float = 0.08,
    pnl_share_by_regime: dict[str, float] | None = None,
    trades_per_year: float = 750.0,
    seed: int = 42,
) -> RobustnessReport:
    """Run the full overfitting battery on a chronological trade list.

    trades: DataFrame with r_multiple (chronological); param_results: optional
    grid (param columns + 'metric') for plateau analysis; n_trials: strategy-
    family trial count for the deflated Sharpe.
    """
    if "entry_time" in trades.columns:
        trades = trades.sort_values("entry_time")
    r = trades["r_multiple"].to_numpy(dtype=np.float64)
    n = len(r)

    wf = walk_forward(r)
    cp = cpcv(r, trades_per_year=trades_per_year)
    mc = mc_perturbation(r, slippage_r=cost_r_per_trade / 2, seed=seed)
    if param_results is not None:
        pl = plateau_analysis(param_results)
        plateau_score, plateau_details = pl.score, pl.to_dict()
    else:
        plateau_score, plateau_details = 0.5, {"note": "no parameter grid supplied; neutral 0.5"}
    cost_score, cost_details = cost_stress_score(r, cost_r_per_trade)
    regime_score = regime_diversification_score(pnl_share_by_regime)
    count_score = trade_count_score(n)
    ds = deflated_sharpe(r, n_trials=n_trials)

    components = {
        "wfe": wf.score,
        "cpcv": cp.score,
        "mc": mc.score,
        "plateau": plateau_score,
        "cost_stress": cost_score,
        "regime_div": regime_score,
        "trade_count": count_score,
    }
    score = float(sum(WEIGHTS[k] * components[k] for k in WEIGHTS))

    gates: list[str] = []
    if n < MIN_TRADES_GATE:
        score = min(score, MIN_TRADES_CAP)
        gates.append(f"trade_count<{MIN_TRADES_GATE}: score capped at {MIN_TRADES_CAP:.0f}")
    if ds.sr_excess < 0:
        gates.append(f"deflated Sharpe excess {ds.sr_excess:.3f} < 0: REJECT")
        verdict = "REJECT"
    elif score >= 70:
        verdict = "PASS"
    else:
        verdict = "WARN"

    return RobustnessReport(
        score=round(score, 2),
        verdict=verdict,
        components=components,
        gates=gates,
        details={
            "walk_forward": wf.to_dict(),
            "cpcv": cp.to_dict(),
            "mc_perturbation": mc.to_dict(),
            "plateau": plateau_details,
            "cost_stress": cost_details,
            "deflated_sharpe": ds.to_dict(),
            "n_trades": n,
        },
    )
