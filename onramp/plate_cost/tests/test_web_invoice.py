"""Tests for the W3 invoice-capture web routes (GET/POST /invoice/upload, POST /invoice/confirm).

Every test that writes monkeypatches src.store.RAW_DIR to a tmp_path — the single canonical seam
directory both the read and write paths reference (W3_review.md LOW-1) — never the real
data/raw/. Covers: the happy path end-to-end (accumulating, not replacing), validation errors
surfaced without a crash, the BOM cross-reference warning, the size-limit boundary, and that
/invoice/confirm re-validates rather than trusting the staged payload.

Auth/identity are bypassed here the same way test_web_upload.py bypasses them —
test_web_auth.py owns the "every protected route redirects" behavior (this file's routes are in
its parametrized list).
"""
import re
from base64 import b64encode
from datetime import datetime, timedelta, timezone

import pandas as pd
import pytest
from fastapi.testclient import TestClient

import src.store as store_mod
import web.app as appmod
from schemas import PriceObservationRow
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


_VALID_INVOICE = (
    b"ingredient_name,unit_price,source_invoice,observed_date\n"
    b"beef patty,3.50,INV-001,2026-06-01\n"
    b"romaine,1.20,INV-001,2026-06-01\n"
)


def _post_invoice_upload(invoice=_VALID_INVOICE):
    return _client.post(
        "/invoice/upload", files={"invoice_file": ("invoice.csv", invoice, "text/csv")},
    )


def _extract_staged_upload_id(html: str) -> str:
    m = re.search(r'name="staged_upload_id" value="([^"]*)"', html)
    assert m, "invoice confirm page is missing the staged_upload_id hidden field"
    return m.group(1)


def _stage_invoice_row_directly(db_sessionmaker, payload: dict[str, str]) -> str:
    """Seeds a staged_uploads row directly, bypassing /invoice/upload — used to prove
    /invoice/confirm re-validates whatever it finds staged rather than trusting it."""
    db = db_sessionmaker()
    try:
        row = StagedUpload(
            user_id=_FAKE_IDENTITY.user_id,
            restaurant_id=_FAKE_IDENTITY.restaurant_id,
            kind="invoice",
            payload=payload,
            expires_at=datetime.now(timezone.utc) + timedelta(minutes=30),
        )
        db.add(row)
        db.commit()
        db.refresh(row)
        return row.id
    finally:
        db.close()


def test_invoice_upload_form_returns_200():
    resp = _client.get("/invoice/upload")
    assert resp.status_code == 200
    assert "invoice_file" in resp.text


def test_invoice_upload_valid_file_shows_confirm_summary():
    resp = _post_invoice_upload()
    assert resp.status_code == 200
    assert "2" in resp.text  # row_count / ingredient_count


def test_invoice_upload_missing_column_returns_422_with_named_error():
    resp = _post_invoice_upload(invoice=b"ingredient_name,unit_price\nbeef,3.50\n")
    assert resp.status_code == 422
    assert "source_invoice" in resp.text


def test_invoice_upload_row_error_is_named_not_a_stack_trace():
    bad = b"ingredient_name,unit_price,source_invoice,observed_date\nbeef,-3.50,INV-1,2026-06-01\n"
    resp = _post_invoice_upload(invoice=bad)
    assert resp.status_code == 422
    assert "Traceback" not in resp.text
    assert "beef" in resp.text


def test_invoice_upload_oversized_file_rejected_before_parsing(monkeypatch):
    monkeypatch.setattr(appmod, "MAX_UPLOAD_BYTES", 10)
    resp = _post_invoice_upload()
    assert resp.status_code == 422
    assert "too large" in resp.text.lower()


def test_invoice_upload_flags_ingredient_not_in_bom(tmp_path, monkeypatch):
    """The non-blocking cross-reference warning: an uploaded BOM that doesn't mention 'beef
    patty' surfaces it on the confirm page rather than silently accepting or rejecting it."""
    # A single patch point now covers both _known_ingredient_ids()'s read (via src.store) and the
    # write below — store.RAW_DIR is the one canonical seam-directory constant both sides
    # reference (W3_review.md LOW-1; this test used to need two independent patches to stay
    # isolated, one of which was easy to forget).
    monkeypatch.setattr(store_mod, "RAW_DIR", tmp_path)
    pd.DataFrame([{
        "dish_id": "salad", "dish_name": "Salad", "ingredient_id": "romaine",
        "ingredient_name": "romaine", "qty": 4.0, "recipe_unit": "oz", "canonical_unit": "oz",
        "yield_factor": 1.0,
    }]).to_parquet(tmp_path / "bom.parquet", index=False, engine="pyarrow")

    resp = _post_invoice_upload()
    assert resp.status_code == 200
    assert "beef patty" in resp.text


def test_confirm_writes_schema_valid_seam_file(tmp_path, monkeypatch):
    monkeypatch.setattr(store_mod, "RAW_DIR", tmp_path)

    upload_resp = _post_invoice_upload()
    staged_id = _extract_staged_upload_id(upload_resp.text)
    confirm_resp = _client.post("/invoice/confirm", data={"staged_upload_id": staged_id})

    assert confirm_resp.status_code == 200
    assert "Saved" in confirm_resp.text

    df = pd.read_parquet(tmp_path / "price_observations.parquet")
    assert len(df) == 2
    PriceObservationRow(**{k: df[k].iloc[0] for k in PriceObservationRow.model_fields})


def test_confirm_accumulates_across_separate_invoices(tmp_path, monkeypatch):
    monkeypatch.setattr(store_mod, "RAW_DIR", tmp_path)

    first_upload = _post_invoice_upload()
    _client.post(
        "/invoice/confirm", data={"staged_upload_id": _extract_staged_upload_id(first_upload.text)},
    )

    second_invoice = (
        b"ingredient_name,unit_price,source_invoice,observed_date\n"
        b"beef patty,4.10,INV-002,2026-06-08\n"
    )
    second_upload = _post_invoice_upload(invoice=second_invoice)
    _client.post(
        "/invoice/confirm", data={"staged_upload_id": _extract_staged_upload_id(second_upload.text)},
    )

    df = pd.read_parquet(tmp_path / "price_observations.parquet")
    assert len(df) == 3  # 2 from the first invoice + 1 new, never replaced


def test_confirm_is_single_use(tmp_path, monkeypatch):
    monkeypatch.setattr(store_mod, "RAW_DIR", tmp_path)

    upload_resp = _post_invoice_upload()
    staged_id = _extract_staged_upload_id(upload_resp.text)

    first = _client.post("/invoice/confirm", data={"staged_upload_id": staged_id})
    second = _client.post("/invoice/confirm", data={"staged_upload_id": staged_id})

    assert first.status_code == 200
    assert second.status_code == 400


def test_confirm_rejects_tampered_staged_payload_never_trusts_it(tmp_path, monkeypatch, db_sessionmaker):
    monkeypatch.setattr(store_mod, "RAW_DIR", tmp_path)
    tampered = b"ingredient_name,unit_price,source_invoice,observed_date\nbeef,-999,INV-1,2026-06-01\n"
    staged_id = _stage_invoice_row_directly(
        db_sessionmaker, {"invoice_csv_b64": b64encode(tampered).decode("ascii")},
    )

    resp = _client.post("/invoice/confirm", data={"staged_upload_id": staged_id})
    assert resp.status_code == 400
    assert not (tmp_path / "price_observations.parquet").exists()


def test_confirm_rejects_malformed_base64_in_staged_payload(db_sessionmaker):
    staged_id = _stage_invoice_row_directly(db_sessionmaker, {"invoice_csv_b64": "not-valid-base64!!!"})
    resp = _client.post("/invoice/confirm", data={"staged_upload_id": staged_id})
    assert resp.status_code == 400
    assert "Traceback" not in resp.text


def test_confirm_rejects_unknown_staged_upload_id():
    resp = _client.post("/invoice/confirm", data={"staged_upload_id": "not-a-real-id"})
    assert resp.status_code == 400
    assert "Traceback" not in resp.text


def test_confirm_enforces_its_own_size_limit_without_going_through_upload(tmp_path, monkeypatch, db_sessionmaker):
    monkeypatch.setattr(store_mod, "RAW_DIR", tmp_path)
    staged_id = _stage_invoice_row_directly(
        db_sessionmaker, {"invoice_csv_b64": b64encode(_VALID_INVOICE).decode("ascii")},
    )
    monkeypatch.setattr(appmod, "MAX_UPLOAD_BYTES", 10)

    resp = _client.post("/invoice/confirm", data={"staged_upload_id": staged_id})
    assert resp.status_code == 422
    assert "too large" in resp.text.lower()
    assert not (tmp_path / "price_observations.parquet").exists()


def test_confirm_recomputes_food_cost_leg_when_bom_already_captured(tmp_path, monkeypatch):
    """A new invoice changes ingredient cost -- food_cost.parquet must reflect the NEW price
    without a trip back through /menu-prices first (W6_review.md MINOR-3: the leg must not go
    stale after an invoice-driven price change)."""
    monkeypatch.setattr(store_mod, "RAW_DIR", tmp_path)
    pd.DataFrame([{
        "dish_id": "burger", "dish_name": "Burger", "ingredient_id": "beef patty",
        "ingredient_name": "beef patty", "qty": 6.0, "recipe_unit": "oz", "canonical_unit": "oz",
        "yield_factor": 1.0,
    }]).to_parquet(tmp_path / "bom.parquet", index=False, engine="pyarrow")

    upload_resp = _post_invoice_upload()
    staged_id = _extract_staged_upload_id(upload_resp.text)
    confirm_resp = _client.post("/invoice/confirm", data={"staged_upload_id": staged_id})
    assert confirm_resp.status_code == 200

    df = pd.read_parquet(tmp_path / "food_cost.parquet")
    assert df["dish_id"].iloc[0] == "burger"
    assert df["food_cost"].iloc[0] == pytest.approx(6.0 * 3.50)  # beef patty @ $3.50/oz, yield 1.0


def test_confirm_without_a_captured_bom_still_succeeds(tmp_path, monkeypatch):
    """No recipe sheet captured yet -- the food_cost recompute has nothing to work from and must
    be skipped cleanly, never blocking the invoice confirmation itself."""
    monkeypatch.setattr(store_mod, "RAW_DIR", tmp_path)

    upload_resp = _post_invoice_upload()
    staged_id = _extract_staged_upload_id(upload_resp.text)
    confirm_resp = _client.post("/invoice/confirm", data={"staged_upload_id": staged_id})

    assert confirm_resp.status_code == 200
    assert not (tmp_path / "food_cost.parquet").exists()


def test_invoice_pages_never_show_the_sample_data_banner(tmp_path, monkeypatch):
    """Mirrors test_web_upload.py's regression guard: pages showing the operator's OWN uploaded
    data must never carry the "sample data" banner."""
    monkeypatch.setattr(store_mod, "RAW_DIR", tmp_path)
    upload_form_resp = _client.get("/invoice/upload")
    upload_resp = _post_invoice_upload()
    confirm_resp = _client.post(
        "/invoice/confirm", data={"staged_upload_id": _extract_staged_upload_id(upload_resp.text)},
    )
    for resp in (upload_form_resp, upload_resp, confirm_resp):
        assert "sample-banner" not in resp.text
