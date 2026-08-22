from itertools import combinations

from orapa_assistant.colors import BaseColor, COLOR_MIXES, RayColor, mix_colors


def test_all_sixteen_color_combinations_are_defined() -> None:
    colors = list(BaseColor)
    subsets = {
        frozenset(combo)
        for size in range(len(colors) + 1)
        for combo in combinations(colors, size)
    }
    assert set(COLOR_MIXES) == subsets


def test_known_mixes() -> None:
    assert mix_colors(set()) == RayColor.TRANSPARENT
    assert mix_colors({BaseColor.RED, BaseColor.BLUE}) == RayColor.VIOLET
    assert mix_colors(set(BaseColor)) == RayColor.GRAY
