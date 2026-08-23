import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication
from PySide6.QtCore import QPoint, Qt

from orapa_assistant.border import BOTTOM_POINTS, RIGHT_POINTS
from orapa_assistant.examples import REAL_GAME_SOLUTION
from orapa_assistant.gui.main_window import MainWindow
from orapa_assistant.colors import RayColor
from orapa_assistant.raytracer import Configuration
from orapa_assistant.solver import CellContent, CellObservation, Observation, Solver


def test_main_window_can_be_created() -> None:
    app = QApplication.instance() or QApplication([])
    window = MainWindow(Solver([REAL_GAME_SOLUTION]))
    assert window.right_panel.minimumWidth() == 320
    assert window.right_panel.maximumWidth() == 320
    assert window.board.width() < 450
    assert window.board_panel.width() == window.board.width() + 28
    assert window.reset_button.text() == "Nouvelle partie"
    assert [label.text() for label in window.right_marker_labels] == list(RIGHT_POINTS)
    assert [label.text() for label in window.bottom_marker_labels] == list(BOTTOM_POINTS)
    assert "Configurations retenues par le modèle : 1" in window.count_label.text()
    assert "losange blanc" in window.certainty_label.text()
    assert window.entry_number.currentText() == "1"
    window.show()
    app.processEvents()
    board_viewport = window.board.viewport().mapTo(window, QPoint(0, 0))
    first_bottom_marker = window.bottom_marker_labels[0].mapTo(
        window, QPoint(0, 0)
    )
    board_bottom = window.board.mapTo(window, QPoint(0, window.board.height())).y()
    assert first_bottom_marker.x() == board_viewport.x()
    assert board_bottom <= first_bottom_marker.y() <= board_bottom + 3
    assert window.board.horizontalScrollBar().maximum() == 0
    assert window.board.verticalScrollBar().maximum() == 0
    assert window.board.horizontalScrollBarPolicy() == Qt.ScrollBarAlwaysOff
    assert window.board.verticalScrollBarPolicy() == Qt.ScrollBarAlwaysOff
    assert window.board.viewport().width() == sum(
        window.board.columnWidth(column) for column in range(10)
    )
    assert window.board.viewport().height() == sum(
        window.board.rowHeight(row) for row in range(8)
    )
    assert window.minimumSizeHint().width() <= 800
    assert window.color.itemText(window.color.findData(RayColor.LIGHT_YELLOW)) == (
        "Jaune citron"
    )
    assert window.color.itemText(window.color.findData(RayColor.LIGHT_BLUE)) == (
        "Bleu ciel"
    )
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
    assert window.solution_view.itemText(1) == "Configuration retenue 1"
    assert window.solution_view.itemText(2) == "Configuration retenue 2"
    window.solution_view.setCurrentIndex(2)
    assert any(
        window.board.item(row, column).text() != "·"
        for row in range(8)
        for column in range(10)
    )
    window.close()
