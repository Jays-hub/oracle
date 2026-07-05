"""Tests for the pure operator-credential check (src/auth/credentials.py).

Covers: correct credentials accepted, wrong username/password rejected, verification fails
CLOSED when unconfigured (no default/hardcoded credential to fall back to), and hash_password
is deterministic (same input always yields the same output — the "reproducibility" guard for
this phase, since there's no stochastic model here to seed).
"""
from src.auth.credentials import (
    PASSWORD_HASH_ENV,
    USERNAME_ENV,
    hash_password,
    verify_credentials,
)


def _set_credential(monkeypatch, username: str, password: str) -> None:
    monkeypatch.setenv(USERNAME_ENV, username)
    monkeypatch.setenv(PASSWORD_HASH_ENV, hash_password(password))


def test_correct_credentials_accepted(monkeypatch):
    _set_credential(monkeypatch, "chef", "s3cret")
    assert verify_credentials("chef", "s3cret") is True


def test_wrong_password_rejected(monkeypatch):
    _set_credential(monkeypatch, "chef", "s3cret")
    assert verify_credentials("chef", "wrong") is False


def test_wrong_username_rejected(monkeypatch):
    _set_credential(monkeypatch, "chef", "s3cret")
    assert verify_credentials("someone-else", "s3cret") is False


def test_fails_closed_when_env_unset(monkeypatch):
    """No configured credential means no login can ever succeed — never fall back to a
    hardcoded default (rule 07: secrets in env, never in code)."""
    monkeypatch.delenv(USERNAME_ENV, raising=False)
    monkeypatch.delenv(PASSWORD_HASH_ENV, raising=False)
    assert verify_credentials("anyone", "anything") is False
    assert verify_credentials("", "") is False


def test_fails_closed_when_only_username_configured(monkeypatch):
    monkeypatch.setenv(USERNAME_ENV, "chef")
    monkeypatch.delenv(PASSWORD_HASH_ENV, raising=False)
    assert verify_credentials("chef", "s3cret") is False


def test_non_ascii_username_rejected_not_raised(monkeypatch):
    """hmac.compare_digest raises TypeError on a non-ASCII str; the raw username must never
    reach it un-encoded (W2_review.md MAJOR-1 — this used to 500 instead of returning False)."""
    _set_credential(monkeypatch, "chef", "s3cret")
    assert verify_credentials("café", "s3cret") is False
    assert verify_credentials("chef", "wrong-café-password") is False


def test_hash_password_is_deterministic():
    assert hash_password("s3cret") == hash_password("s3cret")


def test_hash_password_differs_for_different_passwords():
    assert hash_password("s3cret") != hash_password("other")
