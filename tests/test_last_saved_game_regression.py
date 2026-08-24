from orapa_assistant.colors import RayColor as C
from orapa_assistant.progressive import ProgressiveSolver
from orapa_assistant.relational_filter import _partial_wave_matches
from orapa_assistant.search import configuration_matches
from orapa_assistant.solver import CellContent, CellObservation, Observation


LAST_SAVED_GAME = (
    Observation("10", "R", C.TRANSPARENT),
    Observation("6", "6", C.TRANSPARENT),
    Observation("1", "1", C.RED),
    Observation("8", "8", C.BLUE),
    Observation("9", "9", C.BLUE),
    Observation("7", "7", C.BLUE),
    Observation("12", "Q", C.BLUE),
    Observation("C", "C", C.PINK),
    Observation("11", "11", C.BLUE),
    Observation("D", absorbed=True),
    Observation("A", "A", C.WHITE),
    CellObservation("C", 5, CellContent.NOTHING),
    Observation("B", "2", C.WHITE),
    Observation("G", "L", C.PINK),
    Observation("E", absorbed=True),
    Observation("F", "F", C.YELLOW),
    Observation("O", "O", C.YELLOW),
    Observation("13", "17", C.GREEN),
    Observation("16", "16", C.LIGHT_GREEN),
    CellObservation("D", 4, CellContent.NOTHING),
)

EXPECTED_VERTICES = {
    "white_diamond": ((2, 4), (4, 2), (6, 4), (4, 6)),
    "blue": ((10, 2), (18, 2), (14, 6)),
    "red": ((0, 14), (2, 16), (6, 16), (4, 14)),
    "yellow": ((12, 10), (16, 14), (12, 14)),
    "white_triangle": ((4, 12), (12, 12), (8, 16)),
    "diamond": ((8, 0), (12, 0), (10, 2)),
    "black_body": ((10, 6), (12, 6), (12, 10), (10, 10)),
}

STALLED_GAME = (
    Observation("9", "13", C.WHITE),
    Observation("5", absorbed=True),
    Observation("14", "Q", C.WHITE),
    Observation("11", absorbed=True),
    Observation("7", "17", C.WHITE),
    Observation("H", "15", C.LIGHT_BLUE),
    Observation("M", "M", C.WHITE),
    Observation("6", "8", C.LIGHT_BLUE),
    Observation("2", "A", C.YELLOW),
    Observation("K", "K", C.RED),
    Observation("3", "3", C.RED),
    Observation("C", "C", C.BLUE),
    Observation("G", "18", C.LIGHT_BLUE),
    Observation("10", "R", C.TRANSPARENT),
    Observation("4", absorbed=True),
    Observation("12", absorbed=True),
    Observation("E", "F", C.RED),
    Observation("P", "P", C.WHITE),
    Observation("D", "D", C.YELLOW),
)


def test_last_saved_game_keeps_intermediate_results_and_the_same_final_grid() -> None:
    solver = ProgressiveSolver(include_diamond=True, include_black_body=True)

    for observation in LAST_SAVED_GAME[:13]:
        solver.add_observation(observation)
    assert solver.strategy_sample_count == 65
    assert solver.rank_next_moves()

    expected_counts = (20, 10, 4, 2, 1)
    observed_counts = []
    for observation in LAST_SAVED_GAME[13:]:
        solver.add_observation(observation)
        if solver.candidate_count is not None:
            observed_counts.append(solver.candidate_count)
    assert tuple(observed_counts) == expected_counts

    assert solver.exact
    assert solver.candidate_count == 1
    configuration = solver.candidates[0]
    assert configuration_matches(configuration, LAST_SAVED_GAME)
    assert {
        gem.name: tuple((point.x, point.y) for point in gem.polygon.vertices)
        for gem in configuration.gems
    } == EXPECTED_VERTICES


def test_global_csp_solves_stalled_game_before_two_redundant_clues() -> None:
    _partial_wave_matches.cache_clear()
    solver = ProgressiveSolver(include_diamond=True, include_black_body=True)

    solver.add_observations(STALLED_GAME[:17])

    assert solver.exact
    assert solver.candidate_count == 1
    assert configuration_matches(solver.candidates[0], STALLED_GAME)
