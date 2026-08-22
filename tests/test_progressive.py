from orapa_assistant.examples import REAL_GAME_HISTORY
from orapa_assistant.progressive import ProgressiveSolver


def test_progressive_solver_waits_then_becomes_exact() -> None:
    solver = ProgressiveSolver()
    assert not solver.exact
    assert solver.candidate_count is None
    assert solver.raw_combination_count == 139_158_093_312

    solver.add_observations(REAL_GAME_HISTORY)
    assert solver.exact
    assert solver.raw_combination_count == 1
    assert solver.candidate_count == 1
    assert len(solver.candidates) == 1


def test_removing_last_observation_recomputes_exact_state() -> None:
    solver = ProgressiveSolver()
    solver.add_observations(REAL_GAME_HISTORY)
    solver.remove_observation(len(REAL_GAME_HISTORY) - 1)
    assert solver.exact
    assert solver.candidate_count == 1
    assert solver.raw_combination_count == 1
