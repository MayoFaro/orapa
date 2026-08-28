from orapa_assistant.examples import REAL_GAME_HISTORY, REAL_GAME_SOLUTION
from orapa_assistant.frequency import build_frequency_map, gem_content
from orapa_assistant.progressive import ProgressiveSolver
from orapa_assistant.solver import CellContent


def test_single_configuration_gives_certain_cells() -> None:
    fmap = build_frequency_map([REAL_GAME_SOLUTION], exhaustive=True)
    assert fmap.sample_size == 1
    assert fmap.exhaustive
    # B5 est plein de bleu dans la solution de référence.
    assert fmap.cell("B", 5) == 1.0
    assert fmap.dominant_content("B", 5) == CellContent.BLUE
    # A1 est vide.
    assert fmap.cell("A", 1) == 0.0
    assert fmap.dominant_content("A", 1) is None


def test_frequencies_are_averaged_over_the_sample() -> None:
    empty = REAL_GAME_SOLUTION.__class__(())
    fmap = build_frequency_map([REAL_GAME_SOLUTION, empty], exhaustive=False)
    assert fmap.sample_size == 2
    assert not fmap.exhaustive
    assert fmap.cell("B", 5) == 0.5
    assert 0.0 <= min(min(row) for row in fmap.occupancy)
    assert max(max(row) for row in fmap.occupancy) <= 1.0


def test_empty_sample_is_all_zero() -> None:
    fmap = build_frequency_map([], exhaustive=False)
    assert fmap.sample_size == 0
    assert all(value == 0.0 for row in fmap.occupancy for value in row)


def test_progressive_solver_exposes_estimated_then_exact_map() -> None:
    solver = ProgressiveSolver()
    solver.add_observations(REAL_GAME_HISTORY[:3])
    estimated = solver.frequency_map
    assert estimated is not None
    assert not estimated.exhaustive
    assert estimated.sample_size > 1

    solver.add_observations(REAL_GAME_HISTORY[3:])
    exact = solver.frequency_map
    assert exact is not None
    assert exact.exhaustive
    assert exact.cell("B", 5) == 1.0


def test_gem_content_maps_extensions() -> None:
    diamond, black = None, None
    from orapa_assistant.geometry import doubled_polygon
    from orapa_assistant.raytracer import Gem

    diamond = Gem(None, doubled_polygon((1, 0), (1, 2), (0, 1)), "diamond")
    black = Gem(None, doubled_polygon((0, 0), (2, 0), (2, 1), (0, 1)), "black_body", absorbs=True)
    assert gem_content(diamond) == CellContent.DIAMOND
    assert gem_content(black) == CellContent.BLACK_BODY
