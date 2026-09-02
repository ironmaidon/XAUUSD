from __future__ import annotations

from collections.abc import Iterable
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pyarrow as pa  # type: ignore[import-untyped]
import pyarrow.parquet as pq  # type: ignore[import-untyped]
from sqlalchemy.dialects.sqlite import insert
from sqlalchemy.orm import Session, sessionmaker

from bos.data.db import CandleRow, DownloadManifestRow, ProductRow
from bos.data.quality import DataQuality
from bos.exchange.models import Candle, Product


class HistoricalStore:
    def __init__(self, sessions: sessionmaker[Session], parquet_root: Path) -> None:
        self.sessions = sessions
        self.parquet_root = parquet_root

    def save_candles(
        self,
        symbol: str,
        resolution: str,
        candles: Iterable[Candle],
        *,
        product_id: int | None = None,
        quality: DataQuality = DataQuality.EXACT,
    ) -> int:
        now = datetime.now(UTC)
        rows = [
            {
                "symbol": symbol,
                "product_id": product_id,
                "resolution": resolution,
                "timestamp": c.time,
                "open": c.open,
                "high": c.high,
                "low": c.low,
                "close": c.close,
                "volume": c.volume,
                "quality": quality.value,
                "source": "delta_exchange_india",
                "downloaded_at": now,
            }
            for c in candles
        ]
        if not rows:
            return 0
        with self.sessions.begin() as session:
            statement = (
                insert(CandleRow)
                .values(rows)
                .on_conflict_do_nothing(index_elements=["symbol", "resolution", "timestamp"])
            )
            session.execute(statement)
        return len(rows)

    def save_products(self, products: Iterable[Product]) -> int:
        now = datetime.now(UTC)
        rows = [
            {
                "product_id": p.id,
                "symbol": p.symbol,
                "contract_type": p.contract_type,
                "state": getattr(p, "state", None),
                "strike_price": p.strike_price,
                "settlement_time": p.settlement_time,
                "underlying_symbol": p.underlying_symbol,
                "raw": p.model_dump(mode="json"),
                "downloaded_at": now,
            }
            for p in products
        ]
        with self.sessions.begin() as session:
            for row in rows:
                statement = (
                    insert(ProductRow)
                    .values(**row)
                    .on_conflict_do_update(index_elements=["product_id"], set_=row)
                )
                session.execute(statement)
        return len(rows)

    def write_parquet(
        self, relative_path: Path, rows: list[dict[str, Any]], metadata: dict[str, str]
    ) -> Path:
        path = self.parquet_root / relative_path
        path.parent.mkdir(parents=True, exist_ok=True)
        table = pa.Table.from_pylist(rows)
        table = table.replace_schema_metadata({k.encode(): v.encode() for k, v in metadata.items()})
        pq.write_table(table, path, compression="zstd")
        return path

    def add_manifest(self, **values: Any) -> int:
        with self.sessions.begin() as session:
            row = DownloadManifestRow(**values)
            session.add(row)
        return row.id
