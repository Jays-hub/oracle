"""Staged-upload persistence (W5) — replaces W1-W4's hidden-base64-form-field round trip.

A ``/confirm`` POST used to carry the raw uploaded bytes *back to the server itself* (base64
in a hidden form field, re-decoded and re-validated on arrival). W5 moves that payload
server-side into the ``staged_uploads`` table instead: the client only ever holds an opaque
row id. DB-aware but framework-agnostic (rule 05 — no FastAPI import), mirroring
``src/auth/service.py``'s split from ``web/auth.py``.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from sqlalchemy import update
from sqlalchemy.orm import Session as DbSession

from ..db.models import StagedUpload

# A ~15-25 item recipe sitdown or a single invoice review takes minutes, not hours; 30 minutes
# is generous headroom for a chef who gets pulled away mid-review without leaving stale rows
# accumulating for days (there is no cleanup job yet — see docs/phase_decisions/W5.md deferred).
STAGING_TTL = timedelta(minutes=30)


def _utcnow() -> datetime:
    """Naive datetime representing the current UTC instant — matches src/db/models.py::_utcnow
    exactly (see that docstring): SQLite round-trips a stored DateTime as naive, so every
    timestamp this module stores or compares must be naive-but-UTC too."""
    return datetime.now(timezone.utc).replace(tzinfo=None)


def stage_upload(
    db: DbSession, user_id: str, restaurant_id: str, kind: str, payload: dict[str, str]
) -> str:
    """Persists ``payload`` (base64-encoded file contents, keyed by the same field names the
    old hidden inputs used) and returns the new row's id — the only thing the confirm page's
    hidden field carries now."""
    row = StagedUpload(
        user_id=user_id,
        restaurant_id=restaurant_id,
        kind=kind,
        payload=payload,
        expires_at=_utcnow() + STAGING_TTL,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return row.id


def take_staged_upload(
    db: DbSession, upload_id: str, user_id: str, kind: str
) -> dict[str, str] | None:
    """Returns and consumes (marks used) the payload for ``upload_id`` iff it exists, belongs
    to ``user_id``, matches ``kind``, hasn't expired, and hasn't already been consumed —
    otherwise ``None``. Single-use: a replayed ``/confirm`` POST with the same id fails past
    this point instead of silently re-writing the seam a second time. The ownership check
    (``row.user_id != user_id``) means a guessed-or-leaked id from a different account is
    treated identically to a nonexistent one (rule 07: AuthZ on every data path, not just
    AuthN) — this function never tells the caller *which* check failed.

    Consumption itself is one atomic conditional ``UPDATE ... WHERE consumed_at IS NULL``, not
    a read-check-write: two genuinely concurrent calls for the same id can both pass the
    ownership/kind/expiry read below (those fields never mutate after creation), but only one
    can ever flip ``consumed_at`` from NULL — the loser's ``UPDATE`` matches zero rows and gets
    ``None`` back, instead of both callers believing they won the single use (which would
    double-write the seam; ``docs/phase_decisions/W5_review.md`` LOW-1).
    """
    row = db.get(StagedUpload, upload_id)
    if row is None or row.user_id != user_id or row.kind != kind or row.expires_at <= _utcnow():
        return None
    result = db.execute(
        update(StagedUpload)
        .where(StagedUpload.id == upload_id, StagedUpload.consumed_at.is_(None))
        .values(consumed_at=_utcnow())
        .execution_options(synchronize_session=False)
    )
    db.commit()
    if result.rowcount != 1:
        return None
    return row.payload
