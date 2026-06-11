"""Pydantic request/response schemas for the API."""
from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class TradeIn(BaseModel):
    entry_time: datetime
    exit_time: datetime | None = None
    r_multiple: float
    mae_r: float = 0.0
    mfe_r: float | None = None
    instrument: str | None = None
    direction: str | None = None
    session: str | None = None


class SweepSpec(BaseModel):
    start: float = 0.25
    stop: float = 2.0
    step: float = 0.25


class PropSimRequest(BaseModel):
    trades: list[TradeIn] = Field(min_length=10)
    firm: str = "ftmo_100k_2step"
    sweep: SweepSpec = SweepSpec()
    risks: list[float] | None = None  # overrides sweep when given
    n_paths: int = Field(default=20_000, ge=100, le=200_000)
    seed: int = 42
    block_size: int = 5
    simulate_funded: bool = True
    strategy_id: int | None = None


class StrategyIn(BaseModel):
    name: str
    edge_source: str | None = None
    instrument: str | None = None
    timeframe: str | None = None
    family: str | None = None
    magic_number: int | None = None


class BacktestRequest(BaseModel):
    strategy: StrategyIn
    label: str | None = None
    params: dict | None = None
    trades: list[TradeIn] = Field(min_length=10)


class PortfolioOptimizeRequest(BaseModel):
    strategy_ids: list[int] = Field(min_length=2)
    firm: str = "ftmo_100k_2step"
    risk_grid: list[float] = [0.5, 0.75, 1.0, 1.25, 1.5]
    per_strategy_cap: float = 0.30
    per_edge_source_cap: float = 0.50
    per_instrument_cap: float = 0.40
    n_frontier: int = Field(default=10_000, le=50_000)
    n_paths: int = Field(default=5_000, le=50_000)
    seed: int = 42
