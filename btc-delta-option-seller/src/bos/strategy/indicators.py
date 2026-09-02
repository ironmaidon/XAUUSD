from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass


@dataclass(frozen=True)
class IndicatorSnapshot:
    ema20: float
    ema50: float
    atr14: float
    adx14: float
    swing_high20: float
    swing_low20: float
    normalized_ema20_slope: float


def ema(values: Sequence[float], period: int) -> list[float]:
    if period < 1 or len(values) < period:
        raise ValueError("insufficient values for EMA")
    seed = sum(values[:period]) / period
    output = [seed]
    multiplier = 2.0 / (period + 1)
    for value in values[period:]:
        output.append((value - output[-1]) * multiplier + output[-1])
    return output


def _wilder(values: Sequence[float], period: int) -> list[float]:
    if len(values) < period:
        raise ValueError("insufficient values for Wilder average")
    output = [sum(values[:period]) / period]
    for value in values[period:]:
        output.append((output[-1] * (period - 1) + value) / period)
    return output


def atr(
    highs: Sequence[float], lows: Sequence[float], closes: Sequence[float], period: int = 14
) -> list[float]:
    if not (len(highs) == len(lows) == len(closes)) or len(closes) < period + 1:
        raise ValueError("OHLC lengths must match and include enough bars")
    true_ranges = [
        max(
            highs[index] - lows[index],
            abs(highs[index] - closes[index - 1]),
            abs(lows[index] - closes[index - 1]),
        )
        for index in range(1, len(closes))
    ]
    return _wilder(true_ranges, period)


def adx(
    highs: Sequence[float], lows: Sequence[float], closes: Sequence[float], period: int = 14
) -> list[float]:
    if not (len(highs) == len(lows) == len(closes)) or len(closes) < period * 2 + 1:
        raise ValueError("ADX requires matching OHLC and at least 2*period+1 bars")
    plus_dm: list[float] = []
    minus_dm: list[float] = []
    tr: list[float] = []
    for index in range(1, len(closes)):
        up = highs[index] - highs[index - 1]
        down = lows[index - 1] - lows[index]
        plus_dm.append(up if up > down and up > 0 else 0.0)
        minus_dm.append(down if down > up and down > 0 else 0.0)
        tr.append(
            max(
                highs[index] - lows[index],
                abs(highs[index] - closes[index - 1]),
                abs(lows[index] - closes[index - 1]),
            )
        )
    atr_values = _wilder(tr, period)
    plus_values = _wilder(plus_dm, period)
    minus_values = _wilder(minus_dm, period)
    dx: list[float] = []
    for average_tr, plus, minus in zip(atr_values, plus_values, minus_values, strict=True):
        plus_di = 100 * plus / average_tr if average_tr else 0.0
        minus_di = 100 * minus / average_tr if average_tr else 0.0
        total = plus_di + minus_di
        dx.append(100 * abs(plus_di - minus_di) / total if total else 0.0)
    return _wilder(dx, period)


def calculate_indicators(
    highs: Sequence[float], lows: Sequence[float], closes: Sequence[float]
) -> IndicatorSnapshot:
    if len(closes) < 50:
        raise ValueError("at least 50 confirmed candles are required")
    ema20_values = ema(closes, 20)
    ema50_values = ema(closes, 50)
    atr_value = atr(highs, lows, closes, 14)[-1]
    slope = (ema20_values[-1] - ema20_values[-2]) / closes[-1]
    return IndicatorSnapshot(
        ema20=ema20_values[-1],
        ema50=ema50_values[-1],
        atr14=atr_value,
        adx14=adx(highs, lows, closes, 14)[-1],
        swing_high20=max(highs[-20:]),
        swing_low20=min(lows[-20:]),
        normalized_ema20_slope=slope,
    )
