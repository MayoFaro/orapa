"""Petit oracle exhaustif, volontairement indépendant des moteurs de recherche.

Cet oracle n'est destiné qu'aux domaines réduits des tests. Il s'appuie sur les
deux briques considérées comme la spécification exécutable du jeu : les règles
géométriques entre pierres et le simulateur d'ondes. Il n'importe ni
``search_configurations`` ni aucune classe de solveur.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from itertools import product
from math import log2
from typing import Hashable, Iterable

from orapa_assistant.border import ALL_BORDER_POINTS
from orapa_assistant.constraints import gems_are_compatible
from orapa_assistant.domain_filter import PlacementDomain
from orapa_assistant.raytracer import Configuration, simulate_ray
from orapa_assistant.solver import (
    CellObservation,
    Observation,
    SolverObservation,
    configuration_cell_content,
)


Action = tuple[str, str]

ALL_ACTIONS: tuple[Action, ...] = tuple(
    ("wave", entry) for entry in ALL_BORDER_POINTS
) + tuple(
    ("cell", f"{row}{column}")
    for row in "ABCDEFGH"
    for column in range(1, 11)
)


@dataclass(frozen=True)
class OracleScore:
    action: str
    target: str
    entropy: float
    worst_case: int
    win_probability: float
    expected_remaining: float
    outcome_count: int

    @property
    def sort_key(self) -> tuple[float | int | str, ...]:
        return (
            self.worst_case,
            self.expected_remaining,
            -self.entropy,
            self.action,
            self.target,
        )


def configuration_key(configuration: Configuration) -> tuple:
    """Signature insensible à l'ordre choisi pour parcourir les domaines."""

    return tuple(sorted(
        (
            gem.name,
            gem.color.value if gem.color is not None else None,
            gem.absorbs,
            tuple((point.x, point.y) for point in gem.polygon.vertices),
        )
        for gem in configuration.gems
    ))


def legal_configurations(
    domains: tuple[PlacementDomain, ...],
) -> tuple[Configuration, ...]:
    """Énumère directement le produit cartésien d'un *petit* cas de test."""

    result: list[Configuration] = []
    for assignment in product(*(domain.placements for domain in domains)):
        if all(
            gems_are_compatible(assignment[left], assignment[right])
            for left in range(len(assignment))
            for right in range(left + 1, len(assignment))
        ):
            result.append(Configuration(tuple(assignment)))
    return tuple(result)


def matches_observations(
    configuration: Configuration,
    observations: Iterable[SolverObservation],
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


def solve(
    domains: tuple[PlacementDomain, ...],
    observations: Iterable[SolverObservation] = (),
) -> tuple[Configuration, ...]:
    observations = tuple(observations)
    return tuple(
        configuration
        for configuration in legal_configurations(domains)
        if matches_observations(configuration, observations)
    )


def observe(
    configuration: Configuration, action: str, target: str
) -> SolverObservation:
    """Produit la réponse vraie d'une configuration à une question."""

    if action == "wave":
        outcome = simulate_ray(configuration, target).outcome
        return Observation(
            target,
            outcome.exit_point,
            outcome.color,
            absorbed=outcome.absorbed,
        )
    if action == "cell":
        return CellObservation(
            target[0],
            int(target[1:]),
            configuration_cell_content(configuration, target[0], int(target[1:])),
        )
    raise ValueError(f"Action inconnue : {action!r}")


def action_outcome(
    configuration: Configuration, action: str, target: str
) -> Hashable:
    if action == "wave":
        return simulate_ray(configuration, target).outcome
    if action == "cell":
        return configuration_cell_content(configuration, target[0], int(target[1:]))
    raise ValueError(f"Action inconnue : {action!r}")


def partition_sizes(
    configurations: Iterable[Configuration], action: str, target: str
) -> tuple[int, ...]:
    groups = Counter(
        action_outcome(configuration, action, target)
        for configuration in configurations
    )
    return tuple(sorted(groups.values(), reverse=True))


def score_action(
    configurations: Iterable[Configuration], action: str, target: str
) -> OracleScore:
    configurations = tuple(configurations)
    total = len(configurations)
    if not total:
        raise ValueError("Impossible de noter une action sans hypothèse")
    groups = partition_sizes(configurations, action, target)
    entropy = -sum(
        (size / total) * log2(size / total)
        for size in groups
    )
    expected = sum(size * size for size in groups) / total
    win_probability = sum(1 for size in groups if size == 1) / total
    return OracleScore(
        action,
        target,
        entropy,
        max(groups),
        win_probability,
        expected,
        len(groups),
    )


def best_single_action_worst_case(
    configurations: Iterable[Configuration], excluded: Iterable[Action] = ()
) -> int:
    """Meilleur pire cas atteignable par une unique action supplémentaire.

    Recalculée indépendamment de `Solver._best_single_move_worst_case`, en
    repartant uniquement de `partition_sizes` et de l'énumération complète
    des actions — sert d'oracle pour `next_mover_win_probability`.
    """

    configurations = tuple(configurations)
    total = len(configurations)
    if total <= 1:
        return total
    excluded = set(excluded)
    best = total
    for action, target in ALL_ACTIONS:
        if (action, target) in excluded:
            continue
        best = min(best, max(partition_sizes(configurations, action, target)))
        if best <= 1:
            return best
    return best


def next_mover_win_probability(
    configurations: Iterable[Configuration], action: str, target: str
) -> float:
    """Fraction des candidats pour lesquels, après une branche non gagnante
    de cette action, un unique coup supplémentaire suffirait à conclure —
    voir `Solver._augment_with_next_mover_risk` pour la version testée."""

    configurations = tuple(configurations)
    total = len(configurations)
    groups: dict[Hashable, list[Configuration]] = {}
    for configuration in configurations:
        groups.setdefault(
            action_outcome(configuration, action, target), []
        ).append(configuration)
    excluded = {(action, target)}
    wins = 0
    for branch in groups.values():
        size = len(branch)
        if size <= 1:
            continue
        if size <= 2:
            wins += size
            continue
        if best_single_action_worst_case(branch, excluded) <= 2:
            wins += size
    return wins / total
