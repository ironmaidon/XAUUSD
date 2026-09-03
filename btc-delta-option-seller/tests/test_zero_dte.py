from datetime import UTC, datetime

from bos.strategy.structures import OptionMarket, OptionType
from bos.strategy.zero_dte import (
    ZeroDteSettings,
    entry_window,
    forced_exit_due,
    notional_capped_quantity,
    premium_stop_due,
    select_lowest_available_delta,
)


def market(kind: OptionType, delta: float, strike: float) -> OptionMarket:
    return OptionMarket(1, f"{kind}-{strike}", kind, strike, 10, 11, 100, 100, delta)


def test_selects_lowest_listed_delta_on_each_side() -> None:
    selected = select_lowest_available_delta(
        [
            market(OptionType.CALL, 0.20, 110),
            market(OptionType.CALL, 0.11, 120),
            market(OptionType.PUT, -0.18, 90),
            market(OptionType.PUT, -0.09, 80),
        ]
    )
    assert selected.call.delta == 0.11
    assert selected.put.delta == -0.09


def test_ist_schedule() -> None:
    assert entry_window(datetime(2026, 9, 3, 2, 30, 30, tzinfo=UTC), False)
    assert not entry_window(datetime(2026, 9, 3, 2, 31, tzinfo=UTC), False)
    assert forced_exit_due(datetime(2026, 9, 3, 11, 0, tzinfo=UTC))


def test_100_percent_premium_stop_and_ten_x_notional_cap() -> None:
    settings = ZeroDteSettings(contract_size_btc=0.001)
    assert premium_stop_due(100, 101, 99, settings)
    quantity = notional_capped_quantity(1_000, 100_000, settings)
    assert quantity == 50
