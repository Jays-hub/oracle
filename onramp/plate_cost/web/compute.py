"""Thin glue between the src/ compute chain and the web template layer.

Runs the same chain as src/run.py up to build_grid() and returns a dict of
template-ready data. No business math lives here — presentation plumbing only.
Rule 05: controllers stay thin; business math stays in src/.
"""
import csv
import logging
from pathlib import Path
from typing import TypedDict

from src.bom.loader import load_dishes, load_ingredients, load_recipe_lines
from src.pricing.compute import latest_prices, load_price_observations, plate_cost
from src.report.grid import (
    QUADRANT_ACTIONS,
    build_grid,
    normalize_name,
    round_to_quarter,
)

_log = logging.getLogger(__name__)


# Typed contract for the compute→template boundary (rules 05/07: explicit, typed contracts at every
# layer boundary). These are presentation DTOs, not seam rows — the seam contract lives in schemas/
# (BomRow, SalesExportRow). These never touch data/raw/, so they belong here, not in schemas/.
class DishRow(TypedDict):
    name: str
    menu_price: float
    cost_display: float    # plate cost rounded to the $0.25 grid
    margin_display: float  # menu_price − cost_display (from the ROUNDED cost; reconciles by eye)
    food_cost_pct: float
    food_cost_tier: str
    covers: int
    quadrant: str


class SkippedDish(TypedDict):
    name: str
    reason: str


class GridData(TypedDict):
    rows: list[DishRow]
    total_covers: int
    quadrants: list[str]
    quadrant_actions: dict[str, str]
    skipped: list[SkippedDish]


_PLATE_COST_DIR = Path(__file__).resolve().parents[1]
# W0 reads the on-ramp's *source* inputs (data/sample_*.csv), NOT the seam (data/raw/) and NOT the
# seam read helper src/store.py. The seam deliberately carries only the BOM + sales legs the engine
# needs — it has no menu prices and no ingredient unit prices, so margins cannot be reconstructed
# from it. Reading the seam back is W2's job (once there is captured tenant data); store.py stays the
# sanctioned BOM/sales read path for the engine handoff, not a dependency of this reveal.
_DATA_DIR = _PLATE_COST_DIR / "data"

# round_to_quarter and QUADRANT_ACTIONS are defined once in src/report/grid.py and imported here,
# so the web reveal and the CLI grid round to the same $0.25 grid and label quadrants identically.
# Rule 05: reuse the single definition — a parallel copy would silently drift the reconciliation
# discipline (the very regression audit fix #5 repaired).


def _load_covers(path: Path) -> dict[str, int]:
    covers: dict[str, int] = {}
    with open(path, newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            key = normalize_name(row["dish_name"])
            covers[key] = covers.get(key, 0) + int(row["count"])
    return covers


def build_grid_data() -> GridData:
    """Run the plate-cost compute chain and return template-ready data."""
    ingredients = load_ingredients(_DATA_DIR / "sample_ingredients.csv")
    dishes = load_dishes(_DATA_DIR / "sample_dishes.csv")
    recipe_lines = load_recipe_lines(_DATA_DIR / "sample_recipe_lines.csv")
    observations = load_price_observations(_DATA_DIR / "sample_prices.csv")
    prices = latest_prices(observations)
    covers = _load_covers(_DATA_DIR / "sample_sales.csv")

    dish_costs: dict = {}
    skipped: list[SkippedDish] = []
    for dish_id, dish in dishes.items():
        if not dish.is_active:
            continue
        try:
            cost = plate_cost(dish, recipe_lines, ingredients, prices)
            dish_costs[dish_id] = (dish, cost)
        except ValueError as e:
            # Never drop a dish silently. Name it and surface it (rule 01 missingness report,
            # rule 07 "name the failure — which dish"). Mirrors the CLI skip-collection in
            # src/run.py:136-142 so the web path and the terminal path stay honest in the same way.
            skipped.append({"name": dish.name, "reason": str(e)})
            _log.warning("plate-cost skipped dish %r: %s", dish.name, e)

    rows = build_grid(dish_costs, covers)
    total_covers = sum(r.covers for r in rows)

    enriched: list[DishRow] = []
    for r in rows:
        cost_q = round_to_quarter(r.cost)
        enriched.append({
            "name": r.name,
            "menu_price": r.menu_price,
            "cost_display": cost_q,
            # Margin derives from the rounded cost so Menu − ~Cost = Margin reconciles by eye.
            # Quadrant classification (in build_grid) still uses the precise margin.
            "margin_display": r.menu_price - cost_q,
            "food_cost_pct": r.food_cost_pct,
            "food_cost_tier": r.food_cost_tier,
            "covers": r.covers,
            "quadrant": r.quadrant,
        })

    return {
        "rows": enriched,
        "total_covers": total_covers,
        "quadrants": ["Star", "Plowhorse", "Puzzle", "Dog"],
        "quadrant_actions": QUADRANT_ACTIONS,
        "skipped": skipped,
    }
