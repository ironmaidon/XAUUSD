from datetime import UTC, datetime, timedelta
from pathlib import Path

from sqlalchemy import select

from bos.config import PaperSettings
from bos.data.db import AuditRecord, create_session_factory
from bos.execution.journal import SqlExecutionJournal
from bos.execution.models import OrderRequest, OrderState
from bos.execution.paper import PaperExecutionProvider
from bos.strategy.structures import OptionMarket, OptionType, Side

NOW = datetime(2026, 9, 2, tzinfo=UTC)


def quote(
    *,
    bid: float = 99,
    ask: float = 100,
    bid_size: float = 10,
    ask_size: float = 10,
    received_at: datetime = NOW,
) -> OptionMarket:
    return OptionMarket(
        product_id=1,
        symbol="C-BTC-100000-100926",
        option_type=OptionType.CALL,
        strike=100_000,
        bid=bid,
        ask=ask,
        bid_size=bid_size,
        ask_size=ask_size,
        delta=0.2,
        received_at=received_at,
    )


def request(
    client_id: str = "BOS1-E-260902-C1-A1",
    side: Side = Side.BUY,
    quantity: float = 1,
    limit: float = 101,
) -> OrderRequest:
    return OrderRequest(client_id, 1, "C-BTC-100000-100926", side, quantity, limit)


def test_latency_prevents_instant_fill() -> None:
    provider = PaperExecutionProvider(PaperSettings(latency_ms=250, slippage_bps=0))
    order = provider.submit(request(), NOW)
    assert provider.on_quote(quote(), NOW + timedelta(milliseconds=249)) == ()
    fills = provider.on_quote(quote(), NOW + timedelta(milliseconds=250))
    assert len(fills) == 1
    assert fills[0].price == 100
    assert provider.orders[order.order_id].state is OrderState.FILLED


def test_limit_protection_caps_slippage() -> None:
    provider = PaperExecutionProvider(PaperSettings(latency_ms=0, slippage_bps=100))
    buy = provider.submit(request(limit=100.50), NOW)
    fill = provider.on_quote(quote(), NOW)[0]
    assert fill.price == 100.50
    assert provider.orders[buy.order_id].average_fill_price == 100.50

    sell_request = request("BOS1-X-260902-C1-A1", Side.SELL, limit=98.50)
    provider.submit(sell_request, NOW)
    sell_fill = provider.on_quote(quote(), NOW)[0]
    assert sell_fill.price == 98.50


def test_non_marketable_limit_does_not_fill() -> None:
    provider = PaperExecutionProvider(PaperSettings(latency_ms=0))
    order = provider.submit(request(limit=99.50), NOW)
    assert provider.on_quote(quote(), NOW) == ()
    assert provider.orders[order.order_id].state is OrderState.OPEN


def test_displayed_liquidity_causes_partial_then_complete_fill() -> None:
    provider = PaperExecutionProvider(
        PaperSettings(latency_ms=0, slippage_bps=0, max_book_participation=0.20)
    )
    order = provider.submit(request(quantity=5), NOW)
    first = provider.on_quote(quote(ask_size=10), NOW)
    assert first[0].quantity == 2
    assert provider.orders[order.order_id].state is OrderState.PARTIALLY_FILLED
    second = provider.on_quote(quote(ask_size=20), NOW + timedelta(seconds=1))
    assert second[0].quantity == 3
    assert provider.orders[order.order_id].state is OrderState.FILLED


def test_stale_or_invalid_quote_does_not_fill() -> None:
    provider = PaperExecutionProvider(PaperSettings(latency_ms=0))
    order = provider.submit(request(), NOW)
    stale = quote(received_at=NOW - timedelta(seconds=6))
    assert provider.on_quote(stale, NOW) == ()
    crossed = quote(bid=101, ask=100)
    assert provider.on_quote(crossed, NOW) == ()
    assert provider.orders[order.order_id].state is OrderState.OPEN


def test_duplicate_client_id_and_invalid_values_are_rejected() -> None:
    provider = PaperExecutionProvider(PaperSettings())
    provider.submit(request(), NOW)
    duplicate = provider.submit(request(), NOW)
    assert duplicate.state is OrderState.REJECTED
    assert duplicate.rejection_reason == "DUPLICATE_CLIENT_ORDER_ID"
    invalid = provider.submit(request("x", quantity=0), NOW)
    assert invalid.state is OrderState.REJECTED


def test_open_order_can_be_cancelled_but_fill_is_terminal() -> None:
    provider = PaperExecutionProvider(PaperSettings(latency_ms=0))
    open_order = provider.submit(request(limit=99.50), NOW)
    cancelled = provider.cancel(open_order.order_id, NOW + timedelta(seconds=1))
    assert cancelled.state is OrderState.CANCELLED
    assert provider.on_quote(quote(), NOW + timedelta(seconds=2)) == ()

    filled_order = provider.submit(request("BOS1-E-260902-C1-A2"), NOW)
    provider.on_quote(quote(), NOW)
    assert provider.cancel(filled_order.order_id, NOW).state is OrderState.FILLED


def test_sql_journal_persists_same_order_and_fill_records(tmp_path: Path) -> None:
    sessions = create_session_factory(f"sqlite:///{tmp_path / 'paper.db'}")
    provider = PaperExecutionProvider(
        PaperSettings(latency_ms=0, slippage_bps=0), SqlExecutionJournal(sessions)
    )
    provider.submit(request(), NOW)
    provider.on_quote(quote(), NOW)
    with sessions() as session:
        records = session.scalars(select(AuditRecord).order_by(AuditRecord.id)).all()
    assert [record.kind for record in records] == ["order", "fill", "order"]
    assert records[1].payload["simulated"] is True
    assert records[1].correlation_id == "BOS1-E-260902-C1-A1"
