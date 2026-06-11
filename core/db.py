"""SQLite schema (SQLAlchemy 2.0) and engine/session factories.

Tables: strategies, backtest_runs, trades, prop_sims, equity_snapshots,
live_state, alerts.
"""
from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    Engine,
    Float,
    ForeignKey,
    Integer,
    String,
    create_engine,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column, relationship, sessionmaker


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Base(DeclarativeBase):
    pass


class Strategy(Base):
    __tablename__ = "strategies"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(128), unique=True, index=True)
    edge_source: Mapped[str | None] = mapped_column(String(64))  # e.g. trend, mean_revert, carry, breakout
    instrument: Mapped[str | None] = mapped_column(String(32))
    timeframe: Mapped[str | None] = mapped_column(String(16))
    magic_number: Mapped[int | None] = mapped_column(Integer, unique=True)
    family: Mapped[str | None] = mapped_column(String(64))  # strategy family for trial counting (deflated Sharpe)
    status: Mapped[str] = mapped_column(String(32), default="candidate")  # candidate/live/retired
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    runs: Mapped[list["BacktestRun"]] = relationship(back_populates="strategy")
    trades: Mapped[list["Trade"]] = relationship(back_populates="strategy")


class BacktestRun(Base):
    __tablename__ = "backtest_runs"

    id: Mapped[int] = mapped_column(primary_key=True)
    strategy_id: Mapped[int] = mapped_column(ForeignKey("strategies.id"), index=True)
    label: Mapped[str | None] = mapped_column(String(128))
    params: Mapped[dict | None] = mapped_column(JSON)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    n_trades: Mapped[int | None] = mapped_column(Integer)
    metrics: Mapped[dict | None] = mapped_column(JSON)  # expectancy, sharpe, pf, max_dd_r, robustness...
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    strategy: Mapped[Strategy] = relationship(back_populates="runs")
    trades: Mapped[list["Trade"]] = relationship(back_populates="run")


class Trade(Base):
    __tablename__ = "trades"

    id: Mapped[int] = mapped_column(primary_key=True)
    strategy_id: Mapped[int | None] = mapped_column(ForeignKey("strategies.id"), index=True)
    run_id: Mapped[int | None] = mapped_column(ForeignKey("backtest_runs.id"), index=True)
    instrument: Mapped[str | None] = mapped_column(String(32))
    direction: Mapped[str | None] = mapped_column(String(8))  # long/short
    entry_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    exit_time: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    r_multiple: Mapped[float] = mapped_column(Float)
    mae_r: Mapped[float | None] = mapped_column(Float)  # max adverse excursion, positive R units
    mfe_r: Mapped[float | None] = mapped_column(Float)  # max favorable excursion, positive R units
    pnl: Mapped[float | None] = mapped_column(Float)  # account-currency PnL, if live
    session: Mapped[str | None] = mapped_column(String(16))  # asia/london/newyork
    is_live: Mapped[bool] = mapped_column(Boolean, default=False)

    strategy: Mapped[Strategy | None] = relationship(back_populates="trades")
    run: Mapped[BacktestRun | None] = relationship(back_populates="trades")


class PropSim(Base):
    __tablename__ = "prop_sims"

    id: Mapped[int] = mapped_column(primary_key=True)
    strategy_id: Mapped[int | None] = mapped_column(ForeignKey("strategies.id"), index=True)
    firm: Mapped[str] = mapped_column(String(64))
    risk_pct: Mapped[float | None] = mapped_column(Float)  # null for a sweep
    n_paths: Mapped[int] = mapped_column(Integer)
    seed: Mapped[int] = mapped_column(Integer)
    params: Mapped[dict | None] = mapped_column(JSON)
    results: Mapped[dict | None] = mapped_column(JSON)  # per-risk-level metrics
    status: Mapped[str] = mapped_column(String(16), default="done")  # pending/running/done/failed
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class EquitySnapshot(Base):
    __tablename__ = "equity_snapshots"

    id: Mapped[int] = mapped_column(primary_key=True)
    ts: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    balance: Mapped[float] = mapped_column(Float)
    equity: Mapped[float] = mapped_column(Float)
    floating_pnl: Mapped[float] = mapped_column(Float, default=0.0)
    source: Mapped[str] = mapped_column(String(32), default="mt5")  # mt5/midnight_cet/manual


class LiveState(Base):
    """Current operational state per strategy (one row per strategy)."""

    __tablename__ = "live_state"

    id: Mapped[int] = mapped_column(primary_key=True)
    strategy_id: Mapped[int] = mapped_column(ForeignKey("strategies.id"), unique=True, index=True)
    state: Mapped[str] = mapped_column(String(16), default="HEALTHY")  # HEALTHY/WATCH/REDUCED/SUSPENDED/RETIRED
    risk_pct: Mapped[float] = mapped_column(Float, default=0.0)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    reason: Mapped[str | None] = mapped_column(String(256))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)


class Alert(Base):
    __tablename__ = "alerts"

    id: Mapped[int] = mapped_column(primary_key=True)
    ts: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, index=True)
    severity: Mapped[str] = mapped_column(String(16), default="info")  # info/warning/critical
    source: Mapped[str] = mapped_column(String(32))  # decay/survival/regime/bridge/...
    kind: Mapped[str | None] = mapped_column(String(64))  # e.g. cusum_drift, dd_envelope_p95, state_transition
    strategy_id: Mapped[int | None] = mapped_column(ForeignKey("strategies.id"), index=True)
    message: Mapped[str] = mapped_column(String(512))
    evidence: Mapped[dict | None] = mapped_column(JSON)
    acknowledged: Mapped[bool] = mapped_column(Boolean, default=False)


def get_engine(db_path: Path | str) -> Engine:
    """Create a SQLite engine; parent directory is created if missing."""
    path = Path(db_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    return create_engine(f"sqlite:///{path}", future=True)


def get_session_factory(engine: Engine) -> sessionmaker[Session]:
    return sessionmaker(bind=engine, expire_on_commit=False, future=True)


def init_db(engine: Engine) -> None:
    Base.metadata.create_all(engine)
