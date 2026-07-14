"""Menu-price catalog operations against the app DB (W6) — DB-aware but framework-agnostic
(rule 05: no FastAPI/Starlette import here; ``web/menu_prices.py`` is the only caller that knows
about HTTP), mirroring ``src/auth/service.py``'s split.

The catalog itself (``src/db/models.py::Dish``) is on-ramp-private, app-DB-only — menu price is
user/operational data under the two-store laws
(``docs/website_production_overview.md`` §3) and never crosses the seam. Only the *derived*
``food_cost`` this phase also introduces does that (``tenant_grid.py``).
"""
from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session as DbSession

from ..db.models import Dish
from ..report.grid import normalize_name


def upsert_menu_price(db: DbSession, restaurant_id: str, dish_name: str, menu_price: float) -> Dish:
    """Creates or updates the one ``Dish`` row for ``(restaurant_id, dish_name)``. Raises
    ``ValueError`` (never a bare ``IntegrityError``) on bad input, matching
    ``src/auth/service.py::create_account``'s error-shape convention."""
    dish_name = dish_name.strip()
    if not dish_name:
        raise ValueError("dish_name must not be empty")
    if menu_price <= 0:
        raise ValueError("menu_price must be greater than 0")

    existing = db.scalar(
        select(Dish).where(Dish.restaurant_id == restaurant_id, Dish.dish_name == dish_name)
    )
    if existing is not None:
        existing.menu_price = menu_price
        db.commit()
        db.refresh(existing)
        return existing

    dish = Dish(restaurant_id=restaurant_id, dish_name=dish_name, menu_price=menu_price)
    db.add(dish)
    db.commit()
    db.refresh(dish)
    return dish


def menu_prices_by_seam_key(db: DbSession, restaurant_id: str) -> dict[str, float]:
    """``{seam dish_id: menu_price}`` for joining against ``BomRow``-shaped seam data, whose own
    ``dish_id`` is derived the same way (``normalize_name(dish_name)``,
    ``schemas/seam.py::BomRow``) — one canonical name-key function, not a second one that could
    drift (rule 05 reuse).

    ``Dish`` is unique on the exact ``(restaurant_id, dish_name)``, not the normalized name, so a
    BOM re-upload with different casing/spacing for the same dish can create a second ``Dish`` row
    that normalizes to the same seam key as the first. Ordered by ``updated_at`` ascending so the
    dict comprehension's "last value for a duplicate key wins" behavior resolves any such
    collision to the most-recently-updated price, deterministically, rather than an arbitrary
    query order (W6_review.md MINOR-6)."""
    rows = db.scalars(
        select(Dish).where(Dish.restaurant_id == restaurant_id).order_by(Dish.updated_at)
    )
    return {normalize_name(d.dish_name): d.menu_price for d in rows}
