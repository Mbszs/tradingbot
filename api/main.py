"""FastAPI application factory + /ws/live websocket.

Run with: uvicorn api.main:app --reload  (OpenAPI docs at /docs)
"""
from __future__ import annotations

import asyncio

from fastapi import FastAPI, WebSocket, WebSocketDisconnect

from api.routers import list_alerts, ops_state, router
from core.config import Settings, get_settings
from core.db import get_engine, get_session_factory, init_db


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or get_settings()
    app = FastAPI(
        title="Serpent Lab v2",
        description="Quant research and portfolio management for prop-firm trading EAs",
        version="2.0.0",
    )
    engine = get_engine(settings.db_path)
    init_db(engine)
    app.state.settings = settings
    app.state.session_factory = get_session_factory(engine)
    app.state.ws_poll_seconds = 5.0
    app.include_router(router)

    @app.websocket("/ws/live")
    async def ws_live(websocket: WebSocket) -> None:
        """Streams ops state + recent alerts: one snapshot on connect, then
        a refresh every ws_poll_seconds."""
        await websocket.accept()
        try:
            while True:
                with app.state.session_factory() as db:
                    payload = {
                        "type": "live_state",
                        "ops": ops_state(db=db),
                        "alerts": list_alerts(acknowledged=False, severity=None,
                                              limit=20, db=db),
                    }
                await websocket.send_json(payload)
                await asyncio.sleep(app.state.ws_poll_seconds)
        except WebSocketDisconnect:
            return

    return app


app = create_app()
