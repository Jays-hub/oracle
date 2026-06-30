"""
Phase 0 static margin map runner.

Usage (from onramp/plate_cost/):
    python -m src.run
    python -m src.run --data data/my_bom --no-export
"""
import argparse
import csv
import sys
from pathlib import Path

import pandas as pd

from pydantic import ValidationError

from .bom.loader import load_dishes, load_ingredients, load_recipe_lines
from .pricing.compute import latest_prices, load_price_observations, plate_cost
from .report.grid import build_grid, normalize_name, print_grid

_PLATE_COST_DIR = Path(__file__).parent.parent
# plate_cost -> onramp -> restaurant-dev (the repo root that owns data/raw/, the shared seam).
_REPO_ROOT = _PLATE_COST_DIR.parent.parent

# schemas/ is platform-owned (data/CONTRACT.md) — imported by BOTH peers, owned by neither. It
# lives at the repo root, outside this package's import path, so put the root on sys.path. This is
# contract-sanctioned (importing the shared seam schemas), NOT peer coupling: the on-ramp still
# never imports forecasting/ (the cross-module boundary test, pending, will assert exactly that).
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))
from schemas import BomRow, SalesExportRow  # noqa: E402  (import after the sys.path bootstrap)


def _load_covers(path: Path) -> dict[str, tuple[str, int]]:
    """Covers per dish, keyed by a normalized name and retaining a display name for reporting.

    Returns ``{normalized_name: (display_name, total_count)}``. Matching on a normalized key
    (trim + casefold) stops a stray space or case difference from silently scoring a dish 0 covers.
    """
    covers: dict[str, tuple[str, int]] = {}
    with open(path, newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            raw = row["dish_name"]
            key = normalize_name(raw)
            display, running = covers.get(key, (raw.strip(), 0))
            covers[key] = (display, running + int(row["count"]))
    return covers


def _report_covers_join(dish_costs, dishes, covers, covers_by_key) -> None:
    """Surface mislabels loudly: a menu dish that matched no sales row (scored 0 covers, so it would
    land in 'Dog' by mislabel), and a sales row that matched no menu item (silently dropped)."""
    graded = {normalize_name(dish.name): dish.name for dish, _ in dish_costs.values()}
    unmatched_dishes = sorted(name for key, name in graded.items() if key not in covers)

    menu_keys = {normalize_name(d.name) for d in dishes.values()}
    orphaned_sales = sorted(
        display for key, (display, _) in covers_by_key.items() if key not in menu_keys
    )

    if unmatched_dishes:
        print("\nCovers-join check — these dishes matched NO sales row (scored 0; check the name):")
        for name in unmatched_dishes:
            print(f"  ! {name}")
    if orphaned_sales:
        print("\nCovers-join check — these sales rows matched NO menu item (dropped from the grid):")
        for name in orphaned_sales:
            print(f"  ! {name}")


def _export_to_raw(ingredients, dishes, recipe_lines, sales_src: Path, raw_dir: Path) -> None:
    raw_dir.mkdir(parents=True, exist_ok=True)

    # BOM → Parquet: validate every row through the seam schema before writing.
    bom_rows = []
    for line in recipe_lines:
        dish = dishes[line.dish_id]
        ing = ingredients[line.ingredient_id]
        try:
            row = BomRow(
                dish_id=str(dish.id), dish_name=dish.name,
                ingredient_id=str(ing.id), ingredient_name=ing.name,
                qty=line.qty, recipe_unit=line.recipe_unit,
                canonical_unit=ing.canonical_unit, yield_factor=ing.yield_factor,
            )
        except ValidationError as e:
            raise ValueError(
                f"BOM export row for '{dish.name}' / '{ing.name}' failed the seam schema:\n{e}"
            ) from e
        bom_rows.append(row.model_dump())

    bom_path = raw_dir / "bom.parquet"
    pd.DataFrame(bom_rows).to_parquet(bom_path, index=False, engine="pyarrow")
    print(f"  -> {bom_path.relative_to(_REPO_ROOT)}")

    # Sales → Parquet: validate every row, then write typed Parquet (dates survive the round-trip).
    sales_rows = []
    with open(sales_src, newline="", encoding="utf-8") as f:
        for line_no, row in enumerate(csv.DictReader(f), start=2):
            try:
                validated = SalesExportRow(
                    dish_name=row["dish_name"],
                    count=row["count"],
                    period_start=row["period_start"],
                    period_end=row["period_end"],
                )
            except ValidationError as e:
                raise ValueError(
                    f"sales_export row {line_no} ('{row.get('dish_name', '?')}') "
                    f"failed the seam schema:\n{e}"
                ) from e
            sales_rows.append(validated.model_dump())

    sales_path = raw_dir / "sales_export.parquet"
    pd.DataFrame(sales_rows).to_parquet(sales_path, index=False, engine="pyarrow")
    print(f"  -> {sales_path.relative_to(_REPO_ROOT)}")


def run(data_dir: Path, export: bool = True) -> None:
    ingredients = load_ingredients(data_dir / "sample_ingredients.csv")
    dishes = load_dishes(data_dir / "sample_dishes.csv")
    recipe_lines = load_recipe_lines(data_dir / "sample_recipe_lines.csv")
    observations = load_price_observations(data_dir / "sample_prices.csv")
    prices = latest_prices(observations)
    covers_by_key = _load_covers(data_dir / "sample_sales.csv")
    covers = {key: count for key, (_, count) in covers_by_key.items()}

    dish_costs: dict = {}
    skipped: list[str] = []
    for dish_id, dish in dishes.items():
        if not dish.is_active:
            continue
        try:
            cost = plate_cost(dish, recipe_lines, ingredients, prices)
            dish_costs[dish_id] = (dish, cost)
        except ValueError as e:
            skipped.append(f"  SKIP {dish.name}: {e}")

    if skipped:
        print("\nWarnings:")
        for s in skipped:
            print(s)

    _report_covers_join(dish_costs, dishes, covers, covers_by_key)

    rows = build_grid(dish_costs, covers)
    total_covers = sum(r.covers for r in rows)
    print_grid(rows, period_label=f"{total_covers} covers · seed prices")

    if export:
        print("Writing to data/raw/ ...")
        _export_to_raw(
            ingredients, dishes, recipe_lines,
            data_dir / "sample_sales.csv",
            _REPO_ROOT / "data" / "raw",
        )
        print("Done.\n")


def main() -> None:
    parser = argparse.ArgumentParser(description="Phase 0 — static margin map")
    parser.add_argument(
        "--data", type=Path,
        default=_PLATE_COST_DIR / "data",
        help="Directory containing sample CSV files (default: plate_cost/data/)",
    )
    parser.add_argument(
        "--no-export", action="store_true",
        help="Skip writing BOM and sales export to data/raw/",
    )
    args = parser.parse_args()
    run(data_dir=args.data, export=not args.no_export)


if __name__ == "__main__":
    main()
