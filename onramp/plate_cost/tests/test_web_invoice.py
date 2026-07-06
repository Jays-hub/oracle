"""Tests for the W3 invoice-capture web routes (GET/POST /invoice/upload, POST /invoice/confirm).

Every test that writes monkeypatches src.store.RAW_DIR to a tmp_path — the single canonical seam
directory both the read and write paths reference (W3_review.md LOW-1) — never the real
data/raw/. Covers: the happy path end-to-end (accumulating, not replacing), validation errors
surfaced without a crash, the BOM cross-reference warning, the size-limit boundary, and that
/invoice/confirm re-validates rather than trusting the round-tripped hidden field.

Auth is bypassed here the same way test_web_upload.py bypasses it — test_web_auth.py owns the
"every protected route redirects" behavior (this file's routes were added to its parametrized list).
"""
import re
from base64 import b64encode

import pandas as pd
import pytest
from fastapi.testclient import TestClient

import src.store as store_mod
import web.app as appmod
from schemas import PriceObservationRow
from web.app import app

_client = TestClient(app)


@pytest.fixture(autouse=True)
def _bypass_login(monkeypatch):
    monkeypatch.setattr(appmod, "require_login", lambda request: None)


_VALID_INVOICE = (
    b"ingredient_name,unit_price,source_invoice,observed_date\n"
    b"beef patty,3.50,INV-001,2026-06-01\n"
    b"romaine,1.20,INV-001,2026-06-01\n"
)


def _post_invoice_upload(invoice=_VALID_INVOICE):
    return _client.post(
        "/invoice/upload", files={"invoice_file": ("invoice.csv", invoice, "text/csv")},
    )


def _extract_hidden_field(html: str) -> str:
    m = re.search(r'name="invoice_csv_b64" value="([^"]*)"', html)
    assert m, "invoice confirm page is missing the round-trip hidden field"
    return m.group(1)


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
    invoice_b64 = _extract_hidden_field(upload_resp.text)
    confirm_resp = _client.post("/invoice/confirm", data={"invoice_csv_b64": invoice_b64})

    assert confirm_resp.status_code == 200
    assert "Saved" in confirm_resp.text

    df = pd.read_parquet(tmp_path / "price_observations.parquet")
    assert len(df) == 2
    PriceObservationRow(**{k: df[k].iloc[0] for k in PriceObservationRow.model_fields})


def test_confirm_accumulates_across_separate_invoices(tmp_path, monkeypatch):
    monkeypatch.setattr(store_mod, "RAW_DIR", tmp_path)

    first_upload = _post_invoice_upload()
    _client.post(
        "/invoice/confirm", data={"invoice_csv_b64": _extract_hidden_field(first_upload.text)},
    )

    second_invoice = (
        b"ingredient_name,unit_price,source_invoice,observed_date\n"
        b"beef patty,4.10,INV-002,2026-06-08\n"
    )
    second_upload = _post_invoice_upload(invoice=second_invoice)
    _client.post(
        "/invoice/confirm", data={"invoice_csv_b64": _extract_hidden_field(second_upload.text)},
    )

    df = pd.read_parquet(tmp_path / "price_observations.parquet")
    assert len(df) == 3  # 2 from the first invoice + 1 new, never replaced


def test_confirm_rejects_tampered_payload_never_trusts_the_hidden_field(tmp_path, monkeypatch):
    monkeypatch.setattr(store_mod, "RAW_DIR", tmp_path)
    tampered = b64encode(
        b"ingredient_name,unit_price,source_invoice,observed_date\nbeef,-999,INV-1,2026-06-01\n"
    ).decode("ascii")

    resp = _client.post("/invoice/confirm", data={"invoice_csv_b64": tampered})
    assert resp.status_code == 400
    assert not (tmp_path / "price_observations.parquet").exists()


def test_confirm_rejects_invalid_base64():
    resp = _client.post("/invoice/confirm", data={"invoice_csv_b64": "not-valid-base64!!!"})
    assert resp.status_code == 400
    assert "Traceback" not in resp.text


def test_confirm_enforces_its_own_size_limit_without_going_through_upload(tmp_path, monkeypatch):
    monkeypatch.setattr(store_mod, "RAW_DIR", tmp_path)
    monkeypatch.setattr(appmod, "MAX_UPLOAD_BYTES", 10)

    resp = _client.post(
        "/invoice/confirm",
        data={"invoice_csv_b64": b64encode(_VALID_INVOICE).decode("ascii")},
    )
    assert resp.status_code == 422
    assert "too large" in resp.text.lower()
    assert not (tmp_path / "price_observations.parquet").exists()


def test_invoice_pages_never_show_the_sample_data_banner(tmp_path, monkeypatch):
    """Mirrors test_web_upload.py's regression guard: pages showing the operator's OWN uploaded
    data must never carry the "sample data" banner."""
    monkeypatch.setattr(store_mod, "RAW_DIR", tmp_path)
    upload_form_resp = _client.get("/invoice/upload")
    upload_resp = _post_invoice_upload()
    confirm_resp = _client.post(
        "/invoice/confirm", data={"invoice_csv_b64": _extract_hidden_field(upload_resp.text)},
    )
    for resp in (upload_form_resp, upload_resp, confirm_resp):
        assert "sample-banner" not in resp.text
