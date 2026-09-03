from datetime import UTC, datetime

import pytest

from bos.config import ExecutionSettings
from bos.execution.client_ids import ClientOrderIdGenerator
from bos.execution.models import OrderRequest
from bos.execution.repricing import reprice_schedule
from bos.execution.safety import LegOutcome, SafeStructureExecutor
from bos.strategy.structures import (
    OptionMarket,
    OptionType,
    Side,
    build_credit_spread,
    build_iron_condor,
)

NOW = datetime(2026, 9, 3, tzinfo=UTC)


def option(
    symbol: str, strike: float, kind: OptionType, delta: float, bid: float, ask: float
) -> OptionMarket:
    return OptionMarket(1, symbol, kind, strike, bid, ask, 100, 100, delta, received_at=NOW)


def spread():
    return build_credit_spread(
        option("SHORT", 94_000, OptionType.PUT, -0.2, 800, 820),
        option("WING", 90_000, OptionType.PUT, -0.08, 190, 200),
    )


class ScriptedVenue:
    def __init__(self, outcomes: list[LegOutcome]) -> None:
        self.outcomes = outcomes
        self.requests: list[OrderRequest] = []
        self.cancelled = False

    def execute(self, request: OrderRequest, settings: ExecutionSettings) -> LegOutcome:
        self.requests.append(request)
        return (
            self.outcomes.pop(0)
            if self.outcomes
            else LegOutcome(request.quantity, request.limit_price, True)
        )

    def cancel_pending_entries(self) -> None:
        self.cancelled = True


def test_credit_spread_entry_buys_wing_before_short() -> None:
    venue = ScriptedVenue([LegOutcome(1, 200, True), LegOutcome(1, 800, True)])
    result = SafeStructureExecutor(venue, ExecutionSettings()).enter(spread(), 1, NOW)
    assert result.success
    assert [(item.symbol, item.side) for item in venue.requests] == [
        ("WING", Side.BUY),
        ("SHORT", Side.SELL),
    ]


def test_failure_before_short_fill_closes_orphan_wing() -> None:
    venue = ScriptedVenue([LegOutcome(1, 200, True), LegOutcome(0, None, False, "TIMEOUT")])
    result = SafeStructureExecutor(venue, ExecutionSettings()).enter(spread(), 1, NOW)
    assert not result.success
    assert venue.cancelled
    assert [(item.symbol, item.side) for item in result.cleanup_legs] == [("WING", Side.SELL)]


def test_partial_short_fill_is_bought_back_before_wing_removed() -> None:
    venue = ScriptedVenue([LegOutcome(2, 200, True), LegOutcome(1, 800, False, "PARTIAL")])
    result = SafeStructureExecutor(venue, ExecutionSettings()).enter(spread(), 2, NOW)
    assert not result.success
    assert [(item.symbol, item.side, item.quantity) for item in result.cleanup_legs] == [
        ("SHORT", Side.BUY, 1),
        ("WING", Side.SELL, 2),
    ]


def test_iron_condor_buys_both_wings_before_either_short() -> None:
    condor = build_iron_condor(
        option("SP", 94_000, OptionType.PUT, -0.2, 700, 720),
        option("WP", 90_000, OptionType.PUT, -0.08, 190, 200),
        option("SC", 106_000, OptionType.CALL, 0.2, 700, 720),
        option("WC", 110_000, OptionType.CALL, 0.08, 190, 200),
    )
    venue = ScriptedVenue([LegOutcome(1, 1, True)] * 4)
    assert SafeStructureExecutor(venue, ExecutionSettings()).enter(condor, 1, NOW).success
    assert [(item.symbol, item.side) for item in venue.requests] == [
        ("WP", Side.BUY),
        ("WC", Side.BUY),
        ("SP", Side.SELL),
        ("SC", Side.SELL),
    ]


def test_exit_eliminates_short_before_selling_wing() -> None:
    venue = ScriptedVenue([LegOutcome(1, 1, True)] * 2)
    result = SafeStructureExecutor(venue, ExecutionSettings()).exit(spread(), 1, NOW)
    assert result.success
    assert [(item.symbol, item.side) for item in venue.requests] == [
        ("SHORT", Side.BUY),
        ("WING", Side.SELL),
    ]
    assert all(item.reduce_only for item in venue.requests)


def test_client_ids_are_unique_and_within_delta_limit() -> None:
    ids = ClientOrderIdGenerator()
    value = ids.create(NOW, "IRON_CONDOR", "P1", "ENTRY", 1)
    assert len(value) <= 32
    with pytest.raises(ValueError, match="reuse"):
        ids.create(NOW, "IRON_CONDOR", "P1", "ENTRY", 1)


def test_repricing_moves_from_mid_toward_market_with_cap() -> None:
    settings = ExecutionSettings(reprice_fraction=0.25, maximum_reprices=3)
    assert reprice_schedule(Side.BUY, 90, 110, settings) == (100, 105, 110, 110)
    assert reprice_schedule(Side.SELL, 90, 110, settings) == (100, 95, 90, 90)
