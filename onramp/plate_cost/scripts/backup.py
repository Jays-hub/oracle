#!/usr/bin/env python
"""Snapshot the app DB + seam data (W7) — ``docs/website_production_overview.md`` row 4 ("backups
(app DB + data/raw)").

Two independent artifacts a real deploy needs before hosting past localhost:
  1. A **consistent** copy of the on-ramp app DB (``ONRAMP_DATABASE_URL``) — SQLite's own online
     backup API, not a raw file copy (which could catch a connection mid-write and copy a
     torn page).
  2. A copy of every file under ``data/raw/`` (the seam) — the engine's only input, and the one
     artifact this on-ramp captures that has no other durable copy anywhere.

Writes into ``ONRAMP_BACKUP_DIR/<UTC timestamp>/``. **Local disk only**: this script does the
snapshot mechanics; shipping the result off-box (object storage, a second region, ...) is a
real deploy's job and needs real infra credentials this environment doesn't have — see
``docs/phase_decisions/W7.md`` Explicitly Deferred. Run from ``onramp/plate_cost/``::

    python scripts/backup.py
"""
from __future__ import annotations

import os
import shutil
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path

_PLATE_COST_DIR = Path(__file__).resolve().parents[1]
if str(_PLATE_COST_DIR) not in sys.path:
    sys.path.insert(0, str(_PLATE_COST_DIR))

from src.db.engine import resolve_database_url  # noqa: E402
from src.store import RAW_DIR  # noqa: E402

BACKUP_DIR_ENV = "ONRAMP_BACKUP_DIR"
_DEFAULT_BACKUP_DIR = _PLATE_COST_DIR / "instance" / "backups"

_SQLITE_PREFIX = "sqlite:///"


def resolve_backup_dir() -> Path:
    configured = os.environ.get(BACKUP_DIR_ENV)
    return Path(configured) if configured else _DEFAULT_BACKUP_DIR


def backup_app_db(destination: Path, database_url: str | None = None) -> Path | None:
    """Writes a consistent snapshot of the SQLite app DB to ``destination/app.db`` via
    SQLite's online backup API (``sqlite3.Connection.backup`` — safe to run against a live,
    in-use database, unlike ``shutil.copy``). Returns ``None`` — not an error — if the
    configured database isn't SQLite: a Postgres backup is the hosting platform's job (managed
    snapshots / ``pg_dump``), not this script's (the swap is recorded, not executed, this
    phase — ``docs/phase_decisions/W7.md``)."""
    url = database_url or resolve_database_url()
    if not url.startswith(_SQLITE_PREFIX):
        return None
    source_path = Path(url[len(_SQLITE_PREFIX):])
    if not source_path.exists():
        raise FileNotFoundError(f"app DB not found at {source_path}")

    destination.mkdir(parents=True, exist_ok=True)
    dest_path = destination / "app.db"
    source_conn = sqlite3.connect(str(source_path))
    dest_conn = sqlite3.connect(str(dest_path))
    try:
        source_conn.backup(dest_conn)
    finally:
        dest_conn.close()
        source_conn.close()
    return dest_path


def backup_raw_dir(destination: Path, raw_dir: Path | None = None) -> Path:
    """Copies every file directly under ``data/raw/`` (a flat directory — ``data/CONTRACT.md``)
    into ``destination/raw/``. Returns that directory, created even when the seam is empty, so
    an empty ``data/raw/`` produces a legible zero-file backup rather than a missing one."""
    source = raw_dir or RAW_DIR
    dest_raw = destination / "raw"
    dest_raw.mkdir(parents=True, exist_ok=True)
    if source.exists():
        for item in source.iterdir():
            if item.is_file():
                shutil.copy2(item, dest_raw / item.name)
    return dest_raw


def run_backup(backup_root: Path | None = None) -> Path:
    """Runs both backups into a fresh UTC-timestamped subdirectory of ``backup_root``
    (``resolve_backup_dir()`` if unset) and returns that subdirectory."""
    root = backup_root or resolve_backup_dir()
    snapshot_dir = root / datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    backup_app_db(snapshot_dir)
    backup_raw_dir(snapshot_dir)
    return snapshot_dir


def main(argv: list[str] | None = None) -> int:
    snapshot_dir = run_backup()
    print(f"Backup written to {snapshot_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
