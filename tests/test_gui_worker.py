import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication, QMessageBox

from orapa_assistant.colors import RayColor
from orapa_assistant.examples import REAL_GAME_SOLUTION
from orapa_assistant.gui.main_window import MainWindow
from orapa_assistant.history_store import HistoryStore
from orapa_assistant.solver import Observation, Solver


def test_solver_task_runs_without_blocking_gui_thread() -> None:
    app = QApplication.instance() or QApplication([])
    window = MainWindow(Solver([REAL_GAME_SOLUTION]))
    marker: list[str] = []

    window._start_solver_task(lambda: marker.append("done"))
    assert window._worker is not None
    assert window._worker.wait(1_000)
    app.processEvents()

    assert marker == ["done"]
    assert window.add_button.isEnabled()
    window.close()


def test_solver_task_saves_and_reset_archives_history(
    tmp_path, monkeypatch
) -> None:
    app = QApplication.instance() or QApplication([])
    store = HistoryStore(tmp_path / "history.jsonl")
    store.ensure_current()
    solver = Solver([REAL_GAME_SOLUTION])
    window = MainWindow(solver, history_store=store)
    window.color_selector.set_value(RayColor.WHITE)
    clue = Observation("B", "3", window.color_selector.value())
    assert clue.color is RayColor.WHITE

    window._start_solver_task(lambda: solver.add_observation(clue))
    assert window._worker is not None
    assert window._worker.wait(1_000)
    app.processEvents()
    assert store.load_current().observations == (clue,)

    monkeypatch.setattr(
        QMessageBox,
        "question",
        lambda *args, **kwargs: QMessageBox.Yes,
    )
    window._reset_game()
    assert window._worker is not None
    assert window._worker.wait(1_000)
    app.processEvents()

    assert store.load_current().observations == ()
    assert store.sessions()[0].observations == (clue,)
    window.close()
