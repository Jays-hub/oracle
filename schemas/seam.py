"""Shared seam schemas — the data-quality gate on what crosses ``data/raw/``.

These describe the **on-disk shapes that cross the seam** between the two peers
(``onramp/`` writes, ``forecasting/`` reads) — NOT the in-memory models. A denormalized
``bom.csv`` row is deliberately not the normalized ``RecipeLine`` in
``onramp/plate_cost/src/bom/models.py``; the seam schema describes what is actually written
to disk and read back, per ``../data/CONTRACT.md``.

Owned by neither peer; imported by both (the on-ramp validates on **write**, the engine will
validate on **read**). Thin by design — only the files that actually cross the seam today are
defined here (``bom.csv``, ``sales_export.csv``, ``price_observations.csv`` — added in W3 when the
on-ramp's invoice-ingestion leg first crossed; ``food_cost.csv`` — added in W6, the derived
Co-provenance leg). ``eightysix_log.csv`` still gets a schema only when it first crosses
(Anti-Drift; see ``README.md``).

Gate-4 capture (2026-06-25, Jay): the schema is "a data-quality gate that prevents malformed
data from entering." Say-it-to-a-chef: "the head chef that checks every dish before it goes
out to the customers."
"""
from __future__ import annotations

from datetime import date

from pydantic import BaseModel, Field, model_validator


class BomRow(BaseModel):
    """One row of ``data/raw/bom.csv`` — the BOM leg as it crosses the seam (denormalized)."""

    dish_id: str = Field(min_length=1)
    dish_name: str = Field(min_length=1)
    ingredient_id: str = Field(min_length=1)
    ingredient_name: str = Field(min_length=1)
    qty: float = Field(gt=0.0)
    recipe_unit: str = Field(min_length=1)
    canonical_unit: str = Field(min_length=1)
    yield_factor: float = Field(gt=0.0, le=1.0)


class SalesExportRow(BaseModel):
    """One row of ``data/raw/sales_export.csv`` — the sales-history leg as it crosses the seam."""

    dish_name: str = Field(min_length=1)
    count: int = Field(ge=0)
    period_start: date
    period_end: date

    @model_validator(mode="after")
    def _period_ordered(self) -> "SalesExportRow":
        if self.period_end < self.period_start:
            raise ValueError(
                f"period_end ({self.period_end}) is before period_start ({self.period_start})"
            )
        return self


class PriceObservationRow(BaseModel):
    """One row of ``data/raw/price_observations.csv`` — the invoice/price-history leg.

    Denormalized like ``BomRow``: ``ingredient_id`` is name-derived (``normalize_name()``), not a
    UUID — the CLI-internal ``onramp/plate_cost/src/pricing/models.py::PriceObservation`` keys on
    a UUID, but that model never crosses the seam. This row is the on-disk shape; it deliberately
    joins to ``BomRow.ingredient_id`` on the same name-key convention rather than inventing a
    second ID scheme, so a price observation can be matched to a recipe ingredient without a
    separate entity-resolution table.
    """

    ingredient_id: str = Field(min_length=1)
    ingredient_name: str = Field(min_length=1)
    unit_price: float = Field(gt=0.0)
    source_invoice: str | None = None
    observed_date: date


class FoodCostRow(BaseModel):
    """One row of ``data/raw/food_cost.parquet`` — the derived per-dish ingredient-cost leg (W6).

    Closes ``data/CONTRACT.md``'s "Co provenance" forward note: ``Co`` is the plate cost the
    on-ramp already computes from ``BomRow`` + ``PriceObservationRow`` (the same formula
    ``src/insights/opportunities.py::dish_ingredient_cost`` uses), written through the seam so a
    later engine phase can read a real, on-ramp-computed cost instead of ``config/items.yaml``'s
    hand-typed placeholder. ``dish_id`` matches ``BomRow.dish_id``'s convention
    (``normalize_name(dish_name)``) so the two legs join without a separate id scheme.

    Deliberately carries no ``menu_price``: menu price is user/operational catalog data (the
    two-store laws, ``onramp/plate_cost/docs/website_production_overview.md`` §3) and never
    crosses the seam — only this derived cost does. ``food_cost`` itself doesn't depend on
    ``menu_price`` either; recomputing it is triggered by the on-ramp's menu-price-save action
    (``src/costing/tenant_grid.py``), but the number itself is pure ingredient math.
    """

    dish_id: str = Field(min_length=1)
    dish_name: str = Field(min_length=1)
    food_cost: float = Field(gt=0.0)
    computed_at: date
