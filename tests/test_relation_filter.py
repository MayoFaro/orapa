from math import prod

from orapa_assistant.domain_filter import (
    PlacementDomain,
    apply_exact_observation_filters,
)
from orapa_assistant.examples import REAL_GAME_HISTORY
from orapa_assistant.pieces import PIECES, placements


def _domains():
    return tuple(PlacementDomain(piece.name, placements(piece)) for piece in PIECES)


def test_white_observations_reduce_both_white_piece_domains() -> None:
    filtered = apply_exact_observation_filters(_domains(), REAL_GAME_HISTORY[:3])
    sizes = {domain.piece_name: len(domain.placements) for domain in filtered}
    assert sizes["white_diamond"] < 63
    assert sizes["white_triangle"] < 188


def test_relational_filters_reduce_real_history_below_unary_product() -> None:
    filtered = apply_exact_observation_filters(_domains(), REAL_GAME_HISTORY)
    raw = prod(len(domain.placements) for domain in filtered)
    assert raw < 108_192
    assert all(domain.placements for domain in filtered)
