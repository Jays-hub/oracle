"""Tests for the W6 GET/POST /menu-prices route (web/app.py + web/menu_prices.py).

Covers: the empty state (no recipe sheet captured), the form lists every captured dish, saving a
price persists it and shows up on a re-render, saving also writes the derived food_cost seam leg,
a blank field leaves a dish's price unset (not an error), a non-positive submitted value is
rejected and named, and an unauthenticated request never reaches any tenant data.
"""
import pandas as pd
import pytest
from fastapi.testclient import TestClient

from schemas import BomRow, PriceObservationRow
from src import store
from src.auth.service import create_account
from web.app import app

_BOM_ROW = BomRow(
    dish_id="burger", dish_name="Burger", ingredient_id="beef", ingredient_name="beef",
    qty=6.0, recipe_unit="oz", canonical_unit="oz", yield_factor=0.9,
)
_PRICE_ROW = PriceObservationRow(
    ingredient_id="beef", ingredient_name="beef", unit_price=3.0,
    source_invoice="inv-1", observed_date="2026-06-01",
)


def _seed_raw_dir(raw_dir, with_prices=True):
    pd.DataFrame([_BOM_ROW.model_dump()]).to_parquet(raw_dir / "bom.parquet", index=False, engine="pyarrow")
    if with_prices:
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


def test_menu_prices_redirects_unauthenticated_get_to_login():
    client = TestClient(app)
    resp = client.get("/menu-prices", follow_redirects=False)
    assert resp.status_code == 303
    assert resp.headers["location"] == "/login"


def test_menu_prices_redirects_unauthenticated_post_to_login():
    client = TestClient(app)
    resp = client.post("/menu-prices", data={"price__burger": "12.00"}, follow_redirects=False)
    assert resp.status_code == 303
    assert resp.headers["location"] == "/login"


def test_menu_prices_shows_empty_state_when_no_bom_captured(db_sessionmaker, monkeypatch, tmp_path):
    monkeypatch.setattr(store, "RAW_DIR", tmp_path)
    client = _logged_in_client(db_sessionmaker)
    resp = client.get("/menu-prices")
    assert resp.status_code == 200
    assert "No recipe sheet captured yet" in resp.text


def test_menu_prices_form_lists_captured_dish(db_sessionmaker, monkeypatch, tmp_path):
    _seed_raw_dir(tmp_path)
    monkeypatch.setattr(store, "RAW_DIR", tmp_path)
    client = _logged_in_client(db_sessionmaker)
    resp = client.get("/menu-prices")
    assert resp.status_code == 200
    assert "Burger" in resp.text
    assert 'name="price__burger"' in resp.text


def test_saving_a_menu_price_persists_and_shows_on_rerender(db_sessionmaker, monkeypatch, tmp_path):
    _seed_raw_dir(tmp_path)
    monkeypatch.setattr(store, "RAW_DIR", tmp_path)
    client = _logged_in_client(db_sessionmaker)

    resp = client.post("/menu-prices", data={"price__burger": "12.00"}, follow_redirects=False)
    assert resp.status_code == 303
    assert resp.headers["location"] == "/dishes"

    resp = client.get("/menu-prices")
    assert 'value="12.00"' in resp.text


def test_saving_a_menu_price_writes_the_food_cost_seam_leg(db_sessionmaker, monkeypatch, tmp_path):
    _seed_raw_dir(tmp_path)
    monkeypatch.setattr(store, "RAW_DIR", tmp_path)
    client = _logged_in_client(db_sessionmaker)

    client.post("/menu-prices", data={"price__burger": "12.00"}, follow_redirects=False)

    assert (tmp_path / "food_cost.parquet").exists()
    on_disk = pd.read_parquet(tmp_path / "food_cost.parquet")
    assert on_disk["dish_id"].iloc[0] == "burger"
    assert on_disk["food_cost"].iloc[0] == pytest.approx(6.0 / 0.9 * 3.0)


def test_saving_with_no_price_observations_yet_upserts_price_without_crashing(db_sessionmaker, monkeypatch, tmp_path):
    """An operator may set a menu price before ever uploading an invoice -- no food_cost leg can
    be derived yet (no ingredient prices), but the save itself must still succeed."""
    _seed_raw_dir(tmp_path, with_prices=False)
    monkeypatch.setattr(store, "RAW_DIR", tmp_path)
    client = _logged_in_client(db_sessionmaker)

    resp = client.post("/menu-prices", data={"price__burger": "12.00"}, follow_redirects=False)
    assert resp.status_code == 303
    assert not (tmp_path / "food_cost.parquet").exists()

    resp = client.get("/menu-prices")
    assert 'value="12.00"' in resp.text


def test_food_cost_leg_is_cleared_when_no_dish_remains_costable(db_sessionmaker, monkeypatch, tmp_path):
    """A stale food_cost.parquet from a prior state must not linger once nothing is costable
    (W6_review.md LOW-6): saving a menu price writes the leg, then a price observation going
    missing (e.g. a BOM/price re-upload that leaves the dish uncostable) and a second save must
    clear the file rather than silently keep the old snapshot."""
    _seed_raw_dir(tmp_path)
    monkeypatch.setattr(store, "RAW_DIR", tmp_path)
    client = _logged_in_client(db_sessionmaker)

    client.post("/menu-prices", data={"price__burger": "12.00"}, follow_redirects=False)
    assert (tmp_path / "food_cost.parquet").exists()

    (tmp_path / "price_observations.parquet").unlink()  # simulate: beef no longer has a price

    client.post("/menu-prices", data={"price__burger": "15.00"}, follow_redirects=False)
    assert not (tmp_path / "food_cost.parquet").exists()


def test_blank_price_field_leaves_dish_unset(db_sessionmaker, monkeypatch, tmp_path):
    _seed_raw_dir(tmp_path)
    monkeypatch.setattr(store, "RAW_DIR", tmp_path)
    client = _logged_in_client(db_sessionmaker)

    resp = client.post("/menu-prices", data={"price__burger": ""}, follow_redirects=False)
    assert resp.status_code == 303  # not an error -- just nothing set

    resp = client.get("/menu-prices")
    assert 'value=""' in resp.text or 'placeholder="e.g. 14.00">' in resp.text


def test_non_positive_price_is_rejected_and_named(db_sessionmaker, monkeypatch, tmp_path):
    _seed_raw_dir(tmp_path)
    monkeypatch.setattr(store, "RAW_DIR", tmp_path)
    client = _logged_in_client(db_sessionmaker)

    resp = client.post("/menu-prices", data={"price__burger": "-5"}, follow_redirects=False)
    assert resp.status_code == 422
    assert "burger" in resp.text
    assert "positive number" in resp.text


def test_non_numeric_price_is_rejected(db_sessionmaker, monkeypatch, tmp_path):
    _seed_raw_dir(tmp_path)
    monkeypatch.setattr(store, "RAW_DIR", tmp_path)
    client = _logged_in_client(db_sessionmaker)

    resp = client.post("/menu-prices", data={"price__burger": "abc"}, follow_redirects=False)
    assert resp.status_code == 422
