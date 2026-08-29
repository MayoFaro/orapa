from __future__ import annotations

import time
from dataclasses import dataclass
from random import Random
from typing import Callable, Mapping

from .constraints import gems_are_compatible
from .domain_filter import PlacementDomain
from .ray_witness import (
    LocalHitIndex,
    PlacementCatalog,
    RayWitness,
    RayWitnessFinder,
    WitnessSearchStatus,
)
from .raytracer import Configuration, Gem
from .relational_csp import RelationalCSP, SupportConstraint
from .search import configuration_matches
from .solver import (
    CellContent,
    CellObservation,
    Observation,
    SolverObservation,
    gem_occupies_cell,
)

WitnessCache = dict[Observation, list[Mapping[str, tuple[Gem, ...]]]]


@dataclass(frozen=True)
class OrapaModelResult:
    domains: tuple[PlacementDomain, ...]
    configurations: tuple[Configuration, ...]
    exhausted: bool
    unknown_supports: bool
    visited_nodes: int


class _PairCompatibilityConstraint:
    """Compatibilité spatiale entre deux pièces, sur des indices de placement.

    Un support existe dès qu'une valeur compatible reste dans le domaine de
    l'autre pièce : le balayage s'arrête au premier partenaire trouvé. Les
    verdicts géométriques déjà connus sont réutilisés via un cache de rangée,
    et ``gems_are_compatible`` est lui-même mémoïsé.
    """

    def __init__(
        self,
        scope: tuple[str, str],
        left_gems: tuple[Gem, ...],
        right_gems: tuple[Gem, ...],
    ) -> None:
        self.scope = scope
        self._left_gems = left_gems
        self._right_gems = right_gems
        # value -> masque partiel des partenaires déjà classés compatibles
        self._left_known: dict[int, int] = {}
        self._right_known: dict[int, int] = {}

    def _supported(
        self,
        value: int,
        own_gems: tuple[Gem, ...],
        other_gems: tuple[Gem, ...],
        known: dict[int, int],
        other_values: tuple[int, ...],
    ) -> bool:
        compatible = known.get(value, 0)
        own_gem = own_gems[value]
        for other in other_values:
            bit = 1 << other
            if compatible & bit:
                return True
            if gems_are_compatible(own_gem, other_gems[other]):
                known[value] = compatible | bit
                return True
        return False

    def has_support(
        self,
        variable: str,
        value: int,
        domains: Mapping[str, tuple[int, ...]],
    ) -> bool:
        left, right = self.scope
        if variable == left:
            return self._supported(
                value, self._left_gems, self._right_gems,
                self._left_known, domains[right],
            )
        return self._supported(
            value, self._right_gems, self._left_gems,
            self._right_known, domains[left],
        )


class _AllowedValuesConstraint:
    """Contrainte unaire : la valeur doit appartenir à un ensemble fixe."""

    def __init__(self, scope: tuple[str], allowed: frozenset[int]) -> None:
        self.scope = scope
        self._allowed = allowed

    def has_support(
        self,
        variable: str,
        value: int,
        domains: Mapping[str, tuple[int, ...]],
    ) -> bool:
        return value in self._allowed


class _AtLeastOneOccupiesConstraint:
    """Au moins une des pièces blanches occupe la case examinée."""

    def __init__(
        self, scope: tuple[str, ...], occupying: Mapping[str, frozenset[int]]
    ) -> None:
        self.scope = scope
        self._occupying = dict(occupying)

    def has_support(
        self,
        variable: str,
        value: int,
        domains: Mapping[str, tuple[int, ...]],
    ) -> bool:
        if value in self._occupying[variable]:
            return True
        for other in self.scope:
            if other == variable:
                continue
            if any(candidate in self._occupying[other] for candidate in domains[other]):
                return True
        return False


class _RaySupportOracle:
    def __init__(
        self,
        finder: RayWitnessFinder,
        catalog: PlacementCatalog,
        *,
        max_nodes: int,
        cancelled: Callable[[], bool] | None = None,
    ) -> None:
        self.finder = finder
        self.catalog = catalog
        self.max_nodes = max_nodes
        self.cancelled = cancelled
        self.witnesses: list[RayWitness] = []
        self.unknown = False

    def __call__(
        self,
        variable: str,
        value: int,
        domains: Mapping[str, tuple[int, ...]],
    ) -> bool:
        domain_masks = self.catalog.masks_from_index_domains(domains)
        piece_index = self.catalog.piece_index(variable)
        value_bit = 1 << value
        for witness in self.witnesses:
            if not witness.allowed_masks[piece_index] & value_bit:
                continue
            if all(
                witness_mask & domain_mask
                for witness_mask, domain_mask in zip(
                    witness.allowed_masks, domain_masks
                )
            ):
                return True

        search_masks = list(domain_masks)
        search_masks[piece_index] = domain_masks[piece_index] & value_bit
        result = self.finder.search_masks(
            tuple(search_masks),
            max_nodes=self.max_nodes,
            cancelled=self.cancelled,
        )
        if result.status == WitnessSearchStatus.FOUND:
            assert result.witness is not None
            self.witnesses.append(result.witness)
            return True
        if result.status == WitnessSearchStatus.UNKNOWN:
            self.unknown = True
            return True
        return False


def _add_spatial_constraints(
    problem: RelationalCSP[str, int], catalog: PlacementCatalog
) -> None:
    for left_index in range(len(catalog.names)):
        for right_index in range(left_index + 1, len(catalog.names)):
            problem.add_constraint(
                _PairCompatibilityConstraint(
                    (catalog.names[left_index], catalog.names[right_index]),
                    catalog.placements[left_index],
                    catalog.placements[right_index],
                )
            )


_CELL_CONTENT_PIECES = {
    CellContent.RED: ("red",),
    CellContent.YELLOW: ("yellow",),
    CellContent.BLUE: ("blue",),
    CellContent.DIAMOND: ("diamond",),
    CellContent.BLACK_BODY: ("black_body",),
    CellContent.WHITE: ("white_diamond", "white_triangle"),
}


def _add_cell_constraint(
    problem: RelationalCSP[str, int],
    catalog: PlacementCatalog,
    observation: CellObservation,
) -> None:
    def occupying(name: str) -> frozenset[int]:
        piece_index = catalog.piece_index(name)
        return frozenset(
            value_index
            for value_index, gem in enumerate(catalog.placements[piece_index])
            if gem_occupies_cell(gem, observation.row, observation.column)
        )

    def not_occupying(name: str) -> frozenset[int]:
        piece_index = catalog.piece_index(name)
        full = range(len(catalog.placements[piece_index]))
        return frozenset(full) - occupying(name)

    if observation.content == CellContent.NOTHING:
        for name in catalog.names:
            problem.add_constraint(
                _AllowedValuesConstraint((name,), not_occupying(name))
            )
        return

    target_names = tuple(
        name
        for name in _CELL_CONTENT_PIECES[observation.content]
        if name in catalog.names
    )
    if not target_names:
        problem.add_constraint(
            _AllowedValuesConstraint((catalog.names[0],), frozenset())
        )
        return

    for name in catalog.names:
        if name not in target_names:
            problem.add_constraint(
                _AllowedValuesConstraint((name,), not_occupying(name))
            )

    if observation.content == CellContent.WHITE:
        problem.add_constraint(
            _AtLeastOneOccupiesConstraint(
                target_names, {name: occupying(name) for name in target_names}
            )
        )
    else:
        name = target_names[0]
        problem.add_constraint(
            _AllowedValuesConstraint((name,), occupying(name))
        )


@dataclass
class _BuiltProblem:
    problem: RelationalCSP[str, int]
    catalog: PlacementCatalog
    ray_oracles: list[tuple[Observation, "_RaySupportOracle"]]


def _build_problem(
    domains: tuple[PlacementDomain, ...],
    observations: tuple[SolverObservation, ...],
    *,
    witness_node_limit: int,
    seed: int,
    cancelled: Callable[[], bool] | None,
    witness_cache: WitnessCache | None,
) -> _BuiltProblem:
    random = Random(seed)
    shuffled_domains = {}
    for domain in domains:
        values = list(domain.placements)
        random.shuffle(values)
        shuffled_domains[domain.piece_name] = tuple(values)
    catalog = PlacementCatalog(shuffled_domains)
    hit_index = LocalHitIndex(catalog)

    problem = RelationalCSP[str, int]()
    for name in catalog.names:
        problem.add_variable(
            name, range(len(catalog.placements[catalog.piece_index(name)]))
        )
    _add_spatial_constraints(problem, catalog)

    ray_oracles: list[tuple[Observation, _RaySupportOracle]] = []
    for observation in observations:
        if isinstance(observation, CellObservation):
            _add_cell_constraint(problem, catalog, observation)
            continue
        oracle = _RaySupportOracle(
            RayWitnessFinder(
                catalog,
                observation.entry,
                observation.outcome,
                hit_index=hit_index,
            ),
            catalog,
            max_nodes=witness_node_limit,
            cancelled=cancelled,
        )
        if witness_cache is not None:
            for portable in witness_cache.get(observation, ()):
                oracle.witnesses.append(
                    RayWitness(
                        catalog.masks_from_known_gems(portable),
                        (),
                        observation.exit_point,
                        observation.absorbed,
                    )
                )
        ray_oracles.append((observation, oracle))
        problem.add_constraint(SupportConstraint(catalog.names, oracle))

    return _BuiltProblem(problem, catalog, ray_oracles)


def _save_witness_cache(built: _BuiltProblem, witness_cache: WitnessCache | None) -> None:
    if witness_cache is None:
        return
    for observation, oracle in built.ray_oracles:
        witness_cache[observation] = [
            {
                name: built.catalog.values_from_mask(
                    name, witness.allowed_masks[built.catalog.piece_index(name)]
                )
                for name in built.catalog.names
            }
            for witness in oracle.witnesses
        ]


def _domains_from_index_domains(
    catalog: PlacementCatalog, index_domains: Mapping[str, tuple[int, ...]]
) -> tuple[PlacementDomain, ...]:
    return tuple(
        PlacementDomain(
            name,
            tuple(
                catalog.placements[catalog.piece_index(name)][value_index]
                for value_index in index_domains[name]
            ),
        )
        for name in catalog.names
    )


def propagate_orapa_csp(
    domains: tuple[PlacementDomain, ...],
    observations: tuple[SolverObservation, ...],
    *,
    witness_node_limit: int = 2_000,
    seed: int = 0,
    deadline: float | None = None,
    witness_cache: WitnessCache | None = None,
) -> tuple[tuple[PlacementDomain, ...], int, int]:
    """Réduit les domaines par cohérence d'arc seule, sans chercher de modèle.

    Contrairement au filtre heuristique de ``relational_filter.py``, chaque
    contrainte de rayon porte ici sur *toutes* les pièces à la fois (via le
    même mécanisme de témoins que :func:`solve_orapa_csp`) : une pièce d'une
    autre couleur qui bloquerait géométriquement un trajet est donc exclue
    elle aussi, pas seulement les pièces dont la couleur explique le résultat
    observé. C'est nettement moins cher qu'une résolution complète puisque
    aucune recherche de modèle n'est tentée — seule la cohérence d'arc est
    appliquée.

    Retourne les domaines réduits, ainsi que le nombre d'indices d'onde dont
    la contrainte a été pleinement vérifiée (``applied``) et celui dont au
    moins une recherche de témoin a atteint sa limite sans conclure
    (``deferred``).
    """

    cancelled = (
        None if deadline is None else (lambda: time.monotonic() >= deadline)
    )

    if any(not domain.placements for domain in domains):
        return domains, 0, 0

    built = _build_problem(
        domains,
        observations,
        witness_node_limit=witness_node_limit,
        seed=seed,
        cancelled=cancelled,
        witness_cache=witness_cache,
    )
    propagated = built.problem.propagate()
    _save_witness_cache(built, witness_cache)

    if not propagated.consistent:
        empty = tuple(PlacementDomain(name, ()) for name in built.catalog.names)
        deferred = sum(1 for _, oracle in built.ray_oracles if oracle.unknown)
        return empty, len(built.ray_oracles) - deferred, deferred

    reduced = _domains_from_index_domains(built.catalog, propagated.domains)
    deferred = sum(1 for _, oracle in built.ray_oracles if oracle.unknown)
    return reduced, len(built.ray_oracles) - deferred, deferred


def solve_orapa_csp(
    domains: tuple[PlacementDomain, ...],
    observations: tuple[SolverObservation, ...],
    *,
    model_limit: int = 257,
    witness_node_limit: int = 20_000,
    seed: int = 0,
    deadline: float | None = None,
    witness_cache: WitnessCache | None = None,
) -> OrapaModelResult:
    """Résout les domaines avec des contraintes globales de rayon paresseuses.

    Le CSP travaille sur des indices de placement entiers ; les ``Gem`` ne sont
    reconstruits qu'aux frontières (résultat et vérification finale).

    ``deadline``, s'il est fourni, est une valeur ``time.monotonic()`` au-delà
    de laquelle chaque recherche de témoin abandonne et répond ``UNKNOWN``
    (donc suppose la valeur supportée) plutôt que de continuer à explorer.
    Cela borne le temps total de la résolution sans jamais produire de faux
    négatif : seule la vérification finale de chaque modèle décide s'il est
    conservé.

    ``witness_cache``, s'il est fourni, est mis à jour en place : les témoins
    trouvés sont conservés sous une forme indépendante du catalogue (donc
    réutilisable même si l'ordre de tirage change d'un appel à l'autre), et
    ceux déjà présents pour une observation sont rejoués avant toute nouvelle
    recherche. Un appelant qui refait successivement des résolutions sur des
    domaines de plus en plus réduits (au fil d'une partie) évite ainsi de
    redémontrer les mêmes témoins à chaque nouvel indice.
    """

    cancelled = (
        None if deadline is None else (lambda: time.monotonic() >= deadline)
    )

    if any(not domain.placements for domain in domains):
        return OrapaModelResult(domains, (), True, False, 0)

    built = _build_problem(
        domains,
        observations,
        witness_node_limit=witness_node_limit,
        seed=seed,
        cancelled=cancelled,
        witness_cache=witness_cache,
    )
    problem, catalog, ray_oracles = built.problem, built.catalog, built.ray_oracles

    propagated = problem.propagate()
    propagated_domains = _domains_from_index_domains(catalog, propagated.domains)
    if not propagated.consistent:
        _save_witness_cache(built, witness_cache)
        return OrapaModelResult(
            propagated_domains,
            (),
            True,
            any(oracle.unknown for _, oracle in ray_oracles),
            0,
        )

    searched = problem.solve(limit=model_limit)
    configurations = []
    for model in searched.models:
        configuration = Configuration(
            tuple(
                catalog.placements[catalog.piece_index(name)][model[name]]
                for name in catalog.names
            )
        )
        if configuration_matches(configuration, observations):
            configurations.append(configuration)
    unknown = any(oracle.unknown for _, oracle in ray_oracles)
    exhausted = searched.exhausted and not unknown
    _save_witness_cache(built, witness_cache)
    return OrapaModelResult(
        propagated_domains,
        tuple(configurations),
        exhausted,
        unknown,
        searched.visited_nodes,
    )


__all__ = ["OrapaModelResult", "propagate_orapa_csp", "solve_orapa_csp"]
