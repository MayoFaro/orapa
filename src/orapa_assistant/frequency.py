"""Cartes de fréquences d'occupation des cases sur un ensemble de modèles.

Ces valeurs ne sont des « probabilités » que sous l'hypothèse uniforme : chaque
configuration retenue pèse autant que les autres. Lorsque l'ensemble fourni est
un échantillon borné et non l'énumération exhaustive, la carte reste une
estimation, ce que ``FrequencyMap.exhaustive`` signale explicitement.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence

from .raytracer import Configuration, Gem
from .solver import CellContent, gem_occupies_cell

ROWS = "ABCDEFGH"
COLUMNS = tuple(range(1, 11))

_STONE_CONTENTS = tuple(
    content for content in CellContent if content is not CellContent.NOTHING
)


def gem_content(gem: Gem) -> CellContent:
    """Nature de case révélée par un placement (couleur, diamant ou corps noir)."""

    if gem.name == "diamond":
        return CellContent.DIAMOND
    if gem.name == "black_body":
        return CellContent.BLACK_BODY
    assert gem.color is not None
    return CellContent(gem.color.value)


Grid = tuple[tuple[float, ...], ...]


@dataclass(frozen=True)
class FrequencyMap:
    """Fréquences d'occupation par case, globales et par nature de pierre."""

    sample_size: int
    exhaustive: bool
    occupancy: Grid
    by_content: dict[CellContent, Grid]

    def cell(self, row: str, column: int) -> float:
        return self.occupancy[ROWS.index(row.upper())][column - 1]

    def dominant_content(self, row: str, column: int) -> CellContent | None:
        row_index = ROWS.index(row.upper())
        column_index = column - 1
        best: CellContent | None = None
        best_value = 0.0
        for content, grid in self.by_content.items():
            value = grid[row_index][column_index]
            if value > best_value:
                best, best_value = content, value
        return best


def build_frequency_map(
    configurations: Sequence[Configuration], *, exhaustive: bool
) -> FrequencyMap:
    sample_size = len(configurations)
    occupancy = [[0] * 10 for _ in range(8)]
    by_content = {
        content: [[0] * 10 for _ in range(8)] for content in _STONE_CONTENTS
    }
    for configuration in configurations:
        covered = [[False] * 10 for _ in range(8)]
        for gem in configuration.gems:
            content_grid = by_content[gem_content(gem)]
            for row_index, row in enumerate(ROWS):
                for column_index, column in enumerate(COLUMNS):
                    if gem_occupies_cell(gem, row, column):
                        content_grid[row_index][column_index] += 1
                        covered[row_index][column_index] = True
        for row_index in range(8):
            for column_index in range(10):
                if covered[row_index][column_index]:
                    occupancy[row_index][column_index] += 1

    def scaled(grid: list[list[int]]) -> Grid:
        if not sample_size:
            return tuple(tuple(0.0 for _ in row) for row in grid)
        return tuple(tuple(value / sample_size for value in row) for row in grid)

    return FrequencyMap(
        sample_size=sample_size,
        exhaustive=exhaustive,
        occupancy=scaled(occupancy),
        by_content={
            content: scaled(grid) for content, grid in by_content.items()
        },
    )


__all__ = ["FrequencyMap", "build_frequency_map", "gem_content", "ROWS", "COLUMNS"]
