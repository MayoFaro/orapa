from __future__ import annotations

from dataclasses import dataclass, replace
from enum import Enum
from math import log2
from typing import Iterable

from .border import ALL_BORDER_POINTS, normalize_border_point
from .colors import RayColor
from .constraints import polygons_have_interior_overlap
from .geometry import doubled_polygon
from .raytracer import Configuration, RayOutcome, simulate_ray

# Nombre de candidats en-dessous duquel `rank_next_moves` réévalue, pour le
# coup recommandé, chacune de ses branches non gagnantes afin de repérer si
# un coup adverse pourrait y trancher immédiatement (voir
# `_augment_with_next_mover_risk`). Ce calcul supplémentaire repasse par
# tous les coups possibles sur chaque branche : au-delà de quelques
# dizaines de candidats, il devient coûteux pour un intérêt stratégique qui,
# de toute façon, ne se pose vraiment qu'en toute fin de partie, quand peu
# de candidats subsistent.
ENDGAME_MAX_CANDIDATES_FOR_FOLLOWUP = 60

# Nombre de coups vérifiés en détail lors du classement tenant compte du
# risque adverse (voir `rank_next_moves`). Le calcul complet de
# `next_mover_win_probability` coûte trop cher pour tous les coups possibles
# à la fois (jusqu'à ~25s mesurés à la limite du seuil ci-dessus) ; seuls les
# coups les mieux classés par une estimation bon marché sont donc vérifiés
# exactement.
ENDGAME_RISK_SHORTLIST_SIZE = 10


@dataclass(frozen=True)
class Observation:
    entry: str
    exit_point: str | None = None
    color: RayColor | None = None
    absorbed: bool = False

    def __post_init__(self) -> None:
        object.__setattr__(self, "entry", normalize_border_point(self.entry))
        if self.absorbed:
            object.__setattr__(self, "exit_point", None)
            object.__setattr__(self, "color", None)
            return
        if self.exit_point is None or self.color is None:
            raise ValueError("Une onde non absorbée exige une sortie et une couleur")
        object.__setattr__(self, "exit_point", normalize_border_point(self.exit_point))
        object.__setattr__(self, "color", RayColor(self.color))

    @property
    def outcome(self) -> RayOutcome:
        return RayOutcome(self.exit_point, self.color, self.absorbed)


class CellContent(str, Enum):
    NOTHING = "nothing"
    WHITE = "white"
    RED = "red"
    YELLOW = "yellow"
    BLUE = "blue"
    DIAMOND = "diamond"
    BLACK_BODY = "black_body"


@dataclass(frozen=True)
class CellObservation:
    row: str
    column: int
    content: CellContent | str

    def __post_init__(self) -> None:
        row = self.row.upper()
        if row not in "ABCDEFGH" or not 1 <= self.column <= 10:
            raise ValueError("Case inconnue")
        object.__setattr__(self, "row", row)
        object.__setattr__(self, "content", CellContent(self.content))

    @property
    def cell(self) -> str:
        return f"{self.row}{self.column}"


SolverObservation = Observation | CellObservation


class _InvalidRayOutcome(str, Enum):
    INVALID = "invalid_ray"


def gem_occupies_cell(gem, row: str, column: int) -> bool:
    y = ord(row.upper()) - ord("A")
    cell = doubled_polygon(
        (column - 1, y), (column, y), (column, y + 1), (column - 1, y + 1)
    )
    return polygons_have_interior_overlap(gem.polygon, cell)


def configuration_cell_content(
    configuration: Configuration, row: str, column: int
) -> CellContent:
    occupying = [
        gem for gem in configuration.gems if gem_occupies_cell(gem, row, column)
    ]
    if not occupying:
        return CellContent.NOTHING
    if len(occupying) != 1:
        raise RuntimeError("Plusieurs pierres occupent la même case")
    gem = occupying[0]
    if gem.name == "diamond":
        return CellContent.DIAMOND
    if gem.name == "black_body":
        return CellContent.BLACK_BODY
    return CellContent(gem.color.value)


@dataclass(frozen=True)
class MoveScore:
    action: str
    target: str
    entropy: float
    worst_case: int
    # Taille de la branche la plus favorable — 1 signifie qu'un des résultats
    # possibles de ce coup donne déjà, à lui seul, la solution complète.
    best_case: int
    # Fraction des candidats actuels dont le résultat de ce coup tomberait
    # dans une branche de taille 1, c'est-à-dire la probabilité (sous
    # l'hypothèse usuelle d'équiprobabilité des candidats) que ce coup
    # résolve déjà tout, sans attendre le coup suivant.
    win_probability: float
    expected_remaining: float
    outcome_count: int
    # Parmi les résultats de ce coup qui NE donnent PAS déjà la solution,
    # fraction des candidats actuels pour lesquels celui qui joue juste
    # après (nous ou l'adversaire selon le tour) dispose d'un coup capable
    # de conclure à son tour — soit parce que la branche ne laisse plus que
    # deux candidats (sa marge de propositions suffit alors), soit parce
    # qu'un unique coup supplémentaire la tranche totalement. None hors du
    # régime de fin de partie où ce calcul est mené (voir
    # `ENDGAME_MAX_CANDIDATES_FOR_FOLLOWUP`) — évalué sur TOUTES les
    # branches, pas seulement la plus grande, car rien ne garantit que la
    # branche dangereuse soit la plus probable.
    next_mover_win_probability: float | None = None

    @property
    def entry(self) -> str | None:
        return self.target if self.action == "wave" else None

    @property
    def label(self) -> str:
        return (
            f"Onde depuis {self.target}"
            if self.action == "wave"
            else f"Examiner la case {self.target}"
        )


class Solver:
    """Filtre un catalogue de grilles et classe les prochaines ondes."""

    def __init__(self, configurations: Iterable[Configuration]) -> None:
        self._all = tuple(configurations)
        self._history: list[SolverObservation] = []
        self._candidate_ids = list(range(len(self._all)))
        self._outcome_cache: dict[
            tuple[int, str], RayOutcome | _InvalidRayOutcome
        ] = {}

    @property
    def history(self) -> tuple[SolverObservation, ...]:
        return tuple(self._history)

    @property
    def candidate_count(self) -> int:
        return len(self._candidate_ids)

    @property
    def candidates(self) -> tuple[Configuration, ...]:
        return tuple(self._all[index] for index in self._candidate_ids)

    @property
    def certain_gems(self):
        candidates = self.candidates
        if not candidates:
            return ()
        certain = []
        names = {gem.name for gem in candidates[0].gems}
        for name in names:
            placements = [
                next(gem for gem in configuration.gems if gem.name == name)
                for configuration in candidates
            ]
            if all(gem == placements[0] for gem in placements[1:]):
                certain.append(placements[0])
        return tuple(sorted(certain, key=lambda gem: gem.name))

    def _outcome(
        self, configuration_id: int, entry: str
    ) -> RayOutcome | _InvalidRayOutcome:
        key = (configuration_id, entry)
        if key not in self._outcome_cache:
            try:
                trace = simulate_ray(self._all[configuration_id], entry)
            except RuntimeError:
                self._outcome_cache[key] = _InvalidRayOutcome.INVALID
            else:
                self._outcome_cache[key] = trace.outcome
        return self._outcome_cache[key]

    def _recompute(self) -> None:
        candidates = range(len(self._all))
        for observation in self._history:
            if isinstance(observation, Observation):
                candidates = [
                    index for index in candidates
                    if self._outcome(index, observation.entry) == observation.outcome
                ]
            else:
                candidates = [
                    index for index in candidates
                    if configuration_cell_content(
                        self._all[index], observation.row, observation.column
                    ) == observation.content
                ]
        self._candidate_ids = list(candidates)

    def add_observation(self, observation: SolverObservation) -> None:
        self._history.append(observation)
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

    def suspect_observations(self) -> list[tuple[int, int]]:
        """Retourne (index, candidats restaurés) par retrait d'une saisie."""

        if self.candidate_count:
            return []
        original = list(self._history)
        suspects: list[tuple[int, int]] = []
        for index in range(len(original)):
            self._history = original[:index] + original[index + 1 :]
            self._recompute()
            if self.candidate_count:
                suspects.append((index, self.candidate_count))
        self._history = original
        self._recompute()
        return sorted(suspects, key=lambda item: item[1], reverse=True)

    def _best_single_move_worst_case(
        self,
        candidate_ids: list[int],
        excluded_waves: frozenset[str],
        excluded_cells: frozenset[str],
    ) -> int:
        """Meilleur pire cas atteignable par un unique coup sur ce sous-ensemble.

        Sert à estimer, pour une branche donnée d'un coup, si qui joue
        ensuite dispose d'un coup capable de trancher immédiatement ce qui
        reste — voir `_augment_with_next_mover_risk`.
        """

        total = len(candidate_ids)
        if total <= 1:
            return total
        best = total
        for entry in ALL_BORDER_POINTS:
            if entry in excluded_waves:
                continue
            counts: dict[object, int] = {}
            for index in candidate_ids:
                outcome = self._outcome(index, entry)
                counts[outcome] = counts.get(outcome, 0) + 1
            best = min(best, max(counts.values()))
            if best <= 1:
                return best
        for row in "ABCDEFGH":
            for column in range(1, 11):
                cell = f"{row}{column}"
                if cell in excluded_cells:
                    continue
                counts = {}
                for index in candidate_ids:
                    content = configuration_cell_content(self._all[index], row, column)
                    counts[content] = counts.get(content, 0) + 1
                best = min(best, max(counts.values()))
                if best <= 1:
                    return best
        return best

    def _score_move(
        self, action: str, target: str, groups: dict[object, list[int]], total: int
    ) -> MoveScore:
        sizes = [len(ids) for ids in groups.values()]
        worst_case = max(sizes)
        best_case = min(sizes)
        win_probability = sum(1 for size in sizes if size == 1) / total
        entropy = -sum((size / total) * log2(size / total) for size in sizes)
        expected = sum(size * size for size in sizes) / total
        return MoveScore(
            action, target, entropy, worst_case, best_case, win_probability,
            expected, len(groups),
        )

    def _groups_for(self, action: str, target: str) -> dict[object, list[int]]:
        groups: dict[object, list[int]] = {}
        if action == "wave":
            for index in self._candidate_ids:
                groups.setdefault(self._outcome(index, target), []).append(index)
        else:
            row, column = target[0], int(target[1:])
            for index in self._candidate_ids:
                content = configuration_cell_content(self._all[index], row, column)
                groups.setdefault(content, []).append(index)
        return groups

    def _augment_with_next_mover_risk(
        self,
        score: MoveScore,
        excluded_waves: frozenset[str],
        excluded_cells: frozenset[str],
    ) -> MoveScore:
        """Ajoute `next_mover_win_probability` à un coup donné.

        Coûteux (recherche sur toutes les branches non gagnantes), donc
        réservé par l'appelant à un petit nombre de coups plutôt qu'à tous
        les coups possibles (cf. `ENDGAME_RISK_SHORTLIST_SIZE` dans
        `rank_next_moves`). Contrairement à une version antérieure qui ne
        regardait que la pire branche (la plus grande), toutes les branches
        sont examinées ici : rien ne garantit que la branche dangereuse pour
        nous soit aussi la plus probable.
        """

        if self.candidate_count > ENDGAME_MAX_CANDIDATES_FOR_FOLLOWUP:
            return score
        groups = self._groups_for(score.action, score.target)
        if score.action == "wave":
            excluded_waves = excluded_waves | {score.target}
        else:
            excluded_cells = excluded_cells | {score.target}
        total = self.candidate_count
        next_mover_wins = 0
        for ids in groups.values():
            size = len(ids)
            if size <= 1:
                continue  # nous avons déjà gagné sur cette branche
            if size <= 2:
                next_mover_wins += size
                continue
            if self._best_single_move_worst_case(ids, excluded_waves, excluded_cells) <= 2:
                next_mover_wins += size
        return replace(score, next_mover_win_probability=next_mover_wins / total)

    @staticmethod
    def _base_sort_key(score: MoveScore) -> tuple:
        return (
            score.worst_case,
            score.expected_remaining,
            -score.entropy,
            score.action,
            score.target,
        )

    def rank_next_moves(self, include_used: bool = False) -> list[MoveScore]:
        total = self.candidate_count
        if total <= 1:
            return []
        used_waves = {
            observation.entry for observation in self._history
            if isinstance(observation, Observation)
        }
        used_cells = {
            observation.cell for observation in self._history
            if isinstance(observation, CellObservation)
        }
        endgame = total <= ENDGAME_MAX_CANDIDATES_FOR_FOLLOWUP
        scores: list[MoveScore] = []
        for entry in ALL_BORDER_POINTS:
            if not include_used and entry in used_waves:
                continue
            scores.append(
                self._score_move("wave", entry, self._groups_for("wave", entry), total)
            )
        for row in "ABCDEFGH":
            for column in range(1, 11):
                cell = f"{row}{column}"
                if not include_used and cell in used_cells:
                    continue
                scores.append(
                    self._score_move("cell", cell, self._groups_for("cell", cell), total)
                )

        scores.sort(key=self._base_sort_key)
        if not endgame:
            return scores

        # En fin de partie, le critère glouton habituel (pire cas minimal)
        # ne suffit plus à lui seul : un coup peut être un très bon choix par
        # ce critère tout en offrant, dans ses branches non gagnantes, un
        # coup gagnant à l'adversaire plus souvent qu'il n'en offre un à
        # nous. Il reste néanmoins le meilleur filtre pour écarter d'emblée
        # les coups qui n'apportent rien : un coup sans aucun pouvoir de
        # discrimination (une seule branche géante) aurait, avec une mesure
        # de risque bon marché, un risque adverse faussement nul en
        # apparence (aucune branche de taille exactement deux à repérer) —
        # d'où la présélection ci-dessous avant de comparer le risque, plutôt
        # que d'estimer ce risque à bas coût sur tous les coups.
        excluded_waves = frozenset() if include_used else frozenset(used_waves)
        excluded_cells = frozenset() if include_used else frozenset(used_cells)
        shortlist = scores[:ENDGAME_RISK_SHORTLIST_SIZE]
        refined = [
            self._augment_with_next_mover_risk(score, excluded_waves, excluded_cells)
            for score in shortlist
        ]
        refined.sort(
            key=lambda score: (
                -(score.win_probability - (score.next_mover_win_probability or 0.0)),
                *self._base_sort_key(score),
            )
        )
        best = refined[0]
        others = [
            score for score in scores
            if (score.action, score.target) != (best.action, best.target)
        ]
        return [best] + others
