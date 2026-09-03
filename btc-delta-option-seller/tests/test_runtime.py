from datetime import UTC, datetime
from decimal import Decimal

import pytest

from bos.config import ExchangeSettings, Settings
from bos.dashboard.state import DashboardState
from bos.exchange.models import Candle
from bos.runtime import PaperTradingRuntime


@pytest.mark.asyncio
async def test_paper_runtime_publishes_complete_no_trade_evaluation() -> None:
    settings = Settings()
    state = DashboardState(settings)
    runtime = PaperTradingRuntime(settings, ExchangeSettings(), state)
    candles = [
        Candle(
            time=1_700_000_000 + index * 14_400,
            open=Decimal(80_000 + index),
            high=Decimal(80_100 + index),
            low=Decimal(79_900 + index),
            close=Decimal(80_000 + index),
        )
        for index in range(60)
    ]

    snapshot = await runtime._evaluate(
        80_059,
        candles,
        [],
        None,
        None,
        14,
        1_000_000,
        900_000,
        datetime.now(UTC),
    )

    assert len(snapshot.candles) == 60
    assert snapshot.status.paper_trading_active is True
    assert snapshot.status.heartbeat_healthy is True
    assert snapshot.risk.account_equity_inr == 1_000_000
    assert snapshot.candidate.eligible is False
    assert "IV_OR_REGIME_GATE" in snapshot.candidate.reasons
    assert snapshot.logs[0]["event"] == "PAPER_EVALUATION"
