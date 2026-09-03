from __future__ import annotations

from bos.config import ExecutionSettings
from bos.strategy.structures import Side


def reprice_schedule(
    side: Side, bid: float, ask: float, settings: ExecutionSettings
) -> tuple[float, ...]:
    if bid <= 0 or ask <= bid:
        raise ValueError("valid bid/ask required")
    mid = (bid + ask) / 2
    spread = ask - bid
    prices = [mid]
    for attempt in range(1, settings.maximum_reprices + 1):
        movement = min(spread / 2, spread * settings.reprice_fraction * attempt)
        prices.append(mid + movement if side is Side.BUY else mid - movement)
    worst = ask if side is Side.BUY else bid
    limit = worst * (
        1 + settings.maximum_slippage_bps / 10_000
        if side is Side.BUY
        else 1 - settings.maximum_slippage_bps / 10_000
    )
    if side is Side.BUY:
        return tuple(min(value, limit) for value in prices)
    return tuple(max(value, limit) for value in prices)
