"""Regression tests for the covers-join fix (task #4): match on a normalized name so a stray
space / case difference can't silently score a dish 0 covers."""
from src.bom.models import Dish
from src.report.grid import build_grid, normalize_name


def test_normalize_matches_messy_variants():
    assert normalize_name("  Braised Short Rib ") == normalize_name("braised short rib")


def test_build_grid_attributes_covers_despite_messy_key():
    dish = Dish(name="Braised Short Rib", menu_price=42.0)
    dish_costs = {dish.id: (dish, 9.6765)}
    rows = build_grid(dish_costs, {"  braised SHORT rib ": 85})  # messy sales key
    assert rows[0].covers == 85


def test_build_grid_scores_zero_when_truly_unmatched():
    dish = Dish(name="Tuna Tartare", menu_price=19.0)
    dish_costs = {dish.id: (dish, 6.0)}
    rows = build_grid(dish_costs, {"something else entirely": 10})
    assert rows[0].covers == 0
