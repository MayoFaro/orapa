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


class _EntryExitValue:
    """Vue déléguée sur l'entrée ou la sortie d'un :class:`EntryExitChipSelector`.

    Garde la même API que l'ancien sélecteur dédié (``value``, ``set_value``,
    ``setEnabled``…) alors que les deux ne partagent plus, visuellement,
    qu'un seul jeu de chips.
    """

    def __init__(self, owner: "EntryExitChipSelector", which: str) -> None:
        self._owner = owner
        self._which = which

    def value(self) -> str | None:
        return self._owner._value(self._which)

    def set_value(self, point: str | None) -> None:
        self._owner._set_value(self._which, point)

    def clear(self) -> None:
        self.set_value(None)

    def setEnabled(self, enabled: bool) -> None:  # noqa: N802 (API Qt)
        self._owner._set_enabled(self._which, enabled)

    def isEnabled(self) -> bool:  # noqa: N802 (API Qt)
        return self._owner._enabled(self._which)


class EntryExitChipSelector(QWidget):
    """Un seul jeu de chips point (chiffres + lettres) pour entrée ET sortie.

    Le premier clic fixe l'entrée, le second la sortie ; un clic
    supplémentaire recommence une nouvelle saisie. Un libellé au-dessus des
    chips confirme ce qui vient d'être choisi — sans lui, rien ne montre
    qu'un clic a bien été pris en compte avant que la sortie ne soit fixée
    à son tour.
    """

    changed = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._entry: str | None = None
        self._exit: str | None = None
        self._entry_enabled = True
        self._exit_enabled = True
        self._buttons: dict[str, QPushButton] = {}

        self._feedback = _label("Point : —")
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(2)
        outer.addWidget(self._feedback)
        outer.addWidget(_label("Chiffres"))
        outer.addLayout(self._grid((TOP_POINTS, RIGHT_POINTS)))
        outer.addWidget(_label("Lettres"))
        outer.addLayout(self._grid((LEFT_POINTS, BOTTOM_POINTS)))

        self.entry = _EntryExitValue(self, "entry")
        self.exit = _EntryExitValue(self, "exit")

    def _grid(self, rows: Iterable[Sequence[str]]) -> QGridLayout:
        grid = QGridLayout()
        grid.setSpacing(2)
        for row_index, points in enumerate(rows):
            for column_index, point in enumerate(points):
                button = QPushButton(point)
                button.setFixedSize(28, 24)
                button.setFocusPolicy(Qt.NoFocus)
                button.clicked.connect(
                    lambda _checked=False, point=point: self._handle_click(point)
                )
                self._buttons[point] = button
                grid.addWidget(button, row_index, column_index)
        return grid

    def _handle_click(self, point: str) -> None:
        if self._entry is None or not self._exit_enabled:
            # Rien n'est encore choisi, ou la sortie est désactivée (onde
            # absorbée) : chaque clic redéfinit l'entrée.
            if not self._entry_enabled:
                return
            self._entry = point
            self._exit = None
        elif self._exit is None:
            self._exit = point
        else:
            # Entrée et sortie déjà fixées : on recommence une saisie.
            self._entry = point
            self._exit = None
        self._refresh()
        self.changed.emit()

    def _value(self, which: str) -> str | None:
        return self._entry if which == "entry" else self._exit

    def _set_value(self, which: str, point: str | None) -> None:
        if point is not None and point not in self._buttons:
            raise KeyError(f"chip inconnu : {point!r}")
        if which == "entry":
            self._entry = point
        else:
            self._exit = point
        self._refresh()

    def _enabled(self, which: str) -> bool:
        return self._entry_enabled if which == "entry" else self._exit_enabled

    def _set_enabled(self, which: str, enabled: bool) -> None:
        if which == "entry":
            self._entry_enabled = enabled
        else:
            self._exit_enabled = enabled
        for button in self._buttons.values():
            button.setEnabled(self._entry_enabled)

    def _refresh(self) -> None:
        for point, button in self._buttons.items():
            if point == self._entry and point == self._exit:
                style = (
                    "background-color:#f6c431; font-weight:bold;"
                    " border:2px solid palette(highlight); border-radius:3px;"
                )
            elif point == self._entry:
                style = (
                    "background-color:#a9d3ec; font-weight:bold;"
                    " border:2px solid palette(highlight); border-radius:3px;"
                )
            elif point == self._exit:
                style = (
                    "background-color:#f2a6c0; font-weight:bold;"
                    " border:2px solid palette(highlight); border-radius:3px;"
                )
            else:
                style = ""
            button.setStyleSheet(style)
        if self._entry is None:
            text = "Point : —"
        elif self._exit is None:
            text = f"Entrée : {self._entry}"
        else:
            text = f"Entrée : {self._entry}  →  Sortie : {self._exit}"
        self._feedback.setText(text)

    def clear(self) -> None:
        self._entry = None
        self._exit = None
        self._refresh()


class ObservationChipPanel(QWidget):
    """Regroupe entrée, sortie et couleur pour composer une observation.

    Entrée et sortie partagent un seul jeu de chips point (voir
    :class:`EntryExitChipSelector`). La couleur (``color``) reste un
    sélecteur indépendant, non ajouté à la disposition de ce panneau —
    l'appelant le place où il veut.
    """

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.points = EntryExitChipSelector()
        self.entry = self.points.entry
        self.exit = self.points.exit
        self.color = ColorChipSelector()

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(14)
        layout.addWidget(self.points, 0, Qt.AlignTop)
        layout.addStretch(1)

    def clear(self) -> None:
        self.points.clear()
        self.color.clear()


__all__ = [
    "BorderChipSelector",
    "ColorChipSelector",
    "EntryExitChipSelector",
    "ObservationChipPanel",
    "RAYCOLOR_HEX",
    "RAYCOLOR_LABELS",
]
