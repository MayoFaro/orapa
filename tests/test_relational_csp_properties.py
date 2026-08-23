"""Propriétés génériques du noyau CSP sur de petits problèmes générés.

Les graines sont fixes : les scénarios restent reproductibles, tout en couvrant
beaucoup plus de formes de relations qu'une partie Orapa particulière.
"""

from __future__ import annotations

from itertools import product
from random import Random

import pytest

from orapa_assistant.relational_csp import ExtensionalConstraint, RelationalCSP


VARIABLES = ("a", "b", "c", "d")
VALUES = (0, 1, 2)


def _generated_relations(seed: int):
    random = Random(seed)
    planted = tuple(random.choice(VALUES) for _ in VARIABLES)
    relations = []
    for _ in range(5):
        arity = random.choice((2, 3))
        scope = tuple(random.sample(VARIABLES, arity))
        planted_tuple = tuple(planted[VARIABLES.index(variable)] for variable in scope)
        allowed = {
            values
            for values in product(VALUES, repeat=arity)
            if random.random() < 0.32
        }
        allowed.add(planted_tuple)
        relations.append((scope, frozenset(allowed)))
    return tuple(relations)


def _problem(relations) -> RelationalCSP[str, int]:
    problem = RelationalCSP[str, int]()
    for variable in VARIABLES:
        problem.add_variable(variable, VALUES)
    for scope, allowed in relations:
        problem.add_constraint(ExtensionalConstraint(scope, allowed))
    return problem


def _brute_force(relations, restrictions=None):
    restrictions = restrictions or {}
    models = set()
    for values in product(VALUES, repeat=len(VARIABLES)):
        model = dict(zip(VARIABLES, values, strict=True))
        if any(model[variable] not in allowed for variable, allowed in restrictions.items()):
            continue
        if all(
            tuple(model[variable] for variable in scope) in allowed
            for scope, allowed in relations
        ):
            models.add(values)
    return models


def _model_tuple(model) -> tuple[int, ...]:
    return tuple(model[variable] for variable in VARIABLES)


@pytest.mark.parametrize("seed", range(30))
def test_generated_csp_search_is_sound_and_complete(seed: int) -> None:
    relations = _generated_relations(seed)
    problem = _problem(relations)
    expected = _brute_force(relations)

    propagated = problem.propagate()
    result = problem.solve()
    actual = {_model_tuple(model) for model in result.models}

    assert result.exhausted
    assert actual <= expected  # soundness
    assert expected <= actual  # complétude
    assert propagated.consistent == bool(expected)
    if expected:
        # Une propagation correcte ne retire jamais une valeur appartenant à
        # un modèle, même lorsqu'elle ne suffit pas à établir l'unicité.
        for model in expected:
            assert all(
                model[index] in propagated.domains[variable]
                for index, variable in enumerate(VARIABLES)
            )


@pytest.mark.parametrize("seed", range(15))
def test_generated_restrictions_match_brute_force_and_are_monotone(seed: int) -> None:
    relations = _generated_relations(100 + seed)
    random = Random(seed)
    variable = random.choice(VARIABLES)
    restriction = {variable: tuple(random.sample(VALUES, random.choice((1, 2))))}
    problem = _problem(relations)

    unrestricted = problem.propagate()
    restricted = problem.propagate(restriction)
    expected = _brute_force(relations, restriction)
    actual = {
        _model_tuple(model)
        for model in problem.solve(restrictions=restriction).models
    }

    assert actual == expected
    assert restricted.consistent == bool(expected)
    if restricted.consistent:
        assert all(
            set(restricted.domains[current]) <= set(unrestricted.domains[current])
            for current in VARIABLES
        )


@pytest.mark.parametrize("seed", range(15))
def test_generated_value_proofs_agree_with_counterexample_oracle(seed: int) -> None:
    relations = _generated_relations(200 + seed)
    problem = _problem(relations)
    expected = _brute_force(relations)
    variable = VARIABLES[seed % len(VARIABLES)]
    value = VALUES[(seed // len(VARIABLES)) % len(VALUES)]
    value_index = VARIABLES.index(variable)

    proof = problem.prove_value(variable, value)
    possible = any(model[value_index] == value for model in expected)
    has_counterexample = any(model[value_index] != value for model in expected)

    assert proof.consistent == bool(expected)
    assert proof.possible == possible
    assert proof.forced == (possible and not has_counterexample)
    if proof.witness is not None:
        assert _model_tuple(proof.witness) in expected
        assert proof.witness[variable] == value
    if proof.counterexample is not None:
        assert _model_tuple(proof.counterexample) in expected
        assert proof.counterexample[variable] != value


@pytest.mark.parametrize("seed", range(10))
def test_constraint_order_does_not_change_models_or_fixed_point(seed: int) -> None:
    relations = _generated_relations(300 + seed)
    forward = _problem(relations)
    backward = _problem(tuple(reversed(relations)))

    assert {
        _model_tuple(model) for model in forward.solve().models
    } == {
        _model_tuple(model) for model in backward.solve().models
    }
    assert forward.propagate().domains == backward.propagate().domains
