from __future__ import annotations

from math import prod
from zlib import crc32

from .domain_filter import PlacementDomain
from .pieces import BLACK_BODY, DIAMOND, PIECES, placements
from .orapa_csp import solve_orapa_csp
from .relational_filter import apply_relational_filters
from .search import (
    SearchResult, search_configurations_bounded,
)
from .solver import MoveScore, Solver, SolverObservation


class ProgressiveSolver:
    """Passe automatiquement des domaines symboliques à la recherche exacte."""

    def __init__(
        self,
        *,
        include_diamond: bool = False,
        include_black_body: bool = False,
        exact_search_limit: int = 1_000_000,
    ) -> None:
        self.include_diamond = include_diamond
        self.include_black_body = include_black_body
        self.exact_search_limit = exact_search_limit
        definitions = PIECES
        if include_diamond:
            definitions += (DIAMOND,)
        if include_black_body:
            definitions += (BLACK_BODY,)
        self._base_domains = tuple(
            PlacementDomain(piece.name, placements(piece)) for piece in definitions
        )
        self._history: list[SolverObservation] = []
        self._filtered_domains = self._base_domains
        self._result: SearchResult | None = None
        self._exact_solver: Solver | None = None
        self._strategy_solver: Solver | None = None
        self._representative_candidates = ()
        self._move_scores: list[MoveScore] = []
        self._strategy_sample_count = 0
        self._applied_relation_count = 0
        self._deferred_relation_count = 0
        self._raw_combination_count = prod(
            len(domain.placements) for domain in self._base_domains
        )

    @property
    def history(self) -> tuple[SolverObservation, ...]:
        return tuple(self._history)

    @property
    def raw_combination_count(self) -> int:
        return self._raw_combination_count

    @property
    def exact(self) -> bool:
        return self._result is not None

    @property
    def candidate_count(self) -> int | None:
        return len(self._result.configurations) if self._result else None

    @property
    def candidates(self):
        return self._result.configurations if self._result else ()

    @property
    def representative_candidates(self):
        return self._representative_candidates

    @property
    def recommendation_exact(self) -> bool:
        return self._result is not None

    @property
    def certain_gems(self):
        if self._result is not None:
            if self._exact_solver is None:
                return ()
            return self._exact_solver.certain_gems
        return tuple(
            domain.placements[0]
            for domain in self._filtered_domains
            if len(domain.placements) == 1
        )

    @property
    def domain_sizes(self) -> dict[str, int]:
        return {
            domain.piece_name: len(domain.placements)
            for domain in self._filtered_domains
        }

    @property
    def legal_configuration_count(self) -> int | None:
        return self._result.legal_configuration_count if self._result else None

    @property
    def strategy_sample_count(self) -> int:
        return self._strategy_sample_count

    @property
    def applied_relation_count(self) -> int:
        return self._applied_relation_count

    @property
    def deferred_relation_count(self) -> int:
        return self._deferred_relation_count

    def _recompute(
        self, start_domains: tuple[PlacementDomain, ...] | None = None
    ) -> None:
        observations = tuple(self._history)
        relational = apply_relational_filters(
            self._base_domains if start_domains is None else start_domains,
            observations,
            max_relation_combinations=max(2_000_000, self.exact_search_limit),
        )
        self._filtered_domains = relational.domains
        self._applied_relation_count = relational.applied_relations
        self._deferred_relation_count = relational.deferred_relations
        self._raw_combination_count = prod(
            len(domain.placements) for domain in self._filtered_domains
        )
        self._result = None
        self._exact_solver = None
        self._strategy_solver = None
        self._representative_candidates = ()
        self._move_scores = []
        self._strategy_sample_count = 0
        if observations and self._raw_combination_count <= 150_000_000:
            model_result = solve_orapa_csp(
                self._filtered_domains,
                observations,
                model_limit=65,
                witness_node_limit=(
                    1_000 if self._raw_combination_count > 5_000_000 else 20_000
                ),
                seed=crc32(repr(observations).encode("utf-8")),
            )
            self._filtered_domains = model_result.domains
            self._raw_combination_count = prod(
                len(domain.placements) for domain in self._filtered_domains
            )
            self._representative_candidates = model_result.configurations
            if model_result.exhausted:
                self._result = SearchResult(
                    model_result.configurations,
                    self._raw_combination_count,
                    model_result.visited_nodes,
                )
                self._exact_solver = Solver(model_result.configurations)
                for observation in observations:
                    self._exact_solver.add_observation(observation)
                self._move_scores = self._exact_solver.rank_next_moves()
            elif model_result.configurations:
                self._strategy_solver = Solver(model_result.configurations)
                for observation in observations:
                    self._strategy_solver.add_observation(observation)
                self._strategy_sample_count = len(model_result.configurations)
                self._move_scores = self._strategy_solver.rank_next_moves()
        elif observations:
            bounded = search_configurations_bounded(
                self._filtered_domains,
                observations,
                max_nodes=500,
                seed=crc32(repr(observations).encode("utf-8")),
            )
            self._representative_candidates = bounded.configurations
            if bounded.exhausted:
                self._result = SearchResult(
                    bounded.configurations,
                    self._raw_combination_count,
                    bounded.legal_configuration_count,
                )
                self._exact_solver = Solver(bounded.configurations)
                for observation in observations:
                    self._exact_solver.add_observation(observation)
                self._move_scores = self._exact_solver.rank_next_moves()
            elif bounded.configurations:
                self._strategy_solver = Solver(bounded.configurations)
                for observation in observations:
                    self._strategy_solver.add_observation(observation)
                self._strategy_sample_count = len(bounded.configurations)
                self._move_scores = self._strategy_solver.rank_next_moves()

    def add_observation(self, observation: SolverObservation) -> None:
        previous_domains = self._filtered_domains
        self._history.append(observation)
        self._recompute(previous_domains)

    def add_observations(self, observations: tuple[SolverObservation, ...]) -> None:
        self._history.extend(observations)
        self._recompute()

    def remove_observation(self, index: int) -> SolverObservation:
        observation = self._history.pop(index)
        self._recompute()
        return observation

    def replace_observation(self, index: int, observation: SolverObservation) -> None:
        self._history[index] = observation
        self._recompute()

    def clear(self) -> None:
        self._history.clear()
        self._recompute()

    def rank_next_moves(self, include_used: bool = False) -> list[MoveScore]:
        solver = self._exact_solver or self._strategy_solver
        if solver is None:
            return []
        if include_used:
            return solver.rank_next_moves(include_used=True)
        return list(self._move_scores)

    def suspect_observations(self) -> list[tuple[int, int]]:
        if self._exact_solver is None:
            return []
        return self._exact_solver.suspect_observations()
