import pytest

from bos.config import RiskSettings
from bos.risk import PortfolioRisk, evaluate_portfolio, maximum_loss_per_contract, position_size


def healthy(**changes: float | int | bool) -> PortfolioRisk:
    values: dict[str, float | int | bool] = {
        "equity": 1_000_000,
        "open_defined_risk": 0,
        "daily_realized_pnl": 0,
        "weekly_realized_pnl": 0,
        "drawdown": 0,
        "consecutive_full_stops": 0,
        "open_structures": 0,
        "kill_switch_latched": False,
    }
    values.update(changes)
    return PortfolioRisk(**values)  # type: ignore[arg-type]


def test_defined_loss_and_equity_based_position_size() -> None:
    loss = maximum_loss_per_contract(4000, 0.001, 83)
    assert loss == pytest.approx(332)
    quantity = position_size(1_000_000, loss, 1, 1, 100, RiskSettings())
    assert quantity == 15


def test_quantity_below_exchange_minimum_is_no_trade() -> None:
    assert position_size(10_000, 1000, 1, 1, 100, RiskSettings()) == 0


@pytest.mark.parametrize(
    ("state", "reason"),
    [
        (healthy(open_defined_risk=20_000), "OPEN_RISK_LIMIT"),
        (healthy(daily_realized_pnl=-15_000), "DAILY_LOSS_LIMIT"),
        (healthy(weekly_realized_pnl=-30_000), "WEEKLY_LOSS_LIMIT"),
        (healthy(open_structures=1), "MAX_STRUCTURES"),
    ],
)
def test_portfolio_limits_block_entries(state: PortfolioRisk, reason: str) -> None:
    decision = evaluate_portfolio(state, RiskSettings())
    assert not decision.allowed
    assert reason in decision.reasons


def test_kill_switch_latches_for_drawdown_and_cannot_auto_reset() -> None:
    triggered = evaluate_portfolio(healthy(drawdown=0.08), RiskSettings())
    assert triggered.kill_switch
    latched = evaluate_portfolio(healthy(kill_switch_latched=True), RiskSettings())
    assert not latched.allowed
    assert latched.kill_switch
