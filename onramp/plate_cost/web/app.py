"""On-ramp web layer.

W0: GET / renders the popularity × margin grid from the on-ramp's source inputs (the same src/
chain as run.py). W0 reads source data, not the seam: data/raw/ carries only the BOM + sales
legs, which can't reconstruct margins (see web/compute.py for the why). No writes, no auth.

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

W5: the designated app DB + real identity. Login/logout now authenticate a real DB-backed
User/Credential/Session (src/auth/service.py) instead of W2's single env-configured operator
credential; the session cookie carries only an opaque token looked up (hashed) against the
sessions table, so a session is listable and revocable server-side, not just client-signed.
/upload and /invoice/upload now stage their parsed payload in the staged_uploads table
(src/capture/staging.py) instead of round-tripping it through hidden base64 form fields — the
confirm pages carry only an opaque staged_upload_id. New: GET/POST /reset-password[/{token}]
(docs/phase_decisions/W5.md).

W6: the costed reveal over the tenant's own data. GET/POST /menu-prices is the one missing seam
input — an operator sets a menu price per captured dish (src/costing/menu_prices.py, an app-DB-
only catalog); saving also recomputes and writes the derived data/raw/food_cost.parquet leg
(src/costing/tenant_grid.py), closing data/CONTRACT.md's "Co provenance" forward note. GET
/dishes is the real-tenant popularity x margin grid (the same report/grid.py math the sample
grid at GET / uses) and GET /dishes/{dish_id} is the line-by-line ingredient breakdown
(docs/phase_decisions/W6.md).

W7: production hosting + security hardening. Every state-changing POST now requires a
double-submit CSRF token (web/csrf.py); /login, /reset-password, /upload, and /invoice/upload
are rate-limited per client (web/rate_limit.py); the session cookie is Secure whenever
ONRAMP_ENV=production (web/config.py); a password-reset link is emailed through real SMTP when
ONRAMP_SMTP_HOST is configured, and only then does the server stop logging the raw token
(src/email/sender.py, closing docs/phase_decisions/W5_review.md LOW-2); every request is
logged as one structured JSON line (web/observability.py, wired up in web/__main__.py, not
here — see that module's docstring for why) (docs/phase_decisions/W7.md).

No JS framework anywhere. Server-rendered HTML (Jinja2) only.
(.claude/rules/05–07: thin over pure compute, fast first paint, dollar-legible, hostile-until-
validated input, atomic seam writes, backend-enforced tenant isolation.)
"""
import binascii
import logging
from base64 import b64decode, b64encode
from pathlib import Path
from uuid import uuid4

from fastapi import Depends, FastAPI, File, Form, Request, UploadFile
from fastapi.responses import HTMLResponse, PlainTextResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session as DbSession
from starlette.datastructures import FormData

from src import store
from src.auth.service import (
    SESSION_TTL,
    authenticate,
    create_session,
    request_password_reset,
    reset_password,
    revoke_session,
)
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
from src.capture.staging import stage_upload, take_staged_upload
from src.email.sender import send_password_reset_email

from .auth import SESSION_COOKIE, current_identity, get_db, is_authenticated, require_login
from .compute import build_grid_data
from .config import is_production
from .csrf import CSRFMiddleware
from .dishes import build_dish_detail, build_dishes_summary
from .insights import build_insights_summary
from .invoice import build_invoice_summary
from .menu_prices import (
    build_menu_prices_form,
    recompute_and_write_food_cost,
    save_menu_prices_and_recompute_food_cost,
)
from .observability import RequestLoggingMiddleware
from .rate_limit import check_rate_limit
from .upload import build_summary
from .your_data import (
    build_your_data_summary,
    export_bom_csv,
    export_food_cost_csv,
    export_price_observations_csv,
    export_sales_csv,
)

_WEB_DIR = Path(__file__).resolve().parent

app = FastAPI(title="Plate Cost · On-Ramp", docs_url=None, redoc_url=None, openapi_url=None)
app.mount("/static", StaticFiles(directory=str(_WEB_DIR / "static")), name="static")
# Registration order matters (Starlette: the LAST-added middleware ends up OUTERMOST) — CSRF is
# added first so RequestLogging wraps it and therefore logs every request, including the ones
# CSRF rejects with a 403.
app.add_middleware(CSRFMiddleware)
app.add_middleware(RequestLoggingMiddleware)


def _nav_context(request: Request) -> dict:
    """Merged into every TemplateResponse (base.html's nav needs it everywhere) — one place to
    compute it rather than every route remembering to pass logged_in itself (rule 05 reuse).
    ``csrf_token`` is read from request.state (set by CSRFMiddleware, which always runs before
    the route handler that builds this response) so every form-bearing template gets it for
    free, without each route wiring it into its own context dict."""
    return {"logged_in": is_authenticated(request), "csrf_token": getattr(request.state, "csrf_token", "")}


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


# Generous enough that a chef fat-fingering a password a few times never gets blocked, tight
# enough to slow down an automated guesser (W7: "rate limiting on the funnels" +
# security-hardening in general — brute force is the textbook target for a login endpoint).
_LOGIN_RATE_LIMIT = 10
_RESET_PASSWORD_RATE_LIMIT = 5
_RESET_CONFIRM_RATE_LIMIT = 10
_UPLOAD_RATE_LIMIT = 20


@app.post("/login", response_class=HTMLResponse, response_model=None)
def login_submit(
    request: Request, email: str = Form(...), password: str = Form(...), db: DbSession = Depends(get_db),
) -> HTMLResponse | PlainTextResponse | RedirectResponse:
    if throttled := check_rate_limit(request, "login", _LOGIN_RATE_LIMIT):
        return throttled
    user = authenticate(db, email, password)
    issued = create_session(db, user) if user is not None else None
    if issued is None:
        return _templates.TemplateResponse(
            request=request, name="login.html",
            context={"error": "Incorrect email or password."}, status_code=401,
        )
    token, _row = issued
    response = RedirectResponse(url="/your-data", status_code=303)
    response.set_cookie(
        key=SESSION_COOKIE, value=token, httponly=True, samesite="lax", secure=is_production(),
        max_age=int(SESSION_TTL.total_seconds()),
    )
    return response


@app.post("/logout")
def logout(request: Request, db: DbSession = Depends(get_db)) -> RedirectResponse:
    revoke_session(db, request.cookies.get(SESSION_COOKIE))
    response = RedirectResponse(url="/", status_code=303)
    response.delete_cookie(SESSION_COOKIE)
    return response


@app.get("/reset-password", response_class=HTMLResponse)
def reset_password_request_form(request: Request) -> HTMLResponse:
    return _templates.TemplateResponse(
        request=request, name="reset_password_request.html", context={"submitted": False},
    )


@app.post("/reset-password", response_class=HTMLResponse, response_model=None)
def reset_password_request_submit(
    request: Request, email: str = Form(...), db: DbSession = Depends(get_db),
) -> HTMLResponse | PlainTextResponse:
    if throttled := check_rate_limit(request, "reset-password", _RESET_PASSWORD_RATE_LIMIT):
        return throttled
    token = request_password_reset(db, email)
    if token is not None:
        reset_link = str(request.url_for("reset_password_form", token=token))
        # W7: real SMTP when configured (src/email/sender.py). The raw token is logged
        # server-side ONLY when no email transport exists at all — the W5 dev/localhost
        # stand-in (docs/phase_decisions/W5.md) — never once SMTP is live, since a live reset
        # token is a bearer credential and must not sit in logs when a real inbox can carry it
        # instead (closes docs/phase_decisions/W5_review.md LOW-2).
        try:
            emailed = send_password_reset_email(email.strip().lower(), reset_link)
        except Exception:
            # sender.py raises loudly (by design) when SMTP is configured but the send fails.
            # That "loud" failure must stay server-side only: the route's response can't vary
            # by whether the account exists (review finding W7_review.md MAJOR-2 — an unhandled
            # raise here 500'd only when the account existed, an enumeration oracle). Absorb it
            # into the same response and alert an operator without also reverting to the
            # raw-token-in-logs fallback, which would silently resurrect W5_review.md LOW-2.
            correlation_id = uuid4().hex[:8]
            _log.exception("password reset email send failed (correlation_id=%s)", correlation_id)
            emailed = True
        if not emailed:
            _log.info("password reset requested for %s -> /reset-password/%s", email.strip().lower(), token)
    # Identical response whether or not the account exists — this form must never confirm or
    # deny that an email has an account (enumeration defense).
    return _templates.TemplateResponse(
        request=request, name="reset_password_request.html", context={"submitted": True},
    )


@app.get("/reset-password/{token}", response_class=HTMLResponse)
def reset_password_form(request: Request, token: str) -> HTMLResponse:
    return _templates.TemplateResponse(
        request=request, name="reset_password_confirm.html", context={"token": token, "error": None},
    )


@app.post("/reset-password/{token}", response_class=HTMLResponse, response_model=None)
def reset_password_submit(
    request: Request, token: str, new_password: str = Form(...), db: DbSession = Depends(get_db),
) -> HTMLResponse | PlainTextResponse | RedirectResponse:
    # Tokens are long random values (generate_token), so brute-forcing one is already
    # impractical, but nothing else here throttled guessing attempts at all — cheap to close
    # given the bucket machinery already exists (review finding W7_review.md NIT).
    if throttled := check_rate_limit(request, "reset-confirm", _RESET_CONFIRM_RATE_LIMIT):
        return throttled
    ok = reset_password(db, token, new_password)
    if not ok:
        return _templates.TemplateResponse(
            request=request, name="reset_password_confirm.html",
            context={"token": token, "error": "This reset link is invalid, expired, or the password was too short."},
            status_code=400,
        )
    return RedirectResponse(url="/login", status_code=303)


@app.get("/your-data", response_class=HTMLResponse, response_model=None)
def your_data(request: Request, db: DbSession = Depends(get_db)) -> HTMLResponse | RedirectResponse:
    identity = current_identity(request, db)
    if identity is None:
        return RedirectResponse(url="/login", status_code=303)
    # Same calm-fallback shape as grid()/insights() (W4_review.md MINOR-1): build_your_data_
    # summary() degrades an unreadable *price* leg on its own (src/web/your_data.py's
    # _price_leg_stats()), but this still catches anything unexpected in the BOM/sales path
    # itself, so the trust page never bare-500s.
    try:
        summary = build_your_data_summary(identity.restaurant_id)
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
def your_data_export(request: Request, leg: str, db: DbSession = Depends(get_db)) -> PlainTextResponse | RedirectResponse:
    identity = current_identity(request, db)
    if identity is None:
        return RedirectResponse(url="/login", status_code=303)
    exporters = {
        "bom": ("bom.csv", export_bom_csv),
        "sales": ("sales_export.csv", export_sales_csv),
        "prices": ("price_observations.csv", export_price_observations_csv),
        "food_cost": ("food_cost.csv", export_food_cost_csv),
    }
    match = exporters.get(leg)
    if match is None:
        correlation_id = uuid4().hex[:8]
        _log.warning("your-data export requested unknown leg %r (correlation_id=%s)", leg, correlation_id)
        return PlainTextResponse("Unknown export.", status_code=404)
    filename, export_fn = match
    try:
        csv_text = export_fn(identity.restaurant_id)
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
def upload_form(request: Request, db: DbSession = Depends(get_db)) -> HTMLResponse | RedirectResponse:
    if redirect := require_login(request, db):
        return redirect
    return _templates.TemplateResponse(request=request, name="upload.html", context={"errors": []})


@app.post("/upload", response_class=HTMLResponse, response_model=None)
async def upload_submit(
    request: Request,
    sales_file: UploadFile = File(...),
    bom_file: UploadFile = File(...),
    db: DbSession = Depends(get_db),
) -> HTMLResponse | PlainTextResponse | RedirectResponse:
    identity = current_identity(request, db)
    if identity is None:
        return RedirectResponse(url="/login", status_code=303)
    if throttled := check_rate_limit(request, "upload", _UPLOAD_RATE_LIMIT):
        return throttled
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
    # W5: the parsed payload is staged server-side (src/capture/staging.py) instead of round-
    # tripped through hidden base64 form fields — the confirm page's client only ever holds this
    # row's opaque id, never the bytes themselves (docs/phase_decisions/W5.md).
    staged_id = stage_upload(
        db, identity.user_id, identity.restaurant_id, kind="bom_sales",
        payload={"sales_csv_b64": _b64(sales_bytes), "bom_csv_b64": _b64(bom_bytes)},
    )
    context = {
        "summary": build_summary(bom_result.rows, sales_result.rows),
        "only_in_bom": only_in_bom,
        "only_in_sales": only_in_sales,
        "staged_upload_id": staged_id,
    }
    return _templates.TemplateResponse(request=request, name="confirm.html", context=context)


@app.post("/confirm", response_class=HTMLResponse, response_model=None)
def confirm_submit(
    request: Request, staged_upload_id: str = Form(...), db: DbSession = Depends(get_db),
) -> HTMLResponse | RedirectResponse:
    identity = current_identity(request, db)
    if identity is None:
        return RedirectResponse(url="/login", status_code=303)

    payload = take_staged_upload(db, staged_upload_id, identity.user_id, kind="bom_sales")
    if payload is None:
        correlation_id = uuid4().hex[:8]
        _log.warning(
            "confirm referenced an unknown/expired/consumed staged upload (correlation_id=%s)",
            correlation_id,
        )
        return _templates.TemplateResponse(
            request=request, name="error.html", context={"correlation_id": correlation_id},
            status_code=400,
        )
    try:
        sales_bytes = b64decode(payload["sales_csv_b64"], validate=True)
        bom_bytes = b64decode(payload["bom_csv_b64"], validate=True)
    except (binascii.Error, KeyError):
        correlation_id = uuid4().hex[:8]
        _log.warning("confirm staged payload was malformed (correlation_id=%s)", correlation_id)
        return _templates.TemplateResponse(
            request=request, name="error.html", context={"correlation_id": correlation_id},
            status_code=400,
        )

    # /confirm never assumes a boundary check done at /upload still holds — re-apply the same
    # size policy and re-run the exact same parse/validation the /upload step ran, rather than
    # trusting the staged payload blindly (rule 07). The staging table replaced *how* the payload
    # gets from /upload to /confirm; it did not remove the need to re-validate it here.
    errors = _size_errors(sales_bytes, bom_bytes)
    if errors:
        return _templates.TemplateResponse(
            request=request, name="upload.html", context={"errors": errors}, status_code=422,
        )

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
        write_seam_atomic(bom_result.rows, sales_result.rows, store.tenant_raw_dir(identity.restaurant_id))
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
def invoice_upload_form(request: Request, db: DbSession = Depends(get_db)) -> HTMLResponse | RedirectResponse:
    if redirect := require_login(request, db):
        return redirect
    return _templates.TemplateResponse(
        request=request, name="invoice_upload.html", context={"errors": []},
    )


@app.post("/invoice/upload", response_class=HTMLResponse, response_model=None)
async def invoice_upload_submit(
    request: Request, invoice_file: UploadFile = File(...), db: DbSession = Depends(get_db),
) -> HTMLResponse | PlainTextResponse | RedirectResponse:
    identity = current_identity(request, db)
    if identity is None:
        return RedirectResponse(url="/login", status_code=303)
    if throttled := check_rate_limit(request, "upload", _UPLOAD_RATE_LIMIT):
        return throttled
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

    unmatched = cross_reference_ingredients(result.rows, _known_ingredient_ids(identity.restaurant_id))
    staged_id = stage_upload(
        db, identity.user_id, identity.restaurant_id, kind="invoice",
        payload={"invoice_csv_b64": _b64(invoice_bytes)},
    )
    context = {
        "summary": build_invoice_summary(result.rows),
        "unmatched": unmatched,
        "staged_upload_id": staged_id,
    }
    return _templates.TemplateResponse(request=request, name="invoice_confirm.html", context=context)


@app.post("/invoice/confirm", response_class=HTMLResponse, response_model=None)
def invoice_confirm_submit(
    request: Request, staged_upload_id: str = Form(...), db: DbSession = Depends(get_db),
) -> HTMLResponse | RedirectResponse:
    identity = current_identity(request, db)
    if identity is None:
        return RedirectResponse(url="/login", status_code=303)

    payload = take_staged_upload(db, staged_upload_id, identity.user_id, kind="invoice")
    if payload is None:
        correlation_id = uuid4().hex[:8]
        _log.warning(
            "invoice confirm referenced an unknown/expired/consumed staged upload (correlation_id=%s)",
            correlation_id,
        )
        return _templates.TemplateResponse(
            request=request, name="error.html", context={"correlation_id": correlation_id},
            status_code=400,
        )
    try:
        invoice_bytes = b64decode(payload["invoice_csv_b64"], validate=True)
    except (binascii.Error, KeyError):
        correlation_id = uuid4().hex[:8]
        _log.warning("invoice confirm staged payload was malformed (correlation_id=%s)", correlation_id)
        return _templates.TemplateResponse(
            request=request, name="error.html", context={"correlation_id": correlation_id},
            status_code=400,
        )

    # /invoice/confirm is directly POST-able — re-apply the same size + parse checks
    # /invoice/upload ran rather than trusting the staged payload (mirrors /confirm above).
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
        write_price_observations_atomic(result.rows, store.tenant_raw_dir(identity.restaurant_id))
    except Exception:
        correlation_id = uuid4().hex[:8]
        _log.exception("price observation write failed (correlation_id=%s)", correlation_id)
        return _templates.TemplateResponse(
            request=request, name="error.html", context={"correlation_id": correlation_id},
            status_code=503,
        )

    # A new invoice can change Co for every dish it prices — recompute the derived food_cost
    # seam leg here too, not just on menu-price save, so it never goes stale after a price-only
    # invoice upload (W6_review.md MINOR-3). Best-effort: no consumer reads this leg yet, so a
    # failure here must never fail the invoice confirmation the operator actually came for.
    try:
        bom_df = store.read_bom(identity.restaurant_id)
    except FileNotFoundError:
        bom_df = None
    if bom_df is not None:
        try:
            recompute_and_write_food_cost(bom_df, identity.restaurant_id)
        except Exception:
            _log.exception(
                "food_cost recompute after invoice confirm failed (correlation_id=%s)",
                uuid4().hex[:8],
            )

    summary = build_invoice_summary(result.rows)
    return _templates.TemplateResponse(
        request=request, name="invoice_success.html", context={"summary": summary},
    )


@app.get("/insights", response_class=HTMLResponse, response_model=None)
def insights(request: Request, db: DbSession = Depends(get_db)) -> HTMLResponse | RedirectResponse:
    identity = current_identity(request, db)
    if identity is None:
        return RedirectResponse(url="/login", status_code=303)
    try:
        summary = build_insights_summary(identity.restaurant_id)
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


@app.get("/menu-prices", response_class=HTMLResponse, response_model=None)
def menu_prices_form(request: Request, db: DbSession = Depends(get_db)) -> HTMLResponse | RedirectResponse:
    identity = current_identity(request, db)
    if identity is None:
        return RedirectResponse(url="/login", status_code=303)
    try:
        rows = build_menu_prices_form(db, identity.restaurant_id)
    except Exception:
        correlation_id = uuid4().hex[:8]
        _log.exception("menu-prices form render failed (correlation_id=%s)", correlation_id)
        return _templates.TemplateResponse(
            request=request, name="error.html", context={"correlation_id": correlation_id},
            status_code=503,
        )
    return _templates.TemplateResponse(
        request=request, name="menu_prices.html", context={"rows": rows, "errors": []},
    )


@app.post("/menu-prices", response_class=HTMLResponse, response_model=None)
async def menu_prices_submit(request: Request, db: DbSession = Depends(get_db)) -> HTMLResponse | RedirectResponse:
    identity = current_identity(request, db)
    if identity is None:
        return RedirectResponse(url="/login", status_code=303)

    form = await request.form()
    try:
        dish_names = (
            store.read_bom(identity.restaurant_id)
            .drop_duplicates("dish_id").set_index("dish_id")["dish_name"].to_dict()
        )
    except FileNotFoundError:
        dish_names = {}
    prices_by_dish_id, errors = _parse_menu_price_form(form, dish_names)
    if errors:
        rows = build_menu_prices_form(db, identity.restaurant_id)
        return _templates.TemplateResponse(
            request=request, name="menu_prices.html", context={"rows": rows, "errors": errors},
            status_code=422,
        )

    try:
        save_menu_prices_and_recompute_food_cost(db, identity.restaurant_id, prices_by_dish_id)
    except Exception:
        correlation_id = uuid4().hex[:8]
        _log.exception("menu-price save failed (correlation_id=%s)", correlation_id)
        return _templates.TemplateResponse(
            request=request, name="error.html", context={"correlation_id": correlation_id},
            status_code=503,
        )
    return RedirectResponse(url="/dishes", status_code=303)


@app.get("/dishes", response_class=HTMLResponse, response_model=None)
def dishes_grid(request: Request, db: DbSession = Depends(get_db)) -> HTMLResponse | RedirectResponse:
    identity = current_identity(request, db)
    if identity is None:
        return RedirectResponse(url="/login", status_code=303)
    try:
        summary = build_dishes_summary(db, identity.restaurant_id)
    except Exception:
        correlation_id = uuid4().hex[:8]
        _log.exception("dishes grid render failed (correlation_id=%s)", correlation_id)
        return _templates.TemplateResponse(
            request=request, name="error.html", context={"correlation_id": correlation_id},
            status_code=503,
        )
    return _templates.TemplateResponse(
        request=request, name="dishes.html", context={"summary": summary},
    )


@app.get("/dishes/{dish_id}", response_class=HTMLResponse, response_model=None)
def dish_detail_page(
    request: Request, dish_id: str, db: DbSession = Depends(get_db),
) -> HTMLResponse | RedirectResponse:
    identity = current_identity(request, db)
    if identity is None:
        return RedirectResponse(url="/login", status_code=303)
    try:
        detail = build_dish_detail(db, identity.restaurant_id, dish_id)
    except Exception:
        correlation_id = uuid4().hex[:8]
        _log.exception("dish detail render failed (correlation_id=%s)", correlation_id)
        return _templates.TemplateResponse(
            request=request, name="error.html", context={"correlation_id": correlation_id},
            status_code=503,
        )
    if not detail["found"]:
        return _templates.TemplateResponse(
            request=request, name="dish_not_found.html", context={"dish_id": dish_id},
            status_code=404,
        )
    return _templates.TemplateResponse(
        request=request, name="dish_detail.html", context={"detail": detail},
    )


def _parse_menu_price_form(
    form: FormData, dish_names: dict[str, str]
) -> tuple[dict[str, float], list[str]]:
    """Form fields are named ``price__<seam dish_id>`` (menu_prices.html) — a blank value leaves
    that dish's price unset (not an error, since a chef may only want to price some dishes today),
    but a non-blank, non-positive value is rejected and named (rule 07: hostile input, name which
    field failed). ``dish_names`` (the current BOM's ``{seam dish_id: display name}``) lets the
    error message speak the chef's language ("Caesar Salad") instead of the internal
    ``normalize_name()`` key ("caesar salad") — falls back to the raw key for a dish_id the
    current BOM no longer recognizes (W6_review.md NIT)."""
    prices_by_dish_id: dict[str, float] = {}
    errors: list[str] = []
    for key, value in form.multi_items():
        if not key.startswith("price__"):
            continue
        dish_id = key[len("price__"):]
        raw = (value or "").strip()
        if not raw:
            continue
        try:
            price = float(raw)
            if price <= 0:
                raise ValueError
        except ValueError:
            label = dish_names.get(dish_id, dish_id)
            errors.append(f"{label}: menu price must be a positive number.")
            continue
        prices_by_dish_id[dish_id] = price
    return prices_by_dish_id, errors


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


def _known_ingredient_ids(restaurant_id: str) -> set[str]:
    """Ingredient ids already in the captured BOM, for the invoice cross-reference warning.

    An empty set (no BOM captured yet) is a valid, non-error state — every invoice ingredient
    simply shows as unmatched, which is honest: there's nothing to match against yet.
    """
    try:
        bom_df = store.read_bom(restaurant_id)
    except FileNotFoundError:
        return set()
    return set(bom_df["ingredient_id"])
