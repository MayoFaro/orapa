"""Sélecteurs à « chips » cliquables : plus rapides que les menus déroulants.

Chaque sélecteur est un groupe de boutons *checkable* mutuellement exclusifs.
La valeur courante est celle du bouton coché, ou ``None`` si aucun ne l'est.
Le signal ``changed`` n'est émis que sur une action de l'utilisateur, jamais
par :meth:`set_value`, ce qui permet de piloter la sortie depuis l'entrée sans
boucle de rappel.
"""

from __future__ import annotations

from collections.abc import Iterable, Sequence

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QButtonGroup,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from ..border import BOTTOM_POINTS, LEFT_POINTS, RIGHT_POINTS, TOP_POINTS
from ..colors import RayColor


class _ChipGroup(QWidget):
    """Base commune : boutons exclusifs indexés par une clé de chaîne."""

    changed = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._group = QButtonGroup(self)
        self._group.setExclusive(True)
        self._buttons: dict[str, QPushButton] = {}
        self._group.buttonClicked.connect(lambda _button: self.changed.emit())

    def _add_chip(self, key: str, label: str) -> QPushButton:
        button = QPushButton(label)
        button.setCheckable(True)
        button.setFocusPolicy(Qt.NoFocus)
        self._group.addButton(button)
        self._buttons[key] = button
        return button

    def keys(self) -> tuple[str, ...]:
        return tuple(self._buttons)

    def value(self) -> str | None:
        for key, button in self._buttons.items():
            if button.isChecked():
                return key
        return None

    def set_value(self, key: str | None) -> None:
        if key is not None and key not in self._buttons:
            raise KeyError(f"chip inconnu : {key!r}")
        # Décocher dans un groupe exclusif exige de lever l'exclusivité le temps
        # de la mise à jour.
        self._group.setExclusive(False)
        for candidate, button in self._buttons.items():
            button.setChecked(candidate == key)
        self._group.setExclusive(True)

    def clear(self) -> None:
        self.set_value(None)

    def setEnabled(self, enabled: bool) -> None:  # noqa: N802 (API Qt)
        super().setEnabled(enabled)


def _label(text: str) -> QLabel:
    label = QLabel(text)
    label.setStyleSheet("color: palette(mid); font-size: 10px;")
    return label


class BorderChipSelector(_ChipGroup):
    """Sélection d'un des 36 points de bord (chiffres 1‑18, lettres A‑R)."""

    def __init__(self, title: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(2)
        outer.addWidget(_label(title))
        outer.addWidget(_label("Chiffres"))
        outer.addLayout(self._grid((TOP_POINTS, RIGHT_POINTS)))
        outer.addWidget(_label("Lettres"))
        outer.addLayout(self._grid((LEFT_POINTS, BOTTOM_POINTS)))

    def _grid(self, rows: Iterable[Sequence[str]]) -> QGridLayout:
        grid = QGridLayout()
        grid.setSpacing(2)
        for row_index, points in enumerate(rows):
            for column_index, point in enumerate(points):
                button = self._add_chip(point, point)
                button.setFixedSize(28, 24)
                grid.addWidget(button, row_index, column_index)
        return grid


RAYCOLOR_LABELS: dict[RayColor, str] = {
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

RAYCOLOR_HEX: dict[RayColor, str] = {
    RayColor.TRANSPARENT: "#ededed",
    RayColor.WHITE: "#ffffff",
    RayColor.RED: "#ef2929",
    RayColor.YELLOW: "#f6c431",
    RayColor.BLUE: "#1775bd",
    RayColor.PINK: "#f2a6c0",
    RayColor.LIGHT_YELLOW: "#e9ea9c",
    RayColor.LIGHT_BLUE: "#a9d3ec",
    RayColor.ORANGE: "#f57900",
    RayColor.GREEN: "#4e9a06",
    RayColor.VIOLET: "#75507b",
    RayColor.LIGHT_ORANGE: "#f7c69a",
    RayColor.LIGHT_GREEN: "#b7e0a4",
    RayColor.LIGHT_VIOLET: "#caa9d2",
    RayColor.BLACK: "#202020",
    RayColor.GRAY: "#8a8a8a",
}


def _readable_text(hex_color: str) -> str:
    red = int(hex_color[1:3], 16)
    green = int(hex_color[3:5], 16)
    blue = int(hex_color[5:7], 16)
    luminance = (0.299 * red + 0.587 * green + 0.114 * blue) / 255
    return "#000000" if luminance > 0.55 else "#ffffff"


class ColorChipSelector(_ChipGroup):
    """Sélection d'une des 16 couleurs de rayon, en deux colonnes teintées."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        grid = QGridLayout(self)
        grid.setContentsMargins(0, 0, 0, 0)
        grid.setSpacing(2)
        for index, color in enumerate(RayColor):
            hex_color = RAYCOLOR_HEX[color]
            text_color = _readable_text(hex_color)
            button = self._add_chip(color.value, RAYCOLOR_LABELS[color])
            button.setStyleSheet(
                "QPushButton {"
                f" background: {hex_color}; color: {text_color};"
                " border: 1px solid palette(mid); border-radius: 3px;"
                " padding: 3px 6px; }"
                "QPushButton:checked {"
                " border: 2px solid palette(highlight); font-weight: bold; }"
            )
            button.setMinimumWidth(104)
            button.setFixedHeight(24)
            grid.addWidget(button, index % 8, index // 8)

    def value(self) -> RayColor | None:  # type: ignore[override]
        key = super().value()
        return RayColor(key) if key is not None else None

    def set_value(self, color: RayColor | None) -> None:  # type: ignore[override]
        super().set_value(color.value if color is not None else None)

    def label_for(self, color: RayColor) -> str:
        return RAYCOLOR_LABELS[color]


class ObservationChipPanel(QWidget):
    """Regroupe entrée, sortie et couleur ; câble l'auto‑report de la sortie."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.entry = BorderChipSelector("Entrée")
        self.exit = BorderChipSelector("Sortie")
        self.color = ColorChipSelector()
        self.entry.changed.connect(self._mirror_exit)

        color_column = QVBoxLayout()
        color_column.setSpacing(2)
        color_column.addWidget(_label("Couleur"))
        color_column.addWidget(self.color)
        color_column.addStretch()

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(14)
        layout.addWidget(self.entry, 0, Qt.AlignTop)
        layout.addWidget(self.exit, 0, Qt.AlignTop)
        layout.addLayout(color_column)
        layout.addStretch(1)

    def _mirror_exit(self) -> None:
        # Par défaut la sortie suit l'entrée ; l'utilisateur peut ensuite
        # cliquer un autre chip de sortie pour la corriger.
        self.exit.set_value(self.entry.value())

    def clear(self) -> None:
        self.entry.clear()
        self.exit.clear()
        self.color.clear()


__all__ = [
    "BorderChipSelector",
    "ColorChipSelector",
    "ObservationChipPanel",
    "RAYCOLOR_HEX",
    "RAYCOLOR_LABELS",
]
