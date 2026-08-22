from itertools import combinations

from orapa_assistant.constraints import build_compatibility_index
from orapa_assistant.pieces import PIECES, placements


catalogues = {piece.name: placements(piece) for piece in PIECES}
for left_piece, right_piece in combinations(PIECES, 2):
    left = catalogues[left_piece.name]
    right = catalogues[right_piece.name]
    index = build_compatibility_index(left_piece.name, left, right_piece.name, right)
    total = len(left) * len(right)
    compatible = index.compatible_pair_count
    print(
        f"{left_piece.name:16} × {right_piece.name:16} "
        f"{compatible:>6}/{total:<6} ({compatible / total:6.1%})"
    )
