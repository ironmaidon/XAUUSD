from __future__ import annotations

import argparse
import asyncio
import time
from pathlib import Path

from bos.config import load_settings
from bos.exchange.models import Candle
from bos.exchange.rest import DeltaRestClient
from bos.exchange.services import DeltaProductService
from bos.logging import configure_logging


async def verify_public(config: Path | None) -> None:
    settings = load_settings(config)
    configure_logging(settings.logging)
    async with DeltaRestClient(settings.exchange) as client:
        products = DeltaProductService(client)
        btc = await products.get_product("BTCUSD")
        ticker = await products.get_ticker("BTCUSD")
        print(f"validated product={btc.symbol} id={btc.id} ticker={ticker.symbol}")


async def verify_history(config: Path | None) -> None:
    settings = load_settings(config)
    configure_logging(settings.logging)
    now = int(time.time())
    async with DeltaRestClient(settings.exchange) as client:
        candles = await client.request(
            "GET",
            "/v2/history/candles",
            list[Candle],
            params={"symbol": "BTCUSD", "resolution": "1h", "start": now - 10800, "end": now},
        )
        print(f"validated BTCUSD historical candles rows={len(candles)}")


def main() -> None:
    parser = argparse.ArgumentParser(prog="bos")
    parser.add_argument("command", choices=["verify-public", "verify-history"])
    parser.add_argument("--config", type=Path)
    args = parser.parse_args()
    if args.command == "verify-public":
        asyncio.run(verify_public(args.config))
    elif args.command == "verify-history":
        asyncio.run(verify_history(args.config))
