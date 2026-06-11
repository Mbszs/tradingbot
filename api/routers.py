"""API routers: prop-sim, backtests, strategies, portfolios, ops."""
from __future__ import annotations

import pandas as pd
from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session

from api.schemas import BacktestRequest, PortfolioOptimizeRequest, PropSimRequest
from bridge.mt5_ingest import bars_path, read_bars_parquet
from core.db import Alert, BacktestRun, EquitySnapshot, LiveState, PropSim, Strategy, Trade
from core.dna.analyzer import analyze_strategy, daily_r_stream
from core.overfit.score import robustness_battery
from core.portfolio.objective import optimize_portfolio
from core.portfolio.weights import PortfolioCaps, StrategyMeta
from core.regime.features import compute_features
from core.regime.matrix import recommendations, regime_strategy_matrix
from core.regime.rules import classify_rules
from core.survival.firm import load_firm
from core.survival.sweep import run_risk_sweep, sweep_risks, sweep_to_frame
from core.survival.trades_io import group_trades_by_day

router = APIRouter()


def get_db(request: Request):
    with request.app.state.session_factory() as session:
        yield session


def _trades_frame(trades) -> pd.DataFrame:
    df = pd.DataFrame([t.model_dump() for t in trades])
    df["entry_time"] = pd.to_datetime(df["entry_time"], utc=True)
    return df.sort_values("entry_time").reset_index(drop=True)


def _strategy_trades(db: Session, strategy_id: int) -> pd.DataFrame:
    rows = (db.query(Trade).filter(Trade.strategy_id == strategy_id)
            .order_by(Trade.entry_time).all())
    if not rows:
        raise HTTPException(404, f"no trades for strategy {strategy_id}")
    return pd.DataFrame([{
        "entry_time": pd.Timestamp(t.entry_time, tz="UTC") if t.entry_time.tzinfo is None else t.entry_time,
        "r_multiple": t.r_multiple, "mae_r": t.mae_r or 0.0,
        "session": t.session, "instrument": t.instrument,
    } for t in rows])


# ------------------------------------------------------------------ prop-sim
@router.post("/prop-sim", tags=["survival"])
def create_prop_sim(req: PropSimRequest, db: Session = Depends(get_db)) -> dict:
    firm = _load_firm_or_404(req.firm)
    df = _trades_frame(req.trades)
    days = group_trades_by_day(df, tz=firm.timezone)
    risks = req.risks or sweep_risks(req.sweep.start, req.sweep.stop, req.sweep.step)
    results = run_risk_sweep(days, firm, risks, n_paths=req.n_paths, seed=req.seed,
                             block_size=req.block_size, simulate_funded=req.simulate_funded)
    payload = sweep_to_frame(results).to_dict(orient="records")
    sim = PropSim(strategy_id=req.strategy_id, firm=req.firm, n_paths=req.n_paths,
                  seed=req.seed, params=req.model_dump(exclude={"trades"}, mode="json"),
                  results=payload)
    db.add(sim)
    db.commit()
    return {"id": sim.id, "firm": firm.name, "results": payload}


@router.get("/prop-sim/{sim_id}", tags=["survival"])
def get_prop_sim(sim_id: int, db: Session = Depends(get_db)) -> dict:
    sim = db.get(PropSim, sim_id)
    if sim is None:
        raise HTTPException(404, f"prop_sim {sim_id} not found")
    return {"id": sim.id, "firm": sim.firm, "n_paths": sim.n_paths, "seed": sim.seed,
            "params": sim.params, "results": sim.results,
            "created_at": sim.created_at.isoformat()}


def _load_firm_or_404(name: str):
    try:
        return load_firm(name)
    except FileNotFoundError as exc:
        raise HTTPException(404, str(exc)) from exc


# ------------------------------------------------------------------ backtests
@router.post("/backtests", tags=["backtests"])
def create_backtest(req: BacktestRequest, db: Session = Depends(get_db)) -> dict:
    strat = db.query(Strategy).filter_by(name=req.strategy.name).one_or_none()
    if strat is None:
        strat = Strategy(**req.strategy.model_dump())
        db.add(strat)
        db.flush()

    df = _trades_frame(req.trades)
    r = df["r_multiple"]
    cum = r.cumsum()
    metrics = {
        "expectancy_r": float(r.mean()),
        "win_pct": float((r > 0).mean()),
        "profit_factor": float(r[r > 0].sum() / -r[r < 0].sum()) if (r < 0).any() else None,
        "max_dd_r": float((cum.cummax() - cum).max()),
        "n_trades": int(len(r)),
    }
    run = BacktestRun(strategy_id=strat.id, label=req.label, params=req.params,
                      n_trades=len(df), metrics=metrics)
    db.add(run)
    db.flush()
    db.add_all([
        Trade(strategy_id=strat.id, run_id=run.id,
              entry_time=t.entry_time, exit_time=t.exit_time,
              r_multiple=t.r_multiple, mae_r=t.mae_r, mfe_r=t.mfe_r,
              instrument=t.instrument, direction=t.direction, session=t.session)
        for t in req.trades
    ])
    db.commit()
    return {"run_id": run.id, "strategy_id": strat.id, "metrics": metrics}


@router.get("/backtests/{run_id}/robustness", tags=["backtests"])
def get_robustness(run_id: int, n_trials: int | None = None, db: Session = Depends(get_db)) -> dict:
    run = db.get(BacktestRun, run_id)
    if run is None:
        raise HTTPException(404, f"backtest run {run_id} not found")
    df = _strategy_trades(db, run.strategy_id)

    if n_trials is None:
        strat = db.get(Strategy, run.strategy_id)
        if strat and strat.family:
            from core.overfit.deflated_sharpe import count_family_trials
            n_trials = count_family_trials(db, strat.family)
        else:
            n_trials = 1
    report = robustness_battery(df, n_trials=n_trials)
    run.metrics = {**(run.metrics or {}), "robustness_score": report.score,
                   "robustness_verdict": report.verdict}
    db.commit()
    return report.to_dict()


# ------------------------------------------------------------------ strategies
@router.get("/strategies/{strategy_id}/dna", tags=["strategies"])
def get_dna(strategy_id: int, db: Session = Depends(get_db)) -> dict:
    strat = db.get(Strategy, strategy_id)
    if strat is None:
        raise HTTPException(404, f"strategy {strategy_id} not found")
    trades = _strategy_trades(db, strategy_id)

    streams: dict[str, pd.Series] = {}
    for other in db.query(Strategy).all():
        try:
            streams[other.name] = daily_r_stream(_strategy_trades(db, other.id))
        except HTTPException:
            continue
    dna = analyze_strategy(strat.name, trades, streams, edge_source=strat.edge_source)
    return dna.to_dict()


@router.get("/strategies/{strategy_id}/regime-matrix", tags=["strategies"])
def get_regime_matrix(strategy_id: int, symbol: str | None = None,
                      timeframe: str = "H1", request: Request = None,
                      db: Session = Depends(get_db)) -> dict:
    strat = db.get(Strategy, strategy_id)
    if strat is None:
        raise HTTPException(404, f"strategy {strategy_id} not found")
    symbol = symbol or strat.instrument
    if not symbol:
        raise HTTPException(422, "strategy has no instrument; pass ?symbol=")

    path = bars_path(request.app.state.settings.parquet_dir, symbol, timeframe)
    if not path.exists():
        raise HTTPException(404, f"no bar data at {path}; ingest with bridge.mt5_ingest")
    bars = read_bars_parquet(path)
    labels = classify_rules(compute_features(bars))["regime"]

    trades = _strategy_trades(db, strategy_id).assign(strategy=strat.name)
    matrix = regime_strategy_matrix(trades, labels)
    return {
        "strategy": strat.name,
        "symbol": symbol,
        "timeframe": timeframe,
        "matrix": matrix.to_dict(orient="records"),
        "recommendations": [vars(r) for r in recommendations(matrix)],
    }


# ------------------------------------------------------------------ portfolios
@router.post("/portfolios/optimize", tags=["portfolios"])
def portfolios_optimize(req: PortfolioOptimizeRequest, db: Session = Depends(get_db)) -> dict:
    firm = _load_firm_or_404(req.firm)
    trades_by_strategy: dict[str, pd.DataFrame] = {}
    meta: dict[str, StrategyMeta] = {}
    for sid in req.strategy_ids:
        strat = db.get(Strategy, sid)
        if strat is None:
            raise HTTPException(404, f"strategy {sid} not found")
        trades_by_strategy[strat.name] = _strategy_trades(db, sid)
        meta[strat.name] = StrategyMeta(edge_source=strat.edge_source or f"unknown_{strat.name}",
                                        instrument=strat.instrument or f"unknown_{strat.name}")
    streams = pd.DataFrame({k: daily_r_stream(v) for k, v in trades_by_strategy.items()})
    caps = PortfolioCaps(per_strategy=req.per_strategy_cap,
                         per_edge_source=req.per_edge_source_cap,
                         per_instrument=req.per_instrument_cap)
    try:
        result = optimize_portfolio(streams, trades_by_strategy, firm, meta=meta, caps=caps,
                                    risk_grid=tuple(req.risk_grid), n_frontier=req.n_frontier,
                                    n_paths=req.n_paths, seed=req.seed)
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc
    out = result.to_dict()
    out["frontier_pareto"] = (result.frontier[result.frontier["pareto"]]
                              .to_dict(orient="records"))
    return out


# ------------------------------------------------------------------ ops
@router.get("/ops/state", tags=["ops"])
def ops_state(db: Session = Depends(get_db)) -> dict:
    rows = (db.query(LiveState, Strategy)
            .join(Strategy, LiveState.strategy_id == Strategy.id).all())
    snapshot = (db.query(EquitySnapshot)
                .order_by(EquitySnapshot.ts.desc()).first())
    return {
        "strategies": [{
            "strategy_id": s.id, "name": s.name, "state": ls.state,
            "risk_pct": ls.risk_pct, "enabled": ls.enabled, "reason": ls.reason,
            "updated_at": ls.updated_at.isoformat() if ls.updated_at else None,
        } for ls, s in rows],
        "last_equity_snapshot": ({
            "ts": snapshot.ts.isoformat(), "balance": snapshot.balance,
            "equity": snapshot.equity, "floating_pnl": snapshot.floating_pnl,
        } if snapshot else None),
    }


@router.get("/alerts", tags=["ops"])
def list_alerts(acknowledged: bool | None = None, severity: str | None = None,
                limit: int = 100, db: Session = Depends(get_db)) -> list[dict]:
    q = db.query(Alert).order_by(Alert.ts.desc())
    if acknowledged is not None:
        q = q.filter(Alert.acknowledged == acknowledged)
    if severity is not None:
        q = q.filter(Alert.severity == severity)
    return [{
        "id": a.id, "ts": a.ts.isoformat(), "severity": a.severity, "source": a.source,
        "kind": a.kind, "strategy_id": a.strategy_id, "message": a.message,
        "evidence": a.evidence, "acknowledged": a.acknowledged,
    } for a in q.limit(limit).all()]
