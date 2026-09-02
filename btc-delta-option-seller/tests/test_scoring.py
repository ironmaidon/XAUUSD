import pytest

from bos.strategy.scoring import WEIGHTS, entry_score


def test_entry_score_components_and_threshold() -> None:
    score = entry_score({name: 0.8 for name in WEIGHTS}, True)
    assert score.total == pytest.approx(80)
    assert score.eligible


def test_hard_gate_cannot_be_overridden_by_perfect_score() -> None:
    score = entry_score({name: 1.0 for name in WEIGHTS}, False)
    assert score.total == 100
    assert not score.eligible


def test_score_requires_explainable_components() -> None:
    with pytest.raises(ValueError):
        entry_score({"vrp": 1.0}, True)
