from __future__ import annotations

import argparse
import asyncio
from pathlib import Path

from bos.config import load_settings
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


def main() -> None:
    parser = argparse.ArgumentParser(prog="bos")
    parser.add_argument("command", choices=["verify-public"])
    parser.add_argument("--config", type=Path)
    args = parser.parse_args()
    if args.command == "verify-public":
        asyncio.run(verify_public(args.config))

