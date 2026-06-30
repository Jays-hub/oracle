"""Shared seam schemas — the data-quality gate on what crosses ``data/raw/``.

These describe the **on-disk shapes that cross the seam** between the two peers
(``onramp/`` writes, ``forecasting/`` reads) — NOT the in-memory models. A denormalized
``bom.csv`` row is deliberately not the normalized ``RecipeLine`` in
``onramp/plate_cost/src/bom/models.py``; the seam schema describes what is actually written
to disk and read back, per ``../data/CONTRACT.md``.

Owned by neither peer; imported by both (the on-ramp validates on **write**, the engine will
validate on **read**). Thin by design — only the files that actually cross the seam today are
defined here (``bom.csv``, ``sales_export.csv``). ``price_observations.csv`` and
``eightysix_log.csv`` get schemas when they first cross (Anti-Drift; see ``README.md``).

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
