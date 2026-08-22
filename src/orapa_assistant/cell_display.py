from __future__ import annotations

from .geometry import Point, Polygon
from .raytracer import Configuration


COLOR_CODES = {
    "white": "W",
    "red": "R",
    "yellow": "Y",
    "blue": "B",
}

PIECE_CODES = {
    "diamond": "D",
    "black_body": "N",
}

CORNER_SUFFIXES = {
    "top_left": "hg",
    "top_right": "hd",
    "bottom_left": "bg",
    "bottom_right": "bd",
}


def _cross(origin: Point, end: Point, point: Point) -> int:
    return (end.x - origin.x) * (point.y - origin.y) - (
        end.y - origin.y
    ) * (point.x - origin.x)


def point_in_convex_polygon(point: Point, polygon: Polygon) -> bool:
    """Inclut le bord du polygone ; les gemmes officielles sont convexes."""

    crosses = [
        _cross(segment.start, segment.end, point) for segment in polygon.segments
    ]
    return all(value >= 0 for value in crosses) or all(value <= 0 for value in crosses)


def piece_cell_code(polygon: Polygon, symbol: str, row: int, column: int) -> str | None:
    x0, y0 = 2 * column, 2 * row
    corners = {
        "top_left": Point(x0, y0),
        "top_right": Point(x0 + 2, y0),
        "bottom_left": Point(x0, y0 + 2),
        "bottom_right": Point(x0 + 2, y0 + 2),
    }
    inside = {
        name for name, point in corners.items() if point_in_convex_polygon(point, polygon)
    }
    if len(inside) == 4:
        return symbol
    if len(inside) != 3:
        return None

    missing = ({*corners} - inside).pop()
    opposite = {
        "top_left": "bottom_right",
        "top_right": "bottom_left",
        "bottom_left": "top_right",
        "bottom_right": "top_left",
    }[missing]
    return symbol + CORNER_SUFFIXES[opposite]


def configuration_cell_codes(configuration: Configuration) -> list[list[str]]:
    cells: list[list[list[str]]] = [[[] for _ in range(10)] for _ in range(8)]
    for gem in configuration.gems:
        for row in range(8):
            for column in range(10):
                symbol = (
                    PIECE_CODES[gem.name]
                    if gem.name in PIECE_CODES
                    else COLOR_CODES[gem.color.value]
                )
                code = piece_cell_code(gem.polygon, symbol, row, column)
                if code:
                    cells[row][column].append(code)
    return [["/".join(codes) if codes else "·" for codes in row] for row in cells]
