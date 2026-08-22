from time import perf_counter

from orapa_assistant.cell_display import configuration_cell_codes
from orapa_assistant.domain_filter import PlacementDomain, apply_exact_unary_observations
from orapa_assistant.examples import REAL_GAME_HISTORY
from orapa_assistant.pieces import PIECES, placements
from orapa_assistant.search import search_configurations


started = perf_counter()
domains = tuple(PlacementDomain(piece.name, placements(piece)) for piece in PIECES)
filtered = apply_exact_unary_observations(domains, REAL_GAME_HISTORY)
result = search_configurations(filtered, REAL_GAME_HISTORY)
elapsed = perf_counter() - started

print(f"Combinaisons brutes : {result.raw_combination_count:,}")
print(f"Grilles sans chevauchement : {result.legal_configuration_count:,}")
print(f"Solutions exactes : {len(result.configurations)}")
print(f"Temps : {elapsed:.3f} s")
for configuration in result.configurations:
    print("    " + " ".join(str(number) for number in range(1, 11)))
    for row_name, cells in zip("ABCDEFGH", configuration_cell_codes(configuration)):
        print(f"{row_name}   " + " ".join(f"{cell:>3}" for cell in cells))
