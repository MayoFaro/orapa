from orapa_assistant.colors import RayColor as C
from orapa_assistant.progressive import ProgressiveSolver
from orapa_assistant.solver import CellContent, CellObservation, Observation


FIRST_SIXTEEN_CLUES = (
    Observation("6", "6", C.RED),
    Observation("C", "C", C.BLUE),
    Observation("7", absorbed=True),
    Observation("4", "4", C.TRANSPARENT),
    Observation("8", "1", C.LIGHT_BLUE),
    Observation("15", "15", C.LIGHT_YELLOW),
    Observation("12", absorbed=True),
    Observation("N", "N", C.RED),
    Observation("17", "Q", C.YELLOW),
    Observation("5", "5", C.TRANSPARENT),
    Observation("R", "16", C.YELLOW),
    Observation("F", "F", C.BLUE),
    Observation("13", "9", C.WHITE),
    Observation("10", "14", C.WHITE),
    CellObservation("E", 6, CellContent.NOTHING),
    Observation("3", "K", C.TRANSPARENT),
)

REMAINING_CLUES = (
    Observation("11", absorbed=True),
    Observation("P", "P", C.WHITE),
    Observation("M", "M", C.RED),
    Observation("L", "G", C.WHITE),
    Observation("18", "O", C.RED),
    Observation("J", "I", C.LIGHT_BLUE),
    Observation("H", "H", C.LIGHT_ORANGE),
    Observation("B", absorbed=True),
    Observation("2", absorbed=True),
    Observation("A", absorbed=True),
    CellObservation("D", 4, CellContent.NOTHING),
    CellObservation("D", 3, CellContent.NOTHING),
    CellObservation("B", 4, CellContent.NOTHING),
    CellObservation("F", 3, CellContent.NOTHING),
    CellObservation("B", 2, CellContent.NOTHING),
    CellObservation("C", 8, CellContent.WHITE),
    CellObservation("C", 9, CellContent.WHITE),
    CellObservation("C", 10, CellContent.NOTHING),
)


def test_relational_solver_understands_the_sixteen_clue_prefix() -> None:
    solver = ProgressiveSolver(include_diamond=True, include_black_body=True)
    solver.add_observations(FIRST_SIXTEEN_CLUES[:12])

    assert not solver.exact
    assert solver.deferred_relation_count > 0
    assert solver.strategy_sample_count == 0
    assert solver.rank_next_moves() == []

    for observation in FIRST_SIXTEEN_CLUES[12:]:
        solver.add_observation(observation)

    assert solver.exact
    assert solver.candidate_count == 4
    assert {
        gem.name for gem in solver.certain_gems
    } == {"blue", "yellow", "white_triangle", "white_diamond", "diamond"}
    assert solver.rank_next_moves()[0].label in {
        "Examiner la case A2",
        "Examiner la case A7",
        "Examiner la case B2",
        "Examiner la case B7",
    }


def test_complete_history_recovers_the_published_final_grid() -> None:
    solver = ProgressiveSolver(include_diamond=True, include_black_body=True)
    solver.add_observations(FIRST_SIXTEEN_CLUES + REMAINING_CLUES)

    assert solver.exact
    assert solver.candidate_count == 1
    vertices = {
        gem.name: tuple((point.x, point.y) for point in gem.polygon.vertices)
        for gem in solver.candidates[0].gems
    }
    assert vertices == {
        "white_diamond": ((6, 12), (8, 10), (10, 12), (8, 14)),
        "blue": ((0, 4), (4, 8), (0, 12)),
        "red": ((8, 16), (10, 14), (14, 14), (12, 16)),
        "yellow": ((16, 10), (20, 10), (16, 14)),
        "white_triangle": ((12, 8), (16, 4), (20, 8)),
        "diamond": ((6, 8), (10, 8), (8, 10)),
        "black_body": ((12, 0), (14, 0), (14, 4), (12, 4)),
    }
