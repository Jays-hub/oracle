from __future__ import annotations

from typing import Optional
from uuid import UUID, uuid4

from pydantic import BaseModel, Field


class Ingredient(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    name: str
    canonical_unit: str
    yield_factor: float = Field(gt=0.0, le=1.0)
    notes: Optional[str] = None


class Dish(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    name: str
    menu_price: float = Field(gt=0.0)
    service_period: Optional[str] = None
    is_active: bool = True


class RecipeLine(BaseModel):
    dish_id: UUID
    ingredient_id: UUID
    qty: float = Field(gt=0.0)
    recipe_unit: str
