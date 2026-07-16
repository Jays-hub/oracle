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
from sqlalchemy import select

from schemas import BomRow, PriceObservationRow, SalesExportRow
from src import store
from src.auth.credentials import hash_password
from src.auth.service import create_account
from src.db.models import Credential, Membership, Restaurant, User
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


def _seed_raw_dir(tenant_dir):
    """``tenant_dir`` must already be the tenant's own subdirectory (``tmp_path /
    restaurant_id``, W9) -- callers only learn the real restaurant_id after logging in
    (``_logged_in_client``), since it's a DB-issued id, not a fixed test constant."""
    tenant_dir.mkdir(parents=True, exist_ok=True)
    pd.DataFrame([_BOM_ROW.model_dump()]).to_parquet(tenant_dir / "bom.parquet", index=False, engine="pyarrow")
    pd.DataFrame([_SALES_ROW.model_dump()]).to_parquet(
        tenant_dir / "sales_export.parquet", index=False, engine="pyarrow"
    )


def _seed_raw_dir_as(tenant_dir, dish_name, count):
    """Like ``_seed_raw_dir`` but with a caller-chosen dish name/count, so two tenants' seeded
    data can be told apart in a response body (W9 tenant-isolation test)."""
    tenant_dir.mkdir(parents=True, exist_ok=True)
    bom_row = BomRow(
        dish_id=dish_name.lower(), dish_name=dish_name, ingredient_id="i1", ingredient_name="beef",
        qty=6.0, recipe_unit="oz", canonical_unit="oz", yield_factor=0.9,
    )
    sales_row = SalesExportRow(
        dish_name=dish_name, count=count, period_start="2026-06-01", period_end="2026-06-07",
    )
    pd.DataFrame([bom_row.model_dump()]).to_parquet(tenant_dir / "bom.parquet", index=False, engine="pyarrow")
    pd.DataFrame([sales_row.model_dump()]).to_parquet(
        tenant_dir / "sales_export.parquet", index=False, engine="pyarrow"
    )


def _seed_price_observations(tenant_dir):
    tenant_dir.mkdir(parents=True, exist_ok=True)
    pd.DataFrame([_PRICE_ROW.model_dump()]).to_parquet(
        tenant_dir / "price_observations.parquet", index=False, engine="pyarrow"
    )


def _seed_account(db_sessionmaker, email="chef@example.com", password="s3cret123"):
    """Returns (email, password, restaurant_id) -- the real, DB-issued restaurant_id is needed
    before seeding data/raw/<restaurant_id>/ (W9), since that id doesn't exist until this
    account's Restaurant row does."""
    db = db_sessionmaker()
    try:
        create_account(db, "Test Kitchen", email, password)
        restaurant_id = db.scalars(select(Restaurant)).one().id
    finally:
        db.close()
    return email, password, restaurant_id


def _seed_second_tenant(db_sessionmaker, email, password):
    """Creates a second restaurant + user + credential + membership directly against the DB
    models, bypassing ``create_account``'s single-restaurant fence.

    That fence is deliberate and still in force post-W9 (``src/auth/service.py::create_account``
    docstring): lifting it is its own, separately-reviewable follow-up
    (``docs/phase_decisions/W9.md`` "Explicitly Deferred"), not something this test should do by
    calling the real signup path. What W9 actually changed is the *seam read path* -- whether two
    tenants' `data/raw/` reads and web sessions stay isolated once two restaurants exist -- which
    is exactly what this helper needs to set up to prove, independent of whether onboarding a
    second live account is allowed yet."""
    db = db_sessionmaker()
    try:
        restaurant = Restaurant(name="Second Kitchen")
        user = User(email=email)
        db.add_all([restaurant, user])
        db.flush()
        db.add(Credential(user_id=user.id, password_hash=hash_password(password)))
        db.add(Membership(user_id=user.id, restaurant_id=restaurant.id, role="owner"))
        db.commit()
        return restaurant.id
    finally:
        db.close()


def _logged_in_client(db_sessionmaker) -> tuple[TestClient, str]:
    """Returns (client, restaurant_id). Seeding data/raw/<restaurant_id>/ can happen either
    before or after this call -- login itself never touches the seam -- but callers need the id
    either way to know where to seed (W9)."""
    email, password, restaurant_id = _seed_account(db_sessionmaker)
    client = TestClient(app)
    resp = client.post(
        "/login", data={"email": email, "password": password}, follow_redirects=True,
    )
    assert resp.status_code == 200  # landed on /your-data after the redirect
    return client, restaurant_id


def test_login_form_returns_200():
    client = TestClient(app)
    resp = client.get("/login")
    assert resp.status_code == 200
    assert "email" in resp.text and "password" in resp.text


def test_correct_login_redirects_to_your_data(db_sessionmaker):
    email, password, _ = _seed_account(db_sessionmaker)
    client = TestClient(app)
    resp = client.post(
        "/login", data={"email": email, "password": password}, follow_redirects=False,
    )
    assert resp.status_code == 303
    assert resp.headers["location"] == "/your-data"


def test_wrong_password_returns_401_with_error_and_grants_no_session(db_sessionmaker):
    email, _, _ = _seed_account(db_sessionmaker)
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
    client, _ = _logged_in_client(db_sessionmaker)
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
    client, _ = _logged_in_client(db_sessionmaker)
    resp = client.get("/your-data")
    assert resp.status_code == 200
    assert "Nothing captured yet" in resp.text


def test_your_data_shows_real_captured_summary(db_sessionmaker, monkeypatch, tmp_path):
    monkeypatch.setattr(store, "RAW_DIR", tmp_path)
    client, restaurant_id = _logged_in_client(db_sessionmaker)
    _seed_raw_dir(tmp_path / restaurant_id)

    resp = client.get("/your-data")
    assert resp.status_code == 200
    assert "120" in resp.text  # total covers, read back through src/store.py


def test_export_bom_returns_csv_of_the_real_captured_data(db_sessionmaker, monkeypatch, tmp_path):
    monkeypatch.setattr(store, "RAW_DIR", tmp_path)
    client, restaurant_id = _logged_in_client(db_sessionmaker)
    _seed_raw_dir(tmp_path / restaurant_id)

    resp = client.get("/your-data/export/bom")
    assert resp.status_code == 200
    assert resp.headers["content-type"].startswith("text/csv")
    assert 'filename="bom.csv"' in resp.headers["content-disposition"]
    assert "Burger" in resp.text


def test_export_sales_returns_csv_of_the_real_captured_data(db_sessionmaker, monkeypatch, tmp_path):
    monkeypatch.setattr(store, "RAW_DIR", tmp_path)
    client, restaurant_id = _logged_in_client(db_sessionmaker)
    _seed_raw_dir(tmp_path / restaurant_id)

    resp = client.get("/your-data/export/sales")
    assert resp.status_code == 200
    assert 'filename="sales_export.csv"' in resp.headers["content-disposition"]
    assert "120" in resp.text


def test_your_data_period_renders_as_plain_date_not_timestamp(db_sessionmaker, monkeypatch, tmp_path):
    """period_start/period_end round-trip through Parquet/DuckDB as Timestamps; the page must
    show a plain date ("2026-06-01"), not a machine timestamp ("2026-06-01 00:00:00") on this
    trust surface (W2_review.md MINOR-2)."""
    monkeypatch.setattr(store, "RAW_DIR", tmp_path)
    client, restaurant_id = _logged_in_client(db_sessionmaker)
    _seed_raw_dir(tmp_path / restaurant_id)

    resp = client.get("/your-data")
    assert resp.status_code == 200
    assert "2026-06-01" in resp.text
    assert "00:00:00" not in resp.text


def test_your_data_and_dishes_never_cross_tenants_for_two_real_accounts(db_sessionmaker, monkeypatch, tmp_path):
    """W9's actual promise, composed end-to-end: two real, DB-issued accounts, each with their own
    captured data under data/raw/<restaurant_id>/, and tenant B's session must never surface tenant
    A's dish names or covers count on /your-data or /dishes, and vice versa. test_store.py and
    forecasting/tests/test_loader.py already prove the store/loader read is scoped in isolation;
    this proves the whole session -> identity.restaurant_id -> store composition holds at the real
    request boundary (W9_review.md MINOR-3 -- a store unit test can't catch a route that threads
    the wrong id)."""
    monkeypatch.setattr(store, "RAW_DIR", tmp_path)

    email_a, password_a, restaurant_id_a = _seed_account(db_sessionmaker, email="a@example.com")
    email_b, password_b = "b@example.com", "s3cret123"
    restaurant_id_b = _seed_second_tenant(db_sessionmaker, email_b, password_b)
    assert restaurant_id_a != restaurant_id_b

    _seed_raw_dir_as(tmp_path / restaurant_id_a, "Tenant A Burger", 111)
    _seed_raw_dir_as(tmp_path / restaurant_id_b, "Tenant B Salad", 222)

    client_a = TestClient(app)
    client_a.post("/login", data={"email": email_a, "password": password_a}, follow_redirects=True)
    client_b = TestClient(app)
    client_b.post("/login", data={"email": email_b, "password": password_b}, follow_redirects=True)

    # /your-data shows aggregate counts (covers), not dish names -- "111"/"222" is the marker here.
    resp_a = client_a.get("/your-data")
    assert resp_a.status_code == 200
    assert "111" in resp_a.text
    assert "222" not in resp_a.text

    resp_b = client_b.get("/your-data")
    assert resp_b.status_code == 200
    assert "222" in resp_b.text
    assert "111" not in resp_b.text

    dishes_a = client_a.get("/dishes")
    assert dishes_a.status_code == 200
    assert "Tenant A Burger" in dishes_a.text
    assert "Tenant B Salad" not in dishes_a.text

    dishes_b = client_b.get("/dishes")
    assert dishes_b.status_code == 200
    assert "Tenant B Salad" in dishes_b.text
    assert "Tenant A Burger" not in dishes_b.text


def test_export_unknown_leg_returns_404(db_sessionmaker):
    client, _ = _logged_in_client(db_sessionmaker)
    resp = client.get("/your-data/export/nonexistent")
    assert resp.status_code == 404


def test_export_missing_data_returns_404_not_a_crash(db_sessionmaker, monkeypatch, tmp_path):
    monkeypatch.setattr(store, "RAW_DIR", tmp_path)  # empty dir
    client, _ = _logged_in_client(db_sessionmaker)
    resp = client.get("/your-data/export/bom")
    assert resp.status_code == 404
    assert "Traceback" not in resp.text


def test_your_data_shows_firewall_explanation_even_with_no_data(db_sessionmaker, monkeypatch, tmp_path):
    """The firewall/trust story (W4) is static and shown regardless of capture state — it costs
    nothing to be honest about the hidden-oracle wall before an operator has uploaded anything."""
    monkeypatch.setattr(store, "RAW_DIR", tmp_path)  # empty dir
    client, _ = _logged_in_client(db_sessionmaker)
    resp = client.get("/your-data")
    assert resp.status_code == 200
    assert "What we never touch" in resp.text


def test_your_data_omits_price_leg_and_export_link_when_no_invoices_captured(db_sessionmaker, monkeypatch, tmp_path):
    monkeypatch.setattr(store, "RAW_DIR", tmp_path)
    client, restaurant_id = _logged_in_client(db_sessionmaker)
    _seed_raw_dir(tmp_path / restaurant_id)  # BOM + sales only, no price_observations.parquet

    resp = client.get("/your-data")
    assert resp.status_code == 200
    assert "Not connected yet" in resp.text
    assert "/your-data/export/prices" not in resp.text


def test_your_data_shows_price_leg_when_invoices_captured(db_sessionmaker, monkeypatch, tmp_path):
    monkeypatch.setattr(store, "RAW_DIR", tmp_path)
    client, restaurant_id = _logged_in_client(db_sessionmaker)
    _seed_raw_dir(tmp_path / restaurant_id)
    _seed_price_observations(tmp_path / restaurant_id)

    resp = client.get("/your-data")
    assert resp.status_code == 200
    assert "observation" in resp.text
    assert "/your-data/export/prices" in resp.text


def test_your_data_shows_whats_next_bridge_panel(db_sessionmaker, monkeypatch, tmp_path):
    monkeypatch.setattr(store, "RAW_DIR", tmp_path)
    client, restaurant_id = _logged_in_client(db_sessionmaker)
    _seed_raw_dir(tmp_path / restaurant_id)

    resp = client.get("/your-data")
    assert resp.status_code == 200
    assert "What this unlocks next" in resp.text


def test_export_prices_returns_csv_of_the_real_captured_data(db_sessionmaker, monkeypatch, tmp_path):
    monkeypatch.setattr(store, "RAW_DIR", tmp_path)
    client, restaurant_id = _logged_in_client(db_sessionmaker)
    _seed_raw_dir(tmp_path / restaurant_id)
    _seed_price_observations(tmp_path / restaurant_id)

    resp = client.get("/your-data/export/prices")
    assert resp.status_code == 200
    assert resp.headers["content-type"].startswith("text/csv")
    assert 'filename="price_observations.csv"' in resp.headers["content-disposition"]
    assert "inv-1" in resp.text


def test_export_missing_prices_returns_404_not_a_crash(db_sessionmaker, monkeypatch, tmp_path):
    monkeypatch.setattr(store, "RAW_DIR", tmp_path)
    client, restaurant_id = _logged_in_client(db_sessionmaker)
    _seed_raw_dir(tmp_path / restaurant_id)  # BOM + sales exist, but no price_observations.parquet

    resp = client.get("/your-data/export/prices")
    assert resp.status_code == 404
    assert "Traceback" not in resp.text


def test_your_data_shows_price_leg_and_export_when_only_invoices_captured(db_sessionmaker, monkeypatch, tmp_path):
    """W4_review.md MAJOR-1 regression: an operator who has captured invoice prices but not yet
    BOM/sales must see that leg (and be able to export it), not a false "Nothing captured yet"
    that contradicts the firewall section's own claim that we hold their invoice prices."""
    monkeypatch.setattr(store, "RAW_DIR", tmp_path)
    client, restaurant_id = _logged_in_client(db_sessionmaker)
    _seed_price_observations(tmp_path / restaurant_id)  # price leg only — no bom.parquet/sales_export.parquet

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
    monkeypatch.setattr(store, "RAW_DIR", tmp_path)
    client, restaurant_id = _logged_in_client(db_sessionmaker)
    _seed_raw_dir(tmp_path / restaurant_id)
    (tmp_path / restaurant_id / "price_observations.parquet").write_bytes(b"not a real parquet file")

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
    email, password, restaurant_id = _seed_account(db_sessionmaker)
    client = TestClient(app)
    client.post("/login", data={"email": email, "password": password}, follow_redirects=False)

    tenant_dir = tmp_path / restaurant_id
    tenant_dir.mkdir(parents=True)
    (tenant_dir / "bom.parquet").write_bytes(b"not a real parquet file")
    monkeypatch.setattr(store, "RAW_DIR", tmp_path)

    resp = client.get("/your-data")
    assert resp.status_code == 503
    assert "Traceback" not in resp.text


def test_export_prices_returns_503_not_a_crash_when_price_file_corrupt(db_sessionmaker, monkeypatch, tmp_path):
    """W4_review.md MINOR-1 regression, export-route side: a corrupt (present, unreadable) file
    is a different failure than "never captured" and must fail legibly, not with a bare 500."""
    monkeypatch.setattr(store, "RAW_DIR", tmp_path)
    client, restaurant_id = _logged_in_client(db_sessionmaker)
    tenant_dir = tmp_path / restaurant_id
    tenant_dir.mkdir(parents=True)
    (tenant_dir / "price_observations.parquet").write_bytes(b"not a real parquet file")

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
    email, _old_password, _ = _seed_account(db_sessionmaker, password="old-password-1")
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

    email, _, _ = _seed_account(db_sessionmaker)
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

    email, _, _ = _seed_account(db_sessionmaker, email="real@example.com")
    client = TestClient(app)

    with caplog.at_level("INFO", logger="web.app"):
        known = client.post("/reset-password", data={"email": email})
        unknown = client.post("/reset-password", data={"email": "nobody@example.com"})

    assert known.status_code == unknown.status_code == 200
    assert known.text == unknown.text
    assert not any("/reset-password/" in line for line in caplog.messages)
