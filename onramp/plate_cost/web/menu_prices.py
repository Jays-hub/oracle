"""Thin glue for menu-price capture (W6) — the one missing seam input. Mirrors ``web/your_data.py``'s
role: no business logic here (rule 05), only shaping seam + app-DB reads into template-ready data
and calling ``src/costing``'s pure(ish) write paths.
"""
from __future__ import annotations

from datetime import date
from typing import TypedDict

import pandas as pd
from sqlalchemy.orm import Session as DbSession

from src import store
from src.costing.menu_prices import menu_prices_by_seam_key, upsert_menu_price
from src.costing.tenant_grid import build_food_cost_rows, clear_food_cost, write_food_cost_atomic


class MenuPriceRow(TypedDict):
    dish_id: str
    dish_name: str
    menu_price: float | None


def build_menu_prices_form(db: DbSession, restaurant_id: str) -> list[MenuPriceRow]:
    """Every distinct dish in the captured BOM, with its current menu price if one has been set
    (``None`` if not — the form shows a blank input, never a fabricated $0.00). Empty list if no
    recipe sheet has been captured yet — there is nothing to price."""
    try:
        bom_df = store.read_bom(restaurant_id)
    except FileNotFoundError:
        return []

    existing = menu_prices_by_seam_key(db, restaurant_id)
    dish_names = bom_df.drop_duplicates("dish_id").set_index("dish_id")["dish_name"].to_dict()
    rows: list[MenuPriceRow] = [
        {"dish_id": dish_id, "dish_name": dish_name, "menu_price": existing.get(dish_id)}
        for dish_id, dish_name in dish_names.items()
    ]
    return sorted(rows, key=lambda r: r["dish_name"])


def recompute_and_write_food_cost(bom_df: pd.DataFrame, restaurant_id: str) -> None:
    """Recompute the derived ``food_cost`` seam leg from the current BOM + latest invoice prices
    and write (or, if nothing is costable, clear) it — the one recompute path shared by both
    operator actions that can invalidate ``Co``: a menu-price save
    (``save_menu_prices_and_recompute_food_cost``, below) and a newly confirmed invoice
    (``web/app.py::invoice_confirm_submit``). Previously this only ran on menu-price save, so the
    leg went stale after a price-only invoice upload (W6_review.md MINOR-3); previously an empty
    result was skipped entirely rather than clearing a now-stale prior snapshot (LOW-6).
    """
    try:
        price_df = store.read_price_observations(restaurant_id)
    except FileNotFoundError:
        price_df = pd.DataFrame()

    raw_dir = store.tenant_raw_dir(restaurant_id)
    rows = build_food_cost_rows(bom_df, price_df, as_of=date.today())
    if rows:
        write_food_cost_atomic(rows, raw_dir)
    else:
        clear_food_cost(raw_dir)


def save_menu_prices_and_recompute_food_cost(
    db: DbSession, restaurant_id: str, prices_by_dish_id: dict[str, float]
) -> None:
    """Upsert every submitted menu price, then recompute the derived ``food_cost`` seam leg via
    ``recompute_and_write_food_cost`` — the "one act feeds two products" pattern
    ``data/CONTRACT.md``'s Co-provenance note describes: saving menu prices is one of the operator
    actions W6 ties the engine-facing recompute to, even though the cost math itself never reads
    ``menu_price`` (see ``FoodCostRow``'s docstring).

    ``prices_by_dish_id`` is keyed by the seam's ``dish_id`` (what the form actually submits, not
    an operator-typed name) — the display name written to the ``Dish`` row always comes from the
    current, authoritative BOM read, never round-tripped through the form (rule 07: hostile until
    validated). A submitted ``dish_id`` that no longer matches the current BOM is silently ignored
    rather than guessed at.
    """
    try:
        bom_df = store.read_bom(restaurant_id)
    except FileNotFoundError:
        return  # nothing captured yet — no dish exists to attach a price to

    dish_names = bom_df.drop_duplicates("dish_id").set_index("dish_id")["dish_name"].to_dict()
    for dish_id, price in prices_by_dish_id.items():
        dish_name = dish_names.get(dish_id)
        if dish_name is None:
            continue
        upsert_menu_price(db, restaurant_id, dish_name, price)

    recompute_and_write_food_cost(bom_df, restaurant_id)
