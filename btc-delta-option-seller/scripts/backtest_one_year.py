from __future__ import annotations

import asyncio
import json
import math
import statistics
import time
from collections import Counter
from datetime import UTC, datetime, timedelta
from pathlib import Path

from bos.backtest.engine import BacktestEngine, EntryIntent, MarketFrame
from bos.config import BacktestSettings, RiskSettings, Settings, StrikeSelectionSettings
from bos.data.quality import DataQuality
from bos.exchange.models import Candle
from bos.exchange.rest import DeltaRestClient
from bos.strategy.indicators import calculate_indicators
from bos.strategy.regime import RegimeInput, Structure, classify_regime
from bos.strategy.structures import (
    OptionMarket,
    OptionType,
    SelectionError,
    build_credit_spread,
    build_iron_condor,
    select_short,
    select_wing,
)
from bos.strategy.volatility import expected_move, realized_volatility


def normal_cdf(value: float) -> float:
    return 0.5 * (1 + math.erf(value / math.sqrt(2)))


def option_quote(
    spot: float,
    strike: float,
    iv: float,
    years: float,
    kind: OptionType,
    symbol: str,
    now: datetime,
) -> OptionMarket:
    root = iv * math.sqrt(years)
    d1 = (math.log(spot / strike) + 0.5 * iv * iv * years) / root
    d2 = d1 - root
    if kind is OptionType.CALL:
        fair = spot * normal_cdf(d1) - strike * normal_cdf(d2)
        delta = normal_cdf(d1)
    else:
        fair = strike * normal_cdf(-d2) - spot * normal_cdf(-d1)
        delta = normal_cdf(d1) - 1
    width = max(2.0, fair * 0.04)
    return OptionMarket(
        product_id=abs(hash(symbol)) % 2_000_000_000,
        symbol=symbol,
        option_type=kind,
        strike=strike,
        bid=max(0.5, fair - width / 2),
        ask=max(1.0, fair + width / 2),
        bid_size=10,
        ask_size=10,
        delta=delta,
        received_at=now,
    )


async def candles(settings: Settings, start: int, end: int) -> list[Candle]:
    values: dict[int, Candle] = {}
    async with DeltaRestClient(settings.exchange) as client:
        cursor = start
        while cursor < end:
            stop = min(end, cursor + 1_900 * 14_400)
            batch = await client.request(
                "GET",
                "/v2/history/candles",
                list[Candle],
                params={"symbol": "BTCUSD", "resolution": "4h", "start": cursor, "end": stop},
            )
            values.update({item.time: item for item in batch})
            cursor = stop + 1
    return [values[key] for key in sorted(values)]


def build_frames(source: list[Candle]) -> tuple[list[MarketFrame], dict[datetime, int]]:
    frames: list[MarketFrame] = []
    indexes: dict[datetime, int] = {}
    closes = [float(item.close) for item in source]
    for index, item in enumerate(source):
        now = datetime.fromtimestamp(item.time, UTC)
        spot = closes[index]
        returns = [
            math.log(closes[i] / closes[i - 1]) for i in range(max(1, index - 89), index + 1)
        ]
        rv = statistics.stdev(returns) * math.sqrt(6 * 365) if len(returns) > 2 else 0.60
        iv = min(max(rv * 1.20, 0.35), 1.20)
        quotes: dict[str, OptionMarket] = {}
        day = (now + timedelta(days=7)).date()
        expiries = []
        while len(expiries) < 3:
            if day.weekday() == 4:
                expiries.append(datetime(day.year, day.month, day.day, 12, tzinfo=UTC))
            day += timedelta(days=1)
        low = int((spot - 20_000) // 1000) * 1000
        high = int((spot + 20_000) // 1000) * 1000
        for expiry in expiries:
            years = max((expiry - now).total_seconds() / (365 * 86400), 1 / 3650)
            stamp = expiry.strftime("%y%m%d")
            for strike in range(max(1_000, low), high + 1, 1_000):
                for kind, prefix in ((OptionType.PUT, "P"), (OptionType.CALL, "C")):
                    symbol = f"{prefix}-{stamp}-{strike}"
                    quotes[symbol] = option_quote(spot, strike, iv, years, kind, symbol, now)
        frames.append(MarketFrame(now, quotes, DataQuality.ESTIMATED))
        indexes[now] = index
    return frames, indexes


def run(
    source: list[Candle],
    settings: Settings,
    *,
    frames: list[MarketFrame] | None = None,
    indexes: dict[datetime, int] | None = None,
):
    if frames is None or indexes is None:
        frames, indexes = build_frames(source)
    highs = [float(item.high) for item in source]
    lows = [float(item.low) for item in source]
    closes = [float(item.close) for item in source]

    def strategy(frame: MarketFrame, _history: tuple[MarketFrame, ...]) -> EntryIntent | None:
        index = indexes[frame.timestamp]
        if index < 90:
            return None
        indicators = calculate_indicators(
            highs[: index + 1], lows[: index + 1], closes[: index + 1]
        )
        rv = realized_volatility(closes[: index + 1], 20, 6 * 365)
        iv = min(max(rv * 1.20, 0.35), 1.20)
        regime = classify_regime(
            RegimeInput(
                close=closes[index],
                ema20=indicators.ema20,
                ema50=indicators.ema50,
                normalized_ema20_slope=indicators.normalized_ema20_slope,
                atr14=indicators.atr14,
                adx14=indicators.adx14,
                absolute_24h_move=abs(closes[index] - closes[index - 6]),
            ),
            settings.regime,
        )
        if regime.structure is Structure.NO_TRADE:
            return None
        expiries = sorted({symbol.split("-")[1] for symbol in frame.quotes})
        expiry_stamp = expiries[min(1, len(expiries) - 1)]
        expiry = datetime.strptime(expiry_stamp, "%y%m%d").replace(hour=12, tzinfo=UTC)
        chain = [quote for symbol, quote in frame.quotes.items() if expiry_stamp in symbol]
        move = expected_move(closes[index], iv, (expiry - frame.timestamp).total_seconds() / 86400)
        try:

            def spread(kind: OptionType, swing: float):
                short = select_short(
                    chain,
                    kind,
                    closes[index],
                    move.usd,
                    swing,
                    indicators.atr14,
                    settings.strike_selection,
                )
                wing = select_wing(chain, short, move.usd, settings.strike_selection)
                return build_credit_spread(short, wing)

            if regime.structure is Structure.BULL_PUT_SPREAD:
                structure = spread(OptionType.PUT, indicators.swing_low20)
            elif regime.structure is Structure.BEAR_CALL_SPREAD:
                structure = spread(OptionType.CALL, indicators.swing_high20)
            else:
                put, call = (
                    spread(OptionType.PUT, indicators.swing_low20),
                    spread(OptionType.CALL, indicators.swing_high20),
                )
                structure = build_iron_condor(
                    put.legs[1].market, put.legs[0].market, call.legs[1].market, call.legs[0].market
                )
        except SelectionError:
            return None
        return EntryIntent(
            structure,
            expiry,
            contract_size=1,
            minimum_quantity=0.001,
            quantity_step=0.001,
            liquidity_maximum=1,
        )

    return BacktestEngine(settings.backtest, settings.risk).run(frames, strategy)


async def main() -> None:
    settings = Settings()
    end = int(time.time())
    start = end - 365 * 86400
    source = await candles(settings, start, end)
    frames, indexes = build_frames(source)

    scenarios = {
        "production_safety": settings,
        "strategy_diagnostic_no_consecutive_stop_latch": settings.model_copy(
            update={
                "risk": RiskSettings(
                    consecutive_full_stop_limit=999,
                    drawdown_kill_switch=settings.risk.drawdown_kill_switch,
                )
            }
        ),
        "diagnostic_40pct_profit_capture": settings.model_copy(
            update={
                "risk": RiskSettings(consecutive_full_stop_limit=999),
                "backtest": BacktestSettings(profit_capture=0.40),
            }
        ),
        "diagnostic_conservative_15delta": settings.model_copy(
            update={
                "risk": RiskSettings(consecutive_full_stop_limit=999),
                "strike_selection": StrikeSelectionSettings(
                    target_delta=0.15,
                    minimum_delta=0.12,
                    maximum_delta=0.18,
                    expected_move_distance=1.0,
                ),
            }
        ),
    }

    scenario_reports = {}
    for name, scenario in scenarios.items():
        result = run(source, scenario, frames=frames, indexes=indexes)
        pnls = [trade.net_pnl for trade in result.trades]
        wins = sum(value > 0 for value in pnls)
        scenario_reports[name] = {
            "ending_equity": result.ending_equity,
            "net_pnl": result.ending_equity - result.initial_equity,
            "return_pct": (result.ending_equity / result.initial_equity - 1) * 100,
            "trades": len(result.trades),
            "win_rate_pct": wins / len(pnls) * 100 if pnls else 0,
            "average_trade": statistics.mean(pnls) if pnls else 0,
            "exit_reasons": dict(Counter(trade.exit_reason.value for trade in result.trades)),
            "rejection_reasons": dict(Counter(result.rejected_entries)),
        }
    result = run(source, settings, frames=frames, indexes=indexes)
    baseline = scenario_reports["production_safety"]
    report = {
        "period_start": datetime.fromtimestamp(start, UTC).isoformat(),
        "period_end": datetime.fromtimestamp(end, UTC).isoformat(),
        "candle_count": len(source),
        "data_quality": "ESTIMATED_OPTIONS_REAL_UNDERLYING",
        "initial_equity": result.initial_equity,
        "ending_equity": baseline["ending_equity"],
        "net_pnl": baseline["net_pnl"],
        "return_pct": baseline["return_pct"],
        "trades": baseline["trades"],
        "win_rate_pct": baseline["win_rate_pct"],
        "average_trade": baseline["average_trade"],
        "maximum_drawdown_pct": max(
            (result.initial_equity - point.equity) / result.initial_equity * 100
            for point in result.equity_curve
        )
        if result.equity_curve
        else 0,
        "exit_reasons": {
            reason: sum(trade.exit_reason.value == reason for trade in result.trades)
            for reason in sorted({trade.exit_reason.value for trade in result.trades})
        },
        "rejected_entries": len(result.rejected_entries),
        "fees": result.fee_configuration,
        "scenario_comparison": scenario_reports,
    }
    output = Path("reports/backtest-one-year.json")
    output.parent.mkdir(exist_ok=True)
    await asyncio.to_thread(output.write_text, json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    asyncio.run(main())
