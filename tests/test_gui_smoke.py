import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication
from PySide6.QtCore import Qt

from orapa_assistant.border import BOTTOM_POINTS, RIGHT_POINTS
from orapa_assistant.examples import REAL_GAME_SOLUTION
from orapa_assistant.gui.main_window import MainWindow
from orapa_assistant.colors import RayColor
from orapa_assistant.raytracer import Configuration
from orapa_assistant.solver import CellContent, CellObservation, Observation, Solver


def test_main_window_can_be_created() -> None:
    app = QApplication.instance() or QApplication([])
    window = MainWindow(Solver([REAL_GAME_SOLUTION]))
    assert window.right_panel.minimumWidth() == 340
    assert window.right_panel.maximumWidth() == 340
    assert window.board.minimumWidth() == 500
    assert window.reset_button.text() == "Nouvelle partie"
    assert [label.text() for label in window.right_marker_labels] == list(RIGHT_POINTS)
    assert [label.text() for label in window.bottom_marker_labels] == list(BOTTOM_POINTS)
    assert "Solutions exactes restantes : 1" == window.count_label.text()
    assert "losange blanc" in window.certainty_label.text()
    assert window.entry_number.currentText() == "1"
    window.entry_letter.setCurrentText("A")
    assert window.entry_number.currentText() == "—"
    assert not window.absorbed.isEnabled()
    window.action_type.setCurrentIndex(1)
    assert window.cell_row.isEnabled()
    assert window.cell_content.findData(CellContent.DIAMOND) == -1
    assert not window.entry_number.isEnabled()
    window.action_type.setCurrentIndex(0)
    window.black_checkbox.setChecked(True)
    window.absorbed.setChecked(True)
    assert not window.exit_number.isEnabled()
    assert not window.color.isEnabled()
    window.diamond_checkbox.setChecked(True)
    assert window.solver.include_diamond
    assert window.solver.include_black_body
    assert "diamond" in window.solver.domain_sizes
    window.close()


def test_history_displays_newest_observation_first() -> None:
    app = QApplication.instance() or QApplication([])
    solver = Solver([REAL_GAME_SOLUTION])
    solver.add_observation(Observation("B", "3", RayColor.WHITE))
    solver.add_observation(Observation("D", "D", RayColor.BLUE))
    solver.add_observation(CellObservation("A", 1, CellContent.NOTHING))
    window = MainWindow(solver)
    assert window.history.item(0).text() == "Case A1 → Rien"
    assert window.history.item(0).data(Qt.UserRole) == 2
    assert window.history.item(1).text().startswith("D → D")
    assert window.history.item(2).text().startswith("B → 3")
    window.close()


def test_two_remaining_solutions_can_be_displayed_separately() -> None:
    app = QApplication.instance() or QApplication([])
    window = MainWindow(Solver([Configuration(()), REAL_GAME_SOLUTION]))
    assert not window.solution_view.isHidden()
    assert window.solution_view.count() == 3
    assert window.solution_view.itemText(1) == "Solution possible 1"
    assert window.solution_view.itemText(2) == "Solution possible 2"
    window.solution_view.setCurrentIndex(2)
    assert any(
        window.board.item(row, column).text() != "·"
        for row in range(8)
        for column in range(10)
    )
    window.close()
