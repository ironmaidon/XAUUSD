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
            filters["expiry_date"] = expiry.isoformat()
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
    """M1 boundary: no order-submission methods exist until execution safety is implemented."""


class DeltaPositionService:
    pass


class DeltaWalletService:
    pass


class DeltaHeartbeatService:
    pass
