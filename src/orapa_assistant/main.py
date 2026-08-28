from __future__ import annotations

import argparse

from .examples import REAL_GAME_HISTORY
from .history_store import HistoryStore
from .progressive import ProgressiveSolver


def _run_demo() -> int:
    """Résout la partie de référence en ligne de commande, sans interface."""

    solver = ProgressiveSolver()
    print("Résolution exacte de la partie de référence…", flush=True)
    solver.add_observations(REAL_GAME_HISTORY)
    legal = solver.legal_configuration_count
    legal_text = f"{legal:,}" if legal is not None else "?"
    print(
        f"{solver.candidate_count} solution(s) parmi {legal_text} grilles légales.",
        flush=True,
    )
    return 0


def _run_gui() -> int:
    import sys

    from PySide6.QtWidgets import QApplication, QMessageBox

    from .gui.main_window import MainWindow

    app = QApplication(sys.argv)
    history_store: HistoryStore | None = HistoryStore()
    try:
        saved_game = history_store.ensure_current()
    except OSError as error:
        history_store = None
        solver = ProgressiveSolver()
        QMessageBox.warning(
            None,
            "Historique non sauvegardé",
            "La sauvegarde automatique est indisponible pour cette session : "
            f"{error}",
        )
    else:
        solver = ProgressiveSolver(
            include_diamond=saved_game.include_diamond,
            include_black_body=saved_game.include_black_body,
        )
        if saved_game.observations:
            print(
                f"Restauration de {len(saved_game.observations)} indice(s)…",
                flush=True,
            )
            solver.add_observations(saved_game.observations)
    window = MainWindow(solver, history_store=history_store)
    window.show()
    return app.exec()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--demo",
        action="store_true",
        help="résout la partie de référence en console, sans interface graphique",
    )
    arguments = parser.parse_args()
    if arguments.demo:
        return _run_demo()
    return _run_gui()


if __name__ == "__main__":
    raise SystemExit(main())
