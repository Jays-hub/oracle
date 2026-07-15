"""Thin glue between the W1 capture funnel (src/capture/seam_upload.py) and its templates.

Mirrors web/compute.py's role for the grid: no business logic here, only shaping already-validated
rows into template-ready dicts (rule 05: controllers/glue stay thin, business logic stays in src/).
"""
import sys
from pathlib import Path
from typing import TypedDict

# schemas/ lives at the repo root, outside this package's import path. Self-contained bootstrap
# (not relying on import order vs. src/capture/seam_upload.py doing the same thing first) — a
# little duplicated glue is the price of not coupling module load order across files.
_REPO_ROOT = Path(__file__).resolve().parents[3]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))
from schemas import BomRow, SalesExportRow  # noqa: E402  (import after the sys.path bootstrap)
from src.report.grid import normalize_name  # noqa: E402  (import after the sys.path bootstrap)


class UploadSummary(TypedDict):
    dish_count: int
    costable_dish_count: int
    recipe_line_count: int
    sales_row_count: int
    total_covers: int
    period_start: str
    period_end: str
    dish_names: list[str]


def build_summary(bom_rows: list[BomRow], sales_rows: list[SalesExportRow]) -> UploadSummary:
    """Chef-legible counts for the confirm/success pages — dishes, coverage period, covers.

    ``costable_dish_count`` joins on the same ``normalize_name()`` key
    ``cross_reference_dishes`` uses (W8_review.md MINOR-2) — a dish present in only one file
    (already surfaced separately as ``only_in_bom``/``only_in_sales``) won't actually cost on
    ``/dishes``, so it must not inflate a "this is enough to show value" count.
    """
    dish_names = sorted({r.dish_name for r in bom_rows} | {r.dish_name for r in sales_rows})
    bom_keys = {normalize_name(r.dish_name) for r in bom_rows}
    sales_keys = {normalize_name(r.dish_name) for r in sales_rows}
    return {
        "dish_count": len({r.dish_name for r in bom_rows}),
        "costable_dish_count": len(bom_keys & sales_keys),
        "recipe_line_count": len(bom_rows),
        "sales_row_count": len(sales_rows),
        "total_covers": sum(r.count for r in sales_rows),
        "period_start": min(r.period_start for r in sales_rows).isoformat(),
        "period_end": max(r.period_end for r in sales_rows).isoformat(),
        "dish_names": dish_names,
    }
