from __future__ import annotations

import math
import random
from collections.abc import Sequence
from dataclasses import dataclass


@dataclass(frozen=True)
class MonteCarloResult:
    median_equity_path: tuple[float, ...]
    fifth_percentile_ending_equity: float
    median_ending_equity: float
    ninety_fifth_percentile_drawdown: float
    probability_exceeding_drawdown: float
    consecutive_loss_p50: float
    consecutive_loss_p95: float
    maximum_consecutive_losses: int
    simulations: int
    seed: int


def _percentile(values: Sequence[float], percentile: float) -> float:
    ordered = sorted(values)
    if not ordered:
        raise ValueError("percentile requires observations")
    position = (len(ordered) - 1) * percentile
    lower = math.floor(position)
    upper = math.ceil(position)
    if lower == upper:
        return ordered[lower]
    weight = position - lower
    return ordered[lower] * (1 - weight) + ordered[upper] * weight


def _path_stats(initial_equity: float, pnls: Sequence[float]) -> tuple[list[float], float, int]:
    equity = initial_equity
    peak = initial_equity
    maximum_drawdown = 0.0
    current_losses = 0
    maximum_losses = 0
    path = [equity]
    for pnl in pnls:
        equity += pnl
        path.append(equity)
        peak = max(peak, equity)
        drawdown = (peak - equity) / peak if peak > 0 else 1.0
        maximum_drawdown = max(maximum_drawdown, drawdown)
        if pnl < 0:
            current_losses += 1
            maximum_losses = max(maximum_losses, current_losses)
        else:
            current_losses = 0
    return path, maximum_drawdown, maximum_losses


def monte_carlo(
    historical_trade_pnls: Sequence[float],
    initial_equity: float,
    *,
    simulations: int = 10_000,
    seed: int = 7,
    drawdown_threshold: float = 0.12,
    trades_per_path: int | None = None,
) -> MonteCarloResult:
    if not historical_trade_pnls or not all(math.isfinite(pnl) for pnl in historical_trade_pnls):
        raise ValueError("finite historical trade PnLs are required")
    if initial_equity <= 0 or simulations < 1 or not 0 < drawdown_threshold < 1:
        raise ValueError("invalid Monte Carlo configuration")
    path_length = trades_per_path or len(historical_trade_pnls)
    if path_length < 1:
        raise ValueError("trades_per_path must be positive")
    generator = random.Random(seed)
    paths: list[list[float]] = []
    drawdowns: list[float] = []
    losing_streaks: list[int] = []
    for _ in range(simulations):
        sample = [generator.choice(historical_trade_pnls) for _ in range(path_length)]
        path, drawdown, streak = _path_stats(initial_equity, sample)
        paths.append(path)
        drawdowns.append(drawdown)
        losing_streaks.append(streak)
    endings = [path[-1] for path in paths]
    median_path = tuple(
        _percentile([path[index] for path in paths], 0.50) for index in range(path_length + 1)
    )
    return MonteCarloResult(
        median_equity_path=median_path,
        fifth_percentile_ending_equity=_percentile(endings, 0.05),
        median_ending_equity=_percentile(endings, 0.50),
        ninety_fifth_percentile_drawdown=_percentile(drawdowns, 0.95),
        probability_exceeding_drawdown=sum(drawdown >= drawdown_threshold for drawdown in drawdowns)
        / simulations,
        consecutive_loss_p50=_percentile(losing_streaks, 0.50),
        consecutive_loss_p95=_percentile(losing_streaks, 0.95),
        maximum_consecutive_losses=max(losing_streaks),
        simulations=simulations,
        seed=seed,
    )
