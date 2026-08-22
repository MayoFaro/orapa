from orapa_assistant.pieces import BLACK_BODY, DIAMOND, PIECES, placements, rotations


def test_rotation_and_placement_counts() -> None:
    counts = {piece.name: len(placements(piece)) for piece in PIECES}
    assert counts == {
        "white_diamond": 63,
        "blue": 188,
        "red": 248,
        "yellow": 252,
        "white_triangle": 188,
    }
    assert [len(rotations(piece)) for piece in PIECES] == [1, 4, 4, 4, 4]


def test_extension_piece_placement_counts() -> None:
    assert len(rotations(DIAMOND)) == 4
    assert len(placements(DIAMOND)) == 284
    assert len(rotations(BLACK_BODY)) == 2
    assert len(placements(BLACK_BODY)) == 142
