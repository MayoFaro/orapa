from __future__ import annotations

from collections.abc import Callable

from PySide6.QtCore import QSignalBlocker, QThread, Qt, Signal
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QButtonGroup,
    QComboBox,
    QCheckBox,
    QFormLayout,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
    QHeaderView,
)

from ..border import BOTTOM_POINTS, LEFT_POINTS, RIGHT_POINTS, TOP_POINTS
from ..cell_display import configuration_cell_codes
from ..colors import RayColor
from ..history_store import HistoryStore
from ..raytracer import Configuration
from ..progressive import ProgressiveSolver
from ..solver import CellContent, CellObservation, Observation


COLOR_LABELS = {
    RayColor.TRANSPARENT: "Transparent",
    RayColor.WHITE: "Blanc",
    RayColor.RED: "Rouge",
    RayColor.YELLOW: "Jaune",
    RayColor.BLUE: "Bleu",
    RayColor.PINK: "Rose",
    RayColor.LIGHT_YELLOW: "Jaune citron",
    RayColor.LIGHT_BLUE: "Bleu ciel",
    RayColor.ORANGE: "Orange",
    RayColor.GREEN: "Vert",
    RayColor.VIOLET: "Violet",
    RayColor.LIGHT_ORANGE: "Orange clair",
    RayColor.LIGHT_GREEN: "Vert clair",
    RayColor.LIGHT_VIOLET: "Violet clair",
    RayColor.BLACK: "Noir",
    RayColor.GRAY: "Gris",
}

CELL_CONTENT_LABELS = {
    CellContent.NOTHING: "Rien",
    CellContent.WHITE: "Pierre blanche",
    CellContent.RED: "Pierre rouge",
    CellContent.YELLOW: "Pierre jaune",
    CellContent.BLUE: "Pierre bleue",
    CellContent.DIAMOND: "Diamant",
    CellContent.BLACK_BODY: "Signal absorbé (corps noir)",
}


class SolverWorker(QThread):
    succeeded = Signal()
    failed = Signal(str)

    def __init__(self, operation: Callable[[], None], parent=None) -> None:
        super().__init__(parent)
        self.operation = operation

    def run(self) -> None:
        try:
            self.operation()
        except Exception as error:  # transmis proprement au thread graphique
            self.failed.emit(str(error))
        else:
            self.succeeded.emit()

GEM_COLORS = {
    "red": QColor("#ef2929"),
    "yellow": QColor("#f6c431"),
    "blue": QColor("#1775bd"),
    "white": QColor("#ffffff"),
    "diamond": QColor("#dff8ff"),
    "black_body": QColor("#111936"),
}

CELL_BACKGROUNDS = {
    "W": GEM_COLORS["white"],
    "R": GEM_COLORS["red"],
    "Y": GEM_COLORS["yellow"],
    "B": GEM_COLORS["blue"],
    "D": GEM_COLORS["diamond"],
    "N": GEM_COLORS["black_body"],
}

GEM_LABELS = {
    "white_diamond": "losange blanc",
    "white_triangle": "triangle blanc",
    "blue": "triangle bleu",
    "red": "parallélogramme rouge",
    "yellow": "triangle jaune",
    "diamond": "diamant transparent",
    "black_body": "corps noir",
}

BOARD_COLUMN_WIDTH = 38
BOARD_ROW_HEIGHT = 30
BOTTOM_MARKER_HEIGHT = 20
RIGHT_MARKER_WIDTH = 26
POINT_CHIP_WIDTH = 19
POINT_CHIP_HEIGHT = 20
COLOR_CHIP_WIDTH = 94
COLOR_CHIP_HEIGHT = 18

CHIP_STYLE = """
QPushButton {
    border: 1px solid #8b949e;
    border-radius: 7px;
    background: #f3f4f6;
    padding: 0;
}
QPushButton:checked {
    border: 2px solid #075985;
    background: #1685c5;
    color: white;
    font-weight: bold;
}
QPushButton:disabled {
    border-color: #c7cbd1;
    background: #e5e7eb;
    color: #9ca3af;
}
"""


class MainWindow(QMainWindow):
    def __init__(self, solver, history_store: HistoryStore | None = None) -> None:
        super().__init__()
        self.solver = solver
        self.history_store = history_store
        self._worker: SolverWorker | None = None
        self.setWindowTitle("Orapa Mine Assistant")
        self.resize(900, 650)

        self.board = QTableWidget(8, 10)
        self.board.setHorizontalHeaderLabels([str(number) for number in range(1, 11)])
        self.board.setVerticalHeaderLabels(list("ABCDEFGH"))
        self.board.setEditTriggers(QTableWidget.NoEditTriggers)
        self.board.setSelectionMode(QTableWidget.NoSelection)
        self.board.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.board.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        horizontal_header = self.board.horizontalHeader()
        vertical_header = self.board.verticalHeader()
        horizontal_header.setSectionResizeMode(QHeaderView.Fixed)
        vertical_header.setSectionResizeMode(QHeaderView.Fixed)
        # Certains thèmes imposent une taille minimale supérieure à la taille
        # demandée. Il faut la lever avant de redimensionner chaque section,
        # puis calculer le widget avec les tailles réellement retenues par Qt.
        horizontal_header.setMinimumSectionSize(1)
        vertical_header.setMinimumSectionSize(1)
        horizontal_header.setDefaultSectionSize(BOARD_COLUMN_WIDTH)
        vertical_header.setDefaultSectionSize(BOARD_ROW_HEIGHT)
        for column in range(self.board.columnCount()):
            horizontal_header.resizeSection(column, BOARD_COLUMN_WIDTH)
        for row in range(self.board.rowCount()):
            vertical_header.resizeSection(row, BOARD_ROW_HEIGHT)
        column_widths = tuple(
            horizontal_header.sectionSize(column)
            for column in range(self.board.columnCount())
        )
        row_heights = tuple(
            vertical_header.sectionSize(row)
            for row in range(self.board.rowCount())
        )
        header_height = horizontal_header.sizeHint().height()
        board_width = (
            vertical_header.sizeHint().width()
            + horizontal_header.length()
            + (2 * self.board.frameWidth())
        )
        board_height = header_height + vertical_header.length() + (
            2 * self.board.frameWidth()
        )
        self.board.setFixedSize(board_width, board_height)
        for row in range(8):
            for column in range(10):
                item = QTableWidgetItem("·")
                item.setTextAlignment(Qt.AlignCenter)
                self.board.setItem(row, column, item)

        board_frame = QGridLayout()
        board_frame.setContentsMargins(0, 0, 0, 0)
        board_frame.setSpacing(2)
        board_frame.addWidget(self.board, 0, 0)
        right_markers = QVBoxLayout()
        right_markers.setContentsMargins(
            0, header_height + self.board.frameWidth(), 0, 0
        )
        right_markers.setSpacing(0)
        self.right_marker_labels = []
        for marker, marker_height in zip(RIGHT_POINTS, row_heights):
            label = QLabel(marker)
            label.setAlignment(Qt.AlignCenter)
            label.setFixedSize(RIGHT_MARKER_WIDTH, marker_height)
            right_markers.addWidget(label)
            self.right_marker_labels.append(label)
        right_markers.addStretch()
        right_widget = QWidget()
        right_widget.setLayout(right_markers)
        right_widget.setFixedHeight(board_height)
        board_frame.addWidget(right_widget, 0, 1)
        bottom_markers = QHBoxLayout()
        bottom_markers.setContentsMargins(
            self.board.verticalHeader().sizeHint().width()
            + self.board.frameWidth(),
            0,
            0,
            0,
        )
        bottom_markers.setSpacing(0)
        self.bottom_marker_labels = []
        for marker, marker_width in zip(BOTTOM_POINTS, column_widths):
            label = QLabel(marker)
            label.setAlignment(Qt.AlignCenter)
            label.setFixedSize(marker_width, BOTTOM_MARKER_HEIGHT)
            bottom_markers.addWidget(label)
            self.bottom_marker_labels.append(label)
        bottom_markers.addStretch()
        bottom_widget = QWidget()
        bottom_widget.setLayout(bottom_markers)
        bottom_widget.setFixedHeight(BOTTOM_MARKER_HEIGHT)
        board_frame.addWidget(bottom_widget, 1, 0)
        self.board_panel = QWidget()
        self.board_panel.setLayout(board_frame)
        self.board_panel.setFixedSize(
            board_width + board_frame.spacing() + RIGHT_MARKER_WIDTH,
            board_height + board_frame.spacing() + BOTTOM_MARKER_HEIGHT,
        )

        self.count_label = QLabel()
        self.certainty_label = QLabel()
        self.recommendation_label = QLabel()
        self.solution_view_label = QLabel("Afficher")
        self.solution_view = QComboBox()
        self.solution_view.currentIndexChanged.connect(self._show_certainties)
        self.count_label.setWordWrap(True)
        self.certainty_label.setWordWrap(True)
        self.recommendation_label.setWordWrap(True)
        self.history = QListWidget()

        self.diamond_checkbox = QCheckBox("Variante diamant")
        self.black_checkbox = QCheckBox("Variante corps noir")
        self.diamond_checkbox.setChecked(getattr(solver, "include_diamond", False))
        self.black_checkbox.setChecked(getattr(solver, "include_black_body", False))
        self.diamond_checkbox.toggled.connect(self._change_variants)
        self.black_checkbox.toggled.connect(self._change_variants)

        self.entry_group = QButtonGroup(self)
        self.entry_group.setExclusive(True)
        self.exit_group = QButtonGroup(self)
        self.exit_group.setExclusive(True)
        self.color_group = QButtonGroup(self)
        self.color_group.setExclusive(True)
        self.entry_buttons: dict[str, QPushButton] = {}
        self.exit_buttons: dict[str, QPushButton] = {}
        self.color_buttons: dict[RayColor, QPushButton] = {}
        self.absorbed = QCheckBox("L’onde a été absorbée")
        self.action_type = QComboBox()
        self.action_type.addItem("Envoyer une onde", "wave")
        self.action_type.addItem("Examiner une case", "cell")
        self.cell_row = QComboBox()
        self.cell_row.addItems(list("ABCDEFGH"))
        self.cell_column = QComboBox()
        self.cell_column.addItems([str(number) for number in range(1, 11)])
        self.cell_content = QComboBox()
        number_points = TOP_POINTS + RIGHT_POINTS
        letter_points = LEFT_POINTS + BOTTOM_POINTS
        for point in number_points + letter_points:
            entry_button = self._make_chip(
                point, POINT_CHIP_WIDTH, POINT_CHIP_HEIGHT
            )
            entry_button.setProperty("border_point", point)
            entry_button.clicked.connect(
                lambda checked, selected=point: self._mirror_entry_to_exit(
                    selected, checked
                )
            )
            self.entry_group.addButton(entry_button)
            self.entry_buttons[point] = entry_button

            exit_button = self._make_chip(
                point, POINT_CHIP_WIDTH, POINT_CHIP_HEIGHT
            )
            exit_button.setProperty("border_point", point)
            self.exit_group.addButton(exit_button)
            self.exit_buttons[point] = exit_button

        for color, label in COLOR_LABELS.items():
            color_button = self._make_chip(
                label, COLOR_CHIP_WIDTH, COLOR_CHIP_HEIGHT
            )
            color_button.setProperty("ray_color", color.value)
            self.color_group.addButton(color_button)
            self.color_buttons[color] = color_button

        self.entry_buttons["1"].setChecked(True)
        self.exit_buttons["1"].setChecked(True)
        self.color_buttons[RayColor.TRANSPARENT].setChecked(True)

        point_rows = QVBoxLayout()
        point_rows.setContentsMargins(0, 0, 0, 0)
        point_rows.setSpacing(2)
        for label_text, points, buttons in (
            ("Entrée chiffres", number_points, self.entry_buttons),
            ("Entrée lettres", letter_points, self.entry_buttons),
            ("Sortie chiffres", number_points, self.exit_buttons),
            ("Sortie lettres", letter_points, self.exit_buttons),
        ):
            row = QHBoxLayout()
            row.setContentsMargins(0, 0, 0, 0)
            row.setSpacing(1)
            label = QLabel(label_text)
            label.setFixedWidth(84)
            row.addWidget(label)
            for point in points:
                row.addWidget(buttons[point])
            point_rows.addLayout(row)

        colors = QVBoxLayout()
        colors.setContentsMargins(0, 0, 0, 0)
        colors.setSpacing(1)
        color_label = QLabel("Couleur")
        color_label.setAlignment(Qt.AlignCenter)
        colors.addWidget(color_label)
        for color in COLOR_LABELS:
            colors.addWidget(self.color_buttons[color])

        wave_layout = QHBoxLayout()
        wave_layout.setContentsMargins(0, 0, 0, 0)
        wave_layout.setSpacing(8)
        wave_layout.addLayout(point_rows)
        wave_layout.addLayout(colors)
        wave_layout.addStretch(1)
        self.wave_panel = QWidget()
        self.wave_panel.setLayout(wave_layout)

        left = QVBoxLayout()
        left.setContentsMargins(0, 0, 0, 0)
        left.setSpacing(4)
        left.addWidget(self.board_panel, 0, Qt.AlignTop | Qt.AlignLeft)
        left.addWidget(self.wave_panel, 0, Qt.AlignTop | Qt.AlignLeft)
        left.addStretch(1)
        self.left_panel = QWidget()
        self.left_panel.setLayout(left)
        self.absorbed.toggled.connect(lambda: self._update_result_controls())
        self.action_type.currentIndexChanged.connect(
            lambda: self._update_result_controls()
        )
        self._refresh_cell_contents()

        self.add_button = QPushButton("Ajouter")
        self.add_button.clicked.connect(self._add_observation)
        self.remove_button = QPushButton("Supprimer la sélection")
        self.remove_button.clicked.connect(self._remove_observation)
        self.reset_button = QPushButton("Nouvelle partie")
        self.reset_button.clicked.connect(self._reset_game)

        form = QFormLayout()
        form.addRow("Action", self.action_type)
        form.addRow(self.absorbed)
        form.addRow("Case — ligne", self.cell_row)
        form.addRow("Case — colonne", self.cell_column)
        form.addRow("Résultat de la case", self.cell_content)
        form.addRow(self.add_button)

        right = QVBoxLayout()
        right.addWidget(self.diamond_checkbox)
        right.addWidget(self.black_checkbox)
        right.addWidget(self.count_label)
        right.addWidget(self.certainty_label)
        right.addWidget(self.recommendation_label)
        solution_view_row = QHBoxLayout()
        solution_view_row.addWidget(self.solution_view_label)
        solution_view_row.addWidget(self.solution_view)
        right.addLayout(solution_view_row)
        right.addLayout(form)
        self.history_label = QLabel("Historique")
        if self.history_store is not None:
            self.history_label.setToolTip(
                f"Sauvegarde locale : {self.history_store.path}"
            )
        right.addWidget(self.history_label)
        right.addWidget(self.history)
        history_buttons = QHBoxLayout()
        history_buttons.addWidget(self.remove_button)
        history_buttons.addWidget(self.reset_button)
        right.addLayout(history_buttons)

        self.right_panel = QWidget()
        self.right_panel.setLayout(right)
        self.right_panel.setFixedWidth(320)

        layout = QHBoxLayout()
        layout.addWidget(self.left_panel, 0, Qt.AlignTop | Qt.AlignLeft)
        layout.addStretch(1)
        layout.addWidget(self.right_panel)
        central = QWidget()
        central.setLayout(layout)
        self.setCentralWidget(central)
        self._update_result_controls()
        self._persist_current()
        self.refresh()

    def _add_observation(self) -> None:
        try:
            if self.action_type.currentData() == "cell":
                observation = CellObservation(
                    self.cell_row.currentText(),
                    int(self.cell_column.currentText()),
                    self.cell_content.currentData(),
                )
            else:
                entry = self._selected_border(self.entry_group)
                if self.absorbed.isChecked():
                    observation = Observation(entry, absorbed=True)
                else:
                    observation = Observation(
                        entry,
                        self._selected_border(self.exit_group),
                        self._selected_color(),
                    )
        except ValueError as error:
            QMessageBox.warning(self, "Saisie incomplète", str(error))
            return
        self._start_solver_task(
            lambda: self.solver.add_observation(observation),
            show_result_alerts=True,
        )

    def _show_result_alerts(self) -> None:
        if self.solver.candidate_count == 0:
            suspects = self.solver.suspect_observations()
            detail = ""
            if suspects:
                index, restored = suspects[0]
                detail = f"\nLa saisie n°{index + 1} est suspecte ({restored} candidat(s) restauré(s))."
            QMessageBox.warning(self, "Contradiction", "Aucune configuration compatible." + detail)
        elif self.solver.candidate_count == 1:
            QMessageBox.information(
                self,
                "Configuration unique dans le modèle",
                "Le moteur ne conserve qu’une configuration compatible.",
            )
        elif self.solver.candidate_count == 2:
            QMessageBox.information(
                self,
                "Deux configurations retenues",
                "Le moteur ne conserve que deux configurations dans son "
                "modèle. Vous pouvez les comparer avec le sélecteur Afficher.",
            )

    def _set_busy(self, busy: bool) -> None:
        self.action_type.setEnabled(not busy)
        self.cell_row.setEnabled(not busy)
        self.cell_column.setEnabled(not busy)
        self.cell_content.setEnabled(not busy)
        self.diamond_checkbox.setEnabled(not busy)
        self.black_checkbox.setEnabled(not busy)
        self.add_button.setEnabled(not busy)
        self.remove_button.setEnabled(not busy)
        self.reset_button.setEnabled(not busy)
        self.solution_view.setEnabled(not busy)
        self._update_result_controls(force_busy=busy)
        if busy:
            self.count_label.setText("Mise à jour des contraintes…")
            self.recommendation_label.setText(
                "Calcul en arrière-plan — l’interface reste réactive"
            )

    def _start_solver_task(
        self,
        operation: Callable[[], None],
        *,
        show_result_alerts: bool = False,
        persist_current: bool = True,
    ) -> None:
        if self._worker is not None:
            return
        self._set_busy(True)

        def operation_with_persistence() -> None:
            operation()
            if persist_current:
                self._persist_current()

        worker = SolverWorker(operation_with_persistence, self)
        self._worker = worker

        def succeeded() -> None:
            self._set_busy(False)
            self.refresh()
            if show_result_alerts:
                self._show_result_alerts()

        def failed(message: str) -> None:
            self._set_busy(False)
            self.refresh()
            QMessageBox.critical(self, "Opération impossible", message)

        def cleanup() -> None:
            worker.deleteLater()
            self._worker = None

        worker.succeeded.connect(succeeded)
        worker.failed.connect(failed)
        worker.finished.connect(cleanup)
        worker.start()

    def _remove_observation(self) -> None:
        item = self.history.currentItem()
        if item is not None:
            history_index = item.data(Qt.UserRole)
            self._start_solver_task(
                lambda: self.solver.remove_observation(history_index)
            )

    def _reset_game(self) -> None:
        if self.solver.history:
            answer = QMessageBox.question(
                self,
                "Nouvelle partie",
                "Archiver cette partie et en commencer une nouvelle ?",
            )
            if answer != QMessageBox.Yes:
                return

        def clear_and_archive() -> None:
            if self.history_store is not None:
                self.history_store.start_new_game(
                    include_diamond=getattr(
                        self.solver, "include_diamond", False
                    ),
                    include_black_body=getattr(
                        self.solver, "include_black_body", False
                    ),
                    reason="new_game",
                )
            self.solver.clear()

        self._start_solver_task(clear_and_archive, persist_current=False)

    def _persist_current(self) -> None:
        if self.history_store is None:
            return
        self.history_store.save_current(
            self.solver.history,
            include_diamond=getattr(self.solver, "include_diamond", False),
            include_black_body=getattr(
                self.solver, "include_black_body", False
            ),
        )

    def closeEvent(self, event) -> None:
        if self._worker is not None and self._worker.isRunning():
            self._worker.requestInterruption()
            self._worker.wait()
        try:
            self._persist_current()
        except OSError as error:
            QMessageBox.warning(
                self,
                "Historique non sauvegardé",
                f"Impossible d’enregistrer l’historique : {error}",
            )
        super().closeEvent(event)

    def refresh(self) -> None:
        if self.solver.candidate_count is None:
            raw_count = getattr(self.solver, "raw_combination_count", None)
            domains = getattr(self.solver, "domain_sizes", {})
            domain_text = "\n".join(
                f"{GEM_LABELS.get(name, name)} : {count}"
                for name, count in domains.items()
            )
            applied = getattr(self.solver, "applied_relation_count", 0)
            deferred = getattr(self.solver, "deferred_relation_count", 0)
            representatives = getattr(self.solver, "strategy_sample_count", 0)
            self.count_label.setText(
                "Propagation relationnelle en cours\n"
                f"Borne cartésienne après propagation : {raw_count:,}\n"
                f"Pré-filtres calculés : {applied} — différés : {deferred}\n"
                + (
                    f"Hypothèses globales témoins : {representatives}\n"
                    if representatives else ""
                )
                + "Cette borne n’est pas un nombre de solutions.\n"
                f"{domain_text}"
            )
        else:
            self.count_label.setText(
                "Configurations retenues par le modèle : "
                f"{self.solver.candidate_count}\n"
                "Énumération exhaustive des domaines filtrés"
            )
        scores = self.solver.rank_next_moves()
        if scores:
            best = scores[0]
            qualifier = (
                "exacte"
                if getattr(self.solver, "recommendation_exact", True)
                else "estimée"
            )
            self.recommendation_label.setText(
                f"Action conseillée ({qualifier}) : {best.label}\n"
                f"Pire cas : {best.worst_case} — Entropie : {best.entropy:.2f} bits"
            )
        else:
            if self.solver.candidate_count == 1:
                self.recommendation_label.setText(
                    "Configuration unique dans le modèle"
                )
            else:
                self.recommendation_label.setText(
                    "Recherche de modèles globaux pour classer les actions"
                )

        self.history.clear()
        for history_index in range(len(self.solver.history) - 1, -1, -1):
            observation = self.solver.history[history_index]
            if isinstance(observation, CellObservation):
                text = (
                    f"Case {observation.cell} → "
                    f"{CELL_CONTENT_LABELS[observation.content]}"
                )
            else:
                text = (
                    f"{observation.entry} → onde absorbée"
                    if observation.absorbed
                    else f"{observation.entry} → {observation.exit_point}  "
                    f"{COLOR_LABELS[observation.color]}"
                )
            item = QListWidgetItem(text)
            item.setData(Qt.UserRole, history_index)
            self.history.addItem(item)
        if self.history_store is not None:
            try:
                archived_count = max(len(self.history_store.sessions()) - 1, 0)
            except OSError:
                self.history_label.setText("Historique — sauvegarde indisponible")
            else:
                suffix = (
                    f" — {archived_count} partie(s) archivée(s)"
                    if archived_count
                    else ""
                )
                self.history_label.setText(
                    f"Historique — sauvegarde automatique{suffix}"
                )

        certain_gems = tuple(getattr(self.solver, "certain_gems", ()))
        if certain_gems:
            labels = ", ".join(GEM_LABELS.get(gem.name, gem.name) for gem in certain_gems)
            self.certainty_label.setText(
                f"Formes communes aux configurations retenues : {labels}"
            )
        else:
            self.certainty_label.setText(
                "Formes communes aux configurations retenues : aucune"
            )
        self._refresh_solution_view()
        self._show_certainties()

    def _refresh_solution_view(self) -> None:
        candidates = tuple(getattr(self.solver, "candidates", ()))
        show_choices = len(candidates) == 2
        previous = self.solution_view.currentIndex()
        blocker = QSignalBlocker(self.solution_view)
        self.solution_view.clear()
        self.solution_view.addItem("Certitudes communes", None)
        if show_choices:
            self.solution_view.addItem("Configuration retenue 1", 0)
            self.solution_view.addItem("Configuration retenue 2", 1)
            self.solution_view.setCurrentIndex(min(previous, 2))
        else:
            self.solution_view.setCurrentIndex(0)
        del blocker
        self.solution_view_label.setVisible(show_choices)
        self.solution_view.setVisible(show_choices)

    @staticmethod
    def _make_chip(text: str, width: int, height: int) -> QPushButton:
        button = QPushButton(text)
        button.setCheckable(True)
        button.setFixedSize(width, height)
        button.setStyleSheet(CHIP_STYLE)
        return button

    def _mirror_entry_to_exit(self, point: str, checked: bool) -> None:
        if checked:
            self.exit_buttons[point].setChecked(True)

    @staticmethod
    def _selected_border(group: QButtonGroup) -> str:
        button = group.checkedButton()
        if button is not None:
            return str(button.property("border_point"))
        raise ValueError("Sélectionnez un point de bord")

    def _selected_color(self) -> RayColor:
        button = self.color_group.checkedButton()
        if button is None:
            raise ValueError("Sélectionnez une couleur")
        return RayColor(button.property("ray_color"))

    def _show_certainties(self, _index: int | None = None) -> None:
        for row in range(8):
            for column in range(10):
                item = self.board.item(row, column)
                item.setText("·")
                item.setBackground(QColor("#f3f3f3"))
        selected_candidate = self.solution_view.currentData()
        candidates = tuple(getattr(self.solver, "candidates", ()))
        if selected_candidate is not None and len(candidates) == 2:
            displayed_gems = candidates[selected_candidate].gems
        else:
            displayed_gems = tuple(getattr(self.solver, "certain_gems", ()))
        if not displayed_gems:
            return
        configuration = Configuration(tuple(displayed_gems))
        codes = configuration_cell_codes(configuration)
        for row in range(8):
            for column in range(10):
                code = codes[row][column]
                item = self.board.item(row, column)
                item.setText(code)
                if code != "·" and "/" not in code:
                    item.setBackground(CELL_BACKGROUNDS[code[0]])

    def _update_result_controls(self, force_busy: bool = False) -> None:
        cell_mode = self.action_type.currentData() == "cell"
        black_enabled = self.black_checkbox.isChecked()
        self.absorbed.setEnabled(not force_busy and black_enabled and not cell_mode)
        enabled = not force_busy and not self.absorbed.isChecked() and not cell_mode
        for button in self.entry_buttons.values():
            button.setEnabled(not force_busy and not cell_mode)
        for button in self.exit_buttons.values():
            button.setEnabled(enabled)
        for button in self.color_buttons.values():
            button.setEnabled(enabled)
        self.cell_row.setEnabled(not force_busy and cell_mode)
        self.cell_column.setEnabled(not force_busy and cell_mode)
        self.cell_content.setEnabled(not force_busy and cell_mode)

    def _refresh_cell_contents(self) -> None:
        previous = self.cell_content.currentData()
        allowed = [
            CellContent.NOTHING, CellContent.WHITE, CellContent.RED,
            CellContent.YELLOW, CellContent.BLUE,
        ]
        if self.diamond_checkbox.isChecked():
            allowed.append(CellContent.DIAMOND)
        if self.black_checkbox.isChecked():
            allowed.append(CellContent.BLACK_BODY)
        self.cell_content.clear()
        for content in allowed:
            self.cell_content.addItem(CELL_CONTENT_LABELS[content], content)
        if previous in allowed:
            self.cell_content.setCurrentIndex(allowed.index(previous))

    def _change_variants(self) -> None:
        if self._worker is not None:
            return
        if self.solver.history:
            answer = QMessageBox.question(
                self,
                "Changer de variante",
                "Changer les extensions archivera cette partie et en "
                "commencera une nouvelle. Continuer ?",
            )
            if answer != QMessageBox.Yes:
                diamond_blocker = QSignalBlocker(self.diamond_checkbox)
                black_blocker = QSignalBlocker(self.black_checkbox)
                self.diamond_checkbox.setChecked(
                    getattr(self.solver, "include_diamond", False)
                )
                self.black_checkbox.setChecked(
                    getattr(self.solver, "include_black_body", False)
                )
                del diamond_blocker, black_blocker
                return
        if not self.black_checkbox.isChecked():
            self.absorbed.setChecked(False)
        include_diamond = self.diamond_checkbox.isChecked()
        include_black_body = self.black_checkbox.isChecked()
        if self.history_store is not None:
            try:
                self.history_store.start_new_game(
                    include_diamond=include_diamond,
                    include_black_body=include_black_body,
                    reason="variant_change",
                )
            except OSError as error:
                QMessageBox.critical(
                    self,
                    "Historique non sauvegardé",
                    "Le changement de variante est annulé car l’historique "
                    f"ne peut pas être archivé : {error}",
                )
                diamond_blocker = QSignalBlocker(self.diamond_checkbox)
                black_blocker = QSignalBlocker(self.black_checkbox)
                self.diamond_checkbox.setChecked(
                    getattr(self.solver, "include_diamond", False)
                )
                self.black_checkbox.setChecked(
                    getattr(self.solver, "include_black_body", False)
                )
                del diamond_blocker, black_blocker
                return
        self.solver = ProgressiveSolver(
            include_diamond=include_diamond,
            include_black_body=include_black_body,
        )
        self._refresh_cell_contents()
        self._update_result_controls()
        self.refresh()
