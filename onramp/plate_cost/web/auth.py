"""Session gate for the on-ramp's real, DB-backed accounts (W5).

FastAPI/Starlette glue only — the actual identity/session logic is the pure(r), DB-aware
``src/auth/service.py`` (rule 05: business logic stays out of the web layer). Every
data-bearing route other than the public sample grid (``GET /``) requires a valid session;
enforced here, server-side, never left to the client (rule 06: "isolation is enforced in the
backend, never delegated to the front end").

W5 retires Starlette's ``SessionMiddleware`` (an itsdangerous-signed client cookie) entirely:
the cookie now carries only an opaque random token
(``src.auth.credentials.generate_token()``); validity is checked by a hashed lookup against
the ``sessions`` table on every request, which is also what makes a session listable and
revocable server-side (the W2->W5 forward note in ``docs/website_production_overview.md`` row
2). There is no longer a signing secret to manage at all — this resolves that row's "ephemeral
session secret" problem more completely than simply persisting ``ONRAMP_SESSION_SECRET`` would
have (``docs/phase_decisions/W5.md``).
"""
from __future__ import annotations

import logging

from fastapi import Request
from fastapi.responses import RedirectResponse
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session as DbSession

import src.db.engine as db_engine
from src.auth.service import Identity, resolve_session
from src.db.engine import get_db as get_db  # re-exported: routes import the DB dependency from here

SESSION_COOKIE = "onramp_session"

_log = logging.getLogger(__name__)


def _identity(request: Request, db: DbSession) -> Identity | None:
    """Shared by every function below. Catches DB errors broadly and treats them as "not
    authenticated" rather than raising: this helper backs the nav's cosmetic ``logged_in`` flag
    (called on *every* template render, including public pages, via ``_nav_context`` in
    ``web/app.py``) as well as the real auth gate, and rule 06 requires failing legibly, never
    with a stack trace. A DB outage therefore surfaces as "please log in" rather than a crash —
    an accepted simplification for a pre-hosting, single-process app (no real ops/monitoring
    story exists yet; that is W7's remit). See docs/phase_decisions/W5.md Reviewer Focus Areas.
    """
    try:
        return resolve_session(db, request.cookies.get(SESSION_COOKIE))
    except SQLAlchemyError:
        _log.warning("session lookup failed; treating as unauthenticated", exc_info=True)
        return None


def is_authenticated(request: Request) -> bool:
    """Self-contained (opens and closes its own short-lived DB session) because Jinja2's
    context-processor hook (``_nav_context`` in ``web/app.py``) runs for every template render,
    including public pages that never call ``require_login``, and is invoked with only
    ``request`` — no ``Depends()`` plumbing reaches it."""
    db = db_engine.SessionLocal()
    try:
        return _identity(request, db) is not None
    finally:
        db.close()


def require_login(request: Request, db: DbSession) -> RedirectResponse | None:
    """``None`` if the session is authenticated; otherwise a redirect to ``/login``. Same
    manual early-return shape as W2 (matches this codebase's existing control-flow style) —
    only the resource used to check now differs (a DB session lookup instead of a signed
    cookie read)."""
    if _identity(request, db) is None:
        return RedirectResponse(url="/login", status_code=303)
    return None


def current_identity(request: Request, db: DbSession) -> Identity | None:
    """The authenticated principal, for routes that need the actual user/restaurant ids (a
    staged upload's owner, the login/logout cookie writers) rather than a bare yes/no."""
    return _identity(request, db)
