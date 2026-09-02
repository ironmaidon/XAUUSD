from __future__ import annotations

from dataclasses import asdict

from sqlalchemy.orm import Session, sessionmaker

from bos.data.db import AuditRecord
from bos.execution.models import Fill, Order


class SqlExecutionJournal:
    """Append-only order/fill journal shared by paper and future live providers."""

    def __init__(self, sessions: sessionmaker[Session]) -> None:
        self.sessions = sessions

    def record_order(self, order: Order) -> None:
        self._record("order", order.updated_at, order.request.client_order_id, asdict(order))

    def record_fill(self, fill: Fill) -> None:
        self._record("fill", fill.timestamp, fill.client_order_id, asdict(fill))

    def _record(self, kind: str, timestamp: object, correlation_id: str, payload: object) -> None:
        with self.sessions.begin() as session:
            session.add(
                AuditRecord(
                    kind=kind,
                    timestamp=timestamp,
                    correlation_id=correlation_id,
                    payload=_json_safe(payload),
                )
            )


def _json_safe(value: object) -> object:
    if isinstance(value, dict):
        return {str(key): _json_safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_safe(item) for item in value]
    if hasattr(value, "isoformat"):
        return value.isoformat()
    if hasattr(value, "value"):
        return value.value
    return value
