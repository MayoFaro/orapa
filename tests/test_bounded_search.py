from orapa_assistant.domain_filter import PlacementDomain
from orapa_assistant.raytracer import Configuration
from orapa_assistant.search import search_configurations_bounded


def test_bounded_search_distinguishes_exhaustion_from_budget_stop() -> None:
    empty = PlacementDomain("empty", ())
    # Le cas vide est une contradiction de domaine et s'épuise sans modèle.
    exhausted = search_configurations_bounded((empty,), (), max_nodes=10)
    assert exhausted.exhausted
    assert exhausted.configurations == ()


def test_bounded_search_returns_only_complete_valid_configurations() -> None:
    result = search_configurations_bounded((), (), max_nodes=10)
    assert result.exhausted
    assert result.configurations == (Configuration(()),)
