from __future__ import annotations

import time
from collections.abc import Callable
from math import prod
from zlib import crc32

from .domain_filter import PlacementDomain
from .frequency import FrequencyMap, build_frequency_map
from .pieces import BLACK_BODY, DIAMOND, PIECES, placements
from .orapa_csp import propagate_orapa_csp, solve_orapa_csp
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
        opponent_starts: bool = False,
        exact_search_min_observations: int = 6,
        exact_time_budget: float = 45.0,
        propagate_time_budget: float = 10.0,
        propagate_time_budget_early: float = 10.0,
    ) -> None:
        self.include_diamond = include_diamond
        self.include_black_body = include_black_body
        # Coups et cases sont publics et illimités, mais chaque joueur n'a
        # que deux propositions de solution complète : si un coup laisse une
        # branche qu'un unique coup supplémentaire peut trancher, celui qui
        # joue ensuite en profite. Savoir qui a ouvert la partie est donc la
        # seule information de tour nécessaire pour déterminer à qui profite
        # un coup donné — voir `my_turn`.
        self.opponent_starts = opponent_starts
        self.exact_search_min_observations = exact_search_min_observations
        self.exact_time_budget = exact_time_budget
        self.propagate_time_budget = propagate_time_budget
        self.propagate_time_budget_early = propagate_time_budget_early
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
        self._frequency_map: FrequencyMap | None = None
        self._witness_cache: dict = {}
        # Signal d'annulation externe optionnel (p. ex. l'interruption d'un
        # thread d'interface graphique), vérifié en plus des échéances de
        # temps internes. Réglable à tout moment par l'appelant.
        self.cancelled: Callable[[], bool] | None = None
        self._raw_combination_count = prod(
            len(domain.placements) for domain in self._base_domains
        )

    @property
    def history(self) -> tuple[SolverObservation, ...]:
        return tuple(self._history)

    def _mover(self, index: int) -> str:
        """Qui a joué (ou jouera) le coup d'indice `index` de l'historique."""

        return "opponent" if (index % 2 == 0) == self.opponent_starts else "me"

    @property
    def my_turn(self) -> bool:
        """Vrai si c'est à nous de jouer le prochain coup.

        Sert à distinguer une recommandation qui nous est réellement
        destinée d'une simple évaluation du meilleur coup de l'adversaire —
        les deux se calculent de la même façon, seul le tour change qui en
        profite en premier.
        """

        return self._mover(len(self._history)) == "me"

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
    def _frequency_sample(self) -> tuple:
        return (
            self._result.configurations
            if self._result is not None
            else self._representative_candidates
        )

    @property
    def frequency_available(self) -> bool:
        """Vrai si des modèles globaux permettent une carte de fréquences."""

        return bool(self._frequency_sample)

    @property
    def frequency_map(self) -> FrequencyMap | None:
        """Carte d'occupation des cases sur les modèles globaux disponibles.

        Exacte quand l'énumération est exhaustive, sinon estimée sur
        l'échantillon de modèles vérifiés. Construite à la demande.
        """

        configurations = self._frequency_sample
        if not configurations:
            return None
        if self._frequency_map is None:
            self._frequency_map = build_frequency_map(
                configurations, exhaustive=self._result is not None
            )
        return self._frequency_map

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
        domains = self._base_domains if start_domains is None else start_domains
        self._result = None
        self._exact_solver = None
        self._strategy_solver = None
        self._representative_candidates = ()
        self._move_scores = []
        self._strategy_sample_count = 0
        self._frequency_map = None
        if not observations:
            self._filtered_domains = domains
            self._applied_relation_count = 0
            self._deferred_relation_count = 0
            self._raw_combination_count = prod(
                len(domain.placements) for domain in domains
            )
            return

        # En dessous du seuil de résolution exacte, on sait déjà que rien ne
        # sera prouvé : inutile de laisser le filtrage rapide consommer son
        # budget complet sur un indice isolé qui ne peut rien démontrer.
        propagate_budget = (
            self.propagate_time_budget
            if len(observations) >= self.exact_search_min_observations
            else self.propagate_time_budget_early
        )
        propagate_deadline = time.monotonic() + propagate_budget
        self._filtered_domains, applied, deferred = propagate_orapa_csp(
            domains,
            observations,
            witness_node_limit=2_000,
            seed=crc32(repr(observations).encode("utf-8")),
            deadline=propagate_deadline,
            cancelled=self.cancelled,
            witness_cache=self._witness_cache,
        )
        self._applied_relation_count = applied
        self._deferred_relation_count = deferred
        self._raw_combination_count = prod(
            len(domain.placements) for domain in self._filtered_domains
        )
        if len(observations) >= self.exact_search_min_observations:
            deadline = time.monotonic() + self.exact_time_budget
            model_result = solve_orapa_csp(
                self._filtered_domains,
                observations,
                model_limit=65,
                witness_node_limit=20_000,
                seed=crc32(repr(observations).encode("utf-8")),
                deadline=deadline,
                cancelled=self.cancelled,
                witness_cache=self._witness_cache,
            )
            self._filtered_domains = model_result.domains
            self._raw_combination_count = prod(
                len(domain.placements) for domain in self._filtered_domains
            )
            configurations = model_result.configurations
            exhausted = model_result.exhausted
            legal_count = model_result.visited_nodes
            if not configurations and not exhausted:
                # L'échéance a expiré sans preuve exhaustive, mais la
                # propagation a souvent déjà beaucoup réduit les domaines :
                # un tirage aléatoire y trouve parfois des témoins que la
                # recherche exacte n'a pas eu le temps de démontrer complets.
                bounded = search_configurations_bounded(
                    self._filtered_domains,
                    observations,
                    max_nodes=2_000,
                    seed=crc32(repr(observations).encode("utf-8")),
                )
                configurations = bounded.configurations
                exhausted = bounded.exhausted
                legal_count = bounded.legal_configuration_count
            self._apply_search_outcome(
                configurations, exhausted, legal_count, observations
            )
        else:
            bounded = search_configurations_bounded(
                self._filtered_domains,
                observations,
                max_nodes=500,
                seed=crc32(repr(observations).encode("utf-8")),
            )
            self._apply_search_outcome(
                bounded.configurations,
                bounded.exhausted,
                bounded.legal_configuration_count,
                observations,
            )

    def _apply_search_outcome(
        self,
        configurations,
        exhausted: bool,
        legal_count: int,
        observations: tuple[SolverObservation, ...],
    ) -> None:
        self._representative_candidates = configurations
        if exhausted:
            self._result = SearchResult(
                configurations, self._raw_combination_count, legal_count
            )
            self._exact_solver = Solver(configurations)
            for observation in observations:
                self._exact_solver.add_observation(observation)
            self._move_scores = self._exact_solver.rank_next_moves()
        elif configurations:
            self._strategy_solver = Solver(configurations)
            for observation in observations:
                self._strategy_solver.add_observation(observation)
            self._strategy_sample_count = len(configurations)
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
