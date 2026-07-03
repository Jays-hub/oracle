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


class UploadSummary(TypedDict):
    dish_count: int
    recipe_line_count: int
    sales_row_count: int
    total_covers: int
    period_start: str
    period_end: str
    dish_names: list[str]


def build_summary(bom_rows: list[BomRow], sales_rows: list[SalesExportRow]) -> UploadSummary:
    """Chef-legible counts for the confirm/success pages — dishes, coverage period, covers."""
    dish_names = sorted({r.dish_name for r in bom_rows} | {r.dish_name for r in sales_rows})
    return {
        "dish_count": len({r.dish_name for r in bom_rows}),
        "recipe_line_count": len(bom_rows),
        "sales_row_count": len(sales_rows),
        "total_covers": sum(r.count for r in sales_rows),
        "period_start": min(r.period_start for r in sales_rows).isoformat(),
        "period_end": max(r.period_end for r in sales_rows).isoformat(),
        "dish_names": dish_names,
    }
