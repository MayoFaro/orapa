from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from itertools import product
from math import prod
from time import perf_counter

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
    state: RelationalFilterState


DomainSignature = tuple[tuple[str, tuple[Gem, ...]], ...]


@dataclass(frozen=True)
class RelationAttempt:
    signature: DomainSignature
    completed: bool


@dataclass(frozen=True)
class RelationalFilterState:
    observations: tuple[SolverObservation, ...]
    attempts: tuple[RelationAttempt | None, ...]
    spatial_signature: DomainSignature | None = None


@dataclass(frozen=True)
class _RelationRevision:
    domains: tuple[PlacementDomain, ...]
    completed: bool


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
    domains: tuple[PlacementDomain, ...],
    observation: Observation,
    *,
    max_seconds: float | None = None,
) -> _RelationRevision:
    by_name = {domain.piece_name: domain for domain in domains}
    scope = _wave_scope(domains, observation)
    deadline = perf_counter() + max_seconds if max_seconds is not None else None
    if not scope:
        # Sans diamant, une onde transparente ne rencontre aucune pièce.
        revised = []
        for domain in domains:
            supported = []
            for index, gem in enumerate(domain.placements):
                if (
                    deadline is not None
                    and index % 256 == 0
                    and perf_counter() >= deadline
                ):
                    return _RelationRevision(domains, False)
                if _partial_wave_matches(observation, (gem,)):
                    supported.append(gem)
            revised.append(PlacementDomain(domain.piece_name, tuple(supported)))
        return _RelationRevision(tuple(revised), True)

    scoped_domains = tuple(by_name[name] for name in scope)
    supported: dict[str, set[Gem]] = {name: set() for name in scope}
    for index, gems in enumerate(
        product(*(domain.placements for domain in scoped_domains))
    ):
        if (
            deadline is not None
            and index % 256 == 0
            and perf_counter() >= deadline
        ):
            return _RelationRevision(domains, False)
        if not _spatially_compatible(gems):
            continue
        if not _partial_wave_matches(observation, gems):
            continue
        for name, gem in zip(scope, gems):
            supported[name].add(gem)

    return _RelationRevision(
        tuple(
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
        ),
        True,
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


def _domain_signature(
    domains: tuple[PlacementDomain, ...], names: tuple[str, ...] | None = None
) -> DomainSignature:
    selected = set(names) if names is not None else None
    return tuple(
        (domain.piece_name, domain.placements)
        for domain in domains
        if selected is None or domain.piece_name in selected
    )


def _relation_names(
    domains: tuple[PlacementDomain, ...], observation: SolverObservation
) -> tuple[str, ...]:
    if isinstance(observation, CellObservation):
        if observation.content == CellContent.WHITE:
            return tuple(
                domain.piece_name
                for domain in domains
                if domain.piece_name in ("white_diamond", "white_triangle")
            )
        return ()
    scope = _wave_scope(domains, observation)
    if scope:
        return scope
    # Le cas transparent sans diamant applique un filtre unaire à chaque pièce.
    return tuple(domain.piece_name for domain in domains)


def _relation_work(
    domains: tuple[PlacementDomain, ...], observation: Observation
) -> int:
    scope = _wave_scope(domains, observation)
    if not scope:
        return sum(len(domain.placements) for domain in domains)
    by_name = {domain.piece_name: domain for domain in domains}
    combinations = prod(len(by_name[name].placements) for name in scope)
    compatibility_checks = len(scope) * (len(scope) - 1) // 2
    return combinations * (1 + compatibility_checks)


def _fresh_state(
    observations: tuple[SolverObservation, ...],
) -> RelationalFilterState:
    return RelationalFilterState(
        observations=observations,
        attempts=(None,) * len(observations),
    )


def apply_relational_filters(
    domains: tuple[PlacementDomain, ...],
    observations: tuple[SolverObservation, ...],
    *,
    state: RelationalFilterState | None = None,
    max_relation_work: int = 500_000,
    max_relation_seconds: float | None = None,
    stop_domain_mass: int | None = None,
) -> RelationalFilterResult:
    """Propage exactement les relations abordables et mémorise le point fixe.

    Une relation dépassant le budget est seulement différée : ses domaines
    restent inchangés. La propagation demeure donc sûre, même lorsqu'elle est
    interrompue. L'état optionnel évite de rejouer les relations dont les
    domaines utiles n'ont pas changé depuis leur dernière tentative.
    """

    if max_relation_work <= 0:
        raise ValueError("Le budget relationnel doit être positif")
    if max_relation_seconds is not None and max_relation_seconds <= 0:
        raise ValueError("Le budget temporel doit être positif")
    if stop_domain_mass is not None and stop_domain_mass <= 0:
        raise ValueError("Le seuil d'arrêt doit être positif")

    if (
        state is None
        or len(state.observations) > len(observations)
        or observations[: len(state.observations)] != state.observations
    ):
        state = _fresh_state(observations)
        previous_observation_count = 0
    else:
        previous_observation_count = len(state.observations)
        state = RelationalFilterState(
            observations=observations,
            attempts=state.attempts
            + (None,) * (len(observations) - len(state.attempts)),
            spatial_signature=state.spatial_signature,
        )

    result = domains
    attempts = list(state.attempts)
    spatial_signature = state.spatial_signature

    # Les filtres cellulaires unaires sont monotones : il suffit de les
    # appliquer une fois, à l'arrivée de la nouvelle observation.
    for index in range(previous_observation_count, len(observations)):
        observation = observations[index]
        if not isinstance(observation, CellObservation):
            continue
        result = apply_cell_observation(result, observation)
        if observation.content != CellContent.WHITE:
            attempts[index] = RelationAttempt((), True)

    while True:
        changed = False
        stop_requested = False

        # La contrainte spatiale n'est rejouée que si un domaine a changé
        # depuis son dernier point fixe.
        if prod(len(domain.placements) for domain in result) <= 5_000_000:
            current_spatial_signature = _domain_signature(result)
            if current_spatial_signature != spatial_signature:
                revised = _revise_spatial_constraints(result)
                spatial_signature = current_spatial_signature
                if revised != result:
                    result = revised
                    changed = True

        pending: list[tuple[int, int]] = []
        for index, observation in enumerate(observations):
            names = _relation_names(result, observation)
            if not names:
                continue
            signature = _domain_signature(result, names)
            attempt = attempts[index]
            if attempt is not None and attempt.signature == signature:
                continue
            work = (
                _relation_work(result, observation)
                if isinstance(observation, Observation)
                else 0
            )
            pending.append((work, index))

        if not pending and not changed:
            break

        for _work, index in sorted(pending):
            observation = observations[index]
            names = _relation_names(result, observation)
            signature = _domain_signature(result, names)
            attempt = attempts[index]
            if attempt is not None and attempt.signature == signature:
                continue

            if isinstance(observation, CellObservation):
                revised = _revise_white_cell_relation(result, observation)
                completed = True
            else:
                work = _relation_work(result, observation)
                if work > max_relation_work:
                    attempts[index] = RelationAttempt(signature, False)
                    continue
                revision = _revise_wave_relation(
                    result,
                    observation,
                    max_seconds=max_relation_seconds,
                )
                revised = revision.domains
                completed = revision.completed

            attempts[index] = RelationAttempt(signature, completed)
            if completed and revised != result:
                result = revised
                changed = True
            if any(not domain.placements for domain in result):
                final_state = RelationalFilterState(
                    observations, tuple(attempts), spatial_signature
                )
                applied, deferred = _relation_counts(
                    result, observations, attempts
                )
                return RelationalFilterResult(
                    result, applied, deferred, final_state
                )
            if (
                changed
                and stop_domain_mass is not None
                and sum(len(domain.placements) for domain in result)
                <= stop_domain_mass
            ):
                stop_requested = True
                break

        if stop_requested:
            break

    final_state = RelationalFilterState(
        observations, tuple(attempts), spatial_signature
    )
    applied, deferred = _relation_counts(result, observations, attempts)
    return RelationalFilterResult(
        result, applied, deferred, final_state
    )


def _relation_counts(
    domains: tuple[PlacementDomain, ...],
    observations: tuple[SolverObservation, ...],
    attempts: list[RelationAttempt | None],
) -> tuple[int, int]:
    applied = 0
    deferred = 0
    for index, observation in enumerate(observations):
        if not isinstance(observation, Observation):
            continue
        names = _relation_names(domains, observation)
        signature = _domain_signature(domains, names)
        attempt = attempts[index]
        if (
            attempt is not None
            and attempt.completed
            and attempt.signature == signature
        ):
            applied += 1
        else:
            deferred += 1
    return applied, deferred
