from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum

from bos.strategy.structures import Side


class OrderState(StrEnum):
    OPEN = "OPEN"
    PARTIALLY_FILLED = "PARTIALLY_FILLED"
    FILLED = "FILLED"
    CANCELLED = "CANCELLED"
    REJECTED = "REJECTED"


@dataclass(frozen=True)
class OrderRequest:
    client_order_id: str
    product_id: int
    symbol: str
    side: Side
    quantity: float
    limit_price: float
    reduce_only: bool = False


@dataclass(frozen=True)
class Order:
    order_id: str
    request: OrderRequest
    state: OrderState
    created_at: datetime
    eligible_at: datetime
    updated_at: datetime
    filled_quantity: float = 0
    average_fill_price: float | None = None
    rejection_reason: str | None = None

    @property
    def remaining_quantity(self) -> float:
        return max(0.0, self.request.quantity - self.filled_quantity)


@dataclass(frozen=True)
class Fill:
    fill_id: str
    order_id: str
    client_order_id: str
    product_id: int
    symbol: str
    side: Side
    quantity: float
    price: float
    timestamp: datetime
    simulated: bool = True
