from orapa_assistant.examples import REAL_GAME_HISTORY
from orapa_assistant.progressive import ProgressiveSolver


def test_a_piece_is_exposed_before_the_complete_solution() -> None:
    solver = ProgressiveSolver()
    solver.add_observations(REAL_GAME_HISTORY[:2])
    assert solver.candidate_count is None
    assert [gem.name for gem in solver.certain_gems] == ["white_diamond"]
