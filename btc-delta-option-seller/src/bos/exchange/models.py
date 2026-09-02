from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Any, Generic, TypeVar

from pydantic import BaseModel, ConfigDict, field_validator

T = TypeVar("T")


class ApiEnvelope(BaseModel, Generic[T]):
    model_config = ConfigDict(extra="allow")
    success: bool
    result: T
    meta: dict[str, Any] | None = None


class Product(BaseModel):
    model_config = ConfigDict(extra="allow")
    id: int
    symbol: str
    contract_type: str
    strike_price: Decimal | None = None
    settlement_time: datetime | None = None
    underlying_asset: dict[str, Any] | None = None
    underlying_asset_symbol: str | None = None

    @property
    def underlying_symbol(self) -> str | None:
        if self.underlying_asset_symbol:
            return self.underlying_asset_symbol
        return str(self.underlying_asset.get("symbol")) if self.underlying_asset else None


class Greeks(BaseModel):
    model_config = ConfigDict(extra="allow")
    delta: Decimal | None = None
    gamma: Decimal | None = None
    theta: Decimal | None = None
    vega: Decimal | None = None
    rho: Decimal | None = None


class Ticker(BaseModel):
    model_config = ConfigDict(extra="allow")
    symbol: str
    product_id: int | None = None
    close: Decimal | None = None
    mark_price: Decimal | None = None
    spot_price: Decimal | None = None
    best_bid: Decimal | None = None
    best_ask: Decimal | None = None
    mark_vol: Decimal | None = None
    greeks: Greeks | None = None
    timestamp: int | None = None

    @field_validator("product_id", mode="before")
    @classmethod
    def blank_product_id(cls, value: Any) -> Any:
        return None if value == "" else value


class OptionQuote(BaseModel):
    product: Product
    ticker: Ticker


class DeltaApiError(RuntimeError):
    def __init__(self, status_code: int, code: str, message: str) -> None:
        super().__init__(f"Delta API error {status_code} [{code}]: {message}")
        self.status_code = status_code
        self.code = code
