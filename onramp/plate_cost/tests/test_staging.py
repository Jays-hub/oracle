"""Tests for staged-upload persistence (src/capture/staging.py) — the W5 replacement for
W1-W4's hidden-base64-form-field round trip.

Covers: a staged payload round-trips exactly (correctness), it is single-use (a second take
after consumption returns None — the property that keeps a replayed /confirm from silently
re-writing the seam), the two identity/kind mismatches AuthZ actually depends on: a
different user's id can't take someone else's staged upload, and the wrong ``kind`` can't be
substituted in (a bom_sales payload confirmed through the invoice path, or vice versa) — and
that consumption is genuinely atomic under real concurrent access (W5_review.md LOW-1), not
just sequential replay.
"""
import threading

import pytest
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker

from src.capture.staging import take_staged_upload, stage_upload
from src.db.models import Base


@pytest.fixture()
def db(db_sessionmaker):
    session = db_sessionmaker()
    yield session
    session.close()


def test_stage_and_take_round_trips_the_exact_payload(db):
    payload = {"sales_csv_b64": "abc", "bom_csv_b64": "def"}
    staged_id = stage_upload(db, "user-1", "restaurant-1", kind="bom_sales", payload=payload)

    taken = take_staged_upload(db, staged_id, "user-1", kind="bom_sales")
    assert taken == payload


def test_take_is_single_use(db):
    staged_id = stage_upload(db, "user-1", "restaurant-1", kind="invoice", payload={"invoice_csv_b64": "x"})

    first = take_staged_upload(db, staged_id, "user-1", kind="invoice")
    second = take_staged_upload(db, staged_id, "user-1", kind="invoice")

    assert first is not None
    assert second is None  # already consumed — a replayed /confirm must not re-fetch it


def test_take_rejects_wrong_owner(db):
    staged_id = stage_upload(db, "user-1", "restaurant-1", kind="bom_sales", payload={"a": "b"})
    assert take_staged_upload(db, staged_id, "someone-else", kind="bom_sales") is None


def test_take_rejects_wrong_kind(db):
    staged_id = stage_upload(db, "user-1", "restaurant-1", kind="bom_sales", payload={"a": "b"})
    assert take_staged_upload(db, staged_id, "user-1", kind="invoice") is None


def test_take_rejects_unknown_id(db):
    assert take_staged_upload(db, "not-a-real-id", "user-1", kind="bom_sales") is None


def test_take_staged_upload_is_atomic_under_concurrent_race(tmp_path):
    """Reproduces the concurrent double-submit the read-check-write version couldn't survive:
    several real threads, each with its own Session, race to take the same staged upload. A
    dedicated engine (not the shared conftest one) with a busy-timeout PRAGMA so concurrent
    SQLite writers retry instead of raising ``database is locked``. Exactly one thread may win."""
    engine = create_engine(
        f"sqlite:///{tmp_path / 'staging_race.db'}", connect_args={"check_same_thread": False}
    )

    @event.listens_for(engine, "connect")
    def _set_busy_timeout(dbapi_connection, _connection_record):
        dbapi_connection.execute("PRAGMA busy_timeout = 5000")

    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)

    seed = factory()
    staged_id = stage_upload(
        seed, "user-1", "restaurant-1", kind="invoice", payload={"invoice_csv_b64": "x"}
    )
    seed.close()

    results: list[dict[str, str] | None] = []

    def worker() -> None:
        session = factory()
        try:
            results.append(take_staged_upload(session, staged_id, "user-1", kind="invoice"))
        finally:
            session.close()

    threads = [threading.Thread(target=worker) for _ in range(8)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    engine.dispose()

    assert sum(1 for r in results if r is not None) == 1
