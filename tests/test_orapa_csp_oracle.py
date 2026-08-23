import pytest
from random import Random

from orapa_assistant.border import ALL_BORDER_POINTS
from orapa_assistant.constraints import gems_are_compatible
from orapa_assistant.domain_filter import PlacementDomain
from orapa_assistant.orapa_csp import solve_orapa_csp
from orapa_assistant.pieces import BLACK_BODY, DIAMOND, PIECES, placements
from orapa_assistant.raytracer import Configuration
from tests.bruteforce_oracle import configuration_key, observe, solve
from tests.test_generic_solver_contract import _generated_reduced_problem


@pytest.mark.parametrize("seed", range(8))
def test_global_ray_constraints_equal_independent_oracle(seed: int) -> None:
    domains, truth, actions = _generated_reduced_problem(seed + 500)
    observations = tuple(observe(truth, *action) for action in actions)

    expected = solve(domains, observations)
    actual = solve_orapa_csp(
        domains,
        observations,
        model_limit=1_000,
        witness_node_limit=100_000,
    )

    assert actual.exhausted
    assert not actual.unknown_supports
    assert {configuration_key(item) for item in actual.configurations} == {
        configuration_key(item) for item in expected
    }


def _generated_real_piece_problem(seed: int):
    random = Random(seed)
    definitions = PIECES + (DIAMOND, BLACK_BODY)
    truth = []
    domains = []
    for definition in definitions:
        catalogue = list(placements(definition))
        random.shuffle(catalogue)
        true_gem = next(
            gem
            for gem in catalogue
            if all(gems_are_compatible(gem, previous) for previous in truth)
        )
        truth.append(true_gem)
        decoys = random.sample(
            [gem for gem in catalogue if gem != true_gem], 2
        )
        values = [true_gem, *decoys]
        random.shuffle(values)
        domains.append(PlacementDomain(definition.name, tuple(values)))
    configuration = Configuration(tuple(truth))
    actions = [
        *(('wave', entry) for entry in random.sample(list(ALL_BORDER_POINTS), 6)),
        *(('cell', f"{row}{column}") for row, column in (
            ("A", 1), ("C", 4), ("F", 7), ("H", 10)
        )),
    ]
    return tuple(domains), configuration, tuple(actions)


@pytest.mark.parametrize("seed", range(4))
def test_global_constraints_match_oracle_with_all_real_piece_shapes(seed: int) -> None:
    domains, truth, actions = _generated_real_piece_problem(seed + 800)
    observations = tuple(observe(truth, *action) for action in actions)
    expected = solve(domains, observations)
    actual = solve_orapa_csp(
        domains,
        observations,
        model_limit=5_000,
        witness_node_limit=100_000,
        seed=seed,
    )
    assert actual.exhausted
    assert not actual.unknown_supports
    assert {configuration_key(item) for item in actual.configurations} == {
        configuration_key(item) for item in expected
    }
