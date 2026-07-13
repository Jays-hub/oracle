"""On-ramp web layer.

W0: GET / renders the popularity × margin grid from the on-ramp's source inputs (the same src/
chain as run.py). W0 reads source data, not the seam: data/raw/ carries only the BOM + sales legs,
which can't reconstruct margins (see web/compute.py for the why). No writes, no auth.

W1: GET/POST /upload + POST /confirm are the self-serve capture funnel — a chef uploads a sales
export and a recipe sheet, reviews a summary, then confirms, which writes the two seam legs to
data/raw/ through schemas/ (src/capture/seam_upload.py).

W2: session-based login (GET/POST /login, POST /logout) gates /upload, /confirm, and the new
/your-data page + CSV export. GET / stays public and unauthenticated — it renders the shared
sample grid (no tenant data), the "show a client in 60s" artifact W0 built; there is nothing to
isolate there. /your-data is the first real caller of src/store.py from the web layer — it reads
the operator's own captured seam legs back and offers a one-click CSV export
(docs/phase_decisions/W2.md).

W3: GET/POST /invoice/upload + POST /invoice/confirm are the digital-feed invoice capture funnel
(a chef uploads a CSV of invoice line items, reviews a summary + any unmatched ingredient names,
then confirms, appending PriceObservationRow rows to the accumulating data/raw/
price_observations.parquet leg via src/capture/invoice_upload.py). GET /insights reads that leg
plus the BOM back and surfaces dollar-quantified price-move findings (src/pricing/trends.py,
src/insights/opportunities.py) — deliberately without a margin/tier claim, since the seam still
carries no menu_price (docs/phase_decisions/W3.md).

W4: /your-data deepens into the full transparency view — all three captured legs (BOM, sales,
invoice/price history) enumerated with why each is held, a plain-English explanation of the
engine's hidden-oracle firewall and today's one-tenant honesty, and CSV export now covers the
price-history leg too (missing since W2, since that leg didn't exist until W3). The same page
also carries the new "what this unlocks next" bridge panel — a static, honestly-scoped
description of the forecasting engine's prep-quantity capability, never citing simulation-only
dollar figures as this operator's numbers (docs/phase_decisions/W4.md).

No JS framework anywhere. Server-rendered HTML (Jinja2) only.
(.claude/rules/05–07: thin over pure compute, fast first paint, dollar-legible, hostile-until-
validated input, atomic seam writes, backend-enforced tenant isolation.)
"""
import binascii
import logging
import os
import secrets
from base64 import b64decode, b64encode
from pathlib import Path
from uuid import uuid4

from fastapi import FastAPI, File, Form, Request, UploadFile
from fastapi.responses import HTMLResponse, PlainTextResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from starlette.middleware.sessions import SessionMiddleware

from src import store
from src.auth.credentials import verify_credentials
from src.capture.invoice_upload import (
    cross_reference_ingredients,
    parse_invoice_csv,
    write_price_observations_atomic,
)
from src.capture.seam_upload import (
    MAX_UPLOAD_BYTES,
    cross_reference_dishes,
    parse_bom_csv,
    parse_sales_csv,
    write_seam_atomic,
)

from .auth import RESTAURANT_ID, SESSION_KEY, is_authenticated, require_login
from .compute import build_grid_data
from .insights import build_insights_summary
from .invoice import build_invoice_summary
from .upload import build_summary
from .your_data import (
    build_your_data_summary,
    export_bom_csv,
    export_price_observations_csv,
    export_sales_csv,
)

_WEB_DIR = Path(__file__).resolve().parent

app = FastAPI(title="Plate Cost · On-Ramp", docs_url=None, redoc_url=None, openapi_url=None)
app.mount("/static", StaticFiles(directory=str(_WEB_DIR / "static")), name="static")

# Session signing key: ONRAMP_SESSION_SECRET in env for a real deploy (rule 07 — secrets in env,
# never in code); a fresh random key per process otherwise, which is fine for today's reality —
# a single dev/demo process (web/__main__.py binds 127.0.0.1) with no hosting story yet
# (W0_review.md MINOR-1) — but means every process restart invalidates existing sessions. Revisit
# once a real deploy target sets the env var. https_only=False to match today's plain-HTTP local
# run path; set True once the app is served over TLS. same_site="lax" is stated explicitly
# (rather than left to Starlette's default) so the CSRF posture on these state-changing POSTs is
# a recorded decision, not an implicit one (W2_review.md MINOR-3) — a real per-request CSRF
# token is still the pre-deploy gate item tracked in docs/phase_decisions/W2.md.
_SESSION_SECRET = os.environ.get("ONRAMP_SESSION_SECRET") or secrets.token_hex(32)
app.add_middleware(
    SessionMiddleware, secret_key=_SESSION_SECRET, session_cookie="onramp_session",
    https_only=False, same_site="lax",
)

def _nav_context(request: Request) -> dict:
    """Merged into every TemplateResponse (base.html's nav needs it everywhere) — one place to
    compute it rather than every route remembering to pass logged_in itself (rule 05 reuse)."""
    return {"logged_in": is_authenticated(request)}


_templates = Jinja2Templates(
    directory=str(_WEB_DIR / "templates"), context_processors=[_nav_context],
)
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
    # Public page, no auth required (nothing tenant-specific is shown) — the nav's "Your data" /
    # "Log in" link (via _nav_context) is cosmetic only here, never a content gate.
    return _templates.TemplateResponse(request=request, name="grid.html", context=data)


@app.get("/login", response_class=HTMLResponse)
def login_form(request: Request) -> HTMLResponse:
    return _templates.TemplateResponse(request=request, name="login.html", context={"error": None})


@app.post("/login", response_class=HTMLResponse, response_model=None)
def login_submit(
    request: Request, username: str = Form(...), password: str = Form(...)
) -> HTMLResponse | RedirectResponse:
    if not verify_credentials(username, password):
        return _templates.TemplateResponse(
            request=request, name="login.html",
            context={"error": "Incorrect username or password."}, status_code=401,
        )
    request.session[SESSION_KEY] = RESTAURANT_ID
    return RedirectResponse(url="/your-data", status_code=303)


@app.post("/logout")
def logout(request: Request) -> RedirectResponse:
    request.session.clear()
    return RedirectResponse(url="/", status_code=303)


@app.get("/your-data", response_class=HTMLResponse, response_model=None)
def your_data(request: Request) -> HTMLResponse | RedirectResponse:
    if redirect := require_login(request):
        return redirect
    # Same calm-fallback shape as grid()/insights() (W4_review.md MINOR-1): build_your_data_
    # summary() degrades an unreadable *price* leg on its own (src/web/your_data.py's
    # _price_leg_stats()), but this still catches anything unexpected in the BOM/sales path
    # itself, so the trust page never bare-500s.
    try:
        summary = build_your_data_summary()
    except Exception:
        correlation_id = uuid4().hex[:8]
        _log.exception("your-data render failed (correlation_id=%s)", correlation_id)
        return _templates.TemplateResponse(
            request=request,
            name="error.html",
            context={"correlation_id": correlation_id},
            status_code=503,
        )
    return _templates.TemplateResponse(
        request=request, name="your_data.html", context={"summary": summary},
    )


@app.get("/your-data/export/{leg}", response_model=None)
def your_data_export(request: Request, leg: str) -> PlainTextResponse | RedirectResponse:
    if redirect := require_login(request):
        return redirect
    exporters = {
        "bom": ("bom.csv", export_bom_csv),
        "sales": ("sales_export.csv", export_sales_csv),
        "prices": ("price_observations.csv", export_price_observations_csv),
    }
    match = exporters.get(leg)
    if match is None:
        correlation_id = uuid4().hex[:8]
        _log.warning("your-data export requested unknown leg %r (correlation_id=%s)", leg, correlation_id)
        return PlainTextResponse("Unknown export.", status_code=404)
    filename, export_fn = match
    try:
        csv_text = export_fn()
    except FileNotFoundError:
        return PlainTextResponse("No data captured yet.", status_code=404)
    except Exception:
        # A present-but-corrupt/unreadable file is a different failure than "never captured" —
        # never let it fall through to a bare 500 (W4_review.md MINOR-1, same fix as the route).
        correlation_id = uuid4().hex[:8]
        _log.exception("your-data export failed for leg %r (correlation_id=%s)", leg, correlation_id)
        return PlainTextResponse(
            f"Temporarily unable to export this data (ref {correlation_id}).", status_code=503,
        )
    return PlainTextResponse(
        csv_text, media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@app.get("/upload", response_class=HTMLResponse, response_model=None)
def upload_form(request: Request) -> HTMLResponse | RedirectResponse:
    if redirect := require_login(request):
        return redirect
    return _templates.TemplateResponse(request=request, name="upload.html", context={"errors": []})


@app.post("/upload", response_class=HTMLResponse, response_model=None)
async def upload_submit(
    request: Request,
    sales_file: UploadFile = File(...),
    bom_file: UploadFile = File(...),
) -> HTMLResponse | RedirectResponse:
    if redirect := require_login(request):
        return redirect
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


@app.post("/confirm", response_class=HTMLResponse, response_model=None)
def confirm_submit(
    request: Request,
    sales_csv_b64: str = Form(...),
    bom_csv_b64: str = Form(...),
) -> HTMLResponse | RedirectResponse:
    if redirect := require_login(request):
        return redirect
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
        write_seam_atomic(bom_result.rows, sales_result.rows, store.RAW_DIR)
    except Exception:
        correlation_id = uuid4().hex[:8]
        _log.exception("seam write failed (correlation_id=%s)", correlation_id)
        return _templates.TemplateResponse(
            request=request, name="error.html", context={"correlation_id": correlation_id},
            status_code=503,
        )

    summary = build_summary(bom_result.rows, sales_result.rows)
    return _templates.TemplateResponse(request=request, name="success.html", context={"summary": summary})


@app.get("/invoice/upload", response_class=HTMLResponse, response_model=None)
def invoice_upload_form(request: Request) -> HTMLResponse | RedirectResponse:
    if redirect := require_login(request):
        return redirect
    return _templates.TemplateResponse(
        request=request, name="invoice_upload.html", context={"errors": []},
    )


@app.post("/invoice/upload", response_class=HTMLResponse, response_model=None)
async def invoice_upload_submit(
    request: Request, invoice_file: UploadFile = File(...),
) -> HTMLResponse | RedirectResponse:
    if redirect := require_login(request):
        return redirect
    invoice_bytes = await invoice_file.read(MAX_UPLOAD_BYTES + 1)

    errors = _invoice_size_errors(invoice_bytes)
    if errors:
        return _templates.TemplateResponse(
            request=request, name="invoice_upload.html", context={"errors": errors}, status_code=422,
        )

    result = parse_invoice_csv(invoice_bytes)
    if result.errors:
        return _templates.TemplateResponse(
            request=request, name="invoice_upload.html", context={"errors": result.errors}, status_code=422,
        )

    unmatched = cross_reference_ingredients(result.rows, _known_ingredient_ids())
    context = {
        "summary": build_invoice_summary(result.rows),
        "unmatched": unmatched,
        "invoice_csv_b64": _b64(invoice_bytes),
    }
    return _templates.TemplateResponse(request=request, name="invoice_confirm.html", context=context)


@app.post("/invoice/confirm", response_class=HTMLResponse, response_model=None)
def invoice_confirm_submit(
    request: Request, invoice_csv_b64: str = Form(...),
) -> HTMLResponse | RedirectResponse:
    if redirect := require_login(request):
        return redirect
    try:
        invoice_bytes = b64decode(invoice_csv_b64, validate=True)
    except binascii.Error:
        correlation_id = uuid4().hex[:8]
        _log.warning("invoice confirm payload was not valid base64 (correlation_id=%s)", correlation_id)
        return _templates.TemplateResponse(
            request=request, name="error.html", context={"correlation_id": correlation_id},
            status_code=400,
        )

    # /invoice/confirm is directly POST-able — re-apply the same size + parse checks /invoice/
    # upload ran rather than trusting the round-tripped hidden field (mirrors /confirm above).
    errors = _invoice_size_errors(invoice_bytes)
    if errors:
        return _templates.TemplateResponse(
            request=request, name="invoice_upload.html", context={"errors": errors}, status_code=422,
        )

    result = parse_invoice_csv(invoice_bytes)
    if result.errors:
        correlation_id = uuid4().hex[:8]
        _log.warning(
            "invoice confirm re-validation failed (correlation_id=%s): %s",
            correlation_id, result.errors,
        )
        return _templates.TemplateResponse(
            request=request, name="error.html", context={"correlation_id": correlation_id},
            status_code=400,
        )

    try:
        write_price_observations_atomic(result.rows, store.RAW_DIR)
    except Exception:
        correlation_id = uuid4().hex[:8]
        _log.exception("price observation write failed (correlation_id=%s)", correlation_id)
        return _templates.TemplateResponse(
            request=request, name="error.html", context={"correlation_id": correlation_id},
            status_code=503,
        )

    summary = build_invoice_summary(result.rows)
    return _templates.TemplateResponse(
        request=request, name="invoice_success.html", context={"summary": summary},
    )


@app.get("/insights", response_class=HTMLResponse, response_model=None)
def insights(request: Request) -> HTMLResponse | RedirectResponse:
    if redirect := require_login(request):
        return redirect
    try:
        summary = build_insights_summary()
    except Exception:
        # Fail legibly (rules 06/07), mirroring the grid route: a calm page + correlation id, never
        # a bare 500. dish_ingredient_cost already degrades a non-convertible unit to "not costed"
        # (W3_review.md MAJOR-1), so this is defense-in-depth for anything else that goes wrong.
        correlation_id = uuid4().hex[:8]
        _log.exception("insights render failed (correlation_id=%s)", correlation_id)
        return _templates.TemplateResponse(
            request=request,
            name="error.html",
            context={"correlation_id": correlation_id},
            status_code=503,
        )
    return _templates.TemplateResponse(
        request=request, name="insights.html", context={"summary": summary},
    )


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


def _invoice_size_errors(raw: bytes) -> list[str]:
    """Same size policy as ``_size_errors``, for the single-file invoice upload."""
    if len(raw) > MAX_UPLOAD_BYTES:
        return [f"Invoice file is too large (max {MAX_UPLOAD_BYTES // 1000} KB)."]
    return []


def _known_ingredient_ids() -> set[str]:
    """Ingredient ids already in the captured BOM, for the invoice cross-reference warning.

    An empty set (no BOM captured yet) is a valid, non-error state — every invoice ingredient
    simply shows as unmatched, which is honest: there's nothing to match against yet.
    """
    try:
        bom_df = store.read_bom()
    except FileNotFoundError:
        return set()
    return set(bom_df["ingredient_id"])
