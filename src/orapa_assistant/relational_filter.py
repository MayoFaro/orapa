from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from itertools import product
from math import prod

from .colors import BaseColor, RAY_COLOR_COMPONENTS
from .constraints import gems_are_compatible
from .domain_filter import PlacementDomain, apply_cell_observation
from .raytracer import Configuration, Gem, simulate_ray
from .solver import CellContent, CellObservation, Observation, SolverObservation, gem_occupies_cell


COLOR_PIECE_NAMES = {
    BaseColor.RED: ("red",),
    BaseColor.YELLOW: ("yellow",),
    BaseColor.BLUE: ("blue",),
    BaseColor.WHITE: ("white_diamond", "white_triangle"),
}


@dataclass(frozen=True)
class RelationalFilterResult:
    domains: tuple[PlacementDomain, ...]
    applied_relations: int
    deferred_relations: int


@lru_cache(maxsize=750_000)
def _partial_wave_matches(observation: Observation, gems: tuple[Gem, ...]) -> bool:
    try:
        return (
            simulate_ray(Configuration(gems), observation.entry).outcome
            == observation.outcome
        )
    except RuntimeError:
        return False


def _spatially_compatible(gems: tuple[Gem, ...]) -> bool:
    return all(
        gems_are_compatible(gems[left], gems[right])
        for left in range(len(gems))
        for right in range(left + 1, len(gems))
    )


def _wave_scope(
    domains: tuple[PlacementDomain, ...], observation: Observation
) -> tuple[str, ...]:
    names = {domain.piece_name for domain in domains}
    if observation.absorbed:
        return tuple(domain.piece_name for domain in domains)
    scope: list[str] = []
    assert observation.color is not None
    for color in RAY_COLOR_COMPONENTS[observation.color]:
        scope.extend(name for name in COLOR_PIECE_NAMES[color] if name in names)
    if "diamond" in names:
        scope.append("diamond")
    return tuple(dict.fromkeys(scope))


def _revise_wave_relation(
    domains: tuple[PlacementDomain, ...], observation: Observation
) -> tuple[PlacementDomain, ...]:
    by_name = {domain.piece_name: domain for domain in domains}
    scope = _wave_scope(domains, observation)
    if not scope:
        # Sans diamant, une onde transparente ne rencontre aucune pièce.
        return tuple(
            PlacementDomain(
                domain.piece_name,
                tuple(
                    gem
                    for gem in domain.placements
                    if _partial_wave_matches(observation, (gem,))
                ),
            )
            for domain in domains
        )

    scoped_domains = tuple(by_name[name] for name in scope)
    supported: dict[str, set[Gem]] = {name: set() for name in scope}
    for gems in product(*(domain.placements for domain in scoped_domains)):
        if not _spatially_compatible(gems):
            continue
        if not _partial_wave_matches(observation, gems):
            continue
        for name, gem in zip(scope, gems):
            supported[name].add(gem)

    return tuple(
        PlacementDomain(
            domain.piece_name,
            tuple(
                gem for gem in domain.placements
                if gem in supported[domain.piece_name]
            ),
        )
        if domain.piece_name in supported
        else domain
        for domain in domains
    )


def _revise_white_cell_relation(
    domains: tuple[PlacementDomain, ...], observation: CellObservation
) -> tuple[PlacementDomain, ...]:
    if observation.content != CellContent.WHITE:
        return domains
    by_name = {domain.piece_name: domain for domain in domains}
    white_names = tuple(
        name for name in ("white_diamond", "white_triangle") if name in by_name
    )
    if len(white_names) != 2:
        return domains
    left, right = (by_name[name] for name in white_names)
    supported_left: set[Gem] = set()
    supported_right: set[Gem] = set()
    for first in left.placements:
        for second in right.placements:
            if not gems_are_compatible(first, second):
                continue
            if not (
                gem_occupies_cell(first, observation.row, observation.column)
                or gem_occupies_cell(second, observation.row, observation.column)
            ):
                continue
            supported_left.add(first)
            supported_right.add(second)
    return tuple(
        PlacementDomain(
            domain.piece_name,
            tuple(gem for gem in domain.placements if gem in supported_left),
        )
        if domain.piece_name == white_names[0]
        else PlacementDomain(
            domain.piece_name,
            tuple(gem for gem in domain.placements if gem in supported_right),
        )
        if domain.piece_name == white_names[1]
        else domain
        for domain in domains
    )


def _revise_spatial_constraints(
    domains: tuple[PlacementDomain, ...]
) -> tuple[PlacementDomain, ...]:
    result = list(domains)
    for left_index in range(len(result)):
        for right_index in range(left_index + 1, len(result)):
            left = result[left_index]
            right = result[right_index]
            supported_left = {
                first
                for first in left.placements
                if any(gems_are_compatible(first, second) for second in right.placements)
            }
            supported_right = {
                second
                for second in right.placements
                if any(gems_are_compatible(first, second) for first in supported_left)
            }
            result[left_index] = PlacementDomain(
                left.piece_name,
                tuple(gem for gem in left.placements if gem in supported_left),
            )
            result[right_index] = PlacementDomain(
                right.piece_name,
                tuple(gem for gem in right.placements if gem in supported_right),
            )
    return tuple(result)


def apply_relational_filters(
    domains: tuple[PlacementDomain, ...],
    observations: tuple[SolverObservation, ...],
    *,
    max_relation_combinations: int = 2_000_000,
) -> RelationalFilterResult:
    """Propage les supports communs des observations, sans seuil tout-ou-rien global."""

    result = domains
    cell_observations = tuple(
        observation
        for observation in observations
        if isinstance(observation, CellObservation)
    )
    wave_observations = tuple(
        observation for observation in observations if isinstance(observation, Observation)
    )
    for observation in cell_observations:
        result = apply_cell_observation(result, observation)
        result = _revise_white_cell_relation(result, observation)

    applied: set[int] = set()
    while True:
        previous = tuple(tuple(domain.placements) for domain in result)
        # L'arc-consistance spatiale est utile après les premières réductions,
        # mais très coûteuse et presque stérile sur les catalogues initiaux.
        if prod(len(domain.placements) for domain in result) <= 5_000_000:
            result = _revise_spatial_constraints(result)
        by_name = {domain.piece_name: domain for domain in result}
        ordered = sorted(
            enumerate(wave_observations),
            key=lambda item: prod(
                len(by_name[name].placements)
                for name in _wave_scope(result, item[1])
            ),
        )
        for index, observation in ordered:
            scope = _wave_scope(result, observation)
            combination_count = prod(
                len(by_name[name].placements) for name in scope
            )
            if combination_count > max_relation_combinations:
                continue
            result = _revise_wave_relation(result, observation)
            by_name = {domain.piece_name: domain for domain in result}
            applied.add(index)
            if any(not domain.placements for domain in result):
                return RelationalFilterResult(
                    result, len(applied), len(wave_observations) - len(applied)
                )
        if tuple(tuple(domain.placements) for domain in result) == previous:
            break

    return RelationalFilterResult(
        result, len(applied), len(wave_observations) - len(applied)
    )
