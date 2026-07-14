"""Tests for the pure password/token cryptography (src/auth/credentials.py).

Covers: a correct password verifies, a wrong one doesn't, verification never raises on a
corrupt/foreign hash (fails closed as a clean False, not a 500), hashing is salted (two hashes
of the same password differ — the correctness property that replaces W2's sha256
"hash_password is deterministic" test, since argon2 must NOT be deterministic), and
verify_password is nonetheless repeatable given a fixed hash (the "same seed twice -> identical
result" reproducibility guard, translated to this phase's actual stochastic component: salted
hashing). Token generation/hashing get their own correctness + determinism checks.
"""
from src.auth.credentials import generate_token, hash_password, hash_token, verify_password


def test_correct_password_verifies():
    hashed = hash_password("s3cret")
    assert verify_password("s3cret", hashed) is True


def test_wrong_password_rejected():
    hashed = hash_password("s3cret")
    assert verify_password("wrong", hashed) is False


def test_verify_never_raises_on_a_corrupt_hash():
    """A malformed/foreign hash string (e.g. a stale sha256 hex digest from before W5, or plain
    garbage) must be reported as "doesn't match," never crash the caller."""
    assert verify_password("s3cret", "not-an-argon2-hash") is False
    assert verify_password("s3cret", "") is False


def test_hash_password_is_salted_not_deterministic():
    """Two hashes of the SAME password must differ — argon2's embedded random salt is what
    makes a stolen hash table useless for a rainbow-table lookup. (The opposite property from
    W2's retired sha256 hash_password, which was deliberately deterministic.)"""
    assert hash_password("s3cret") != hash_password("s3cret")


def test_verify_password_is_repeatable_given_a_fixed_hash():
    """Reproducibility guard: checking the same (password, hash) pair twice always agrees —
    the salt lives inside the hash string, so re-verification is deterministic even though
    hashing itself is not."""
    hashed = hash_password("s3cret")
    assert verify_password("s3cret", hashed) == verify_password("s3cret", hashed) is True


def test_generate_token_is_unique_and_url_safe():
    a, b = generate_token(), generate_token()
    assert a != b
    assert all(c.isalnum() or c in "-_" for c in a)


def test_hash_token_is_deterministic_and_distinguishes_inputs():
    token = generate_token()
    assert hash_token(token) == hash_token(token)
    assert hash_token(token) != hash_token(generate_token())
