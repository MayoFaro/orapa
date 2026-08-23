"""Témoins symboliques exacts pour les observations d'ondes.

Le module ne construit jamais le produit cartésien des grilles.  Un témoin est
une boîte de bitsets : pour chaque variable-pièce, il contient les placements
qui peuvent être choisis librement tout en conservant exactement le même trajet
et le même résultat.  Les contraintes spatiales entre pierres restent des
contraintes CSP séparées.

La recherche est paresseuse et tri-état.  Une limite de nœuds ou une annulation
renvoie ``UNKNOWN`` ; seul ``IMPOSSIBLE`` constitue une preuve d'absence de
support.
"""

from __future__ import annotations

from collections.abc import Callable, Iterable, Mapping, Sequence
from dataclasses import dataclass
from enum import Enum

from .colors import BaseColor, RAY_COLOR_COMPONENTS
from .geometry import Point
from .raytracer import (
    Direction,
    Gem,
    RayOutcome,
    advance_ray,
    first_local_hit,
    ray_entry_state,
    ray_exit_point,
)


_COLOR_BITS = {
    color: 1 << index for index, color in enumerate(BaseColor)
}


class WitnessSearchStatus(str, Enum):
    FOUND = "found"
    IMPOSSIBLE = "impossible"
    UNKNOWN = "unknown"


@dataclass(frozen=True)
class RayWitnessLeg:
    """Un événement canonique du trajet représenté par un témoin."""

    position: Point
    incoming: Direction
    distance: int
    hit_point: Point
    actor: str
    outgoing: Direction | None
    absorbed: bool = False


@dataclass(frozen=True)
class RayWitness:
    """Produit de domaines dont chaque tuple reproduit l'observation."""

    allowed_masks: tuple[int, ...]
    legs: tuple[RayWitnessLeg, ...]
    exit_point: str | None
    absorbed: bool

    def mask_for(self, catalog: PlacementCatalog, piece_name: str) -> int:
        return self.allowed_masks[catalog.piece_index(piece_name)]

    def values_for(
        self, catalog: PlacementCatalog, piece_name: str
    ) -> tuple[Gem, ...]:
        return catalog.values_from_mask(
            piece_name, self.mask_for(catalog, piece_name)
        )


@dataclass(frozen=True)
class WitnessSearchResult:
    status: WitnessSearchStatus
    witness: RayWitness | None
    explored_nodes: int
    cycle_prunes: int = 0
    reason: str | None = None

    @property
    def definitive(self) -> bool:
        return self.status != WitnessSearchStatus.UNKNOWN


class PlacementCatalog:
    """Catalogue immuable de valeurs et conversion rapide vers des bitsets."""

    def __init__(self, pieces: Mapping[str, Iterable[Gem]]) -> None:
        if not pieces:
            raise ValueError("un catalogue doit contenir au moins une pièce")
        self.names = tuple(pieces)
        if len(set(self.names)) != len(self.names):
            raise ValueError("les noms de pièces doivent être uniques")
        self.placements = tuple(tuple(pieces[name]) for name in self.names)
        if any(not values for values in self.placements):
            raise ValueError("chaque pièce doit avoir au moins un placement")
        if any(len(set(values)) != len(values) for values in self.placements):
            raise ValueError("les placements d'une pièce doivent être uniques")

        self._name_indices = {
            name: index for index, name in enumerate(self.names)
        }
        self._value_indices = tuple(
            {gem: index for index, gem in enumerate(values)}
            for values in self.placements
        )
        self.full_masks = tuple(
            (1 << len(values)) - 1 for values in self.placements
        )

        colors: list[BaseColor | None] = []
        absorbs: list[bool] = []
        for name, values in zip(self.names, self.placements):
            piece_colors = {gem.color for gem in values}
            piece_absorptions = {gem.absorbs for gem in values}
            if len(piece_colors) != 1 or len(piece_absorptions) != 1:
                raise ValueError(
                    f"la variable {name!r} mélange plusieurs types de pierres"
                )
            colors.append(next(iter(piece_colors)))
            absorbs.append(next(iter(piece_absorptions)))
        self.colors = tuple(colors)
        self.absorbs = tuple(absorbs)
        self.color_bits = tuple(
            0 if color is None else _COLOR_BITS[color] for color in self.colors
        )

    def __len__(self) -> int:
        return len(self.names)

    def piece_index(self, piece_name: str) -> int:
        try:
            return self._name_indices[piece_name]
        except KeyError as error:
            raise KeyError(f"pièce inconnue : {piece_name!r}") from error

    def value_index(self, piece_name: str, gem: Gem) -> int:
        piece_index = self.piece_index(piece_name)
        try:
            return self._value_indices[piece_index][gem]
        except KeyError as error:
            raise ValueError(
                f"placement absent du catalogue pour {piece_name!r}"
            ) from error

    def values_from_mask(self, piece_name: str, mask: int) -> tuple[Gem, ...]:
        piece_index = self.piece_index(piece_name)
        values = self.placements[piece_index]
        return tuple(
            value for index, value in enumerate(values) if mask & (1 << index)
        )

    def masks_from_domains(
        self,
        domains: Mapping[str, Iterable[Gem]] | None = None,
    ) -> tuple[int, ...]:
        if domains is None:
            return self.full_masks
        missing = tuple(name for name in self.names if name not in domains)
        unknown = tuple(name for name in domains if name not in self._name_indices)
        if missing or unknown:
            raise KeyError(
                f"domaines incomplets (manquants={missing!r}, inconnus={unknown!r})"
            )
        masks: list[int] = []
        for piece_index, name in enumerate(self.names):
            mask = 0
            indices = self._value_indices[piece_index]
            for gem in domains[name]:
                try:
                    mask |= 1 << indices[gem]
                except KeyError as error:
                    raise ValueError(
                        f"placement absent du catalogue pour {name!r}"
                    ) from error
            masks.append(mask)
        return tuple(masks)


class StateHitIndex:
    """Bitsets des premiers impacts d'une pièce depuis un état du rayon."""

    def __init__(
        self,
        *,
        no_hit_mask: int,
        exact_at: Mapping[int, int],
        reflecting_at: Mapping[tuple[int, Direction], int],
        absorbing_at: Mapping[int, int],
    ) -> None:
        self.no_hit_mask = no_hit_mask
        self.exact_at = dict(exact_at)
        self.reflecting_at = dict(reflecting_at)
        self.absorbing_at = dict(absorbing_at)
        self.distances = tuple(sorted(self.exact_at))
        self._strict_after_cache: dict[int, int] = {}
        self._not_before_cache: dict[int, int] = {}

    def strict_after(self, distance: int) -> int:
        if distance not in self._strict_after_cache:
            mask = self.no_hit_mask
            for hit_distance, exact_mask in self.exact_at.items():
                if hit_distance > distance:
                    mask |= exact_mask
            self._strict_after_cache[distance] = mask
        return self._strict_after_cache[distance]

    def not_before(self, distance: int) -> int:
        if distance not in self._not_before_cache:
            mask = self.no_hit_mask
            for hit_distance, exact_mask in self.exact_at.items():
                if hit_distance >= distance:
                    mask |= exact_mask
            self._not_before_cache[distance] = mask
        return self._not_before_cache[distance]


class LocalHitIndex:
    """Index paresseux partagé par toutes les observations d'un catalogue."""

    def __init__(self, catalog: PlacementCatalog) -> None:
        self.catalog = catalog
        self._cache: dict[tuple[int, Point, Direction], StateHitIndex] = {}

    @property
    def cached_state_count(self) -> int:
        return len(self._cache)

    def for_state(
        self,
        piece_index: int,
        position: Point,
        direction: Direction,
    ) -> StateHitIndex:
        key = (piece_index, position, direction)
        cached = self._cache.get(key)
        if cached is not None:
            return cached

        no_hit_mask = 0
        exact_at: dict[int, int] = {}
        reflecting_at: dict[tuple[int, Direction], int] = {}
        absorbing_at: dict[int, int] = {}
        for value_index, gem in enumerate(self.catalog.placements[piece_index]):
            bit = 1 << value_index
            hit = first_local_hit(gem, position, direction)
            if hit is None:
                no_hit_mask |= bit
                continue
            exact_at[hit.distance] = exact_at.get(hit.distance, 0) | bit
            if hit.absorbed:
                absorbing_at[hit.distance] = (
                    absorbing_at.get(hit.distance, 0) | bit
                )
            elif len(hit.outgoing) == 1:
                outgoing = next(iter(hit.outgoing))
                signature = (hit.distance, outgoing)
                reflecting_at[signature] = reflecting_at.get(signature, 0) | bit

        result = StateHitIndex(
            no_hit_mask=no_hit_mask,
            exact_at=exact_at,
            reflecting_at=reflecting_at,
            absorbing_at=absorbing_at,
        )
        self._cache[key] = result
        return result


@dataclass(frozen=True)
class _SearchNode:
    position: Point
    direction: Direction
    colors: int
    masks: tuple[int, ...]
    visited: frozenset[tuple[Point, Direction]]
    legs: tuple[RayWitnessLeg, ...]


class RayWitnessFinder:
    """Cherche un support exact d'une observation dans des domaines finis."""

    def __init__(
        self,
        catalog: PlacementCatalog,
        entry: str,
        expected: RayOutcome,
        *,
        hit_index: LocalHitIndex | None = None,
    ) -> None:
        if expected.absorbed:
            if expected.exit_point is not None or expected.color is not None:
                raise ValueError("une absorption ne possède ni sortie ni couleur")
            target_colors = None
        else:
            if expected.exit_point is None or expected.color is None:
                raise ValueError("une onde non absorbée exige sortie et couleur")
            target_colors = sum(
                _COLOR_BITS[color]
                for color in RAY_COLOR_COMPONENTS[expected.color]
            )
        if hit_index is not None and hit_index.catalog is not catalog:
            raise ValueError("l'index d'impacts appartient à un autre catalogue")

        self.catalog = catalog
        self.entry = entry
        self.expected = expected
        self.target_colors = target_colors
        self.hit_index = hit_index or LocalHitIndex(catalog)

    def find_support(
        self,
        variable: str,
        value: Gem,
        domains: Mapping[str, Iterable[Gem]],
        *,
        max_nodes: int | None = None,
        cancelled: Callable[[], bool] | None = None,
    ) -> WitnessSearchResult:
        masks = list(self.catalog.masks_from_domains(domains))
        piece_index = self.catalog.piece_index(variable)
        value_index = self.catalog.value_index(variable, value)
        masks[piece_index] &= 1 << value_index
        return self.search_masks(
            tuple(masks), max_nodes=max_nodes, cancelled=cancelled
        )

    def search(
        self,
        domains: Mapping[str, Iterable[Gem]] | None = None,
        *,
        max_nodes: int | None = None,
        cancelled: Callable[[], bool] | None = None,
    ) -> WitnessSearchResult:
        return self.search_masks(
            self.catalog.masks_from_domains(domains),
            max_nodes=max_nodes,
            cancelled=cancelled,
        )

    def search_masks(
        self,
        masks: Sequence[int],
        *,
        max_nodes: int | None = None,
        cancelled: Callable[[], bool] | None = None,
    ) -> WitnessSearchResult:
        if max_nodes is not None and max_nodes < 0:
            raise ValueError("max_nodes doit être positif ou nul")
        domain_masks = tuple(masks)
        if len(domain_masks) != len(self.catalog):
            raise ValueError("un masque de domaine est requis par pièce")
        if any(mask < 0 for mask in domain_masks):
            raise ValueError("un masque de domaine ne peut pas être négatif")
        domain_masks = tuple(
            mask & full
            for mask, full in zip(domain_masks, self.catalog.full_masks)
        )
        if any(mask == 0 for mask in domain_masks):
            return WitnessSearchResult(
                WitnessSearchStatus.IMPOSSIBLE, None, explored_nodes=0
            )

        position, direction = ray_entry_state(self.entry)
        stack = [
            _SearchNode(
                position,
                direction,
                0,
                domain_masks,
                frozenset(),
                (),
            )
        ]
        explored_nodes = 0
        cycle_prunes = 0
        explored_states: set[
            tuple[
                Point,
                Direction,
                int,
                tuple[int, ...],
                frozenset[tuple[Point, Direction]],
            ]
        ] = set()

        while stack:
            if cancelled is not None and cancelled():
                return WitnessSearchResult(
                    WitnessSearchStatus.UNKNOWN,
                    None,
                    explored_nodes,
                    cycle_prunes,
                    "cancelled",
                )
            if max_nodes is not None and explored_nodes >= max_nodes:
                return WitnessSearchResult(
                    WitnessSearchStatus.UNKNOWN,
                    None,
                    explored_nodes,
                    cycle_prunes,
                    "node_budget",
                )

            node = stack.pop()
            explored_nodes += 1
            state = (node.position, node.direction)
            if state in node.visited:
                cycle_prunes += 1
                continue
            state_key = (
                node.position,
                node.direction,
                node.colors,
                node.masks,
                node.visited,
            )
            if state_key in explored_states:
                continue
            explored_states.add(state_key)

            state_indices = tuple(
                self.hit_index.for_state(index, node.position, node.direction)
                for index in range(len(self.catalog))
            )

            terminal = self._terminal_witness(node, state_indices)
            if terminal is not None:
                return WitnessSearchResult(
                    WitnessSearchStatus.FOUND,
                    terminal,
                    explored_nodes,
                    cycle_prunes,
                )

            visited = node.visited | {state}
            children = self._reflection_children(node, state_indices, visited)
            # Les enfants sont produits dans l'ordre heuristique souhaité.
            stack.extend(reversed(children))

        return WitnessSearchResult(
            WitnessSearchStatus.IMPOSSIBLE,
            None,
            explored_nodes,
            cycle_prunes,
        )

    def _terminal_witness(
        self,
        node: _SearchNode,
        state_indices: tuple[StateHitIndex, ...],
    ) -> RayWitness | None:
        if self.expected.absorbed:
            return self._absorption_witness(node, state_indices)

        no_hit_masks = tuple(
            mask & index.no_hit_mask
            for mask, index in zip(node.masks, state_indices)
        )
        if (
            all(no_hit_masks)
            and node.colors == self.target_colors
            and ray_exit_point(node.position, node.direction)
            == self.expected.exit_point
        ):
            return RayWitness(
                no_hit_masks,
                node.legs,
                self.expected.exit_point,
                False,
            )
        return None

    def _absorption_witness(
        self,
        node: _SearchNode,
        state_indices: tuple[StateHitIndex, ...],
    ) -> RayWitness | None:
        candidates: list[tuple[int, int, int]] = []
        for actor, (mask, index) in enumerate(zip(node.masks, state_indices)):
            if not self.catalog.absorbs[actor]:
                continue
            for distance, raw_mask in index.absorbing_at.items():
                actor_mask = mask & raw_mask
                if actor_mask:
                    candidates.append((distance, actor, actor_mask))
        candidates.sort()

        for distance, actor, actor_mask in candidates:
            allowed: list[int] = []
            for piece_index, (mask, index) in enumerate(
                zip(node.masks, state_indices)
            ):
                if piece_index == actor:
                    current = actor_mask
                elif piece_index < actor and self.catalog.absorbs[piece_index]:
                    # Canonicalise les absorbeurs simultanés.
                    current = mask & index.strict_after(distance)
                else:
                    current = mask & index.not_before(distance)
                if not current:
                    break
                allowed.append(current)
            else:
                hit_point = advance_ray(node.position, node.direction, distance)
                leg = RayWitnessLeg(
                    node.position,
                    node.direction,
                    distance,
                    hit_point,
                    self.catalog.names[actor],
                    None,
                    True,
                )
                return RayWitness(
                    tuple(allowed), node.legs + (leg,), None, True
                )
        return None

    def _reflection_children(
        self,
        node: _SearchNode,
        state_indices: tuple[StateHitIndex, ...],
        visited: frozenset[tuple[Point, Direction]],
    ) -> list[_SearchNode]:
        candidates: list[tuple[int, int, Direction, int]] = []
        for actor, (mask, index) in enumerate(zip(node.masks, state_indices)):
            if self.catalog.absorbs[actor]:
                continue
            for (distance, outgoing), raw_mask in index.reflecting_at.items():
                actor_mask = mask & raw_mask
                if not actor_mask:
                    continue
                actor_color = self.catalog.color_bits[actor]
                if (
                    self.target_colors is not None
                    and actor_color
                    and not actor_color & self.target_colors
                ):
                    continue
                candidates.append((distance, actor, outgoing, actor_mask))

        missing_colors = (
            0
            if self.target_colors is None
            else self.target_colors & ~node.colors
        )
        candidates.sort(
            key=lambda candidate: (
                not bool(self.catalog.color_bits[candidate[1]] & missing_colors),
                self.catalog.color_bits[candidate[1]] == 0,
                candidate[0],
                candidate[1],
                candidate[2].value,
            )
        )

        children: list[_SearchNode] = []
        for distance, actor, outgoing, actor_mask in candidates:
            actor_color = self.catalog.color_bits[actor]
            initial_colors = node.colors | actor_color
            if (
                self.target_colors is not None
                and initial_colors & ~self.target_colors
            ):
                continue

            branches: list[tuple[list[int], int]] = [([], initial_colors)]
            for piece_index, (mask, index) in enumerate(
                zip(node.masks, state_indices)
            ):
                late = mask & index.strict_after(distance)
                if piece_index < actor or self.catalog.absorbs[piece_index]:
                    branch_kind = "fixed"
                    fixed_mask = late
                elif piece_index == actor:
                    branch_kind = "fixed"
                    fixed_mask = actor_mask
                else:
                    tied = mask & index.reflecting_at.get(
                        (distance, outgoing), 0
                    )
                    color = self.catalog.color_bits[piece_index]
                    if self.target_colors is None or color == 0:
                        branch_kind = "fixed"
                        fixed_mask = late | tied
                    elif color & ~self.target_colors:
                        branch_kind = "fixed"
                        fixed_mask = late
                    else:
                        branch_kind = "colored_tie"
                        fixed_mask = 0

                next_branches: list[tuple[list[int], int]] = []
                for accumulated, colors in branches:
                    if branch_kind == "colored_tie":
                        # Une égalité doit être séparée tant qu'elle introduit
                        # une couleur. Une fois la couleur déjà rencontrée,
                        # retard et égalité ont exactement le même effet.
                        options = (
                            ((late | tied, 0),)
                            if colors & color
                            else ((late, 0), (tied, color))
                        )
                    else:
                        options = ((fixed_mask, 0),)
                    for option_mask, added_color in options:
                        if not option_mask:
                            continue
                        new_colors = colors | added_color
                        if (
                            self.target_colors is not None
                            and new_colors & ~self.target_colors
                        ):
                            continue
                        next_branches.append(
                            (accumulated + [option_mask], new_colors)
                        )
                branches = next_branches
                if not branches:
                    break

            if not branches:
                continue
            hit_point = advance_ray(node.position, node.direction, distance)
            leg = RayWitnessLeg(
                node.position,
                node.direction,
                distance,
                hit_point,
                self.catalog.names[actor],
                outgoing,
            )
            for masks, colors in branches:
                children.append(
                    _SearchNode(
                        hit_point,
                        outgoing,
                        colors,
                        tuple(masks),
                        visited,
                        node.legs + (leg,),
                    )
                )
        return children


__all__ = [
    "LocalHitIndex",
    "PlacementCatalog",
    "RayWitness",
    "RayWitnessFinder",
    "RayWitnessLeg",
    "StateHitIndex",
    "WitnessSearchResult",
    "WitnessSearchStatus",
]
