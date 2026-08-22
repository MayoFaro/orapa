from orapa_assistant.colors import RayColor
from orapa_assistant.domain_filter import (
    PlacementDomain,
    apply_exact_unary_observations,
    apply_transparent_observations,
)
from orapa_assistant.pieces import PIECES, placements
from orapa_assistant.solver import Observation


def test_real_transparent_waves_reduce_every_piece_domain() -> None:
    domains = tuple(PlacementDomain(piece.name, placements(piece)) for piece in PIECES)
    filtered = apply_transparent_observations(
        domains,
        (
            Observation("H", "18", RayColor.TRANSPARENT),
            Observation("7", "O", RayColor.TRANSPARENT),
        ),
    )
    before = {domain.piece_name: len(domain.placements) for domain in domains}
    after = {domain.piece_name: len(domain.placements) for domain in filtered}
    assert all(after[name] < before[name] for name in before)
    assert after == {
        "white_diamond": 42,
        "blue": 92,
        "red": 160,
        "yellow": 168,
        "white_triangle": 92,
    }


def test_real_single_color_waves_determine_small_colored_domains() -> None:
    domains = tuple(PlacementDomain(piece.name, placements(piece)) for piece in PIECES)
    observations = (
        Observation("H", "18", RayColor.TRANSPARENT),
        Observation("7", "O", RayColor.TRANSPARENT),
        Observation("E", "E", RayColor.YELLOW),
        Observation("9", "16", RayColor.YELLOW),
        Observation("8", "12", RayColor.RED),
        Observation("13", "13", RayColor.RED),
        Observation("D", "D", RayColor.BLUE),
    )
    filtered = apply_exact_unary_observations(domains, observations)
    after = {domain.piece_name: len(domain.placements) for domain in filtered}
    assert after == {
        "white_diamond": 42,
        "blue": 28,
        "red": 1,
        "yellow": 1,
        "white_triangle": 92,
    }
