import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication
from PySide6.QtCore import QPoint, Qt

from orapa_assistant.border import BOTTOM_POINTS, RIGHT_POINTS
from orapa_assistant.examples import REAL_GAME_HISTORY, REAL_GAME_SOLUTION
from orapa_assistant.gui.main_window import (
    BOARD_COLUMN_WIDTH,
    BOARD_ROW_HEIGHT,
    MainWindow,
)
from orapa_assistant.colors import RayColor
from orapa_assistant.progressive import ProgressiveSolver
from orapa_assistant.raytracer import Configuration
from orapa_assistant.solver import CellContent, CellObservation, Observation, Solver


def test_main_window_can_be_created() -> None:
    app = QApplication.instance() or QApplication([])
    window = MainWindow(Solver([REAL_GAME_SOLUTION]))
    assert bool(window.windowFlags() & Qt.WindowStaysOnTopHint)
    # La grille — elle seule — vit dans sa propre fenêtre détachée, elle
    # aussi toujours au-dessus ; le reste (variantes, affichage, conseils)
    # reste sur la fenêtre principale, dans le volet « Certitudes et
    # conseils ».
    assert window.grid_window is not window
    assert bool(window.grid_window.windowFlags() & Qt.WindowStaysOnTopHint)
    assert window.grid_window.centralWidget() is window.board_panel
    assert [
        window.panel_tabs.tabText(index)
        for index in range(window.panel_tabs.count())
    ] == ["Saisie", "Certitudes et conseils"]
    assert window.entry_panel.isVisibleTo(window)
    assert not window.grid_side_widget.isVisibleTo(window)
    window.panel_tabs.setCurrentIndex(1)
    assert not window.entry_panel.isVisibleTo(window)
    assert window.grid_side_widget.isVisibleTo(window)
    window.panel_tabs.setCurrentIndex(0)
    assert window.board.width() < 450
    assert window.board_panel.width() == window.board.width() + 20
    assert window.reset_button.text() == "Nouvelle partie"
    assert [label.text() for label in window.right_marker_labels] == list(RIGHT_POINTS)
    assert [label.text() for label in window.bottom_marker_labels] == list(BOTTOM_POINTS)
    assert "Configurations retenues par le modèle : 1" in window.count_label.text()
    assert "losange blanc" in window.certainty_label.text()
    assert window.entry_selector.value() is None
    assert window.exit_selector.value() is None
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
    assert all(
        window.board.columnWidth(column) == BOARD_COLUMN_WIDTH
        for column in range(10)
    )
    assert all(
        window.board.rowHeight(row) == BOARD_ROW_HEIGHT for row in range(8)
    )
    assert [label.width() for label in window.bottom_marker_labels] == [
        window.board.columnWidth(column) for column in range(10)
    ]
    assert [label.height() for label in window.right_marker_labels] == [
        window.board.rowHeight(row) for row in range(8)
    ]
    assert window.color_selector.label_for(RayColor.LIGHT_YELLOW) == "Jaune citron"
    assert window.color_selector.label_for(RayColor.LIGHT_BLUE) == "Bleu ciel"
    window.entry_selector.set_value("A")
    assert window.entry_selector.value() == "A"
    assert not window.absorbed.isEnabled()
    window.action_type.setCurrentIndex(1)
    assert window.cell_row.isEnabled()
    assert window.cell_content.findData(CellContent.DIAMOND) == -1
    assert not window.entry_selector.isEnabled()
    assert window.wave_container.isHidden()
    assert window.cell_container.isVisible()
    window.action_type.setCurrentIndex(0)
    assert not window.cell_container.isVisibleTo(window)
    window.black_checkbox.setChecked(True)
    window.absorbed.setChecked(True)
    assert not window.exit_selector.isEnabled()
    assert not window.color_selector.isEnabled()
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


def test_frequency_map_view_colours_the_board() -> None:
    app = QApplication.instance() or QApplication([])
    solver = ProgressiveSolver()
    solver.add_observations(REAL_GAME_HISTORY[:3])
    window = MainWindow(solver)

    index = window.solution_view.findData("frequency")
    assert index >= 0
    assert window.solution_view.itemText(index).startswith("Carte de fréquences")
    assert not window.solution_view.isHidden()

    window.solution_view.setCurrentIndex(index)
    assert "Carte de fréquences" in window.certainty_label.text()
    painted = [
        window.board.item(row, column).text()
        for row in range(8)
        for column in range(10)
        if window.board.item(row, column).text() != "·"
    ]
    assert painted
    assert all(text.isdigit() for text in painted)

    window.solution_view.setCurrentIndex(0)
    assert "Formes communes" in window.certainty_label.text()
    window.close()


def test_board_paints_gem_codes_without_error() -> None:
    app = QApplication.instance() or QApplication([])
    window = MainWindow(Solver([REAL_GAME_SOLUTION]))
    window.show()
    app.processEvents()
    # La solution de référence mélange carrés pleins et demi-carrés ; le rendu
    # (délégué) ne doit pas lever.
    codes = {
        window.board.item(row, column).text()
        for row in range(8)
        for column in range(10)
    }
    assert any(code[-2:] in {"hg", "hd", "bg", "bd"} for code in codes if len(code) > 1)
    assert "B" in codes  # au moins un carré plein (triangle bleu, pointe)
    pixmap = window.board.grab()
    assert not pixmap.isNull()
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
