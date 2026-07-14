"""Tests for the DB-aware identity operations (src/auth/service.py).

Covers: the invite-only account-creation act (restaurant + user + credential + membership in
one transaction, duplicate email rejected), login authenticate() success/failure paths, the
full session lifecycle (issue -> resolve -> revoke, expired/revoked sessions rejected — the
edge cases a revocable, DB-backed session actually needs to get right), and the full
password-reset round trip (request -> use token -> old password stops working, new one works,
every prior session gets revoked, token is single-use).
"""
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import select

from src.auth.service import (
    authenticate,
    create_account,
    create_session,
    request_password_reset,
    reset_password,
    resolve_session,
    revoke_session,
)
from src.db.models import Session as SessionRow


@pytest.fixture()
def db(db_sessionmaker):
    session = db_sessionmaker()
    yield session
    session.close()


def test_create_account_creates_restaurant_user_credential_membership(db):
    user = create_account(db, "Marco's Trattoria", "Chef@Example.com", "s3cret123")
    assert user.email == "chef@example.com"  # normalized to lowercase
    assert user.credential is not None
    assert len(user.memberships) == 1
    assert user.memberships[0].restaurant.name == "Marco's Trattoria"
    assert user.memberships[0].role == "owner"


def test_create_account_rejects_duplicate_email(db):
    create_account(db, "Restaurant A", "chef@example.com", "s3cret123")
    with pytest.raises(ValueError, match="already exists"):
        create_account(db, "Restaurant B", "chef@example.com", "different-pass")


def test_create_account_rejects_short_password(db):
    with pytest.raises(ValueError, match="at least"):
        create_account(db, "Restaurant A", "chef@example.com", "short")


def test_create_account_rejects_a_second_restaurant(db):
    """W5_review.md BLOCKER-1: data/raw/ stays global/unpartitioned until W9, so a second
    restaurant today would read and write the very same seam files as the first — proven
    reachable by the review (a second account could see and export the first's BOM). Fenced to
    exactly one restaurant until W9 does the real cross-peer seam partitioning."""
    create_account(db, "Restaurant A", "chef-a@example.com", "s3cret123")
    with pytest.raises(ValueError, match="second tenant"):
        create_account(db, "Restaurant B", "chef-b@example.com", "s3cret123")


def test_authenticate_correct_password_returns_user(db):
    create_account(db, "Restaurant A", "chef@example.com", "s3cret123")
    user = authenticate(db, "chef@example.com", "s3cret123")
    assert user is not None
    assert user.email == "chef@example.com"


def test_authenticate_wrong_password_returns_none(db):
    create_account(db, "Restaurant A", "chef@example.com", "s3cret123")
    assert authenticate(db, "chef@example.com", "wrong") is None


def test_authenticate_unknown_email_returns_none(db):
    assert authenticate(db, "nobody@example.com", "anything") is None


def test_authenticate_unknown_email_still_pays_argon2_cost(db, monkeypatch):
    """W5_review.md MINOR-1: an unknown email must not short-circuit before argon2 runs, or
    response latency (not just the message) leaks whether the email has an account. Verified
    by observing verify_password is actually invoked (against the fixed dummy hash), not by
    timing — timing assertions are flaky; this checks the control-flow property that produces
    the timing parity instead."""
    import src.auth.service as service_module
    from src.auth.credentials import DUMMY_PASSWORD_HASH

    calls = []
    real_verify_password = service_module.verify_password
    monkeypatch.setattr(
        service_module,
        "verify_password",
        lambda password, password_hash: calls.append((password, password_hash))
        or real_verify_password(password, password_hash),
    )

    assert authenticate(db, "nobody@example.com", "anything") is None
    assert calls == [("anything", DUMMY_PASSWORD_HASH)]


def test_authenticate_email_is_case_insensitive(db):
    create_account(db, "Restaurant A", "chef@example.com", "s3cret123")
    assert authenticate(db, "Chef@Example.com", "s3cret123") is not None


def test_session_lifecycle_issue_resolve_revoke(db):
    user = create_account(db, "Restaurant A", "chef@example.com", "s3cret123")
    token, _row = create_session(db, user)

    identity = resolve_session(db, token)
    assert identity is not None
    assert identity.user_id == user.id
    assert identity.email == "chef@example.com"
    assert identity.restaurant_name == "Restaurant A"

    revoke_session(db, token)
    assert resolve_session(db, token) is None  # revoked sessions no longer authenticate


def test_resolve_session_rejects_unknown_token(db):
    assert resolve_session(db, "not-a-real-token") is None


def test_resolve_session_rejects_none_and_empty(db):
    assert resolve_session(db, None) is None
    assert resolve_session(db, "") is None


def test_resolve_session_rejects_expired_session(db):
    user = create_account(db, "Restaurant A", "chef@example.com", "s3cret123")
    token, row = create_session(db, user)
    row.expires_at = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(seconds=1)
    db.commit()

    assert resolve_session(db, token) is None


def test_password_reset_full_round_trip(db):
    user = create_account(db, "Restaurant A", "chef@example.com", "old-password")
    old_token, _ = create_session(db, user)

    reset_token = request_password_reset(db, "chef@example.com")
    assert reset_token is not None

    assert reset_password(db, reset_token, "new-password-123") is True

    assert authenticate(db, "chef@example.com", "old-password") is None
    assert authenticate(db, "chef@example.com", "new-password-123") is not None
    # Every session alive before the reset is revoked, not just the one used to request it.
    assert resolve_session(db, old_token) is None


def test_password_reset_token_is_single_use(db):
    create_account(db, "Restaurant A", "chef@example.com", "old-password")
    reset_token = request_password_reset(db, "chef@example.com")

    assert reset_password(db, reset_token, "new-password-123") is True
    assert reset_password(db, reset_token, "another-password-456") is False


def test_password_reset_rejects_expired_token(db):
    user = create_account(db, "Restaurant A", "chef@example.com", "old-password")
    reset_token = request_password_reset(db, "chef@example.com")

    user.credential.reset_token_expires_at = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(seconds=1)
    db.commit()

    assert reset_password(db, reset_token, "new-password-123") is False


def test_request_password_reset_returns_none_for_unknown_email(db):
    """Never leaks which emails have accounts — a route relies on this returning None for a
    caller to build an identical response either way."""
    assert request_password_reset(db, "nobody@example.com") is None


def test_session_records_are_listed_in_the_sessions_table(db):
    """The whole point of a DB-backed session over W2's signed cookie: it must be enumerable
    server-side (docs/website_production_overview.md row 2)."""
    user = create_account(db, "Restaurant A", "chef@example.com", "s3cret123")
    create_session(db, user)
    create_session(db, user)

    rows = db.scalars(select(SessionRow).where(SessionRow.user_id == user.id)).all()
    assert len(rows) == 2
