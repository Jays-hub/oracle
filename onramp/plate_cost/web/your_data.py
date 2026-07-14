"""Thin glue between the DuckDB-over-Parquet store (src/store.py) and the "your data" page.

Mirrors web/compute.py's role for the grid and web/upload.py's role for the capture funnel: no
business logic here, only shaping already-validated seam rows into template-ready dicts (rule
05: controllers/glue stay thin). This is the first real caller of src/store.py from the web
layer — W0/W1 deliberately did not read the seam back (see web/compute.py's docstring); wiring
that read is W2's job (`docs/phase_decisions/W2.md`).
"""
import logging
from typing import TypedDict

import pandas as pd

from src import store

_log = logging.getLogger(__name__)


class YourDataSummary(TypedDict):
    has_data: bool
    dish_count: int
    bom_row_count: int
    sales_row_count: int
    total_covers: int
    period_start: str | None
    period_end: str | None
    price_observation_count: int
    priced_ingredient_count: int
    has_price_data: bool
    price_leg_error: bool
    food_cost_dish_count: int
    has_food_cost_data: bool
    food_cost_leg_error: bool


def build_your_data_summary() -> YourDataSummary:
    """Read the operator's own captured seam legs back through the store helper.

    ``write_seam_atomic`` (src/capture/seam_upload.py) always writes both legs together, so in
    practice either both Parquet files exist or neither does. If no capture has happened yet,
    ``store.read_bom``/``read_sales`` raise ``FileNotFoundError`` (rule 07 legible-failure
    contract) — caught here and reported as ``has_data=False`` rather than propagated, so the
    page can show a calm "nothing captured yet" state instead of an error page.

    The price-observation (invoice) leg is read independently of BOM/sales (W4): it arrives
    through its own W3 funnel on its own schedule, so an operator can have one without the other.
    The template renders each leg's presence independently too (W4_review.md MAJOR-1) — this
    function only has to report the true per-leg state, never collapse three legs into one flag.
    """
    price_count, priced_ingredients, has_price_data, price_leg_error = _price_leg_stats()
    food_cost_dish_count, has_food_cost_data, food_cost_leg_error = _food_cost_leg_stats()

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
            "price_observation_count": price_count,
            "priced_ingredient_count": priced_ingredients,
            "has_price_data": has_price_data,
            "price_leg_error": price_leg_error,
            "food_cost_dish_count": food_cost_dish_count,
            "has_food_cost_data": has_food_cost_data,
            "food_cost_leg_error": food_cost_leg_error,
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
        "price_observation_count": price_count,
        "priced_ingredient_count": priced_ingredients,
        "has_price_data": has_price_data,
        "price_leg_error": price_leg_error,
        "food_cost_dish_count": food_cost_dish_count,
        "has_food_cost_data": has_food_cost_data,
        "food_cost_leg_error": food_cost_leg_error,
    }


def _price_leg_stats() -> tuple[int, int, bool, bool]:
    """Row/ingredient count, presence, and error state for the invoice/price-history leg (W3).

    Returns ``(count, ingredient_count, has_price_data, price_leg_error)``. A missing leg is a
    normal, non-error state (not every operator has uploaded an invoice yet) — zeros, no error. A
    *present but unreadable* leg (corrupt/partial Parquet) is reported as its own explicit error
    state rather than silently folded into "not connected yet": the operator gets an honest
    "temporarily unavailable," never a false claim that nothing was ever uploaded
    (W4_review.md MINOR-1). The route layer still wraps the whole summary build in a calm
    fallback for anything unexpected in the BOM/sales path; this local catch is what lets THIS
    leg degrade on its own without taking the rest of the page down with it.
    """
    try:
        price_df = store.read_price_observations()
    except FileNotFoundError:
        return 0, 0, False, False
    except Exception:
        _log.exception("price-observations leg unreadable while building /your-data summary")
        return 0, 0, False, True
    return len(price_df), price_df["ingredient_id"].nunique(), True, False


def _food_cost_leg_stats() -> tuple[int, bool, bool]:
    """Dish count, presence, and error state for the derived food-cost leg (W6) -- the same
    independent-per-leg, non-error-when-missing pattern ``_price_leg_stats`` established, so
    ``/your-data`` discloses the new engine-bound leg menu_prices.html already points operators
    at (W6_review.md MAJOR-1: the leg was written but never disclosed here). No menu price ever
    appears in this leg or its export -- only the derived cost."""
    try:
        food_cost_df = store.read_food_cost()
    except FileNotFoundError:
        return 0, False, False
    except Exception:
        _log.exception("food_cost leg unreadable while building /your-data summary")
        return 0, False, True
    return len(food_cost_df), True, False


def export_bom_csv() -> str:
    """The operator's own BOM leg as CSV — same open format the seam uses (rule: no lock-in)."""
    return store.read_bom().to_csv(index=False)


def export_sales_csv() -> str:
    """The operator's own sales-export leg as CSV."""
    return store.read_sales().to_csv(index=False)


def export_price_observations_csv() -> str:
    """The operator's own invoice/price-history leg as CSV (W4 — was missing from the W2 export
    set entirely, since that leg didn't exist until W3 added it and /your-data was never
    revisited until now)."""
    return store.read_price_observations().to_csv(index=False)


def export_food_cost_csv() -> str:
    """The derived per-dish food-cost leg as CSV (W6) — what menu_prices.html promises the
    operator they can see under "what we send the forecasting engine" (W6_review.md MAJOR-1)."""
    return store.read_food_cost().to_csv(index=False)
