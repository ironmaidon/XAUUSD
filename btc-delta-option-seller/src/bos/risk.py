from __future__ import annotations

import math
from dataclasses import dataclass

from bos.config import RiskSettings


@dataclass(frozen=True)
class PortfolioRisk:
    equity: float
    open_defined_risk: float
    daily_realized_pnl: float
    weekly_realized_pnl: float
    drawdown: float
    consecutive_full_stops: int
    open_structures: int
    kill_switch_latched: bool = False


@dataclass(frozen=True)
class RiskDecision:
    allowed: bool
    reasons: tuple[str, ...]
    kill_switch: bool


def maximum_loss_per_contract(
    structure_max_loss: float, contract_size: float, settlement_conversion: float = 1.0
) -> float:
    if structure_max_loss <= 0 or contract_size <= 0 or settlement_conversion <= 0:
        raise ValueError("loss, contract size, and conversion must be positive")
    return structure_max_loss * contract_size * settlement_conversion


def position_size(
    equity: float,
    max_loss_per_contract: float,
    minimum_quantity: float,
    quantity_step: float,
    liquidity_maximum: float,
    settings: RiskSettings,
) -> float:
    if equity <= 0 or max_loss_per_contract <= 0 or minimum_quantity <= 0 or quantity_step <= 0:
        raise ValueError("sizing inputs must be positive")
    risk_pct = min(settings.risk_per_trade, settings.hard_trade_risk_cap)
    raw = min(equity * risk_pct / max_loss_per_contract, liquidity_maximum)
    quantity = math.floor((raw + 1e-12) / quantity_step) * quantity_step
    return round(quantity, 12) if quantity >= minimum_quantity else 0.0


def evaluate_portfolio(state: PortfolioRisk, settings: RiskSettings) -> RiskDecision:
    if state.equity <= 0:
        return RiskDecision(False, ("INVALID_EQUITY",), True)
    reasons: list[str] = []
    kill = state.kill_switch_latched
    if state.open_defined_risk / state.equity >= settings.total_open_defined_risk:
        reasons.append("OPEN_RISK_LIMIT")
    if state.daily_realized_pnl <= -state.equity * settings.daily_realized_loss_limit:
        reasons.append("DAILY_LOSS_LIMIT")
    if state.weekly_realized_pnl <= -state.equity * settings.weekly_realized_loss_limit:
        reasons.append("WEEKLY_LOSS_LIMIT")
    if state.drawdown >= settings.drawdown_kill_switch:
        reasons.append("DRAWDOWN_KILL_SWITCH")
        kill = True
    if state.consecutive_full_stops >= settings.consecutive_full_stop_limit:
        reasons.append("CONSECUTIVE_STOP_KILL_SWITCH")
        kill = True
    if state.open_structures >= settings.maximum_structures:
        reasons.append("MAX_STRUCTURES")
    if state.kill_switch_latched:
        reasons.append("KILL_SWITCH_LATCHED")
    return RiskDecision(not reasons and not kill, tuple(reasons), kill)
