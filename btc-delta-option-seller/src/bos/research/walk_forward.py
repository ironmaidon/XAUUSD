from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from typing import Generic, TypeVar

T = TypeVar("T")
Parameters = Mapping[str, float]
Objective = Callable[[Sequence[T], Parameters], float]


@dataclass(frozen=True)
class WalkForwardFold(Generic[T]):
    number: int
    train: tuple[T, ...]
    validation: tuple[T, ...]
    out_of_sample: tuple[T, ...]


@dataclass(frozen=True)
class FoldResult:
    fold: int
    parameters: dict[str, float]
    in_sample_score: float
    validation_score: float
    out_of_sample_score: float


@dataclass(frozen=True)
class WalkForwardResult:
    folds: tuple[FoldResult, ...]
    mean_validation_score: float
    mean_out_of_sample_score: float
    positive_out_of_sample_fraction: float


def make_folds(
    observations: Sequence[T],
    train_size: int,
    validation_size: int,
    test_size: int,
    step_size: int,
) -> tuple[WalkForwardFold[T], ...]:
    if min(train_size, validation_size, test_size, step_size) <= 0:
        raise ValueError("walk-forward sizes must be positive")
    folds: list[WalkForwardFold[T]] = []
    start = 0
    required = train_size + validation_size + test_size
    while start + required <= len(observations):
        train_end = start + train_size
        validation_end = train_end + validation_size
        test_end = validation_end + test_size
        folds.append(
            WalkForwardFold(
                number=len(folds) + 1,
                train=tuple(observations[start:train_end]),
                validation=tuple(observations[train_end:validation_end]),
                out_of_sample=tuple(observations[validation_end:test_end]),
            )
        )
        start += step_size
    if not folds:
        raise ValueError("insufficient observations for one complete walk-forward fold")
    return tuple(folds)


def run_walk_forward(
    observations: Sequence[T],
    parameter_candidates: Sequence[Parameters],
    objective: Objective[T],
    *,
    train_size: int,
    validation_size: int,
    test_size: int,
    step_size: int,
) -> WalkForwardResult:
    if not parameter_candidates:
        raise ValueError("at least one parameter candidate is required")
    folds = make_folds(observations, train_size, validation_size, test_size, step_size)
    results: list[FoldResult] = []
    for fold in folds:
        ranked = [
            (objective(fold.train, parameters), index, parameters)
            for index, parameters in enumerate(parameter_candidates)
        ]
        train_score, _, selected = max(ranked, key=lambda item: (item[0], -item[1]))
        results.append(
            FoldResult(
                fold=fold.number,
                parameters=dict(selected),
                in_sample_score=train_score,
                validation_score=objective(fold.validation, selected),
                out_of_sample_score=objective(fold.out_of_sample, selected),
            )
        )
    count = len(results)
    return WalkForwardResult(
        folds=tuple(results),
        mean_validation_score=sum(item.validation_score for item in results) / count,
        mean_out_of_sample_score=sum(item.out_of_sample_score for item in results) / count,
        positive_out_of_sample_fraction=sum(item.out_of_sample_score > 0 for item in results)
        / count,
    )
