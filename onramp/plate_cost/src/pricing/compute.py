import csv
from datetime import date
from pathlib import Path
from uuid import UUID

from ..bom.models import Dish, Ingredient, RecipeLine
from ..bom.units import convert
from .models import PriceObservation


def load_price_observations(path: Path) -> list[PriceObservation]:
    result: list[PriceObservation] = []
    with open(path, newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            result.append(PriceObservation(
                ingredient_id=UUID(row["ingredient_id"]),
                unit_price=float(row["unit_price"]),
                source_invoice=row.get("source_invoice") or None,
                observed_date=date.fromisoformat(row["observed_date"]),
            ))
    return result


def latest_prices(observations: list[PriceObservation]) -> dict[UUID, float]:
    """Most recent unit price per ingredient.

    Tie-break: on equal observed_date, the last observation in input order wins (a same-day
    re-entry supersedes an earlier one) — a defined, deterministic rule rather than the silent
    first-wins a strict ``>`` would give.
    """
    best: dict[UUID, tuple[date, float]] = {}
    for obs in observations:
        if obs.ingredient_id not in best or obs.observed_date >= best[obs.ingredient_id][0]:
            best[obs.ingredient_id] = (obs.observed_date, obs.unit_price)
    return {ing_id: price for ing_id, (_, price) in best.items()}


def plate_cost(
    dish: Dish,
    recipe_lines: list[RecipeLine],
    ingredients: dict[UUID, Ingredient],
    prices: dict[UUID, float],
) -> float:
    dish_lines = [line for line in recipe_lines if line.dish_id == dish.id]
    if not dish_lines:
        raise ValueError(f"No recipe lines found for dish '{dish.name}'")
    total = 0.0
    for line in dish_lines:
        ingredient = ingredients.get(line.ingredient_id)
        if ingredient is None:
            raise ValueError(
                f"Recipe for '{dish.name}' references unknown ingredient_id {line.ingredient_id}"
            )
        price = prices.get(line.ingredient_id)
        if price is None:
            raise ValueError(
                f"No price for '{ingredient.name}' (needed by '{dish.name}')"
            )
        qty_canonical = convert(line.qty, line.recipe_unit, ingredient.canonical_unit)
        total += (qty_canonical / ingredient.yield_factor) * price
    return total
