import pytest

from bos.strategy.indicators import adx, atr, calculate_indicators, ema


def test_ema_known_sequence() -> None:
    assert ema([1, 2, 3, 4, 5], 3) == pytest.approx([2, 3, 4])


def test_atr_constant_range() -> None:
    closes = [100.0] * 16
    highs = [101.0] * 16
    lows = [99.0] * 16
    assert atr(highs, lows, closes)[-1] == pytest.approx(2.0)


def test_adx_and_snapshot_on_confirmed_input() -> None:
    closes = [100.0 + index for index in range(60)]
    highs = [value + 1 for value in closes]
    lows = [value - 1 for value in closes]
    assert adx(highs, lows, closes)[-1] == pytest.approx(100.0)
    result = calculate_indicators(highs, lows, closes)
    assert result.ema20 > result.ema50
    assert result.swing_high20 == 160.0
    assert result.normalized_ema20_slope > 0
