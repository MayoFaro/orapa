from orapa_assistant.colors import RayColor as C
from orapa_assistant.progressive import ProgressiveSolver
from orapa_assistant.solver import Observation


HISTORY_BEFORE_G10 = (
    Observation("10", "10", C.TRANSPARENT),
    Observation("7", "7", C.YELLOW),
    Observation("H", "I", C.RED),
    Observation("11", "M", C.BLUE),
    Observation("15", "L", C.WHITE),
    Observation("14", absorbed=True),
    Observation("K", "6", C.WHITE),
    Observation("D", "D", C.WHITE),
    Observation("12", "12", C.LIGHT_GREEN),
    Observation("16", absorbed=True),
    Observation("18", "18", C.RED),
    Observation("8", "8", C.YELLOW),
    Observation("13", absorbed=True),
    Observation("P", "Q", C.YELLOW),
)


def test_relational_solver_finishes_before_the_former_g10_question() -> None:
    solver = ProgressiveSolver(include_diamond=True, include_black_body=True)
    solver.add_observations(HISTORY_BEFORE_G10)
    assert solver.raw_combination_count == 1
    assert solver.exact
    assert solver.candidate_count == 1
