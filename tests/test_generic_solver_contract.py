from __future__ import annotations

from random import Random

import pytest

from orapa_assistant.border import ALL_BORDER_POINTS
from orapa_assistant.colors import BaseColor
from orapa_assistant.domain_filter import PlacementDomain
from orapa_assistant.geometry import doubled_polygon
from orapa_assistant.raytracer import Configuration, Gem
from orapa_assistant.search import search_configurations
from orapa_assistant.solver import Solver
from tests.bruteforce_oracle import (
    configuration_key,
    legal_configurations,
    observe,
    score_action,
    solve,
)


SAFE_CELLS = tuple(
    (column, row)
    for row in (0, 2, 4, 6)
    for column in (1, 3, 5, 7, 9)
)
PIECE_SPECS = (
    ("red", BaseColor.RED),
    ("blue", BaseColor.BLUE),
    ("yellow", BaseColor.YELLOW),
)


def _square(name: str, color: BaseColor, cell: tuple[int, int]) -> Gem:
    column, row = cell
    return Gem(
        color,
        doubled_polygon(
            (column - 1, row),
            (column, row),
            (column, row + 1),
            (column - 1, row + 1),
        ),
        name,
    )


def _generated_reduced_problem(
    seed: int,
) -> tuple[tuple[PlacementDomain, ...], Configuration, tuple[tuple[str, str], ...]]:
    """Crée un CSP minuscule sans reprendre aucun historique de partie."""

    random = Random(seed)
    true_cells = random.sample(SAFE_CELLS, len(PIECE_SPECS))
    domains: list[PlacementDomain] = []
    true_gems: list[Gem] = []
    for (name, color), true_cell in zip(PIECE_SPECS, true_cells, strict=True):
        decoys = random.sample(
            [cell for cell in SAFE_CELLS if cell != true_cell],
            2,
        )
        cells = [true_cell, *decoys]
        random.shuffle(cells)
        gems = tuple(_square(name, color, cell) for cell in cells)
        domains.append(PlacementDomain(name, gems))
        true_gems.append(_square(name, color, true_cell))

    empty_cells = [cell for cell in SAFE_CELLS if cell not in true_cells]
    inspected = [*true_cells, *random.sample(empty_cells, 2)]
    random.shuffle(inspected)
    actions = [
        *(("wave", entry) for entry in random.sample(list(ALL_BORDER_POINTS), 5)),
        *(("cell", f"{chr(ord('A') + row)}{column}") for column, row in inspected),
    ]
    random.shuffle(actions)
    return tuple(domains), Configuration(tuple(true_gems)), tuple(actions)


def _keys(configurations) -> set[tuple]:
    return {configuration_key(configuration) for configuration in configurations}


@pytest.mark.parametrize("seed", range(8))
def test_exact_search_equals_independent_oracle_on_generated_small_domains(
    seed: int,
) -> None:
    domains, truth, actions = _generated_reduced_problem(seed)
    observations = []
    previous_keys = _keys(legal_configurations(domains))

    for action, target in actions:
        observations.append(observe(truth, action, target))
        expected = solve(domains, observations)
        result = search_configurations(
            domains,
            tuple(observations),
            max_raw_combinations=1_000,
        )
        actual_keys = _keys(result.configurations)
        expected_keys = _keys(expected)

        # Complétude et soundness sont vérifiées séparément pour rendre une
        # éventuelle régression immédiatement lisible.
        assert expected_keys <= actual_keys
        assert actual_keys <= expected_keys
        assert configuration_key(truth) in actual_keys
        assert actual_keys <= previous_keys
        previous_keys = actual_keys


def test_filtering_is_independent_of_observation_order() -> None:
    domains, truth, actions = _generated_reduced_problem(73)
    observations = tuple(observe(truth, *action) for action in actions)
    forward = search_configurations(domains, observations, max_raw_combinations=1_000)
    backward = search_configurations(
        domains,
        tuple(reversed(observations)),
        max_raw_combinations=1_000,
    )
    assert _keys(forward.configurations) == _keys(backward.configurations)


def test_certainties_are_exactly_the_placements_shared_by_all_models() -> None:
    domains, truth, actions = _generated_reduced_problem(101)
    catalogue = legal_configurations(domains)
    solver = Solver(catalogue)
    for action in actions[:6]:
        solver.add_observation(observe(truth, *action))

    expected = []
    for name, _ in PIECE_SPECS:
        placements = {
            next(gem for gem in candidate.gems if gem.name == name)
            for candidate in solver.candidates
        }
        if len(placements) == 1:
            expected.extend(placements)

    assert set(solver.certain_gems) == set(expected)


def test_every_recommendation_metric_matches_an_independent_partition() -> None:
    domains, truth, actions = _generated_reduced_problem(211)
    solver = Solver(legal_configurations(domains))
    used_action = actions[0]
    solver.add_observation(observe(truth, *used_action))
    scores = solver.rank_next_moves()

    assert scores
    assert (used_action[0], used_action[1]) not in {
        (score.action, score.target) for score in scores
    }
    for score in scores:
        expected = score_action(solver.candidates, score.action, score.target)
        assert score.worst_case == expected.worst_case
        assert score.expected_remaining == pytest.approx(expected.expected_remaining)
        assert score.entropy == pytest.approx(expected.entropy)
        assert score.outcome_count == expected.outcome_count

    expected_scores = [
        score_action(solver.candidates, "wave", entry)
        for entry in ALL_BORDER_POINTS
        if used_action != ("wave", entry)
    ]
    expected_scores.extend(
        score_action(solver.candidates, "cell", f"{row}{column}")
        for row in "ABCDEFGH"
        for column in range(1, 11)
        if used_action != ("cell", f"{row}{column}")
    )
    assert {
        (score.action, score.target) for score in scores
    } == {
        (score.action, score.target) for score in expected_scores
    }

    minimum_worst_case = min(score.worst_case for score in expected_scores)
    minimum_expected = min(
        score.expected_remaining
        for score in expected_scores
        if score.worst_case == minimum_worst_case
    )
    maximum_entropy = max(
        score.entropy
        for score in expected_scores
        if score.worst_case == minimum_worst_case
        and score.expected_remaining == pytest.approx(minimum_expected)
    )
    best = scores[0]
    assert best.worst_case == minimum_worst_case
    assert best.expected_remaining == pytest.approx(minimum_expected)
    assert best.entropy == pytest.approx(maximum_entropy)
