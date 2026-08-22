from orapa_assistant.colors import BaseColor, RayColor
from orapa_assistant.geometry import doubled_polygon
from orapa_assistant.raytracer import Configuration, Gem, simulate_ray


def test_ray_hits_a_gem_face_placed_on_entry_border() -> None:
    gem = Gem(
        BaseColor.BLUE,
        doubled_polygon((0, 4), (2, 6), (0, 8)),
        "blue_on_left_border",
    )
    outcome = simulate_ray(Configuration((gem,)), "H").outcome
    assert outcome.exit_point == "H"
    assert outcome.color == RayColor.BLUE
