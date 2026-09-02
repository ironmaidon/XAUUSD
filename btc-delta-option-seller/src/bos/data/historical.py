from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from typing import cast

from bos.config import HistoricalSettings
from bos.data.quality import DataQuality
from bos.data.store import HistoricalStore
from bos.exchange.models import Candle, Product
from bos.exchange.rest import DeltaRestClient

RESOLUTION_SECONDS = {
    "1m": 60,
    "3m": 180,
    "5m": 300,
    "15m": 900,
    "30m": 1800,
    "1h": 3600,
    "2h": 7200,
    "4h": 14400,
    "6h": 21600,
    "1d": 86400,
    "1w": 604800,
}


class DeltaHistoricalDownloader:
    def __init__(
        self, client: DeltaRestClient, store: HistoricalStore, settings: HistoricalSettings
    ):
        self.client = client
        self.store = store
        self.settings = settings

    async def candles(
        self, symbol: str, resolution: str, start: int, end: int, product_id: int | None = None
    ) -> int:
        if resolution not in RESOLUTION_SECONDS:
            raise ValueError(f"Unsupported resolution: {resolution}")
        if end <= start:
            raise ValueError("end must be greater than start")
        window = RESOLUTION_SECONDS[resolution] * self.settings.candle_page_limit
        all_candles: dict[int, Candle] = {}
        cursor = start
        while cursor < end:
            chunk_end = min(end, cursor + window - RESOLUTION_SECONDS[resolution])
            result = await self.client.request(
                "GET",
                "/v2/history/candles",
                list[Candle],
                params={
                    "symbol": symbol,
                    "resolution": resolution,
                    "start": cursor,
                    "end": chunk_end,
                },
            )
            for candle in cast(list[Candle], result):
                if start <= candle.time <= end:
                    all_candles[candle.time] = candle
            cursor = chunk_end + RESOLUTION_SECONDS[resolution]
        ordered = [all_candles[key] for key in sorted(all_candles)]
        inserted = self.store.save_candles(
            symbol, resolution, ordered, product_id=product_id, quality=DataQuality.EXACT
        )
        rows = [c.model_dump(mode="json") for c in ordered]
        now = datetime.now(UTC)
        safe_symbol = symbol.replace(":", "_")
        path = self.store.write_parquet(
            Path("candles") / safe_symbol / resolution / f"{start}-{end}.parquet",
            rows,
            {
                "source": "delta_exchange_india",
                "symbol": symbol,
                "resolution": resolution,
                "downloaded_at": now.isoformat(),
                "quality": DataQuality.EXACT.value,
            },
        )
        self.store.add_manifest(
            source="delta_exchange_india",
            symbol=symbol,
            product_id=product_id,
            data_kind="candles",
            started_at=now,
            completed_at=datetime.now(UTC),
            quality=DataQuality.EXACT.value,
            row_count=len(ordered),
            missing_fields=[],
            parquet_path=str(path),
            metadata_json={"resolution": resolution, "inserted": inserted},
        )
        return len(ordered)

    async def expired_btc_options(self) -> int:
        after: str | None = None
        products: dict[int, Product] = {}
        while True:
            params = {
                "contract_types": "call_options,put_options",
                "states": "expired,settled",
                "page_size": self.settings.product_page_size,
                "after": after,
            }
            envelope = await self.client.request_envelope(
                "GET", "/v2/products", list[Product], params=params
            )
            for product in cast(list[Product], envelope.result):
                if product.underlying_symbol == "BTC":
                    products[product.id] = product
            next_after = (
                str(envelope.meta.get("after"))
                if envelope.meta and envelope.meta.get("after")
                else None
            )
            if not next_after or next_after == after:
                break
            after = next_after
        return self.store.save_products(products.values())
