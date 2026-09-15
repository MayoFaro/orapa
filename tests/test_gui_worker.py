import os
import time

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


def test_starting_a_task_while_busy_interrupts_and_restarts() -> None:
    # Une nouvelle saisie pendant un calcul en cours ne doit ni être
    # ignorée, ni faire attendre l'utilisateur la fin du calcul précédent :
    # elle interrompt celui-ci et repart aussitôt avec la demande à jour.
    app = QApplication.instance() or QApplication([])
    window = MainWindow(Solver([REAL_GAME_SOLUTION]))
    order: list[str] = []

    def slow_operation() -> None:
        order.append("first-start")
        worker = window._worker
        for _ in range(2_000):
            if worker is not None and worker.isInterruptionRequested():
                order.append("first-interrupted")
                return
            time.sleep(0.001)
        order.append("first-finished-without-interruption")

    window._start_solver_task(slow_operation)
    first_worker = window._worker
    assert first_worker is not None

    window._start_solver_task(lambda: order.append("second-done"))

    assert window._worker is not None
    assert window._worker is not first_worker
    assert window._worker.wait(2_000)
    app.processEvents()

    assert order[:2] == ["first-start", "first-interrupted"]
    assert order[-1] == "second-done"
    window.close()


def test_status_indicator_reflects_busy_state() -> None:
    app = QApplication.instance() or QApplication([])
    window = MainWindow(Solver([REAL_GAME_SOLUTION]))
    assert "Prêt" in window.status_indicator.text()

    release = False

    def slow_operation() -> None:
        while not release:
            time.sleep(0.001)

    window._start_solver_task(slow_operation)
    app.processEvents()
    assert "réflexion" in window.status_indicator.text()

    release = True
    assert window._worker is not None
    assert window._worker.wait(2_000)
    app.processEvents()
    assert "Prêt" in window.status_indicator.text()
    window.close()


def test_a_new_entry_appears_in_history_immediately_even_while_busy(
    monkeypatch,
) -> None:
    # Sans confirmation immédiate, un ajout pendant un calcul en cours
    # n'apparaît dans l'historique qu'une fois ce calcul terminé — ce qui
    # peut prendre un moment et laisser croire que la saisie s'est perdue.
    app = QApplication.instance() or QApplication([])
    # `_add_observation` peut ouvrir une boîte de dialogue modale une fois
    # le calcul terminé (ex. "configuration unique") ; sans utilisateur
    # pour la fermer, elle bloquerait indéfiniment en environnement de test.
    monkeypatch.setattr(QMessageBox, "information", lambda *a, **k: None)
    monkeypatch.setattr(QMessageBox, "warning", lambda *a, **k: None)
    window = MainWindow(Solver([REAL_GAME_SOLUTION]))

    def slow_operation() -> None:
        worker = window._worker
        for _ in range(2_000):
            if worker is not None and worker.isInterruptionRequested():
                return
            time.sleep(0.001)

    window._start_solver_task(slow_operation)
    app.processEvents()

    window.entry_selector.set_value("A")
    window.exit_selector.set_value("A")
    window.color_selector.set_value(RayColor.WHITE)
    # L'insertion optimiste se fait de façon synchrone, sur le thread
    # graphique, avant même le démarrage du nouveau calcul : elle doit donc
    # être visible immédiatement, sans laisser le nouveau calcul (rapide)
    # avoir la moindre chance de la remplacer en premier.
    window._add_observation()

    assert window.history.count() >= 1
    assert "en attente" in window.history.item(0).text()

    assert window._worker is not None
    assert window._worker.wait(2_000)
    app.processEvents()
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
