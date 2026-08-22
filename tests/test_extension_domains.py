from orapa_assistant.colors import RayColor
from orapa_assistant.domain_filter import apply_exact_observation_filters
from orapa_assistant.progressive import ProgressiveSolver
from orapa_assistant.solver import Observation


def test_progressive_solver_adds_requested_extension_domains() -> None:
    solver = ProgressiveSolver(include_diamond=True, include_black_body=True)
    assert solver.domain_sizes["diamond"] == 284
    assert solver.domain_sizes["black_body"] == 142


def test_transparent_deflection_can_constrain_diamond() -> None:
    solver = ProgressiveSolver(include_diamond=True)
    solver.add_observation(Observation("A", "1", RayColor.TRANSPARENT))
    assert solver.domain_sizes["diamond"] < 284


def test_absorbed_observation_is_structured_without_exit_or_color() -> None:
    observation = Observation("8", absorbed=True)
    assert observation.outcome.absorbed
    assert observation.exit_point is None
    assert observation.color is None
