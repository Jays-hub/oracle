"""Tests for the W2 session-based login gate and the /your-data page + export.

Covers: correct/incorrect login, fail-closed when unconfigured, every protected route
(/your-data, /upload, /confirm, the export endpoints) redirects an unauthenticated request to
/login rather than serving any tenant data — the concrete, verifiable form of "tenant isolation
holds" today (07-backend-api.md's testing section): there is exactly one tenant in the physical
store, so the isolation boundary that actually exists is anonymous-vs-authenticated, not
tenant-vs-tenant (see docs/phase_decisions/W2.md for why a physical multi-tenant partition isn't
built here) — logout clears the session, and /your-data reads real captured data back through
src/store.py (the first real caller of that helper from the web layer), including the empty
state when nothing has been captured yet.

Each test builds its own TestClient rather than sharing one module-level instance (unlike
test_web.py/test_web_upload.py) because these tests specifically exercise session-cookie state,
which must not leak between tests.
"""
import pandas as pd
import pytest
from fastapi.testclient import TestClient

from schemas import BomRow, SalesExportRow
from src import store
from src.auth.credentials import PASSWORD_HASH_ENV, USERNAME_ENV, hash_password
from web.app import app

_BOM_ROW = BomRow(
    dish_id="d1", dish_name="Burger", ingredient_id="i1", ingredient_name="beef",
    qty=6.0, recipe_unit="oz", canonical_unit="oz", yield_factor=0.9,
)
_SALES_ROW = SalesExportRow(
    dish_name="Burger", count=120, period_start="2026-06-01", period_end="2026-06-07",
)


def _seed_raw_dir(tmp_path):
    pd.DataFrame([_BOM_ROW.model_dump()]).to_parquet(tmp_path / "bom.parquet", index=False, engine="pyarrow")
    pd.DataFrame([_SALES_ROW.model_dump()]).to_parquet(
        tmp_path / "sales_export.parquet", index=False, engine="pyarrow"
    )


def _set_credential(monkeypatch, username="chef", password="s3cret"):
    monkeypatch.setenv(USERNAME_ENV, username)
    monkeypatch.setenv(PASSWORD_HASH_ENV, hash_password(password))
    return username, password


def _logged_in_client(monkeypatch) -> TestClient:
    username, password = _set_credential(monkeypatch)
    client = TestClient(app)
    resp = client.post(
        "/login", data={"username": username, "password": password}, follow_redirects=True,
    )
    assert resp.status_code == 200  # landed on /your-data after the redirect
    return client


def test_login_form_returns_200():
    client = TestClient(app)
    resp = client.get("/login")
    assert resp.status_code == 200
    assert "username" in resp.text and "password" in resp.text


def test_correct_login_redirects_to_your_data(monkeypatch):
    username, password = _set_credential(monkeypatch)
    client = TestClient(app)
    resp = client.post(
        "/login", data={"username": username, "password": password}, follow_redirects=False,
    )
    assert resp.status_code == 303
    assert resp.headers["location"] == "/your-data"


def test_wrong_password_returns_401_with_error_and_grants_no_session(monkeypatch):
    username, _ = _set_credential(monkeypatch)
    client = TestClient(app)
    resp = client.post("/login", data={"username": username, "password": "wrong"})
    assert resp.status_code == 401
    assert "Incorrect username or password" in resp.text

    protected = client.get("/your-data", follow_redirects=False)
    assert protected.status_code == 303
    assert protected.headers["location"] == "/login"


def test_login_fails_closed_when_credential_unconfigured(monkeypatch):
    monkeypatch.delenv(USERNAME_ENV, raising=False)
    monkeypatch.delenv(PASSWORD_HASH_ENV, raising=False)
    client = TestClient(app)
    resp = client.post("/login", data={"username": "anyone", "password": "anything"})
    assert resp.status_code == 401


@pytest.mark.parametrize(
    "method, path, kwargs",
    [
        ("get", "/your-data", {}),
        ("get", "/upload", {}),
        ("post", "/confirm", {"data": {"sales_csv_b64": "x", "bom_csv_b64": "x"}}),
        ("get", "/your-data/export/bom", {}),
        ("get", "/your-data/export/sales", {}),
        ("get", "/invoice/upload", {}),
        ("post", "/invoice/confirm", {"data": {"invoice_csv_b64": "x"}}),
        ("get", "/insights", {}),
    ],
)
def test_protected_routes_redirect_unauthenticated_requests_to_login(method, path, kwargs):
    """No data-bearing route serves its content to an unauthenticated request — every one
    redirects to /login instead of the page/file itself."""
    client = TestClient(app)
    resp = getattr(client, method)(path, follow_redirects=False, **kwargs)
    assert resp.status_code == 303
    assert resp.headers["location"] == "/login"


def test_public_grid_still_accessible_without_login():
    """GET / is the deliberately public sample-data reveal (W0) — it must stay reachable with no
    session, since there is no tenant data on that page to isolate."""
    client = TestClient(app)
    resp = client.get("/")
    assert resp.status_code == 200


def test_logout_clears_session(monkeypatch):
    client = _logged_in_client(monkeypatch)
    assert client.get("/your-data").status_code == 200

    client.post("/logout")
    after = client.get("/your-data", follow_redirects=False)
    assert after.status_code == 303
    assert after.headers["location"] == "/login"


def test_your_data_shows_empty_state_when_nothing_captured(monkeypatch, tmp_path):
    monkeypatch.setattr(store, "RAW_DIR", tmp_path)  # empty dir — nothing captured yet
    client = _logged_in_client(monkeypatch)
    resp = client.get("/your-data")
    assert resp.status_code == 200
    assert "Nothing captured yet" in resp.text


def test_your_data_shows_real_captured_summary(monkeypatch, tmp_path):
    _seed_raw_dir(tmp_path)
    monkeypatch.setattr(store, "RAW_DIR", tmp_path)

    client = _logged_in_client(monkeypatch)
    resp = client.get("/your-data")
    assert resp.status_code == 200
    assert "120" in resp.text  # total covers, read back through src/store.py


def test_export_bom_returns_csv_of_the_real_captured_data(monkeypatch, tmp_path):
    _seed_raw_dir(tmp_path)
    monkeypatch.setattr(store, "RAW_DIR", tmp_path)

    client = _logged_in_client(monkeypatch)
    resp = client.get("/your-data/export/bom")
    assert resp.status_code == 200
    assert resp.headers["content-type"].startswith("text/csv")
    assert 'filename="bom.csv"' in resp.headers["content-disposition"]
    assert "Burger" in resp.text


def test_export_sales_returns_csv_of_the_real_captured_data(monkeypatch, tmp_path):
    _seed_raw_dir(tmp_path)
    monkeypatch.setattr(store, "RAW_DIR", tmp_path)

    client = _logged_in_client(monkeypatch)
    resp = client.get("/your-data/export/sales")
    assert resp.status_code == 200
    assert 'filename="sales_export.csv"' in resp.headers["content-disposition"]
    assert "120" in resp.text


def test_your_data_period_renders_as_plain_date_not_timestamp(monkeypatch, tmp_path):
    """period_start/period_end round-trip through Parquet/DuckDB as Timestamps; the page must
    show a plain date ("2026-06-01"), not a machine timestamp ("2026-06-01 00:00:00") on this
    trust surface (W2_review.md MINOR-2)."""
    _seed_raw_dir(tmp_path)
    monkeypatch.setattr(store, "RAW_DIR", tmp_path)

    client = _logged_in_client(monkeypatch)
    resp = client.get("/your-data")
    assert resp.status_code == 200
    assert "2026-06-01" in resp.text
    assert "00:00:00" not in resp.text


def test_export_unknown_leg_returns_404(monkeypatch):
    client = _logged_in_client(monkeypatch)
    resp = client.get("/your-data/export/prices")
    assert resp.status_code == 404


def test_export_missing_data_returns_404_not_a_crash(monkeypatch, tmp_path):
    monkeypatch.setattr(store, "RAW_DIR", tmp_path)  # empty dir
    client = _logged_in_client(monkeypatch)
    resp = client.get("/your-data/export/bom")
    assert resp.status_code == 404
    assert "Traceback" not in resp.text
