from __future__ import annotations

import asyncio
import json
from datetime import UTC, datetime
from pathlib import Path

from bos.config import Mode, Settings
from bos.dashboard.models import DashboardSnapshot, SystemStatusView


class DashboardState:
    """Atomic read model; services publish complete normalized snapshots."""

    def __init__(self, settings: Settings) -> None:
        self._lock = asyncio.Lock()
        self._version = 0
        self._changed = asyncio.Condition()
        report_path = Path(__file__).resolve().parents[3] / "reports" / "backtest-one-year.json"
        backtests = []
        if report_path.is_file():
            backtests = [json.loads(report_path.read_text(encoding="utf-8"))]
        self._snapshot = DashboardSnapshot(
            status=SystemStatusView(
                mode=settings.mode.value,
                armed=False,
                updated_at=datetime.now(UTC),
            ),
            backtests=backtests,
        )

    async def get(self) -> tuple[int, DashboardSnapshot]:
        async with self._lock:
            return self._version, self._snapshot.model_copy(deep=True)

    async def publish(self, snapshot: DashboardSnapshot) -> int:
        snapshot.status.armed = (
            False if snapshot.status.mode != Mode.LIVE.value else snapshot.status.armed
        )
        snapshot.status.updated_at = datetime.now(UTC)
        async with self._lock:
            self._snapshot = snapshot.model_copy(deep=True)
            self._version += 1
            version = self._version
        async with self._changed:
            self._changed.notify_all()
        return version

    async def wait_after(
        self, version: int, wait_seconds: float = 30
    ) -> tuple[int, DashboardSnapshot]:
        current, snapshot = await self.get()
        if current > version:
            return current, snapshot
        async with self._changed:
            try:
                await asyncio.wait_for(self._changed.wait(), wait_seconds)
            except TimeoutError:
                pass
        return await self.get()
