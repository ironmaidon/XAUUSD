import pytest

from bos.research.monte_carlo import monte_carlo


def test_monte_carlo_is_seeded_and_reports_required_tail_metrics() -> None:
    pnls = [100, 120, -80, 90, -50, 110, -70, 130]
    first = monte_carlo(
        pnls,
        10_000,
        simulations=500,
        seed=42,
        drawdown_threshold=0.02,
        trades_per_path=20,
    )
    second = monte_carlo(
        pnls,
        10_000,
        simulations=500,
        seed=42,
        drawdown_threshold=0.02,
        trades_per_path=20,
    )
    assert first == second
    assert len(first.median_equity_path) == 21
    assert first.fifth_percentile_ending_equity <= first.median_ending_equity
    assert 0 <= first.probability_exceeding_drawdown <= 1
    assert first.ninety_fifth_percentile_drawdown >= 0
    assert first.consecutive_loss_p95 >= first.consecutive_loss_p50


def test_all_winning_distribution_has_no_drawdown_or_losing_streak() -> None:
    result = monte_carlo([10, 20], 1000, simulations=100, seed=1)
    assert result.ninety_fifth_percentile_drawdown == 0
    assert result.maximum_consecutive_losses == 0
    assert result.fifth_percentile_ending_equity >= 1020


@pytest.mark.parametrize(
    "pnls",
    [[], [1, float("nan")]],
)
def test_invalid_trade_distribution_fails(pnls: list[float]) -> None:
    with pytest.raises(ValueError):
        monte_carlo(pnls, 1000, simulations=100)
