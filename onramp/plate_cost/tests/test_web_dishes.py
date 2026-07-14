"""Tests for the W6 GET /dishes and GET /dishes/{dish_id} routes (web/app.py + web/dishes.py).

Covers: unauthenticated requests never reach tenant data, the empty state (no BOM captured), a
fully priced/costed dish shows real margin/cost/tier figures, an unpriced dish is named as unpriced
rather than silently dropped, the dish-detail line-by-line breakdown reconciles by eye (lines sum
to the shown total), a dish detail with a missing ingredient price degrades honestly instead of
crashing, and an unknown dish_id returns a calm 404.
"""
import pandas as pd
from fastapi.testclient import TestClient
from sqlalchemy import select

from schemas import BomRow, PriceObservationRow, SalesExportRow
from src import store
from src.auth.service import create_account
from web.app import app

_BOM_ROWS = [
    BomRow(dish_id="burger", dish_name="Burger", ingredient_id="beef", ingredient_name="beef",
           qty=6.0, recipe_unit="oz", canonical_unit="oz", yield_factor=0.9),
    BomRow(dish_id="salad", dish_name="Salad", ingredient_id="romaine", ingredient_name="romaine",
           qty=4.0, recipe_unit="oz", canonical_unit="oz", yield_factor=1.0),
]
_SALES_ROW = SalesExportRow(
    dish_name="Burger", count=100, period_start="2026-06-01", period_end="2026-06-07",
)
_PRICE_ROW = PriceObservationRow(
    ingredient_id="beef", ingredient_name="beef", unit_price=3.0,
    source_invoice="inv-1", observed_date="2026-06-01",
)


def _seed_raw_dir(raw_dir):
    pd.DataFrame([r.model_dump() for r in _BOM_ROWS]).to_parquet(
        raw_dir / "bom.parquet", index=False, engine="pyarrow"
    )
    pd.DataFrame([_SALES_ROW.model_dump()]).to_parquet(
        raw_dir / "sales_export.parquet", index=False, engine="pyarrow"
    )
    pd.DataFrame([_PRICE_ROW.model_dump()]).to_parquet(
        raw_dir / "price_observations.parquet", index=False, engine="pyarrow"
    )


def _logged_in_client(db_sessionmaker) -> TestClient:
    db = db_sessionmaker()
    try:
        create_account(db, "Test Kitchen", "chef@example.com", "s3cret123")
    finally:
        db.close()
    client = TestClient(app)
    resp = client.post(
        "/login", data={"email": "chef@example.com", "password": "s3cret123"}, follow_redirects=True,
    )
    assert resp.status_code == 200
    return client


def _set_menu_price(db_sessionmaker, dish_name="Burger", price=25.0):
    from src.costing.menu_prices import upsert_menu_price
    from src.db.models import Restaurant
    db = db_sessionmaker()
    try:
        restaurant = db.scalars(select(Restaurant)).one()
        upsert_menu_price(db, restaurant.id, dish_name, price)
    finally:
        db.close()


def test_dishes_grid_redirects_unauthenticated_to_login():
    client = TestClient(app)
    resp = client.get("/dishes", follow_redirects=False)
    assert resp.status_code == 303
    assert resp.headers["location"] == "/login"


def test_dish_detail_redirects_unauthenticated_to_login():
    client = TestClient(app)
    resp = client.get("/dishes/burger", follow_redirects=False)
    assert resp.status_code == 303
    assert resp.headers["location"] == "/login"


def test_dishes_grid_shows_empty_state_when_no_bom_captured(db_sessionmaker, monkeypatch, tmp_path):
    monkeypatch.setattr(store, "RAW_DIR", tmp_path)
    client = _logged_in_client(db_sessionmaker)
    resp = client.get("/dishes")
    assert resp.status_code == 200
    assert "No recipe sheet captured yet" in resp.text


def test_dishes_grid_shows_real_costed_dish(db_sessionmaker, monkeypatch, tmp_path):
    _seed_raw_dir(tmp_path)
    monkeypatch.setattr(store, "RAW_DIR", tmp_path)
    client = _logged_in_client(db_sessionmaker)
    _set_menu_price(db_sessionmaker, "Burger", 25.0)

    resp = client.get("/dishes")
    assert resp.status_code == 200
    assert "Burger" in resp.text
    assert "$20.00" in resp.text  # ~cost: 6oz*3.00/0.9 = 20.00
    assert "$5.00" in resp.text   # margin: 25.00 - 20.00


def test_dishes_grid_names_unpriced_dish_instead_of_dropping_it(db_sessionmaker, monkeypatch, tmp_path):
    """Salad has no menu price and no romaine price observation -- must be named in the unpriced
    list, never silently omitted with no explanation."""
    _seed_raw_dir(tmp_path)
    monkeypatch.setattr(store, "RAW_DIR", tmp_path)
    client = _logged_in_client(db_sessionmaker)
    _set_menu_price(db_sessionmaker, "Burger", 25.0)

    resp = client.get("/dishes")
    assert resp.status_code == 200
    assert "Salad" in resp.text
    assert "not shown below" in resp.text


def test_dish_detail_shows_ingredient_breakdown_reconciling_to_total(db_sessionmaker, monkeypatch, tmp_path):
    _seed_raw_dir(tmp_path)
    monkeypatch.setattr(store, "RAW_DIR", tmp_path)
    client = _logged_in_client(db_sessionmaker)
    _set_menu_price(db_sessionmaker, "Burger", 25.0)

    resp = client.get("/dishes/burger")
    assert resp.status_code == 200
    assert "beef" in resp.text
    assert "$20.00" in resp.text  # the one line IS the total here
    assert "$5.00" in resp.text   # margin


_MULTI_INGREDIENT_BOM_ROWS = [
    BomRow(dish_id="fries", dish_name="Fries", ingredient_id="garlic", ingredient_name="garlic",
           qty=0.5, recipe_unit="oz", canonical_unit="oz", yield_factor=1.0),
    BomRow(dish_id="fries", dish_name="Fries", ingredient_id="butter", ingredient_name="butter",
           qty=0.5, recipe_unit="oz", canonical_unit="oz", yield_factor=1.0),
    BomRow(dish_id="fries", dish_name="Fries", ingredient_id="salt", ingredient_name="salt",
           qty=0.5, recipe_unit="oz", canonical_unit="oz", yield_factor=1.0),
]
_MULTI_INGREDIENT_PRICE_ROWS = [
    PriceObservationRow(ingredient_id="garlic", ingredient_name="garlic", unit_price=0.20,
                         source_invoice="inv-1", observed_date="2026-06-01"),
    PriceObservationRow(ingredient_id="butter", ingredient_name="butter", unit_price=0.24,
                         source_invoice="inv-1", observed_date="2026-06-01"),
    PriceObservationRow(ingredient_id="salt", ingredient_name="salt", unit_price=0.20,
                         source_invoice="inv-1", observed_date="2026-06-01"),
]


def test_dish_detail_total_reconciles_with_grid_for_a_multi_ingredient_dish(db_sessionmaker, monkeypatch, tmp_path):
    """Regression for W6_review.md BLOCKER-1: garlic/butter/salt each cost $0.10/$0.12/$0.10 --
    every one individually rounds to $0.00 on the $0.25 grid, but the real $0.32 total rounds
    ONCE, on the aggregate, to $0.25. The single-ingredient reconciliation test above can't catch
    this (its one line IS the total); this fixture is the one the bug actually breaks. The grid
    and the detail page must show the identical ~Cost and margin for the same dish."""
    pd.DataFrame([r.model_dump() for r in _MULTI_INGREDIENT_BOM_ROWS]).to_parquet(
        tmp_path / "bom.parquet", index=False, engine="pyarrow"
    )
    pd.DataFrame([r.model_dump() for r in _MULTI_INGREDIENT_PRICE_ROWS]).to_parquet(
        tmp_path / "price_observations.parquet", index=False, engine="pyarrow"
    )
    monkeypatch.setattr(store, "RAW_DIR", tmp_path)
    client = _logged_in_client(db_sessionmaker)
    _set_menu_price(db_sessionmaker, "Fries", 9.00)

    grid_resp = client.get("/dishes")
    detail_resp = client.get("/dishes/fries")
    assert grid_resp.status_code == 200
    assert detail_resp.status_code == 200

    assert "$0.25" in grid_resp.text     # NOT $0.00 -- round once, on the aggregate
    assert "$0.25" in detail_resp.text
    assert "$8.75" in grid_resp.text     # margin: 9.00 - 0.25
    assert "$8.75" in detail_resp.text


def test_dish_detail_degrades_honestly_when_ingredient_price_missing(db_sessionmaker, monkeypatch, tmp_path):
    """Salad's romaine has no price observation -- the page must render (not crash) and say the
    total isn't available, rather than showing a fabricated $0 cost."""
    _seed_raw_dir(tmp_path)
    monkeypatch.setattr(store, "RAW_DIR", tmp_path)
    client = _logged_in_client(db_sessionmaker)

    resp = client.get("/dishes/salad")
    assert resp.status_code == 200
    assert "price not yet captured" in resp.text
    assert "unavailable" in resp.text.lower()


def test_dish_detail_returns_calm_404_for_unknown_dish(db_sessionmaker, monkeypatch, tmp_path):
    _seed_raw_dir(tmp_path)
    monkeypatch.setattr(store, "RAW_DIR", tmp_path)
    client = _logged_in_client(db_sessionmaker)

    resp = client.get("/dishes/nonexistent-dish")
    assert resp.status_code == 404
    assert "Traceback" not in resp.text


def test_dish_detail_returns_calm_404_when_no_bom_captured(db_sessionmaker, monkeypatch, tmp_path):
    monkeypatch.setattr(store, "RAW_DIR", tmp_path)
    client = _logged_in_client(db_sessionmaker)

    resp = client.get("/dishes/burger")
    assert resp.status_code == 404


def test_dishes_grid_returns_calm_503_on_unexpected_failure(db_sessionmaker, monkeypatch, tmp_path):
    import web.app as appmod

    def boom(db, restaurant_id):
        raise RuntimeError("simulated: something broke at /secret/internal/path")

    monkeypatch.setattr(appmod, "build_dishes_summary", boom)
    client = _logged_in_client(db_sessionmaker)
    resp = client.get("/dishes")
    assert resp.status_code == 503
    assert "simulated" not in resp.text
    assert "Traceback" not in resp.text
