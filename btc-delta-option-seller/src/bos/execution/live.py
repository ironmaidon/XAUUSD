from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Protocol

from bos.config import Mode, Settings
from bos.execution.models import Order, OrderRequest, OrderState
from bos.execution.provider import ExecutionJournal, NullJournal

MANUAL_CONFIRMATION = "ARM LIVE TRADING"


@dataclass(frozen=True)
class LiveSafetyState:
    reconciliation_successful: bool
    heartbeat_healthy: bool
    kill_switch_active: bool


class LiveOrderGateway(Protocol):
    async def place_limit(self, order: OrderRequest) -> dict[str, object]: ...

    async def cancel(self, product_id: int, client_order_id: str) -> dict[str, object]: ...


class LiveTradingGuard:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self._armed = False
        self._safety = LiveSafetyState(False, False, False)

    @property
    def armed(self) -> bool:
        return self._armed

    @property
    def safety(self) -> LiveSafetyState:
        return self._safety

    def update_safety(self, safety: LiveSafetyState) -> None:
        self._safety = safety
        if not self._dynamic_gates_pass(safety):
            self._armed = False

    def arm(self, confirmation: str) -> None:
        failures = self.failures()
        if confirmation != MANUAL_CONFIRMATION:
            raise PermissionError("exact manual live-trading confirmation is required")
        if failures:
            raise PermissionError(f"live trading gates failed: {','.join(failures)}")
        self._armed = True

    def disarm(self) -> None:
        self._armed = False

    def assert_order_allowed(self) -> None:
        if not self._armed:
            raise PermissionError("live trading is disarmed")
        failures = self.failures()
        if failures:
            self._armed = False
            raise PermissionError(f"live trading gates failed: {','.join(failures)}")

    def failures(self) -> tuple[str, ...]:
        failures: list[str] = []
        if self.settings.mode is not Mode.LIVE:
            failures.append("MODE_NOT_LIVE")
        if not self.settings.live.live_trading:
            failures.append("LIVE_ENV_DISABLED")
        if self.settings.exchange.api_key is None or self.settings.exchange.api_secret is None:
            failures.append("CREDENTIALS_MISSING")
        if not self._safety.reconciliation_successful:
            failures.append("RECONCILIATION_FAILED")
        if not self._safety.heartbeat_healthy:
            failures.append("HEARTBEAT_UNHEALTHY")
        if self._safety.kill_switch_active:
            failures.append("KILL_SWITCH_ACTIVE")
        return tuple(failures)

    @staticmethod
    def _dynamic_gates_pass(safety: LiveSafetyState) -> bool:
        return (
            safety.reconciliation_successful
            and safety.heartbeat_healthy
            and not safety.kill_switch_active
        )


class LiveExecutionProvider:
    def __init__(
        self,
        gateway: LiveOrderGateway,
        guard: LiveTradingGuard,
        journal: ExecutionJournal | None = None,
    ) -> None:
        self.gateway = gateway
        self.guard = guard
        self.journal = journal or NullJournal()

    async def submit(self, request: OrderRequest, now: datetime) -> Order:
        self.guard.assert_order_allowed()
        if len(request.client_order_id) > 32 or not request.client_order_id:
            raise ValueError("invalid client_order_id")
        if request.quantity <= 0 or request.limit_price <= 0:
            raise ValueError("live orders require positive quantity and limit price")
        response = await self.gateway.place_limit(request)
        unfilled = float(str(response.get("unfilled_size", request.quantity)))
        order = Order(
            order_id=str(response["id"]),
            request=request,
            state=_map_state(str(response.get("state", "open"))),
            created_at=now,
            eligible_at=now,
            updated_at=now,
            filled_quantity=request.quantity - unfilled,
        )
        self.journal.record_order(order)
        return order

    async def cancel(self, order: Order, now: datetime) -> Order:
        await self.gateway.cancel(order.request.product_id, order.request.client_order_id)
        cancelled = Order(
            **{
                **order.__dict__,
                "state": OrderState.CANCELLED,
                "updated_at": now,
            }
        )
        self.journal.record_order(cancelled)
        return cancelled


def _map_state(value: str) -> OrderState:
    return {
        "open": OrderState.OPEN,
        "pending": OrderState.OPEN,
        "closed": OrderState.FILLED,
        "filled": OrderState.FILLED,
        "cancelled": OrderState.CANCELLED,
        "rejected": OrderState.REJECTED,
    }.get(value.lower(), OrderState.OPEN)
