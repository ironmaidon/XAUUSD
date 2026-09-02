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
