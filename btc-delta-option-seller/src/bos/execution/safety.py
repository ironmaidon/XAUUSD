from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime
from typing import Protocol

from bos.config import ExecutionSettings
from bos.execution.client_ids import ClientOrderIdGenerator
from bos.execution.models import OrderRequest
from bos.strategy.structures import DefinedRiskStructure, Leg, Side


@dataclass(frozen=True)
class LegOutcome:
    filled_quantity: float
    average_price: float | None
    completed: bool
    reason: str | None = None


class LegExecutionVenue(Protocol):
    def execute(self, request: OrderRequest, settings: ExecutionSettings) -> LegOutcome: ...

    def cancel_pending_entries(self) -> None: ...


@dataclass(frozen=True)
class ExecutionResult:
    success: bool
    filled_legs: tuple[OrderRequest, ...]
    cleanup_legs: tuple[OrderRequest, ...]
    reason: str | None


class SafeStructureExecutor:
    def __init__(
        self,
        venue: LegExecutionVenue,
        settings: ExecutionSettings,
        ids: ClientOrderIdGenerator | None = None,
    ) -> None:
        self.venue = venue
        self.settings = settings
        self.ids = ids or ClientOrderIdGenerator()

    def enter(
        self, structure: DefinedRiskStructure, quantity: float, timestamp: datetime
    ) -> ExecutionResult:
        if quantity <= 0:
            raise ValueError("quantity must be positive")
        buys = [leg for leg in structure.legs if leg.side is Side.BUY]
        sells = [leg for leg in structure.legs if leg.side is Side.SELL]
        ordered = buys + sells
        filled: list[OrderRequest] = []
        for index, leg in enumerate(ordered, start=1):
            request = self._request(structure.name, leg, quantity, timestamp, "E", index)
            outcome = self.venue.execute(request, self.settings)
            if outcome.filled_quantity > 0:
                filled.append(
                    OrderRequest(
                        **{
                            **request.__dict__,
                            "quantity": outcome.filled_quantity,
                        }
                    )
                )
            if not outcome.completed or outcome.filled_quantity < quantity:
                self.venue.cancel_pending_entries()
                cleanup = self._cleanup(structure.name, filled, timestamp)
                return ExecutionResult(
                    False, tuple(filled), cleanup, outcome.reason or "PARTIAL_FILL"
                )
        return ExecutionResult(True, tuple(filled), (), None)

    def exit(
        self, structure: DefinedRiskStructure, quantity: float, timestamp: datetime
    ) -> ExecutionResult:
        shorts = [leg for leg in structure.legs if leg.side is Side.SELL]
        wings = [leg for leg in structure.legs if leg.side is Side.BUY]
        ordered = shorts + wings
        filled: list[OrderRequest] = []
        for index, leg in enumerate(ordered, start=1):
            closing = Leg(leg.market, Side.BUY if leg.side is Side.SELL else Side.SELL)
            request = self._request(structure.name, closing, quantity, timestamp, "X", index, True)
            outcome = self.venue.execute(request, self.settings)
            if outcome.filled_quantity > 0:
                filled.append(request)
            if not outcome.completed:
                return ExecutionResult(
                    False, tuple(filled), (), outcome.reason or "EXIT_INCOMPLETE"
                )
        return ExecutionResult(True, tuple(filled), (), None)

    def _cleanup(
        self, structure: str, filled: Sequence[OrderRequest], timestamp: datetime
    ) -> tuple[OrderRequest, ...]:
        cleanup: list[OrderRequest] = []
        # Remove short risk before selling protective inventory.
        priority = sorted(filled, key=lambda item: item.side is Side.BUY)
        for index, original in enumerate(priority, start=1):
            opposite = Side.SELL if original.side is Side.BUY else Side.BUY
            request = OrderRequest(
                client_order_id=self.ids.create(timestamp, structure, f"C{index}", "C", 1),
                product_id=original.product_id,
                symbol=original.symbol,
                side=opposite,
                quantity=original.quantity,
                limit_price=original.limit_price,
                reduce_only=original.side is Side.SELL,
            )
            self.venue.execute(request, self.settings)
            cleanup.append(request)
        return tuple(cleanup)

    def _request(
        self,
        structure: str,
        leg: Leg,
        quantity: float,
        timestamp: datetime,
        phase: str,
        index: int,
        reduce_only: bool = False,
    ) -> OrderRequest:
        price = leg.market.ask if leg.side is Side.BUY else leg.market.bid
        return OrderRequest(
            client_order_id=self.ids.create(timestamp, structure, f"L{index}", phase, 1),
            product_id=leg.market.product_id,
            symbol=leg.market.symbol,
            side=leg.side,
            quantity=quantity,
            limit_price=price,
            reduce_only=reduce_only,
        )
