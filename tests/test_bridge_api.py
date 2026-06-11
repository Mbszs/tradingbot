"""Module 7 (bridge + API) tests."""
from __future__ import annotations

import json

import numpy as np
import pandas as pd
import pytest
from fastapi.testclient import TestClient

from bridge.mt5_ingest import bars_path, read_bars_parquet, write_bars_parquet
from bridge.signals import (
    SIGNAL_SCHEMA_VERSION,
    SignalFile,
    StrategySignal,
    build_signals_from_db,
    read_signals,
    write_signals,
)
from core.config import Settings
from core.regime.sample_data import generate_sample_ohlc
from core.survival.sample import generate_sample_trades


# ---------------------------------------------------------------- bridge
def test_parquet_roundtrip_zstd_and_merge(tmp_path):
    bars = generate_sample_ohlc([("chop", 100)], seed=1).drop(columns=["segment"])
    path = bars_path(tmp_path, "EURUSD", "H1")
    write_bars_parquet(bars.iloc[:60], path)
    write_bars_parquet(bars.iloc[40:], path)  # overlapping write -> dedup
    out = read_bars_parquet(path)
    assert len(out) == 100
    assert out.index.is_monotonic_increasing
    pd.testing.assert_frame_equal(out, bars.rename_axis("time"), check_freq=False)


def test_signal_file_roundtrip_and_atomicity(tmp_path):
    sig = SignalFile(
        generated_at=pd.Timestamp("2026-06-11T14:00:00Z").to_pydatetime(),
        account="ftmo-001",
        strategies={
            "trend_eu": StrategySignal(magic=770001, enabled=True, risk_pct=1.0),
            "mr_gb": StrategySignal(magic=770002, enabled=False, risk_pct=0.0,
                                    state="SUSPENDED", comment="cusum"),
        },
    )
    target = write_signals(sig, tmp_path)
    assert target.name == "signals.json"
    assert not list(tmp_path.glob("*.tmp"))  # no temp litter

    loaded = read_signals(tmp_path)
    assert loaded.version == SIGNAL_SCHEMA_VERSION
    assert loaded.strategies["trend_eu"].risk_pct == 1.0
    assert loaded.strategies["mr_gb"].state == "SUSPENDED"
    assert not loaded.kill_switch

    raw = json.loads(target.read_text())  # contract field names are stable
    assert {"version", "generated_at", "account", "kill_switch", "strategies"} <= set(raw)


def test_build_signals_from_db(tmp_path):
    from core.db import LiveState, Strategy, get_engine, get_session_factory, init_db

    engine = get_engine(tmp_path / "t.db")
    init_db(engine)
    with get_session_factory(engine)() as s:
        strat = Strategy(name="trend_eu", magic_number=770001)
        s.add(strat)
        s.flush()
        s.add(LiveState(strategy_id=strat.id, state="REDUCED", risk_pct=0.5, enabled=True,
                        reason="dd p95"))
        s.commit()
        sig = build_signals_from_db(s, account="acc")
    assert sig.strategies["trend_eu"].magic == 770001
    assert sig.strategies["trend_eu"].risk_pct == 0.5
    assert sig.strategies["trend_eu"].state == "REDUCED"


def test_mt5_guard_raises_off_windows():
    from bridge import mt5_ingest

    if not mt5_ingest.MT5_AVAILABLE:
        with pytest.raises(RuntimeError, match="Windows"):
            mt5_ingest.fetch_bars_mt5("EURUSD", "H1", None, None)


# ---------------------------------------------------------------- api
@pytest.fixture()
def client(tmp_path) -> TestClient:
    from api.main import create_app

    settings = Settings(db_path=tmp_path / "api.db", parquet_dir=tmp_path / "parquet",
                        signals_dir=tmp_path / "signals")
    return TestClient(create_app(settings))


def _trades_payload(n=240, seed=42, **kw) -> list[dict]:
    df = generate_sample_trades(n=n, seed=seed, **kw)
    df["entry_time"] = df["entry_time"].astype(str)
    df["exit_time"] = df["exit_time"].astype(str)
    return df.to_dict(orient="records")


def _post_backtest(client, name="alpha", seed=42, instrument="EURUSD", edge="trend"):
    return client.post("/backtests", json={
        "strategy": {"name": name, "edge_source": edge, "instrument": instrument,
                     "timeframe": "H1", "family": f"{edge}_family"},
        "label": "v1",
        "trades": _trades_payload(seed=seed),
    })


def test_prop_sim_post_and_get(client):
    resp = client.post("/prop-sim", json={
        "trades": _trades_payload(n=200),
        "firm": "ftmo_100k_2step",
        "risks": [0.5, 1.0],
        "n_paths": 1000,
    })
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert len(body["results"]) == 2
    assert body["results"][1]["risk_pct"] == 1.0
    assert 0 <= body["results"][1]["p_pass"] <= 1

    got = client.get(f"/prop-sim/{body['id']}")
    assert got.status_code == 200
    assert got.json()["results"] == body["results"]
    assert client.get("/prop-sim/99999").status_code == 404


def test_prop_sim_unknown_firm_404(client):
    resp = client.post("/prop-sim", json={"trades": _trades_payload(n=50), "firm": "nope"})
    assert resp.status_code == 404


def test_backtest_and_robustness(client):
    resp = _post_backtest(client)
    assert resp.status_code == 200, resp.text
    run_id = resp.json()["run_id"]
    assert resp.json()["metrics"]["n_trades"] == 240

    rob = client.get(f"/backtests/{run_id}/robustness")
    assert rob.status_code == 200, rob.text
    body = rob.json()
    assert 0 <= body["score"] <= 100
    assert body["verdict"] in ("PASS", "WARN", "REJECT")
    assert set(body["components"]) == {"wfe", "cpcv", "mc", "plateau",
                                       "cost_stress", "regime_div", "trade_count"}


def test_strategy_dna_endpoint(client):
    sid = _post_backtest(client, "alpha", seed=1).json()["strategy_id"]
    _post_backtest(client, "beta", seed=2)
    resp = client.get(f"/strategies/{sid}/dna")
    assert resp.status_code == 200, resp.text
    dna = resp.json()
    assert dna["strategy"] == "alpha"
    assert "beta" in dna["correlations_full"]
    assert dna["edge_source"] == "trend"


def test_regime_matrix_endpoint(client, tmp_path):
    sid = _post_backtest(client, "alpha", seed=1).json()["strategy_id"]
    # trades start 2024-01-01; bars must cover that span
    bars = generate_sample_ohlc([("chop", 300), ("trend_up_quiet", 300)],
                                start="2023-06-01", seed=3).drop(columns=["segment"])
    write_bars_parquet(bars, bars_path(tmp_path / "parquet", "EURUSD", "H1"))

    resp = client.get(f"/strategies/{sid}/regime-matrix")
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["symbol"] == "EURUSD"
    assert len(body["matrix"]) >= 1
    assert {"regime", "n_trades", "expectancy_r", "profit_factor"} <= set(body["matrix"][0])
    assert all(r["action"] in ("enable", "disable", "neutral") for r in body["recommendations"])

    missing = client.get(f"/strategies/{sid}/regime-matrix", params={"symbol": "GBPUSD"})
    assert missing.status_code == 404


def test_portfolio_optimize_endpoint(client):
    ids = [_post_backtest(client, n, seed=s, instrument=i, edge=e).json()["strategy_id"]
           for n, s, i, e in [("alpha", 1, "EURUSD", "trend"),
                              ("beta", 2, "GBPUSD", "meanrev"),
                              ("gamma", 3, "XAUUSD", "breakout")]]
    resp = client.post("/portfolios/optimize", json={
        "strategy_ids": ids,
        "risk_grid": [0.5, 1.0],
        "per_strategy_cap": 0.40,
        "n_frontier": 500,
        "n_paths": 1000,
    })
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["best"] is not None
    assert body["best"]["feasible"]
    assert abs(sum(body["best"]["weights"].values()) - 1.0) < 1e-6
    assert len(body["frontier_pareto"]) >= 1


def test_ops_state_alerts_and_ws(client):
    sid = _post_backtest(client, "alpha", seed=1).json()["strategy_id"]
    # drive a decay transition to populate live_state + alerts
    from core.db import get_engine, get_session_factory
    from core.decay.state_machine import apply_evaluation, evaluate_decay

    engine = get_engine(client.app.state.settings.db_path)
    with get_session_factory(engine)() as s:
        hist = np.random.default_rng(0).choice([2.0, -1.0], 500)
        ev = evaluate_decay("alpha", "HEALTHY", pd.DataFrame({"r_multiple": [-1.0] * 60}), hist)
        apply_evaluation(s, sid, ev, base_risk_pct=1.0)

    ops = client.get("/ops/state").json()
    assert ops["strategies"][0]["state"] == "SUSPENDED"
    alerts = client.get("/alerts", params={"acknowledged": False}).json()
    assert any(a["kind"] == "state_transition" for a in alerts)

    with client.websocket_connect("/ws/live") as ws:
        msg = ws.receive_json()
        assert msg["type"] == "live_state"
        assert msg["ops"]["strategies"][0]["name"] == "alpha"
        assert len(msg["alerts"]) >= 1


def test_openapi_docs_enabled(client):
    assert client.get("/openapi.json").status_code == 200
    assert client.get("/docs").status_code == 200
