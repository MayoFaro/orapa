from orapa_assistant.colors import RayColor
from orapa_assistant.examples import REAL_GAME_SOLUTION
from orapa_assistant.raytracer import Configuration
from orapa_assistant.solver import Observation, Solver


def test_solver_filters_and_restores_candidates() -> None:
    empty = Configuration(())
    solver = Solver([empty, REAL_GAME_SOLUTION])
    solver.add_observation(Observation("8", "12", RayColor.RED))
    assert solver.candidate_count == 1
    assert solver.candidates == (REAL_GAME_SOLUTION,)
    solver.remove_observation(0)
    assert solver.candidate_count == 2


def test_solver_finds_suspect_observation() -> None:
    solver = Solver([REAL_GAME_SOLUTION])
    solver.add_observation(Observation("8", "12", RayColor.RED))
    solver.add_observation(Observation("D", "D", RayColor.RED))
    assert solver.candidate_count == 0
    assert solver.suspect_observations() == [(1, 1)]


def test_move_ranking_prefers_a_discriminating_entry() -> None:
    solver = Solver([Configuration(()), REAL_GAME_SOLUTION])
    scores = solver.rank_next_moves()
    assert scores
    assert scores[0].worst_case == 1
    assert scores[0].outcome_count == 2
