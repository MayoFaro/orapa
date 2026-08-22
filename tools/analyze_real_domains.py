from math import prod

from orapa_assistant.colors import RayColor
from orapa_assistant.domain_filter import PlacementDomain, apply_exact_unary_observations
from orapa_assistant.pieces import PIECES, placements
from orapa_assistant.solver import Observation


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
for before, after in zip(domains, filtered):
    print(
        f"{before.piece_name:16} {len(before.placements):>4} -> "
        f"{len(after.placements):>4} ({len(after.placements) / len(before.placements):6.1%})"
    )
print(f"Produit brut avant : {prod(len(domain.placements) for domain in domains):,}")
print(f"Produit brut après : {prod(len(domain.placements) for domain in filtered):,}")
