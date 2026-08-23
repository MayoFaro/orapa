from __future__ import annotations

import argparse
import sys

from PySide6.QtWidgets import QApplication, QMessageBox

from .examples import REAL_GAME_HISTORY
from .gui.main_window import MainWindow
from .history_store import HistoryStore
from .progressive import ProgressiveSolver


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--demo",
        action="store_true",
        help="résout exactement la partie de référence puis ouvre son résultat",
    )
    arguments = parser.parse_args()
    app = QApplication(sys.argv)
    history_store: HistoryStore | None = None
    if arguments.demo:
        solver = ProgressiveSolver()
        print("Résolution exacte de la partie de référence…", flush=True)
        solver.add_observations(REAL_GAME_HISTORY)
        print(
            f"{solver.candidate_count} solution(s) parmi "
            f"{solver.legal_configuration_count:,} grilles légales.",
            flush=True,
        )
    else:
        history_store = HistoryStore()
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


if __name__ == "__main__":
    raise SystemExit(main())
