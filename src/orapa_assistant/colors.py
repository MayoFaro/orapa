from __future__ import annotations

from enum import Enum


class BaseColor(str, Enum):
    RED = "red"
    YELLOW = "yellow"
    BLUE = "blue"
    WHITE = "white"


class RayColor(str, Enum):
    TRANSPARENT = "transparent"
    WHITE = "white"
    RED = "red"
    YELLOW = "yellow"
    BLUE = "blue"
    PINK = "pink"
    LIGHT_YELLOW = "light_yellow"
    LIGHT_BLUE = "light_blue"
    ORANGE = "orange"
    GREEN = "green"
    VIOLET = "violet"
    LIGHT_ORANGE = "light_orange"
    LIGHT_GREEN = "light_green"
    LIGHT_VIOLET = "light_violet"
    BLACK = "black"
    GRAY = "gray"


R = BaseColor.RED
Y = BaseColor.YELLOW
B = BaseColor.BLUE
W = BaseColor.WHITE

COLOR_MIXES: dict[frozenset[BaseColor], RayColor] = {
    frozenset(): RayColor.TRANSPARENT,
    frozenset({W}): RayColor.WHITE,
    frozenset({R}): RayColor.RED,
    frozenset({Y}): RayColor.YELLOW,
    frozenset({B}): RayColor.BLUE,
    frozenset({R, W}): RayColor.PINK,
    frozenset({Y, W}): RayColor.LIGHT_YELLOW,
    frozenset({B, W}): RayColor.LIGHT_BLUE,
    frozenset({R, Y}): RayColor.ORANGE,
    frozenset({Y, B}): RayColor.GREEN,
    frozenset({R, B}): RayColor.VIOLET,
    frozenset({R, Y, W}): RayColor.LIGHT_ORANGE,
    frozenset({Y, B, W}): RayColor.LIGHT_GREEN,
    frozenset({R, B, W}): RayColor.LIGHT_VIOLET,
    frozenset({R, Y, B}): RayColor.BLACK,
    frozenset({R, Y, B, W}): RayColor.GRAY,
}

RAY_COLOR_COMPONENTS: dict[RayColor, frozenset[BaseColor]] = {
    ray_color: base_colors for base_colors, ray_color in COLOR_MIXES.items()
}


def mix_colors(colors: set[BaseColor] | frozenset[BaseColor]) -> RayColor:
    return COLOR_MIXES[frozenset(colors)]
