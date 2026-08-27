from __future__ import annotations

from datetime import date
from typing import Optional
from uuid import UUID, uuid4

from pydantic import BaseModel, Field


class PriceObservation(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    ingredient_id: UUID
    # As-purchased price per canonical_unit (what's on the invoice). Yield correction applied at compute time.
    unit_price: float = Field(gt=0.0)
    source_invoice: Optional[str] = None
    observed_date: date
