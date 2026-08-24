from orapa_assistant.colors import RayColor as C
from orapa_assistant.domain_filter import PlacementDomain
from orapa_assistant.pieces import DIAMOND, PIECES, placements
from orapa_assistant import relational_filter
from orapa_assistant.relational_filter import apply_relational_filters
from orapa_assistant.solver import Observation


def _base_domains() -> tuple[PlacementDomain, ...]:
    definitions = PIECES + (DIAMOND,)
    return tuple(
        PlacementDomain(piece.name, placements(piece)) for piece in definitions
    )


def test_relation_over_budget_is_deferred_without_pruning() -> None:
    domains = _base_domains()
    observation = Observation("C", "C", C.PINK)

    result = apply_relational_filters(
        domains,
        (observation,),
        max_relation_work=1,
        max_relation_seconds=None,
    )

    assert result.domains == domains
    assert result.applied_relations == 0
    assert result.deferred_relations == 1


def test_stable_relation_is_not_replayed(monkeypatch) -> None:
    domains = _base_domains()
    observation = Observation("10", "R", C.TRANSPARENT)
    calls = 0
    original = relational_filter._revise_wave_relation

    def counted(*args, **kwargs):
        nonlocal calls
        calls += 1
        return original(*args, **kwargs)

    monkeypatch.setattr(relational_filter, "_revise_wave_relation", counted)
    first = apply_relational_filters(
        domains,
        (observation,),
        max_relation_work=100_000_000,
        max_relation_seconds=None,
    )
    calls_after_first_point = calls

    second = apply_relational_filters(
        first.domains,
        (observation, observation),
        state=first.state,
        max_relation_work=100_000_000,
        max_relation_seconds=None,
    )

    assert calls_after_first_point > 0
    assert calls == calls_after_first_point + 1
    assert second.applied_relations == 2

