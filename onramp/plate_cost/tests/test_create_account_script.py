"""Tests for the invite-only account-creation CLI (scripts/create_account.py).

Covers: the happy path actually persists a working account (correctness — logs in
successfully afterward), mismatched password confirmation is rejected before anything is
written, and a too-short password is rejected the same way create_account() itself would
reject it (the script's own pre-check, so a chef never sees a raw ValueError traceback).
"""
import runpy
from pathlib import Path

import pytest

_SCRIPT_PATH = Path(__file__).resolve().parents[1] / "scripts" / "create_account.py"


def _load_main():
    """scripts/ has no __init__.py (deliberately — see the script's own docstring), so it's
    loaded by path rather than imported as a package module."""
    module = runpy.run_path(str(_SCRIPT_PATH), run_name="create_account_under_test")
    return module["main"]


@pytest.fixture()
def main(db_sessionmaker):
    return _load_main()


def test_create_account_script_persists_a_working_account(main, monkeypatch, capsys):
    passwords = iter(["s3cret123", "s3cret123"])
    monkeypatch.setattr("getpass.getpass", lambda prompt="": next(passwords))

    exit_code = main(["--restaurant", "Marco's Trattoria", "--email", "chef@example.com"])

    assert exit_code == 0
    assert "Created" in capsys.readouterr().out

    from src.auth.service import authenticate
    from src.db.engine import SessionLocal

    db = SessionLocal()
    try:
        assert authenticate(db, "chef@example.com", "s3cret123") is not None
    finally:
        db.close()


def test_create_account_script_rejects_mismatched_passwords(main, monkeypatch, capsys):
    passwords = iter(["s3cret123", "different456"])
    monkeypatch.setattr("getpass.getpass", lambda prompt="": next(passwords))

    exit_code = main(["--restaurant", "Marco's Trattoria", "--email", "chef@example.com"])

    assert exit_code == 1
    assert "did not match" in capsys.readouterr().err


def test_create_account_script_rejects_short_password(main, monkeypatch, capsys):
    passwords = iter(["short", "short"])
    monkeypatch.setattr("getpass.getpass", lambda prompt="": next(passwords))

    exit_code = main(["--restaurant", "Marco's Trattoria", "--email", "chef@example.com"])

    assert exit_code == 1
    assert "at least" in capsys.readouterr().err
