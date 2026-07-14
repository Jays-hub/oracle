"""On-ramp application database — engine/session factory (W5).

SQLite via SQLAlchemy first, swapped for Postgres at W7 by changing ``ONRAMP_DATABASE_URL``
alone (no code change) — the "server-class DB" decision deferred to that recorded moment
(``docs/website_production_overview.md`` §3, ``docs/common_base_reconciliation.md`` §6.6).

Deliberately **not** ``data/`` — the app DB is on-ramp-private, never the seam. The default path
resolves beside this module (``onramp/plate_cost/instance/``), gitignored, never under the
repo-root ``data/`` directory the seam contract owns (``data/CONTRACT.md``).
"""
from __future__ import annotations

import os
from collections.abc import Generator
from pathlib import Path

from sqlalchemy import Engine, create_engine, event
from sqlalchemy.orm import Session, sessionmaker

# engine.py -> parents: [db, src, plate_cost]
_PLATE_COST_DIR = Path(__file__).resolve().parents[2]
_DEFAULT_DB_PATH = _PLATE_COST_DIR / "instance" / "onramp.db"

DATABASE_URL_ENV = "ONRAMP_DATABASE_URL"


def _default_sqlite_url() -> str:
    _DEFAULT_DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    return f"sqlite:///{_DEFAULT_DB_PATH}"


def resolve_database_url() -> str:
    """``ONRAMP_DATABASE_URL`` if set (rule 07: secrets/connection strings in env), else a
    local gitignored SQLite file beside this module. Shared by this module, ``migrations/env.py``,
    and ``scripts/create_account.py`` so the URL is derived in exactly one place."""
    return os.environ.get(DATABASE_URL_ENV) or _default_sqlite_url()


def build_engine(database_url: str | None = None) -> Engine:
    """A fresh engine for ``database_url`` (``resolve_database_url()`` if unset).

    SQLite needs ``check_same_thread=False`` because FastAPI's threadpool can service a request
    on a different thread than the one that opened the connection; each request still gets its
    own ``Session`` from ``SessionLocal`` (see ``get_db`` below), so no connection is ever
    *shared* across concurrent requests — this flag only lifts sqlite3's same-thread default,
    it does not remove the isolation a per-request Session already gives us.

    SQLite also ignores every ``ForeignKey`` declared in ``src/db/models.py`` unless
    ``PRAGMA foreign_keys=ON`` is set on each connection — off by default in sqlite3, so a
    connect-event listener below turns it on for every connection this engine opens. Without
    it, the FKs on ``memberships``/``credentials``/``sessions``/``staged_uploads`` are
    documentation, not an enforced guard (``docs/phase_decisions/W5_review.md`` LOW-3).
    """
    url = database_url or resolve_database_url()
    connect_args = {"check_same_thread": False} if url.startswith("sqlite") else {}
    built_engine = create_engine(url, connect_args=connect_args)
    if url.startswith("sqlite"):
        @event.listens_for(built_engine, "connect")
        def _enable_sqlite_foreign_keys(dbapi_connection, _connection_record):
            cursor = dbapi_connection.cursor()
            cursor.execute("PRAGMA foreign_keys=ON")
            cursor.close()
    return built_engine


engine: Engine = build_engine()
SessionLocal: sessionmaker[Session] = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


def get_db() -> Generator[Session, None, None]:
    """FastAPI dependency: one ``Session`` per request, always closed.

    References the bare name ``SessionLocal``, resolved from this module's namespace fresh on
    every call (ordinary Python global lookup, not bound at function-definition time) — the same
    "read it fresh through the module" pattern ``src/store.py`` uses for ``RAW_DIR``, so a
    test's ``monkeypatch.setattr(db_engine, "SessionLocal", ...)`` (which mutates this module's
    ``__dict__`` in place) takes effect for every route that depends on this function.
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
