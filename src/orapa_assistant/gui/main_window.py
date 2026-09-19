from __future__ import annotations

from collections.abc import Callable

from PySide6.QtCore import QPointF, QRectF, QSignalBlocker, QThread, Qt, Signal
from PySide6.QtGui import QColor, QPainter, QPen, QPolygonF
from PySide6.QtWidgets import (
    QComboBox,
    QCheckBox,
    QFormLayout,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QListView,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QStyledItemDelegate,
    QTabBar,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
    QHeaderView,
)

from ..border import BOTTOM_POINTS, RIGHT_POINTS
from ..cell_display import configuration_cell_codes
from ..history_store import HistoryStore
from ..raytracer import Configuration
from ..progressive import ProgressiveSolver
from ..solver import CellContent, CellObservation, Observation
from .chips import ObservationChipPanel, RAYCOLOR_LABELS as COLOR_LABELS

CELL_CONTENT_LABELS = {
    CellContent.NOTHING: "Rien",
    CellContent.WHITE: "Pierre blanche",
    CellContent.RED: "Pierre rouge",
    CellContent.YELLOW: "Pierre jaune",
    CellContent.BLUE: "Pierre bleue",
    CellContent.DIAMOND: "Diamant",
    CellContent.BLACK_BODY: "Signal absorbé (corps noir)",
}


def _format_observation_text(observation) -> str:
    if isinstance(observation, CellObservation):
        return f"Case {observation.cell} → {CELL_CONTENT_LABELS[observation.content]}"
    if observation.absorbed:
        return f"{observation.entry} → onde absorbée"
    return (
        f"{observation.entry} → {observation.exit_point}  "
        f"{COLOR_LABELS[observation.color]}"
    )


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


def _blend_toward_white(color: QColor, weight: float) -> QColor:
    """Interpole du blanc (poids 0) vers ``color`` (poids 1)."""

    weight = max(0.0, min(1.0, weight))
    return QColor(
        round(255 + (color.red() - 255) * weight),
        round(255 + (color.green() - 255) * weight),
        round(255 + (color.blue() - 255) * weight),
    )


# Coins d'un demi‑carré (fractions de la case) : le suffixe nomme l'angle droit.
_TRIANGLE_CORNERS = {
    "hg": ((0.0, 0.0), (1.0, 0.0), (0.0, 1.0)),
    "hd": ((0.0, 0.0), (1.0, 0.0), (1.0, 1.0)),
    "bg": ((0.0, 0.0), (0.0, 1.0), (1.0, 1.0)),
    "bd": ((1.0, 0.0), (0.0, 1.0), (1.0, 1.0)),
}


class BoardCellDelegate(QStyledItemDelegate):
    """Peint les pierres : triangle orienté pour un demi‑carré, carré sinon.

    Les cases vides et la carte de fréquences (texte + fond) gardent le rendu
    par défaut.
    """

    def paint(self, painter, option, index) -> None:
        code = index.data(Qt.DisplayRole)
        if not code or code == "·" or code[0].isdigit():
            super().paint(painter, option, index)
            return
        painter.save()
        painter.setRenderHint(QPainter.Antialiasing)
        painter.setPen(QPen(QColor("#2b2b2b"), 1))
        cell = QRectF(option.rect).adjusted(0.5, 0.5, -0.5, -0.5)
        for part in code.split("/"):
            painter.setBrush(CELL_BACKGROUNDS.get(part[0], QColor("#8a8a8a")))
            corners = _TRIANGLE_CORNERS.get(part[1:])
            if corners is None:
                painter.drawRect(cell)
            else:
                painter.drawPolygon(
                    QPolygonF(
                        [
                            QPointF(
                                cell.left() + fraction_x * cell.width(),
                                cell.top() + fraction_y * cell.height(),
                            )
                            for fraction_x, fraction_y in corners
                        ]
                    )
                )
        painter.restore()


GEM_LABELS = {
    "white_diamond": "losange blanc",
    "white_triangle": "triangle blanc",
    "blue": "triangle bleu",
    "red": "parallélogramme rouge",
    "yellow": "triangle jaune",
    "diamond": "diamant transparent",
    "black_body": "corps noir",
}

BOARD_COLUMN_WIDTH = 22
BOARD_ROW_HEIGHT = 18
BOTTOM_MARKER_HEIGHT = 14
RIGHT_MARKER_WIDTH = 18


class MainWindow(QMainWindow):
    def __init__(self, solver, history_store: HistoryStore | None = None) -> None:
        super().__init__()
        self.solver = solver
        self.history_store = history_store
        self._worker: SolverWorker | None = None
        self.setWindowTitle("Orapa Mine Assistant")
        # Hauteur retenue pour chaque onglet (« Saisie » / « Certitudes et
        # conseils »), pour la restaurer lors d'un changement d'onglet
        # plutôt que d'imposer systématiquement la taille par défaut — voir
        # `_switch_panel`.
        self._panel_heights: dict[int, int] = {}
        self._current_panel_index: int | None = None

        self.board = QTableWidget(8, 10)
        self.board.setHorizontalHeaderLabels([str(number) for number in range(1, 11)])
        self.board.setVerticalHeaderLabels(list("ABCDEFGH"))
        self.board.setEditTriggers(QTableWidget.NoEditTriggers)
        self.board.setSelectionMode(QTableWidget.NoSelection)
        self.board.setItemDelegate(BoardCellDelegate(self.board))
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
        # Largeur fixe : le sizeHint() d'un QLabel à retour à la ligne ne
        # reflète sa hauteur réelle qu'une fois une largeur connue — sans
        # quoi Qt sous-estime la place nécessaire tant que le libellé n'a
        # jamais été redimensionné à sa largeur définitive.
        for label in (self.count_label, self.certainty_label, self.recommendation_label):
            label.setFixedWidth(170)
        self.history = QListWidget()
        # Deux colonnes plutôt qu'une longue liste verticale : au-delà d'un
        # certain nombre d'indices, les suivants se décalent naturellement
        # dans la colonne suivante au lieu d'exiger de faire défiler.
        self.history.setFlow(QListView.TopToBottom)
        self.history.setWrapping(True)
        self.history.setResizeMode(QListView.Adjust)

        self.diamond_checkbox = QCheckBox("Variante diamant")
        self.black_checkbox = QCheckBox("Variante corps noir")
        self.diamond_checkbox.setChecked(getattr(solver, "include_diamond", False))
        self.black_checkbox.setChecked(getattr(solver, "include_black_body", False))
        self.diamond_checkbox.toggled.connect(self._change_variants)
        self.black_checkbox.toggled.connect(self._change_variants)

        self.observation_panel = ObservationChipPanel()
        self.entry_selector = self.observation_panel.entry
        self.exit_selector = self.observation_panel.exit
        self.color_selector = self.observation_panel.color
        self.absorbed = QCheckBox("L’onde a été absorbée")
        self.action_type = QComboBox()
        self.action_type.addItem("Envoyer une onde", "wave")
        self.action_type.addItem("Examiner une case", "cell")
        self.cell_row = QComboBox()
        self.cell_row.addItems(list("ABCDEFGH"))
        self.cell_column = QComboBox()
        self.cell_column.addItems([str(number) for number in range(1, 11)])
        self.cell_content = QComboBox()
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

        cell_form = QFormLayout()
        cell_form.addRow("Case — ligne", self.cell_row)
        cell_form.addRow("Case — colonne", self.cell_column)
        cell_form.addRow("Résultat de la case", self.cell_content)
        self.cell_container = QWidget()
        self.cell_container.setLayout(cell_form)
        self._cell_form = cell_form

        wave_layout = QVBoxLayout()
        # La couleur reste à côté des chips point (16 boutons sur 8 rangées :
        # bien plus haut qu'une ligne de menu, donc l'empiler au-dessus
        # augmenterait la hauteur totale au lieu de la réduire). On lui
        # retire juste son libellé, inutile et un peu de hauteur en moins.
        color_column = QVBoxLayout()
        color_column.setContentsMargins(0, 0, 0, 0)
        color_column.addWidget(self.color_selector, 0, Qt.AlignTop)
        color_column.addStretch(1)

        # Le bouton "Ajouter" vit juste sous les chips point, dans sa propre
        # colonne : coller sa taille à celle (plus haute) de la colonne
        # couleur le laissait flotter loin sous les chips point, plus
        # courtes.
        self.add_button.setFixedWidth(280)
        self.add_button.setMinimumHeight(36)
        points_column = QVBoxLayout()
        points_column.setContentsMargins(0, 0, 0, 0)
        points_column.addWidget(self.observation_panel, 0, Qt.AlignTop)
        points_column.addWidget(self.add_button, 0, Qt.AlignLeft)
        points_column.addStretch(1)
        self._points_column = points_column

        wave_row = QHBoxLayout()
        wave_row.setContentsMargins(0, 0, 0, 0)
        wave_row.addLayout(points_column)
        wave_row.addLayout(color_column)
        wave_row.addStretch(1)

        wave_layout.setContentsMargins(0, 0, 0, 0)
        wave_layout.addLayout(wave_row)
        wave_layout.addWidget(self.absorbed)
        self.wave_container = QWidget()
        self.wave_container.setLayout(wave_layout)

        action_row = QHBoxLayout()
        action_row.addWidget(QLabel("Action"))
        action_row.addWidget(self.action_type)
        action_row.addStretch(1)

        observation_layout = QVBoxLayout()
        observation_layout.addLayout(action_row)
        observation_layout.addWidget(self.wave_container)
        observation_layout.addWidget(self.cell_container)
        self.observation_area = QWidget()
        self.observation_area.setLayout(observation_layout)

        # --- Volet « Certitudes et conseils » : choix (variantes, affichage)
        # et détail d'avancée sur deux colonnes plutôt qu'empilés : ça prend
        # moins de hauteur.
        grid_side_choices = QVBoxLayout()
        grid_side_choices.addWidget(self.diamond_checkbox)
        grid_side_choices.addWidget(self.black_checkbox)
        solution_view_row = QHBoxLayout()
        solution_view_row.addWidget(self.solution_view_label)
        solution_view_row.addWidget(self.solution_view)
        grid_side_choices.addLayout(solution_view_row)
        grid_side_choices.addStretch(1)

        grid_side_progress = QVBoxLayout()
        grid_side_progress.addWidget(self.count_label)
        grid_side_progress.addWidget(self.certainty_label)
        grid_side_progress.addWidget(self.recommendation_label)
        grid_side_progress.addStretch(1)

        grid_side_row = QHBoxLayout()
        grid_side_row.addLayout(grid_side_choices)
        grid_side_row.addLayout(grid_side_progress)
        self.grid_side_widget = QWidget()
        self.grid_side_widget.setLayout(grid_side_row)

        # --- Volet « Saisie » : chips à gauche, historique à droite.
        history_column = QVBoxLayout()
        self.history_label = QLabel("Historique")
        if self.history_store is not None:
            self.history_label.setToolTip(
                f"Sauvegarde locale : {self.history_store.path}"
            )
        history_column.addWidget(self.history_label)
        history_column.addWidget(self.history)
        history_buttons = QHBoxLayout()
        history_buttons.addWidget(self.remove_button)
        history_buttons.addWidget(self.reset_button)
        history_column.addLayout(history_buttons)
        history_widget = QWidget()
        history_widget.setLayout(history_column)

        entry_panel_layout = QHBoxLayout()
        entry_panel_layout.addWidget(self.observation_area)
        entry_panel_layout.addWidget(history_widget)
        self.entry_panel = QWidget()
        self.entry_panel.setLayout(entry_panel_layout)

        # Témoin d'activité : un seul, sur la fenêtre principale — la fenêtre
        # de grille ne contient plus que la grille elle-même.
        self.status_indicator = QLabel()
        self.status_indicator.setAlignment(Qt.AlignCenter)
        self.status_indicator.setAutoFillBackground(True)
        self._set_status_indicator(busy=False)

        # --- Fenêtre détachée : uniquement la grille, toujours au-dessus.
        self.grid_window = QMainWindow()
        self.grid_window.setWindowTitle("Orapa Mine — Grille")
        self.grid_window.setCentralWidget(self.board_panel)
        self.grid_window.setWindowFlag(Qt.WindowStaysOnTopHint, True)

        # --- Fenêtre principale : deux volets, « Saisie » et « Certitudes
        # et conseils » (l'ancien contenu du volet grille, hors la grille
        # elle-même, désormais détachée).
        self.panel_tabs = QTabBar()
        self.panel_tabs.addTab("Saisie")
        self.panel_tabs.addTab("Certitudes et conseils")
        self.panel_tabs.currentChanged.connect(self._switch_panel)

        main_layout = QVBoxLayout()
        main_layout.addWidget(self.status_indicator)
        main_layout.addWidget(self.panel_tabs)
        main_layout.addWidget(self.entry_panel)
        main_layout.addWidget(self.grid_side_widget)
        central = QWidget()
        central.setLayout(main_layout)
        self.setCentralWidget(central)
        self.setWindowFlag(Qt.WindowStaysOnTopHint, True)
        self._switch_panel(0)
        self._update_result_controls()
        self._persist_current()
        self.refresh()
        self.grid_window.show()

    def _switch_panel(self, index: int) -> None:
        # On relève la hauteur courante — qu'elle soit celle par défaut ou
        # un redimensionnement manuel de l'utilisateur — juste avant de
        # quitter l'onglet, pour la restaurer telle quelle à son prochain
        # affichage. Comme la mesure se fait ici plutôt que dans un
        # `resizeEvent` général, il n'y a pas besoin de distinguer un
        # redimensionnement « utilisateur » d'un redimensionnement
        # « programmatique » déclenché par ce même changement d'onglet.
        if self._current_panel_index is not None:
            self._panel_heights[self._current_panel_index] = self.height()
        self._current_panel_index = index
        self.entry_panel.setVisible(index == 0)
        self.grid_side_widget.setVisible(index == 1)
        # Sans ça, la fenêtre garde la hauteur du volet le plus haut même une
        # fois basculée sur l'autre, plus court — elle doit épouser le volet
        # affiché, pas le maximum des deux. `invalidate()` est nécessaire
        # avant `activate()` : sans lui, `sizeHint()` peut encore renvoyer
        # une valeur mise en cache pour l'ancienne visibilité des volets. Le
        # layout interne (celui du widget central) ET celui de la fenêtre
        # (QMainWindowLayout, qui garde lui aussi une taille minimale en
        # cache) doivent tous les deux être invalidés : sans le second, le
        # `resize()` ci-dessous est silencieusement replafonné à l'ancienne
        # taille minimale mémorisée par la fenêtre.
        inner_layout = self.centralWidget().layout()
        inner_layout.invalidate()
        inner_layout.activate()
        outer_layout = self.layout()
        outer_layout.invalidate()
        outer_layout.activate()
        target_height = self._panel_heights.get(index)
        if target_height is None:
            target_height = self.centralWidget().sizeHint().height()
        self.resize(self.width(), target_height)

    def _add_observation(self) -> None:
        try:
            if self.action_type.currentData() == "cell":
                observation = CellObservation(
                    self.cell_row.currentText(),
                    int(self.cell_column.currentText()),
                    self.cell_content.currentData(),
                )
            else:
                entry = self.entry_selector.value()
                if entry is None:
                    raise ValueError("Sélectionnez un point d’entrée")
                if self.absorbed.isChecked():
                    observation = Observation(entry, absorbed=True)
                else:
                    exit_point = self.exit_selector.value()
                    color = self.color_selector.value()
                    if exit_point is None or color is None:
                        raise ValueError("Sélectionnez une sortie et une couleur")
                    observation = Observation(entry, exit_point, color)
        except ValueError as error:
            QMessageBox.warning(self, "Saisie incomplète", str(error))
            return
        # La case ne doit pas rester cochée pour la saisie suivante : la
        # plupart des ondes ne sont pas absorbées, mieux vaut décocher par
        # défaut une fois l'observation ajoutée plutôt que forcer l'utilisateur
        # à le faire à chaque fois.
        self.absorbed.setChecked(False)
        # Confirmation immédiate, avant même que le calcul ne démarre : sans
        # ça, un ajout pendant que le moteur travaille encore n'apparaît
        # dans l'historique qu'une fois CE calcul terminé, ce qui peut
        # prendre un moment — laissant croire que la saisie s'est perdue.
        pending_item = QListWidgetItem(
            f"{_format_observation_text(observation)}  (en attente…)"
        )
        pending_item.setData(Qt.UserRole, None)
        self.history.insertItem(0, pending_item)
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

    def _set_status_indicator(self, *, busy: bool) -> None:
        text = "⏳ En réflexion…" if busy else "✓ Prêt"
        colour = "#fff3c4" if busy else "#d9f2d9"
        style = f"padding: 2px 10px; font-weight: bold; background-color: {colour};"
        self.status_indicator.setText(text)
        self.status_indicator.setStyleSheet(style)

    def _set_busy(self, busy: bool) -> None:
        # L'interface reste utilisable pendant un calcul : saisir un nouvel
        # indice et cliquer sur Ajouter interrompt le calcul en cours et
        # relance immédiatement avec la saisie à jour (voir
        # `_start_solver_task`), plutôt que de bloquer les commandes.
        self._set_status_indicator(busy=busy)
        if busy:
            self.count_label.setText("Mise à jour des contraintes…")
            self.recommendation_label.setText(
                "Calcul en arrière-plan — un nouvel ajout l’interrompt "
                "et relance aussitôt"
            )

    def _start_solver_task(
        self,
        operation: Callable[[], None],
        *,
        show_result_alerts: bool = False,
        persist_current: bool = True,
    ) -> None:
        if self._worker is not None:
            # Un calcul est déjà en cours : on l'interrompt pour repartir
            # aussitôt avec la demande à jour (nouvel indice, suppression,
            # nouvelle partie...) au lieu d'ignorer la saisie ou de faire
            # attendre l'utilisateur. L'interruption est vérifiée très
            # souvent par le moteur (à chaque nœud exploré), donc cette
            # attente reste imperceptible.
            self._worker.requestInterruption()
            self._worker.wait()
        self._set_busy(True)

        def operation_with_persistence() -> None:
            operation()
            if persist_current:
                self._persist_current()

        worker = SolverWorker(operation_with_persistence, self)
        self.solver.cancelled = worker.isInterruptionRequested
        self._worker = worker

        def succeeded() -> None:
            if self._worker is not worker:
                return  # supplanté par une demande plus récente
            self._set_busy(False)
            self.refresh()
            if show_result_alerts:
                self._show_result_alerts()

        def failed(message: str) -> None:
            if self._worker is not worker:
                return
            self._set_busy(False)
            self.refresh()
            QMessageBox.critical(self, "Opération impossible", message)

        def cleanup() -> None:
            worker.deleteLater()
            if self._worker is worker:
                self._worker = None

        worker.succeeded.connect(succeeded)
        worker.failed.connect(failed)
        worker.finished.connect(cleanup)
        worker.start()

    def _remove_observation(self) -> None:
        item = self.history.currentItem()
        if item is None:
            return
        history_index = item.data(Qt.UserRole)
        if history_index is None:
            # Ligne encore "en attente" : le moteur ne l'a pas encore prise
            # en compte, rien à retirer de son historique pour l'instant.
            QMessageBox.information(
                self,
                "Encore en attente",
                "Cet indice n’a pas encore été pris en compte par le "
                "moteur — réessayez dans un instant.",
            )
            return
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
        self.grid_window.close()
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
            item = QListWidgetItem(_format_observation_text(observation))
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

        self._refresh_certainty_label()
        self._refresh_solution_view()
        self._show_certainties()

    def _refresh_certainty_label(self) -> None:
        certain_gems = tuple(getattr(self.solver, "certain_gems", ()))
        if certain_gems:
            labels = ", ".join(
                GEM_LABELS.get(gem.name, gem.name) for gem in certain_gems
            )
            self.certainty_label.setText(
                f"Formes communes aux configurations retenues : {labels}"
            )
        else:
            self.certainty_label.setText(
                "Formes communes aux configurations retenues : aucune"
            )

    def _refresh_solution_view(self) -> None:
        candidates = tuple(getattr(self.solver, "candidates", ()))
        show_choices = len(candidates) == 2
        previous_data = self.solution_view.currentData()
        blocker = QSignalBlocker(self.solution_view)
        self.solution_view.clear()
        self.solution_view.addItem("Certitudes communes", None)
        if show_choices:
            self.solution_view.addItem("Configuration retenue 1", 0)
            self.solution_view.addItem("Configuration retenue 2", 1)
        elif getattr(self.solver, "frequency_available", False):
            qualifier = (
                "exacte"
                if getattr(self.solver, "recommendation_exact", False)
                else "estimée"
            )
            self.solution_view.addItem(
                f"Carte de fréquences ({qualifier})", "frequency"
            )
        restored = self.solution_view.findData(previous_data)
        self.solution_view.setCurrentIndex(restored if restored >= 0 else 0)
        del blocker
        has_options = self.solution_view.count() > 1
        self.solution_view_label.setVisible(has_options)
        self.solution_view.setVisible(has_options)

    def _show_certainties(self, _index: int | None = None) -> None:
        for row in range(8):
            for column in range(10):
                item = self.board.item(row, column)
                item.setText("·")
                item.setBackground(QColor("#f3f3f3"))
        selected_candidate = self.solution_view.currentData()
        if selected_candidate == "frequency":
            self._render_frequency_map()
            return
        self._refresh_certainty_label()
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
                # Le délégué peint la forme (carré ou triangle) d'après ce code.
                self.board.item(row, column).setText(codes[row][column])

    def _render_frequency_map(self) -> None:
        frequency_map = getattr(self.solver, "frequency_map", None)
        if frequency_map is None or frequency_map.sample_size == 0:
            return
        if frequency_map.exhaustive:
            note = "exacte"
        else:
            note = f"estimée sur {frequency_map.sample_size} modèle(s)"
        self.certainty_label.setText(
            f"Carte de fréquences {note} : % de configurations où une pierre "
            "occupe la case (teinte = pierre la plus fréquente)"
        )
        for row_index in range(8):
            row_name = "ABCDEFGH"[row_index]
            for column_index in range(10):
                probability = frequency_map.occupancy[row_index][column_index]
                item = self.board.item(row_index, column_index)
                if probability <= 0.0:
                    continue
                dominant = frequency_map.dominant_content(
                    row_name, column_index + 1
                )
                base = GEM_COLORS.get(
                    dominant.value if dominant is not None else "white",
                    GEM_COLORS["white"],
                )
                item.setText(str(round(probability * 100)))
                item.setBackground(_blend_toward_white(base, probability))

    def _place_add_button(self, cell_mode: bool) -> None:
        # Le bouton "Ajouter" sert aux deux modes mais n'a de place fixe
        # dans aucun des deux widgets qu'ils partagent : on le déplace donc
        # vers celui qui est visible, juste sous son contenu.
        self._points_column.removeWidget(self.add_button)
        self._cell_form.removeWidget(self.add_button)
        if cell_mode:
            self._cell_form.addRow(self.add_button)
        else:
            self._points_column.insertWidget(1, self.add_button)

    def _update_result_controls(self, force_busy: bool = False) -> None:
        cell_mode = self.action_type.currentData() == "cell"
        black_enabled = self.black_checkbox.isChecked()
        self.wave_container.setVisible(not cell_mode)
        self.cell_container.setVisible(cell_mode)
        self._place_add_button(cell_mode)
        self.absorbed.setEnabled(not force_busy and black_enabled and not cell_mode)
        result_enabled = (
            not force_busy and not self.absorbed.isChecked() and not cell_mode
        )
        self.entry_selector.setEnabled(not force_busy and not cell_mode)
        self.exit_selector.setEnabled(result_enabled)
        self.color_selector.setEnabled(result_enabled)
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
