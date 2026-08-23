from __future__ import annotations

from dataclasses import dataclass
from random import Random
from typing import Mapping

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
from .relational_csp import PredicateConstraint, RelationalCSP, SupportConstraint
from .search import configuration_matches
from .solver import (
    CellContent,
    CellObservation,
    Observation,
    SolverObservation,
    gem_occupies_cell,
)


@dataclass(frozen=True)
class OrapaModelResult:
    domains: tuple[PlacementDomain, ...]
    configurations: tuple[Configuration, ...]
    exhausted: bool
    unknown_supports: bool
    visited_nodes: int


class _RaySupportOracle:
    def __init__(
        self,
        finder: RayWitnessFinder,
        catalog: PlacementCatalog,
        *,
        max_nodes: int,
    ) -> None:
        self.finder = finder
        self.catalog = catalog
        self.max_nodes = max_nodes
        self.witnesses: list[RayWitness] = []
        self.unknown = False

    def __call__(
        self,
        variable: str,
        value: Gem,
        domains: Mapping[str, tuple[Gem, ...]],
    ) -> bool:
        domain_masks = self.catalog.masks_from_domains(domains)
        piece_index = self.catalog.piece_index(variable)
        value_bit = 1 << self.catalog.value_index(variable, value)
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

        result = self.finder.find_support(
            variable, value, domains, max_nodes=self.max_nodes
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
    problem: RelationalCSP[str, Gem], domains: tuple[PlacementDomain, ...]
) -> None:
    names = tuple(domain.piece_name for domain in domains)
    for left in range(len(names)):
        for right in range(left + 1, len(names)):
            problem.add_constraint(
                PredicateConstraint(
                    (names[left], names[right]), gems_are_compatible
                )
            )


def _add_cell_constraint(
    problem: RelationalCSP[str, Gem],
    names: tuple[str, ...],
    observation: CellObservation,
) -> None:
    matching = {
        CellContent.RED: ("red",),
        CellContent.YELLOW: ("yellow",),
        CellContent.BLUE: ("blue",),
        CellContent.DIAMOND: ("diamond",),
        CellContent.BLACK_BODY: ("black_body",),
        CellContent.WHITE: ("white_diamond", "white_triangle"),
    }

    def occupies(gem: Gem) -> bool:
        return gem_occupies_cell(gem, observation.row, observation.column)

    if observation.content == CellContent.NOTHING:
        for name in names:
            problem.add_constraint(PredicateConstraint((name,), lambda gem: not occupies(gem)))
        return

    target_names = tuple(name for name in matching[observation.content] if name in names)
    if not target_names:
        problem.add_constraint(
            PredicateConstraint((names[0],), lambda _gem: False)
        )
        return
    for name in names:
        if name not in target_names:
            problem.add_constraint(PredicateConstraint((name,), lambda gem: not occupies(gem)))
    if observation.content == CellContent.WHITE:
        problem.add_constraint(
            PredicateConstraint(
                target_names,
                lambda *gems: any(occupies(gem) for gem in gems),
            )
        )
    else:
        problem.add_constraint(PredicateConstraint(target_names, lambda gem: occupies(gem)))


def solve_orapa_csp(
    domains: tuple[PlacementDomain, ...],
    observations: tuple[SolverObservation, ...],
    *,
    model_limit: int = 257,
    witness_node_limit: int = 20_000,
    seed: int = 0,
) -> OrapaModelResult:
    """Résout les domaines avec des contraintes globales de rayon paresseuses."""

    if any(not domain.placements for domain in domains):
        return OrapaModelResult(domains, (), True, False, 0)
    random = Random(seed)
    shuffled_domains = {}
    for domain in domains:
        values = list(domain.placements)
        random.shuffle(values)
        shuffled_domains[domain.piece_name] = tuple(values)
    catalog = PlacementCatalog(shuffled_domains)
    hit_index = LocalHitIndex(catalog)
    problem = RelationalCSP[str, Gem]()
    for domain in domains:
        problem.add_variable(domain.piece_name, domain.placements)
    _add_spatial_constraints(problem, domains)

    ray_oracles: list[_RaySupportOracle] = []
    for observation in observations:
        if isinstance(observation, CellObservation):
            _add_cell_constraint(problem, catalog.names, observation)
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
        )
        ray_oracles.append(oracle)
        problem.add_constraint(SupportConstraint(catalog.names, oracle))

    propagated = problem.propagate()
    propagated_domains = tuple(
        PlacementDomain(name, tuple(propagated.domains[name]))
        for name in catalog.names
    )
    if not propagated.consistent:
        return OrapaModelResult(
            propagated_domains,
            (),
            True,
            any(oracle.unknown for oracle in ray_oracles),
            0,
        )

    searched = problem.solve(limit=model_limit)
    configurations = []
    for model in searched.models:
        configuration = Configuration(
            tuple(model[name] for name in catalog.names)
        )
        if configuration_matches(configuration, observations):
            configurations.append(configuration)
    unknown = any(oracle.unknown for oracle in ray_oracles)
    exhausted = searched.exhausted and not unknown
    return OrapaModelResult(
        propagated_domains,
        tuple(configurations),
        exhausted,
        unknown,
        searched.visited_nodes,
    )


__all__ = ["OrapaModelResult", "solve_orapa_csp"]
