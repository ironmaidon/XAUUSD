from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field


class VolatilityView(BaseModel):
    atm_iv: float | None = None
    rv20: float | None = None
    vrp: float | None = None
    iv_percentile: float | None = None
    skew_25: float | None = None
    term_ratio: float | None = None
    iv_change_24h: float | None = None
    expected_move_usd: float | None = None


class SystemStatusView(BaseModel):
    mode: Literal["BACKTEST", "REPLAY", "PAPER", "LIVE"] = "PAPER"
    armed: bool = False
    connection: Literal["CONNECTED", "DEGRADED", "DISCONNECTED"] = "DISCONNECTED"
    btc_price: float | None = None
    regime: str = "AMBIGUOUS"
    entry_score: float = Field(default=0, ge=0, le=100)
    target_expiry: datetime | None = None
    dte: float | None = None
    heartbeat_healthy: bool = False
    paper_trading_active: bool = False
    reconciliation_status: str = "NOT_REQUIRED_PAPER"
    volatility: VolatilityView = Field(default_factory=VolatilityView)
    updated_at: datetime


class CandidateView(BaseModel):
    structure: str | None = None
    strikes: list[float] = Field(default_factory=list)
    deltas: list[float] = Field(default_factory=list)
    net_credit: float | None = None
    wing_width: float | None = None
    credit_ratio: float | None = None
    max_loss: float | None = None
    risk_pct: float | None = None
    quantity: float | None = None
    entry_score: float = 0
    eligible: bool = False
    reasons: list[str] = Field(default_factory=lambda: ["NO_EVALUATION"])
    score_components: dict[str, float] = Field(default_factory=dict)


class RiskView(BaseModel):
    account_equity_inr: float = 0
    available_funds_inr: float = 0
    trade_risk_pct: float = 0
    open_defined_risk_pct: float = 0
    margin_usage_pct: float = 0
    daily_pnl: float = 0
    weekly_pnl: float = 0
    current_drawdown_pct: float = 0
    maximum_drawdown_pct: float = 0
    consecutive_losses: int = 0
    kill_switches: list[str] = Field(default_factory=list)


class DashboardSnapshot(BaseModel):
    status: SystemStatusView
    candidate: CandidateView = Field(default_factory=CandidateView)
    risk: RiskView = Field(default_factory=RiskView)
    option_chain: list[dict[str, Any]] = Field(default_factory=list)
    positions: list[dict[str, Any]] = Field(default_factory=list)
    orders: list[dict[str, Any]] = Field(default_factory=list)
    fills: list[dict[str, Any]] = Field(default_factory=list)
    backtests: list[dict[str, Any]] = Field(default_factory=list)
    logs: list[dict[str, Any]] = Field(default_factory=list)
    candles: list[dict[str, Any]] = Field(default_factory=list)


class CredentialRequest(BaseModel):
    environment: Literal["production", "testnet"] = "production"
    api_key: str = Field(min_length=1, max_length=512)
    api_secret: str = Field(min_length=1, max_length=512)


class ConnectionView(BaseModel):
    connected: bool
    environment: Literal["production", "testnet"]
    message: str


class PaperTradingView(BaseModel):
    active: bool
    message: str
