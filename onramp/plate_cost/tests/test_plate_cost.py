"""Unit tests for the plate-cost compute -- the dollar-bearing math.

Per Gate-3 (c): test the money math, not cosmetic formatting.
"""
from datetime import date
from pathlib import Path
from uuid import UUID

import pytest

from src.bom.loader import load_dishes, load_ingredients, load_recipe_lines
from src.pricing.compute import latest_prices, load_price_observations, plate_cost
from src.pricing.models import PriceObservation

_DATA = Path(__file__).resolve().parents[1] / "data"


def _load():
    ingredients = load_ingredients(_DATA / "sample_ingredients.csv")
    dishes = load_dishes(_DATA / "sample_dishes.csv")
    recipe_lines = load_recipe_lines(_DATA / "sample_recipe_lines.csv")
    prices = latest_prices(load_price_observations(_DATA / "sample_prices.csv"))
    return ingredients, dishes, recipe_lines, prices


def _dish_by_name(dishes, name):
    return next(d for d in dishes.values() if d.name == name)


def test_short_rib_plate_cost():
    ingredients, dishes, recipe_lines, prices = _load()
    dish = _dish_by_name(dishes, "Braised Short Rib")
    cost = plate_cost(dish, recipe_lines, ingredients, prices)
    # 120/7*0.469 (=8.04) + 3*0.1875 + 8*0.078 + 1*0.25 + 20/9*0.09 (=0.2) = 9.6765
    assert cost == pytest.approx(9.6765, abs=1e-4)


def test_every_active_dish_costs_below_menu_price():
    ingredients, dishes, recipe_lines, prices = _load()
    for dish in dishes.values():
        if dish.is_active:
            cost = plate_cost(dish, recipe_lines, ingredients, prices)
            assert 0 < cost < dish.menu_price, f"{dish.name}: cost {cost} vs menu {dish.menu_price}"


def test_latest_prices_picks_most_recent_observation():
    iid = UUID("00000000-0000-0000-0000-000000000001")
    observations = [
        PriceObservation(ingredient_id=iid, unit_price=1.0, observed_date=date(2026, 1, 1)),
        PriceObservation(ingredient_id=iid, unit_price=2.0, observed_date=date(2026, 6, 1)),
    ]
    assert latest_prices(observations)[iid] == 2.0


def test_latest_prices_tiebreak_last_same_date_wins():
    # On an equal observed_date, the last observation in input order supersedes (defined tie-break).
    iid = UUID("00000000-0000-0000-0000-000000000001")
    observations = [
        PriceObservation(ingredient_id=iid, unit_price=1.0, observed_date=date(2026, 6, 1)),
        PriceObservation(ingredient_id=iid, unit_price=3.0, observed_date=date(2026, 6, 1)),
    ]
    assert latest_prices(observations)[iid] == 3.0
