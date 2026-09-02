from __future__ import annotations

import math
import statistics
from collections.abc import Sequence
from dataclasses import dataclass


@dataclass(frozen=True)
class ExpectedMove:
    usd: float
    pct: float
    upper: float
    lower: float


def realized_volatility(
    closes: Sequence[float], window: int = 20, annualization_days: int = 365
) -> float:
    if len(closes) < window + 1:
        raise ValueError(f"RV{window} requires at least {window + 1} closes")
    if any(value <= 0 or not math.isfinite(value) for value in closes[-(window + 1) :]):
        raise ValueError("closes must be positive finite values")
    values = closes[-(window + 1) :]
    returns = [math.log(values[index] / values[index - 1]) for index in range(1, len(values))]
    return statistics.stdev(returns) * math.sqrt(annualization_days)


def atm_iv(call_mark_iv: float | None, put_mark_iv: float | None) -> float | None:
    valid = [value for value in (call_mark_iv, put_mark_iv) if value is not None and value > 0]
    return sum(valid) / len(valid) if valid else None


def iv_percentile(current: float, history: Sequence[float]) -> float:
    valid = [value for value in history if value > 0 and math.isfinite(value)]
    if not valid or current <= 0 or not math.isfinite(current):
        raise ValueError("current and history must contain valid positive IV values")
    return 100.0 * sum(value < current for value in valid) / len(valid)


def vrp_ratio(atm_implied_volatility: float, realized_volatility_value: float) -> float:
    if atm_implied_volatility <= 0 or realized_volatility_value <= 0:
        raise ValueError("IV and RV must be positive")
    return atm_implied_volatility / realized_volatility_value


def expected_move(spot: float, implied_volatility: float, dte: float) -> ExpectedMove:
    if spot <= 0 or implied_volatility <= 0 or dte <= 0:
        raise ValueError("spot, IV, and DTE must be positive")
    move = spot * implied_volatility * math.sqrt(dte / 365.0)
    return ExpectedMove(usd=move, pct=move / spot, upper=spot + move, lower=spot - move)


def skew_25(put_iv: float, call_iv: float) -> float:
    return put_iv - call_iv


def term_ratio(target_iv: float, next_iv: float) -> float:
    if target_iv <= 0 or next_iv <= 0:
        raise ValueError("term IV values must be positive")
    return target_iv / next_iv
