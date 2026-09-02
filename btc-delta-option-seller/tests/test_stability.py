from bos.research.stability import ParameterScore, assess_parameter_stability


def test_isolated_profitable_parameter_point_is_flagged() -> None:
    results = [
        ParameterScore({"delta": 0.17}, -1),
        ParameterScore({"delta": 0.20}, 5),
        ParameterScore({"delta": 0.23}, -2),
    ]
    assessments = assess_parameter_stability(results, {"delta": [0.17, 0.20, 0.23]})
    center = assessments[1]
    assert center.neighbor_count == 2
    assert center.isolated_profitable_point
    assert not center.stable


def test_profitable_neighborhood_is_stable() -> None:
    results = [
        ParameterScore({"delta": delta, "vrp": vrp}, score)
        for delta, vrp, score in [
            (0.17, 1.15, 1),
            (0.20, 1.15, 2),
            (0.23, 1.15, 1),
            (0.17, 1.20, 1),
            (0.20, 1.20, 3),
            (0.23, 1.20, 1),
        ]
    ]
    assessments = assess_parameter_stability(
        results, {"delta": [0.17, 0.20, 0.23], "vrp": [1.15, 1.20]}
    )
    selected = next(
        item for item in assessments if item.result.parameters == {"delta": 0.20, "vrp": 1.20}
    )
    assert selected.stable
    assert selected.profitable_neighbor_fraction == 1
