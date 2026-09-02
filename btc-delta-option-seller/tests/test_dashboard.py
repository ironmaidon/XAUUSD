from datetime import UTC, datetime

from fastapi.testclient import TestClient

from bos.config import Settings
from bos.dashboard.app import create_app
from bos.dashboard.models import DashboardSnapshot, SystemStatusView
from bos.dashboard.state import DashboardState


def test_dashboard_defaults_are_paper_and_disarmed() -> None:
    client = TestClient(create_app(Settings()))
    response = client.get("/api/snapshot")
    assert response.status_code == 200
    payload = response.json()
    assert payload["status"]["mode"] == "PAPER"
    assert payload["status"]["armed"] is False
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
