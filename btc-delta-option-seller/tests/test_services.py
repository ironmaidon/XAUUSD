from datetime import date
from unittest.mock import AsyncMock

import pytest

from bos.exchange.models import Product, Ticker
from bos.exchange.services import DeltaOptionChainService


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
        expiry_date="2026-09-10",
    )
