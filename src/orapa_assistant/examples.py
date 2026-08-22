from .colors import BaseColor
from .geometry import doubled_polygon
from .raytracer import Configuration, Gem
from .colors import RayColor
from .solver import Observation


REAL_GAME_SOLUTION = Configuration(
    (
        Gem(BaseColor.WHITE, doubled_polygon((3, 1), (4, 2), (3, 3), (2, 2)), "white_diamond"),
        Gem(BaseColor.BLUE, doubled_polygon((4, 0), (6, 2), (4, 4)), "blue"),
        Gem(BaseColor.RED, doubled_polygon((7, 1), (8, 2), (8, 4), (7, 3)), "red"),
        Gem(BaseColor.YELLOW, doubled_polygon((7, 4), (9, 6), (7, 6)), "yellow"),
        Gem(BaseColor.WHITE, doubled_polygon((1, 5), (5, 5), (3, 7)), "white_triangle"),
    )
)

REAL_GAME_HISTORY = (
    Observation("B", "3", RayColor.WHITE),
    Observation("2", "2", RayColor.WHITE),
    Observation("C", "C", RayColor.WHITE),
    Observation("E", "E", RayColor.YELLOW),
    Observation("8", "12", RayColor.RED),
    Observation("15", "15", RayColor.GRAY),
    Observation("M", "M", RayColor.LIGHT_YELLOW),
    Observation("H", "18", RayColor.TRANSPARENT),
    Observation("13", "13", RayColor.RED),
    Observation("9", "16", RayColor.YELLOW),
    Observation("K", "G", RayColor.WHITE),
    Observation("N", "N", RayColor.VIOLET),
    Observation("6", "6", RayColor.VIOLET),
    Observation("7", "O", RayColor.TRANSPARENT),
    Observation("D", "D", RayColor.BLUE),
)
