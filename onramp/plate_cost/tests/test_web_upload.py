"""Tests for the W1 capture-funnel web routes (GET/POST /upload, POST /confirm).

Every test that writes monkeypatches src.store.RAW_DIR to a tmp_path — the single canonical seam
directory both the read and write paths reference (W3_review.md LOW-1 collapsed the previous
write-side web.app._RAW_DIR copy into this one shared constant) — never the real data/raw/.
Covers: the happy path end-to-end (and that it actually lands schema-valid Parquet), validation
errors surfaced without a crash, the cross-file mismatch warning, the size-limit boundary, and that
/confirm re-validates rather than trusting the staged payload.

W2 added a login gate in front of these routes (test_web_auth.py owns that behavior). W5 added a
real identity behind that gate (a staged upload is owned by a user/restaurant id). These tests
are about upload/confirm logic, not auth/identity, so an autouse fixture bypasses both with a
fixed fake identity — mirrors how test_web.py's grid tests don't re-verify plate-cost math that
src/pricing/ already covers.
"""
import re
from base64 import b64encode
from datetime import datetime, timedelta, timezone

import pandas as pd
import pytest
from fastapi.testclient import TestClient

import src.store as store_mod
import web.app as appmod
from schemas import BomRow, SalesExportRow
from src.auth.service import Identity
from src.db.models import StagedUpload
from web.app import app

_client = TestClient(app)

_FAKE_IDENTITY = Identity(
    session_id="s1", user_id="u1", email="chef@example.com",
    restaurant_id="r1", restaurant_name="Test Kitchen",
)


@pytest.fixture(autouse=True)
def _bypass_login(monkeypatch):
    monkeypatch.setattr(appmod, "require_login", lambda request, db: None)
    monkeypatch.setattr(appmod, "current_identity", lambda request, db: _FAKE_IDENTITY)


_VALID_SALES = (
    b"dish_name,count,period_start,period_end\n"
    b"Burger,120,2026-06-01,2026-06-07\n"
    b"Salad,40,2026-06-01,2026-06-07\n"
)
_VALID_BOM = (
    b"dish_name,ingredient_name,qty,recipe_unit,canonical_unit,yield_factor\n"
    b"Burger,beef patty,6,oz,oz,0.9\n"
    b"Salad,romaine,4,oz,oz,0.85\n"
)


def _post_upload(sales=_VALID_SALES, bom=_VALID_BOM):
    return _client.post(
        "/upload",
        files={
            "sales_file": ("sales.csv", sales, "text/csv"),
            "bom_file": ("bom.csv", bom, "text/csv"),
        },
    )


def _extract_staged_upload_id(html: str) -> str:
    m = re.search(r'name="staged_upload_id" value="([^"]*)"', html)
    assert m, "confirm page is missing the staged_upload_id hidden field"
    return m.group(1)


def _stage_row_directly(db_sessionmaker, payload: dict[str, str]) -> str:
    """Seeds a staged_uploads row directly through the DB, bypassing /upload entirely — used to
    prove /confirm re-validates whatever it finds staged rather than trusting it, now that a
    client can no longer submit the payload bytes itself (only an opaque id)."""
    db = db_sessionmaker()
    try:
        row = StagedUpload(
            user_id=_FAKE_IDENTITY.user_id,
            restaurant_id=_FAKE_IDENTITY.restaurant_id,
            kind="bom_sales",
            payload=payload,
            expires_at=datetime.now(timezone.utc) + timedelta(minutes=30),
        )
        db.add(row)
        db.commit()
        db.refresh(row)
        return row.id
    finally:
        db.close()


def _stage_bom_sales_directly(db_sessionmaker, sales=_VALID_SALES, bom=_VALID_BOM) -> str:
    return _stage_row_directly(db_sessionmaker, {
        "sales_csv_b64": b64encode(sales).decode("ascii"),
        "bom_csv_b64": b64encode(bom).decode("ascii"),
    })


def test_upload_form_returns_200():
    resp = _client.get("/upload")
    assert resp.status_code == 200
    assert "sales_file" in resp.text
    assert "bom_file" in resp.text


def test_capture_funnel_pages_never_show_the_sample_data_banner(tmp_path, monkeypatch):
    """Regression for the review's MAJOR finding: the grid's "Sample data — illustrative only,
    not your restaurant's numbers" banner must never appear on a page showing the operator's OWN
    uploaded data — the confirm and success pages show real dish names and covers pulled straight
    from the chef's files, and the banner directly contradicted that."""
    monkeypatch.setattr(store_mod, "RAW_DIR", tmp_path)

    upload_form_resp = _client.get("/upload")
    upload_resp = _post_upload()
    staged_id = _extract_staged_upload_id(upload_resp.text)
    confirm_resp = _client.post("/confirm", data={"staged_upload_id": staged_id})

    for resp in (upload_form_resp, upload_resp, confirm_resp):
        assert "sample-banner" not in resp.text

    # The grid at / is unrelated sample data and must keep showing the banner (rule 06).
    grid_resp = _client.get("/")
    assert "sample-banner" in grid_resp.text


def test_upload_valid_files_shows_confirm_summary():
    resp = _post_upload()
    assert resp.status_code == 200
    assert "2" in resp.text  # dish_count
    assert "Burger" in resp.text and "Salad" in resp.text


def test_upload_missing_column_returns_422_with_named_error():
    resp = _post_upload(sales=b"dish_name,count\nBurger,10\n")
    assert resp.status_code == 422
    assert "period_start" in resp.text


def test_upload_row_error_is_named_not_a_stack_trace():
    bad_sales = (
        b"dish_name,count,period_start,period_end\n"
        b"Burger,-5,2026-06-01,2026-06-07\n"
    )
    resp = _post_upload(sales=bad_sales)
    assert resp.status_code == 422
    assert "Traceback" not in resp.text
    assert "Burger" in resp.text


def test_upload_oversized_file_rejected_before_parsing(monkeypatch):
    monkeypatch.setattr(appmod, "MAX_UPLOAD_BYTES", 10)
    resp = _post_upload()
    assert resp.status_code == 422
    assert "too large" in resp.text.lower()


def test_upload_cross_file_mismatch_is_surfaced_as_a_warning():
    sales_with_extra = (
        b"dish_name,count,period_start,period_end\n"
        b"Burger,120,2026-06-01,2026-06-07\n"
        b"Soup,15,2026-06-01,2026-06-07\n"
    )
    resp = _post_upload(sales=sales_with_extra)
    assert resp.status_code == 200
    assert "Soup" in resp.text


def test_confirm_writes_schema_valid_seam_files(tmp_path, monkeypatch):
    """The end-to-end path: upload -> confirm actually lands Parquet that satisfies the seam
    schema, in an isolated tmp_path (never the real data/raw/)."""
    monkeypatch.setattr(store_mod, "RAW_DIR", tmp_path)

    upload_resp = _post_upload()
    staged_id = _extract_staged_upload_id(upload_resp.text)

    confirm_resp = _client.post("/confirm", data={"staged_upload_id": staged_id})
    assert confirm_resp.status_code == 200
    assert "Saved" in confirm_resp.text

    bom_df = pd.read_parquet(tmp_path / "r1" / "bom.parquet")
    sales_df = pd.read_parquet(tmp_path / "r1" / "sales_export.parquet")
    assert len(bom_df) == 2
    assert len(sales_df) == 2
    BomRow(**{k: bom_df[k].iloc[0] for k in BomRow.model_fields})
    SalesExportRow(**{k: sales_df[k].iloc[0] for k in SalesExportRow.model_fields})


def test_confirm_is_single_use(tmp_path, monkeypatch):
    """W5: a replayed /confirm POST with the same staged_upload_id must not re-write the seam a
    second time — the staging row is consumed on first use."""
    monkeypatch.setattr(store_mod, "RAW_DIR", tmp_path)

    upload_resp = _post_upload()
    staged_id = _extract_staged_upload_id(upload_resp.text)

    first = _client.post("/confirm", data={"staged_upload_id": staged_id})
    second = _client.post("/confirm", data={"staged_upload_id": staged_id})

    assert first.status_code == 200
    assert second.status_code == 400


def test_confirm_never_touches_real_raw_dir_when_isolated(tmp_path, monkeypatch):
    """Sanity check on the test isolation itself: confirming against a monkeypatched RAW_DIR
    must not also write the real seam (guards against a future refactor re-introducing a
    hard-coded path that bypasses the isolation).

    data/raw/ is gitignored, so a fresh checkout (e.g. CI) has no bom.parquet at all — this must
    hold whether or not the real file happens to exist locally from a prior `python -m src.run`."""
    real_bom = store_mod.RAW_DIR / "r1" / "bom.parquet"  # captured BEFORE patching — the real, unpatched path
    existed_before = real_bom.exists()
    mtime_before = real_bom.stat().st_mtime if existed_before else None

    monkeypatch.setattr(store_mod, "RAW_DIR", tmp_path)

    upload_resp = _post_upload()
    staged_id = _extract_staged_upload_id(upload_resp.text)
    _client.post("/confirm", data={"staged_upload_id": staged_id})

    assert real_bom.exists() == existed_before
    if existed_before:
        assert real_bom.stat().st_mtime == mtime_before


def test_confirm_rejects_tampered_staged_payload_never_trusts_it(tmp_path, monkeypatch, db_sessionmaker):
    """Rule 07: /confirm must re-validate, not blindly trust the staged payload. Seed a staged
    row directly (bypassing /upload) whose bytes decode to CSV content failing schema
    validation, and confirm it is rejected rather than written."""
    monkeypatch.setattr(store_mod, "RAW_DIR", tmp_path)
    tampered_sales = b"dish_name,count,period_start,period_end\nBurger,-999,2026-06-01,2026-06-07\n"
    staged_id = _stage_bom_sales_directly(db_sessionmaker, sales=tampered_sales, bom=_VALID_BOM)

    resp = _client.post("/confirm", data={"staged_upload_id": staged_id})
    assert resp.status_code == 400
    assert not (tmp_path / "r1" / "bom.parquet").exists()
    assert not (tmp_path / "r1" / "sales_export.parquet").exists()


def test_confirm_rejects_unknown_staged_upload_id():
    resp = _client.post("/confirm", data={"staged_upload_id": "not-a-real-id"})
    assert resp.status_code == 400
    assert "Traceback" not in resp.text


def test_confirm_rejects_malformed_base64_in_staged_payload(db_sessionmaker):
    """Distinct failure mode from a schema-invalid CSV: the staged payload itself isn't valid
    base64 at all (binascii.Error, not a ValidationError) — must still fail legibly, not crash."""
    staged_id = _stage_row_directly(db_sessionmaker, {
        "sales_csv_b64": "not-valid-base64!!!", "bom_csv_b64": "also-bad!!!",
    })
    resp = _client.post("/confirm", data={"staged_upload_id": staged_id})
    assert resp.status_code == 400
    assert "Traceback" not in resp.text


def test_confirm_enforces_its_own_size_limit_without_going_through_upload(tmp_path, monkeypatch, db_sessionmaker):
    """/confirm must not rely on /upload having already size-checked — re-applies the same size
    policy to whatever it finds staged."""
    monkeypatch.setattr(store_mod, "RAW_DIR", tmp_path)
    staged_id = _stage_bom_sales_directly(db_sessionmaker)
    monkeypatch.setattr(appmod, "MAX_UPLOAD_BYTES", 10)

    resp = _client.post("/confirm", data={"staged_upload_id": staged_id})
    assert resp.status_code == 422
    assert "too large" in resp.text.lower()
    assert not (tmp_path / "r1" / "bom.parquet").exists()
    assert not (tmp_path / "r1" / "sales_export.parquet").exists()
