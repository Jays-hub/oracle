"""W3 invoice capture — pure compute for the digital-feed invoice/price upload.

Parses an uploaded flat CSV of invoice line items into schema-valid ``schemas/seam.py``
``PriceObservationRow`` rows, cross-references ingredient names against the already-captured BOM,
and appends the result to the accumulating ``price_observations.parquet`` seam leg. No FastAPI
import here (rule 05: compute stays pure and unit-testable without the web layer) —
``web/app.py`` is the only caller that knows about HTTP.

This module is the **digital vendor feed** half of the Phase-2 "invoice capture" build
(`onramp/plate_cost/docs/purpose_and_phases.md`'s "photo + OCR, **or** digital vendor feed"). It
deliberately does not touch ``src/ingestion/`` — that package is reserved for the heavier photo+OCR
+ learned-mapping entity resolution and stays gated behind the POS-absorption competitive check
(see its own module docstring). A structured CSV upload is architecturally identical to the W1
capture funnel (``src/capture/seam_upload.py``), so it lives beside it instead, following the same
proven parse/cross-reference/write shape rather than inventing a new one.

Entity resolution here is intentionally thin: ``ingredient_id`` is derived via the same
``normalize_name()`` key ``BomRow`` already uses, so a price observation joins to a recipe
ingredient without a separate UUID/learned-mapping table. An invoice ingredient name that doesn't
match any name already in the BOM is surfaced as a non-blocking warning (mirrors
``cross_reference_dishes``), not silently dropped and not hard-blocked — the full confirmation-
queue-with-learned-mappings system the roadmap describes is explicitly deferred
(``docs/phase_decisions/W3.md``).
"""
from __future__ import annotations

import csv
import fcntl
import io
import os
from pathlib import Path

import pandas as pd
from pydantic import ValidationError

from ..report.grid import normalize_name
# Reuses seam_upload's ParseResult/_decode/_validation_message/_stage_parquet rather than forking
# a second copy (rule 05) — a structured CSV upload is the same shape as the W1 capture funnel.
# web/app.py imports MAX_UPLOAD_BYTES from seam_upload directly; no need to re-export here.
from .seam_upload import ParseResult, _decode, _stage_parquet, _validation_message

# schemas/ bootstrap already ran when seam_upload was imported above (sys.path is process-global),
# but import PriceObservationRow explicitly here rather than relying on that side effect.
from schemas import PriceObservationRow  # noqa: E402  (after the seam_upload import, same reason)

_INVOICE_REQUIRED_COLUMNS = {"ingredient_name", "unit_price", "source_invoice", "observed_date"}


def parse_invoice_csv(raw: bytes) -> ParseResult[PriceObservationRow]:
    """Validate an uploaded invoice CSV against ``PriceObservationRow`` — one error per bad row.

    ``ingredient_id`` is derived from ``ingredient_name`` via ``normalize_name()``, matching
    ``BomRow``'s convention (not supplied by the chef — this format has no UUIDs to invent).
    """
    text = _decode(raw)
    if text is None:
        return ParseResult(errors=["Invoice file is not valid UTF-8 text."])

    reader = csv.DictReader(io.StringIO(text))
    if reader.fieldnames is None:
        return ParseResult(errors=["Invoice file is empty."])
    missing = _INVOICE_REQUIRED_COLUMNS - set(reader.fieldnames)
    if missing:
        return ParseResult(errors=[f"Invoice file is missing column(s): {', '.join(sorted(missing))}"])

    rows: list[PriceObservationRow] = []
    errors: list[str] = []
    for line_no, raw_row in enumerate(reader, start=2):
        ingredient_name = (raw_row.get("ingredient_name") or "").strip()
        source_invoice = (raw_row.get("source_invoice") or "").strip() or None
        try:
            rows.append(PriceObservationRow(
                ingredient_id=normalize_name(ingredient_name),
                ingredient_name=ingredient_name,
                unit_price=raw_row["unit_price"],
                source_invoice=source_invoice,
                observed_date=raw_row["observed_date"],
            ))
        except ValidationError as e:
            errors.append(f"Invoice row {line_no} ({ingredient_name or '?'}): {_validation_message(e)}")

    if not errors and not rows:
        errors.append("Invoice file has no data rows.")
    return ParseResult(rows=rows, errors=errors)


def cross_reference_ingredients(
    price_rows: list[PriceObservationRow], known_ingredient_ids: set[str]
) -> list[str]:
    """Invoice ingredient names that don't match any ingredient already in the recipe sheet (BOM).

    Non-blocking (mirrors ``seam_upload.cross_reference_dishes``'s honesty pattern): a chef should
    see a likely typo/rename before confirming, but a genuinely new ingredient (or an invoice
    uploaded before the recipe sheet) is not an error — just something to double-check. Takes a
    bare id set rather than a list of ``BomRow`` (unlike ``cross_reference_dishes``) since the
    caller already has the known ids from ``store.read_bom()``'s ``ingredient_id`` column and
    reconstructing full rows just to get that set would be pure overhead.
    """
    by_key = {r.ingredient_id: r.ingredient_name for r in price_rows}
    return sorted(name for key, name in by_key.items() if key not in known_ingredient_ids)


_DEDUPE_KEYS = ["ingredient_id", "observed_date", "unit_price", "source_invoice"]


def write_price_observations_atomic(rows: list[PriceObservationRow], raw_dir: Path) -> None:
    """Append newly confirmed price observations to the accumulating price-history leg.

    Unlike ``bom``/``sales_export`` (a full-replace "current snapshot" model — see
    ``seam_upload.write_seam_atomic``), price history **accumulates**: every invoice adds rows
    without discarding prior ones (history is always retained, never overwritten — the same
    invariant ``src/ingestion/__init__.py``'s docstring states for the eventual OCR path). A
    re-submitted invoice is idempotent: a row identical on (ingredient_id, observed_date,
    unit_price, source_invoice) to one already on disk is not duplicated (rule 07).

    The read-modify-write is not safe under concurrent writers on its own — only the final rename
    is atomic. An advisory exclusive lock (``fcntl.flock``; POSIX-only, fine for this repo's
    Darwin-dev/ubuntu-CI reality) serializes the whole read-combine-write-rename sequence across
    processes/threads sharing ``raw_dir``, closing the lost-update race two overlapping
    ``/invoice/confirm`` requests would otherwise hit — each reading the pre-write state, with the
    second's rename silently discarding the first's rows (W3_review.md MINOR-4).
    """
    if not rows:
        raise ValueError("write_price_observations_atomic: no price rows to write")

    new_df = pd.DataFrame([r.model_dump() for r in rows])
    raw_dir.mkdir(parents=True, exist_ok=True)
    dest = raw_dir / "price_observations.parquet"
    lock_path = raw_dir / "price_observations.parquet.lock"

    with open(lock_path, "w") as lock_file:
        fcntl.flock(lock_file, fcntl.LOCK_EX)
        try:
            if dest.exists():
                combined = pd.concat([pd.read_parquet(dest), new_df], ignore_index=True)
            else:
                combined = new_df
            combined = combined.drop_duplicates(subset=_DEDUPE_KEYS, keep="last").reset_index(drop=True)

            tmp_path = _stage_parquet(combined, dest)
            os.replace(tmp_path, dest)
        finally:
            fcntl.flock(lock_file, fcntl.LOCK_UN)
