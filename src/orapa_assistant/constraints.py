from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from functools import lru_cache

from .geometry import Point, Polygon, Segment
from .raytracer import Gem


class SpatialRelation(str, Enum):
    DISJOINT = "disjoint"
    TOUCH_POINT = "touch_point"
    TOUCH_EDGE = "touch_edge"
    OVERLAP = "overlap"


def _axes(polygon: Polygon) -> set[tuple[int, int]]:
    axes: set[tuple[int, int]] = set()
    for segment in polygon.segments:
        dx = segment.end.x - segment.start.x
        dy = segment.end.y - segment.start.y
        axis = (-dy, dx)
        if axis[0] < 0 or (axis[0] == 0 and axis[1] < 0):
            axis = (-axis[0], -axis[1])
        divisor = max(abs(axis[0]), abs(axis[1]))
        axes.add((axis[0] // divisor, axis[1] // divisor))
    return axes


def _projection(polygon: Polygon, axis: tuple[int, int]) -> tuple[int, int]:
    values = [point.x * axis[0] + point.y * axis[1] for point in polygon.vertices]
    return min(values), max(values)


def polygons_have_interior_overlap(first: Polygon, second: Polygon) -> bool:
    """Test SAT strict : un simple contact n'est pas un chevauchement."""

    for axis in _axes(first) | _axes(second):
        first_min, first_max = _projection(first, axis)
        second_min, second_max = _projection(second, axis)
        if first_max <= second_min or second_max <= first_min:
            return False
    return True


def _orientation(a: Point, b: Point, c: Point) -> int:
    value = (b.x - a.x) * (c.y - a.y) - (b.y - a.y) * (c.x - a.x)
    return (value > 0) - (value < 0)


def _on_segment(point: Point, segment: Segment) -> bool:
    return (
        _orientation(segment.start, segment.end, point) == 0
        and min(segment.start.x, segment.end.x) <= point.x <= max(segment.start.x, segment.end.x)
        and min(segment.start.y, segment.end.y) <= point.y <= max(segment.start.y, segment.end.y)
    )


def _collinear_overlap_length(first: Segment, second: Segment) -> int:
    if _orientation(first.start, first.end, second.start) != 0:
        return 0
    if _orientation(first.start, first.end, second.end) != 0:
        return 0
    if first.start.x != first.end.x:
        return max(
            0,
            min(max(first.start.x, first.end.x), max(second.start.x, second.end.x))
            - max(min(first.start.x, first.end.x), min(second.start.x, second.end.x)),
        )
    return max(
        0,
        min(max(first.start.y, first.end.y), max(second.start.y, second.end.y))
        - max(min(first.start.y, first.end.y), min(second.start.y, second.end.y)),
    )


def _segments_touch(first: Segment, second: Segment) -> bool:
    o1 = _orientation(first.start, first.end, second.start)
    o2 = _orientation(first.start, first.end, second.end)
    o3 = _orientation(second.start, second.end, first.start)
    o4 = _orientation(second.start, second.end, first.end)
    if o1 != o2 and o3 != o4:
        return True
    return (
        (o1 == 0 and _on_segment(second.start, first))
        or (o2 == 0 and _on_segment(second.end, first))
        or (o3 == 0 and _on_segment(first.start, second))
        or (o4 == 0 and _on_segment(first.end, second))
    )


def polygon_relation(first: Polygon, second: Polygon) -> SpatialRelation:
    if polygons_have_interior_overlap(first, second):
        return SpatialRelation.OVERLAP
    touches = False
    for first_segment in first.segments:
        for second_segment in second.segments:
            if _collinear_overlap_length(first_segment, second_segment) > 0:
                return SpatialRelation.TOUCH_EDGE
            touches = touches or _segments_touch(first_segment, second_segment)
    return SpatialRelation.TOUCH_POINT if touches else SpatialRelation.DISJOINT


@lru_cache(maxsize=500_000)
def gems_are_compatible(first: Gem, second: Gem) -> bool:
    relation = polygon_relation(first.polygon, second.polygon)
    if relation in (SpatialRelation.DISJOINT, SpatialRelation.TOUCH_POINT):
        return True
    if relation != SpatialRelation.TOUCH_EDGE:
        return False
    # Une arête commune sur une ligne de grille sépare deux cases et reste
    # légale. Une diagonale commune à l'intérieur d'une case ferait en revanche
    # occuper cette même case par deux pierres, réponse que le jeu ne prévoit pas.
    return not any(
        first_segment.slope in ("slash", "backslash")
        and _collinear_overlap_length(first_segment, second_segment) > 0
        for first_segment in first.polygon.segments
        for second_segment in second.polygon.segments
    )


@dataclass(frozen=True)
class CompatibilityIndex:
    """Pour chaque placement gauche, bitset des placements droits compatibles."""

    left_name: str
    right_name: str
    masks: tuple[int, ...]
    right_count: int

    def compatible_indices(self, left_index: int) -> tuple[int, ...]:
        mask = self.masks[left_index]
        return tuple(index for index in range(self.right_count) if mask & (1 << index))

    @property
    def compatible_pair_count(self) -> int:
        return sum(mask.bit_count() for mask in self.masks)


def build_compatibility_index(
    left_name: str,
    left: tuple[Gem, ...],
    right_name: str,
    right: tuple[Gem, ...],
) -> CompatibilityIndex:
    masks: list[int] = []
    for left_gem in left:
        mask = 0
        for index, right_gem in enumerate(right):
            if gems_are_compatible(left_gem, right_gem):
                mask |= 1 << index
        masks.append(mask)
    return CompatibilityIndex(left_name, right_name, tuple(masks), len(right))
