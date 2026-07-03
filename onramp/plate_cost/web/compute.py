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
    covers_join_report,
    food_cost_tier,
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


class CoversWarnings(TypedDict):
    unmatched_dishes: list[str]   # menu dishes that matched no sales row (show 0 covers)
    orphaned_sales: list[str]     # sales rows that matched no menu item (excluded from every card)


class GridData(TypedDict):
    rows: list[DishRow]
    total_covers: int
    quadrants: list[str]
    quadrant_actions: dict[str, str]
    skipped: list[SkippedDish]
    covers_warnings: CoversWarnings


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


def _load_covers(path: Path) -> dict[str, tuple[str, int]]:
    """Covers per dish, keyed by a normalized name and retaining a display name for reporting.

    Mirrors `src/run.py`'s `_load_covers` so the web and CLI paths join sales the same way (rule 05:
    reuse, don't fork, the join logic) — returns ``{normalized_name: (display_name, total_count)}``.
    """
    covers: dict[str, tuple[str, int]] = {}
    with open(path, newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            raw = row["dish_name"]
            key = normalize_name(raw)
            display, running = covers.get(key, (raw.strip(), 0))
            covers[key] = (display, running + int(row["count"]))
    return covers


def build_grid_data() -> GridData:
    """Run the plate-cost compute chain and return template-ready data."""
    ingredients = load_ingredients(_DATA_DIR / "sample_ingredients.csv")
    dishes = load_dishes(_DATA_DIR / "sample_dishes.csv")
    recipe_lines = load_recipe_lines(_DATA_DIR / "sample_recipe_lines.csv")
    observations = load_price_observations(_DATA_DIR / "sample_prices.csv")
    prices = latest_prices(observations)
    covers_by_key = _load_covers(_DATA_DIR / "sample_sales.csv")
    covers = {key: count for key, (_, count) in covers_by_key.items()}

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

    unmatched_dishes, orphaned_sales = covers_join_report(dish_costs, dishes, covers_by_key)

    rows = build_grid(dish_costs, covers)
    # The true total, not sum(r.covers for r in rows): that would silently understate "covers on
    # record" whenever a sales row is orphaned (matches no menu item) or a dish was skipped as
    # uncostable — both already excluded from `rows`. Sum straight from the raw sales load instead.
    total_covers = sum(count for _, count in covers_by_key.values())

    enriched: list[DishRow] = []
    for r in rows:
        cost_q = round_to_quarter(r.cost)
        # Food-cost % (and its tier) is derived from the SAME rounded cost as cost_display/
        # margin_display, so the third number on the card reconciles by eye too — not just the
        # margin line. r.food_cost_pct (from the unrounded cost) is intentionally not used here.
        food_cost_pct_q = cost_q / r.menu_price
        enriched.append({
            "name": r.name,
            "menu_price": r.menu_price,
            "cost_display": cost_q,
            # Margin derives from the rounded cost so Menu − ~Cost = Margin reconciles by eye.
            # Quadrant classification (in build_grid) still uses the precise margin.
            "margin_display": r.menu_price - cost_q,
            "food_cost_pct": food_cost_pct_q,
            "food_cost_tier": food_cost_tier(food_cost_pct_q),
            "covers": r.covers,
            "quadrant": r.quadrant,
        })

    return {
        "rows": enriched,
        "total_covers": total_covers,
        "quadrants": ["Star", "Plowhorse", "Puzzle", "Dog"],
        "quadrant_actions": QUADRANT_ACTIONS,
        "skipped": skipped,
        "covers_warnings": {
            "unmatched_dishes": unmatched_dishes,
            "orphaned_sales": orphaned_sales,
        },
    }
