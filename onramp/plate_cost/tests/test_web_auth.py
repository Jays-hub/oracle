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

from schemas import BomRow, PriceObservationRow, SalesExportRow
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
_PRICE_ROW = PriceObservationRow(
    ingredient_id="i1", ingredient_name="beef", unit_price=4.5,
    source_invoice="inv-1", observed_date="2026-06-05",
)


def _seed_raw_dir(tmp_path):
    pd.DataFrame([_BOM_ROW.model_dump()]).to_parquet(tmp_path / "bom.parquet", index=False, engine="pyarrow")
    pd.DataFrame([_SALES_ROW.model_dump()]).to_parquet(
        tmp_path / "sales_export.parquet", index=False, engine="pyarrow"
    )


def _seed_price_observations(tmp_path):
    pd.DataFrame([_PRICE_ROW.model_dump()]).to_parquet(
        tmp_path / "price_observations.parquet", index=False, engine="pyarrow"
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
        ("get", "/your-data/export/prices", {}),
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
    resp = client.get("/your-data/export/nonexistent")
    assert resp.status_code == 404


def test_export_missing_data_returns_404_not_a_crash(monkeypatch, tmp_path):
    monkeypatch.setattr(store, "RAW_DIR", tmp_path)  # empty dir
    client = _logged_in_client(monkeypatch)
    resp = client.get("/your-data/export/bom")
    assert resp.status_code == 404
    assert "Traceback" not in resp.text


def test_your_data_shows_firewall_explanation_even_with_no_data(monkeypatch, tmp_path):
    """The firewall/trust story (W4) is static and shown regardless of capture state — it costs
    nothing to be honest about the hidden-oracle wall before an operator has uploaded anything."""
    monkeypatch.setattr(store, "RAW_DIR", tmp_path)  # empty dir
    client = _logged_in_client(monkeypatch)
    resp = client.get("/your-data")
    assert resp.status_code == 200
    assert "What we never touch" in resp.text


def test_your_data_omits_price_leg_and_export_link_when_no_invoices_captured(monkeypatch, tmp_path):
    _seed_raw_dir(tmp_path)  # BOM + sales only, no price_observations.parquet
    monkeypatch.setattr(store, "RAW_DIR", tmp_path)

    client = _logged_in_client(monkeypatch)
    resp = client.get("/your-data")
    assert resp.status_code == 200
    assert "Not connected yet" in resp.text
    assert "/your-data/export/prices" not in resp.text


def test_your_data_shows_price_leg_when_invoices_captured(monkeypatch, tmp_path):
    _seed_raw_dir(tmp_path)
    _seed_price_observations(tmp_path)
    monkeypatch.setattr(store, "RAW_DIR", tmp_path)

    client = _logged_in_client(monkeypatch)
    resp = client.get("/your-data")
    assert resp.status_code == 200
    assert "observation" in resp.text
    assert "/your-data/export/prices" in resp.text


def test_your_data_shows_whats_next_bridge_panel(monkeypatch, tmp_path):
    _seed_raw_dir(tmp_path)
    monkeypatch.setattr(store, "RAW_DIR", tmp_path)

    client = _logged_in_client(monkeypatch)
    resp = client.get("/your-data")
    assert resp.status_code == 200
    assert "What this unlocks next" in resp.text


def test_export_prices_returns_csv_of_the_real_captured_data(monkeypatch, tmp_path):
    _seed_raw_dir(tmp_path)
    _seed_price_observations(tmp_path)
    monkeypatch.setattr(store, "RAW_DIR", tmp_path)

    client = _logged_in_client(monkeypatch)
    resp = client.get("/your-data/export/prices")
    assert resp.status_code == 200
    assert resp.headers["content-type"].startswith("text/csv")
    assert 'filename="price_observations.csv"' in resp.headers["content-disposition"]
    assert "inv-1" in resp.text


def test_export_missing_prices_returns_404_not_a_crash(monkeypatch, tmp_path):
    _seed_raw_dir(tmp_path)  # BOM + sales exist, but no price_observations.parquet
    monkeypatch.setattr(store, "RAW_DIR", tmp_path)

    client = _logged_in_client(monkeypatch)
    resp = client.get("/your-data/export/prices")
    assert resp.status_code == 404
    assert "Traceback" not in resp.text


def test_your_data_shows_price_leg_and_export_when_only_invoices_captured(monkeypatch, tmp_path):
    """W4_review.md MAJOR-1 regression: an operator who has captured invoice prices but not yet
    BOM/sales must see that leg (and be able to export it), not a false "Nothing captured yet"
    that contradicts the firewall section's own claim that we hold their invoice prices."""
    _seed_price_observations(tmp_path)  # price leg only — no bom.parquet/sales_export.parquet
    monkeypatch.setattr(store, "RAW_DIR", tmp_path)

    client = _logged_in_client(monkeypatch)
    resp = client.get("/your-data")
    assert resp.status_code == 200
    assert "Nothing captured yet" not in resp.text
    assert "observation" in resp.text
    assert "/your-data/export/prices" in resp.text
    # No BOM/sales means no counts section and no bridge panel (its copy specifically claims
    # "you've already given us the sales history and recipes," which would be false here).
    assert "What this unlocks next" not in resp.text


def test_your_data_degrades_price_leg_without_crashing_when_price_file_corrupt(monkeypatch, tmp_path):
    """W4_review.md MINOR-1 regression: a present-but-unreadable price_observations.parquet must
    degrade that one leg to an honest "temporarily unavailable," not 500 the whole trust page and
    not be silently reported as "not connected yet" (which would be a different, false claim)."""
    _seed_raw_dir(tmp_path)
    (tmp_path / "price_observations.parquet").write_bytes(b"not a real parquet file")
    monkeypatch.setattr(store, "RAW_DIR", tmp_path)

    client = _logged_in_client(monkeypatch)
    resp = client.get("/your-data")
    assert resp.status_code == 200
    assert "Temporarily unavailable" in resp.text
    assert "Not connected yet" not in resp.text
    assert "/your-data/export/prices" not in resp.text  # can't offer an export that will fail


def test_your_data_returns_calm_503_when_bom_read_fails_unexpectedly(monkeypatch, tmp_path):
    """W4_review.md MINOR-1 regression: /your-data now wraps build_your_data_summary() the same
    way grid()/insights() already wrap their compute — a corrupt BOM/sales file must fail legibly
    (calm error page + correlation id), never a bare crash.

    Logs in against the real (clean) store first, with follow_redirects=False, so the login
    step itself never routes through /your-data before the corrupt file is in place — unlike
    _logged_in_client(), which follows the post-login redirect straight into /your-data.
    """
    username, password = _set_credential(monkeypatch)
    client = TestClient(app)
    client.post("/login", data={"username": username, "password": password}, follow_redirects=False)

    (tmp_path / "bom.parquet").write_bytes(b"not a real parquet file")
    monkeypatch.setattr(store, "RAW_DIR", tmp_path)

    resp = client.get("/your-data")
    assert resp.status_code == 503
    assert "Traceback" not in resp.text


def test_export_prices_returns_503_not_a_crash_when_price_file_corrupt(monkeypatch, tmp_path):
    """W4_review.md MINOR-1 regression, export-route side: a corrupt (present, unreadable) file
    is a different failure than "never captured" and must fail legibly, not with a bare 500."""
    (tmp_path / "price_observations.parquet").write_bytes(b"not a real parquet file")
    monkeypatch.setattr(store, "RAW_DIR", tmp_path)

    client = _logged_in_client(monkeypatch)
    resp = client.get("/your-data/export/prices")
    assert resp.status_code == 503
    assert "Traceback" not in resp.text
