"""Tests for src/costing/menu_prices.py — the app-DB menu-price catalog (W6).

Covers: upsert creates on first save and updates in place on a second (never a duplicate row),
bad input is rejected with a named ValueError (never a bare IntegrityError), two restaurants'
catalogs never see each other's dishes, and menu_prices_by_seam_key keys by the same
normalize_name() convention the seam's own BomRow.dish_id uses.
"""
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import select

from src.costing.menu_prices import menu_prices_by_seam_key, upsert_menu_price
from src.db.models import Dish, Restaurant


def _make_restaurant(db_sessionmaker, name="Test Kitchen") -> str:
    db = db_sessionmaker()
    try:
        r = Restaurant(name=name)
        db.add(r)
        db.commit()
        db.refresh(r)
        return r.id
    finally:
        db.close()


def test_upsert_creates_new_dish(db_sessionmaker):
    restaurant_id = _make_restaurant(db_sessionmaker)
    db = db_sessionmaker()
    try:
        dish = upsert_menu_price(db, restaurant_id, "Burger", 12.0)
        assert dish.dish_name == "Burger"
        assert dish.menu_price == pytest.approx(12.0)
        assert db.scalar(select(Dish)).id == dish.id
    finally:
        db.close()


def test_upsert_updates_existing_dish_in_place(db_sessionmaker):
    """A second save for the same (restaurant, dish_name) must update the one row, not insert a
    second — the catalog has exactly one current price per dish, not a history."""
    restaurant_id = _make_restaurant(db_sessionmaker)
    db = db_sessionmaker()
    try:
        first = upsert_menu_price(db, restaurant_id, "Burger", 12.0)
        second = upsert_menu_price(db, restaurant_id, "Burger", 13.50)
        assert first.id == second.id
        assert second.menu_price == pytest.approx(13.50)
        assert db.scalar(select(Dish)).menu_price == pytest.approx(13.50)
        assert len(db.scalars(select(Dish)).all()) == 1
    finally:
        db.close()


@pytest.mark.parametrize("dish_name, menu_price", [
    ("", 12.0),        # empty name rejected
    ("   ", 12.0),     # whitespace-only name rejected
    ("Burger", 0.0),   # price must be > 0
    ("Burger", -5.0),  # price can't be negative
])
def test_upsert_rejects_bad_input(db_sessionmaker, dish_name, menu_price):
    restaurant_id = _make_restaurant(db_sessionmaker)
    db = db_sessionmaker()
    try:
        with pytest.raises(ValueError):
            upsert_menu_price(db, restaurant_id, dish_name, menu_price)
    finally:
        db.close()


def test_menu_prices_by_seam_key_normalizes_like_bomrow(db_sessionmaker):
    """The seam's own BomRow.dish_id is normalize_name(dish_name) — the catalog must key its
    lookup dict the identical way so a real BOM row joins without a second id scheme."""
    restaurant_id = _make_restaurant(db_sessionmaker)
    db = db_sessionmaker()
    try:
        upsert_menu_price(db, restaurant_id, "  Caesar Salad  ", 10.0)
        prices = menu_prices_by_seam_key(db, restaurant_id)
        assert prices == {"caesar salad": 10.0}
    finally:
        db.close()


def test_menu_prices_by_seam_key_resolves_normalize_collision_to_most_recent(db_sessionmaker):
    """``Dish`` is unique on the EXACT ``(restaurant_id, dish_name)``, not the normalized name, so
    a BOM re-upload with a different casing/spacing for the same dish can leave two rows that
    normalize to the same seam key. The lookup must resolve that deterministically to the
    most-recently-updated price, not an arbitrary query order (W6_review.md MINOR-6)."""
    restaurant_id = _make_restaurant(db_sessionmaker)
    db = db_sessionmaker()
    try:
        now = datetime.now(timezone.utc)
        old = Dish(
            restaurant_id=restaurant_id, dish_name="Burger", menu_price=12.0,
            created_at=now - timedelta(days=1), updated_at=now - timedelta(days=1),
        )
        new = Dish(
            restaurant_id=restaurant_id, dish_name="burger", menu_price=15.0,
            created_at=now, updated_at=now,
        )
        db.add_all([old, new])
        db.commit()

        assert menu_prices_by_seam_key(db, restaurant_id) == {"burger": 15.0}
    finally:
        db.close()


def test_menu_prices_scoped_to_one_restaurant(db_sessionmaker):
    """Two restaurants' catalogs never leak into each other's lookup (server-enforced tenant
    isolation, rule 06)."""
    db = db_sessionmaker()
    try:
        r1 = Restaurant(name="Kitchen One")
        r2 = Restaurant(name="Kitchen Two")
        db.add_all([r1, r2])
        db.commit()
        db.refresh(r1)
        db.refresh(r2)
    finally:
        db.close()

    db = db_sessionmaker()
    try:
        upsert_menu_price(db, r1.id, "Burger", 12.0)
        upsert_menu_price(db, r2.id, "Salad", 9.0)
        assert menu_prices_by_seam_key(db, r1.id) == {"burger": 12.0}
        assert menu_prices_by_seam_key(db, r2.id) == {"salad": 9.0}
    finally:
        db.close()
