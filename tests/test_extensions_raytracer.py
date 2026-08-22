from orapa_assistant.colors import BaseColor, RayColor
from orapa_assistant.geometry import doubled_polygon
from orapa_assistant.raytracer import Configuration, Gem, simulate_ray


def test_diamond_reflects_without_coloring_the_wave() -> None:
    diamond = Gem(None, doubled_polygon((1, 0), (1, 2), (0, 1)), "diamond")
    outcome = simulate_ray(Configuration((diamond,)), "A").outcome
    assert outcome.exit_point == "1"
    assert outcome.color == RayColor.TRANSPARENT
    assert not outcome.absorbed


def test_diamond_can_redirect_a_wave_towards_a_colored_gem() -> None:
    diamond = Gem(None, doubled_polygon((1, 1), (1, 3), (0, 2)), "diamond")
    red = Gem(
        BaseColor.RED,
        doubled_polygon((0, 3), (2, 3), (2, 4), (0, 4)),
        "red",
    )
    outcome = simulate_ray(Configuration((diamond, red)), "C").outcome
    assert outcome.color == RayColor.RED


def test_black_body_absorbs_without_exit_or_color() -> None:
    black = Gem(
        None,
        doubled_polygon((2, 2), (4, 2), (4, 3), (2, 3)),
        "black_body",
        absorbs=True,
    )
    outcome = simulate_ray(Configuration((black,)), "C").outcome
    assert outcome.absorbed
    assert outcome.exit_point is None
    assert outcome.color is None
