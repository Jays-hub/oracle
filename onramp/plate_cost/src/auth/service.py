"""Identity operations against the app DB — DB-aware but framework-agnostic (rule 05: no
FastAPI/Starlette import here; ``web/auth.py`` is the only caller that knows about HTTP/cookies).

Retires W2's single env-configured operator credential: a login now authenticates a real
``User`` row (via its ``Credential``), resolves the restaurant they belong to through
``Membership``, and issues a DB-backed, revocable ``Session`` row instead of a client-signed
cookie. Also the "invite-only account creation" act (``docs/website_production_overview.md``
W5 row): ``create_account`` is the whole thing ``scripts/create_account.py`` calls.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session as DbSession

from ..db.models import Credential, Membership, Restaurant, Session as SessionRow, User
from .credentials import DUMMY_PASSWORD_HASH, generate_token, hash_password, hash_token, verify_password

SESSION_TTL = timedelta(days=14)
RESET_TOKEN_TTL = timedelta(hours=1)
MIN_PASSWORD_LENGTH = 8


def _utcnow() -> datetime:
    """Naive datetime representing the current UTC instant — matches src/db/models.py::_utcnow
    exactly (see that docstring): SQLite round-trips a stored DateTime as naive, so every
    timestamp this module stores or compares must be naive-but-UTC too, or a value freshly read
    back from the DB (naive) can't be compared against a fresh aware "now"."""
    return datetime.now(timezone.utc).replace(tzinfo=None)


@dataclass(frozen=True)
class Identity:
    """The authenticated principal for a request — a user acting within one restaurant's
    context. ``restaurant_id`` is carried for identity/audit purposes only: ``data/raw/`` reads
    stay global/unpartitioned in W5 (seam-level tenancy is W9), so this does not yet scope
    *which seam rows* a route can see — only which app-DB rows (staged uploads, sessions)."""

    session_id: str
    user_id: str
    email: str
    restaurant_id: str
    restaurant_name: str


def create_account(
    db: DbSession, restaurant_name: str, email: str, password: str, role: str = "owner"
) -> User:
    """Creates a restaurant + user + credential + membership in one transaction — the whole
    "invite" act. Raises ``ValueError`` (never a bare ``IntegrityError``) if the email is
    already registered or the password is too short, so a CLI caller gets a clean message.

    **Fenced to a single restaurant until W9.** Every call creates a brand-new ``Restaurant``
    row, but ``data/raw/`` (the seam) stays global and unpartitioned until W9 does the real
    cross-peer partitioning (``data/CONTRACT.md``, ``docs/website_production_overview.md`` §4).
    A second restaurant today would read and write the *same* seam files as the first — proven
    reachable by ``/review-web W5`` (``docs/phase_decisions/W5_review.md`` BLOCKER-1: a second
    account could see and export the first restaurant's BOM). Refusing it here makes "exactly
    one tenant" a real constraint instead of an accidental, unenforced convention.
    """
    email = email.strip().lower()
    if not email:
        raise ValueError("email must not be empty")
    if len(password) < MIN_PASSWORD_LENGTH:
        raise ValueError(f"password must be at least {MIN_PASSWORD_LENGTH} characters")
    if db.scalar(select(User).where(User.email == email)) is not None:
        raise ValueError(f"an account already exists for {email!r}")
    if db.scalar(select(Restaurant.id)) is not None:
        raise ValueError(
            "a restaurant already exists; a second tenant cannot be created until W9 "
            "partitions the seam (data/raw/ is still global — see "
            "docs/phase_decisions/W5_review.md BLOCKER-1)"
        )

    restaurant = Restaurant(name=restaurant_name)
    user = User(email=email)
    db.add_all([restaurant, user])
    db.flush()  # assign ids before the FK rows below reference them
    db.add(Credential(user_id=user.id, password_hash=hash_password(password)))
    db.add(Membership(user_id=user.id, restaurant_id=restaurant.id, role=role))
    db.commit()
    db.refresh(user)
    return user


def authenticate(db: DbSession, email: str, password: str) -> User | None:
    """None on any failure (unknown email, no credential row, wrong password) — the *response*
    is identical either way, and so is the *work*: an unknown email still runs a full argon2
    verify (against a fixed dummy hash) rather than short-circuiting, so response latency
    doesn't hand an attacker a cheaper way to enumerate accounts than the message does
    (docs/phase_decisions/W5_review.md MINOR-1)."""
    email = email.strip().lower()
    if not email or not password:
        return None
    user = db.scalar(select(User).where(User.email == email))
    if user is None or user.credential is None:
        verify_password(password, DUMMY_PASSWORD_HASH)
        return None
    if not verify_password(password, user.credential.password_hash):
        return None
    return user


def _primary_membership(db: DbSession, user: User) -> Membership | None:
    """The restaurant a session is scoped to. A user has exactly one membership in W5 (the
    invite-only CLI bootstraps one restaurant + one owner membership per account atomically) —
    picking the earliest-created row is a forward-compatible tie-break for the day a user
    belongs to more than one restaurant (W10's "team access" milestone), not a claim that
    multi-restaurant membership is exercised or tested today."""
    return db.scalar(
        select(Membership).where(Membership.user_id == user.id).order_by(Membership.created_at)
    )


def create_session(db: DbSession, user: User) -> tuple[str, SessionRow] | None:
    """Issues a new session for ``user``'s primary restaurant. Returns ``(raw_token, row)`` —
    the raw token is handed back exactly once; only its hash is ever persisted (mirrors
    password storage discipline). ``None`` if the user has no restaurant membership at all
    (shouldn't happen for an account created through ``create_account``, but a login path must
    never assume a data invariant it didn't itself just check)."""
    membership = _primary_membership(db, user)
    if membership is None:
        return None
    token = generate_token()
    row = SessionRow(
        user_id=user.id,
        restaurant_id=membership.restaurant_id,
        token_hash=hash_token(token),
        expires_at=_utcnow() + SESSION_TTL,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return token, row


def resolve_session(db: DbSession, raw_token: str | None) -> Identity | None:
    """The live ``Identity`` for a raw cookie token, or ``None`` if missing/expired/revoked/
    dangling (a session whose user or restaurant row was since deleted)."""
    if not raw_token:
        return None
    row = db.scalar(select(SessionRow).where(SessionRow.token_hash == hash_token(raw_token)))
    if row is None or row.revoked_at is not None or row.expires_at <= _utcnow():
        return None
    user = db.get(User, row.user_id)
    restaurant = db.get(Restaurant, row.restaurant_id)
    if user is None or restaurant is None:
        return None
    return Identity(
        session_id=row.id,
        user_id=user.id,
        email=user.email,
        restaurant_id=restaurant.id,
        restaurant_name=restaurant.name,
    )


def revoke_session(db: DbSession, raw_token: str | None) -> None:
    """Logout: marks the session revoked rather than deleting the row, so it stays in the app
    DB's own history (the ``sessions`` table the production overview names as "the app DB can
    list and revoke" — a deleted row can't be listed)."""
    if not raw_token:
        return
    row = db.scalar(select(SessionRow).where(SessionRow.token_hash == hash_token(raw_token)))
    if row is not None and row.revoked_at is None:
        row.revoked_at = _utcnow()
        db.commit()


def _revoke_all_sessions(db: DbSession, user_id: str) -> None:
    """Called on password reset — a changed password should kill every existing session, not
    just the one used to request the reset (defense against a stolen-but-not-yet-noticed
    session surviving a credential rotation)."""
    rows = db.scalars(
        select(SessionRow).where(SessionRow.user_id == user_id, SessionRow.revoked_at.is_(None))
    )
    now = _utcnow()
    for row in rows:
        row.revoked_at = now
    db.commit()


def request_password_reset(db: DbSession, email: str) -> str | None:
    """Issues a reset token for ``email`` if a matching account exists and returns the RAW
    token; ``None`` if no account matches. The caller (a web route) must show an **identical**
    response either way — never let this function's return value leak which emails have
    accounts (see ``docs/phase_decisions/W5.md`` for why W5 has no email transport and how the
    route surfaces the token instead)."""
    email = email.strip().lower()
    user = db.scalar(select(User).where(User.email == email))
    if user is None or user.credential is None:
        return None
    token = generate_token()
    user.credential.reset_token_hash = hash_token(token)
    user.credential.reset_token_expires_at = _utcnow() + RESET_TOKEN_TTL
    db.commit()
    return token


def reset_password(db: DbSession, raw_token: str, new_password: str) -> bool:
    """True, and applies the new password, iff ``raw_token`` matches a live, unexpired reset
    token and ``new_password`` meets the minimum length. Single-use: the token is cleared on
    success; a failed or expired attempt leaves it in place (still unusable, since expiry is
    checked independently) until a new reset request overwrites it. On success, every existing
    session for that user is also revoked."""
    if not raw_token or len(new_password) < MIN_PASSWORD_LENGTH:
        return False
    token_hash = hash_token(raw_token)
    credential = db.scalar(select(Credential).where(Credential.reset_token_hash == token_hash))
    if credential is None or credential.reset_token_expires_at is None:
        return False
    if credential.reset_token_expires_at <= _utcnow():
        return False

    credential.password_hash = hash_password(new_password)
    credential.reset_token_hash = None
    credential.reset_token_expires_at = None
    db.commit()
    _revoke_all_sessions(db, credential.user_id)
    return True
