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


def test_observation_panel_first_click_sets_entry_second_sets_exit() -> None:
    _app()
    panel = ObservationChipPanel()
    # Un seul jeu de chips : le premier clic fixe l'entrée...
    panel.points._buttons["8"].click()
    assert panel.entry.value() == "8"
    assert panel.exit.value() is None
    # ...le second fixe la sortie.
    panel.points._buttons["12"].click()
    assert panel.entry.value() == "8"
    assert panel.exit.value() == "12"
    # Un clic de plus recommence une nouvelle saisie.
    panel.points._buttons["C"].click()
    assert panel.entry.value() == "C"
    assert panel.exit.value() is None


def test_observation_panel_set_value_does_not_touch_click_sequence() -> None:
    _app()
    panel = ObservationChipPanel()
    panel.entry.set_value("8")
    assert panel.exit.value() is None
    panel.exit.set_value("12")
    assert panel.entry.value() == "8"
    assert panel.exit.value() == "12"
