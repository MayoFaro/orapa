from __future__ import annotations

from itertools import product

import pytest

from orapa_assistant.relational_csp import (
    ExtensionalConstraint,
    PredicateConstraint,
    RelationalCSP,
    SupportConstraint,
)


def test_extensional_constraints_propagate_relations_to_a_fixed_point() -> None:
    problem = RelationalCSP[str, int]()
    problem.add_variable("x", (1, 2, 3))
    problem.add_variable("y", (1, 2, 3))
    problem.add_variable("z", (1, 2, 3))
    problem.add_constraint(
        ExtensionalConstraint(("x", "y"), ((1, 1), (2, 2)))
    )
    problem.add_constraint(ExtensionalConstraint(("y", "z"), ((1, 1),)))

    result = problem.propagate()

    assert result.consistent
    assert result.domains == {"x": (1,), "y": (1,), "z": (1,)}
    assert result.removed_values == 6


def test_propagate_processes_lower_cost_constraints_first() -> None:
    # Une contrainte dont la portée touche un domaine plus petit doit être
    # révisée avant une contrainte plus coûteuse, même si celle-ci a été
    # enregistrée en premier — pour que le travail bon marché débroussaille
    # le terrain avant d'attaquer les contraintes onéreuses.
    problem = RelationalCSP[str, int]()
    problem.add_variable("large", range(100))
    problem.add_variable("small", range(2))
    log: list[str] = []

    def record(variable, value, domains):
        log.append(variable)
        return True

    problem.add_constraint(SupportConstraint(("large",), record))
    problem.add_constraint(SupportConstraint(("small",), record))

    problem.propagate()

    last_small = max(index for index, name in enumerate(log) if name == "small")
    first_large = min(index for index, name in enumerate(log) if name == "large")
    assert last_small < first_large


class _CostHintConstraint:
    """Contrainte de test dont le coût déclaré ne suit pas sa portée."""

    def __init__(self, scope: tuple[str, ...], log: list[str], cost: int) -> None:
        self.scope = scope
        self._log = log
        self._cost = cost

    def has_support(self, variable, value, domains) -> bool:
        self._log.append(variable)
        return True

    def estimated_cost(self, domains) -> int:
        return self._cost


def test_propagate_uses_a_constraint_provided_cost_estimate_when_available() -> None:
    # Deux contraintes portant sur des domaines de même taille (donc le même
    # coût par défaut) ; l'une déclare explicitement être bien moins chère
    # via `estimated_cost` — elle doit être révisée en premier, malgré une
    # portée formelle identique et un enregistrement postérieur.
    problem = RelationalCSP[str, int]()
    problem.add_variable("expensive", range(100))
    problem.add_variable("cheap", range(100))
    log: list[str] = []

    problem.add_constraint(
        _CostHintConstraint(("expensive",), log, cost=1_000_000)
    )
    problem.add_constraint(_CostHintConstraint(("cheap",), log, cost=1))

    problem.propagate()

    assert log[0] == "cheap"


def test_predicate_constraint_search_matches_brute_force() -> None:
    problem = RelationalCSP[str, int]()
    for variable in ("x", "y", "z"):
        problem.add_variable(variable, range(4))
    problem.add_constraint(
        PredicateConstraint(("x", "y", "z"), lambda x, y, z: x + y == z)
    )
    problem.add_constraint(
        PredicateConstraint(("x", "y"), lambda x, y: x < y)
    )

    result = problem.solve()
    actual = {
        (model["x"], model["y"], model["z"])
        for model in result.models
    }
    expected = {
        (x, y, z)
        for x, y, z in product(range(4), repeat=3)
        if x < y and x + y == z
    }

    assert result.exhausted
    assert not result.limit_reached
    assert actual == expected


def test_custom_support_constraint_can_avoid_materialising_a_relation() -> None:
    problem = RelationalCSP[str, int]()
    for variable in ("a", "b", "c"):
        problem.add_variable(variable, (1, 2, 3))
    problem.add_variable("outside_scope", (8, 9))

    def all_different_support(variable, value, domains):
        assert set(domains) == {"a", "b", "c"}
        candidate_domains = [
            (value,) if current == variable else domains[current]
            for current in ("a", "b", "c")
        ]
        return any(
            len(set(values)) == 3 for values in product(*candidate_domains)
        )

    problem.add_constraint(
        SupportConstraint(("a", "b", "c"), all_different_support)
    )

    propagated = problem.propagate({"a": (1,), "b": (2,)})

    assert propagated.consistent
    assert propagated.domains == {
        "a": (1,),
        "b": (2,),
        "c": (3,),
        "outside_scope": (8, 9),
    }


def test_bounded_search_finds_one_two_or_n_models_without_claiming_exhaustion() -> None:
    problem = RelationalCSP[str, int]()
    problem.add_variable("x", (1, 2, 3))
    problem.add_variable("y", (1, 2, 3))
    problem.add_constraint(PredicateConstraint(("x", "y"), lambda x, y: x != y))

    one = problem.solve(limit=1)
    two = problem.solve(limit=2)
    all_models = problem.solve()

    assert len(one.models) == 1
    assert one.limit_reached and not one.exhausted
    assert len(two.models) == 2
    assert two.limit_reached and not two.exhausted
    assert len(all_models.models) == 6
    assert all_models.exhausted and not all_models.limit_reached


def test_value_is_proved_only_when_no_counterexample_exists() -> None:
    problem = RelationalCSP[str, int]()
    problem.add_variable("x", (1, 2, 3))
    problem.add_variable("y", (1, 2, 3))
    problem.add_constraint(
        ExtensionalConstraint(("x", "y"), ((1, 3), (2, 2), (3, 1)))
    )

    open_proof = problem.prove_value("x", 2)
    forced_proof = problem.prove_value("x", 2, {"y": (2,)})
    impossible_proof = problem.prove_value("x", 1, {"y": (2,)})

    assert open_proof.consistent and open_proof.possible
    assert not open_proof.forced
    assert open_proof.witness is not None
    assert open_proof.counterexample is not None

    assert forced_proof.consistent and forced_proof.possible
    assert forced_proof.forced
    assert forced_proof.witness == {"x": 2, "y": 2}
    assert forced_proof.counterexample is None

    assert impossible_proof.consistent
    assert not impossible_proof.possible
    assert not impossible_proof.forced
    assert impossible_proof.witness is None
    assert impossible_proof.counterexample == {"x": 2, "y": 2}


def test_contradiction_is_reported_without_searching_models() -> None:
    problem = RelationalCSP[str, int]()
    problem.add_variable("x", (1, 2))
    problem.add_variable("y", (1, 2))
    problem.add_constraint(ExtensionalConstraint(("x", "y"), ()))

    propagated = problem.propagate()
    searched = problem.solve(limit=2)
    proof = problem.prove_value("x", 1)

    assert not propagated.consistent
    assert searched.models == ()
    assert searched.exhausted
    assert not proof.consistent
    assert not proof.possible
    assert not proof.forced


def test_input_validation_rejects_invalid_problem_definitions() -> None:
    problem = RelationalCSP[str, int]()

    with pytest.raises(ValueError, match="non-empty"):
        problem.add_variable("empty", ())

    problem.add_variable("x", (1, 1, 2))
    assert problem.domains["x"] == (1, 2)

    with pytest.raises(ValueError, match="already exists"):
        problem.add_variable("x", (3,))
    with pytest.raises(ValueError, match="unknown"):
        problem.add_constraint(ExtensionalConstraint(("missing",), ((1,),)))
    with pytest.raises(ValueError, match="repeat"):
        PredicateConstraint(("x", "x"), lambda x1, x2: x1 == x2)
    with pytest.raises(ValueError, match="arity"):
        ExtensionalConstraint(("x",), ((1, 2),))
    with pytest.raises(ValueError, match="positive"):
        problem.solve(limit=0)
    with pytest.raises(KeyError, match="unknown"):
        problem.propagate({"missing": (1,)})


def test_restrictions_are_intersected_without_mutating_the_base_problem() -> None:
    problem = RelationalCSP[str, int]()
    problem.add_variable("x", (1, 2, 3))

    restricted = problem.propagate({"x": (2, 3, 99)})
    contradiction = problem.propagate({"x": ()})

    assert restricted.domains["x"] == (2, 3)
    assert not contradiction.consistent
    assert problem.domains["x"] == (1, 2, 3)
