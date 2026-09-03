from __future__ import annotations

from collections.abc import Awaitable, Callable
from pathlib import Path
from typing import cast

from fastapi import FastAPI, HTTPException, Request, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import SecretStr

from bos.config import Environment, ExchangeSettings, Settings
from bos.dashboard.models import (
    ConnectionView,
    CredentialRequest,
    DashboardSnapshot,
    PaperTradingView,
)
from bos.dashboard.state import DashboardState
from bos.exchange.rest import DeltaRestClient
from bos.exchange.services import DeltaWalletService

CredentialValidator = Callable[[ExchangeSettings], Awaitable[None]]


async def validate_credentials(settings: ExchangeSettings) -> None:
    async with DeltaRestClient(settings) as client:
        await DeltaWalletService(client).balances()


def create_app(
    settings: Settings | None = None,
    state: DashboardState | None = None,
    credential_validator: CredentialValidator = validate_credentials,
) -> FastAPI:
    configured = settings or Settings()
    dashboard = state or DashboardState(configured)
    app = FastAPI(title="BTC Delta Exchange Option Seller V1", version="0.10.0")
    app.state.dashboard = dashboard
    app.state.exchange_settings = configured.exchange
    app.state.credentials_connected = False
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
        allow_credentials=False,
        allow_methods=["GET", "POST"],
        allow_headers=["*"],
    )

    def read_state(request: Request) -> DashboardState:
        return cast(DashboardState, request.app.state.dashboard)

    @app.get("/api/health")
    async def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/api/snapshot", response_model=DashboardSnapshot)
    async def snapshot(request: Request) -> DashboardSnapshot:
        _, value = await read_state(request).get()
        return value

    @app.get("/api/status")
    async def status(request: Request) -> object:
        _, value = await read_state(request).get()
        return value.status

    @app.post("/api/settings/connect", response_model=ConnectionView)
    async def connect(credentials: CredentialRequest, request: Request) -> ConnectionView:
        exchange = ExchangeSettings(
            environment=Environment(credentials.environment),
            api_key=SecretStr(credentials.api_key),
            api_secret=SecretStr(credentials.api_secret),
        )
        try:
            await credential_validator(exchange)
        except Exception as error:
            request.app.state.credentials_connected = False
            _, current = await read_state(request).get()
            current.status.connection = "DISCONNECTED"
            current.status.paper_trading_active = False
            await read_state(request).publish(current)
            raise HTTPException(
                status_code=400, detail="Delta rejected the credentials or could not be reached"
            ) from error

        request.app.state.exchange_settings = exchange
        request.app.state.credentials_connected = True
        _, current = await read_state(request).get()
        current.status.connection = "CONNECTED"
        await read_state(request).publish(current)
        return ConnectionView(
            connected=True,
            environment=credentials.environment,
            message="Delta credentials verified and held in memory for this process only",
        )

    @app.post("/api/paper/start", response_model=PaperTradingView)
    async def start_paper(request: Request) -> PaperTradingView:
        if not request.app.state.credentials_connected:
            raise HTTPException(
                status_code=409, detail="Connect to Delta before starting paper mode"
            )
        _, current = await read_state(request).get()
        current.status.mode = "PAPER"
        current.status.armed = False
        current.status.paper_trading_active = True
        current.status.reconciliation_status = "NOT_REQUIRED_PAPER"
        await read_state(request).publish(current)
        return PaperTradingView(
            active=True, message="Paper trading session started; live execution remains disabled"
        )

    def collection_route(field: str) -> Callable[[Request], Awaitable[object]]:
        async def collection(request: Request) -> object:
            _, value = await read_state(request).get()
            return getattr(value, field)

        return collection

    for path, attribute in {
        "/api/option-chain": "option_chain",
        "/api/trade-candidate": "candidate",
        "/api/risk": "risk",
        "/api/positions": "positions",
        "/api/orders": "orders",
        "/api/fills": "fills",
        "/api/backtests": "backtests",
        "/api/logs": "logs",
    }.items():
        app.add_api_route(path, collection_route(attribute), methods=["GET"])

    @app.websocket("/ws")
    async def updates(websocket: WebSocket) -> None:
        await websocket.accept()
        version = -1
        try:
            while True:
                version, value = await dashboard.wait_after(version)
                await websocket.send_text(value.model_dump_json())
        except WebSocketDisconnect:
            return

    frontend = (Path(__file__).resolve().parents[3] / "frontend" / "dist").resolve()
    if frontend.is_dir():
        assets = frontend / "assets"
        if assets.is_dir():
            app.mount("/assets", StaticFiles(directory=assets), name="dashboard-assets")

        @app.get("/{client_path:path}", include_in_schema=False)
        async def dashboard_client(client_path: str) -> FileResponse:
            if client_path.startswith("api/"):
                raise HTTPException(status_code=404)

            requested = (frontend / client_path).resolve()
            if client_path and requested.is_file() and frontend in requested.parents:
                return FileResponse(requested)
            return FileResponse(frontend / "index.html")

    return app


app = create_app()
