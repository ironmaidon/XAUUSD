from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock

import pytest

from bos.config import HeartbeatSettings
from bos.heartbeat import HeartbeatMonitor, HeartbeatSupervisor


def test_heartbeat_must_be_enabled_and_recent() -> None:
    now = datetime(2026, 9, 3, tzinfo=UTC)
    monitor = HeartbeatMonitor(HeartbeatSettings(unhealthy_after_seconds=35))
    assert not monitor.healthy(now)
    monitor.acknowledged(now)
    assert monitor.healthy(now + timedelta(seconds=35))
    assert not monitor.healthy(now + timedelta(seconds=36))


def test_one_failed_ack_marks_unhealthy_until_success() -> None:
    now = datetime(2026, 9, 3, tzinfo=UTC)
    monitor = HeartbeatMonitor(HeartbeatSettings())
    monitor.acknowledged(now)
    monitor.failed()
    assert not monitor.healthy(now)
    monitor.acknowledged(now)
    assert monitor.healthy(now)


@pytest.mark.asyncio
async def test_supervisor_acknowledges_and_fails_closed() -> None:
    now = datetime(2026, 9, 3, tzinfo=UTC)
    service = AsyncMock()
    monitor = HeartbeatMonitor(HeartbeatSettings())
    supervisor = HeartbeatSupervisor(service, monitor)
    assert await supervisor.tick(now)
    service.acknowledge.assert_awaited_once_with("bos1-india", 30_000)
    service.acknowledge.side_effect = TimeoutError
    assert not await supervisor.tick(now)
    assert not monitor.healthy(now)
