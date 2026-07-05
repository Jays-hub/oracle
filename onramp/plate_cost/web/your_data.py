"""Thin glue between the DuckDB-over-Parquet store (src/store.py) and the "your data" page.

Mirrors web/compute.py's role for the grid and web/upload.py's role for the capture funnel: no
business logic here, only shaping already-validated seam rows into template-ready dicts (rule
05: controllers/glue stay thin). This is the first real caller of src/store.py from the web
layer — W0/W1 deliberately did not read the seam back (see web/compute.py's docstring); wiring
that read is W2's job (`docs/phase_decisions/W2.md`).
"""
from typing import TypedDict

import pandas as pd

from src import store


class YourDataSummary(TypedDict):
    has_data: bool
    dish_count: int
    bom_row_count: int
    sales_row_count: int
    total_covers: int
    period_start: str | None
    period_end: str | None


def build_your_data_summary() -> YourDataSummary:
    """Read the operator's own captured seam legs back through the store helper.

    ``write_seam_atomic`` (src/capture/seam_upload.py) always writes both legs together, so in
    practice either both Parquet files exist or neither does. If no capture has happened yet,
    ``store.read_bom``/``read_sales`` raise ``FileNotFoundError`` (rule 07 legible-failure
    contract) — caught here and reported as ``has_data=False`` rather than propagated, so the
    page can show a calm "nothing captured yet" state instead of an error page.
    """
    try:
        bom_df = store.read_bom()
        sales_df = store.read_sales()
    except FileNotFoundError:
        return {
            "has_data": False,
            "dish_count": 0,
            "bom_row_count": 0,
            "sales_row_count": 0,
            "total_covers": 0,
            "period_start": None,
            "period_end": None,
        }

    return {
        "has_data": True,
        "dish_count": bom_df["dish_name"].nunique(),
        "bom_row_count": len(bom_df),
        "sales_row_count": len(sales_df),
        "total_covers": int(sales_df["count"].sum()),
        # period_start/period_end are pydantic `date`s but round-trip through Parquet/DuckDB
        # as datetime64 Timestamps; str()-ing a Timestamp directly renders a spurious
        # "00:00:00" on this trust/transparency surface (W2_review.md MINOR-2). Route through
        # pd.Timestamp(...).date() so the page always shows a plain date either way.
        "period_start": str(pd.Timestamp(sales_df["period_start"].min()).date()),
        "period_end": str(pd.Timestamp(sales_df["period_end"].max()).date()),
    }


def export_bom_csv() -> str:
    """The operator's own BOM leg as CSV — same open format the seam uses (rule: no lock-in)."""
    return store.read_bom().to_csv(index=False)


def export_sales_csv() -> str:
    """The operator's own sales-export leg as CSV."""
    return store.read_sales().to_csv(index=False)
