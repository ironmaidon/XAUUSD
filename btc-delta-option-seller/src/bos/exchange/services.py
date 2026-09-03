from __future__ import annotations

from datetime import date
from typing import cast

from bos.exchange.models import OptionQuote, Product, Ticker
from bos.exchange.rest import DeltaRestClient


class DeltaProductService:
    def __init__(self, client: DeltaRestClient) -> None:
        self.client = client

    async def list_products(self) -> list[Product]:
        result = await self.client.request("GET", "/v2/products", list[Product])
        return cast(list[Product], result)

    async def get_product(self, symbol: str) -> Product:
        result = await self.client.request("GET", f"/v2/products/{symbol}", Product)
        return cast(Product, result)

    async def list_tickers(self, **filters: str) -> list[Ticker]:
        result = await self.client.request("GET", "/v2/tickers", list[Ticker], params=filters)
        return cast(list[Ticker], result)

    async def get_ticker(self, symbol: str) -> Ticker:
        result = await self.client.request("GET", f"/v2/tickers/{symbol}", Ticker)
        return cast(Ticker, result)


class DeltaOptionChainService:
    OPTION_TYPES = {"call_options", "put_options"}

    def __init__(self, products: DeltaProductService) -> None:
        self.products = products

    async def load(self, expiry: date | None = None) -> list[OptionQuote]:
        filters = {
            "contract_types": "call_options,put_options",
            "underlying_asset_symbols": "BTC",
        }
        if expiry:
            filters["expiry_date"] = expiry.strftime("%d-%m-%Y")
        tickers = await self.products.list_tickers(**filters)
        product_list = await self.products.list_products()
        by_symbol = {
            p.symbol: p
            for p in product_list
            if p.contract_type in self.OPTION_TYPES and p.underlying_symbol == "BTC"
        }
        return [
            OptionQuote(product=by_symbol[t.symbol], ticker=t)
            for t in tickers
            if t.symbol in by_symbol
        ]


class DeltaOrderService:
    def __init__(self, client: DeltaRestClient) -> None:
        self.client = client

    async def open_orders(self) -> list[dict[str, object]]:
        result = await self.client.request(
            "GET", "/v2/orders", list[dict[str, object]], authenticated=True
        )
        return cast(list[dict[str, object]], result)

    async def recent_fills(self) -> list[dict[str, object]]:
        result = await self.client.request(
            "GET", "/v2/fills", list[dict[str, object]], authenticated=True
        )
        return cast(list[dict[str, object]], result)

    async def cancel(self, product_id: int, client_order_id: str) -> dict[str, object]:
        result = await self.client.request(
            "DELETE",
            "/v2/orders",
            dict[str, object],
            json_body={"product_id": product_id, "client_order_id": client_order_id},
            authenticated=True,
        )
        return cast(dict[str, object], result)


class DeltaPositionService:
    def __init__(self, client: DeltaRestClient) -> None:
        self.client = client

    async def list(self, underlying_asset_symbol: str = "BTC") -> list[dict[str, object]]:
        result = await self.client.request(
            "GET",
            "/v2/positions",
            list[dict[str, object]],
            params={"underlying_asset_symbol": underlying_asset_symbol},
            authenticated=True,
        )
        return cast(list[dict[str, object]], result)


class DeltaWalletService:
    def __init__(self, client: DeltaRestClient) -> None:
        self.client = client

    async def balances(self) -> list[dict[str, object]]:
        result = await self.client.request(
            "GET", "/v2/wallet/balances", list[dict[str, object]], authenticated=True
        )
        return cast(list[dict[str, object]], result)


class DeltaHeartbeatService:
    def __init__(self, client: DeltaRestClient) -> None:
        self.client = client

    async def create(self, heartbeat_id: str) -> dict[str, object]:
        result = await self.client.request(
            "POST",
            "/v2/heartbeat/create",
            dict[str, object],
            json_body={
                "heartbeat_id": heartbeat_id,
                "impact": "all_subaccounts",
                "config": [{"action": "cancel_orders", "unhealthy_count": 1, "tag": "bos1"}],
            },
            authenticated=True,
        )
        return cast(dict[str, object], result)

    async def acknowledge(self, heartbeat_id: str, ttl_ms: int) -> dict[str, object]:
        result = await self.client.request(
            "POST",
            "/v2/heartbeat",
            dict[str, object],
            json_body={"heartbeat_id": heartbeat_id, "ttl": ttl_ms},
            authenticated=True,
        )
        return cast(dict[str, object], result)

    async def list(self, user_id: int) -> list[dict[str, object]]:
        result = await self.client.request(
            "GET",
            "/v2/heartbeat",
            list[dict[str, object]],
            params={"user_id": user_id},
            authenticated=True,
        )
        return cast(list[dict[str, object]], result)
