"""Autouse fixtures for the L4 surface tests (W5/W7).

The app-DB fixture is autouse *here* and nowhere else: `surface/web/app.py`'s nav context
processor (`_nav_context -> is_authenticated`) opens a DB session on **every** template render,
including pages that have nothing to do with auth (the public grid, error pages), so leaving even
one surface test unpatched would have it silently hit the real default database path. Tests in
other layers that genuinely need a database request `db_sessionmaker` by name from
`tests/conftest.py`.
"""
import pytest

import surface.web.csrf as csrf_module
import surface.web.rate_limit as rate_limit_module


@pytest.fixture(autouse=True)
def _app_db(db_sessionmaker):
    """Attaches tests/conftest.py's app-DB fixture to every test in this directory."""
    return db_sessionmaker


@pytest.fixture(autouse=True)
def _bypass_csrf_by_default(monkeypatch):
    """W7's CSRFMiddleware rejects any POST/PUT/PATCH/DELETE whose form doesn't echo back a
    matching cookie token — every existing test in this suite predates that and posts directly
    with plain form ``data=``, the same way a non-browser API caller would. Bypassed here by
    default (mirrors test_web_upload.py's pre-existing ``_bypass_login`` pattern: patch the
    unrelated concern away so a test file can focus on the behavior it actually owns) so W7
    doesn't force-touch every POST call site in the suite. ``test_web_csrf.py`` overrides this
    fixture (same name, defined in that module) to test the real enforcement.

    Patches the module attribute CSRFMiddleware calls by bare name at request time (the same
    "read it fresh through the module" pattern db/engine.py::get_db documents), so this takes
    effect without touching surface/web/csrf.py itself.
    """
    async def _always_valid(request, cookie_token):
        return True

    monkeypatch.setattr(csrf_module, "verify_csrf_request", _always_valid)


@pytest.fixture(autouse=True)
def _reset_rate_limits():
    """W7's rate limiter is process-global state (surface/web/rate_limit.py) keyed by client IP —
    every test using TestClient shares the same fake IP ("testclient"), so without a per-test
    reset, an earlier test's login/upload attempts would count against a later test's budget."""
    rate_limit_module.reset_rate_limits()
    yield
    rate_limit_module.reset_rate_limits()
