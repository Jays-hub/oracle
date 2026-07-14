"""The costed reveal over the operator's own captured data (W6) — the real-tenant analogue of
``web/compute.py``'s sample-data grid, now that a menu price is capturable
(``src/costing/menu_prices.py``). No FastAPI import (rule 05): unit-testable with bare
DataFrames/dicts, independent of the web layer.

Reuses ``src.insights.opportunities.dish_ingredient_cost`` for the per-dish ingredient-cost sum —
same missing-price / non-convertible-unit degrade-to-"not costed" behavior W3 already hardened
(W3_review.md MAJOR-1) — rather than forking a second copy (rule 05), and
``src.report.grid.build_grid`` for the popularity x margin classification, so quadrant/tiering
math is identical whether the dishes are sample data or a real tenant's.
"""
from __future__ import annotations

import os
from dataclasses import dataclass
from datetime import date
from pathlib import Path

import pandas as pd

from ..bom.units import convert
from ..capture.seam_upload import _stage_parquet
from ..insights.opportunities import dish_ingredient_cost
from ..pricing.trends import latest_price_per_ingredient
from ..report.grid import DishResult, build_grid, round_to_quarter

# schemas/ bootstrap (sys.path insert) already ran as a side effect of the seam_upload import
# above (sys.path is process-global) — matches src/capture/invoice_upload.py's identical pattern.
from schemas import FoodCostRow  # noqa: E402  (after the seam_upload import, same reason)


@dataclass
class _PricedDish:
    """Duck-typed stand-in for ``src/bom/models.py::Dish`` — ``build_grid`` only reads
    ``.name``/``.menu_price``. The sample-data CLI model is UUID-keyed and never touches the
    seam; a real tenant dish is string-keyed seam data plus an app-DB menu price, so a second
    lightweight shape here is more honest than reusing a pydantic model built for a different id
    universe."""

    name: str
    menu_price: float


@dataclass
class UnpricedDish:
    """A captured dish (has BOM lines) that couldn't make it onto the grid — no menu price set
    yet, or its ingredients can't be fully costed. Named and surfaced, never dropped silently
    (rule 07)."""

    dish_name: str
    reason: str


@dataclass
class DishLineItem:
    """One ingredient's as-used cost within a dish's breakdown — real cents, never rounded to the
    $0.25 grid (that rounding happens ONCE, on the aggregate, in ``build_dish_line_items``'s
    return value, never per line — W6_review.md BLOCKER-1: summing already-rounded lines is not
    the same number as rounding the sum, and silently inflates a multi-ingredient dish)."""

    ingredient_name: str
    qty: float
    recipe_unit: str
    as_used_cost: float | None  # real cents; None if uncosted (no price yet, or unconvertible unit)


def _dish_names_by_id(bom_df: pd.DataFrame) -> dict[str, str]:
    return bom_df.drop_duplicates("dish_id").set_index("dish_id")["dish_name"].to_dict()


def _latest_prices(price_obs_df: pd.DataFrame) -> dict[str, float]:
    latest = latest_price_per_ingredient(price_obs_df)
    return dict(zip(latest["ingredient_id"], latest["unit_price"]))


def build_tenant_grid(
    bom_df: pd.DataFrame,
    sales_df: pd.DataFrame,
    price_obs_df: pd.DataFrame,
    menu_prices: dict[str, float],
) -> tuple[list[DishResult], list[UnpricedDish]]:
    """``menu_prices`` is keyed by the seam's ``dish_id``
    (``src.costing.menu_prices.menu_prices_by_seam_key``'s output shape). Returns the same
    ``DishResult`` rows the sample-data grid produces (sorted by quadrant then margin) plus every
    captured dish that couldn't be priced, with why.
    """
    if bom_df.empty:
        return [], []

    prices = _latest_prices(price_obs_df)
    costs = dish_ingredient_cost(bom_df, prices)
    dish_names = _dish_names_by_id(bom_df)
    covers = (
        sales_df.groupby("dish_name")["count"].sum().to_dict() if not sales_df.empty else {}
    )

    dish_costs: dict[str, tuple[_PricedDish, float]] = {}
    unpriced: list[UnpricedDish] = []
    for dish_id, dish_name in dish_names.items():
        if dish_id not in costs:
            unpriced.append(UnpricedDish(
                dish_name=dish_name,
                reason="Ingredient cost not yet available (a price or a convertible unit is missing).",
            ))
            continue
        menu_price = menu_prices.get(dish_id)
        if menu_price is None:
            unpriced.append(UnpricedDish(dish_name=dish_name, reason="No menu price set yet."))
            continue
        dish_costs[dish_id] = (_PricedDish(name=dish_name, menu_price=menu_price), costs[dish_id])

    rows = build_grid(dish_costs, covers)
    return rows, sorted(unpriced, key=lambda u: u.dish_name)


def build_dish_line_items(
    bom_df: pd.DataFrame, price_obs_df: pd.DataFrame, dish_id: str
) -> tuple[list[DishLineItem], float | None]:
    """Ingredient -> qty -> as-used cost for one dish (website_vision.md §3B "Dish detail"), plus
    the SAME rounded total the grid shows for that dish. Uses the identical per-line formula
    ``dish_ingredient_cost`` sums (``qty_canonical / yield_factor * price``) so a dish's detail
    total is structurally guaranteed to equal its grid ~Cost: round ONCE, on the raw aggregate,
    here — never round-then-sum (W6_review.md BLOCKER-1). Returns ``(lines, cost_display)``;
    ``cost_display`` is ``None`` if any line is uncosted, matching ``dish_ingredient_cost``'s
    all-or-nothing degrade.
    """
    dish_rows = bom_df[bom_df["dish_id"] == dish_id]
    prices = _latest_prices(price_obs_df)

    lines: list[DishLineItem] = []
    raw_total = 0.0
    any_missing = False
    for _, row in dish_rows.iterrows():
        price = prices.get(row["ingredient_id"])
        as_used_cost: float | None = None
        if price is not None:
            try:
                qty_canonical = convert(row["qty"], row["recipe_unit"], row["canonical_unit"])
                as_used_cost = (qty_canonical / row["yield_factor"]) * price
                raw_total += as_used_cost
            except ValueError:
                any_missing = True
        else:
            any_missing = True
        lines.append(DishLineItem(
            ingredient_name=row["ingredient_name"], qty=row["qty"],
            recipe_unit=row["recipe_unit"], as_used_cost=as_used_cost,
        ))

    cost_display = None if any_missing else round_to_quarter(raw_total)
    return lines, cost_display


def build_food_cost_rows(
    bom_df: pd.DataFrame, price_obs_df: pd.DataFrame, as_of: date
) -> list[FoodCostRow]:
    """Every dish the BOM says is fully costable (a real price for every ingredient, all
    convertible units) gets a ``FoodCostRow`` — independent of whether a menu price is set: ``Co``
    is the ingredient cost alone, so this seam leg does not wait on menu-price capture (see
    ``FoodCostRow``'s docstring)."""
    if bom_df.empty:
        return []
    prices = _latest_prices(price_obs_df)
    costs = dish_ingredient_cost(bom_df, prices)
    dish_names = _dish_names_by_id(bom_df)
    return [
        FoodCostRow(dish_id=dish_id, dish_name=dish_names[dish_id], food_cost=cost, computed_at=as_of)
        for dish_id, cost in costs.items()
    ]


def write_food_cost_atomic(rows: list[FoodCostRow], raw_dir: Path) -> None:
    """Full-replace write of the derived ``food_cost`` seam leg — a fresh, always-current
    snapshot recomputed from the latest BOM + price data (mirrors ``bom.parquet``/
    ``sales_export.parquet``'s "current snapshot only" semantics in
    ``src/capture/seam_upload.py::write_seam_atomic``, not ``price_observations.parquet``'s
    accumulating-history model: ``Co`` is a current fact about a dish's cost, not a history to
    retain). Reuses ``seam_upload._stage_parquet`` for the write-to-temp-then-rename step (rule
    05 reuse — the same helper ``src/capture/invoice_upload.py`` already imports across modules).
    """
    if not rows:
        raise ValueError("write_food_cost_atomic: no food-cost rows to write")
    df = pd.DataFrame([r.model_dump() for r in rows])
    dest = raw_dir / "food_cost.parquet"
    tmp_path = _stage_parquet(df, dest)
    os.replace(tmp_path, dest)


def clear_food_cost(raw_dir: Path) -> None:
    """Remove the derived ``food_cost`` seam leg when no dish is currently costable, so a stale
    snapshot from a prior BOM/price state never lingers once nothing costs (mirrors
    ``write_food_cost_atomic``'s "current snapshot only" contract for the empty case —
    W6_review.md LOW-6). A no-op if the file was never written."""
    (raw_dir / "food_cost.parquet").unlink(missing_ok=True)
