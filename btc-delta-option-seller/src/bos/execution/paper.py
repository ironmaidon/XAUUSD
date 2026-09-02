from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timedelta
from uuid import uuid4

from bos.config import PaperSettings
from bos.execution.models import Fill, Order, OrderRequest, OrderState
from bos.execution.provider import ExecutionJournal, NullJournal
from bos.strategy.structures import OptionMarket, Side


class PaperExecutionProvider:
    def __init__(self, settings: PaperSettings, journal: ExecutionJournal | None = None) -> None:
        self.settings = settings
        self.journal = journal or NullJournal()
        self.orders: dict[str, Order] = {}
        self._client_ids: set[str] = set()
        self.fills: list[Fill] = []

    def submit(self, request: OrderRequest, now: datetime) -> Order:
        rejection = self._validate_request(request)
        state = OrderState.REJECTED if rejection else OrderState.OPEN
        order = Order(
            order_id=f"paper-{uuid4().hex}",
            request=request,
            state=state,
            created_at=now,
            eligible_at=now + timedelta(milliseconds=self.settings.latency_ms),
            updated_at=now,
            rejection_reason=rejection,
        )
        if not rejection:
            self._client_ids.add(request.client_order_id)
        self.orders[order.order_id] = order
        self.journal.record_order(order)
        return order

    def cancel(self, order_id: str, now: datetime) -> Order:
        order = self.orders[order_id]
        if order.state not in {OrderState.OPEN, OrderState.PARTIALLY_FILLED}:
            return order
        updated = replace(order, state=OrderState.CANCELLED, updated_at=now)
        self.orders[order_id] = updated
        self.journal.record_order(updated)
        return updated

    def on_quote(self, quote: OptionMarket, now: datetime) -> tuple[Fill, ...]:
        created: list[Fill] = []
        for order_id, order in tuple(self.orders.items()):
            if order.request.symbol != quote.symbol or order.state not in {
                OrderState.OPEN,
                OrderState.PARTIALLY_FILLED,
            }:
                continue
            if now < order.eligible_at:
                continue
            if not self._valid_quote(quote, now) or not self._marketable(order.request, quote):
                continue
            relevant_size = quote.ask_size if order.request.side is Side.BUY else quote.bid_size
            capacity = relevant_size * self.settings.max_book_participation
            fill_quantity = min(order.remaining_quantity, capacity)
            if fill_quantity <= 0:
                continue
            fill_price = self._fill_price(order.request, quote)
            previous_notional = (order.average_fill_price or 0) * order.filled_quantity
            total_quantity = order.filled_quantity + fill_quantity
            average = (previous_notional + fill_price * fill_quantity) / total_quantity
            state = (
                OrderState.FILLED
                if total_quantity >= order.request.quantity - 1e-12
                else OrderState.PARTIALLY_FILLED
            )
            updated = replace(
                order,
                state=state,
                updated_at=now,
                filled_quantity=total_quantity,
                average_fill_price=average,
            )
            fill = Fill(
                fill_id=f"paper-fill-{uuid4().hex}",
                order_id=order_id,
                client_order_id=order.request.client_order_id,
                product_id=order.request.product_id,
                symbol=order.request.symbol,
                side=order.request.side,
                quantity=fill_quantity,
                price=fill_price,
                timestamp=now,
            )
            self.orders[order_id] = updated
            self.fills.append(fill)
            self.journal.record_fill(fill)
            self.journal.record_order(updated)
            created.append(fill)
        return tuple(created)

    def _validate_request(self, request: OrderRequest) -> str | None:
        if request.client_order_id in self._client_ids:
            return "DUPLICATE_CLIENT_ORDER_ID"
        if not request.client_order_id or len(request.client_order_id) > 32:
            return "INVALID_CLIENT_ORDER_ID"
        if request.quantity <= 0 or request.limit_price <= 0:
            return "INVALID_ORDER_VALUES"
        return None

    def _valid_quote(self, quote: OptionMarket, now: datetime) -> bool:
        age = (now - quote.received_at).total_seconds()
        return (
            0 <= age <= self.settings.reject_stale_after_seconds
            and quote.bid > 0
            and quote.ask > quote.bid
            and quote.bid_size >= 0
            and quote.ask_size >= 0
        )

    @staticmethod
    def _marketable(request: OrderRequest, quote: OptionMarket) -> bool:
        return (
            request.limit_price >= quote.ask
            if request.side is Side.BUY
            else request.limit_price <= quote.bid
        )

    def _fill_price(self, request: OrderRequest, quote: OptionMarket) -> float:
        slip = self.settings.slippage_bps / 10_000
        if request.side is Side.BUY:
            return min(request.limit_price, quote.ask * (1 + slip))
        return max(request.limit_price, quote.bid * (1 - slip))
