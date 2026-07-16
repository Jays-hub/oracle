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

from pydantic import ValidationError

from .bom.loader import load_dishes, load_ingredients, load_recipe_lines
from .capture.seam_upload import write_seam_atomic
from .pricing.compute import latest_prices, load_price_observations, plate_cost
from .report.grid import build_grid, covers_join_report, normalize_name, print_grid

_PLATE_COST_DIR = Path(__file__).parent.parent
# plate_cost -> onramp -> restaurant-dev (the repo root that owns data/raw/, the shared seam).
_REPO_ROOT = _PLATE_COST_DIR.parent.parent

# data/raw/ is a per-tenant container since W9 (data/CONTRACT.md) — this CLI predates the web
# app's accounts entirely (no login, no Restaurant row), so it writes into a fixed, non-account-
# linked bucket rather than inventing tenant selection this standalone demo tool doesn't need.
# The nil UUID (uuid.UUID(int=0).hex) is the documented sentinel both peers hardcode identically
# for exactly this "no real signup-issued tenant" case (data/CONTRACT.md).
_DEMO_RESTAURANT_ID = "00000000000000000000000000000000"

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


def _report_covers_join(dish_costs, dishes, covers_by_key) -> None:
    """Print the shared covers-join check (`report.grid.covers_join_report`) to the terminal."""
    unmatched_dishes, orphaned_sales = covers_join_report(dish_costs, dishes, covers_by_key)

    if unmatched_dishes:
        print("\nCovers-join check — these dishes matched NO sales row (scored 0; check the name):")
        for name in unmatched_dishes:
            print(f"  ! {name}")
    if orphaned_sales:
        print("\nCovers-join check — these sales rows matched NO menu item (dropped from the grid):")
        for name in orphaned_sales:
            print(f"  ! {name}")


def _export_to_raw(ingredients, dishes, recipe_lines, sales_src: Path, raw_dir: Path) -> None:
    # BOM: validate every row through the seam schema before writing.
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
        bom_rows.append(row)

    # Sales: validate every row against the same seam schema the self-serve upload uses (W1).
    sales_rows = []
    with open(sales_src, newline="", encoding="utf-8") as f:
        for line_no, row in enumerate(csv.DictReader(f), start=2):
            try:
                sales_rows.append(SalesExportRow(
                    dish_name=row["dish_name"],
                    count=row["count"],
                    period_start=row["period_start"],
                    period_end=row["period_end"],
                ))
            except ValidationError as e:
                raise ValueError(
                    f"sales_export row {line_no} ('{row.get('dish_name', '?')}') "
                    f"failed the seam schema:\n{e}"
                ) from e

    # One shared, atomic (temp-then-rename) writer for both producers of the seam — the CLI here
    # and the web upload/confirm flow (src/capture/seam_upload.py) — so there is exactly one place
    # that knows how to persist bom.parquet/sales_export.parquet correctly (rule 05 reuse; rule 07
    # atomicity).
    write_seam_atomic(bom_rows, sales_rows, raw_dir)
    print(f"  -> {(raw_dir / 'bom.parquet').relative_to(_REPO_ROOT)}")
    print(f"  -> {(raw_dir / 'sales_export.parquet').relative_to(_REPO_ROOT)}")


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

    _report_covers_join(dish_costs, dishes, covers_by_key)

    rows = build_grid(dish_costs, covers)
    total_covers = sum(r.covers for r in rows)
    print_grid(rows, period_label=f"{total_covers} covers · seed prices")

    if export:
        print("Writing to data/raw/ ...")
        _export_to_raw(
            ingredients, dishes, recipe_lines,
            data_dir / "sample_sales.csv",
            _REPO_ROOT / "data" / "raw" / _DEMO_RESTAURANT_ID,
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
