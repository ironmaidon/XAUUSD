from datetime import date
from unittest.mock import AsyncMock

import pytest

from bos.exchange.models import Product, Ticker
from bos.exchange.services import DeltaOptionChainService, DeltaOrderService
from bos.execution.models import OrderRequest
from bos.strategy.structures import Side


@pytest.mark.asyncio
async def test_option_chain_keeps_only_btc_options() -> None:
    products = AsyncMock()
    products.list_tickers.return_value = [
        Ticker(symbol="C-BTC-100000-100926"),
        Ticker(symbol="BTCUSD"),
    ]
    products.list_products.return_value = [
        Product(
            id=1,
            symbol="C-BTC-100000-100926",
            contract_type="call_options",
            strike_price="100000",
            underlying_asset={"symbol": "BTC"},
        ),
        Product(
            id=2,
            symbol="BTCUSD",
            contract_type="perpetual_futures",
            underlying_asset={"symbol": "BTC"},
        ),
    ]
    chain = await DeltaOptionChainService(products).load(date(2026, 9, 10))
    assert [quote.product.id for quote in chain] == [1]
    products.list_tickers.assert_awaited_once_with(
        contract_types="call_options,put_options",
        underlying_asset_symbols="BTC",
        expiry_date="10-09-2026",
    )


@pytest.mark.asyncio
async def test_live_limit_order_uses_current_delta_contract() -> None:
    client = AsyncMock()
    client.request.return_value = {"id": 1}
    request = OrderRequest("BOS1-E-2609031200-DS-L1-1", 7, "WING", Side.BUY, 2, 100.5)
    await DeltaOrderService(client).place_limit(request)
    client.request.assert_awaited_once_with(
        "POST",
        "/v2/orders",
        dict[str, object],
        json_body={
            "product_id": 7,
            "size": 2,
            "side": "buy",
            "order_type": "limit_order",
            "limit_price": "100.5",
            "time_in_force": "gtc",
            "post_only": False,
            "reduce_only": False,
            "client_order_id": "BOS1-E-2609031200-DS-L1-1",
        },
        authenticated=True,
    )
