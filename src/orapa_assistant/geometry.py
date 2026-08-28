from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, order=True)
class Point:
    """Point en coordonnées doublées, donc toujours exactes."""

    x: int
    y: int

    def __hash__(self) -> int:
        cached = getattr(self, "_hash", None)
        if cached is None:
            cached = hash((self.x, self.y))
            object.__setattr__(self, "_hash", cached)
        return cached


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
        if dx == 0:
            slope = "vertical"
        elif dy == 0:
            slope = "horizontal"
        else:
            slope = "backslash" if dx * dy > 0 else "slash"
        object.__setattr__(self, "_slope", slope)

    @property
    def slope(self) -> str:
        return self._slope


@dataclass(frozen=True)
class Polygon:
    vertices: tuple[Point, ...]

    def __post_init__(self) -> None:
        if len(self.vertices) < 3:
            raise ValueError("Un polygone doit avoir au moins trois sommets")
        # La construction de chaque Segment valide déjà son inclinaison.
        segments = tuple(
            Segment(self.vertices[index], self.vertices[(index + 1) % len(self.vertices)])
            for index in range(len(self.vertices))
        )
        object.__setattr__(self, "_segments", segments)

    def __hash__(self) -> int:
        cached = getattr(self, "_hash", None)
        if cached is None:
            cached = hash(self.vertices)
            object.__setattr__(self, "_hash", cached)
        return cached

    @property
    def segments(self) -> tuple[Segment, ...]:
        return self._segments


def doubled_polygon(*vertices: tuple[int, int]) -> Polygon:
    """Construit un polygone depuis des coordonnées logiques de grille."""

    return Polygon(tuple(Point(2 * x, 2 * y) for x, y in vertices))
