"""Thin glue between the W3 invoice capture (src/capture/invoice_upload.py) and its templates.

Mirrors web/upload.py's role for the W1 funnel: no business logic here, only shaping already-
validated rows into template-ready dicts (rule 05: controllers/glue stay thin).
"""
import sys
from pathlib import Path
from typing import TypedDict

# schemas/ lives at the repo root, outside this package's import path. Self-contained bootstrap,
# mirroring web/upload.py exactly (a little duplicated glue is the price of not coupling module
# load order across files).
_REPO_ROOT = Path(__file__).resolve().parents[3]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))
from schemas import PriceObservationRow  # noqa: E402  (import after the sys.path bootstrap)


class InvoiceSummary(TypedDict):
    row_count: int
    ingredient_count: int
    period_start: str
    period_end: str


def build_invoice_summary(rows: list[PriceObservationRow]) -> InvoiceSummary:
    """Chef-legible counts for the invoice confirm/success pages."""
    dates = [r.observed_date for r in rows]
    return {
        "row_count": len(rows),
        "ingredient_count": len({r.ingredient_id for r in rows}),
        "period_start": min(dates).isoformat(),
        "period_end": max(dates).isoformat(),
    }
