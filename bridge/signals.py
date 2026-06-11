"""File-based JSON signal IO between Serpent Lab and the MQL5 EA.

Serpent Lab writes `signals.json` atomically (temp file + rename) so the EA
never reads a half-written file. The EA polls the file each timer tick and
applies enable/disable and risk sizing per strategy (matched by magic
number). See bridge/SIGNAL_CONTRACT.md for the full contract.
"""
from __future__ import annotations

import json
import os
import tempfile
from datetime import datetime, timezone
from pathlib import Path

from pydantic import BaseModel, Field

SIGNAL_SCHEMA_VERSION = 2
SIGNALS_FILENAME = "signals.json"
ACK_FILENAME = "signals_ack.json"


class StrategySignal(BaseModel):
    magic: int = Field(description="EA magic number identifying the strategy")
    enabled: bool
    risk_pct: float = Field(ge=0, le=10, description="Per-trade risk, % of initial balance")
    state: str = "HEALTHY"  # decay state, informational for the EA log
    comment: str = ""


class SignalFile(BaseModel):
    version: int = SIGNAL_SCHEMA_VERSION
    generated_at: datetime
    account: str = ""
    kill_switch: bool = Field(default=False, description="True = EA closes everything and stops")
    strategies: dict[str, StrategySignal] = Field(default_factory=dict,
                                                  description="keyed by strategy name")


def write_signals(signals: SignalFile, signals_dir: Path) -> Path:
    """Atomic write: the EA can never observe a partial file."""
    signals_dir = Path(signals_dir)
    signals_dir.mkdir(parents=True, exist_ok=True)
    target = signals_dir / SIGNALS_FILENAME
    payload = signals.model_dump_json(indent=2)
    fd, tmp = tempfile.mkstemp(dir=signals_dir, suffix=".tmp")
    try:
        with os.fdopen(fd, "w") as fh:
            fh.write(payload)
        os.replace(tmp, target)
    except BaseException:
        if os.path.exists(tmp):
            os.unlink(tmp)
        raise
    return target


def read_signals(signals_dir: Path) -> SignalFile:
    target = Path(signals_dir) / SIGNALS_FILENAME
    return SignalFile.model_validate_json(target.read_text())


def read_ack(signals_dir: Path) -> dict | None:
    """EA acknowledgement (written by the EA after applying a signal file)."""
    target = Path(signals_dir) / ACK_FILENAME
    if not target.exists():
        return None
    return json.loads(target.read_text())


def build_signals_from_db(session, account: str = "") -> SignalFile:
    """Snapshot live_state into a signal file."""
    from core.db import LiveState, Strategy

    rows = (session.query(LiveState, Strategy)
            .join(Strategy, LiveState.strategy_id == Strategy.id).all())
    strategies = {}
    for state, strat in rows:
        strategies[strat.name] = StrategySignal(
            magic=strat.magic_number or 0,
            enabled=state.enabled and state.risk_pct > 0,
            risk_pct=state.risk_pct,
            state=state.state,
            comment=state.reason or "",
        )
    return SignalFile(generated_at=datetime.now(timezone.utc), account=account,
                      strategies=strategies)
