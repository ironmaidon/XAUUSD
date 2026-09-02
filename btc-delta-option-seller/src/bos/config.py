from __future__ import annotations

import os
from enum import StrEnum
from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, Field, SecretStr, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Mode(StrEnum):
    BACKTEST = "BACKTEST"
    REPLAY = "REPLAY"
    PAPER = "PAPER"
    LIVE = "LIVE"


class Environment(StrEnum):
    PRODUCTION = "production"
    TESTNET = "testnet"


class ExchangeSettings(BaseModel):
    environment: Environment = Environment.PRODUCTION
    api_key: SecretStr | None = Field(default=None, repr=False)
    api_secret: SecretStr | None = Field(default=None, repr=False)
    request_timeout_seconds: float = Field(default=10, gt=0, le=60)
    user_agent: str = "btc-delta-option-seller/0.1.0"
    reconnect_initial_seconds: float = Field(default=1, gt=0)
    reconnect_max_seconds: float = Field(default=30, gt=0, le=300)

    @property
    def rest_url(self) -> str:
        return (
            "https://api.india.delta.exchange"
            if self.environment is Environment.PRODUCTION
            else "https://cdn-ind.testnet.deltaex.org"
        )

    @property
    def public_ws_url(self) -> str:
        return (
            "wss://public-socket.india.delta.exchange"
            if self.environment is Environment.PRODUCTION
            else "wss://socket-ind-pub.testnet.deltaex.org"
        )

    @property
    def private_ws_url(self) -> str:
        return (
            "wss://socket.india.delta.exchange"
            if self.environment is Environment.PRODUCTION
            else "wss://socket-ind.testnet.deltaex.org"
        )


class MarketDataSettings(BaseModel):
    max_quote_age_seconds: float = Field(default=5, gt=0)


class HistoricalSettings(BaseModel):
    database_url: str = "sqlite:///runtime/bos.db"
    parquet_root: Path = Path("runtime/parquet")
    candle_page_limit: int = Field(default=2000, ge=1, le=2000)
    product_page_size: int = Field(default=100, ge=1, le=1000)


class VolatilitySettings(BaseModel):
    rv_window: int = Field(default=20, ge=2)
    annualization_days: int = Field(default=365, ge=1)
    iv_percentile_days: int = Field(default=180, ge=1)
    vrp_minimum: float = Field(default=1.15, gt=0)
    iv_shock_points: float = Field(default=15.0, gt=0)
    term_ratio_stress: float = Field(default=1.25, gt=0)


class RegimeSettings(BaseModel):
    directional_adx_min: float = Field(default=18, ge=0)
    directional_adx_max: float = Field(default=35, gt=0)
    neutral_adx_max: float = Field(default=22, gt=0)
    neutral_ema_atr_ratio: float = Field(default=0.60, gt=0)
    flat_slope_threshold: float = Field(default=0.0005, ge=0)
    extreme_adx: float = Field(default=35, gt=0)
    extreme_move_atr_multiple: float = Field(default=2.5, gt=0)


class StrikeSelectionSettings(BaseModel):
    target_delta: float = Field(default=0.20, gt=0, lt=1)
    minimum_delta: float = Field(default=0.17, gt=0, lt=1)
    maximum_delta: float = Field(default=0.23, gt=0, lt=1)
    expected_move_distance: float = Field(default=0.90, gt=0)
    swing_atr_buffer: float = Field(default=0.25, ge=0)
    wing_expected_move_multiplier: float = Field(default=0.35, gt=0)
    minimum_wing_width: float = Field(default=3000, gt=0)
    maximum_wing_width: float = Field(default=5000, gt=0)


class LiquiditySettings(BaseModel):
    short_max_width_pct: float = Field(default=0.08, gt=0)
    wing_max_width_pct: float = Field(default=0.15, gt=0)
    top_book_multiple: float = Field(default=2.0, ge=1)
    max_book_participation: float = Field(default=0.20, gt=0, le=1)


class RiskSettings(BaseModel):
    risk_per_trade: float = Field(default=0.005, gt=0, le=0.01)
    hard_trade_risk_cap: float = Field(default=0.01, gt=0, le=0.01)
    total_open_defined_risk: float = Field(default=0.02, gt=0)
    daily_realized_loss_limit: float = Field(default=0.015, gt=0)
    weekly_realized_loss_limit: float = Field(default=0.03, gt=0)
    drawdown_kill_switch: float = Field(default=0.08, gt=0)
    consecutive_full_stop_limit: int = Field(default=3, ge=1)
    maximum_structures: int = Field(default=1, ge=1)


class BacktestSettings(BaseModel):
    initial_equity: float = Field(default=1_000_000, gt=0)
    slippage_bps: float = Field(default=5, ge=0)
    option_fee_rate: float = Field(default=0.0003, ge=0)
    gst_rate: float = Field(default=0.18, ge=0)
    settlement_fee_rate: float = Field(default=0, ge=0)
    partial_fill_ratio: float = Field(default=1.0, gt=0, le=1)
    profit_capture: float = Field(default=0.55, gt=0, lt=1)
    premium_stop_multiple: float = Field(default=2.0, gt=1)
    delta_mandatory_exit: float = Field(default=0.35, gt=0, lt=1)
    delta_emergency_exit: float = Field(default=0.40, gt=0, lt=1)
    time_exit_hours: float = Field(default=30, ge=24, le=36)


class ResearchSettings(BaseModel):
    train_size: int = Field(default=365, ge=1)
    validation_size: int = Field(default=90, ge=1)
    test_size: int = Field(default=90, ge=1)
    step_size: int = Field(default=90, ge=1)
    monte_carlo_simulations: int = Field(default=10_000, ge=100)
    monte_carlo_seed: int = 7
    drawdown_threshold: float = Field(default=0.12, gt=0, lt=1)


class LiveSettings(BaseModel):
    live_trading: bool = False


class LoggingSettings(BaseModel):
    model_config = {"populate_by_name": True}
    level: str = "INFO"
    json_output: bool = Field(default=True, alias="json")


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="BOS_", env_nested_delimiter="__", case_sensitive=False, extra="forbid"
    )
    mode: Mode = Mode.PAPER
    exchange: ExchangeSettings = Field(default_factory=ExchangeSettings)
    market_data: MarketDataSettings = Field(default_factory=MarketDataSettings)
    historical: HistoricalSettings = Field(default_factory=HistoricalSettings)
    volatility: VolatilitySettings = Field(default_factory=VolatilitySettings)
    regime: RegimeSettings = Field(default_factory=RegimeSettings)
    strike_selection: StrikeSelectionSettings = Field(default_factory=StrikeSelectionSettings)
    liquidity: LiquiditySettings = Field(default_factory=LiquiditySettings)
    risk: RiskSettings = Field(default_factory=RiskSettings)
    backtest: BacktestSettings = Field(default_factory=BacktestSettings)
    research: ResearchSettings = Field(default_factory=ResearchSettings)
    live: LiveSettings = Field(default_factory=LiveSettings)
    logging: LoggingSettings = Field(default_factory=LoggingSettings)
    armed: bool = False

    @model_validator(mode="after")
    def enforce_live_safety(self) -> Settings:
        # Arming is deliberately in-memory only and is reset at every startup.
        self.armed = False
        if self.mode is Mode.LIVE and not self.live.live_trading:
            raise ValueError("LIVE mode requires BOS_LIVE__LIVE_TRADING=true")
        return self

    @classmethod
    def from_yaml(cls, path: Path) -> Settings:
        raw: dict[str, Any] = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        # BaseSettings lets environment variables override constructor values only when absent;
        # YAML is the explicit baseline for this factory.
        return cls(**raw)


def load_settings(path: Path | None = None) -> Settings:
    settings = Settings.from_yaml(path) if path else Settings()
    updates: dict[str, SecretStr] = {}
    if value := os.getenv("DELTA_API_KEY"):
        updates["api_key"] = SecretStr(value)
    if value := os.getenv("DELTA_API_SECRET"):
        updates["api_secret"] = SecretStr(value)
    if updates:
        settings.exchange = settings.exchange.model_copy(update=updates)
    return settings
