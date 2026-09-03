from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol


class ReconciliationGateway(Protocol):
    async def wallet(self) -> list[dict[str, Any]]: ...

    async def positions(self) -> list[dict[str, Any]]: ...

    async def open_orders(self) -> list[dict[str, Any]]: ...

    async def recent_fills(self) -> list[dict[str, Any]]: ...


@dataclass(frozen=True)
class ReconciliationResult:
    successful: bool
    critical: bool
    new_entries_allowed: bool
    reasons: tuple[str, ...]
    exchange_positions: tuple[dict[str, Any], ...]
    exchange_orders: tuple[dict[str, Any], ...]
    reconstructed: bool


async def reconcile(
    gateway: ReconciliationGateway,
    local_position_product_ids: set[int],
) -> ReconciliationResult:
    try:
        wallet = await gateway.wallet()
        positions = await gateway.positions()
        orders = await gateway.open_orders()
        await gateway.recent_fills()
    except Exception as error:
        return ReconciliationResult(
            False, True, False, (f"RECONCILIATION_ERROR:{type(error).__name__}",), (), (), False
        )
    reasons: list[str] = []
    if not wallet:
        reasons.append("WALLET_UNAVAILABLE")
    exposed = {
        int(position["product_id"]) for position in positions if float(position.get("size", 0)) != 0
    }
    unexpected = exposed - local_position_product_ids
    missing = local_position_product_ids - exposed
    if unexpected:
        reasons.append("UNEXPECTED_EXCHANGE_POSITION")
    if missing:
        reasons.append("LOCAL_POSITION_MISSING_ON_EXCHANGE")
    reconstructed = bool(unexpected)
    critical = bool(reasons)
    return ReconciliationResult(
        successful=not critical,
        critical=critical,
        new_entries_allowed=not critical,
        reasons=tuple(reasons),
        exchange_positions=tuple(positions),
        exchange_orders=tuple(orders),
        reconstructed=reconstructed,
    )
