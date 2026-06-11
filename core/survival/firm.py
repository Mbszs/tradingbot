"""Config-driven prop firm rule engine.

Firm rule sets are YAML files (see core/survival/firms/). A FirmConfig fully
parameterizes the Monte Carlo simulator: phases with profit targets and
minimum trading days, equity-based daily loss measured from the midnight-CET
snapshot (floating PnL counts), static max total loss, and funded-stage
economics for EV-per-attempt.
"""
from __future__ import annotations

from pathlib import Path
from typing import Literal

import yaml
from pydantic import BaseModel, Field, field_validator

FIRMS_DIR = Path(__file__).parent / "firms"


class PhaseRule(BaseModel):
    """One evaluation phase (e.g. FTMO Phase 1)."""

    name: str
    profit_target_pct: float = Field(gt=0, description="Profit target, % of initial balance")
    min_trading_days: int = Field(default=0, ge=0)
    max_days: int | None = Field(default=None, description="Calendar limit; None = no time limit")


class FundedRule(BaseModel):
    """Funded-stage economics used for EV-per-attempt estimation."""

    profit_split: float = Field(default=0.8, ge=0, le=1)
    payout_every_days: int = Field(default=21, gt=0, description="Trading days between payouts")
    horizon_days: int = Field(default=126, ge=0, description="Funded trading days simulated for EV (0 disables)")
    fee_refund_on_first_payout: bool = True


class FirmConfig(BaseModel):
    """Complete prop firm rule set."""

    name: str
    account_size: float = Field(gt=0)
    currency: str = "USD"
    challenge_fee: float = Field(default=0.0, ge=0)

    # Daily loss: equity-based, measured against the midnight (firm timezone)
    # balance/equity snapshot; floating PnL counts (breach can occur mid-trade).
    daily_loss_pct: float | None = Field(default=None, description="Max daily loss, % of initial balance; None disables")
    daily_anchor: Literal["balance", "equity", "max_balance_equity"] = "equity"
    # Total loss: static floor below the initial balance.
    max_total_loss_pct: float = Field(gt=0)
    timezone: str = "Europe/Prague"  # CET/CEST — FTMO reset time

    phases: list[PhaseRule]
    funded: FundedRule = FundedRule()

    # Simulation cap so zero-edge paths terminate ("no time limit" firms).
    sim_max_days_per_phase: int = 750

    @field_validator("phases")
    @classmethod
    def _at_least_one_phase(cls, v: list[PhaseRule]) -> list[PhaseRule]:
        if not v:
            raise ValueError("firm config needs at least one phase")
        return v


def load_firm(name_or_path: str | Path, firms_dir: Path | None = None) -> FirmConfig:
    """Load a firm config by name (resolved in firms_dir) or explicit path."""
    base = firms_dir or FIRMS_DIR
    p = Path(name_or_path)
    if not p.suffix:
        p = base / f"{name_or_path}.yaml"
    if not p.exists():
        available = sorted(f.stem for f in base.glob("*.yaml"))
        raise FileNotFoundError(f"firm config '{name_or_path}' not found; available: {available}")
    with open(p) as fh:
        raw = yaml.safe_load(fh)
    return FirmConfig.model_validate(raw)
