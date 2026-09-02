from __future__ import annotations

from datetime import datetime
from typing import Protocol

from bos.execution.models import Fill, Order, OrderRequest
from bos.strategy.structures import OptionMarket


class ExecutionJournal(Protocol):
    def record_order(self, order: Order) -> None: ...

    def record_fill(self, fill: Fill) -> None: ...


class ExecutionProvider(Protocol):
    def submit(self, request: OrderRequest, now: datetime) -> Order: ...

    def on_quote(self, quote: OptionMarket, now: datetime) -> tuple[Fill, ...]: ...

    def cancel(self, order_id: str, now: datetime) -> Order: ...


class NullJournal:
    def record_order(self, order: Order) -> None:
        pass

    def record_fill(self, fill: Fill) -> None:
        pass
