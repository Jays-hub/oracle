"""W1 capture funnel — pure compute for the self-serve POS-export + recipe upload.

Parses the two flat CSVs a chef uploads (sales export, recipe/BOM sheet) into schema-valid
``schemas/seam.py`` rows, cross-checks the two files against each other, and atomically writes
the seam legs to ``data/raw/``. No FastAPI import here (rule 05: compute stays pure and
unit-testable without the web layer) — ``web/app.py`` is the only caller that knows about HTTP.

The self-serve BOM format is deliberately flatter than the CLI's normalized 3-file model
(``sample_dishes.csv`` / ``sample_ingredients.csv`` / ``sample_recipe_lines.csv``): a chef has
dish names and ingredient names, not UUIDs, so one denormalized sheet
(``dish_name, ingredient_name, qty, recipe_unit, canonical_unit, yield_factor``) is the whole
recipe-confirmation act. ``dish_id`` / ``ingredient_id`` are derived from the names via the same
``normalize_name()`` the grid already uses to join sales to dishes — one canonical name-key
function, not a second one that could drift (rule 05 reuse).
"""
from __future__ import annotations

import csv
import io
import os
import sys
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Generic, TypeVar

import pandas as pd
from pydantic import ValidationError

from ..report.grid import normalize_name

# capture/seam_upload.py -> parents: [capture, src, plate_cost, onramp, repo-root]
_REPO_ROOT = Path(__file__).resolve().parents[4]
RAW_DIR = _REPO_ROOT / "data" / "raw"

# schemas/ is platform-owned (data/CONTRACT.md), imported by both peers, and lives outside this
# package's import path — same sys.path bootstrap as src/run.py, needed here too since this
# module (not just the CLI entry point) is the one that imports it directly.
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))
from schemas import BomRow, SalesExportRow  # noqa: E402  (import after the sys.path bootstrap)

# Fail loudly at import time, mirroring src/store.py's structural invariant on the read side.
assert RAW_DIR.parts[-2:] == ("data", "raw"), (
    f"seam_upload path invariant violated: expected .../data/raw, got {RAW_DIR}"
)

# A ~15-25 item recipe sitdown produces a CSV of a few KB; 700 KB is generous headroom while still
# rejecting a runaway or wrong-file upload before it reaches the parser (rule 07: hostile input).
# Capped below 786,432 bytes on purpose: the confirm step round-trips the raw bytes through a
# base64 form field (~1.33x inflation), and Starlette's default per-field cap on a POSTed form is
# 1 MiB (1,048,576 bytes) — 700_000 * 4/3 ≈ 933 KB stays safely under that with margin, so nothing
# that passes this check at /upload can ever be rejected by the framework at /confirm.
MAX_UPLOAD_BYTES = 700_000

_SALES_REQUIRED_COLUMNS = {"dish_name", "count", "period_start", "period_end"}
_BOM_REQUIRED_COLUMNS = {
    "dish_name", "ingredient_name", "qty", "recipe_unit", "canonical_unit", "yield_factor",
}

T = TypeVar("T")


@dataclass
class ParseResult(Generic[T]):
    """Every row error accumulated (not fail-fast), so a chef sees everything wrong in one pass."""

    rows: list[T] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.errors and bool(self.rows)


def _decode(raw: bytes) -> str | None:
    """Decode upload bytes as UTF-8 (BOM-tolerant, since Excel exports one). None on failure."""
    try:
        return raw.decode("utf-8-sig")
    except UnicodeDecodeError:
        return None


def _validation_message(e: ValidationError) -> str:
    # loc is empty for a model-level validator (e.g. SalesExportRow's period_end/period_start
    # cross-field check) — those errors have no single field to prefix.
    return "; ".join(
        f"{err['loc'][0]}: {err['msg']}" if err["loc"] else err["msg"]
        for err in e.errors()
    )


def parse_sales_csv(raw: bytes) -> ParseResult[SalesExportRow]:
    """Validate an uploaded sales-export CSV against ``SalesExportRow`` — one error per bad row."""
    text = _decode(raw)
    if text is None:
        return ParseResult(errors=["Sales file is not valid UTF-8 text."])

    reader = csv.DictReader(io.StringIO(text))
    if reader.fieldnames is None:
        return ParseResult(errors=["Sales file is empty."])
    missing = _SALES_REQUIRED_COLUMNS - set(reader.fieldnames)
    if missing:
        return ParseResult(errors=[f"Sales file is missing column(s): {', '.join(sorted(missing))}"])

    rows: list[SalesExportRow] = []
    errors: list[str] = []
    for line_no, raw_row in enumerate(reader, start=2):
        dish_name = (raw_row.get("dish_name") or "").strip()
        try:
            rows.append(SalesExportRow(
                dish_name=raw_row["dish_name"],
                count=raw_row["count"],
                period_start=raw_row["period_start"],
                period_end=raw_row["period_end"],
            ))
        except ValidationError as e:
            errors.append(f"Sales row {line_no} ({dish_name or '?'}): {_validation_message(e)}")

    if not errors and not rows:
        errors.append("Sales file has no data rows.")
    return ParseResult(rows=rows, errors=errors)


def parse_bom_csv(raw: bytes) -> ParseResult[BomRow]:
    """Validate an uploaded recipe/BOM CSV against ``BomRow`` — one error per bad row.

    ``dish_id`` / ``ingredient_id`` are derived from the names via ``normalize_name()``, not
    supplied by the chef — this upload format has no UUIDs to invent.
    """
    text = _decode(raw)
    if text is None:
        return ParseResult(errors=["Recipe file is not valid UTF-8 text."])

    reader = csv.DictReader(io.StringIO(text))
    if reader.fieldnames is None:
        return ParseResult(errors=["Recipe file is empty."])
    missing = _BOM_REQUIRED_COLUMNS - set(reader.fieldnames)
    if missing:
        return ParseResult(errors=[f"Recipe file is missing column(s): {', '.join(sorted(missing))}"])

    rows: list[BomRow] = []
    errors: list[str] = []
    for line_no, raw_row in enumerate(reader, start=2):
        dish_name = (raw_row.get("dish_name") or "").strip()
        ingredient_name = (raw_row.get("ingredient_name") or "").strip()
        try:
            rows.append(BomRow(
                dish_id=normalize_name(dish_name),
                dish_name=dish_name,
                ingredient_id=normalize_name(ingredient_name),
                ingredient_name=ingredient_name,
                qty=raw_row["qty"],
                recipe_unit=raw_row["recipe_unit"],
                canonical_unit=raw_row["canonical_unit"],
                yield_factor=raw_row["yield_factor"],
            ))
        except ValidationError as e:
            errors.append(
                f"Recipe row {line_no} ({dish_name or '?'} / {ingredient_name or '?'}): "
                f"{_validation_message(e)}"
            )

    if not errors and not rows:
        errors.append("Recipe file has no data rows.")
    return ParseResult(rows=rows, errors=errors)


def cross_reference_dishes(
    bom_rows: list[BomRow], sales_rows: list[SalesExportRow]
) -> tuple[list[str], list[str]]:
    """Dish names present in one file but not the other — a likely typo, surfaced as a warning.

    Non-blocking (mirrors ``report.grid.covers_join_report``'s existing honesty pattern): a name
    mismatch doesn't fail the schema, but a chef should see it before confirming, not discover it
    later as a silently-dropped join.
    """
    bom_by_key = {normalize_name(r.dish_name): r.dish_name for r in bom_rows}
    sales_by_key = {normalize_name(r.dish_name): r.dish_name for r in sales_rows}
    only_in_bom = sorted(name for key, name in bom_by_key.items() if key not in sales_by_key)
    only_in_sales = sorted(name for key, name in sales_by_key.items() if key not in bom_by_key)
    return only_in_bom, only_in_sales


def _stage_parquet(df: pd.DataFrame, dest: Path) -> Path:
    """Serialize ``df`` to a temp file beside ``dest``; returns the temp path uncommitted.

    Splitting "write the temp file" from "commit it" (in ``write_seam_atomic`` below) lets both
    seam legs be fully staged before either destination file is touched, so a failure *during*
    serialization of either file can never leave a mismatched bom/sales pair — only a crash
    between the two (near-instant) renames that follow could, which is as close to a joint
    transaction as two independent files get without a manifest/versioning layer (out of scope
    for this phase — see `docs/phase_decisions/W1.md`).
    """
    dest.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(dir=dest.parent, prefix=f".{dest.name}.", suffix=".tmp")
    os.close(fd)
    tmp_path = Path(tmp_name)
    try:
        df.to_parquet(tmp_path, index=False, engine="pyarrow")
    except BaseException:
        tmp_path.unlink(missing_ok=True)
        raise
    return tmp_path


def write_seam_atomic(
    bom_rows: list[BomRow], sales_rows: list[SalesExportRow], raw_dir: Path
) -> None:
    """Write both seam legs, staging both before committing either (rule 07).

    A full replace, not an append or a merge — matches the CLI's existing one-shot export
    semantics and this on-ramp's "current snapshot only" model (no upload history/versioning;
    that's a `data/raw/` persistence-layer question for W2, not this phase).
    """
    if not bom_rows:
        raise ValueError("write_seam_atomic: no BOM rows to write")
    if not sales_rows:
        raise ValueError("write_seam_atomic: no sales rows to write")

    bom_df = pd.DataFrame([r.model_dump() for r in bom_rows])
    sales_df = pd.DataFrame([r.model_dump() for r in sales_rows])

    bom_dest = raw_dir / "bom.parquet"
    sales_dest = raw_dir / "sales_export.parquet"

    bom_tmp = _stage_parquet(bom_df, bom_dest)
    try:
        sales_tmp = _stage_parquet(sales_df, sales_dest)
    except BaseException:
        bom_tmp.unlink(missing_ok=True)
        raise

    # Both legs are now fully written to disk under temp names — commit both. Neither destination
    # file has been touched until this point, so a failure anywhere above never mixes an old and
    # a new seam file.
    os.replace(bom_tmp, bom_dest)
    os.replace(sales_tmp, sales_dest)
