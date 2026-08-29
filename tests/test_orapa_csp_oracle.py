import time

import pytest
from random import Random

from orapa_assistant.border import ALL_BORDER_POINTS
from orapa_assistant.constraints import gems_are_compatible
from orapa_assistant.domain_filter import PlacementDomain
from orapa_assistant.examples import REAL_GAME_HISTORY
from orapa_assistant.orapa_csp import propagate_orapa_csp, solve_orapa_csp
from orapa_assistant.pieces import BLACK_BODY, DIAMOND, PIECES, placements
from orapa_assistant.raytracer import Configuration
from orapa_assistant.relational_filter import apply_relational_filters
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


def test_witness_cache_lets_a_later_call_succeed_with_a_tiny_search_budget() -> None:
    # Un cache partagé entre deux appels doit permettre au second de
    # retrouver une bonne partie des témoins déjà prouvés par le premier, et
    # donc de réussir avec un budget de recherche qui serait autrement
    # insuffisant pour repartir de zéro.
    domains, truth, actions = _generated_reduced_problem(600)
    observations = tuple(observe(truth, *action) for action in actions)
    cache: dict = {}
    tiny_budget = 1

    first = solve_orapa_csp(
        domains,
        observations,
        model_limit=1_000,
        witness_node_limit=100_000,
        witness_cache=cache,
    )
    assert first.exhausted
    assert cache

    cached = solve_orapa_csp(
        domains,
        observations,
        model_limit=1_000,
        witness_node_limit=tiny_budget,
        witness_cache=cache,
    )
    uncached = solve_orapa_csp(
        domains,
        observations,
        model_limit=1_000,
        witness_node_limit=tiny_budget,
    )

    assert cached.exhausted
    assert not uncached.exhausted
    assert {configuration_key(item) for item in cached.configurations} == {
        configuration_key(item) for item in first.configurations
    }


def test_an_expired_deadline_stops_the_search_instead_of_hanging() -> None:
    # Catalogues bruts, avant tout filtrage : c'est exactement l'état d'une
    # partie qui vient de commencer, avec un seul indice trop faible pour
    # contraindre quoi que ce soit. Sans échéance, la recherche de témoins
    # peut explorer ces domaines énormes pendant plusieurs minutes.
    domains = tuple(
        PlacementDomain(piece.name, placements(piece))
        for piece in PIECES + (DIAMOND, BLACK_BODY)
    )
    observations = REAL_GAME_HISTORY[:1]
    deadline = time.monotonic() - 1.0

    start = time.monotonic()
    result = solve_orapa_csp(
        domains,
        observations,
        model_limit=65,
        witness_node_limit=20_000,
        deadline=deadline,
    )
    elapsed = time.monotonic() - start

    assert elapsed < 5.0
    assert not result.exhausted
    assert result.unknown_supports


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


@pytest.mark.parametrize("seed", range(4))
def test_propagate_prunes_at_least_as_much_as_the_heuristic_filter(
    seed: int,
) -> None:
    # `apply_relational_filters` ne considère, pour un rayon coloré, que les
    # pièces dont la couleur explique le résultat observé : une pièce d'une
    # autre couleur qui bloquerait géométriquement le trajet n'est pas
    # exclue. `propagate_orapa_csp` raisonne sur toutes les pièces à la fois
    # et doit donc au moins égaler, et souvent dépasser, ce filtrage — tout
    # en restant sain (la vraie configuration reste toujours possible).
    domains, truth, actions = _generated_real_piece_problem(seed + 900)
    observations = tuple(observe(truth, *action) for action in actions)

    heuristic = apply_relational_filters(domains, observations)
    propagated, _applied, _deferred = propagate_orapa_csp(
        domains, observations, witness_node_limit=50_000, seed=seed
    )

    heuristic_by_name = {d.piece_name: set(d.placements) for d in heuristic.domains}
    propagated_by_name = {d.piece_name: set(d.placements) for d in propagated}

    for gem, domain in zip(truth.gems, domains):
        assert gem in propagated_by_name[domain.piece_name]

    total_heuristic = sum(len(values) for values in heuristic_by_name.values())
    total_propagated = sum(len(values) for values in propagated_by_name.values())
    for name in heuristic_by_name:
        assert propagated_by_name[name] <= heuristic_by_name[name]
    assert total_propagated <= total_heuristic
