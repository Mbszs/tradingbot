"""Rule-based regime classifier.

Labels: CRISIS, HIGH_VOL_TREND, LOW_VOL_TREND, MEAN_REVERT, SIDEWAYS_QUIET,
SIDEWAYS_CHOP — each with a BULL/BEAR overlay from the 50-bar slope sign.

Precedence: CRISIS (extreme vol + vol-of-vol) -> trend split by ATR percentile
-> mean reversion (low Hurst) -> quiet vs choppy sideways by ATR percentile.
"""
from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

REGIMES = ("CRISIS", "HIGH_VOL_TREND", "LOW_VOL_TREND", "MEAN_REVERT",
           "SIDEWAYS_QUIET", "SIDEWAYS_CHOP")


@dataclass(frozen=True)
class RuleParams:
    crisis_atr_pctile: float = 0.93
    crisis_volvol_pctile: float = 0.80
    trend_adx: float = 25.0
    trend_r2: float = 0.35
    trend_er: float = 0.30
    high_vol_pctile: float = 0.60
    mean_revert_hurst: float = 0.45
    quiet_atr_pctile: float = 0.35


def classify_rules(features: pd.DataFrame, params: RuleParams | None = None) -> pd.DataFrame:
    """Classify each bar. Returns DataFrame with regime, direction, regime_full."""
    p = params or RuleParams()
    f = features

    is_crisis = (f["atr_pctile"] >= p.crisis_atr_pctile) & (f["volvol_pctile"] >= p.crisis_volvol_pctile)
    is_trend = (f["adx"] >= p.trend_adx) & ((f["r2"] >= p.trend_r2) | (f["efficiency_ratio"] >= p.trend_er))
    is_high_vol = f["atr_pctile"] >= p.high_vol_pctile
    is_mr = f["hurst"] <= p.mean_revert_hurst
    is_quiet = f["atr_pctile"] <= p.quiet_atr_pctile

    regime = pd.Series("SIDEWAYS_CHOP", index=f.index, name="regime")
    regime[is_quiet] = "SIDEWAYS_QUIET"
    regime[is_mr] = "MEAN_REVERT"
    regime[is_trend & ~is_high_vol] = "LOW_VOL_TREND"
    regime[is_trend & is_high_vol] = "HIGH_VOL_TREND"
    regime[is_crisis] = "CRISIS"
    regime[f[["adx", "atr_pctile", "hurst"]].isna().any(axis=1)] = "UNKNOWN"

    direction = pd.Series("BULL", index=f.index, name="direction").where(f["slope"] >= 0, "BEAR")
    direction[regime == "UNKNOWN"] = "NA"

    out = pd.DataFrame({"regime": regime, "direction": direction})
    out["regime_full"] = out["regime"] + "/" + out["direction"]
    return out
