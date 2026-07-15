"""Tests for the W7 environment/production posture module (web/config.py)."""
import pytest

from web.config import ensure_production_config, ensure_safe_bind, is_production, resolve_tls_files


@pytest.fixture(autouse=True)
def _clean_env(monkeypatch):
    for var in (
        "ONRAMP_ENV", "ONRAMP_DATABASE_URL", "ONRAMP_SMTP_HOST",
        "ONRAMP_TLS_CERTFILE", "ONRAMP_TLS_KEYFILE",
    ):
        monkeypatch.delenv(var, raising=False)


def test_is_production_false_by_default():
    assert is_production() is False


def test_is_production_true_when_env_set(monkeypatch):
    monkeypatch.setenv("ONRAMP_ENV", "production")
    assert is_production() is True


def test_is_production_false_for_any_other_value(monkeypatch):
    monkeypatch.setenv("ONRAMP_ENV", "staging")
    assert is_production() is False


def test_ensure_production_config_is_a_noop_in_development():
    ensure_production_config()  # must not raise even with nothing else configured


def test_ensure_production_config_raises_when_database_url_missing(monkeypatch):
    monkeypatch.setenv("ONRAMP_ENV", "production")
    monkeypatch.setenv("ONRAMP_SMTP_HOST", "smtp.example.com")
    with pytest.raises(SystemExit, match="ONRAMP_DATABASE_URL"):
        ensure_production_config()


def test_ensure_production_config_raises_when_smtp_host_missing(monkeypatch):
    monkeypatch.setenv("ONRAMP_ENV", "production")
    monkeypatch.setenv("ONRAMP_DATABASE_URL", "sqlite:////var/lib/onramp/onramp.db")
    with pytest.raises(SystemExit, match="ONRAMP_SMTP_HOST"):
        ensure_production_config()


def test_ensure_production_config_passes_when_fully_configured(monkeypatch):
    monkeypatch.setenv("ONRAMP_ENV", "production")
    monkeypatch.setenv("ONRAMP_DATABASE_URL", "sqlite:////var/lib/onramp/onramp.db")
    monkeypatch.setenv("ONRAMP_SMTP_HOST", "smtp.example.com")
    ensure_production_config()  # must not raise


def test_resolve_tls_files_returns_none_none_when_unset():
    assert resolve_tls_files() == (None, None)


def test_resolve_tls_files_returns_both_when_both_set(monkeypatch):
    monkeypatch.setenv("ONRAMP_TLS_CERTFILE", "/etc/ssl/cert.pem")
    monkeypatch.setenv("ONRAMP_TLS_KEYFILE", "/etc/ssl/key.pem")
    assert resolve_tls_files() == ("/etc/ssl/cert.pem", "/etc/ssl/key.pem")


@pytest.mark.parametrize("set_var", ["ONRAMP_TLS_CERTFILE", "ONRAMP_TLS_KEYFILE"])
def test_resolve_tls_files_raises_when_only_one_is_set(monkeypatch, set_var):
    monkeypatch.setenv(set_var, "/etc/ssl/only-one.pem")
    with pytest.raises(SystemExit, match="must both be set"):
        resolve_tls_files()


def test_ensure_safe_bind_allows_loopback_without_tls():
    ensure_safe_bind("127.0.0.1", None)  # must not raise
    ensure_safe_bind("localhost", None)  # must not raise


def test_ensure_safe_bind_allows_non_loopback_with_tls():
    ensure_safe_bind("0.0.0.0", "/etc/ssl/cert.pem")  # must not raise


def test_ensure_safe_bind_refuses_non_loopback_without_tls():
    with pytest.raises(SystemExit, match="Refusing to bind"):
        ensure_safe_bind("0.0.0.0", None)
