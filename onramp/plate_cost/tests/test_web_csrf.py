"""Tests for the W7 double-submit CSRF protection (web/csrf.py).

Every other test file in this suite bypasses CSRF by default (conftest.py's autouse
``_bypass_csrf_by_default``) so it can focus on its own concern — this file overrides that
bypass (same fixture name, defined here, per pytest's module-shadows-conftest rule) to exercise
the real enforcement end-to-end.
"""
import pytest
from fastapi.testclient import TestClient

from web.app import app
from web.csrf import COOKIE_NAME, FIELD_NAME


@pytest.fixture(autouse=True)
def _bypass_csrf_by_default():
    """Overrides conftest.py's autouse bypass — this file tests the real thing."""
    yield


def test_get_request_sets_a_csrf_cookie():
    client = TestClient(app)
    resp = client.get("/")
    assert resp.status_code == 200
    assert client.cookies.get(COOKIE_NAME) is not None


def test_csrf_cookie_is_httponly_and_not_readable_by_a_script():
    """The double-submit defense depends on this: a cross-site attacker's page can make the
    victim's browser SEND the cookie, but must never be able to READ its value to also put a
    matching value in a forged form field."""
    client = TestClient(app)
    resp = client.get("/")
    set_cookie = resp.headers.get("set-cookie", "")
    assert "httponly" in set_cookie.lower()


def test_post_with_no_csrf_token_is_rejected():
    client = TestClient(app)
    client.get("/")  # establishes the cookie
    resp = client.post("/login", data={"email": "chef@example.com", "password": "x"})
    assert resp.status_code == 403


def test_post_with_mismatched_csrf_token_is_rejected():
    client = TestClient(app)
    client.get("/")
    resp = client.post(
        "/login",
        data={"email": "chef@example.com", "password": "x", FIELD_NAME: "not-the-real-token"},
    )
    assert resp.status_code == 403


def test_post_with_no_cookie_at_all_is_rejected_even_with_a_field_value():
    """A cold client (no prior GET) that guesses a form field value still can't pass — there is
    no cookie to match it against."""
    client = TestClient(app)
    resp = client.post("/login", data={"email": "chef@example.com", "password": "x", FIELD_NAME: "guessed"})
    assert resp.status_code == 403


def test_post_with_matching_csrf_token_is_accepted():
    """A matching token lets the request reach the route itself — proven by getting the
    route's OWN response (401 bad credentials) instead of CSRF's 403."""
    client = TestClient(app)
    client.get("/login")
    token = client.cookies.get(COOKIE_NAME)
    resp = client.post(
        "/login", data={"email": "chef@example.com", "password": "wrong", FIELD_NAME: token},
    )
    assert resp.status_code == 401  # the route's own "incorrect email or password", not a 403


def test_login_form_renders_the_csrf_hidden_field_matching_the_cookie():
    client = TestClient(app)
    resp = client.get("/login")
    token = client.cookies.get(COOKIE_NAME)
    assert f'name="csrf_token" value="{token}"' in resp.text


def test_get_requests_are_never_blocked_by_csrf():
    client = TestClient(app)
    resp = client.get("/")
    assert resp.status_code == 200


def test_multipart_post_form_fields_survive_csrf_verification(monkeypatch):
    """Regression: CSRFMiddleware reads the request body to check the token; if that read
    isn't done in a way BaseHTTPMiddleware can replay, every downstream Form(...)/UploadFile
    dependency sees an empty body and 422s with "field required" — reproduced live during this
    phase's build before web/csrf.py::verify_csrf_request added the request.body() priming
    call. Bypasses login only (not CSRF) to isolate the multipart-body-survives-the-middleware
    behavior from auth.
    """
    import web.app as appmod
    from src.auth.service import Identity

    fake_identity = Identity(
        session_id="s1", user_id="u1", email="chef@example.com",
        restaurant_id="r1", restaurant_name="Test Kitchen",
    )
    monkeypatch.setattr(appmod, "current_identity", lambda request, db: fake_identity)

    client = TestClient(app)
    client.get("/upload")
    token = client.cookies.get(COOKIE_NAME)

    sales = b"dish_name,count,period_start,period_end\nBurger,120,2026-06-01,2026-06-07\n"
    bom = (
        b"dish_name,ingredient_name,qty,recipe_unit,canonical_unit,yield_factor\n"
        b"Burger,beef,6,oz,oz,0.9\n"
    )
    resp = client.post(
        "/upload",
        data={FIELD_NAME: token},
        files={
            "sales_file": ("sales.csv", sales, "text/csv"),
            "bom_file": ("bom.csv", bom, "text/csv"),
        },
    )
    assert resp.status_code == 200
    assert "Burger" in resp.text


def test_public_grid_get_still_works_without_any_csrf_setup():
    """W0's deliberately public, unauthenticated page must not gain a new failure mode from a
    security feature aimed at state-changing requests."""
    client = TestClient(app)
    resp = client.get("/")
    assert resp.status_code == 200


def test_oversized_post_is_rejected_before_the_body_is_buffered():
    """Regression for W7_review.md MAJOR-1: verify_csrf_request's request.body() call used to
    run unconditionally, buffering the WHOLE body in memory before the CSRF token was even
    compared and before any route's own size guard ran — an unauthenticated caller could force
    arbitrary-size in-memory buffering. A declared oversized Content-Length must now 413 without
    needing a valid cookie/token at all."""
    client = TestClient(app)
    oversized = "x" * 3_500_001  # one byte past _MAX_REQUEST_BODY_BYTES
    resp = client.post("/login", data={"email": "a@b.com", "password": "x", "pad": oversized})
    assert resp.status_code == 413


def test_reasonable_sized_multipart_upload_is_unaffected_by_the_size_guard(monkeypatch):
    """The 413 guard's cap must sit comfortably above the largest legitimate body (the two-file
    /upload route) so it never rejects real traffic — only proven-hostile oversized requests."""
    import web.app as appmod
    from src.auth.service import Identity

    fake_identity = Identity(
        session_id="s1", user_id="u1", email="chef@example.com",
        restaurant_id="r1", restaurant_name="Test Kitchen",
    )
    monkeypatch.setattr(appmod, "current_identity", lambda request, db: fake_identity)

    client = TestClient(app)
    client.get("/upload")
    token = client.cookies.get(COOKIE_NAME)

    sales = b"dish_name,count,period_start,period_end\nBurger,120,2026-06-01,2026-06-07\n"
    bom = (
        b"dish_name,ingredient_name,qty,recipe_unit,canonical_unit,yield_factor\n"
        b"Burger,beef,6,oz,oz,0.9\n"
    )
    resp = client.post(
        "/upload",
        data={FIELD_NAME: token},
        files={
            "sales_file": ("sales.csv", sales, "text/csv"),
            "bom_file": ("bom.csv", bom, "text/csv"),
        },
    )
    assert resp.status_code == 200
