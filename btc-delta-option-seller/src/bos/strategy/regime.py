from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from bos.config import RegimeSettings


class Regime(StrEnum):
    BULLISH = "BULLISH"
    BEARISH = "BEARISH"
    NEUTRAL = "NEUTRAL"
    AMBIGUOUS = "AMBIGUOUS"
    EXTREME = "EXTREME"


class Structure(StrEnum):
    BULL_PUT_SPREAD = "BULL_PUT_SPREAD"
    BEAR_CALL_SPREAD = "BEAR_CALL_SPREAD"
    IRON_CONDOR = "IRON_CONDOR"
    NO_TRADE = "NO_TRADE"


@dataclass(frozen=True)
class RegimeInput:
    close: float
    ema20: float
    ema50: float
    normalized_ema20_slope: float
    atr14: float
    adx14: float
    absolute_24h_move: float
    volatility_shock: bool = False


@dataclass(frozen=True)
class RegimeDecision:
    regime: Regime
    structure: Structure
    reasons: tuple[str, ...]


REGIME_STRUCTURES = {
    Regime.BULLISH: Structure.BULL_PUT_SPREAD,
    Regime.BEARISH: Structure.BEAR_CALL_SPREAD,
    Regime.NEUTRAL: Structure.IRON_CONDOR,
    Regime.AMBIGUOUS: Structure.NO_TRADE,
    Regime.EXTREME: Structure.NO_TRADE,
}


def classify_regime(values: RegimeInput, settings: RegimeSettings) -> RegimeDecision:
    if values.atr14 <= 0:
        raise ValueError("ATR must be positive")
    extreme_reasons: list[str] = []
    if values.adx14 > settings.extreme_adx:
        extreme_reasons.append("ADX_EXTREME")
    if values.absolute_24h_move > settings.extreme_move_atr_multiple * values.atr14:
        extreme_reasons.append("MOVE_EXTREME")
    if values.volatility_shock:
        extreme_reasons.append("VOLATILITY_SHOCK")
    if extreme_reasons:
        return RegimeDecision(Regime.EXTREME, Structure.NO_TRADE, tuple(extreme_reasons))

    directional_adx = settings.directional_adx_min <= values.adx14 <= settings.directional_adx_max
    if (
        values.close > values.ema20 > values.ema50
        and values.normalized_ema20_slope > 0
        and directional_adx
    ):
        return RegimeDecision(Regime.BULLISH, Structure.BULL_PUT_SPREAD, ("BULLISH_TREND",))
    if (
        values.close < values.ema20 < values.ema50
        and values.normalized_ema20_slope < 0
        and directional_adx
    ):
        return RegimeDecision(Regime.BEARISH, Structure.BEAR_CALL_SPREAD, ("BEARISH_TREND",))

    ema_distance = abs(values.ema20 - values.ema50)
    if (
        values.adx14 < settings.neutral_adx_max
        and ema_distance < settings.neutral_ema_atr_ratio * values.atr14
        and abs(values.normalized_ema20_slope) <= settings.flat_slope_threshold
    ):
        return RegimeDecision(Regime.NEUTRAL, Structure.IRON_CONDOR, ("RANGE_REGIME",))

    return RegimeDecision(Regime.AMBIGUOUS, Structure.NO_TRADE, ("NO_CLEAN_REGIME",))
