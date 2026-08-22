from orapa_assistant.cell_display import configuration_cell_codes
from orapa_assistant.domain_filter import PlacementDomain, apply_exact_unary_observations
from orapa_assistant.examples import REAL_GAME_HISTORY, REAL_GAME_SOLUTION
from orapa_assistant.pieces import PIECES, placements
from orapa_assistant.search import search_configurations


def test_exact_search_finds_the_real_solution() -> None:
    domains = tuple(PlacementDomain(piece.name, placements(piece)) for piece in PIECES)
    filtered = apply_exact_unary_observations(domains, REAL_GAME_HISTORY)
    result = search_configurations(filtered, REAL_GAME_HISTORY)
    assert result.raw_combination_count == 108_192
    assert len(result.configurations) == 1
    assert configuration_cell_codes(result.configurations[0]) == configuration_cell_codes(
        REAL_GAME_SOLUTION
    )
