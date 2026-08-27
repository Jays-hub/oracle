import csv
from pathlib import Path
from uuid import UUID

from .models import Dish, Ingredient, RecipeLine


def load_ingredients(path: Path) -> dict[UUID, Ingredient]:
    result: dict[UUID, Ingredient] = {}
    with open(path, newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            ing = Ingredient(
                id=UUID(row["id"]),
                name=row["name"],
                canonical_unit=row["canonical_unit"],
                yield_factor=float(row["yield_factor"]),
                notes=row.get("notes") or None,
            )
            result[ing.id] = ing
    return result


def load_dishes(path: Path) -> dict[UUID, Dish]:
    result: dict[UUID, Dish] = {}
    with open(path, newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            dish = Dish(
                id=UUID(row["id"]),
                name=row["name"],
                menu_price=float(row["menu_price"]),
                service_period=row.get("service_period") or None,
                is_active=row.get("is_active", "true").strip().lower() != "false",
            )
            result[dish.id] = dish
    return result


def load_recipe_lines(path: Path) -> list[RecipeLine]:
    result: list[RecipeLine] = []
    with open(path, newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            result.append(RecipeLine(
                dish_id=UUID(row["dish_id"]),
                ingredient_id=UUID(row["ingredient_id"]),
                qty=float(row["qty"]),
                recipe_unit=row["recipe_unit"],
            ))
    return result
