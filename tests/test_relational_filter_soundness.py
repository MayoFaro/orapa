import pytest

from orapa_assistant.relational_filter import apply_relational_filters
from orapa_assistant.search import search_configurations
from tests.bruteforce_oracle import configuration_key, observe, solve
from tests.test_generic_solver_contract import _generated_reduced_problem


@pytest.mark.parametrize("seed", range(8))
def test_relational_propagation_never_removes_a_true_configuration(seed: int) -> None:
    domains, truth, actions = _generated_reduced_problem(seed + 300)
    observations = []
    truth_by_name = {gem.name: gem for gem in truth.gems}

    for action in actions:
        observations.append(observe(truth, *action))
        propagated = apply_relational_filters(domains, tuple(observations)).domains
        for domain in propagated:
            assert truth_by_name[domain.piece_name] in domain.placements

        expected = solve(domains, observations)
        actual = search_configurations(
            propagated, tuple(observations), max_raw_combinations=1_000
        ).configurations
        assert {configuration_key(item) for item in actual} == {
            configuration_key(item) for item in expected
        }
