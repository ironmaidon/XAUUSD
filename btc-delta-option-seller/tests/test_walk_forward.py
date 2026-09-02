import pytest

from bos.research.walk_forward import make_folds, run_walk_forward


def test_folds_are_chronological_and_non_overlapping_within_fold() -> None:
    observations = list(range(20))
    folds = make_folds(observations, train_size=8, validation_size=3, test_size=3, step_size=3)
    assert len(folds) == 3
    first = folds[0]
    assert first.train == tuple(range(8))
    assert first.validation == tuple(range(8, 11))
    assert first.out_of_sample == tuple(range(11, 14))
    for fold in folds:
        assert max(fold.train) < min(fold.validation) < min(fold.out_of_sample)


def test_parameter_selection_uses_training_data_only() -> None:
    observations = [1.0] * 4 + [-1.0] * 2 + [-1.0] * 2
    candidates = [{"direction": 1.0}, {"direction": -1.0}]
    calls: list[tuple[tuple[float, ...], float]] = []

    def objective(data: tuple[float, ...], parameters: dict[str, float]) -> float:
        calls.append((tuple(data), parameters["direction"]))
        return sum(data) * parameters["direction"]

    result = run_walk_forward(
        observations,
        candidates,
        objective,
        train_size=4,
        validation_size=2,
        test_size=2,
        step_size=2,
    )
    assert result.folds[0].parameters == {"direction": 1.0}
    assert result.folds[0].in_sample_score == 4
    assert result.folds[0].validation_score == -2
    assert result.folds[0].out_of_sample_score == -2
    training_calls = calls[:2]
    assert all(call[0] == (1.0, 1.0, 1.0, 1.0) for call in training_calls)


def test_walk_forward_aggregates_multiple_oos_folds() -> None:
    result = run_walk_forward(
        list(range(12)),
        [{"scale": 1.0}],
        lambda data, params: sum(data) * params["scale"],
        train_size=4,
        validation_size=2,
        test_size=2,
        step_size=2,
    )
    assert len(result.folds) == 3
    assert result.positive_out_of_sample_fraction == 1


def test_insufficient_data_and_empty_candidates_fail() -> None:
    with pytest.raises(ValueError, match="insufficient"):
        make_folds([1, 2], 2, 1, 1, 1)
    with pytest.raises(ValueError, match="candidate"):
        run_walk_forward(
            list(range(8)),
            [],
            lambda data, params: 0,
            train_size=4,
            validation_size=2,
            test_size=2,
            step_size=2,
        )
