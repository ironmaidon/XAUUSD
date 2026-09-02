from datetime import UTC, datetime, timedelta

import pytest

from bos.backtest.engine import BacktestEngine, EntryIntent, ExitReason, MarketFrame
from bos.config import BacktestSettings, RiskSettings
from bos.data.quality import DataQuality
from bos.strategy.structures import OptionMarket, OptionType, build_credit_spread

START = datetime(2026, 1, 1, tzinfo=UTC)
EXPIRY = START + timedelta(days=7)


def market(
    symbol: str,
    strike: float,
    delta: float,
    bid: float,
    ask: float,
    timestamp: datetime,
    size: float = 100,
) -> OptionMarket:
    return OptionMarket(
        product_id=int(strike),
        symbol=symbol,
        option_type=OptionType.PUT,
        strike=strike,
        bid=bid,
        ask=ask,
        bid_size=size,
        ask_size=size,
        delta=delta,
        received_at=timestamp,
    )


def frame(
    timestamp: datetime,
    short_bid: float,
    short_ask: float,
    wing_bid: float,
    wing_ask: float,
    delta: float = -0.20,
    quality: DataQuality = DataQuality.EXACT,
    size: float = 100,
) -> MarketFrame:
    short = market("SHORT", 94_000, delta, short_bid, short_ask, timestamp, size)
    wing = market("WING", 90_000, -0.08, wing_bid, wing_ask, timestamp, size)
    return MarketFrame(timestamp, {"SHORT": short, "WING": wing}, quality)


def intent(entry: MarketFrame, liquidity_maximum: float = 100) -> EntryIntent:
    structure = build_credit_spread(entry.quotes["SHORT"], entry.quotes["WING"])
    return EntryIntent(
        structure=structure,
        expiry=EXPIRY,
        contract_size=1,
        liquidity_maximum=liquidity_maximum,
    )


def first_frame_strategy(entry: MarketFrame):
    def strategy(current: MarketFrame, history: tuple[MarketFrame, ...]) -> EntryIntent | None:
        assert history[-1] is current
        assert all(item.timestamp <= current.timestamp for item in history)
        return intent(entry) if current.timestamp == entry.timestamp else None

    return strategy


def engine(**changes: float) -> BacktestEngine:
    defaults = {
        "initial_equity": 1_000_000,
        "slippage_bps": 0,
        "option_fee_rate": 0,
        "gst_rate": 0,
    }
    defaults.update(changes)
    return BacktestEngine(BacktestSettings(**defaults), RiskSettings())


def test_profit_target_uses_executable_close_bid_ask() -> None:
    entry = frame(START, 800, 820, 190, 200)
    profitable = frame(START + timedelta(hours=4), 280, 300, 100, 110)
    result = engine().run([entry, profitable], first_frame_strategy(entry))
    assert len(result.trades) == 1
    assert result.trades[0].exit_reason is ExitReason.PROFIT_TARGET
    assert result.trades[0].entry_credit == 600
    assert result.trades[0].exit_debit == 200
    assert result.trades[0].net_pnl == 400


def test_premium_and_delta_stops() -> None:
    entry = frame(START, 800, 820, 190, 200)
    expensive = frame(START + timedelta(hours=4), 1480, 1500, 100, 110)
    premium = engine().run([entry, expensive], first_frame_strategy(entry))
    assert premium.trades[0].exit_reason is ExitReason.PREMIUM_STOP

    threatened = frame(START + timedelta(hours=4), 800, 820, 190, 200, delta=-0.36)
    delta = engine().run([entry, threatened], first_frame_strategy(entry))
    assert delta.trades[0].exit_reason is ExitReason.DELTA_STOP


def test_emergency_delta_has_priority_over_profit() -> None:
    entry = frame(START, 800, 820, 190, 200)
    cheap_but_dangerous = frame(START + timedelta(hours=4), 280, 300, 100, 110, delta=-0.41)
    result = engine().run([entry, cheap_but_dangerous], first_frame_strategy(entry))
    assert result.trades[0].exit_reason is ExitReason.EMERGENCY_DELTA


def test_time_exit_before_zero_dte() -> None:
    entry = frame(START, 800, 820, 190, 200)
    time_exit = frame(EXPIRY - timedelta(hours=30), 800, 820, 190, 200)
    result = engine().run([entry, time_exit], first_frame_strategy(entry))
    assert result.trades[0].exit_reason is ExitReason.TIME_EXIT


def test_fees_slippage_and_configuration_are_reproducible() -> None:
    entry = frame(START, 800, 820, 190, 200)
    final = frame(START + timedelta(hours=4), 280, 300, 100, 110)
    configured = engine(slippage_bps=10, option_fee_rate=0.001, gst_rate=0.18)
    result = configured.run([entry, final], first_frame_strategy(entry))
    assert result.trades[0].fees > 0
    assert result.trades[0].net_pnl < 400
    assert result.fee_configuration["slippage_bps"] == 10
    assert configured.configuration_snapshot()["backtest"]["gst_rate"] == 0.18


def test_partial_liquidity_reduces_fill_without_naked_legs() -> None:
    entry = frame(START, 800, 820, 190, 200, size=10)
    final = frame(START + timedelta(hours=4), 280, 300, 100, 110, size=10)
    result = engine(partial_fill_ratio=0.5).run([entry, final], first_frame_strategy(entry))
    assert result.trades[0].quantity == 1  # risk budget is tighter than five contracts


def test_quality_mix_and_mixed_trade_quality_are_reported() -> None:
    entry = frame(START, 800, 820, 190, 200, quality=DataQuality.EXACT)
    final = frame(
        START + timedelta(hours=4),
        280,
        300,
        100,
        110,
        quality=DataQuality.ESTIMATED,
    )
    result = engine().run([entry, final], first_frame_strategy(entry))
    assert result.quality_percentages[DataQuality.EXACT] == 50
    assert result.quality_percentages[DataQuality.ESTIMATED] == 50
    assert result.trades[0].quality is DataQuality.RECONSTRUCTED


def test_unsorted_or_duplicate_events_are_rejected() -> None:
    one = frame(START, 800, 820, 190, 200)
    with pytest.raises(ValueError, match="strictly increasing"):
        engine().run([one, one], first_frame_strategy(one))


def test_costs_can_reject_entry() -> None:
    entry = frame(START, 201, 210, 199, 200)
    result = engine(option_fee_rate=1).run([entry], first_frame_strategy(entry))
    assert result.trades == ()
    assert result.rejected_entries == ("COSTS_EXCEED_CREDIT",)


def test_consecutive_stops_latch_and_block_future_entries() -> None:
    frames = []
    for index in range(7):
        timestamp = START + timedelta(hours=index)
        if index % 2 == 0:
            frames.append(frame(timestamp, 800, 820, 190, 200))
        else:
            frames.append(frame(timestamp, 1480, 1500, 100, 110))

    def repeated_entries(
        current: MarketFrame, history: tuple[MarketFrame, ...]
    ) -> EntryIntent | None:
        return intent(current) if len(history) in {1, 3, 5, 7} else None

    result = engine().run(frames, repeated_entries)
    assert len(result.trades) == 3
    assert "CONSECUTIVE_STOP_KILL_SWITCH" in result.rejected_entries


def test_disappearing_quote_is_not_valued_optimistically() -> None:
    entry = frame(START, 800, 820, 190, 200)
    missing = MarketFrame(START + timedelta(hours=4), {"WING": entry.quotes["WING"]})
    result = engine().run([entry, missing], first_frame_strategy(entry))
    trade = result.trades[0]
    assert trade.exit_reason is ExitReason.MISSING_QUOTE
    assert trade.net_pnl == -trade.max_loss
    assert trade.quality is DataQuality.ESTIMATED
