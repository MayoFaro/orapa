"""Generic finite-domain relational constraint solver.

The module deliberately contains no Orapa-specific knowledge.  A problem is made
of variables, finite domains and constraints able to answer one question:
whether a candidate value still has a support in the current domains.  This is
enough to provide generalized arc consistency, bounded model search and proofs
of a value by looking for a counterexample.

The implementation favours a small, explicit API over a modelling language.  A
specialised caller can use :class:`SupportConstraint` to avoid materialising a
large relation, while small relations can use :class:`ExtensionalConstraint`.
"""

from __future__ import annotations

from collections import defaultdict, deque
from dataclasses import dataclass, field
from itertools import product
from types import MappingProxyType
from typing import (
    Callable,
    Generic,
    Hashable,
    Iterable,
    Mapping,
    Protocol,
    TypeVar,
)


VariableT = TypeVar("VariableT", bound=Hashable)
ValueT = TypeVar("ValueT", bound=Hashable)

__all__ = [
    "Constraint",
    "ExtensionalConstraint",
    "ModelSearchResult",
    "PredicateConstraint",
    "PropagationResult",
    "RelationalCSP",
    "SupportConstraint",
    "ValueProof",
]


class Constraint(Protocol[VariableT, ValueT]):
    """Protocol implemented by every relation understood by the solver."""

    scope: tuple[VariableT, ...]

    def has_support(
        self,
        variable: VariableT,
        value: ValueT,
        domains: Mapping[VariableT, tuple[ValueT, ...]],
    ) -> bool:
        """Return whether ``value`` participates in a currently possible tuple."""


def _normalise_scope(scope: Iterable[VariableT]) -> tuple[VariableT, ...]:
    normalised = tuple(scope)
    if not normalised:
        raise ValueError("a constraint must contain at least one variable")
    if len(set(normalised)) != len(normalised):
        raise ValueError("a constraint scope cannot repeat a variable")
    return normalised


@dataclass(frozen=True)
class ExtensionalConstraint(Generic[VariableT, ValueT]):
    """A relation represented by the complete collection of its allowed tuples.

    Tuple values follow the order of :attr:`scope`.  An index is built once, so
    propagation considers only tuples containing the candidate being revised.
    """

    scope: tuple[VariableT, ...]
    allowed_tuples: tuple[tuple[ValueT, ...], ...]
    _supports: Mapping[tuple[VariableT, ValueT], tuple[tuple[ValueT, ...], ...]] = (
        field(init=False, repr=False, compare=False)
    )

    def __init__(
        self,
        scope: Iterable[VariableT],
        allowed_tuples: Iterable[Iterable[ValueT]],
    ) -> None:
        normalised_scope = _normalise_scope(scope)
        normalised_tuples = tuple(tuple(values) for values in allowed_tuples)
        arity = len(normalised_scope)
        if any(len(values) != arity for values in normalised_tuples):
            raise ValueError("every allowed tuple must have the constraint arity")

        index: dict[
            tuple[VariableT, ValueT], list[tuple[ValueT, ...]]
        ] = defaultdict(list)
        for values in normalised_tuples:
            for variable, value in zip(normalised_scope, values):
                index[(variable, value)].append(values)

        object.__setattr__(self, "scope", normalised_scope)
        object.__setattr__(self, "allowed_tuples", normalised_tuples)
        object.__setattr__(
            self,
            "_supports",
            MappingProxyType(
                {key: tuple(supports) for key, supports in index.items()}
            ),
        )

    def has_support(
        self,
        variable: VariableT,
        value: ValueT,
        domains: Mapping[VariableT, tuple[ValueT, ...]],
    ) -> bool:
        if variable not in self.scope:
            raise ValueError(f"{variable!r} is not in this constraint's scope")
        for values in self._supports.get((variable, value), ()):
            if all(
                tuple_value in domains[tuple_variable]
                for tuple_variable, tuple_value in zip(self.scope, values)
            ):
                return True
        return False


@dataclass(frozen=True, eq=False)
class PredicateConstraint(Generic[VariableT, ValueT]):
    """A relation defined by a predicate over complete tuples.

    This convenience constraint enumerates the current Cartesian product when it
    searches for a support.  It is intended for small relations.  Large or
    structured relations should use :class:`SupportConstraint` instead.
    """

    scope: tuple[VariableT, ...]
    predicate: Callable[..., bool] = field(repr=False, compare=False)

    def __init__(
        self,
        scope: Iterable[VariableT],
        predicate: Callable[..., bool],
    ) -> None:
        object.__setattr__(self, "scope", _normalise_scope(scope))
        object.__setattr__(self, "predicate", predicate)

    def has_support(
        self,
        variable: VariableT,
        value: ValueT,
        domains: Mapping[VariableT, tuple[ValueT, ...]],
    ) -> bool:
        if variable not in self.scope:
            raise ValueError(f"{variable!r} is not in this constraint's scope")
        candidates = tuple(
            (value,) if scoped_variable == variable else domains[scoped_variable]
            for scoped_variable in self.scope
        )
        return any(self.predicate(*values) for values in product(*candidates))


SupportFinder = Callable[
    [VariableT, ValueT, Mapping[VariableT, tuple[ValueT, ...]]], bool
]


@dataclass(frozen=True, eq=False)
class SupportConstraint(Generic[VariableT, ValueT]):
    """A relation backed by a specialised support-finding function.

    The callback receives the revised variable, its candidate value and an
    immutable view of every current domain in the constraint's scope.  It must
    return ``True`` exactly when a complete tuple satisfying this relation
    exists in those domains.
    """

    scope: tuple[VariableT, ...]
    support_finder: SupportFinder[VariableT, ValueT] = field(
        repr=False, compare=False
    )

    def __init__(
        self,
        scope: Iterable[VariableT],
        support_finder: SupportFinder[VariableT, ValueT],
    ) -> None:
        object.__setattr__(self, "scope", _normalise_scope(scope))
        object.__setattr__(self, "support_finder", support_finder)

    def has_support(
        self,
        variable: VariableT,
        value: ValueT,
        domains: Mapping[VariableT, tuple[ValueT, ...]],
    ) -> bool:
        if variable not in self.scope:
            raise ValueError(f"{variable!r} is not in this constraint's scope")
        scoped_domains = MappingProxyType(
            {scoped_variable: domains[scoped_variable] for scoped_variable in self.scope}
        )
        return self.support_finder(variable, value, scoped_domains)


@dataclass(frozen=True)
class PropagationResult(Generic[VariableT, ValueT]):
    """Domains at the propagation fixed point, or at the first contradiction."""

    domains: Mapping[VariableT, tuple[ValueT, ...]]
    consistent: bool
    removed_values: int
    revised_arcs: int


@dataclass(frozen=True)
class ModelSearchResult(Generic[VariableT, ValueT]):
    """Models found by a bounded depth-first search.

    ``exhausted`` is true only if the complete remaining search tree was
    inspected.  When ``limit_reached`` is true, more models may exist.
    """

    models: tuple[Mapping[VariableT, ValueT], ...]
    exhausted: bool
    limit_reached: bool
    visited_nodes: int
    propagation_count: int


@dataclass(frozen=True)
class ValueProof(Generic[VariableT, ValueT]):
    """Proof status for the proposition ``variable == value``.

    A forced value is established by both a witness and the absence of any
    counterexample.  If neither exists, the whole problem (under the supplied
    restrictions) is inconsistent.
    """

    variable: VariableT
    value: ValueT
    consistent: bool
    possible: bool
    forced: bool
    witness: Mapping[VariableT, ValueT] | None
    counterexample: Mapping[VariableT, ValueT] | None


class RelationalCSP(Generic[VariableT, ValueT]):
    """Mutable problem definition with immutable propagation/search results."""

    def __init__(self) -> None:
        self._domains: dict[VariableT, tuple[ValueT, ...]] = {}
        self._constraints: list[Constraint[VariableT, ValueT]] = []
        self._neighbours: dict[VariableT, list[int]] = defaultdict(list)

    @property
    def variables(self) -> tuple[VariableT, ...]:
        return tuple(self._domains)

    @property
    def domains(self) -> Mapping[VariableT, tuple[ValueT, ...]]:
        return MappingProxyType(dict(self._domains))

    @property
    def constraints(self) -> tuple[Constraint[VariableT, ValueT], ...]:
        return tuple(self._constraints)

    def add_variable(
        self, variable: VariableT, domain: Iterable[ValueT]
    ) -> RelationalCSP[VariableT, ValueT]:
        if variable in self._domains:
            raise ValueError(f"variable {variable!r} already exists")

        values = tuple(dict.fromkeys(domain))
        if not values:
            raise ValueError("a variable must have a non-empty finite domain")
        self._domains[variable] = values
        return self

    def add_constraint(
        self, constraint: Constraint[VariableT, ValueT]
    ) -> RelationalCSP[VariableT, ValueT]:
        _normalise_scope(constraint.scope)
        unknown = tuple(
            variable
            for variable in constraint.scope
            if variable not in self._domains
        )
        if unknown:
            raise ValueError(f"constraint refers to unknown variables: {unknown!r}")

        constraint_index = len(self._constraints)
        self._constraints.append(constraint)
        for variable in constraint.scope:
            self._neighbours[variable].append(constraint_index)
        return self

    def propagate(
        self,
        restrictions: Mapping[VariableT, Iterable[ValueT]] | None = None,
    ) -> PropagationResult[VariableT, ValueT]:
        """Enforce generalized arc consistency until a fixed point is reached."""

        domains = self._initial_domains(restrictions)
        return self._propagate_domains(domains)

    def solve(
        self,
        *,
        limit: int | None = None,
        restrictions: Mapping[VariableT, Iterable[ValueT]] | None = None,
    ) -> ModelSearchResult[VariableT, ValueT]:
        """Find all models, or at most ``limit`` models.

        Search uses MRV with a degree tie-breaker and propagates after every
        branch assignment.  ``limit=1``, ``2`` or any other positive integer is
        supported; ``None`` requests exhaustive enumeration.
        """

        if limit is not None and limit <= 0:
            raise ValueError("the model limit must be a positive integer")

        root = self.propagate(restrictions)
        propagation_count = 1
        visited_nodes = 0
        models: list[Mapping[VariableT, ValueT]] = []
        stopped_early = False

        if not root.consistent:
            return ModelSearchResult((), True, False, 0, propagation_count)

        variable_order = {
            variable: index for index, variable in enumerate(self._domains)
        }

        def select_variable(
            domains: Mapping[VariableT, tuple[ValueT, ...]],
        ) -> VariableT | None:
            undecided = tuple(
                variable for variable, values in domains.items() if len(values) > 1
            )
            if not undecided:
                return None
            return min(
                undecided,
                key=lambda variable: (
                    len(domains[variable]),
                    -len(self._neighbours[variable]),
                    variable_order[variable],
                ),
            )

        def visit(domains: Mapping[VariableT, tuple[ValueT, ...]]) -> None:
            nonlocal propagation_count, stopped_early, visited_nodes
            if limit is not None and len(models) >= limit:
                stopped_early = True
                return

            visited_nodes += 1
            variable = select_variable(domains)
            if variable is None:
                models.append(
                    MappingProxyType(
                        {name: values[0] for name, values in domains.items()}
                    )
                )
                return

            for value in domains[variable]:
                if limit is not None and len(models) >= limit:
                    stopped_early = True
                    return
                branch_domains = dict(domains)
                branch_domains[variable] = (value,)
                propagated = self._propagate_domains(branch_domains)
                propagation_count += 1
                if propagated.consistent:
                    visit(propagated.domains)

        visit(root.domains)
        return ModelSearchResult(
            tuple(models),
            not stopped_early,
            stopped_early,
            visited_nodes,
            propagation_count,
        )

    def find_model(
        self,
        restrictions: Mapping[VariableT, Iterable[ValueT]] | None = None,
    ) -> Mapping[VariableT, ValueT] | None:
        """Return one model, if one exists."""

        result = self.solve(limit=1, restrictions=restrictions)
        return result.models[0] if result.models else None

    def find_counterexample(
        self,
        variable: VariableT,
        value: ValueT,
        restrictions: Mapping[VariableT, Iterable[ValueT]] | None = None,
    ) -> Mapping[VariableT, ValueT] | None:
        """Find a model in which ``variable`` does not equal ``value``."""

        normalised = self._normalise_restrictions(restrictions)
        allowed = tuple(
            candidate
            for candidate in self._restricted_domain(variable, normalised)
            if candidate != value
        )
        normalised[variable] = allowed
        return self.find_model(normalised)

    def prove_value(
        self,
        variable: VariableT,
        value: ValueT,
        restrictions: Mapping[VariableT, Iterable[ValueT]] | None = None,
    ) -> ValueProof[VariableT, ValueT]:
        """Prove or refute a value by searching both sides of the proposition."""

        normalised = self._normalise_restrictions(restrictions)
        current_domain = self._restricted_domain(variable, normalised)

        with_value = dict(normalised)
        with_value[variable] = (value,) if value in current_domain else ()
        witness = self.find_model(with_value)

        without_value = dict(normalised)
        without_value[variable] = tuple(
            candidate for candidate in current_domain if candidate != value
        )
        counterexample = self.find_model(without_value)

        possible = witness is not None
        consistent = possible or counterexample is not None
        return ValueProof(
            variable=variable,
            value=value,
            consistent=consistent,
            possible=possible,
            forced=possible and counterexample is None,
            witness=witness,
            counterexample=counterexample,
        )

    def _normalise_restrictions(
        self,
        restrictions: Mapping[VariableT, Iterable[ValueT]] | None,
    ) -> dict[VariableT, tuple[ValueT, ...]]:
        if restrictions is None:
            return {}
        unknown = tuple(
            variable for variable in restrictions if variable not in self._domains
        )
        if unknown:
            raise KeyError(f"unknown variables in restrictions: {unknown!r}")
        return {variable: tuple(values) for variable, values in restrictions.items()}

    def _restricted_domain(
        self,
        variable: VariableT,
        restrictions: Mapping[VariableT, tuple[ValueT, ...]],
    ) -> tuple[ValueT, ...]:
        if variable not in self._domains:
            raise KeyError(f"unknown variable: {variable!r}")
        if variable not in restrictions:
            return self._domains[variable]
        permitted = set(restrictions[variable])
        return tuple(value for value in self._domains[variable] if value in permitted)

    def _initial_domains(
        self,
        restrictions: Mapping[VariableT, Iterable[ValueT]] | None,
    ) -> dict[VariableT, tuple[ValueT, ...]]:
        normalised = self._normalise_restrictions(restrictions)
        return {
            variable: self._restricted_domain(variable, normalised)
            for variable in self._domains
        }

    def _propagate_domains(
        self,
        initial_domains: Mapping[VariableT, tuple[ValueT, ...]],
    ) -> PropagationResult[VariableT, ValueT]:
        domains = {
            variable: tuple(values)
            for variable, values in initial_domains.items()
        }
        if any(not values for values in domains.values()):
            return PropagationResult(
                MappingProxyType(domains), False, 0, 0
            )

        pending = deque(
            (constraint_index, variable)
            for constraint_index, constraint in enumerate(self._constraints)
            for variable in constraint.scope
        )
        queued = set(pending)
        removed_values = 0
        revised_arcs = 0

        while pending:
            constraint_index, variable = pending.popleft()
            queued.remove((constraint_index, variable))
            constraint = self._constraints[constraint_index]
            domain_view = MappingProxyType(domains)
            revised_arcs += 1
            revised = tuple(
                value
                for value in domains[variable]
                if constraint.has_support(variable, value, domain_view)
            )
            if len(revised) == len(domains[variable]):
                continue

            removed_values += len(domains[variable]) - len(revised)
            domains[variable] = revised
            if not revised:
                return PropagationResult(
                    MappingProxyType(domains),
                    False,
                    removed_values,
                    revised_arcs,
                )

            for neighbour_index in self._neighbours[variable]:
                neighbour = self._constraints[neighbour_index]
                for affected_variable in neighbour.scope:
                    arc = (neighbour_index, affected_variable)
                    if arc not in queued:
                        pending.append(arc)
                        queued.add(arc)

        return PropagationResult(
            MappingProxyType(domains), True, removed_values, revised_arcs
        )
