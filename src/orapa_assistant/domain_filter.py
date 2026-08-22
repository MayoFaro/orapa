from __future__ import annotations

from dataclasses import dataclass
from itertools import product
from math import prod

from .colors import BaseColor, RAY_COLOR_COMPONENTS, RayColor
from .constraints import gems_are_compatible
from .raytracer import Configuration, Gem, simulate_ray
from .solver import (
    CellContent, CellObservation, Observation, SolverObservation, gem_occupies_cell,
)


@dataclass(frozen=True)
class PlacementDomain:
    piece_name: str
    placements: tuple[Gem, ...]


SINGLE_COLOR_OUTCOMES = {
    RayColor.RED: BaseColor.RED,
    RayColor.YELLOW: BaseColor.YELLOW,
    RayColor.BLUE: BaseColor.BLUE,
}


def filter_domain_by_transparent_observation(
    domain: PlacementDomain,
    observation: Observation,
) -> PlacementDomain:
    """Filtre exact pour le jeu de base, qui ne contient pas de diamant."""

    if observation.color != RayColor.TRANSPARENT:
        raise ValueError("Ce filtre ne s'applique qu'aux ondes transparentes")
    compatible = tuple(
        gem
        for gem in domain.placements
        if simulate_ray(Configuration((gem,)), observation.entry).outcome
        == observation.outcome
    )
    return PlacementDomain(domain.piece_name, compatible)


def apply_transparent_observations(
    domains: tuple[PlacementDomain, ...],
    observations: tuple[Observation, ...],
) -> tuple[PlacementDomain, ...]:
    if any(domain.piece_name == "diamond" for domain in domains):
        return domains
    result = domains
    for observation in observations:
        if observation.color == RayColor.TRANSPARENT:
            result = tuple(
                filter_domain_by_transparent_observation(domain, observation)
                for domain in result
            )
    return result


def apply_unique_color_observations(
    domains: tuple[PlacementDomain, ...],
    observations: tuple[Observation, ...],
) -> tuple[PlacementDomain, ...]:
    """Contraint rouge/jaune/bleu, présents chacun en un seul exemplaire."""

    if any(domain.piece_name == "diamond" for domain in domains):
        return domains
    result: list[PlacementDomain] = []
    for domain in domains:
        placements = domain.placements
        if not placements:
            result.append(domain)
            continue
        piece_color = placements[0].color
        relevant = tuple(
            observation
            for observation in observations
            if SINGLE_COLOR_OUTCOMES.get(observation.color) == piece_color
        )
        for observation in relevant:
            placements = tuple(
                gem
                for gem in placements
                if simulate_ray(Configuration((gem,)), observation.entry).outcome
                == observation.outcome
            )
        result.append(PlacementDomain(domain.piece_name, placements))
    return tuple(result)


def apply_exact_unary_observations(
    domains: tuple[PlacementDomain, ...],
    observations: tuple[Observation, ...],
) -> tuple[PlacementDomain, ...]:
    transparent_filtered = apply_transparent_observations(domains, observations)
    return apply_unique_color_observations(transparent_filtered, observations)


def _tuple_is_spatially_compatible(gems: tuple[Gem, ...]) -> bool:
    return all(
        gems_are_compatible(gems[left], gems[right])
        for left in range(len(gems))
        for right in range(left + 1, len(gems))
    )


def prune_domains_by_observation_support(
    domains: tuple[PlacementDomain, ...],
    observation: Observation,
    *,
    max_relation_combinations: int = 20_000,
) -> tuple[PlacementDomain, ...]:
    """Conserve chaque placement ayant au moins un support pour l'observation.

    Les pièces dont la couleur n'apparaît pas dans le résultat ne peuvent pas
    avoir été rencontrées. En les retirant, le trajet observable ne change donc
    pas. La relation sur les seules couleurs présentes est une contrainte exacte.
    """

    if observation.absorbed:
        involved_indices = tuple(range(len(domains)))
    else:
        if observation.color is None:
            return domains
        included_colors = RAY_COLOR_COMPONENTS[observation.color]
        involved_indices = tuple(
            index
            for index, domain in enumerate(domains)
            if domain.placements
            and (
                domain.placements[0].color in included_colors
                or domain.piece_name == "diamond"
            )
        )
    if not involved_indices:
        return domains
    involved_domains = tuple(domains[index] for index in involved_indices)
    combination_count = prod(len(domain.placements) for domain in involved_domains)
    if combination_count > max_relation_combinations:
        return domains

    supported: list[set[Gem]] = [set() for _ in involved_domains]
    for gems in product(*(domain.placements for domain in involved_domains)):
        if not _tuple_is_spatially_compatible(gems):
            continue
        configuration = Configuration(gems)
        if simulate_ray(configuration, observation.entry).outcome != observation.outcome:
            continue
        for index, gem in enumerate(gems):
            supported[index].add(gem)

    result = list(domains)
    for local_index, domain_index in enumerate(involved_indices):
        result[domain_index] = PlacementDomain(
            domains[domain_index].piece_name,
            tuple(
                gem
                for gem in domains[domain_index].placements
                if gem in supported[local_index]
            ),
        )
    return tuple(result)


def apply_exact_observation_filters(
    domains: tuple[PlacementDomain, ...],
    observations: tuple[SolverObservation, ...],
    *,
    max_relation_combinations: int = 20_000,
) -> tuple[PlacementDomain, ...]:
    wave_observations = tuple(
        observation for observation in observations
        if isinstance(observation, Observation)
    )
    result = apply_exact_unary_observations(domains, wave_observations)
    for observation in observations:
        if isinstance(observation, CellObservation):
            result = apply_cell_observation(result, observation)
    while True:
        previous_sizes = tuple(len(domain.placements) for domain in result)
        for observation in wave_observations:
            result = prune_domains_by_observation_support(
                result,
                observation,
                max_relation_combinations=max_relation_combinations,
            )
        if tuple(len(domain.placements) for domain in result) == previous_sizes:
            return result


def apply_cell_observation(
    domains: tuple[PlacementDomain, ...], observation: CellObservation
) -> tuple[PlacementDomain, ...]:
    """Applique exactement l'information révélée, sans déduire l'orientation."""

    def matches_piece(domain: PlacementDomain) -> bool:
        if observation.content == CellContent.WHITE:
            return domain.piece_name in ("white_diamond", "white_triangle")
        return domain.piece_name == observation.content.value

    if observation.content == CellContent.NOTHING:
        return tuple(
            PlacementDomain(domain.piece_name, tuple(
                gem for gem in domain.placements
                if not gem_occupies_cell(gem, observation.row, observation.column)
            ))
            for domain in domains
        )

    result = []
    for domain in domains:
        if matches_piece(domain):
            placements = domain.placements
            # Pour le blanc, l'autre pierre blanche peut être celle qui occupe la case.
            if observation.content != CellContent.WHITE:
                placements = tuple(
                    gem for gem in placements
                    if gem_occupies_cell(gem, observation.row, observation.column)
                )
        else:
            placements = tuple(
                gem for gem in domain.placements
                if not gem_occupies_cell(gem, observation.row, observation.column)
            )
        result.append(PlacementDomain(domain.piece_name, placements))
    return tuple(result)
