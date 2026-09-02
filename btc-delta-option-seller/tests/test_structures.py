from datetime import UTC, datetime, timedelta

import pytest

from bos.config import LiquiditySettings, StrikeSelectionSettings
from bos.strategy.structures import (
    OptionMarket,
    OptionType,
    SelectionError,
    Side,
    build_credit_spread,
    build_iron_condor,
    select_short,
    select_wing,
    validate_market,
)

NOW = datetime(2026, 9, 2, tzinfo=UTC)


def option(
    strike: float, delta: float, kind: OptionType, bid: float = 500, ask: float = 510
) -> OptionMarket:
    return OptionMarket(
        product_id=int(strike),
        symbol=f"{kind}-{strike}",
        option_type=kind,
        strike=strike,
        bid=bid,
        ask=ask,
        bid_size=100,
        ask_size=100,
        delta=delta,
        gamma=0.01,
        theta=-5,
        vega=10,
        received_at=NOW,
    )


def test_put_short_moves_outward_to_pass_expected_move_and_swing() -> None:
    chain = [option(96_000, -0.20, OptionType.PUT), option(94_000, -0.18, OptionType.PUT)]
    selected = select_short(
        chain, OptionType.PUT, 100_000, 5_000, 96_000, 1_000, StrikeSelectionSettings()
    )
    assert selected.strike == 94_000


def test_wing_is_mandatory_and_outward() -> None:
    short = option(94_000, -0.20, OptionType.PUT)
    wing = select_wing(
        [option(90_000, -0.08, OptionType.PUT)], short, 10_000, StrikeSelectionSettings()
    )
    assert wing.strike < short.strike
    with pytest.raises(SelectionError, match="NO_PROTECTIVE_WING"):
        select_wing([], short, 10_000, StrikeSelectionSettings())


def test_executable_credit_spread_metrics() -> None:
    short = option(94_000, -0.20, OptionType.PUT, bid=800, ask=820)
    wing = option(90_000, -0.08, OptionType.PUT, bid=190, ask=200)
    spread = build_credit_spread(short, wing, costs=20)
    assert spread.net_credit == 580
    assert spread.max_loss == 3420
    assert spread.breakevens == (93_420,)
    assert [leg.side for leg in spread.legs] == [Side.BUY, Side.SELL]


def test_iron_condor_max_loss_uses_wider_side() -> None:
    result = build_iron_condor(
        option(94_000, -0.2, OptionType.PUT, 700, 720),
        option(90_000, -0.08, OptionType.PUT, 190, 200),
        option(106_000, 0.2, OptionType.CALL, 700, 720),
        option(111_000, 0.08, OptionType.CALL, 190, 200),
        costs=20,
    )
    assert result.net_credit == 980
    assert result.max_loss == 4020
    assert [leg.side for leg in result.legs[:2]] == [Side.BUY, Side.BUY]


def test_stale_wide_and_thin_markets_fail() -> None:
    liquid = option(94_000, -0.2, OptionType.PUT)
    validate_market(liquid, 1, NOW, 5, 0.08, LiquiditySettings(), Side.SELL)
    with pytest.raises(SelectionError, match="STALE"):
        validate_market(
            liquid, 1, NOW + timedelta(seconds=6), 5, 0.08, LiquiditySettings(), Side.SELL
        )
    wide = option(94_000, -0.2, OptionType.PUT, bid=1, ask=2)
    with pytest.raises(SelectionError, match="WIDE"):
        validate_market(wide, 1, NOW, 5, 0.08, LiquiditySettings(), Side.SELL)
