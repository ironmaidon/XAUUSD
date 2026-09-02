import math
import statistics

import pytest

from bos.strategy.volatility import (
    atm_iv,
    expected_move,
    iv_percentile,
    realized_volatility,
    term_ratio,
    vrp_ratio,
)


def test_rv20_known_numerical_example() -> None:
    closes = [100 * (1.01**index) * (1.002 if index % 2 else 0.998) for index in range(21)]
    returns = [math.log(closes[index] / closes[index - 1]) for index in range(1, 21)]
    assert realized_volatility(closes) == pytest.approx(statistics.stdev(returns) * math.sqrt(365))


def test_rv_rejects_incomplete_or_invalid_data() -> None:
    with pytest.raises(ValueError):
        realized_volatility([100.0] * 20)
    with pytest.raises(ValueError):
        realized_volatility([100.0] * 20 + [0.0])


def test_atm_iv_uses_available_marks_without_invention() -> None:
    assert atm_iv(0.6, 0.8) == pytest.approx(0.7)
    assert atm_iv(0.6, None) == 0.6
    assert atm_iv(None, None) is None


def test_iv_percentile_is_strictly_below() -> None:
    assert iv_percentile(0.5, [0.2, 0.5, 0.7, 0.4]) == 50.0


def test_expected_move_and_vrp() -> None:
    result = expected_move(100_000, 0.60, 7)
    expected = 100_000 * 0.60 * math.sqrt(7 / 365)
    assert result.usd == pytest.approx(expected)
    assert result.upper == pytest.approx(100_000 + expected)
    assert result.lower == pytest.approx(100_000 - expected)
    assert vrp_ratio(0.69, 0.60) == pytest.approx(1.15)
    assert term_ratio(0.75, 0.60) == pytest.approx(1.25)
