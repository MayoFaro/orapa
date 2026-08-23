from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from enum import Enum
from math import log2
from typing import Iterable

from .border import ALL_BORDER_POINTS, normalize_border_point
from .colors import RayColor
from .constraints import polygons_have_interior_overlap
from .geometry import doubled_polygon
from .raytracer import Configuration, RayOutcome, simulate_ray


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
    expected_remaining: float
    outcome_count: int

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
        scores: list[MoveScore] = []
        for entry in ALL_BORDER_POINTS:
            if not include_used and entry in used_waves:
                continue
            groups = Counter(self._outcome(index, entry) for index in self._candidate_ids)
            entropy = -sum(
                (size / total) * log2(size / total) for size in groups.values()
            )
            expected = sum(size * size for size in groups.values()) / total
            scores.append(
                MoveScore("wave", entry, entropy, max(groups.values()), expected, len(groups))
            )
        for row in "ABCDEFGH":
            for column in range(1, 11):
                cell = f"{row}{column}"
                if not include_used and cell in used_cells:
                    continue
                groups = Counter(
                    configuration_cell_content(self._all[index], row, column)
                    for index in self._candidate_ids
                )
                entropy = -sum(
                    (size / total) * log2(size / total) for size in groups.values()
                )
                expected = sum(size * size for size in groups.values()) / total
                scores.append(MoveScore(
                    "cell", cell, entropy, max(groups.values()), expected, len(groups)
                ))
        return sorted(
            scores,
            key=lambda score: (
                score.worst_case,
                score.expected_remaining,
                -score.entropy,
                score.action,
                score.target,
            ),
        )
