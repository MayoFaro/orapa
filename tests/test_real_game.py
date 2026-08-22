import pytest

from orapa_assistant.colors import BaseColor, RayColor
from orapa_assistant.geometry import doubled_polygon
from orapa_assistant.raytracer import Configuration, Gem, simulate_ray


@pytest.fixture
def final_configuration() -> Configuration:
    return Configuration(
        (
            Gem(BaseColor.WHITE, doubled_polygon((3, 1), (4, 2), (3, 3), (2, 2)), "white_diamond"),
            Gem(BaseColor.BLUE, doubled_polygon((4, 0), (6, 2), (4, 4)), "blue"),
            Gem(BaseColor.RED, doubled_polygon((7, 1), (8, 2), (8, 4), (7, 3)), "red"),
            Gem(BaseColor.YELLOW, doubled_polygon((7, 4), (9, 6), (7, 6)), "yellow"),
            Gem(BaseColor.WHITE, doubled_polygon((1, 5), (5, 5), (3, 7)), "white_triangle"),
        )
    )


@pytest.mark.parametrize(
    ("entry", "exit_point", "color"),
    [
        ("B", "3", RayColor.WHITE),
        ("2", "2", RayColor.WHITE),
        ("C", "C", RayColor.WHITE),
        ("E", "E", RayColor.YELLOW),
        ("8", "12", RayColor.RED),
        ("15", "15", RayColor.GRAY),
        ("M", "M", RayColor.LIGHT_YELLOW),
        ("H", "18", RayColor.TRANSPARENT),
        ("13", "13", RayColor.RED),
        ("9", "16", RayColor.YELLOW),
        ("K", "G", RayColor.WHITE),
        ("N", "N", RayColor.VIOLET),
        ("6", "6", RayColor.VIOLET),
        ("7", "O", RayColor.TRANSPARENT),
        ("D", "D", RayColor.BLUE),
    ],
)
def test_final_grid_reproduces_history(
    final_configuration: Configuration,
    entry: str,
    exit_point: str,
    color: RayColor,
) -> None:
    outcome = simulate_ray(final_configuration, entry).outcome
    assert outcome.exit_point == exit_point
    assert outcome.color == color
