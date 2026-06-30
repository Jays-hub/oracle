"""Regression test for task #6: a recipe line referencing an unknown ingredient_id must raise a
friendly ValueError (which run.py catches and skips), not a bare KeyError that crashes the run."""
from uuid import uuid4

import pytest

from src.bom.models import Dish, Ingredient, RecipeLine
from src.pricing.compute import plate_cost


def test_dangling_ingredient_id_raises_valueerror():
    dish = Dish(name="Ghost Dish", menu_price=20.0)
    missing_id = uuid4()
    recipe_lines = [RecipeLine(dish_id=dish.id, ingredient_id=missing_id, qty=1.0, recipe_unit="oz")]
    with pytest.raises(ValueError, match="unknown ingredient_id"):
        plate_cost(dish, recipe_lines, ingredients={}, prices={})


def test_missing_price_still_raises_valueerror():
    dish = Dish(name="Priceless", menu_price=20.0)
    ing = Ingredient(name="beef", canonical_unit="oz", yield_factor=0.7)
    recipe_lines = [RecipeLine(dish_id=dish.id, ingredient_id=ing.id, qty=1.0, recipe_unit="oz")]
    with pytest.raises(ValueError, match="No price"):
        plate_cost(dish, recipe_lines, ingredients={ing.id: ing}, prices={})
