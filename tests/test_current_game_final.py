from orapa_assistant.colors import BaseColor, RayColor
from orapa_assistant.geometry import Point, Polygon
from orapa_assistant.raytracer import Configuration, Gem
from orapa_assistant.search import configuration_matches
from orapa_assistant.solver import (
    CellContent,
    CellObservation,
    Observation,
    configuration_cell_content,
)


def _gem(
    name: str,
    color: BaseColor | None,
    vertices: tuple[tuple[int, int], ...],
    *,
    absorbs: bool = False,
) -> Gem:
    return Gem(
        color,
        Polygon(tuple(Point(x, y) for x, y in vertices)),
        name,
        absorbs,
    )


FINAL_CONFIGURATION = Configuration(
    (
        _gem(
            "black_body",
            None,
            ((2, 0), (4, 0), (4, 4), (2, 4)),
            absorbs=True,
        ),
        _gem("blue", BaseColor.BLUE, ((0, 6), (8, 6), (4, 10))),
        _gem("diamond", None, ((10, 12), (14, 12), (12, 14))),
        _gem(
            "red",
            BaseColor.RED,
            ((16, 6), (16, 10), (18, 8), (18, 4)),
        ),
        _gem(
            "white_diamond",
            BaseColor.WHITE,
            ((4, 4), (6, 2), (8, 4), (6, 6)),
        ),
        _gem(
            "white_triangle",
            BaseColor.WHITE,
            ((10, 2), (14, 6), (10, 10)),
        ),
        _gem(
            "yellow",
            BaseColor.YELLOW,
            ((14, 14), (18, 10), (18, 14)),
        ),
    )
)

FIRST_THIRTEEN_CLUES = (
    Observation("5", "M", RayColor.TRANSPARENT),
    Observation("Q", "Q", RayColor.YELLOW),
    Observation("P", "P", RayColor.YELLOW),
    Observation("G", "N", RayColor.TRANSPARENT),
    Observation("16", "16", RayColor.YELLOW),
    Observation("B", absorbed=True),
    Observation("1", "1", RayColor.BLUE),
    Observation("13", "13", RayColor.RED),
    Observation("10", "R", RayColor.TRANSPARENT),
    Observation("E", "J", RayColor.BLUE),
    Observation("C", "C", RayColor.LIGHT_BLUE),
    Observation("7", "9", RayColor.PINK),
    Observation("15", "F", RayColor.ORANGE),
)


def test_final_grid_matches_all_thirteen_wave_clues() -> None:
    assert configuration_matches(FINAL_CONFIGURATION, FIRST_THIRTEEN_CLUES)


def test_b2_nothing_is_the_clue_that_excludes_the_final_grid() -> None:
    assert (
        configuration_cell_content(FINAL_CONFIGURATION, "B", 2)
        == CellContent.BLACK_BODY
    )
    assert not configuration_matches(
        FINAL_CONFIGURATION,
        FIRST_THIRTEEN_CLUES
        + (CellObservation("B", 2, CellContent.NOTHING),),
    )


def test_later_empty_cell_clues_are_compatible_with_the_final_grid() -> None:
    assert configuration_cell_content(FINAL_CONFIGURATION, "A", 4) == CellContent.NOTHING
    assert configuration_cell_content(FINAL_CONFIGURATION, "A", 3) == CellContent.NOTHING
