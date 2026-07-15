"""Tests for the W5 DB-backed login gate and the /your-data page + export.

Covers: correct/incorrect login against a real seeded account, every protected route
(/your-data, /upload, /confirm, the export endpoints, /invoice/*, /insights) redirects an
unauthenticated request to /login rather than serving any tenant data, logout revokes the
session server-side (not just clearing a client cookie — the point of a DB-backed session), and
/your-data reads real captured data back through src/store.py, including the empty state when
nothing has been captured yet.

Each test builds its own TestClient rather than sharing one module-level instance (unlike
test_web.py/test_web_upload.py) because these tests specifically exercise session-cookie state,
which must not leak between tests. The app DB itself is isolated per test by the autouse
db_sessionmaker fixture in conftest.py.
"""
import pandas as pd
import pytest
from fastapi.testclient import TestClient

from schemas import BomRow, PriceObservationRow, SalesExportRow
from src import store
from src.auth.service import create_account
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


def _seed_account(db_sessionmaker, email="chef@example.com", password="s3cret123"):
    db = db_sessionmaker()
    try:
        create_account(db, "Test Kitchen", email, password)
    finally:
        db.close()
    return email, password


def _logged_in_client(db_sessionmaker) -> TestClient:
    email, password = _seed_account(db_sessionmaker)
    client = TestClient(app)
    resp = client.post(
        "/login", data={"email": email, "password": password}, follow_redirects=True,
    )
    assert resp.status_code == 200  # landed on /your-data after the redirect
    return client


def test_login_form_returns_200():
    client = TestClient(app)
    resp = client.get("/login")
    assert resp.status_code == 200
    assert "email" in resp.text and "password" in resp.text


def test_correct_login_redirects_to_your_data(db_sessionmaker):
    email, password = _seed_account(db_sessionmaker)
    client = TestClient(app)
    resp = client.post(
        "/login", data={"email": email, "password": password}, follow_redirects=False,
    )
    assert resp.status_code == 303
    assert resp.headers["location"] == "/your-data"


def test_wrong_password_returns_401_with_error_and_grants_no_session(db_sessionmaker):
    email, _ = _seed_account(db_sessionmaker)
    client = TestClient(app)
    resp = client.post("/login", data={"email": email, "password": "wrong"})
    assert resp.status_code == 401
    assert "Incorrect email or password" in resp.text

    protected = client.get("/your-data", follow_redirects=False)
    assert protected.status_code == 303
    assert protected.headers["location"] == "/login"


def test_login_fails_for_unknown_account():
    client = TestClient(app)
    resp = client.post("/login", data={"email": "nobody@example.com", "password": "anything"})
    assert resp.status_code == 401


@pytest.mark.parametrize(
    "method, path, kwargs",
    [
        ("get", "/your-data", {}),
        ("get", "/upload", {}),
        ("post", "/confirm", {"data": {"staged_upload_id": "x"}}),
        ("get", "/your-data/export/bom", {}),
        ("get", "/your-data/export/sales", {}),
        ("get", "/your-data/export/prices", {}),
        ("get", "/invoice/upload", {}),
        ("post", "/invoice/confirm", {"data": {"staged_upload_id": "x"}}),
        ("get", "/insights", {}),
        ("get", "/menu-prices", {}),
        ("post", "/menu-prices", {"data": {"price__burger": "12.00"}}),
        ("get", "/dishes", {}),
        ("get", "/dishes/burger", {}),
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


def test_logout_revokes_session_server_side(db_sessionmaker):
    """The point of a DB-backed session over W2's client-signed cookie: logout must actually
    revoke the sessions-table row, not just clear a cookie the server never tracked."""
    client = _logged_in_client(db_sessionmaker)
    cookie_value = client.cookies.get("onramp_session")
    assert cookie_value is not None

    client.post("/logout")
    after = client.get("/your-data", follow_redirects=False)
    assert after.status_code == 303
    assert after.headers["location"] == "/login"

    # Even presenting the OLD cookie value again must not authenticate — it was revoked, not
    # merely forgotten client-side.
    stale_client = TestClient(app)
    stale_client.cookies.set("onramp_session", cookie_value)
    stale_resp = stale_client.get("/your-data", follow_redirects=False)
    assert stale_resp.status_code == 303
    assert stale_resp.headers["location"] == "/login"


def test_your_data_shows_empty_state_when_nothing_captured(db_sessionmaker, monkeypatch, tmp_path):
    monkeypatch.setattr(store, "RAW_DIR", tmp_path)  # empty dir — nothing captured yet
    client = _logged_in_client(db_sessionmaker)
    resp = client.get("/your-data")
    assert resp.status_code == 200
    assert "Nothing captured yet" in resp.text


def test_your_data_shows_real_captured_summary(db_sessionmaker, monkeypatch, tmp_path):
    _seed_raw_dir(tmp_path)
    monkeypatch.setattr(store, "RAW_DIR", tmp_path)

    client = _logged_in_client(db_sessionmaker)
    resp = client.get("/your-data")
    assert resp.status_code == 200
    assert "120" in resp.text  # total covers, read back through src/store.py


def test_export_bom_returns_csv_of_the_real_captured_data(db_sessionmaker, monkeypatch, tmp_path):
    _seed_raw_dir(tmp_path)
    monkeypatch.setattr(store, "RAW_DIR", tmp_path)

    client = _logged_in_client(db_sessionmaker)
    resp = client.get("/your-data/export/bom")
    assert resp.status_code == 200
    assert resp.headers["content-type"].startswith("text/csv")
    assert 'filename="bom.csv"' in resp.headers["content-disposition"]
    assert "Burger" in resp.text


def test_export_sales_returns_csv_of_the_real_captured_data(db_sessionmaker, monkeypatch, tmp_path):
    _seed_raw_dir(tmp_path)
    monkeypatch.setattr(store, "RAW_DIR", tmp_path)

    client = _logged_in_client(db_sessionmaker)
    resp = client.get("/your-data/export/sales")
    assert resp.status_code == 200
    assert 'filename="sales_export.csv"' in resp.headers["content-disposition"]
    assert "120" in resp.text


def test_your_data_period_renders_as_plain_date_not_timestamp(db_sessionmaker, monkeypatch, tmp_path):
    """period_start/period_end round-trip through Parquet/DuckDB as Timestamps; the page must
    show a plain date ("2026-06-01"), not a machine timestamp ("2026-06-01 00:00:00") on this
    trust surface (W2_review.md MINOR-2)."""
    _seed_raw_dir(tmp_path)
    monkeypatch.setattr(store, "RAW_DIR", tmp_path)

    client = _logged_in_client(db_sessionmaker)
    resp = client.get("/your-data")
    assert resp.status_code == 200
    assert "2026-06-01" in resp.text
    assert "00:00:00" not in resp.text


def test_export_unknown_leg_returns_404(db_sessionmaker):
    client = _logged_in_client(db_sessionmaker)
    resp = client.get("/your-data/export/nonexistent")
    assert resp.status_code == 404


def test_export_missing_data_returns_404_not_a_crash(db_sessionmaker, monkeypatch, tmp_path):
    monkeypatch.setattr(store, "RAW_DIR", tmp_path)  # empty dir
    client = _logged_in_client(db_sessionmaker)
    resp = client.get("/your-data/export/bom")
    assert resp.status_code == 404
    assert "Traceback" not in resp.text


def test_your_data_shows_firewall_explanation_even_with_no_data(db_sessionmaker, monkeypatch, tmp_path):
    """The firewall/trust story (W4) is static and shown regardless of capture state — it costs
    nothing to be honest about the hidden-oracle wall before an operator has uploaded anything."""
    monkeypatch.setattr(store, "RAW_DIR", tmp_path)  # empty dir
    client = _logged_in_client(db_sessionmaker)
    resp = client.get("/your-data")
    assert resp.status_code == 200
    assert "What we never touch" in resp.text


def test_your_data_omits_price_leg_and_export_link_when_no_invoices_captured(db_sessionmaker, monkeypatch, tmp_path):
    _seed_raw_dir(tmp_path)  # BOM + sales only, no price_observations.parquet
    monkeypatch.setattr(store, "RAW_DIR", tmp_path)

    client = _logged_in_client(db_sessionmaker)
    resp = client.get("/your-data")
    assert resp.status_code == 200
    assert "Not connected yet" in resp.text
    assert "/your-data/export/prices" not in resp.text


def test_your_data_shows_price_leg_when_invoices_captured(db_sessionmaker, monkeypatch, tmp_path):
    _seed_raw_dir(tmp_path)
    _seed_price_observations(tmp_path)
    monkeypatch.setattr(store, "RAW_DIR", tmp_path)

    client = _logged_in_client(db_sessionmaker)
    resp = client.get("/your-data")
    assert resp.status_code == 200
    assert "observation" in resp.text
    assert "/your-data/export/prices" in resp.text


def test_your_data_shows_whats_next_bridge_panel(db_sessionmaker, monkeypatch, tmp_path):
    _seed_raw_dir(tmp_path)
    monkeypatch.setattr(store, "RAW_DIR", tmp_path)

    client = _logged_in_client(db_sessionmaker)
    resp = client.get("/your-data")
    assert resp.status_code == 200
    assert "What this unlocks next" in resp.text


def test_export_prices_returns_csv_of_the_real_captured_data(db_sessionmaker, monkeypatch, tmp_path):
    _seed_raw_dir(tmp_path)
    _seed_price_observations(tmp_path)
    monkeypatch.setattr(store, "RAW_DIR", tmp_path)

    client = _logged_in_client(db_sessionmaker)
    resp = client.get("/your-data/export/prices")
    assert resp.status_code == 200
    assert resp.headers["content-type"].startswith("text/csv")
    assert 'filename="price_observations.csv"' in resp.headers["content-disposition"]
    assert "inv-1" in resp.text


def test_export_missing_prices_returns_404_not_a_crash(db_sessionmaker, monkeypatch, tmp_path):
    _seed_raw_dir(tmp_path)  # BOM + sales exist, but no price_observations.parquet
    monkeypatch.setattr(store, "RAW_DIR", tmp_path)

    client = _logged_in_client(db_sessionmaker)
    resp = client.get("/your-data/export/prices")
    assert resp.status_code == 404
    assert "Traceback" not in resp.text


def test_your_data_shows_price_leg_and_export_when_only_invoices_captured(db_sessionmaker, monkeypatch, tmp_path):
    """W4_review.md MAJOR-1 regression: an operator who has captured invoice prices but not yet
    BOM/sales must see that leg (and be able to export it), not a false "Nothing captured yet"
    that contradicts the firewall section's own claim that we hold their invoice prices."""
    _seed_price_observations(tmp_path)  # price leg only — no bom.parquet/sales_export.parquet
    monkeypatch.setattr(store, "RAW_DIR", tmp_path)

    client = _logged_in_client(db_sessionmaker)
    resp = client.get("/your-data")
    assert resp.status_code == 200
    assert "Nothing captured yet" not in resp.text
    assert "observation" in resp.text
    assert "/your-data/export/prices" in resp.text
    # No BOM/sales means no counts section and no bridge panel (its copy specifically claims
    # "you've already given us the sales history and recipes," which would be false here).
    assert "What this unlocks next" not in resp.text


def test_your_data_degrades_price_leg_without_crashing_when_price_file_corrupt(db_sessionmaker, monkeypatch, tmp_path):
    """W4_review.md MINOR-1 regression: a present-but-unreadable price_observations.parquet must
    degrade that one leg to an honest "temporarily unavailable," not 500 the whole trust page and
    not be silently reported as "not connected yet" (which would be a different, false claim)."""
    _seed_raw_dir(tmp_path)
    (tmp_path / "price_observations.parquet").write_bytes(b"not a real parquet file")
    monkeypatch.setattr(store, "RAW_DIR", tmp_path)

    client = _logged_in_client(db_sessionmaker)
    resp = client.get("/your-data")
    assert resp.status_code == 200
    assert "Temporarily unavailable" in resp.text
    assert "Not connected yet" not in resp.text
    assert "/your-data/export/prices" not in resp.text  # can't offer an export that will fail


def test_your_data_returns_calm_503_when_bom_read_fails_unexpectedly(db_sessionmaker, monkeypatch, tmp_path):
    """W4_review.md MINOR-1 regression: /your-data now wraps build_your_data_summary() the same
    way grid()/insights() already wrap their compute — a corrupt BOM/sales file must fail legibly
    (calm error page + correlation id), never a bare crash.

    Logs in against the real (clean) store first, with follow_redirects=False, so the login
    step itself never routes through /your-data before the corrupt file is in place — unlike
    _logged_in_client(), which follows the post-login redirect straight into /your-data.
    """
    email, password = _seed_account(db_sessionmaker)
    client = TestClient(app)
    client.post("/login", data={"email": email, "password": password}, follow_redirects=False)

    (tmp_path / "bom.parquet").write_bytes(b"not a real parquet file")
    monkeypatch.setattr(store, "RAW_DIR", tmp_path)

    resp = client.get("/your-data")
    assert resp.status_code == 503
    assert "Traceback" not in resp.text


def test_export_prices_returns_503_not_a_crash_when_price_file_corrupt(db_sessionmaker, monkeypatch, tmp_path):
    """W4_review.md MINOR-1 regression, export-route side: a corrupt (present, unreadable) file
    is a different failure than "never captured" and must fail legibly, not with a bare 500."""
    (tmp_path / "price_observations.parquet").write_bytes(b"not a real parquet file")
    monkeypatch.setattr(store, "RAW_DIR", tmp_path)

    client = _logged_in_client(db_sessionmaker)
    resp = client.get("/your-data/export/prices")
    assert resp.status_code == 503
    assert "Traceback" not in resp.text


def test_reset_password_form_returns_200():
    client = TestClient(app)
    resp = client.get("/reset-password")
    assert resp.status_code == 200
    assert "email" in resp.text


def test_reset_password_request_gives_identical_response_for_unknown_email(db_sessionmaker):
    """Never confirm or deny that an email has an account (enumeration defense)."""
    _seed_account(db_sessionmaker, email="real@example.com")
    client = TestClient(app)

    known = client.post("/reset-password", data={"email": "real@example.com"})
    unknown = client.post("/reset-password", data={"email": "nobody@example.com"})
    assert known.status_code == unknown.status_code == 200
    assert known.text == unknown.text


def test_full_password_reset_flow_via_http(db_sessionmaker, caplog):
    """End to end through the actual routes: request a reset, read the token off the log (W5's
    documented no-email-transport stand-in), submit a new password, log in with it."""
    email, _old_password = _seed_account(db_sessionmaker, password="old-password-1")
    client = TestClient(app)

    # Named explicitly (not just the root logger): some other test in the suite may have left
    # a specific logger's effective level elevated, which at_level("INFO") without a name
    # wouldn't reliably override (observed as an order-dependent flake in the full suite run).
    with caplog.at_level("INFO", logger="web.app"):
        client.post("/reset-password", data={"email": email})
    token = next(
        line.rsplit("/reset-password/", 1)[1]
        for line in caplog.messages
        if "/reset-password/" in line
    )

    form_resp = client.get(f"/reset-password/{token}")
    assert form_resp.status_code == 200

    submit_resp = client.post(
        f"/reset-password/{token}", data={"new_password": "new-password-2"}, follow_redirects=False,
    )
    assert submit_resp.status_code == 303
    assert submit_resp.headers["location"] == "/login"

    login_resp = client.post(
        "/login", data={"email": email, "password": "new-password-2"}, follow_redirects=False,
    )
    assert login_resp.status_code == 303


def test_reset_password_submit_rejects_invalid_token():
    client = TestClient(app)
    resp = client.post(
        "/reset-password/not-a-real-token", data={"new_password": "new-password-123"},
    )
    assert resp.status_code == 400
    assert "invalid" in resp.text.lower()


def test_reset_password_request_emails_the_link_and_stops_logging_the_raw_token_when_smtp_is_configured(
    db_sessionmaker, monkeypatch, caplog,
):
    """W7 (closes docs/phase_decisions/W5_review.md LOW-2): once real email transport exists,
    the raw reset token — a 1-hour bearer credential — must not also sit in the server log."""
    import smtplib

    sent: list[object] = []

    class _FakeSMTP:
        def __init__(self, host, port, timeout=None):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *exc):
            return False

        def starttls(self):
            pass

        def login(self, username, password):
            pass

        def send_message(self, message):
            sent.append(message)

    monkeypatch.setenv("ONRAMP_SMTP_HOST", "smtp.example.com")
    monkeypatch.setattr(smtplib, "SMTP", _FakeSMTP)

    email, _ = _seed_account(db_sessionmaker)
    client = TestClient(app)

    with caplog.at_level("INFO", logger="web.app"):
        resp = client.post("/reset-password", data={"email": email})

    assert resp.status_code == 200
    assert len(sent) == 1
    assert email in sent[0]["To"]
    assert not any("/reset-password/" in line for line in caplog.messages)


def test_reset_password_request_identical_response_when_smtp_configured_but_send_fails(
    db_sessionmaker, monkeypatch, caplog,
):
    """Regression for W7_review.md MAJOR-2: send_password_reset_email raises (by design) when
    SMTP is configured but the send fails; an unhandled raise used to 500 ONLY when the account
    existed (a non-existent email never calls the sender at all), an enumeration oracle. The
    route must now absorb the failure into the SAME response as the unknown-email path, and must
    not fall back to logging the raw token now that SMTP is (nominally) configured."""
    import smtplib

    class _FailingSMTP:
        def __init__(self, host, port, timeout=None):
            pass

        def __enter__(self):
            raise RuntimeError("connection refused")

        def __exit__(self, *exc):
            return False

    monkeypatch.setenv("ONRAMP_SMTP_HOST", "smtp.example.com")
    monkeypatch.setattr(smtplib, "SMTP", _FailingSMTP)

    email, _ = _seed_account(db_sessionmaker, email="real@example.com")
    client = TestClient(app)

    with caplog.at_level("INFO", logger="web.app"):
        known = client.post("/reset-password", data={"email": email})
        unknown = client.post("/reset-password", data={"email": "nobody@example.com"})

    assert known.status_code == unknown.status_code == 200
    assert known.text == unknown.text
    assert not any("/reset-password/" in line for line in caplog.messages)
