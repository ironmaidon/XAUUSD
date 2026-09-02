import pytest
from pydantic import SecretStr

from bos.config import Environment, ExchangeSettings
from bos.exchange.signing import sign_websocket
from bos.exchange.websocket import DeltaPrivateWebSocket, DeltaPublicWebSocket


def test_current_key_auth_payload() -> None:
    settings = ExchangeSettings(api_key=SecretStr("key"), api_secret=SecretStr("secret"))
    payload = DeltaPrivateWebSocket(settings).authentication_message(123)
    assert payload == {
        "type": "key-auth",
        "payload": {
            "api-key": "key",
            "timestamp": 123,
            "signature": sign_websocket("secret", "123"),
        },
    }


def test_private_socket_refuses_missing_credentials() -> None:
    with pytest.raises(RuntimeError, match="environment-provided"):
        DeltaPrivateWebSocket(ExchangeSettings()).authentication_message(123)


def test_new_public_endpoint_and_subscription_shape() -> None:
    socket = DeltaPublicWebSocket(ExchangeSettings(environment=Environment.PRODUCTION))
    assert socket.settings.public_ws_url == "wss://public-socket.india.delta.exchange"
    message = socket.subscribe_message([{"name": "ticker", "symbols": ["BTCUSD"]}])
    assert message == {
        "type": "subscribe",
        "payload": {"channels": [{"name": "ticker", "symbols": ["BTCUSD"]}]},
    }
