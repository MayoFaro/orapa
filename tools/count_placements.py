from math import prod

from orapa_assistant.pieces import PIECES, placements


counts = {piece.name: len(placements(piece)) for piece in PIECES}
for name, count in counts.items():
    print(f"{name:16} {count:>5}")
print(f"Produit brut     {prod(counts.values()):>14,}")
