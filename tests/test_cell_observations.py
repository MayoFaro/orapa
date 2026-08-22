from orapa_assistant.colors import BaseColor
from orapa_assistant.geometry import doubled_polygon
from orapa_assistant.raytracer import Configuration, Gem
from orapa_assistant.solver import (
    CellContent,
    CellObservation,
    Solver,
    configuration_cell_content,
)


def square(color: BaseColor, column: int, row: int, name: str) -> Gem:
    return Gem(
        color,
        doubled_polygon(
            (column - 1, row), (column, row),
            (column, row + 1), (column - 1, row + 1),
        ),
        name,
    )


def test_cell_content_reports_color_or_nothing_without_orientation() -> None:
    configuration = Configuration((square(BaseColor.BLUE, 3, 1, "blue"),))
    assert configuration_cell_content(configuration, "B", 3) == CellContent.BLUE
    assert configuration_cell_content(configuration, "B", 4) == CellContent.NOTHING


def test_cell_observation_filters_configurations() -> None:
    first = Configuration((square(BaseColor.RED, 1, 0, "red"),))
    second = Configuration((square(BaseColor.RED, 2, 0, "red"),))
    solver = Solver((first, second))
    solver.add_observation(CellObservation("A", 1, CellContent.RED))
    assert solver.candidates == (first,)


def test_cell_observation_accepts_string_returned_by_qt_combo_box() -> None:
    observation = CellObservation("a", 1, "red")
    assert observation.row == "A"
    assert observation.content is CellContent.RED


def test_strategy_compares_waves_and_cells() -> None:
    first = Configuration((square(BaseColor.RED, 1, 0, "red"),))
    second = Configuration((square(BaseColor.RED, 2, 0, "red"),))
    scores = Solver((first, second)).rank_next_moves()
    assert any(score.action == "wave" for score in scores)
    assert any(score.action == "cell" for score in scores)
    assert scores[0].worst_case == 1
