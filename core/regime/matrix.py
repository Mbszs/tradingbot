"""Regime x strategy performance matrix and enable/disable recommendations.

Each trade is stamped with the regime active at its entry time (merge_asof
against the bar-level regime series); per (strategy, regime) cell we report
trades, win%, expectancy R, profit factor, max drawdown (R) and share of total
PnL. Recommendations flag regimes where a strategy reliably makes or loses
money.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd


@dataclass(frozen=True)
class RegimeRecommendation:
    strategy: str
    regime: str
    action: str  # enable / disable / neutral
    reason: str
    n_trades: int
    expectancy_r: float


def label_trades_with_regime(
    trades: pd.DataFrame,
    regimes: pd.Series,
    time_col: str = "entry_time",
) -> pd.DataFrame:
    """Stamp each trade with the most recent bar regime at entry."""
    reg = regimes.rename("regime").sort_index()
    reg.index = pd.DatetimeIndex(reg.index)
    t = trades.copy()
    t[time_col] = pd.to_datetime(t[time_col], utc=True)
    idx = reg.index.tz_localize("UTC") if reg.index.tz is None else reg.index.tz_convert("UTC")
    reg_utc = pd.Series(reg.values, index=idx, name="regime")
    t = t.sort_values(time_col)
    merged = pd.merge_asof(t, reg_utc.reset_index().rename(columns={"index": "bar_time"}),
                           left_on=time_col, right_on="bar_time", direction="backward")
    merged["regime"] = merged["regime"].fillna("UNKNOWN")
    return merged.drop(columns=["bar_time"])


def _max_dd_r(r: np.ndarray) -> float:
    cum = np.cumsum(r)
    return float(np.max(np.maximum.accumulate(cum) - cum)) if len(cum) else 0.0


def regime_strategy_matrix(
    trades: pd.DataFrame,
    regimes: pd.Series,
    strategy_col: str = "strategy",
) -> pd.DataFrame:
    """Per (strategy, regime) performance table."""
    labeled = label_trades_with_regime(trades, regimes)
    rows = []
    for (strat, regime), g in labeled.groupby([strategy_col, "regime"]):
        r = g["r_multiple"].to_numpy(dtype=np.float64)
        gross_win = r[r > 0].sum()
        gross_loss = -r[r < 0].sum()
        total_pnl_strat = labeled.loc[labeled[strategy_col] == strat, "r_multiple"].sum()
        rows.append({
            "strategy": strat,
            "regime": regime,
            "n_trades": len(r),
            "win_pct": float((r > 0).mean()),
            "expectancy_r": float(r.mean()),
            "profit_factor": float(gross_win / gross_loss) if gross_loss > 0 else float("inf"),
            "max_dd_r": _max_dd_r(r),
            "pnl_share": float(r.sum() / total_pnl_strat) if abs(total_pnl_strat) > 1e-12 else float("nan"),
        })
    return pd.DataFrame(rows).sort_values(["strategy", "regime"]).reset_index(drop=True)


def recommendations(
    matrix: pd.DataFrame,
    min_trades: int = 20,
    disable_below_r: float = -0.10,
    enable_above_r: float = 0.10,
) -> list[RegimeRecommendation]:
    recs: list[RegimeRecommendation] = []
    for _, row in matrix.iterrows():
        if row["regime"] == "UNKNOWN":
            continue
        n, exp = int(row["n_trades"]), float(row["expectancy_r"])
        if n < min_trades:
            action, reason = "neutral", f"insufficient sample (n={n} < {min_trades})"
        elif exp <= disable_below_r:
            action, reason = "disable", f"negative expectancy {exp:+.2f}R over {n} trades"
        elif exp >= enable_above_r:
            action, reason = "enable", f"positive expectancy {exp:+.2f}R over {n} trades"
        else:
            action, reason = "neutral", f"marginal expectancy {exp:+.2f}R"
        recs.append(RegimeRecommendation(
            strategy=str(row["strategy"]), regime=str(row["regime"]),
            action=action, reason=reason, n_trades=n, expectancy_r=exp,
        ))
    return recs


def pnl_share_by_regime(matrix: pd.DataFrame, strategy: str) -> dict[str, float]:
    """Positive-PnL share per regime for one strategy (feeds the overfit
    regime-diversification component)."""
    sub = matrix[matrix["strategy"] == strategy]
    out = {}
    for _, row in sub.iterrows():
        pnl = row["expectancy_r"] * row["n_trades"]
        out[str(row["regime"])] = max(float(pnl), 0.0)
    return out
