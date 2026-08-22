from __future__ import annotations


TOP_POINTS = tuple(str(number) for number in range(1, 11))
RIGHT_POINTS = tuple(str(number) for number in range(11, 19))
BOTTOM_POINTS = tuple(chr(code) for code in range(ord("I"), ord("R") + 1))
LEFT_POINTS = tuple(chr(code) for code in range(ord("A"), ord("H") + 1))
ALL_BORDER_POINTS = TOP_POINTS + RIGHT_POINTS + BOTTOM_POINTS + LEFT_POINTS


def normalize_border_point(value: str) -> str:
    point = value.strip().upper()
    if point not in ALL_BORDER_POINTS:
        raise ValueError(f"Point de bord inconnu : {value!r}")
    return point
