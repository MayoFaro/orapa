from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import json
import os
from pathlib import Path
from threading import RLock
from typing import Iterable, Mapping
from uuid import uuid4

from .colors import RayColor
from .solver import CellObservation, Observation, SolverObservation


JOURNAL_VERSION = 1


@dataclass(frozen=True)
class SavedGame:
    session_id: str
    recorded_at: str
    include_diamond: bool
    include_black_body: bool
    observations: tuple[SolverObservation, ...]
    reason: str


def default_history_path() -> Path:
    configured_root = os.environ.get("XDG_DATA_HOME")
    data_root = (
        Path(configured_root).expanduser()
        if configured_root
        else Path.home() / ".local" / "share"
    )
    return data_root / "orapa-assistant" / "history.jsonl"


def observation_to_dict(observation: SolverObservation) -> dict[str, object]:
    if isinstance(observation, CellObservation):
        return {
            "type": "cell",
            "row": observation.row,
            "column": observation.column,
            "content": observation.content.value,
        }
    result: dict[str, object] = {
        "type": "wave",
        "entry": observation.entry,
        "absorbed": observation.absorbed,
    }
    if not observation.absorbed:
        result["exit"] = observation.exit_point
        result["color"] = RayColor(observation.color).value
    return result


def observation_from_dict(data: Mapping[str, object]) -> SolverObservation:
    observation_type = data.get("type")
    if observation_type == "cell":
        row = data.get("row")
        column = data.get("column")
        content = data.get("content")
        if (
            not isinstance(row, str)
            or not isinstance(column, int)
            or isinstance(column, bool)
            or not isinstance(content, str)
        ):
            raise ValueError("Observation de case invalide")
        return CellObservation(row, column, content)
    if observation_type == "wave":
        entry = data.get("entry")
        absorbed = data.get("absorbed", False)
        if not isinstance(entry, str) or not isinstance(absorbed, bool):
            raise ValueError("Observation d’onde invalide")
        if absorbed:
            return Observation(entry, absorbed=True)
        exit_point = data.get("exit")
        color = data.get("color")
        if not isinstance(exit_point, str) or not isinstance(color, str):
            raise ValueError("Résultat d’onde invalide")
        return Observation(entry, exit_point, RayColor(color))
    raise ValueError("Type d’observation inconnu")


class HistoryStore:
    """Journal local d'instantanés, robuste à une dernière écriture incomplète."""

    def __init__(self, path: str | Path | None = None) -> None:
        self.path = Path(path) if path is not None else default_history_path()
        self._lock = RLock()

    def _records(self) -> list[SavedGame]:
        if not self.path.exists():
            return []
        records: list[SavedGame] = []
        with self.path.open("r", encoding="utf-8", errors="replace") as journal:
            for line in journal:
                try:
                    raw = json.loads(line)
                    if not isinstance(raw, dict) or raw.get("version") != JOURNAL_VERSION:
                        continue
                    encoded_observations = raw.get("observations")
                    if not isinstance(encoded_observations, list):
                        continue
                    observations = tuple(
                        observation_from_dict(item)
                        for item in encoded_observations
                        if isinstance(item, dict)
                    )
                    if len(observations) != len(encoded_observations):
                        continue
                    session_id = raw.get("session_id")
                    recorded_at = raw.get("recorded_at")
                    reason = raw.get("reason")
                    include_diamond = raw.get("include_diamond")
                    include_black_body = raw.get("include_black_body")
                    if (
                        not isinstance(session_id, str)
                        or not isinstance(recorded_at, str)
                        or not isinstance(reason, str)
                        or not isinstance(include_diamond, bool)
                        or not isinstance(include_black_body, bool)
                    ):
                        continue
                except (json.JSONDecodeError, TypeError, ValueError):
                    continue
                records.append(
                    SavedGame(
                        session_id=session_id,
                        recorded_at=recorded_at,
                        include_diamond=include_diamond,
                        include_black_body=include_black_body,
                        observations=observations,
                        reason=reason,
                    )
                )
        return records

    @staticmethod
    def _timestamp() -> str:
        return datetime.now(timezone.utc).isoformat()

    def _append(self, game: SavedGame) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        record = {
            "version": JOURNAL_VERSION,
            "recorded_at": game.recorded_at,
            "session_id": game.session_id,
            "reason": game.reason,
            "include_diamond": game.include_diamond,
            "include_black_body": game.include_black_body,
            "observations": [
                observation_to_dict(observation)
                for observation in game.observations
            ],
        }
        encoded = (json.dumps(record, ensure_ascii=False) + "\n").encode("utf-8")
        with self.path.open("a+b") as journal:
            journal.seek(0, os.SEEK_END)
            if journal.tell():
                journal.seek(-1, os.SEEK_END)
                if journal.read(1) != b"\n":
                    journal.seek(0, os.SEEK_END)
                    journal.write(b"\n")
            journal.seek(0, os.SEEK_END)
            journal.write(encoded)
            journal.flush()
            os.fsync(journal.fileno())

    def load_current(self) -> SavedGame | None:
        with self._lock:
            records = self._records()
            return records[-1] if records else None

    def sessions(self) -> tuple[SavedGame, ...]:
        """Retourne le dernier instantané valide de chaque partie."""

        with self._lock:
            latest_by_session: dict[str, SavedGame] = {}
            for record in self._records():
                latest_by_session[record.session_id] = record
            return tuple(latest_by_session.values())

    def ensure_current(
        self,
        *,
        include_diamond: bool = False,
        include_black_body: bool = False,
    ) -> SavedGame:
        with self._lock:
            current = self.load_current()
            if current is not None:
                return current
            return self._start_session(
                include_diamond=include_diamond,
                include_black_body=include_black_body,
                reason="initial",
            )

    def _start_session(
        self,
        *,
        include_diamond: bool,
        include_black_body: bool,
        reason: str,
    ) -> SavedGame:
        game = SavedGame(
            session_id=uuid4().hex,
            recorded_at=self._timestamp(),
            include_diamond=include_diamond,
            include_black_body=include_black_body,
            observations=(),
            reason=reason,
        )
        self._append(game)
        return game

    def start_new_game(
        self,
        *,
        include_diamond: bool,
        include_black_body: bool,
        reason: str,
    ) -> SavedGame:
        with self._lock:
            return self._start_session(
                include_diamond=include_diamond,
                include_black_body=include_black_body,
                reason=reason,
            )

    def save_current(
        self,
        observations: Iterable[SolverObservation],
        *,
        include_diamond: bool,
        include_black_body: bool,
    ) -> SavedGame:
        with self._lock:
            saved_observations = tuple(observations)
            current = self.load_current()
            if current is None:
                current = self._start_session(
                    include_diamond=include_diamond,
                    include_black_body=include_black_body,
                    reason="initial",
                )
            if (
                current.observations == saved_observations
                and current.include_diamond == include_diamond
                and current.include_black_body == include_black_body
            ):
                return current
            saved = SavedGame(
                session_id=current.session_id,
                recorded_at=self._timestamp(),
                include_diamond=include_diamond,
                include_black_body=include_black_body,
                observations=saved_observations,
                reason="autosave",
            )
            self._append(saved)
            return saved
