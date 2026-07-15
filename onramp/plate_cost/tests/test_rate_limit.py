"""Tests for the W7 in-process rate limiter (web/rate_limit.py) — pure unit tests against
``check_rate_limit`` (a bare Request stand-in), plus one end-to-end test that a flooded
``POST /login`` actually gets a 429 through the real app.
"""
from dataclasses import dataclass, field

import pytest
from fastapi.testclient import TestClient

from web.app import app
from web.csrf import COOKIE_NAME, FIELD_NAME
from web.rate_limit import _client_ip, check_rate_limit, reset_rate_limits


@dataclass
class _FakeClient:
    host: str


@dataclass
class _FakeRequest:
    client: _FakeClient
    headers: dict = field(default_factory=dict)


def _request(ip: str = "1.2.3.4") -> _FakeRequest:
    return _FakeRequest(client=_FakeClient(host=ip))


@pytest.fixture(autouse=True)
def _clean_buckets():
    reset_rate_limits()
    yield
    reset_rate_limits()


def test_requests_within_budget_are_never_throttled():
    req = _request()
    for _ in range(5):
        assert check_rate_limit(req, "bucket", max_requests=5) is None


def test_the_request_that_exceeds_budget_is_throttled_with_429():
    req = _request()
    for _ in range(5):
        assert check_rate_limit(req, "bucket", max_requests=5) is None
    throttled = check_rate_limit(req, "bucket", max_requests=5)
    assert throttled is not None
    assert throttled.status_code == 429


def test_different_ips_have_independent_budgets():
    a, b = _request("1.1.1.1"), _request("2.2.2.2")
    for _ in range(5):
        assert check_rate_limit(a, "bucket", max_requests=5) is None
    # b's budget is untouched by a's requests
    assert check_rate_limit(b, "bucket", max_requests=5) is None


def test_different_buckets_have_independent_budgets_for_the_same_ip():
    """A chef's own login attempts must never burn their upload budget, and vice versa."""
    req = _request()
    for _ in range(5):
        assert check_rate_limit(req, "login", max_requests=5) is None
    assert check_rate_limit(req, "upload", max_requests=5) is None


def test_reset_rate_limits_clears_all_buckets():
    req = _request()
    for _ in range(5):
        check_rate_limit(req, "bucket", max_requests=5)
    reset_rate_limits()
    assert check_rate_limit(req, "bucket", max_requests=5) is None


def test_login_endpoint_429s_after_its_configured_budget(db_sessionmaker):
    """End-to-end: TestClient's fixed fake IP means every request in this test shares one
    budget, so repeatedly POSTing /login must eventually 429 rather than accept forever."""
    client = TestClient(app)
    client.get("/login")
    token = client.cookies.get(COOKIE_NAME)

    statuses = []
    for _ in range(15):
        resp = client.post(
            "/login", data={"email": "nobody@example.com", "password": "x", FIELD_NAME: token},
        )
        statuses.append(resp.status_code)

    assert 429 in statuses
    # Every response before the throttle kicked in was a normal auth failure, not a crash.
    assert all(s in (401, 429) for s in statuses)


def test_client_ip_ignores_forwarded_header_from_an_untrusted_peer():
    """Regression for W7_review.md MAJOR-3: without a trusted-proxy allowlist, a caller must not
    be able to forge its own rate-limit identity via X-Forwarded-For."""
    req = _FakeRequest(client=_FakeClient(host="10.0.0.5"), headers={"x-forwarded-for": "1.1.1.1"})
    assert _client_ip(req) == "10.0.0.5"


def test_client_ip_reads_forwarded_header_only_from_a_trusted_proxy(monkeypatch):
    """The bug this reproduces: under the reverse-proxy deploy web/config.py itself recommends,
    _client_ip returned the PROXY's address for every real visitor, collapsing every tenant into
    one shared budget. With the proxy's address in ONRAMP_TRUSTED_PROXY_IPS, two different real
    clients behind that proxy must now get independent budgets."""
    monkeypatch.setenv("ONRAMP_TRUSTED_PROXY_IPS", "127.0.0.1")
    req_a = _FakeRequest(client=_FakeClient(host="127.0.0.1"), headers={"x-forwarded-for": "9.9.9.9"})
    req_b = _FakeRequest(client=_FakeClient(host="127.0.0.1"), headers={"x-forwarded-for": "8.8.8.8"})
    assert _client_ip(req_a) == "9.9.9.9"
    assert _client_ip(req_b) == "8.8.8.8"

    for _ in range(5):
        assert check_rate_limit(req_a, "bucket", max_requests=5) is None
    assert check_rate_limit(req_b, "bucket", max_requests=5) is None


def test_reset_confirm_endpoint_429s_after_its_configured_budget():
    """NIT from W7_review.md: POST /reset-password/{token} (token consumption) had no throttle
    at all -- cheap to close given the bucket machinery already exists."""
    client = TestClient(app)

    statuses = []
    for _ in range(15):
        resp = client.post(
            "/reset-password/not-a-real-token", data={"new_password": "whatever-123"},
        )
        statuses.append(resp.status_code)

    assert 429 in statuses
    assert all(s in (400, 429) for s in statuses)
