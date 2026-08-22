from orapa_assistant.cell_display import configuration_cell_codes
from orapa_assistant.examples import REAL_GAME_SOLUTION
from orapa_assistant.geometry import doubled_polygon
from orapa_assistant.raytracer import Configuration, Gem


def test_real_solution_distinguishes_full_and_half_cells() -> None:
    cells = configuration_cell_codes(REAL_GAME_SOLUTION)
    assert cells == [
        ["·", "·", "·", "·", "Bbg", "·", "·", "·", "·", "·"],
        ["·", "·", "Wbd", "Wbg", "B", "Bbg", "·", "Rbg", "·", "·"],
        ["·", "·", "Whd", "Whg", "B", "Bhg", "·", "R", "·", "·"],
        ["·", "·", "·", "·", "Bhg", "·", "·", "Rhd", "·", "·"],
        ["·", "·", "·", "·", "·", "·", "·", "Ybg", "·", "·"],
        ["·", "Whd", "W", "W", "Whg", "·", "·", "Y", "Ybg", "·"],
        ["·", "·", "Whd", "Whg", "·", "·", "·", "·", "·", "·"],
        ["·", "·", "·", "·", "·", "·", "·", "·", "·", "·"],
    ]


def test_extension_cell_codes_use_diamond_and_black_symbols() -> None:
    configuration = Configuration(
        (
            Gem(None, doubled_polygon((1, 0), (1, 2), (0, 1)), "diamond"),
            Gem(
                None,
                doubled_polygon((2, 0), (4, 0), (4, 1), (2, 1)),
                "black_body",
                absorbs=True,
            ),
        )
    )
    cells = configuration_cell_codes(configuration)
    assert cells[0][:4] == ["Dbd", "·", "N", "N"]
    assert cells[1][0] == "Dhd"
