"""Tests for the W7 SMTP email transport (src/email/sender.py).

Every test explicitly clears the ONRAMP_SMTP_* env vars first (monkeypatch.delenv) so this
suite behaves identically whether or not the machine running it happens to have them set.
"""
import smtplib

import pytest

from src.email.sender import is_configured, send_password_reset_email

_ENV_VARS = [
    "ONRAMP_SMTP_HOST", "ONRAMP_SMTP_PORT", "ONRAMP_SMTP_USERNAME",
    "ONRAMP_SMTP_PASSWORD", "ONRAMP_SMTP_FROM",
]


@pytest.fixture(autouse=True)
def _clean_smtp_env(monkeypatch):
    for var in _ENV_VARS:
        monkeypatch.delenv(var, raising=False)


class _FakeSMTP:
    """Records what would have been sent, without touching a network."""

    instances: list["_FakeSMTP"] = []

    def __init__(self, host, port, timeout=None):
        self.host = host
        self.port = port
        self.started_tls = False
        self.login_args = None
        self.sent_message = None
        _FakeSMTP.instances.append(self)

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def starttls(self):
        self.started_tls = True

    def login(self, username, password):
        self.login_args = (username, password)

    def send_message(self, message):
        self.sent_message = message


@pytest.fixture(autouse=True)
def _reset_fake_smtp():
    _FakeSMTP.instances.clear()
    yield


def test_is_configured_false_when_no_host_set():
    assert is_configured() is False


def test_is_configured_true_when_host_set(monkeypatch):
    monkeypatch.setenv("ONRAMP_SMTP_HOST", "smtp.example.com")
    assert is_configured() is True


def test_send_returns_false_and_makes_no_network_call_when_unconfigured(monkeypatch):
    monkeypatch.setattr(smtplib, "SMTP", _FakeSMTP)
    result = send_password_reset_email("chef@example.com", "https://example.com/reset-password/tok")
    assert result is False
    assert _FakeSMTP.instances == []


def test_send_delivers_via_smtp_when_configured(monkeypatch):
    monkeypatch.setenv("ONRAMP_SMTP_HOST", "smtp.example.com")
    monkeypatch.setenv("ONRAMP_SMTP_PORT", "2525")
    monkeypatch.setenv("ONRAMP_SMTP_USERNAME", "apikey")
    monkeypatch.setenv("ONRAMP_SMTP_PASSWORD", "secret")
    monkeypatch.setattr(smtplib, "SMTP", _FakeSMTP)

    result = send_password_reset_email("chef@example.com", "https://example.com/reset-password/tok123")

    assert result is True
    assert len(_FakeSMTP.instances) == 1
    fake = _FakeSMTP.instances[0]
    assert fake.host == "smtp.example.com"
    assert fake.port == 2525
    assert fake.started_tls is True
    assert fake.login_args == ("apikey", "secret")
    assert fake.sent_message["To"] == "chef@example.com"
    assert "reset-password/tok123" in fake.sent_message.get_content()


def test_send_does_not_login_when_no_credentials_configured(monkeypatch):
    monkeypatch.setenv("ONRAMP_SMTP_HOST", "smtp.example.com")
    monkeypatch.setattr(smtplib, "SMTP", _FakeSMTP)

    send_password_reset_email("chef@example.com", "https://example.com/reset-password/tok")

    assert _FakeSMTP.instances[0].login_args is None


def test_send_raises_on_smtp_failure_rather_than_silently_falling_back(monkeypatch):
    """A misconfigured production deploy must fail loudly, never quietly revert to logging the
    raw token — silently swallowing this would resurrect the exact risk this phase closes."""
    class _BrokenSMTP(_FakeSMTP):
        def send_message(self, message):
            raise smtplib.SMTPException("connection refused")

    monkeypatch.setenv("ONRAMP_SMTP_HOST", "smtp.example.com")
    monkeypatch.setattr(smtplib, "SMTP", _BrokenSMTP)

    with pytest.raises(smtplib.SMTPException):
        send_password_reset_email("chef@example.com", "https://example.com/reset-password/tok")
