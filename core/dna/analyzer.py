"""Strategy DNA analyzer.

Per strategy: edge-source tag, trade frequency, convexity (R-distribution skew
+ tail ratio), volatility exposure (daily PnL beta to ATR change), correlation
vector vs all other strategies on daily R-streams (full-sample AND
crisis-regime-conditional), cost sensitivity (edge at 1x/1.5x/2x costs),
session dependency, best/worst regimes, and auto-extracted failure conditions.
"""
from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import pandas as pd
from scipy import stats

COST_MULTIPLIERS = (1.0, 1.5, 2.0)


@dataclass(frozen=True)
class StrategyDNA:
    strategy: str
    edge_source: str | None
    n_trades: int
    trades_per_week: float
    expectancy_r: float
    convexity: dict  # skew, tail_ratio
    vol_exposure_beta: float | None
    correlations_full: dict[str, float]
    correlations_crisis: dict[str, float]
    cost_sensitivity: dict[str, float]  # "1.0x" -> expectancy R
    session_dependency: dict[str, dict]
    best_regimes: list[str]
    worst_regimes: list[str]
    failure_conditions: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {k: getattr(self, k) for k in self.__dataclass_fields__}


def daily_r_stream(trades: pd.DataFrame, tz: str = "UTC") -> pd.Series:
    """Daily summed R per calendar day in tz."""
    t = pd.to_datetime(trades["entry_time"], utc=True).dt.tz_convert(tz)
    return trades.groupby(t.dt.normalize())["r_multiple"].sum().sort_index()


def convexity_metrics(r: np.ndarray) -> dict:
    """Positive skew + tail ratio > 1 indicates convex (long-vol-like) payoff."""
    p95 = float(np.percentile(r, 95))
    p5 = float(np.percentile(r, 5))
    return {
        "skew": float(stats.skew(r)),
        "tail_ratio": float(abs(p95) / abs(p5)) if p5 != 0 else float("inf"),
    }


def vol_exposure_beta(daily_r: pd.Series, atr: pd.Series) -> float | None:
    """OLS beta of daily R PnL on the daily change in (normalized) ATR.

    Positive beta: strategy profits when volatility expands."""
    atr_change = atr.pct_change().rename("atr_chg")
    if atr_change.index.tz is None:
        atr_change.index = atr_change.index.tz_localize("UTC")
    df = pd.concat([daily_r.rename("r"), atr_change], axis=1, join="inner").dropna()
    if len(df) < 20 or df["atr_chg"].std() < 1e-12:
        return None
    slope, *_ = stats.linregress(df["atr_chg"], df["r"])
    return float(slope)


def correlation_vector(
    own: pd.Series,
    others: dict[str, pd.Series],
    days_filter: pd.DatetimeIndex | None = None,
) -> dict[str, float]:
    """Pearson correlation of daily R-streams vs each other strategy,
    optionally restricted to a set of days (e.g. crisis-regime days)."""
    out: dict[str, float] = {}
    for name, s in others.items():
        df = pd.concat([own.rename("a"), s.rename("b")], axis=1).fillna(0.0)
        if days_filter is not None:
            df = df.loc[df.index.isin(days_filter)]
        if len(df) < 10 or df["a"].std() < 1e-12 or df["b"].std() < 1e-12:
            out[name] = float("nan")
        else:
            out[name] = float(df["a"].corr(df["b"]))
    return out


def cost_sensitivity(r: np.ndarray, cost_r_1x: float) -> dict[str, float]:
    """Expectancy after adding (m-1)x extra cost per trade; the recorded trades
    already carry 1x costs."""
    return {f"{m:.1f}x": float(r.mean() - (m - 1.0) * cost_r_1x) for m in COST_MULTIPLIERS}


SESSION_HOURS = ((0, 7, "asia"), (7, 13, "london"), (13, 22, "newyork"), (22, 24, "asia"))


def infer_session(entry_time: pd.Series) -> pd.Series:
    hours = pd.to_datetime(entry_time, utc=True).dt.hour
    out = pd.Series("asia", index=entry_time.index)
    for lo, hi, name in SESSION_HOURS:
        out[(hours >= lo) & (hours < hi)] = name
    return out


def session_dependency(trades: pd.DataFrame) -> dict[str, dict]:
    t = trades.copy()
    if "session" not in t.columns or t["session"].isna().any():
        t["session"] = infer_session(t["entry_time"])
    out = {}
    for sess, g in t.groupby("session"):
        r = g["r_multiple"].to_numpy()
        out[str(sess)] = {"n": len(r), "expectancy_r": float(r.mean()),
                          "win_pct": float((r > 0).mean())}
    return out


def extract_failure_conditions(
    regime_matrix_strat: pd.DataFrame,
    sessions: dict[str, dict],
    costs: dict[str, float],
    convexity: dict,
    min_trades: int = 20,
) -> list[str]:
    conditions: list[str] = []
    for _, row in regime_matrix_strat.iterrows():
        if row["n_trades"] >= min_trades and row["expectancy_r"] < -0.05:
            conditions.append(
                f"loses in {row['regime']} ({row['expectancy_r']:+.2f}R over {row['n_trades']} trades)")
    for sess, m in sessions.items():
        if m["n"] >= min_trades and m["expectancy_r"] < -0.05:
            conditions.append(f"loses in {sess} session ({m['expectancy_r']:+.2f}R over {m['n']} trades)")
    if costs.get("2.0x", 1.0) <= 0:
        conditions.append(f"edge dies at 2x costs ({costs['2.0x']:+.2f}R)")
    if convexity["skew"] < -0.5 and convexity["tail_ratio"] < 1.0:
        conditions.append("concave payoff: left-tail heavy R distribution (short-vol profile)")
    return conditions


def analyze_strategy(
    strategy: str,
    trades: pd.DataFrame,
    all_daily_streams: dict[str, pd.Series],
    regime_matrix: pd.DataFrame | None = None,
    atr: pd.Series | None = None,
    crisis_days: pd.DatetimeIndex | None = None,
    edge_source: str | None = None,
    cost_r_1x: float = 0.08,
) -> StrategyDNA:
    """Build the full DNA profile for one strategy.

    all_daily_streams: daily R-streams of every strategy (incl. this one);
    crisis_days: days labeled CRISIS by the regime engine.
    """
    r = trades["r_multiple"].to_numpy(dtype=np.float64)
    own = all_daily_streams[strategy]
    others = {k: v for k, v in all_daily_streams.items() if k != strategy}

    t = pd.to_datetime(trades["entry_time"], utc=True)
    span_weeks = max(((t.max() - t.min()).days + 1) / 7.0, 1e-9)

    conv = convexity_metrics(r)
    costs = cost_sensitivity(r, cost_r_1x)
    sessions = session_dependency(trades)

    best_regimes: list[str] = []
    worst_regimes: list[str] = []
    failure: list[str] = []
    if regime_matrix is not None:
        sub = regime_matrix[(regime_matrix["strategy"] == strategy)
                            & (regime_matrix["regime"] != "UNKNOWN")
                            & (regime_matrix["n_trades"] >= 10)]
        ranked = sub.sort_values("expectancy_r", ascending=False)
        best_regimes = ranked.head(2)["regime"].tolist()
        worst_regimes = ranked.tail(2)["regime"].tolist()[::-1]
        failure = extract_failure_conditions(sub, sessions, costs, conv)
    else:
        failure = extract_failure_conditions(pd.DataFrame(columns=["regime", "n_trades", "expectancy_r"]),
                                             sessions, costs, conv)

    return StrategyDNA(
        strategy=strategy,
        edge_source=edge_source,
        n_trades=len(r),
        trades_per_week=float(len(r) / span_weeks),
        expectancy_r=float(r.mean()),
        convexity=conv,
        vol_exposure_beta=vol_exposure_beta(own, atr) if atr is not None else None,
        correlations_full=correlation_vector(own, others),
        correlations_crisis=(correlation_vector(own, others, crisis_days)
                             if crisis_days is not None else {}),
        cost_sensitivity=costs,
        session_dependency=sessions,
        best_regimes=best_regimes,
        worst_regimes=worst_regimes,
        failure_conditions=failure,
    )
