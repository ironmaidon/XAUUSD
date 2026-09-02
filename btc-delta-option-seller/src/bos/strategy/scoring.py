from __future__ import annotations

from dataclasses import dataclass

WEIGHTS = {
    "vrp": 25.0,
    "iv_percentile": 15.0,
    "regime_quality": 15.0,
    "liquidity": 15.0,
    "credit_efficiency": 15.0,
    "volatility_stability": 10.0,
    "skew_alignment": 5.0,
}


@dataclass(frozen=True)
class EntryScore:
    total: float
    components: dict[str, float]
    eligible: bool


def entry_score(components: dict[str, float], hard_gates_passed: bool) -> EntryScore:
    if set(components) != set(WEIGHTS):
        raise ValueError("all and only configured score components are required")
    bounded = {name: min(max(value, 0.0), 1.0) for name, value in components.items()}
    points = {name: bounded[name] * weight for name, weight in WEIGHTS.items()}
    total = sum(points.values())
    return EntryScore(total=total, components=points, eligible=hard_gates_passed and total >= 70)
