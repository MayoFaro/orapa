import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication

from orapa_assistant.border import ALL_BORDER_POINTS
from orapa_assistant.colors import RayColor
from orapa_assistant.gui.chips import (
    BorderChipSelector,
    ColorChipSelector,
    ObservationChipPanel,
)


def _app() -> QApplication:
    return QApplication.instance() or QApplication([])


def test_border_selector_covers_every_border_point() -> None:
    _app()
    selector = BorderChipSelector("Entrée")
    assert set(selector.keys()) == set(ALL_BORDER_POINTS)
    assert selector.value() is None


def test_border_selector_is_exclusive_and_clearable() -> None:
    _app()
    selector = BorderChipSelector("Entrée")
    selector.set_value("8")
    assert selector.value() == "8"
    selector.set_value("C")
    assert selector.value() == "C"
    selector.clear()
    assert selector.value() is None
    with_unknown = "ZZ"
    try:
        selector.set_value(with_unknown)
    except KeyError:
        pass
    else:  # pragma: no cover - garde-fou
        raise AssertionError("un chip inconnu doit lever KeyError")


def test_color_selector_returns_enum() -> None:
    _app()
    selector = ColorChipSelector()
    assert selector.value() is None
    selector.set_value(RayColor.LIGHT_YELLOW)
    assert selector.value() is RayColor.LIGHT_YELLOW
    assert selector.label_for(RayColor.LIGHT_YELLOW) == "Jaune citron"


def test_observation_panel_mirrors_exit_on_user_entry_click() -> None:
    _app()
    panel = ObservationChipPanel()
    # Un clic utilisateur sur un chip d'entrée : la sortie suit.
    panel.entry._buttons["8"].click()
    assert panel.entry.value() == "8"
    assert panel.exit.value() == "8"
    # L'utilisateur corrige la sortie sans toucher l'entrée.
    panel.exit._buttons["12"].click()
    assert panel.entry.value() == "8"
    assert panel.exit.value() == "12"
    # Nouvelle entrée : la sortie se recale.
    panel.entry._buttons["C"].click()
    assert panel.exit.value() == "C"


def test_observation_panel_set_value_does_not_mirror() -> None:
    _app()
    panel = ObservationChipPanel()
    panel.entry.set_value("8")
    # set_value n'émet pas changed : la sortie reste vide.
    assert panel.exit.value() is None
