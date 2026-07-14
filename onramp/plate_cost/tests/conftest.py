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
