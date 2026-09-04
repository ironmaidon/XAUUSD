from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta, timezone

from bos.strategy.structures import OptionMarket, OptionType

IST = timezone(timedelta(hours=5, minutes=30), name="IST")


@dataclass(frozen=True)
class ZeroDteSettings:
    entry_time: time = time(9, 20)
    exit_time: time = time(16, 30)
    premium_stop_multiple: float = 2.0
    gross_notional_multiple: float = 10.0
    contract_size_btc: float = 0.001
    minimum_quantity: float = 1.0
    quantity_step: float = 1.0


@dataclass(frozen=True)
class StrangleSelection:
    call: OptionMarket
    put: OptionMarket

    @property
    def entry_credit(self) -> float:
        return self.call.bid + self.put.bid


DEFAULT_ZERO_DTE_SETTINGS = ZeroDteSettings()


def local_date(value: datetime) -> date:
    return value.astimezone(IST).date()


def entry_window(value: datetime, already_entered: bool) -> bool:
    local = value.astimezone(IST)
    return not already_entered and time(9, 20) <= local.time() < time(9, 21)


def forced_exit_due(value: datetime) -> bool:
    return value.astimezone(IST).time() >= time(16, 30)


def select_lowest_available_delta(markets: list[OptionMarket]) -> StrangleSelection:
    calls = [
        market for market in markets if market.option_type is OptionType.CALL and market.delta > 0
    ]
    puts = [
        market for market in markets if market.option_type is OptionType.PUT and market.delta < 0
    ]
    if not calls or not puts:
        raise ValueError("BOTH_CALL_AND_PUT_REQUIRED")
    return StrangleSelection(
        call=min(calls, key=lambda market: abs(market.delta)),
        put=min(puts, key=lambda market: abs(market.delta)),
    )


def notional_capped_quantity(
    equity: float, spot: float, settings: ZeroDteSettings = DEFAULT_ZERO_DTE_SETTINGS
) -> float:
    if equity <= 0 or spot <= 0:
        return 0
    combined_notional = 2 * spot * settings.contract_size_btc
    raw = equity * settings.gross_notional_multiple / combined_notional
    quantity = math.floor(raw / settings.quantity_step) * settings.quantity_step
    return quantity if quantity >= settings.minimum_quantity else 0


def premium_stop_due(
    entry_credit: float,
    call_ask: float,
    put_ask: float,
    settings: ZeroDteSettings = DEFAULT_ZERO_DTE_SETTINGS,
) -> bool:
    return call_ask + put_ask >= entry_credit * settings.premium_stop_multiple
