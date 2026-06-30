"""On-ramp web layer — W0: read-only plate-cost grid.

Single route: GET / renders the popularity × margin grid from the on-ramp's source inputs
(the same src/ chain as run.py). W0 reads source data, not the seam: data/raw/ carries only the
BOM + sales legs, which can't reconstruct margins (see web/compute.py for the why).
No writes, no auth, no JS framework. Server-rendered HTML (Jinja2) only.
(.claude/rules/05–06: thin over pure compute, fast first paint, dollar-legible.)
"""
import logging
from pathlib import Path
from uuid import uuid4

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from .compute import build_grid_data

_WEB_DIR = Path(__file__).resolve().parent

app = FastAPI(title="Plate Cost · On-Ramp", docs_url=None, redoc_url=None)
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
