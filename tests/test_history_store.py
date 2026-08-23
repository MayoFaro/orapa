import json

import pytest

from orapa_assistant.colors import RayColor
from orapa_assistant.history_store import (
    HistoryStore,
    default_history_path,
    observation_from_dict,
    observation_to_dict,
)
from orapa_assistant.solver import CellContent, CellObservation, Observation


@pytest.mark.parametrize(
    "observation",
    (
        Observation("K", "6", RayColor.WHITE),
        Observation("B", "3", "white"),
        Observation("13", absorbed=True),
        CellObservation("G", 10, CellContent.NOTHING),
        CellObservation("B", 3, CellContent.DIAMOND),
    ),
)
def test_observation_serialization_round_trip(observation) -> None:
    assert observation_from_dict(observation_to_dict(observation)) == observation


def test_wave_color_is_normalized_when_qt_returns_a_string() -> None:
    observation = Observation("B", "3", "white")

    assert observation.color is RayColor.WHITE
    assert observation_to_dict(observation)["color"] == "white"


def test_current_game_is_saved_and_reloaded_without_duplicates(tmp_path) -> None:
    path = tmp_path / "history.jsonl"
    store = HistoryStore(path)
    initial = store.ensure_current(
        include_diamond=True,
        include_black_body=False,
    )
    observations = (
        Observation("K", "6", RayColor.WHITE),
        CellObservation("G", 10, CellContent.NOTHING),
    )

    saved = store.save_current(
        observations,
        include_diamond=True,
        include_black_body=False,
    )
    store.save_current(
        observations,
        include_diamond=True,
        include_black_body=False,
    )
    restored = HistoryStore(path).load_current()

    assert saved.session_id == initial.session_id
    assert restored is not None
    assert restored.observations == observations
    assert restored.include_diamond
    assert not restored.include_black_body
    assert len(path.read_text(encoding="utf-8").splitlines()) == 2


def test_new_game_keeps_the_previous_session_in_the_journal(tmp_path) -> None:
    path = tmp_path / "history.jsonl"
    store = HistoryStore(path)
    store.ensure_current()
    clue = Observation("13", absorbed=True)
    store.save_current(
        (clue,),
        include_diamond=False,
        include_black_body=True,
    )

    new_game = store.start_new_game(
        include_diamond=True,
        include_black_body=True,
        reason="new_game",
    )

    sessions = store.sessions()
    assert len(sessions) == 2
    assert sessions[0].observations == (clue,)
    assert sessions[1] == new_game
    assert new_game.observations == ()
    assert new_game.include_diamond
    assert new_game.include_black_body
    assert json.loads(path.read_text(encoding="utf-8").splitlines()[-1])[
        "reason"
    ] == "new_game"


def test_removed_and_duplicate_clues_remain_in_older_snapshots(tmp_path) -> None:
    path = tmp_path / "history.jsonl"
    store = HistoryStore(path)
    store.ensure_current()
    clue = Observation("K", "6", RayColor.WHITE)
    store.save_current(
        (clue, clue),
        include_diamond=False,
        include_black_body=False,
    )
    store.save_current(
        (clue,),
        include_diamond=False,
        include_black_body=False,
    )

    assert store.load_current().observations == (clue,)
    snapshots = [json.loads(line) for line in path.read_text().splitlines()]
    assert snapshots[-2]["observations"] == [
        observation_to_dict(clue),
        observation_to_dict(clue),
    ]


def test_incomplete_last_write_does_not_destroy_the_last_valid_state(
    tmp_path,
) -> None:
    path = tmp_path / "history.jsonl"
    store = HistoryStore(path)
    clue = Observation("K", "6", RayColor.WHITE)
    store.ensure_current()
    store.save_current(
        (clue,),
        include_diamond=False,
        include_black_body=False,
    )
    with path.open("ab") as journal:
        journal.write(b'{"recorded_at":')

    assert HistoryStore(path).load_current().observations == (clue,)
    HistoryStore(path).start_new_game(
        include_diamond=False,
        include_black_body=False,
        reason="new_game",
    )
    assert HistoryStore(path).load_current().observations == ()


def test_default_path_honours_xdg_data_home(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path))
    assert default_history_path() == tmp_path / "orapa-assistant" / "history.jsonl"
