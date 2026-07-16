"""Thin glue for the costed reveal over the tenant's own data (W6) — ``GET /dishes`` (the grid)
and ``GET /dishes/{dish_id}`` (the line-by-line breakdown), the real-data analogue of
``web/compute.py``'s sample-data grid. Rule 05: no business math here, only shaping
``src/costing`` + ``src/store`` reads into template-ready data.
"""
from __future__ import annotations

from typing import TypedDict

import pandas as pd
from sqlalchemy.orm import Session as DbSession

from src import store
from src.costing.menu_prices import menu_prices_by_seam_key
from src.costing.tenant_grid import build_dish_line_items, build_tenant_grid
from src.report.grid import QUADRANT_ACTIONS, food_cost_pct_display, food_cost_tier, round_to_quarter


class DishRow(TypedDict):
    dish_id: str
    name: str
    menu_price: float
    cost_display: float
    margin_display: float
    food_cost_pct: float
    food_cost_tier: str
    covers: int
    quadrant: str


class UnpricedDishRow(TypedDict):
    dish_name: str
    reason: str


class DishesSummary(TypedDict):
    has_data: bool
    rows: list[DishRow]
    unpriced: list[UnpricedDishRow]
    quadrant_actions: dict[str, str]


def _read_optional(read_fn, empty_columns: list[str]) -> pd.DataFrame:
    try:
        return read_fn()
    except FileNotFoundError:
        return pd.DataFrame(columns=empty_columns)


def build_dishes_summary(db: DbSession, restaurant_id: str) -> DishesSummary:
    """Calm "nothing captured yet" state mirrors ``your_data``/``insights`` — a missing BOM is not
    an error, just nothing to show. Sales and price history are each independently optional
    (an operator may have a recipe sheet with no sales/invoices on record yet)."""
    empty: DishesSummary = {
        "has_data": False, "rows": [], "unpriced": [], "quadrant_actions": QUADRANT_ACTIONS,
    }
    try:
        bom_df = store.read_bom(restaurant_id)
    except FileNotFoundError:
        return empty

    sales_df = _read_optional(lambda: store.read_sales(restaurant_id), ["dish_name", "count"])
    price_df = _read_optional(
        lambda: store.read_price_observations(restaurant_id), ["ingredient_id", "unit_price"]
    )
    menu_prices = menu_prices_by_seam_key(db, restaurant_id)

    rows, unpriced = build_tenant_grid(bom_df, sales_df, price_df, menu_prices)

    enriched: list[DishRow] = []
    for r in rows:
        cost_q = round_to_quarter(r.cost)
        food_cost_pct_q = food_cost_pct_display(cost_q, r.menu_price)
        enriched.append({
            "dish_id": str(r.dish_id), "name": r.name, "menu_price": r.menu_price,
            "cost_display": cost_q,
            "margin_display": r.menu_price - cost_q,
            "food_cost_pct": food_cost_pct_q,
            "food_cost_tier": food_cost_tier(food_cost_pct_q),
            "covers": r.covers, "quadrant": r.quadrant,
        })

    return {
        "has_data": True,
        "rows": enriched,
        "unpriced": [{"dish_name": u.dish_name, "reason": u.reason} for u in unpriced],
        "quadrant_actions": QUADRANT_ACTIONS,
    }


class IngredientLine(TypedDict):
    ingredient_name: str
    qty: float
    recipe_unit: str
    as_used_cost: float | None  # None if this ingredient has no price yet, or an unconvertible unit


class DishDetail(TypedDict):
    found: bool
    dish_id: str
    dish_name: str
    menu_price: float | None
    lines: list[IngredientLine]
    cost_display: float | None       # rounded-to-quarter total; None if any line is uncosted
    margin_display: float | None     # menu_price - cost_display; None if either input is missing
    food_cost_pct: float | None
    food_cost_tier: str | None
    any_missing: bool


_NOT_FOUND: DishDetail = {
    "found": False, "dish_id": "", "dish_name": "", "menu_price": None, "lines": [],
    "cost_display": None, "margin_display": None, "food_cost_pct": None, "food_cost_tier": None,
    "any_missing": False,
}


def build_dish_detail(db: DbSession, restaurant_id: str, dish_id: str) -> DishDetail:
    """Line-by-line ingredient -> qty -> as-used cost for one dish (website_vision.md §3B "Dish
    detail"), so a chef can audit every number rather than trust an opaque total. Delegates to
    ``src.costing.tenant_grid.build_dish_line_items`` (rule 05: no business math in the web
    layer) — per-line costs are shown at real precision (a provenance/audit surface, not a
    headline dollar claim — rule 06's "provenance is reachable" mandate), and ``cost_display`` is
    that SAME shared function's rounded-once aggregate, so this page's total always equals the
    grid's ~Cost for the same dish (W6_review.md BLOCKER-1: two independently-rounded
    implementations could — and did — disagree).
    """
    try:
        bom_df = store.read_bom(restaurant_id)
    except FileNotFoundError:
        return _NOT_FOUND

    dish_rows = bom_df[bom_df["dish_id"] == dish_id]
    if dish_rows.empty:
        return _NOT_FOUND
    dish_name = dish_rows.iloc[0]["dish_name"]

    price_df = _read_optional(
        lambda: store.read_price_observations(restaurant_id), ["ingredient_id", "unit_price"]
    )
    line_items, cost_display = build_dish_line_items(bom_df, price_df, dish_id)
    any_missing = cost_display is None
    lines: list[IngredientLine] = [
        {
            "ingredient_name": li.ingredient_name, "qty": li.qty,
            "recipe_unit": li.recipe_unit, "as_used_cost": li.as_used_cost,
        }
        for li in line_items
    ]

    menu_prices = menu_prices_by_seam_key(db, restaurant_id)
    menu_price = menu_prices.get(dish_id)
    margin_display = (
        None if cost_display is None or menu_price is None else menu_price - cost_display
    )
    food_cost_pct = (
        None if cost_display is None or not menu_price
        else food_cost_pct_display(cost_display, menu_price)
    )

    return {
        "found": True, "dish_id": dish_id, "dish_name": dish_name, "menu_price": menu_price,
        "lines": lines, "cost_display": cost_display, "margin_display": margin_display,
        "food_cost_pct": food_cost_pct,
        "food_cost_tier": None if food_cost_pct is None else food_cost_tier(food_cost_pct),
        "any_missing": any_missing,
    }
