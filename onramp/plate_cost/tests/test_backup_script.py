"""Tests for the W7 backup script (scripts/backup.py) — app-DB snapshot + data/raw copy.

scripts/ has no __init__.py (deliberately — same convention test_create_account_script.py
documents), so the module is loaded by path rather than imported as a package module.
"""
import runpy
import sqlite3
from pathlib import Path

import pandas as pd
import pytest

_SCRIPT_PATH = Path(__file__).resolve().parents[1] / "scripts" / "backup.py"


@pytest.fixture()
def backup_mod():
    return runpy.run_path(str(_SCRIPT_PATH), run_name="backup_under_test")


def _make_sqlite_db(path: Path) -> None:
    conn = sqlite3.connect(str(path))
    conn.execute("CREATE TABLE users (id TEXT PRIMARY KEY, email TEXT)")
    conn.execute("INSERT INTO users VALUES ('u1', 'chef@example.com')")
    conn.commit()
    conn.close()


def test_backup_app_db_writes_a_readable_snapshot(backup_mod, tmp_path):
    source_db = tmp_path / "source.db"
    _make_sqlite_db(source_db)
    destination = tmp_path / "snapshot"

    result_path = backup_mod["backup_app_db"](destination, database_url=f"sqlite:///{source_db}")

    assert result_path == destination / "app.db"
    assert result_path.exists()
    conn = sqlite3.connect(str(result_path))
    rows = conn.execute("SELECT email FROM users").fetchall()
    conn.close()
    assert rows == [("chef@example.com",)]


def test_backup_app_db_is_independent_of_the_source_after_the_fact(backup_mod, tmp_path):
    """A real backup, not a hardlink/reference -- mutating the source afterward must not
    change the already-written snapshot."""
    source_db = tmp_path / "source.db"
    _make_sqlite_db(source_db)
    destination = tmp_path / "snapshot"
    result_path = backup_mod["backup_app_db"](destination, database_url=f"sqlite:///{source_db}")

    conn = sqlite3.connect(str(source_db))
    conn.execute("INSERT INTO users VALUES ('u2', 'new@example.com')")
    conn.commit()
    conn.close()

    snap_conn = sqlite3.connect(str(result_path))
    rows = snap_conn.execute("SELECT email FROM users").fetchall()
    snap_conn.close()
    assert rows == [("chef@example.com",)]  # the later insert never reached the snapshot


def test_backup_app_db_returns_none_for_a_non_sqlite_url(backup_mod, tmp_path):
    result = backup_mod["backup_app_db"](tmp_path / "snapshot", database_url="postgresql://host/db")
    assert result is None


def test_backup_app_db_raises_when_the_source_file_is_missing(backup_mod, tmp_path):
    with pytest.raises(FileNotFoundError):
        backup_mod["backup_app_db"](tmp_path / "snapshot", database_url=f"sqlite:///{tmp_path / 'nope.db'}")


def test_backup_raw_dir_copies_every_seam_file(backup_mod, tmp_path):
    raw_dir = tmp_path / "raw"
    raw_dir.mkdir()
    pd.DataFrame({"a": [1]}).to_parquet(raw_dir / "bom.parquet", index=False, engine="pyarrow")
    pd.DataFrame({"a": [2]}).to_parquet(raw_dir / "sales_export.parquet", index=False, engine="pyarrow")
    destination = tmp_path / "snapshot"

    dest_raw = backup_mod["backup_raw_dir"](destination, raw_dir=raw_dir)

    assert dest_raw == destination / "raw"
    assert (dest_raw / "bom.parquet").exists()
    assert (dest_raw / "sales_export.parquet").exists()
    assert pd.read_parquet(dest_raw / "bom.parquet")["a"].iloc[0] == 1


def test_backup_raw_dir_produces_an_empty_but_present_directory_when_seam_is_empty(backup_mod, tmp_path):
    raw_dir = tmp_path / "raw"
    raw_dir.mkdir()
    destination = tmp_path / "snapshot"

    dest_raw = backup_mod["backup_raw_dir"](destination, raw_dir=raw_dir)

    assert dest_raw.exists()
    assert list(dest_raw.iterdir()) == []


def test_run_backup_creates_a_fresh_timestamped_subdirectory(backup_mod, tmp_path, monkeypatch):
    """run_backup() with only backup_root given falls back to resolve_database_url()/RAW_DIR
    for the other two inputs. ONRAMP_DATABASE_URL is set so it resolves to an isolated tmp DB;
    the module's own RAW_DIR binding is swapped for an isolated tmp dir the same way
    test_web_upload.py etc. monkeypatch src.store.RAW_DIR -- never the real data/raw/."""
    source_db = tmp_path / "source.db"
    _make_sqlite_db(source_db)
    monkeypatch.setenv("ONRAMP_DATABASE_URL", f"sqlite:///{source_db}")
    isolated_raw_dir = tmp_path / "raw"
    isolated_raw_dir.mkdir()
    backup_mod["RAW_DIR"] = isolated_raw_dir

    backup_root = tmp_path / "backups"
    snapshot_dir = backup_mod["run_backup"](backup_root)

    assert snapshot_dir.parent == backup_root
    assert (snapshot_dir / "app.db").exists()
    assert (snapshot_dir / "raw").exists()


def test_resolve_backup_dir_uses_env_override(backup_mod, monkeypatch, tmp_path):
    monkeypatch.setenv("ONRAMP_BACKUP_DIR", str(tmp_path / "custom"))
    assert backup_mod["resolve_backup_dir"]() == tmp_path / "custom"


def test_resolve_backup_dir_defaults_under_instance(backup_mod, monkeypatch):
    monkeypatch.delenv("ONRAMP_BACKUP_DIR", raising=False)
    result = backup_mod["resolve_backup_dir"]()
    assert result.parts[-2:] == ("instance", "backups")


def test_main_prints_the_snapshot_path(backup_mod, tmp_path, monkeypatch, capsys):
    source_db = tmp_path / "source.db"
    _make_sqlite_db(source_db)
    monkeypatch.setenv("ONRAMP_DATABASE_URL", f"sqlite:///{source_db}")
    monkeypatch.setenv("ONRAMP_BACKUP_DIR", str(tmp_path / "backups"))
    backup_mod["RAW_DIR"] = tmp_path / "raw"  # isolated -- never the real data/raw/
    backup_mod["RAW_DIR"].mkdir()

    exit_code = backup_mod["main"]([])

    assert exit_code == 0
    assert "Backup written to" in capsys.readouterr().out
