"""Decay state machine: HEALTHY -> WATCH -> REDUCED -> SUSPENDED -> RETIRED.

Transition policy per evaluation:
- DD envelope P99 .............................. SUSPENDED (risk off)
- DD envelope P95 .............................. REDUCED (halve risk)
- CUSUM 3-sigma drift or KS shift .............. escalate one step (max REDUCED)
- All detectors clean .......................... de-escalate one step toward HEALTHY
- Regime mismatch (underperformance regime-expected) suppresses
  CUSUM/KS escalation, never the DD-envelope hard checks.
- RETIRED is terminal and only entered manually (retire()).

Every transition is recorded in live_state and logged to alerts with the full
detector evidence.
"""
from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import pandas as pd

from core.decay.detectors import (
    cusum_check,
    dd_envelope_check,
    ks_shift_check,
    regime_mismatch_check,
)

STATES = ("HEALTHY", "WATCH", "REDUCED", "SUSPENDED", "RETIRED")
_ORDER = {s: i for i, s in enumerate(STATES)}
RISK_MULTIPLIER = {"HEALTHY": 1.0, "WATCH": 1.0, "REDUCED": 0.5, "SUSPENDED": 0.0, "RETIRED": 0.0}


@dataclass(frozen=True)
class DecayEvaluation:
    strategy: str
    previous_state: str
    new_state: str
    risk_multiplier: float
    triggers: list[str]
    suppressed: list[str]
    evidence: dict = field(default_factory=dict)

    @property
    def transitioned(self) -> bool:
        return self.new_state != self.previous_state

    def to_dict(self) -> dict:
        return {k: getattr(self, k) for k in self.__dataclass_fields__}


def evaluate_decay(
    strategy: str,
    current_state: str,
    live_trades: pd.DataFrame,
    hist_r: np.ndarray,
    regime_expectancy: dict[str, float] | None = None,
    ks_window: int = 30,
    seed: int = 42,
) -> DecayEvaluation:
    """Run all detectors on the live record and compute the next state.

    live_trades: chronological live trades (r_multiple, optional regime).
    hist_r: the strategy's validated backtest R distribution.
    """
    if current_state == "RETIRED":
        return DecayEvaluation(strategy, "RETIRED", "RETIRED", 0.0, [], [],
                               {"note": "terminal state"})

    hist_r = np.asarray(hist_r, dtype=np.float64)
    live_r = live_trades["r_multiple"].to_numpy(dtype=np.float64)
    hist_mean, hist_std = float(hist_r.mean()), float(hist_r.std(ddof=1))

    cusum = cusum_check(live_r, hist_mean, hist_std)
    dd = dd_envelope_check(live_r, hist_r, seed=seed)
    ks = ks_shift_check(live_r, hist_r, window=ks_window)
    mismatch = regime_mismatch_check(live_trades, regime_expectancy or {}, hist_mean)

    triggers: list[str] = []
    suppressed: list[str] = []

    soft_triggers = []
    if cusum.triggered:
        soft_triggers.append(f"cusum_drift z={cusum.z:.2f} >= 3.0")
    if ks.shifted:
        soft_triggers.append(f"ks_shift p={ks.p_value:.4f} on last {ks.n_recent} trades")
    if mismatch.regime_expected and soft_triggers:
        suppressed = soft_triggers
        soft_triggers = []
    triggers.extend(soft_triggers)

    if dd.level == "P99":
        triggers.append(f"dd_envelope live {dd.live_dd_r:.1f}R >= p99 {dd.p99_dd_r:.1f}R")
        new_state = "SUSPENDED"
    elif dd.level == "P95":
        triggers.append(f"dd_envelope live {dd.live_dd_r:.1f}R >= p95 {dd.p95_dd_r:.1f}R")
        new_state = _max_state("REDUCED", _escalate(current_state) if soft_triggers else current_state)
    elif soft_triggers:
        new_state = _min_state(_escalate(current_state), "REDUCED")  # soft evidence never suspends
    else:
        new_state = _deescalate(current_state)

    evidence = {
        "cusum": cusum.to_dict(),
        "dd_envelope": dd.to_dict(),
        "ks": ks.to_dict(),
        "regime_mismatch": mismatch.to_dict(),
        "n_live_trades": int(len(live_r)),
    }
    return DecayEvaluation(strategy, current_state, new_state,
                           RISK_MULTIPLIER[new_state], triggers, suppressed, evidence)


def _escalate(state: str) -> str:
    return STATES[min(_ORDER[state] + 1, _ORDER["SUSPENDED"])]


def _deescalate(state: str) -> str:
    return STATES[max(_ORDER[state] - 1, 0)] if state != "RETIRED" else "RETIRED"


def _max_state(a: str, b: str) -> str:
    return a if _ORDER[a] >= _ORDER[b] else b


def _min_state(a: str, b: str) -> str:
    return a if _ORDER[a] <= _ORDER[b] else b


def apply_evaluation(session, strategy_id: int, evaluation: DecayEvaluation,
                     base_risk_pct: float) -> None:
    """Persist the new state to live_state and log the transition to alerts."""
    from core.db import Alert, LiveState

    state_row = session.query(LiveState).filter_by(strategy_id=strategy_id).one_or_none()
    if state_row is None:
        state_row = LiveState(strategy_id=strategy_id)
        session.add(state_row)
    state_row.state = evaluation.new_state
    state_row.risk_pct = base_risk_pct * evaluation.risk_multiplier
    state_row.enabled = evaluation.risk_multiplier > 0
    state_row.reason = "; ".join(evaluation.triggers) or "all detectors clean"

    if evaluation.transitioned:
        session.add(Alert(
            severity="critical" if evaluation.new_state in ("SUSPENDED", "RETIRED") else "warning",
            source="decay",
            kind="state_transition",
            strategy_id=strategy_id,
            message=(f"{evaluation.strategy}: {evaluation.previous_state} -> "
                     f"{evaluation.new_state} ({state_row.reason})"),
            evidence=evaluation.evidence,
        ))
    session.commit()


def retire(session, strategy_id: int, strategy_name: str, reason: str) -> None:
    """Manual terminal transition."""
    from core.db import Alert, LiveState

    state_row = session.query(LiveState).filter_by(strategy_id=strategy_id).one_or_none()
    previous = state_row.state if state_row else "HEALTHY"
    if state_row is None:
        state_row = LiveState(strategy_id=strategy_id)
        session.add(state_row)
    state_row.state = "RETIRED"
    state_row.risk_pct = 0.0
    state_row.enabled = False
    state_row.reason = reason
    session.add(Alert(severity="critical", source="decay", kind="state_transition",
                      strategy_id=strategy_id,
                      message=f"{strategy_name}: {previous} -> RETIRED ({reason})",
                      evidence={"manual": True, "reason": reason}))
    session.commit()
