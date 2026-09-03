from __future__ import annotations

import asyncio
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from typing import Protocol

from bos.config import HeartbeatSettings


@dataclass
class HeartbeatMonitor:
    settings: HeartbeatSettings
    last_acknowledged_at: datetime | None = None
    failures: int = 0
    enabled: bool = False

    def acknowledged(self, timestamp: datetime) -> None:
        self.last_acknowledged_at = timestamp
        self.failures = 0
        self.enabled = True

    def failed(self) -> None:
        self.failures += 1

    def disable(self) -> None:
        self.enabled = False

    def healthy(self, now: datetime) -> bool:
        if not self.enabled or self.failures > 0 or self.last_acknowledged_at is None:
            return False
        age = (now - self.last_acknowledged_at).total_seconds()
        return 0 <= age <= self.settings.unhealthy_after_seconds


class HeartbeatAcknowledger(Protocol):
    async def acknowledge(self, heartbeat_id: str, ttl_ms: int) -> object: ...


class HeartbeatSupervisor:
    def __init__(
        self,
        service: HeartbeatAcknowledger,
        monitor: HeartbeatMonitor,
    ) -> None:
        self.service = service
        self.monitor = monitor

    async def tick(self, now: datetime) -> bool:
        try:
            await self.service.acknowledge(
                self.monitor.settings.heartbeat_id,
                self.monitor.settings.ttl_ms,
            )
        except Exception:
            self.monitor.failed()
            return False
        self.monitor.acknowledged(now)
        return True

    async def run(self, clock: Callable[[], datetime], stop: asyncio.Event) -> None:
        while not stop.is_set():
            await self.tick(clock())
            try:
                await asyncio.wait_for(
                    stop.wait(), self.monitor.settings.acknowledgment_interval_seconds
                )
            except TimeoutError:
                pass
