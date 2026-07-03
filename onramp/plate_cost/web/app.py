"""On-ramp web layer.

W0: GET / renders the popularity × margin grid from the on-ramp's source inputs (the same src/
chain as run.py). W0 reads source data, not the seam: data/raw/ carries only the BOM + sales legs,
which can't reconstruct margins (see web/compute.py for the why). No writes, no auth.

W1: GET/POST /upload + POST /confirm are the self-serve capture funnel — a chef uploads a sales
export and a recipe sheet, reviews a summary, then confirms, which writes the two seam legs to
data/raw/ through schemas/ (src/capture/seam_upload.py). Confirming does NOT change what GET /
shows (see web/templates/success.html) — W0's reveal still reads local sample data, not the seam;
wiring the grid to read a tenant's own uploaded data is W2's job (auth + persistence), not this
phase's.

No JS framework anywhere. Server-rendered HTML (Jinja2) only.
(.claude/rules/05–07: thin over pure compute, fast first paint, dollar-legible, hostile-until-
validated input, atomic seam writes.)
"""
import binascii
import logging
from base64 import b64decode, b64encode
from pathlib import Path
from uuid import uuid4

from fastapi import FastAPI, File, Form, Request, UploadFile
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from src.capture.seam_upload import (
    MAX_UPLOAD_BYTES,
    RAW_DIR,
    cross_reference_dishes,
    parse_bom_csv,
    parse_sales_csv,
    write_seam_atomic,
)

from .compute import build_grid_data
from .upload import build_summary

_WEB_DIR = Path(__file__).resolve().parent
_RAW_DIR = RAW_DIR

app = FastAPI(title="Plate Cost · On-Ramp", docs_url=None, redoc_url=None, openapi_url=None)
app.mount("/static", StaticFiles(directory=str(_WEB_DIR / "static")), name="static")

_templates = Jinja2Templates(directory=str(_WEB_DIR / "templates"))
_log = logging.getLogger(__name__)


@app.get("/", response_class=HTMLResponse)
def grid(request: Request) -> HTMLResponse:
    # Sync handler on purpose: build_grid_data() does blocking file I/O (open/csv/pandas). A plain
    # `def` lets FastAPI run it in a threadpool; an `async def` would run that blocking work directly
    # on the event loop and stall every other request.
    try:
        data = build_grid_data()
    except Exception:
        # Fail legibly (rules 06/07): a calm page + a correlation id the operator can quote, never a
        # stack trace or internal path to the client. The detail stays server-side in the log.
        correlation_id = uuid4().hex[:8]
        _log.exception("grid render failed (correlation_id=%s)", correlation_id)
        return _templates.TemplateResponse(
            request=request,
            name="error.html",
            context={"correlation_id": correlation_id},
            status_code=503,
        )
    return _templates.TemplateResponse(request=request, name="grid.html", context=data)


@app.get("/upload", response_class=HTMLResponse)
def upload_form(request: Request) -> HTMLResponse:
    return _templates.TemplateResponse(request=request, name="upload.html", context={"errors": []})


@app.post("/upload", response_class=HTMLResponse)
async def upload_submit(
    request: Request,
    sales_file: UploadFile = File(...),
    bom_file: UploadFile = File(...),
) -> HTMLResponse:
    # Hostile until validated (rule 07): size-check before we even try to decode/parse either file.
    sales_bytes = await sales_file.read(MAX_UPLOAD_BYTES + 1)
    bom_bytes = await bom_file.read(MAX_UPLOAD_BYTES + 1)

    errors = _size_errors(sales_bytes, bom_bytes)
    if errors:
        return _templates.TemplateResponse(
            request=request, name="upload.html", context={"errors": errors}, status_code=422,
        )

    sales_result = parse_sales_csv(sales_bytes)
    bom_result = parse_bom_csv(bom_bytes)
    errors = sales_result.errors + bom_result.errors
    if errors:
        return _templates.TemplateResponse(
            request=request, name="upload.html", context={"errors": errors}, status_code=422,
        )

    only_in_bom, only_in_sales = cross_reference_dishes(bom_result.rows, sales_result.rows)
    context = {
        "summary": build_summary(bom_result.rows, sales_result.rows),
        "only_in_bom": only_in_bom,
        "only_in_sales": only_in_sales,
        # Round-tripped through the confirm page's hidden fields so /confirm can re-validate and
        # write without any server-side session/staging state (rule 07: stateless handlers).
        "sales_csv_b64": _b64(sales_bytes),
        "bom_csv_b64": _b64(bom_bytes),
    }
    return _templates.TemplateResponse(request=request, name="confirm.html", context=context)


@app.post("/confirm", response_class=HTMLResponse)
def confirm_submit(
    request: Request,
    sales_csv_b64: str = Form(...),
    bom_csv_b64: str = Form(...),
) -> HTMLResponse:
    try:
        sales_bytes = b64decode(sales_csv_b64, validate=True)
        bom_bytes = b64decode(bom_csv_b64, validate=True)
    except binascii.Error:
        correlation_id = uuid4().hex[:8]
        _log.warning("confirm payload was not valid base64 (correlation_id=%s)", correlation_id)
        return _templates.TemplateResponse(
            request=request, name="error.html", context={"correlation_id": correlation_id},
            status_code=400,
        )

    # /confirm is directly POST-able — never assume a boundary check done at /upload still holds
    # here. Re-apply the same size policy rather than relying on Starlette's incidental per-field
    # cap, which is a different (tighter, opaque-failure) ceiling than our own (rule 07).
    errors = _size_errors(sales_bytes, bom_bytes)
    if errors:
        return _templates.TemplateResponse(
            request=request, name="upload.html", context={"errors": errors}, status_code=422,
        )

    # Never trust a round-tripped hidden field blindly — re-run the exact same validation the
    # /upload step ran, rather than assuming the payload that came back is still what we sent out.
    sales_result = parse_sales_csv(sales_bytes)
    bom_result = parse_bom_csv(bom_bytes)
    if sales_result.errors or bom_result.errors:
        correlation_id = uuid4().hex[:8]
        _log.warning(
            "confirm re-validation failed (correlation_id=%s): %s",
            correlation_id, sales_result.errors + bom_result.errors,
        )
        return _templates.TemplateResponse(
            request=request, name="error.html", context={"correlation_id": correlation_id},
            status_code=400,
        )

    try:
        write_seam_atomic(bom_result.rows, sales_result.rows, _RAW_DIR)
    except Exception:
        correlation_id = uuid4().hex[:8]
        _log.exception("seam write failed (correlation_id=%s)", correlation_id)
        return _templates.TemplateResponse(
            request=request, name="error.html", context={"correlation_id": correlation_id},
            status_code=503,
        )

    summary = build_summary(bom_result.rows, sales_result.rows)
    return _templates.TemplateResponse(request=request, name="success.html", context={"summary": summary})


def _b64(raw: bytes) -> str:
    return b64encode(raw).decode("ascii")


def _size_errors(sales_bytes: bytes, bom_bytes: bytes) -> list[str]:
    """Shared by /upload and /confirm — the same size policy must hold at both entry points,
    since /confirm is directly POST-able and must not rely on /upload having already checked."""
    errors: list[str] = []
    if len(sales_bytes) > MAX_UPLOAD_BYTES:
        errors.append(f"Sales file is too large (max {MAX_UPLOAD_BYTES // 1000} KB).")
    if len(bom_bytes) > MAX_UPLOAD_BYTES:
        errors.append(f"Recipe file is too large (max {MAX_UPLOAD_BYTES // 1000} KB).")
    return errors
