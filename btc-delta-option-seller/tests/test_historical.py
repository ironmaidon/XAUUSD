from pathlib import Path
from unittest.mock import AsyncMock

import pyarrow.parquet as pq
import pytest

from bos.config import HistoricalSettings
from bos.data.db import CandleRow, create_session_factory
from bos.data.historical import DeltaHistoricalDownloader
from bos.data.store import HistoricalStore
from bos.exchange.models import ApiEnvelope, Candle, Product


@pytest.mark.asyncio
async def test_candle_downloader_chunks_deduplicates_and_writes_parquet(tmp_path: Path) -> None:
    sessions = create_session_factory(f"sqlite:///{tmp_path / 'test.db'}")
    store = HistoricalStore(sessions, tmp_path / "parquet")
    client = AsyncMock()
    client.request.side_effect = [
        [
            Candle(time=0, open=1, high=2, low=1, close=2, volume=3),
            Candle(time=60, open=2, high=3, low=2, close=3, volume=4),
        ],
        [
            Candle(time=60, open=2, high=3, low=2, close=3, volume=4),
            Candle(time=120, open=3, high=4, low=3, close=4, volume=5),
        ],
    ]
    settings = HistoricalSettings(candle_page_limit=2, parquet_root=tmp_path / "parquet")
    count = await DeltaHistoricalDownloader(client, store, settings).candles("BTCUSD", "1m", 0, 180)
    assert count == 3
    with sessions() as session:
        assert session.query(CandleRow).count() == 3
    file = next((tmp_path / "parquet").rglob("*.parquet"))
    assert pq.read_table(file).num_rows == 3
    assert pq.read_metadata(file).metadata[b"quality"] == b"EXACT"


@pytest.mark.asyncio
async def test_expired_products_follow_after_cursor(tmp_path: Path) -> None:
    sessions = create_session_factory(f"sqlite:///{tmp_path / 'test.db'}")
    store = HistoricalStore(sessions, tmp_path / "parquet")
    client = AsyncMock()
    btc = Product(
        id=1,
        symbol="C-BTC-1-010126",
        contract_type="call_options",
        underlying_asset={"symbol": "BTC"},
    )
    eth = Product(
        id=2,
        symbol="C-ETH-1-010126",
        contract_type="call_options",
        underlying_asset={"symbol": "ETH"},
    )
    client.request_envelope.side_effect = [
        ApiEnvelope(success=True, result=[btc, eth], meta={"after": "next"}),
        ApiEnvelope(success=True, result=[btc], meta={"after": None}),
    ]
    count = await DeltaHistoricalDownloader(
        client, store, HistoricalSettings()
    ).expired_btc_options()
    assert count == 1
    assert client.request_envelope.await_count == 2


@pytest.mark.asyncio
async def test_invalid_candle_range_fails_before_request(tmp_path: Path) -> None:
    store = HistoricalStore(create_session_factory(f"sqlite:///{tmp_path / 'x.db'}"), tmp_path)
    with pytest.raises(ValueError, match="end must"):
        await DeltaHistoricalDownloader(AsyncMock(), store, HistoricalSettings()).candles(
            "BTCUSD", "1h", 2, 1
        )
