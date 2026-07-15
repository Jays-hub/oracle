"""Shared app-DB fixture for the on-ramp test suite (W5).

Every test in this directory gets an isolated SQLite file under tmp_path, with all W5 tables
created fresh — never the real onramp/plate_cost/instance/onramp.db. Autouse (not opt-in)
because web/app.py's nav context processor (_nav_context -> is_authenticated) now opens a DB
session on *every* template render, including pages that have nothing to do with auth (the
public grid, error pages) — leaving even one test unpatched would have it silently hit the
real default database path.

Mirrors the existing src.store.RAW_DIR monkeypatch convention (test_web_auth.py etc.): patch
the module attribute the code actually reads at call time, not a name captured at import time.
"""
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

import src.db.engine as db_engine
import web.csrf as csrf_module
import web.rate_limit as rate_limit_module
from src.db.models import Base


@pytest.fixture(autouse=True)
def db_sessionmaker(tmp_path, monkeypatch):
    """Yields the sessionmaker so a test can open its own Session to seed rows directly, e.g.
    ``db = db_sessionmaker(); ...; db.close()``."""
    test_engine = create_engine(
        f"sqlite:///{tmp_path / 'test_app.db'}", connect_args={"check_same_thread": False},
    )
    Base.metadata.create_all(test_engine)
    factory = sessionmaker(bind=test_engine, autoflush=False, expire_on_commit=False)
    monkeypatch.setattr(db_engine, "SessionLocal", factory)
    yield factory
    test_engine.dispose()


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
    "read it fresh through the module" pattern src/db/engine.py::get_db documents), so this
    takes effect without touching web/csrf.py itself.
    """
    async def _always_valid(request, cookie_token):
        return True

    monkeypatch.setattr(csrf_module, "verify_csrf_request", _always_valid)


@pytest.fixture(autouse=True)
def _reset_rate_limits():
    """W7's rate limiter is process-global state (web/rate_limit.py) keyed by client IP —
    every test using TestClient shares the same fake IP ("testclient"), so without a per-test
    reset, an earlier test's login/upload attempts would count against a later test's budget."""
    rate_limit_module.reset_rate_limits()
    yield
    rate_limit_module.reset_rate_limits()
