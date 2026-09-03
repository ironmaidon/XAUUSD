from unittest.mock import AsyncMock

import pytest

from bos.reconciliation import reconcile


def gateway() -> AsyncMock:
    value = AsyncMock()
    value.wallet.return_value = [{"asset_symbol": "INR"}]
    value.positions.return_value = []
    value.open_orders.return_value = []
    value.recent_fills.return_value = []
    return value


@pytest.mark.asyncio
async def test_matching_exchange_state_allows_entries() -> None:
    value = gateway()
    value.positions.return_value = [{"product_id": 1, "size": 2}]
    result = await reconcile(value, {1})
    assert result.successful
    assert result.new_entries_allowed


@pytest.mark.asyncio
async def test_unexpected_exchange_exposure_is_critical_and_reconstructed() -> None:
    value = gateway()
    value.positions.return_value = [{"product_id": 2, "size": "1"}]
    result = await reconcile(value, set())
    assert result.critical
    assert not result.new_entries_allowed
    assert result.reconstructed
    assert "UNEXPECTED_EXCHANGE_POSITION" in result.reasons


@pytest.mark.asyncio
async def test_local_position_missing_at_exchange_blocks_entries() -> None:
    result = await reconcile(gateway(), {1})
    assert "LOCAL_POSITION_MISSING_ON_EXCHANGE" in result.reasons
    assert not result.new_entries_allowed


@pytest.mark.asyncio
async def test_rest_timeout_fails_closed() -> None:
    value = gateway()
    value.wallet.side_effect = TimeoutError
    result = await reconcile(value, set())
    assert result.critical
    assert result.reasons == ("RECONCILIATION_ERROR:TimeoutError",)
