"""Thin glue between the W3 invoice capture (ingest/capture/invoice_upload.py) and its templates.

Mirrors surface/web/upload.py's role for the W1 funnel: no business logic here, only shaping
already-validated rows into template-ready dicts (rule 05: controllers/glue stay thin).

No sys.path bootstrap since the layer restructure: schemas/ is a repo-root package like this one.
"""
from typing import TypedDict

from schemas import PriceObservationRow


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
