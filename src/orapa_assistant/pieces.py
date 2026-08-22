from __future__ import annotations

from dataclasses import dataclass

from .colors import BaseColor
from .geometry import Point, Polygon
from .raytracer import Gem


@dataclass(frozen=True)
class PieceDefinition:
    name: str
    color: BaseColor | None
    vertices: tuple[Point, ...]
    absorbs: bool = False
    allow_reflection: bool = False


PIECES = (
    PieceDefinition(
        "white_diamond",
        BaseColor.WHITE,
        (Point(2, 0), Point(4, 2), Point(2, 4), Point(0, 2)),
    ),
    PieceDefinition(
        "blue",
        BaseColor.BLUE,
        (Point(0, 0), Point(4, 4), Point(0, 8)),
    ),
    PieceDefinition(
        "red",
        BaseColor.RED,
        (Point(0, 0), Point(2, 2), Point(2, 6), Point(0, 4)),
        allow_reflection=True,
    ),
    PieceDefinition(
        "yellow",
        BaseColor.YELLOW,
        (Point(0, 0), Point(4, 4), Point(0, 4)),
    ),
    PieceDefinition(
        "white_triangle",
        BaseColor.WHITE,
        (Point(0, 0), Point(8, 0), Point(4, 4)),
    ),
)

DIAMOND = PieceDefinition(
    "diamond",
    None,
    (Point(2, 0), Point(2, 4), Point(0, 2)),
)

BLACK_BODY = PieceDefinition(
    "black_body",
    None,
    (Point(0, 0), Point(4, 0), Point(4, 2), Point(0, 2)),
    absorbs=True,
)


def _normalize(vertices: tuple[Point, ...]) -> tuple[Point, ...]:
    min_x = min(point.x for point in vertices)
    min_y = min(point.y for point in vertices)
    translated = tuple(Point(point.x - min_x, point.y - min_y) for point in vertices)
    start = min(range(len(translated)), key=lambda index: translated[index])
    return translated[start:] + translated[:start]


def rotations(piece: PieceDefinition) -> tuple[tuple[Point, ...], ...]:
    unique: list[tuple[Point, ...]] = []
    seeds = [piece.vertices]
    if piece.allow_reflection:
        seeds.append(tuple(Point(-point.x, point.y) for point in piece.vertices))
    for seed in seeds:
        current = seed
        for _ in range(4):
            normalized = _normalize(current)
            if normalized not in unique:
                unique.append(normalized)
            current = tuple(Point(-point.y, point.x) for point in current)
    return tuple(unique)


def placements(piece: PieceDefinition) -> tuple[Gem, ...]:
    result: list[Gem] = []
    for orientation in rotations(piece):
        width = max(point.x for point in orientation)
        height = max(point.y for point in orientation)
        for offset_x in range(0, 20 - width + 1, 2):
            for offset_y in range(0, 16 - height + 1, 2):
                polygon = Polygon(
                    tuple(Point(point.x + offset_x, point.y + offset_y) for point in orientation)
                )
                result.append(Gem(piece.color, polygon, piece.name, piece.absorbs))
    return tuple(result)
