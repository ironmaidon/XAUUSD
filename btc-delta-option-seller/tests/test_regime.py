import pytest

from bos.config import RegimeSettings
from bos.strategy.regime import Regime, RegimeInput, Structure, classify_regime


def values(**changes: float | bool) -> RegimeInput:
    defaults: dict[str, float | bool] = {
        "close": 110,
        "ema20": 105,
        "ema50": 100,
        "normalized_ema20_slope": 0.001,
        "atr14": 10,
        "adx14": 25,
        "absolute_24h_move": 5,
        "volatility_shock": False,
    }
    defaults.update(changes)
    return RegimeInput(**defaults)  # type: ignore[arg-type]


@pytest.mark.parametrize(
    ("inputs", "regime", "structure"),
    [
        (values(), Regime.BULLISH, Structure.BULL_PUT_SPREAD),
        (
            values(close=90, ema20=95, ema50=100, normalized_ema20_slope=-0.001),
            Regime.BEARISH,
            Structure.BEAR_CALL_SPREAD,
        ),
        (
            values(close=101, ema20=100, ema50=99, normalized_ema20_slope=0, adx14=15),
            Regime.NEUTRAL,
            Structure.IRON_CONDOR,
        ),
        (
            values(close=101, ema20=100, ema50=80, normalized_ema20_slope=0, adx14=15),
            Regime.AMBIGUOUS,
            Structure.NO_TRADE,
        ),
    ],
)
def test_regime_classification(inputs: RegimeInput, regime: Regime, structure: Structure) -> None:
    result = classify_regime(inputs, RegimeSettings())
    assert result.regime is regime
    assert result.structure is structure


@pytest.mark.parametrize(
    "inputs",
    [values(adx14=36), values(absolute_24h_move=26), values(volatility_shock=True)],
)
def test_extreme_has_priority(inputs: RegimeInput) -> None:
    result = classify_regime(inputs, RegimeSettings())
    assert result.regime is Regime.EXTREME
    assert result.structure is Structure.NO_TRADE


def test_invalid_atr_is_rejected() -> None:
    with pytest.raises(ValueError, match="ATR"):
        classify_regime(values(atr14=0), RegimeSettings())
