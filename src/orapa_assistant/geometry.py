from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, order=True)
class Point:
    """Point en coordonnées doublées, donc toujours exactes."""

    x: int
    y: int


@dataclass(frozen=True)
class Segment:
    start: Point
    end: Point

    def __post_init__(self) -> None:
        dx = self.end.x - self.start.x
        dy = self.end.y - self.start.y
        if not (dx == 0 or dy == 0 or abs(dx) == abs(dy)):
            raise ValueError("Une surface doit être horizontale, verticale ou à 45°")
        if dx == 0 and dy == 0:
            raise ValueError("Un segment ne peut pas être vide")

    @property
    def slope(self) -> str:
        dx = self.end.x - self.start.x
        dy = self.end.y - self.start.y
        if dx == 0:
            return "vertical"
        if dy == 0:
            return "horizontal"
        return "backslash" if dx * dy > 0 else "slash"


@dataclass(frozen=True)
class Polygon:
    vertices: tuple[Point, ...]

    def __post_init__(self) -> None:
        if len(self.vertices) < 3:
            raise ValueError("Un polygone doit avoir au moins trois sommets")
        for segment in self.segments:
            segment.__post_init__()

    @property
    def segments(self) -> tuple[Segment, ...]:
        return tuple(
            Segment(self.vertices[index], self.vertices[(index + 1) % len(self.vertices)])
            for index in range(len(self.vertices))
        )


def doubled_polygon(*vertices: tuple[int, int]) -> Polygon:
    """Construit un polygone depuis des coordonnées logiques de grille."""

    return Polygon(tuple(Point(2 * x, 2 * y) for x, y in vertices))
