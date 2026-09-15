import time
from unittest.mock import patch

from orapa_assistant.colors import RayColor as C
from orapa_assistant.examples import REAL_GAME_HISTORY
from orapa_assistant.orapa_csp import OrapaModelResult
from orapa_assistant.progressive import ProgressiveSolver
from orapa_assistant.solver import Observation


def test_exact_solve_is_not_attempted_below_the_minimum_observation_count() -> None:
    solver = ProgressiveSolver(exact_search_min_observations=6)

    with patch("orapa_assistant.progressive.solve_orapa_csp") as mocked:
        solver.add_observations(REAL_GAME_HISTORY[:5])

    mocked.assert_not_called()


def test_propagate_uses_a_short_budget_below_the_minimum_observation_count() -> None:
    # En dessous du seuil, on sait déjà que rien ne sera résolu : inutile de
    # laisser le filtrage rapide consommer son budget complet (10s) sur un
    # indice isolé qui ne peut de toute façon rien prouver.
    solver = ProgressiveSolver(
        exact_search_min_observations=6,
        propagate_time_budget=10.0,
        propagate_time_budget_early=2.0,
    )

    def passthrough(domains, observations, **kwargs):
        return domains, 0, 0

    before = time.monotonic()
    with patch(
        "orapa_assistant.progressive.propagate_orapa_csp", side_effect=passthrough
    ) as mocked:
        solver.add_observations(REAL_GAME_HISTORY[:3])

    deadline = mocked.call_args.kwargs["deadline"]
    assert deadline - before < 3.0


def test_propagate_uses_the_full_budget_at_the_minimum_observation_count() -> None:
    solver = ProgressiveSolver(
        exact_search_min_observations=6,
        propagate_time_budget=10.0,
        propagate_time_budget_early=2.0,
    )

    def propagate_passthrough(domains, observations, **kwargs):
        return domains, 0, 0

    def solve_passthrough(domains, observations, **kwargs):
        return OrapaModelResult(domains, (), False, False, 0)

    before = time.monotonic()
    with patch(
        "orapa_assistant.progressive.propagate_orapa_csp",
        side_effect=propagate_passthrough,
    ) as mocked_propagate, patch(
        "orapa_assistant.progressive.solve_orapa_csp", side_effect=solve_passthrough
    ):
        solver.add_observations(REAL_GAME_HISTORY[:6])

    deadline = mocked_propagate.call_args.kwargs["deadline"]
    assert deadline - before > 8.0


def test_the_same_witness_cache_is_reused_across_incremental_solves() -> None:
    # Chaque nouvel indice ne doit pas repartir de zéro : le même dictionnaire
    # de témoins doit être transmis d'un appel à l'autre pour que
    # `solve_orapa_csp` puisse réutiliser ce qu'il a déjà prouvé.
    solver = ProgressiveSolver(exact_search_min_observations=6)

    def passthrough(domains, observations, **kwargs):
        return OrapaModelResult(domains, (), False, False, 0)

    with patch(
        "orapa_assistant.progressive.solve_orapa_csp", side_effect=passthrough
    ) as mocked:
        solver.add_observations(REAL_GAME_HISTORY[:6])
        solver.add_observation(REAL_GAME_HISTORY[6])

    assert mocked.call_count == 2
    first_cache = mocked.call_args_list[0].kwargs["witness_cache"]
    second_cache = mocked.call_args_list[1].kwargs["witness_cache"]
    assert first_cache is not None
    assert first_cache is second_cache


def test_exact_solve_is_attempted_at_the_minimum_observation_count() -> None:
    solver = ProgressiveSolver(exact_search_min_observations=6)

    def passthrough(domains, observations, **kwargs):
        return OrapaModelResult(domains, (), False, False, 0)

    with patch(
        "orapa_assistant.progressive.solve_orapa_csp", side_effect=passthrough
    ) as mocked:
        solver.add_observations(REAL_GAME_HISTORY[:6])

    mocked.assert_called_once()
    _, kwargs = mocked.call_args
    assert kwargs["deadline"] is not None


def test_cancelled_hook_is_forwarded_to_both_search_stages() -> None:
    # L'interface graphique interrompt un calcul en cours en réglant ce
    # signal (p. ex. l'interruption d'un thread) plutôt qu'en attendant une
    # échéance de temps.
    solver = ProgressiveSolver(exact_search_min_observations=6)
    sentinel = lambda: False  # noqa: E731 - identité importe, pas le comportement

    def propagate_passthrough(domains, observations, **kwargs):
        return domains, 0, 0

    def solve_passthrough(domains, observations, **kwargs):
        return OrapaModelResult(domains, (), False, False, 0)

    solver.cancelled = sentinel
    with patch(
        "orapa_assistant.progressive.propagate_orapa_csp",
        side_effect=propagate_passthrough,
    ) as mocked_propagate, patch(
        "orapa_assistant.progressive.solve_orapa_csp", side_effect=solve_passthrough
    ) as mocked_solve:
        solver.add_observations(REAL_GAME_HISTORY[:6])

    assert mocked_propagate.call_args.kwargs["cancelled"] is sentinel
    assert mocked_solve.call_args.kwargs["cancelled"] is sentinel


def test_progressive_solver_waits_then_becomes_exact() -> None:
    solver = ProgressiveSolver()
    assert not solver.exact
    assert solver.candidate_count is None
    assert solver.raw_combination_count == 139_158_093_312

    solver.add_observations(REAL_GAME_HISTORY)
    assert solver.exact
    assert solver.raw_combination_count == 1
    assert solver.candidate_count == 1
    assert len(solver.candidates) == 1


def test_removing_last_observation_recomputes_exact_state() -> None:
    solver = ProgressiveSolver()
    solver.add_observations(REAL_GAME_HISTORY)
    solver.remove_observation(len(REAL_GAME_HISTORY) - 1)
    assert solver.exact
    assert solver.candidate_count == 1
    assert solver.raw_combination_count == 1


# Partie réelle jouée avec diamant et corps noir : le produit brut des
# domaines dépasse 10^12, largement au-dessus de l'ancien seuil de 150M qui
# empêchait la résolution exacte de seulement être tentée.
LARGE_SEARCH_SPACE_GAME = (
    Observation("11", "3", C.WHITE),
    Observation("1", absorbed=True),
    Observation("2", "A", C.WHITE),
    Observation("B", absorbed=True),
    Observation("10", "10", C.VIOLET),
    Observation("R", "R", C.GREEN),
    Observation("18", "18", C.YELLOW),
    Observation("9", "9", C.WHITE),
    Observation("Q", "F", C.BLUE),
    Observation("5", "N", C.PINK),
    Observation("12", "E", C.LIGHT_BLUE),
    Observation("8", "8", C.WHITE),
    Observation("M", "M", C.YELLOW),
    Observation("P", "13", C.WHITE),
    Observation("H", absorbed=True),
    Observation("L", "L", C.YELLOW),
    Observation("D", "D", C.PINK),
)


def test_large_search_space_game_still_reaches_an_exact_solution() -> None:
    # Après seulement le filtrage relationnel (avant toute tentative de
    # résolution exacte), le produit brut des domaines dépasse 10^12 sur
    # cette partie — bien au-delà de l'ancien seuil de 150M qui empêchait
    # `solve_orapa_csp` d'être seulement tenté. La propagation de la
    # résolution exacte elle-même est nettement plus efficace que ce seuil
    # naïf ne le laissait supposer.
    solver = ProgressiveSolver(include_diamond=True, include_black_body=True)

    solver.add_observations(LARGE_SEARCH_SPACE_GAME)

    assert solver.exact
    assert solver.candidate_count == 1
