from __future__ import annotations

from dataclasses import dataclass
from math import prod

from .constraints import gems_are_compatible
from .domain_filter import PlacementDomain
from .raytracer import Configuration, Gem, simulate_ray
from .solver import (
    CellObservation, Observation, SolverObservation, configuration_cell_content,
)


class SearchSpaceTooLarge(RuntimeError):
    pass


@dataclass(frozen=True)
class SearchResult:
    configurations: tuple[Configuration, ...]
    raw_combination_count: int
    legal_configuration_count: int


def configuration_matches(
    configuration: Configuration,
    observations: tuple[SolverObservation, ...],
) -> bool:
    for observation in observations:
        if isinstance(observation, Observation):
            if simulate_ray(configuration, observation.entry).outcome != observation.outcome:
                return False
        elif configuration_cell_content(
            configuration, observation.row, observation.column
        ) != observation.content:
            return False
    return True


def search_configurations(
    domains: tuple[PlacementDomain, ...],
    observations: tuple[SolverObservation, ...],
    *,
    max_raw_combinations: int = 5_000_000,
) -> SearchResult:
    raw_count = prod(len(domain.placements) for domain in domains)
    if raw_count > max_raw_combinations:
        raise SearchSpaceTooLarge(
            f"{raw_count:,} combinaisons brutes dépassent la limite "
            f"de {max_raw_combinations:,}"
        )

    ordered = tuple(sorted(domains, key=lambda domain: len(domain.placements)))
    solutions: list[Configuration] = []
    legal_count = 0

    def visit(depth: int, selected: tuple[Gem, ...]) -> None:
        nonlocal legal_count
        if depth == len(ordered):
            legal_count += 1
            configuration = Configuration(selected)
            if configuration_matches(configuration, observations):
                solutions.append(configuration)
            return

        for gem in ordered[depth].placements:
            if all(gems_are_compatible(gem, previous) for previous in selected):
                visit(depth + 1, selected + (gem,))

    visit(0, ())
    return SearchResult(tuple(solutions), raw_count, legal_count)
