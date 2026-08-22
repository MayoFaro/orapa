from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from .colors import BaseColor, RayColor, mix_colors
from .geometry import Point, Polygon, Segment

BOARD_WIDTH = 20
BOARD_HEIGHT = 16


class Direction(str, Enum):
    NORTH = "north"
    SOUTH = "south"
    EAST = "east"
    WEST = "west"


@dataclass(frozen=True)
class Gem:
    color: BaseColor | None
    polygon: Polygon
    name: str = ""
    absorbs: bool = False


@dataclass(frozen=True)
class Configuration:
    gems: tuple[Gem, ...]


@dataclass(frozen=True)
class Interaction:
    point: Point
    gem_name: str
    color: BaseColor
    incoming: Direction
    outgoing: Direction


@dataclass(frozen=True)
class RayOutcome:
    exit_point: str | None
    color: RayColor | None
    absorbed: bool = False

    @classmethod
    def absorption(cls) -> "RayOutcome":
        return cls(None, None, True)


@dataclass(frozen=True)
class RayTrace:
    outcome: RayOutcome
    interactions: tuple[Interaction, ...]


def _entry_state(entry: str) -> tuple[Point, Direction]:
    if entry.isdigit():
        number = int(entry)
        if 1 <= number <= 10:
            return Point(2 * number - 1, -1), Direction.SOUTH
        if 11 <= number <= 18:
            return Point(BOARD_WIDTH + 1, 2 * (number - 10) - 1), Direction.WEST
    if len(entry) == 1 and "A" <= entry <= "H":
        return Point(-1, 2 * (ord(entry) - ord("A")) + 1), Direction.EAST
    if len(entry) == 1 and "I" <= entry <= "R":
        return Point(2 * (ord(entry) - ord("I")) + 1, BOARD_HEIGHT + 1), Direction.NORTH
    raise ValueError(f"Point de bord inconnu : {entry!r}")


def _exit_point(position: Point, direction: Direction) -> str:
    if direction == Direction.NORTH:
        return str((position.x + 1) // 2)
    if direction == Direction.SOUTH:
        return chr(ord("I") + (position.x - 1) // 2)
    if direction == Direction.WEST:
        return chr(ord("A") + (position.y - 1) // 2)
    return str(11 + (position.y - 1) // 2)


def _distance_to_segment(position: Point, direction: Direction, segment: Segment) -> int | None:
    x, y = position.x, position.y
    x1, y1 = segment.start.x, segment.start.y
    x2, y2 = segment.end.x, segment.end.y

    if direction in (Direction.EAST, Direction.WEST):
        if segment.slope == "horizontal":
            return None
        if segment.slope == "vertical":
            hit_x = x1
            if not min(y1, y2) <= y <= max(y1, y2):
                return None
        else:
            sign = 1 if segment.slope == "backslash" else -1
            hit_x = x1 + sign * (y - y1)
            if not min(x1, x2) <= hit_x <= max(x1, x2):
                return None
        distance = hit_x - x if direction == Direction.EAST else x - hit_x
    else:
        if segment.slope == "vertical":
            return None
        if segment.slope == "horizontal":
            hit_y = y1
            if not min(x1, x2) <= x <= max(x1, x2):
                return None
        else:
            sign = 1 if segment.slope == "backslash" else -1
            hit_y = y1 + sign * (x - x1)
            if not min(y1, y2) <= hit_y <= max(y1, y2):
                return None
        distance = hit_y - y if direction == Direction.SOUTH else y - hit_y

    return distance if distance > 0 else None


def _advance(point: Point, direction: Direction, distance: int) -> Point:
    dx, dy = {
        Direction.NORTH: (0, -1),
        Direction.SOUTH: (0, 1),
        Direction.EAST: (1, 0),
        Direction.WEST: (-1, 0),
    }[direction]
    return Point(point.x + dx * distance, point.y + dy * distance)


def _reflect(direction: Direction, surface: Segment) -> Direction:
    reflections = {
        "horizontal": {
            Direction.NORTH: Direction.SOUTH,
            Direction.SOUTH: Direction.NORTH,
        },
        "vertical": {
            Direction.EAST: Direction.WEST,
            Direction.WEST: Direction.EAST,
        },
        "backslash": {
            Direction.EAST: Direction.SOUTH,
            Direction.SOUTH: Direction.EAST,
            Direction.WEST: Direction.NORTH,
            Direction.NORTH: Direction.WEST,
        },
        "slash": {
            Direction.EAST: Direction.NORTH,
            Direction.NORTH: Direction.EAST,
            Direction.WEST: Direction.SOUTH,
            Direction.SOUTH: Direction.WEST,
        },
    }
    try:
        return reflections[surface.slope][direction]
    except KeyError as error:
        raise ValueError("Le rayon est colinéaire à une surface") from error


def simulate_ray(configuration: Configuration, entry_point: str) -> RayTrace:
    position, direction = _entry_state(entry_point.upper())
    encountered: set[BaseColor] = set()
    interactions: list[Interaction] = []
    visited: set[tuple[Point, Direction]] = set()

    while True:
        state = (position, direction)
        if state in visited:
            raise RuntimeError("Le rayon est enfermé dans un cycle")
        visited.add(state)

        hits: list[tuple[int, Gem, Segment]] = []
        for gem in configuration.gems:
            for segment in gem.polygon.segments:
                distance = _distance_to_segment(position, direction, segment)
                if distance is not None:
                    hits.append((distance, gem, segment))

        if not hits:
            return RayTrace(
                outcome=RayOutcome(_exit_point(position, direction), mix_colors(encountered)),
                interactions=tuple(interactions),
            )

        nearest = min(distance for distance, _, _ in hits)
        nearest_hits = [(gem, segment) for distance, gem, segment in hits if distance == nearest]
        if any(gem.absorbs for gem, _ in nearest_hits):
            return RayTrace(
                outcome=RayOutcome.absorption(),
                interactions=tuple(interactions),
            )
        outgoing = {_reflect(direction, segment) for _, segment in nearest_hits}
        if len(outgoing) != 1:
            raise RuntimeError("Collision ambiguë entre plusieurs surfaces")

        hit_point = _advance(position, direction, nearest)
        new_direction = outgoing.pop()
        for gem, _ in nearest_hits:
            if gem.color is not None:
                encountered.add(gem.color)
            if gem.color is not None:
                interactions.append(
                    Interaction(hit_point, gem.name, gem.color, direction, new_direction)
                )
        position = hit_point
        direction = new_direction
