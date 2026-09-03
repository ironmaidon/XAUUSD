from datetime import UTC, datetime

from fastapi.testclient import TestClient

from bos.config import Settings
from bos.dashboard.app import create_app
from bos.dashboard.models import DashboardSnapshot, SystemStatusView
from bos.dashboard.state import DashboardState
from bos.exchange.models import DeltaApiError


def test_dashboard_defaults_are_paper_and_disarmed() -> None:
    client = TestClient(create_app(Settings()))
    response = client.get("/api/snapshot")
    assert response.status_code == 200
    payload = response.json()
    assert payload["status"]["mode"] == "PAPER"
    assert payload["status"]["armed"] is False
    assert payload["status"]["credentials_connected"] is False
    assert payload["candidate"]["eligible"] is False


def test_dashboard_collections_share_atomic_snapshot() -> None:
    state = DashboardState(Settings())
    snapshot = DashboardSnapshot(
        status=SystemStatusView(updated_at=datetime.now(UTC), connection="CONNECTED"),
        positions=[{"structure": "BULL_PUT_SPREAD"}],
        orders=[{"state": "FILLED"}],
    )
    import asyncio

    asyncio.run(state.publish(snapshot))
    client = TestClient(create_app(Settings(), state))
    assert client.get("/api/positions").json()[0]["structure"] == "BULL_PUT_SPREAD"
    assert client.get("/api/orders").json()[0]["state"] == "FILLED"


def test_websocket_sends_snapshot() -> None:
    with TestClient(create_app(Settings())) as client:
        with client.websocket_connect("/ws") as socket:
            payload = socket.receive_json()
            assert payload["status"]["armed"] is False


def test_unknown_api_route_is_not_hidden_by_dashboard_fallback() -> None:
    client = TestClient(create_app(Settings()))
    assert client.get("/api/does-not-exist").status_code == 404


def test_connect_and_start_paper_trading_without_exposing_credentials() -> None:
    captured = []

    async def validate(exchange: object) -> None:
        captured.append(exchange)

    client = TestClient(create_app(Settings(), credential_validator=validate))
    response = client.post(
        "/api/settings/connect",
        json={"environment": "testnet", "api_key": "key-value", "api_secret": "secret-value"},
    )
    assert response.status_code == 200
    assert response.json()["connected"] is True
    assert "key-value" not in response.text
    assert "secret-value" not in response.text

    started = client.post("/api/paper/start")
    assert started.status_code == 200
    snapshot = client.get("/api/snapshot").json()
    assert snapshot["status"]["mode"] == "PAPER"
    assert snapshot["status"]["armed"] is False
    assert snapshot["status"]["credentials_connected"] is True
    assert snapshot["status"]["paper_trading_active"] is True
    assert captured


def test_paper_trading_requires_verified_connection() -> None:
    client = TestClient(create_app(Settings()))
    response = client.post("/api/paper/start")
    assert response.status_code == 409


def test_connect_reports_safe_delta_error_without_secret() -> None:
    async def reject(_exchange: object) -> None:
        raise DeltaApiError(401, "InvalidApiKey", "Api Key not found")

    client = TestClient(create_app(Settings(), credential_validator=reject))
    response = client.post(
        "/api/settings/connect",
        json={"environment": "testnet", "api_key": "bad-key", "api_secret": "secret"},
    )
    assert response.status_code == 400
    assert response.json()["detail"] == "API key is invalid for the selected testnet environment"
    assert "bad-key" not in response.text
    assert "secret" not in response.text


def test_connect_reports_ip_seen_by_delta() -> None:
    async def reject(_exchange: object) -> None:
        raise DeltaApiError(
            401,
            "ip_not_whitelisted",
            "IP address not whitelisted. Your IP: 203.0.113.42",
        )

    client = TestClient(create_app(Settings(), credential_validator=reject))
    response = client.post(
        "/api/settings/connect",
        json={"environment": "production", "api_key": "key", "api_secret": "secret"},
    )
    assert response.status_code == 400
    assert response.json()["detail"] == (
        "Delta sees public IPv4 203.0.113.42; whitelist that exact address"
    )


def test_connect_trims_pasted_credentials() -> None:
    captured = []

    async def validate(exchange: object) -> None:
        captured.append(exchange)

    client = TestClient(create_app(Settings(), credential_validator=validate))
    response = client.post(
        "/api/settings/connect",
        json={
            "environment": "production",
            "api_key": " key ",
            "api_secret": " secret ",
        },
    )
    assert response.status_code == 200
    exchange = captured[0]
    assert exchange.api_key.get_secret_value() == "key"
    assert exchange.api_secret.get_secret_value() == "secret"


def test_btc_market_feed_updates_dashboard_snapshot() -> None:
    async def price(_exchange: object) -> float:
        return 111_234.5

    client = TestClient(create_app(Settings(), market_price_fetcher=price))
    response = client.get("/api/market/btc")
    assert response.status_code == 200
    assert response.json()["status"]["btc_price"] == 111_234.5
    assert response.json()["status"]["connection"] == "CONNECTED"


def test_btc_market_feed_failure_is_degraded() -> None:
    async def unavailable(_exchange: object) -> float:
        raise TimeoutError

    client = TestClient(create_app(Settings(), market_price_fetcher=unavailable))
    assert client.get("/api/market/btc").status_code == 503
    assert client.get("/api/snapshot").json()["status"]["connection"] == "DEGRADED"
