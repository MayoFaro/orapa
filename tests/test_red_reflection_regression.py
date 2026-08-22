from orapa_assistant.colors import RayColor
from orapa_assistant.geometry import doubled_polygon
from orapa_assistant.pieces import PIECES, placements
from orapa_assistant.progressive import ProgressiveSolver
from orapa_assistant.solver import Observation


AMBIGUOUS_HISTORY = (
    Observation("M", "M", RayColor.RED),
    Observation("9", "9", RayColor.WHITE),
    Observation("I", "E", RayColor.WHITE),
    Observation("2", "C", RayColor.YELLOW),
    Observation("12", "12", RayColor.YELLOW),
    Observation("13", "Q", RayColor.WHITE),
    Observation("16", "16", RayColor.BLUE),
    Observation("7", "7", RayColor.WHITE),
    Observation("O", "O", RayColor.LIGHT_BLUE),
    Observation("11", "A", RayColor.TRANSPARENT),
    Observation("5", "5", RayColor.LIGHT_GREEN),
)


def _vertex_set(polygon):
    return frozenset(polygon.vertices)


def test_red_catalog_contains_both_mirrored_bottom_placements() -> None:
    red_definition = next(piece for piece in PIECES if piece.name == "red")
    catalog = {_vertex_set(gem.polygon) for gem in placements(red_definition)}
    slopes_left = doubled_polygon((4, 7), (6, 7), (5, 8), (3, 8))
    slopes_right = doubled_polygon((2, 7), (4, 7), (5, 8), (3, 8))
    assert _vertex_set(slopes_left) in catalog
    assert _vertex_set(slopes_right) in catalog


def test_ambiguous_history_does_not_report_a_unique_solution() -> None:
    solver = ProgressiveSolver()
    solver.add_observations(AMBIGUOUS_HISTORY)
    assert solver.exact
    assert solver.candidate_count == 3
