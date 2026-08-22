from __future__ import annotations

from math import prod

from .domain_filter import (
    PlacementDomain, apply_cell_observation, apply_exact_observation_filters,
)
from .pieces import BLACK_BODY, DIAMOND, PIECES, placements
from .search import SearchResult, search_configurations
from .solver import CellContent, CellObservation, MoveScore, Solver, SolverObservation


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
        self._move_scores: list[MoveScore] = []
        self._strategy_sample_count = 0
        self._promising_cell_actions: list[tuple[CellObservation, int]] = []
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
    def promising_cell_actions(self) -> tuple[tuple[CellObservation, int], ...]:
        return tuple(self._promising_cell_actions)

    def _recompute(self) -> None:
        observations = tuple(self._history)
        self._filtered_domains = apply_exact_observation_filters(
            self._base_domains, observations
        )
        self._raw_combination_count = prod(
            len(domain.placements) for domain in self._filtered_domains
        )
        self._result = None
        self._exact_solver = None
        self._move_scores = []
        self._strategy_sample_count = 0
        self._promising_cell_actions = []
        if self._raw_combination_count <= self.exact_search_limit:
            self._result = search_configurations(
                self._filtered_domains,
                observations,
                max_raw_combinations=self.exact_search_limit,
            )
            self._exact_solver = Solver(self._result.configurations)
            for observation in observations:
                self._exact_solver.add_observation(observation)
            self._move_scores = self._exact_solver.rank_next_moves()
        elif observations:
            # Même sans catalogue exact, repère les réponses qui ramèneraient
            # immédiatement l'espace sous le seuil de résolution exhaustive.
            trigger_limit = int(self.exact_search_limit * 1.1)
            used_cells = {
                observation.cell for observation in observations
                if isinstance(observation, CellObservation)
            }
            contents = list(CellContent)
            if not self.include_diamond:
                contents.remove(CellContent.DIAMOND)
            if not self.include_black_body:
                contents.remove(CellContent.BLACK_BODY)
            for row in "ABCDEFGH":
                for column in range(1, 11):
                    if f"{row}{column}" in used_cells:
                        continue
                    for content in contents:
                        observation = CellObservation(row, column, content)
                        branch = apply_cell_observation(
                            self._filtered_domains, observation
                        )
                        branch_size = prod(
                            len(domain.placements) for domain in branch
                        )
                        if 0 < branch_size <= trigger_limit:
                            self._promising_cell_actions.append(
                                (observation, branch_size)
                            )
            self._promising_cell_actions.sort(
                key=lambda item: (item[0].cell, item[1], item[0].content.value)
            )

    def add_observation(self, observation: SolverObservation) -> None:
        self._history.append(observation)
        self._recompute()

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
        if self._exact_solver is None:
            return []
        if include_used:
            return self._exact_solver.rank_next_moves(include_used=True)
        return list(self._move_scores)

    def suspect_observations(self) -> list[tuple[int, int]]:
        if self._exact_solver is None:
            return []
        return self._exact_solver.suspect_observations()
