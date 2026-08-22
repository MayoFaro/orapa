from __future__ import annotations

import argparse
import sys

from PySide6.QtWidgets import QApplication

from .examples import REAL_GAME_HISTORY
from .gui.main_window import MainWindow
from .progressive import ProgressiveSolver


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--demo",
        action="store_true",
        help="résout exactement la partie de référence puis ouvre son résultat",
    )
    arguments = parser.parse_args()
    solver = ProgressiveSolver()
    if arguments.demo:
        print("Résolution exacte de la partie de référence…", flush=True)
        solver.add_observations(REAL_GAME_HISTORY)
        print(
            f"{solver.candidate_count} solution(s) parmi "
            f"{solver.legal_configuration_count:,} grilles légales.",
            flush=True,
        )
    app = QApplication(sys.argv)
    window = MainWindow(solver)
    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
