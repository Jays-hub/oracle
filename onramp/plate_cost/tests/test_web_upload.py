"""Tests for the W1 capture-funnel web routes (GET/POST /upload, POST /confirm).

Every test that writes monkeypatches web.app._RAW_DIR to a tmp_path — never the real data/raw/ —
mirroring test_store.py's isolation pattern. Covers: the happy path end-to-end (and that it
actually lands schema-valid Parquet), validation errors surfaced without a crash, the cross-file
mismatch warning, the size-limit boundary, and that /confirm re-validates rather than trusting the
round-tripped hidden fields.
"""
import re

import pandas as pd
from fastapi.testclient import TestClient

import web.app as appmod
from schemas import BomRow, SalesExportRow
from web.app import app

_client = TestClient(app)

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


def _extract_hidden_fields(html: str) -> tuple[str, str]:
    sales_m = re.search(r'name="sales_csv_b64" value="([^"]*)"', html)
    bom_m = re.search(r'name="bom_csv_b64" value="([^"]*)"', html)
    assert sales_m and bom_m, "confirm page is missing the round-trip hidden fields"
    return sales_m.group(1), bom_m.group(1)


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
    monkeypatch.setattr(appmod, "_RAW_DIR", tmp_path)

    upload_form_resp = _client.get("/upload")
    upload_resp = _post_upload()
    sales_b64, bom_b64 = _extract_hidden_fields(upload_resp.text)
    confirm_resp = _client.post(
        "/confirm", data={"sales_csv_b64": sales_b64, "bom_csv_b64": bom_b64},
    )

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
    monkeypatch.setattr(appmod, "_RAW_DIR", tmp_path)

    upload_resp = _post_upload()
    sales_b64, bom_b64 = _extract_hidden_fields(upload_resp.text)

    confirm_resp = _client.post(
        "/confirm", data={"sales_csv_b64": sales_b64, "bom_csv_b64": bom_b64},
    )
    assert confirm_resp.status_code == 200
    assert "Saved" in confirm_resp.text

    bom_df = pd.read_parquet(tmp_path / "bom.parquet")
    sales_df = pd.read_parquet(tmp_path / "sales_export.parquet")
    assert len(bom_df) == 2
    assert len(sales_df) == 2
    BomRow(**{k: bom_df[k].iloc[0] for k in BomRow.model_fields})
    SalesExportRow(**{k: sales_df[k].iloc[0] for k in SalesExportRow.model_fields})


def test_confirm_never_touches_real_raw_dir_when_isolated(tmp_path, monkeypatch):
    """Sanity check on the test isolation itself: confirming against a monkeypatched _RAW_DIR
    must not also write the real seam (guards against a future refactor re-introducing a
    hard-coded path that bypasses the isolation)."""
    monkeypatch.setattr(appmod, "_RAW_DIR", tmp_path)
    real_raw_dir = appmod.RAW_DIR
    before = (real_raw_dir / "bom.parquet").stat().st_mtime

    upload_resp = _post_upload()
    sales_b64, bom_b64 = _extract_hidden_fields(upload_resp.text)
    _client.post("/confirm", data={"sales_csv_b64": sales_b64, "bom_csv_b64": bom_b64})

    after = (real_raw_dir / "bom.parquet").stat().st_mtime
    assert before == after


def test_confirm_rejects_tampered_payload_never_trusts_the_hidden_field(tmp_path, monkeypatch):
    """Rule 07: /confirm must re-validate, not blindly trust a round-tripped hidden field. Craft
    a base64 payload that decodes to CSV content failing schema validation and confirm it is
    rejected rather than written."""
    monkeypatch.setattr(appmod, "_RAW_DIR", tmp_path)
    from base64 import b64encode

    tampered_sales = b64encode(
        b"dish_name,count,period_start,period_end\nBurger,-999,2026-06-01,2026-06-07\n"
    ).decode("ascii")
    valid_bom = b64encode(_VALID_BOM).decode("ascii")

    resp = _client.post(
        "/confirm", data={"sales_csv_b64": tampered_sales, "bom_csv_b64": valid_bom},
    )
    assert resp.status_code == 400
    assert not (tmp_path / "bom.parquet").exists()
    assert not (tmp_path / "sales_export.parquet").exists()


def test_confirm_rejects_invalid_base64():
    resp = _client.post(
        "/confirm", data={"sales_csv_b64": "not-valid-base64!!!", "bom_csv_b64": "also-bad!!!"},
    )
    assert resp.status_code == 400
    assert "Traceback" not in resp.text


def test_confirm_enforces_its_own_size_limit_without_going_through_upload(tmp_path, monkeypatch):
    """/confirm is directly POST-able and must not rely on /upload having already size-checked.
    Regression for the review finding that /confirm had no size policy of its own and could only
    be incidentally rejected by Starlette's unrelated per-field cap."""
    monkeypatch.setattr(appmod, "_RAW_DIR", tmp_path)
    monkeypatch.setattr(appmod, "MAX_UPLOAD_BYTES", 10)
    from base64 import b64encode

    resp = _client.post(
        "/confirm",
        data={
            "sales_csv_b64": b64encode(_VALID_SALES).decode("ascii"),
            "bom_csv_b64": b64encode(_VALID_BOM).decode("ascii"),
        },
    )
    assert resp.status_code == 422
    assert "too large" in resp.text.lower()
    assert not (tmp_path / "bom.parquet").exists()
    assert not (tmp_path / "sales_export.parquet").exists()
