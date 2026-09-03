import httpx
import pytest
from pydantic import SecretStr

from bos.config import ExchangeSettings
from bos.exchange.models import DeltaApiError, Product
from bos.exchange.rest import DeltaRestClient


@pytest.mark.asyncio
async def test_product_response_is_validated() -> None:
    async def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/v2/products/BTCUSD"
        assert request.headers["user-agent"] == "btc-delta-option-seller/0.1.0"
        return httpx.Response(
            200,
            json={
                "success": True,
                "result": {
                    "id": 27,
                    "symbol": "BTCUSD",
                    "contract_type": "perpetual_futures",
                },
            },
        )

    client = DeltaRestClient(ExchangeSettings(), httpx.MockTransport(handler))
    try:
        product = await client.request("GET", "/v2/products/BTCUSD", Product)
        assert product.id == 27
    finally:
        await client.close()


@pytest.mark.asyncio
async def test_api_error_is_typed() -> None:
    transport = httpx.MockTransport(
        lambda _: httpx.Response(
            401,
            json={
                "success": False,
                "error": {"code": "invalid_api_key", "message": "invalid"},
            },
        )
    )
    settings = ExchangeSettings(api_key=SecretStr("key"), api_secret=SecretStr("secret"))
    client = DeltaRestClient(settings, transport)
    try:
        with pytest.raises(DeltaApiError, match="invalid_api_key"):
            await client.request("GET", "/v2/positions", dict, authenticated=True)
    finally:
        await client.close()


@pytest.mark.asyncio
async def test_authenticated_call_without_secrets_fails_before_network() -> None:
    client = DeltaRestClient(ExchangeSettings(), httpx.MockTransport(lambda _: httpx.Response(500)))
    try:
        with pytest.raises(RuntimeError, match="environment-provided"):
            await client.request("GET", "/v2/positions", dict, authenticated=True)
    finally:
        await client.close()


@pytest.mark.asyncio
async def test_default_transport_forces_ipv4(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict[str, object] = {}
    real_transport = httpx.AsyncHTTPTransport

    def transport(**kwargs: object) -> httpx.AsyncHTTPTransport:
        captured.update(kwargs)
        return real_transport(**kwargs)

    monkeypatch.setattr(httpx, "AsyncHTTPTransport", transport)
    client = DeltaRestClient(ExchangeSettings())
    await client.close()
    assert captured["local_address"] == "0.0.0.0"
