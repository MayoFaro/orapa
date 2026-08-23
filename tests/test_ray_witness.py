from __future__ import annotations

from itertools import product
import random

import pytest

from orapa_assistant.colors import BaseColor, RayColor
from orapa_assistant.geometry import Point, Polygon
from orapa_assistant.pieces import BLACK_BODY, DIAMOND, PIECES, placements
from orapa_assistant.ray_witness import (
    LocalHitIndex,
    PlacementCatalog,
    RayWitnessFinder,
    WitnessSearchStatus,
)
from orapa_assistant.raytracer import (
    Configuration,
    Direction,
    Gem,
    RayOutcome,
    first_local_hit,
    ray_entry_state,
    simulate_ray,
)


BACKSLASH_TRIANGLE = ((0, 0), (2, 2), (2, 0))
SLASH_TRIANGLE = ((2, 0), (0, 2), (2, 2))


def _polygon(
    coordinates: tuple[tuple[int, int], ...], dx: int = 0, dy: int = 0
) -> Polygon:
    return Polygon(tuple(Point(x + dx, y + dy) for x, y in coordinates))


def _small_catalog() -> PlacementCatalog:
    return PlacementCatalog(
        {
            "red": (
                Gem(BaseColor.RED, _polygon(BACKSLASH_TRIANGLE), "red"),
                Gem(BaseColor.RED, _polygon(BACKSLASH_TRIANGLE, 6), "red"),
                Gem(BaseColor.RED, _polygon(BACKSLASH_TRIANGLE, 0, 6), "red"),
            ),
            "blue": (
                # Même impact et même direction que red[0].
                Gem(BaseColor.BLUE, _polygon(BACKSLASH_TRIANGLE), "blue"),
                # Même impact, mais direction opposée : collision ambiguë.
                Gem(BaseColor.BLUE, _polygon(SLASH_TRIANGLE), "blue"),
                Gem(BaseColor.BLUE, _polygon(BACKSLASH_TRIANGLE, 8, 6), "blue"),
            ),
            "diamond": (
                Gem(None, _polygon(BACKSLASH_TRIANGLE, 2), "diamond"),
                Gem(None, _polygon(SLASH_TRIANGLE, 10), "diamond"),
                Gem(None, _polygon(BACKSLASH_TRIANGLE, 4, 6), "diamond"),
            ),
            "black": (
                Gem(
                    None,
                    _polygon(((4, 0), (6, 0), (6, 2), (4, 2))),
                    "black",
                    True,
                ),
                Gem(
                    None,
                    _polygon(((4, 6), (8, 6), (8, 8), (4, 8))),
                    "black",
                    True,
                ),
                Gem(
                    None,
                    _polygon(((12, 0), (14, 0), (14, 2), (12, 2))),
                    "black",
                    True,
                ),
            ),
        }
    )


def _outcome_or_none(gems: tuple[Gem, ...], entry: str) -> RayOutcome | None:
    try:
        return simulate_ray(Configuration(gems), entry).outcome
    except RuntimeError:
        # Une collision ambiguë ou un cycle n'est le support d'aucune réponse.
        return None


def _values_for_masks(
    catalog: PlacementCatalog, masks: tuple[int, ...]
) -> tuple[tuple[Gem, ...], ...]:
    return tuple(
        tuple(
            gem
            for value_index, gem in enumerate(values)
            if mask & (1 << value_index)
        )
        for values, mask in zip(catalog.placements, masks)
    )


def test_first_local_hit_exposes_exact_distance_and_corner_directions() -> None:
    gem = Gem(BaseColor.RED, _polygon(BACKSLASH_TRIANGLE), "red")
    position, direction = ray_entry_state("A")
    hit = first_local_hit(gem, position, direction)
    assert hit is not None
    assert hit.distance == 2
    assert hit.outgoing == frozenset({Direction.SOUTH})
    assert not hit.absorbed


def test_local_hit_index_groups_placements_in_bitsets() -> None:
    catalog = _small_catalog()
    index = LocalHitIndex(catalog)
    position, direction = ray_entry_state("A")
    red = index.for_state(catalog.piece_index("red"), position, direction)
    assert red.reflecting_at[(2, Direction.SOUTH)] & 1
    assert red.no_hit_mask & (1 << 2)
    assert red.strict_after(2) & (1 << 1)
    assert not red.strict_after(2) & 1


def test_witness_boxes_are_sound_for_all_reduced_domain_outcomes() -> None:
    catalog = _small_catalog()
    configurations = tuple(product(*catalog.placements))
    outcomes = {
        outcome
        for gems in configurations
        if (outcome := _outcome_or_none(gems, "A")) is not None
    }
    assert RayOutcome.absorption() in outcomes
    assert RayOutcome("I", RayColor.VIOLET) in outcomes

    shared_index = LocalHitIndex(catalog)
    for outcome in outcomes:
        result = RayWitnessFinder(
            catalog, "A", outcome, hit_index=shared_index
        ).search(max_nodes=100_000)
        assert result.status == WitnessSearchStatus.FOUND
        assert result.witness is not None
        for gems in product(
            *_values_for_masks(catalog, result.witness.allowed_masks)
        ):
            assert _outcome_or_none(gems, "A") == outcome


def test_support_search_matches_exhaustive_oracle_on_reduced_domains() -> None:
    catalog = _small_catalog()
    configurations = tuple(product(*catalog.placements))
    outcomes = {
        outcome
        for gems in configurations
        if (outcome := _outcome_or_none(gems, "A")) is not None
    }
    shared_index = LocalHitIndex(catalog)

    for outcome in outcomes:
        finder = RayWitnessFinder(
            catalog, "A", outcome, hit_index=shared_index
        )
        for piece_index, piece_name in enumerate(catalog.names):
            for value_index, value in enumerate(catalog.placements[piece_index]):
                expected = any(
                    gems[piece_index] == value
                    and _outcome_or_none(gems, "A") == outcome
                    for gems in configurations
                )
                masks = list(catalog.full_masks)
                masks[piece_index] = 1 << value_index
                result = finder.search_masks(tuple(masks), max_nodes=100_000)
                assert result.status != WitnessSearchStatus.UNKNOWN
                assert (result.status == WitnessSearchStatus.FOUND) == expected, (
                    outcome,
                    piece_name,
                    value_index,
                )


@pytest.mark.parametrize(
    ("seed", "entry"), ((11, "A"), (29, "6"), (47, "15"), (71, "K"))
)
def test_support_search_matches_oracle_on_real_piece_subdomains(
    seed: int, entry: str
) -> None:
    rng = random.Random(seed)
    definitions = (*PIECES, DIAMOND, BLACK_BODY)
    catalog = PlacementCatalog(
        {
            definition.name: tuple(rng.sample(placements(definition), 2))
            for definition in definitions
        }
    )
    configurations = tuple(product(*catalog.placements))
    by_outcome: dict[RayOutcome, list[tuple[Gem, ...]]] = {}
    for gems in configurations:
        outcome = _outcome_or_none(gems, entry)
        if outcome is not None:
            by_outcome.setdefault(outcome, []).append(gems)

    shared_index = LocalHitIndex(catalog)
    for outcome, matching in by_outcome.items():
        finder = RayWitnessFinder(
            catalog, entry, outcome, hit_index=shared_index
        )
        for piece_index in range(len(catalog)):
            for value_index, value in enumerate(catalog.placements[piece_index]):
                expected = any(gems[piece_index] == value for gems in matching)
                masks = list(catalog.full_masks)
                masks[piece_index] = 1 << value_index
                result = finder.search_masks(tuple(masks), max_nodes=100_000)
                assert result.status != WitnessSearchStatus.UNKNOWN
                assert (result.status == WitnessSearchStatus.FOUND) == expected


def test_same_direction_simultaneous_hits_mix_both_colors() -> None:
    polygon = _polygon(BACKSLASH_TRIANGLE)
    catalog = PlacementCatalog(
        {
            "red": (Gem(BaseColor.RED, polygon, "red"),),
            "blue": (Gem(BaseColor.BLUE, polygon, "blue"),),
        }
    )
    expected = RayOutcome("I", RayColor.VIOLET)
    assert simulate_ray(
        Configuration(tuple(values[0] for values in catalog.placements)), "A"
    ).outcome == expected
    result = RayWitnessFinder(catalog, "A", expected).search()
    assert result.status == WitnessSearchStatus.FOUND


def test_opposite_direction_simultaneous_hits_have_no_support() -> None:
    catalog = PlacementCatalog(
        {
            "red": (
                Gem(BaseColor.RED, _polygon(BACKSLASH_TRIANGLE), "red"),
            ),
            "blue": (
                Gem(BaseColor.BLUE, _polygon(SLASH_TRIANGLE), "blue"),
            ),
        }
    )
    result = RayWitnessFinder(
        catalog, "A", RayOutcome("I", RayColor.VIOLET)
    ).search()
    assert result.status == WitnessSearchStatus.IMPOSSIBLE


def test_absorber_wins_a_simultaneous_collision() -> None:
    polygon = _polygon(BACKSLASH_TRIANGLE)
    catalog = PlacementCatalog(
        {
            "red": (Gem(BaseColor.RED, polygon, "red"),),
            "black": (Gem(None, polygon, "black", True),),
        }
    )
    expected = RayOutcome.absorption()
    gems = tuple(values[0] for values in catalog.placements)
    assert simulate_ray(Configuration(gems), "A").outcome == expected
    result = RayWitnessFinder(catalog, "A", expected).search()
    assert result.status == WitnessSearchStatus.FOUND
    assert result.witness is not None
    assert result.witness.absorbed


def test_budget_and_cancellation_return_unknown_never_impossible() -> None:
    catalog = _small_catalog()
    finder = RayWitnessFinder(
        catalog, "A", RayOutcome("I", RayColor.VIOLET)
    )
    budget = finder.search(max_nodes=0)
    assert budget.status == WitnessSearchStatus.UNKNOWN
    assert not budget.definitive
    assert budget.reason == "node_budget"

    cancelled = finder.search(cancelled=lambda: True)
    assert cancelled.status == WitnessSearchStatus.UNKNOWN
    assert not cancelled.definitive
    assert cancelled.reason == "cancelled"
