"""Structured logging + request visibility (W7) — the "monitoring/structured logs" item in
``docs/website_production_overview.md`` row 4.

``configure_logging()`` is called exactly once, from ``web/__main__.py`` at process start — it
is deliberately **not** invoked on import here or from ``web/app.py``, since every test in this
suite imports ``web.app`` directly and relies on pytest's own ``caplog`` capture
(``test_web_auth.py::test_full_password_reset_flow_via_http``); reconfiguring the root logger's
handlers at import time would break that.
"""
from __future__ import annotations

import json
import logging
import os
import sys
import time
from datetime import datetime, timezone

from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.responses import Response

LOG_LEVEL_ENV = "ONRAMP_LOG_LEVEL"

_log = logging.getLogger("web.request")


class JsonFormatter(logging.Formatter):
    """One JSON object per line — the shape a real log aggregator (the "monitoring" half of
    this phase's deliverable) can parse without a custom grok pattern. Kept intentionally small
    (no dependency on `python-json-logger` or similar — five fields is the whole format)."""

    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "timestamp": datetime.fromtimestamp(record.created, tz=timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        if record.exc_info:
            payload["exc_info"] = self.formatException(record.exc_info)
        return json.dumps(payload)


def configure_logging(level: str | None = None) -> None:
    """Replaces the root logger's handlers with a single stdout stream in JSON. ``level``
    overrides ``ONRAMP_LOG_LEVEL`` (default ``INFO``) for callers that want to force a level
    (e.g. a future test that needs to assert on DEBUG output) without touching the environment."""
    resolved = (level or os.environ.get(LOG_LEVEL_ENV, "INFO")).upper()
    # Explicit stdout: logging.StreamHandler() with no argument defaults to stderr, which
    # disagreed with this docstring and the module docstring's "to stdout/stderr" (review
    # finding W7_review.md MINOR — some log collectors treat stderr as error-level regardless
    # of the record's actual level).
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JsonFormatter())
    root = logging.getLogger()
    root.handlers = [handler]
    root.setLevel(resolved)


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    """Logs one line per request — method, path, status, and duration — so an operator running
    this behind real hosting (W7) has request-level visibility without a separate APM agent.
    Deliberately independent of the per-route ``correlation_id`` values ``web/app.py``'s error
    handlers already generate (those name a specific *failure*; this names every *request*,
    success or not) — unifying the two is a bigger refactor than this phase's scope
    (``docs/phase_decisions/W7.md``).
    """

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        start = time.monotonic()
        try:
            response = await call_next(request)
        except Exception:
            # An unhandled exception downstream previously skipped this log line entirely (the
            # early raise never reached the success-path _log.info below) — silently omitting
            # exactly the requests a "monitoring" deliverable most needs to surface (review
            # finding W7_review.md MINOR). Log what's known, then re-raise so the normal
            # error-handling (ServerErrorMiddleware, route-level try/except) still runs.
            duration_ms = (time.monotonic() - start) * 1000
            _log.exception(
                "%s %s -> 500 (%.1fms)", request.method, request.url.path, duration_ms,
            )
            raise
        duration_ms = (time.monotonic() - start) * 1000
        _log.info(
            "%s %s -> %d (%.1fms)",
            request.method, request.url.path, response.status_code, duration_ms,
        )
        return response
