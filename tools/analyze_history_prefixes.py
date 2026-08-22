from math import prod

from orapa_assistant.domain_filter import PlacementDomain, apply_exact_observation_filters
from orapa_assistant.examples import REAL_GAME_HISTORY
from orapa_assistant.pieces import PIECES, placements


base = tuple(PlacementDomain(piece.name, placements(piece)) for piece in PIECES)
for count in range(len(REAL_GAME_HISTORY) + 1):
    domains = apply_exact_observation_filters(base, REAL_GAME_HISTORY[:count])
    sizes = [len(domain.placements) for domain in domains]
    print(f"{count:>2} observations : {prod(sizes):>14,}  {sizes}")
