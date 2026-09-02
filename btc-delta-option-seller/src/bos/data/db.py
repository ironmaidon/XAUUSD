from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from pathlib import Path

from sqlalchemy import (
    JSON,
    DateTime,
    Index,
    Integer,
    Numeric,
    String,
    UniqueConstraint,
    create_engine,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column, sessionmaker


class Base(DeclarativeBase):
    pass


class CandleRow(Base):
    __tablename__ = "candles"
    __table_args__ = (UniqueConstraint("symbol", "resolution", "timestamp", name="uq_candle"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    symbol: Mapped[str] = mapped_column(String(96), index=True)
    product_id: Mapped[int | None] = mapped_column(index=True)
    resolution: Mapped[str] = mapped_column(String(8))
    timestamp: Mapped[int] = mapped_column(index=True)
    open: Mapped[Decimal] = mapped_column(Numeric(30, 12))
    high: Mapped[Decimal] = mapped_column(Numeric(30, 12))
    low: Mapped[Decimal] = mapped_column(Numeric(30, 12))
    close: Mapped[Decimal] = mapped_column(Numeric(30, 12))
    volume: Mapped[Decimal | None] = mapped_column(Numeric(30, 12))
    quality: Mapped[str] = mapped_column(String(16), default="EXACT")
    source: Mapped[str] = mapped_column(String(64))
    downloaded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class ProductRow(Base):
    __tablename__ = "products"
    product_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    symbol: Mapped[str] = mapped_column(String(96), unique=True, index=True)
    contract_type: Mapped[str] = mapped_column(String(32), index=True)
    state: Mapped[str | None] = mapped_column(String(24), index=True)
    strike_price: Mapped[Decimal | None] = mapped_column(Numeric(30, 12))
    settlement_time: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)
    underlying_symbol: Mapped[str | None] = mapped_column(String(16), index=True)
    raw: Mapped[dict[str, object]] = mapped_column(JSON)
    downloaded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class DownloadManifestRow(Base):
    __tablename__ = "download_manifests"
    id: Mapped[int] = mapped_column(primary_key=True)
    source: Mapped[str] = mapped_column(String(64))
    symbol: Mapped[str] = mapped_column(String(96), index=True)
    product_id: Mapped[int | None]
    data_kind: Mapped[str] = mapped_column(String(32))
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    quality: Mapped[str] = mapped_column(String(16))
    row_count: Mapped[int] = mapped_column(default=0)
    missing_fields: Mapped[list[str]] = mapped_column(JSON, default=list)
    parquet_path: Mapped[str | None] = mapped_column(String(512))
    metadata_json: Mapped[dict[str, object]] = mapped_column(JSON, default=dict)


class AuditRecord(Base):
    """Append-only payloads for entities whose full domain schemas arrive in later milestones."""

    __tablename__ = "audit_records"
    __table_args__ = (Index("ix_audit_kind_time", "kind", "timestamp"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    kind: Mapped[str] = mapped_column(String(40))
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    correlation_id: Mapped[str | None] = mapped_column(String(96), index=True)
    payload: Mapped[dict[str, object]] = mapped_column(JSON)


AUDIT_KINDS = frozenset(
    {
        "market_snapshot",
        "option_chain",
        "iv_history",
        "strategy_evaluation",
        "trade_candidate",
        "structure",
        "leg",
        "order",
        "fill",
        "position",
        "risk_snapshot",
        "account_snapshot",
        "strategy_state_change",
        "event",
        "error",
        "system_health",
        "backtest_run",
        "backtest_trade",
    }
)


def create_session_factory(database_url: str) -> sessionmaker[Session]:
    if database_url.startswith("sqlite:///"):
        db_path = Path(database_url.removeprefix("sqlite:///"))
        db_path.parent.mkdir(parents=True, exist_ok=True)
    engine = create_engine(database_url)
    Base.metadata.create_all(engine)
    return sessionmaker(engine, expire_on_commit=False)
