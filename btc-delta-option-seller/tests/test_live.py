from datetime import UTC, datetime
from unittest.mock import AsyncMock

import pytest
from pydantic import SecretStr

from bos.config import ExchangeSettings, LiveSettings, Mode, Settings
from bos.execution.live import (
    MANUAL_CONFIRMATION,
    LiveExecutionProvider,
    LiveSafetyState,
    LiveTradingGuard,
)
from bos.execution.models import OrderRequest, OrderState
from bos.strategy.structures import Side

NOW = datetime(2026, 9, 3, tzinfo=UTC)


def live_settings() -> Settings:
    return Settings(
        mode=Mode.LIVE,
        live=LiveSettings(live_trading=True),
        exchange=ExchangeSettings(
            api_key=SecretStr("test-key"), api_secret=SecretStr("test-secret")
        ),
    )


def safe_guard() -> LiveTradingGuard:
    guard = LiveTradingGuard(live_settings())
    guard.update_safety(LiveSafetyState(True, True, False))
    return guard


def order() -> OrderRequest:
    return OrderRequest("BOS1-E-2609031200-DS-L1-1", 1, "WING", Side.BUY, 1, 100)


def test_startup_is_always_disarmed_even_with_all_static_gates() -> None:
    guard = safe_guard()
    assert not guard.armed
    with pytest.raises(PermissionError, match="disarmed"):
        guard.assert_order_allowed()


@pytest.mark.parametrize(
    "safety",
    [
        LiveSafetyState(False, True, False),
        LiveSafetyState(True, False, False),
        LiveSafetyState(True, True, True),
    ],
)
def test_dynamic_safety_gates_block_arming(safety: LiveSafetyState) -> None:
    guard = LiveTradingGuard(live_settings())
    guard.update_safety(safety)
    with pytest.raises(PermissionError, match="gates failed"):
        guard.arm(MANUAL_CONFIRMATION)


def test_exact_manual_confirmation_is_required() -> None:
    guard = safe_guard()
    with pytest.raises(PermissionError, match="exact manual"):
        guard.arm("yes")
    guard.arm(MANUAL_CONFIRMATION)
    assert guard.armed


def test_health_failure_immediately_disarms() -> None:
    guard = safe_guard()
    guard.arm(MANUAL_CONFIRMATION)
    guard.update_safety(LiveSafetyState(True, False, False))
    assert not guard.armed


@pytest.mark.asyncio
async def test_live_submit_calls_gateway_only_after_every_gate() -> None:
    gateway = AsyncMock()
    gateway.place_limit.return_value = {"id": 123, "state": "open", "unfilled_size": 1}
    guard = safe_guard()
    provider = LiveExecutionProvider(gateway, guard)
    with pytest.raises(PermissionError):
        await provider.submit(order(), NOW)
    gateway.place_limit.assert_not_awaited()
    guard.arm(MANUAL_CONFIRMATION)
    submitted = await provider.submit(order(), NOW)
    gateway.place_limit.assert_awaited_once_with(order())
    assert submitted.order_id == "123"
    assert submitted.state is OrderState.OPEN


@pytest.mark.asyncio
async def test_live_adapter_has_no_market_order_path() -> None:
    gateway = AsyncMock()
    gateway.place_limit.return_value = {"id": 1, "state": "open"}
    guard = safe_guard()
    guard.arm(MANUAL_CONFIRMATION)
    provider = LiveExecutionProvider(gateway, guard)
    with pytest.raises(ValueError):
        await provider.submit(OrderRequest("BOS1-X", 1, "X", Side.BUY, 1, 0), NOW)
