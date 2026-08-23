from orapa_assistant.constraints import (
    SpatialRelation,
    build_compatibility_index,
    gems_are_compatible,
    polygon_relation,
)
from orapa_assistant.colors import BaseColor
from orapa_assistant.geometry import doubled_polygon
from orapa_assistant.raytracer import Gem


def test_polygon_relations_distinguish_overlap_and_legal_contacts() -> None:
    square = doubled_polygon((0, 0), (1, 0), (1, 1), (0, 1))
    overlap = doubled_polygon((0, 0), (1, 0), (1, 1), (0, 1))
    edge = doubled_polygon((1, 0), (2, 0), (2, 1), (1, 1))
    point = doubled_polygon((1, 1), (2, 1), (2, 2), (1, 2))
    distant = doubled_polygon((3, 0), (4, 0), (4, 1), (3, 1))

    assert polygon_relation(square, overlap) == SpatialRelation.OVERLAP
    assert polygon_relation(square, edge) == SpatialRelation.TOUCH_EDGE
    assert polygon_relation(square, point) == SpatialRelation.TOUCH_POINT
    assert polygon_relation(square, distant) == SpatialRelation.DISJOINT


def test_complementary_triangles_cannot_share_a_diagonal() -> None:
    first = doubled_polygon((0, 0), (1, 0), (1, 1))
    second = doubled_polygon((0, 0), (1, 1), (0, 1))
    assert polygon_relation(first, second) == SpatialRelation.TOUCH_EDGE
    left = Gem(BaseColor.WHITE, first, "left")
    right = Gem(BaseColor.RED, second, "right")
    assert not gems_are_compatible(left, right)


def test_pieces_can_share_an_edge_along_a_grid_line() -> None:
    left = Gem(
        BaseColor.WHITE,
        doubled_polygon((0, 0), (1, 0), (1, 1), (0, 1)),
        "left",
    )
    right = Gem(
        BaseColor.RED,
        doubled_polygon((1, 0), (2, 0), (2, 1), (1, 1)),
        "right",
    )

    assert polygon_relation(left.polygon, right.polygon) == SpatialRelation.TOUCH_EDGE
    assert gems_are_compatible(left, right)


def test_contact_at_one_point_remains_legal() -> None:
    first = Gem(
        BaseColor.WHITE,
        doubled_polygon((0, 0), (1, 0), (1, 1), (0, 1)),
        "first",
    )
    second = Gem(
        BaseColor.RED,
        doubled_polygon((1, 1), (2, 1), (2, 2), (1, 2)),
        "second",
    )
    assert gems_are_compatible(first, second)


def test_compatibility_index_uses_bitsets() -> None:
    left = (
        Gem(BaseColor.RED, doubled_polygon((0, 0), (1, 0), (1, 1)), "left"),
    )
    right = (
        Gem(BaseColor.BLUE, doubled_polygon((0, 0), (1, 0), (1, 1)), "overlap"),
        Gem(BaseColor.BLUE, doubled_polygon((2, 0), (3, 0), (3, 1)), "apart"),
    )
    index = build_compatibility_index("left", left, "right", right)
    assert index.compatible_indices(0) == (1,)
    assert index.compatible_pair_count == 1
    assert not gems_are_compatible(left[0], right[0])
