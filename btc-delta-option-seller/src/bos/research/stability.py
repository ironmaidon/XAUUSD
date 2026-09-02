from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass


@dataclass(frozen=True)
class ParameterScore:
    parameters: dict[str, float]
    score: float


@dataclass(frozen=True)
class StabilityAssessment:
    result: ParameterScore
    neighbor_count: int
    profitable_neighbor_fraction: float
    isolated_profitable_point: bool
    stable: bool


def assess_parameter_stability(
    results: Sequence[ParameterScore], grid: Mapping[str, Sequence[float]]
) -> tuple[StabilityAssessment, ...]:
    if not results:
        raise ValueError("parameter results are required")
    normalized_grid = {name: tuple(sorted(set(values))) for name, values in grid.items()}
    if any(not values for values in normalized_grid.values()):
        raise ValueError("grid dimensions cannot be empty")
    by_point = {tuple(sorted(item.parameters.items())): item for item in results}
    assessments: list[StabilityAssessment] = []
    for result in results:
        neighbors: list[ParameterScore] = []
        for name, values in normalized_grid.items():
            current = result.parameters[name]
            try:
                index = values.index(current)
            except ValueError as error:
                raise ValueError(f"parameter {name}={current} is not in its grid") from error
            for adjacent in (index - 1, index + 1):
                if 0 <= adjacent < len(values):
                    candidate = dict(result.parameters)
                    candidate[name] = values[adjacent]
                    neighbor = by_point.get(tuple(sorted(candidate.items())))
                    if neighbor is not None:
                        neighbors.append(neighbor)
        fraction = (
            sum(neighbor.score > 0 for neighbor in neighbors) / len(neighbors) if neighbors else 0.0
        )
        isolated = result.score > 0 and bool(neighbors) and fraction == 0
        assessments.append(
            StabilityAssessment(
                result=result,
                neighbor_count=len(neighbors),
                profitable_neighbor_fraction=fraction,
                isolated_profitable_point=isolated,
                stable=result.score > 0 and len(neighbors) >= 2 and fraction >= 0.5,
            )
        )
    return tuple(assessments)
