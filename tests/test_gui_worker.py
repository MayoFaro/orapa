import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication

from orapa_assistant.examples import REAL_GAME_SOLUTION
from orapa_assistant.gui.main_window import MainWindow
from orapa_assistant.solver import Solver


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
