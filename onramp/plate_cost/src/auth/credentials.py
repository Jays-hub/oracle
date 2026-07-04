"""Operator credential check — pure, framework-agnostic (rule 05: compute stays pure).

W2 is a single-operator tool today: one restaurant, one login, no signup and no password
reset. The credential lives entirely in environment variables (rule 07: secrets in env, never
in code or the repo) rather than a user table, because nothing has yet validated a need for
more than one account (see docs/phase_decisions/W2.md — a user table is a forward note, not
built here). Verification fails CLOSED: if either env var is unset, every attempt fails rather
than falling back to a default or hardcoded credential.
"""
from __future__ import annotations

import hashlib
import hmac
import os

USERNAME_ENV = "ONRAMP_AUTH_USERNAME"
PASSWORD_HASH_ENV = "ONRAMP_AUTH_PASSWORD_HASH"


def hash_password(password: str) -> str:
    """SHA-256 hex digest of a password — deterministic (same input always yields the same
    output), used both to seed ONRAMP_AUTH_PASSWORD_HASH and to check a login attempt.

    Not a slow KDF (bcrypt/scrypt/argon2): the threat model here is one operator credential
    checked against a login form, not a leaked table of many user hashes worth slowing down
    offline brute-force against. Revisit if this ever becomes a real multi-user credential store.
    """
    return hashlib.sha256(password.encode("utf-8")).hexdigest()


def verify_credentials(username: str, password: str) -> bool:
    """True iff username/password match the configured operator credential.

    Both comparisons run unconditionally (no short-circuit before the final `and`) and use
    `hmac.compare_digest` so a wrong-username attempt and a wrong-password attempt take
    indistinguishable time.
    """
    expected_username = os.environ.get(USERNAME_ENV)
    expected_hash = os.environ.get(PASSWORD_HASH_ENV)
    if not expected_username or not expected_hash:
        return False
    # Compare as UTF-8 bytes, not str: hmac.compare_digest raises TypeError on a str
    # argument containing non-ASCII characters, which would turn a login attempt with an
    # accented username into a 500 instead of a clean rejection (W2_review.md MAJOR-1).
    username_ok = hmac.compare_digest(username.encode("utf-8"), expected_username.encode("utf-8"))
    password_ok = hmac.compare_digest(hash_password(password), expected_hash)
    return username_ok and password_ok
