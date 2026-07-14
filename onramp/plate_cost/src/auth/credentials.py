"""Password + token cryptography — pure, framework- and DB-agnostic (rule 05: compute stays
pure). ``src/auth/service.py`` is the DB-aware layer that calls these; ``web/auth.py`` is the
only caller that knows about HTTP/cookies.

W5 retires W2's single env-configured SHA-256 operator credential: passwords now hash with
argon2id, a slow memory-hard KDF appropriate for a real, growing user table — the W2 module's
own docstring flagged "revisit if this ever becomes a real multi-user credential store," and
W5 is that revisit (``docs/phase_decisions/W5.md``). ``PasswordHasher`` embeds its own salt and
cost parameters inside the returned hash string, so no separate salt column is needed.

Session and password-reset tokens are a different problem with a different right answer:
they're already 256 bits of ``secrets``-grade randomness, not a low-entropy human password, so
hashing them for at-rest storage needs no memory-hard KDF — a fast SHA-256 is exactly right.
"""
from __future__ import annotations

import hashlib
import secrets

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError, VerifyMismatchError

_hasher = PasswordHasher()


def hash_password(password: str) -> str:
    """Argon2id hash of ``password`` — salted internally, non-deterministic across calls (two
    hashes of the same password never match byte-for-byte; ``verify_password`` is how you
    check one against the other)."""
    return _hasher.hash(password)


# A fixed, valid argon2id hash with no corresponding real account. src.auth.service.authenticate
# verifies against this when the email doesn't match any user, so an unknown email still pays
# the same KDF cost as a known one with a wrong password — otherwise the *response* is identical
# either way but the *latency* isn't, and a timing side-channel enumerates accounts even though
# the message never does (docs/phase_decisions/W5_review.md MINOR-1).
DUMMY_PASSWORD_HASH = hash_password("not-a-real-account-timing-parity-only")


def verify_password(password: str, password_hash: str) -> bool:
    """True iff ``password`` matches ``password_hash``. Never raises on a bad/foreign/corrupt
    hash — that is just "doesn't match," not a 500 (mirrors W2's non-ASCII-safe credential
    check, generalized to any malformed-input failure mode argon2 can raise)."""
    try:
        return _hasher.verify(password_hash, password)
    except (VerifyMismatchError, VerificationError, InvalidHashError):
        return False


def generate_token() -> str:
    """A high-entropy opaque token for session cookies / password-reset links: 32 random bytes,
    URL-safe text. The raw value is what the client holds (a cookie, a reset-link path
    segment); only its hash (``hash_token`` below) is ever persisted."""
    return secrets.token_urlsafe(32)


def hash_token(token: str) -> str:
    """SHA-256 hex digest, for at-rest storage of session/reset tokens — so a DB read, backup,
    or log line never yields a directly usable token. Not argon2: the input is already a
    uniform 256-bit random value, not a human password, so a KDF's deliberate slowness buys
    nothing here and would only slow down every request's session lookup."""
    return hashlib.sha256(token.encode("utf-8")).hexdigest()
