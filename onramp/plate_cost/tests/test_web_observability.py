"""Tests for the W7 structured logging + request-log middleware (web/observability.py)."""
import json
import logging

from fastapi.testclient import TestClient
from starlette.applications import Starlette
from starlette.routing import Route
from starlette.testclient import TestClient as StarletteTestClient

from web.app import app
from web.observability import JsonFormatter, RequestLoggingMiddleware, configure_logging


def test_json_formatter_produces_one_parseable_json_object():
    record = logging.LogRecord(
        name="test.logger", level=logging.INFO, pathname=__file__, lineno=1,
        msg="hello %s", args=("world",), exc_info=None,
    )
    line = JsonFormatter().format(record)
    payload = json.loads(line)
    assert payload["message"] == "hello world"
    assert payload["level"] == "INFO"
    assert payload["logger"] == "test.logger"
    assert "timestamp" in payload


def test_json_formatter_includes_exc_info_when_present():
    try:
        raise ValueError("boom")
    except ValueError:
        record = logging.LogRecord(
            name="test.logger", level=logging.ERROR, pathname=__file__, lineno=1,
            msg="failed", args=(), exc_info=__import__("sys").exc_info(),
        )
    payload = json.loads(JsonFormatter().format(record))
    assert "ValueError" in payload["exc_info"]
    assert "boom" in payload["exc_info"]


def test_request_logging_middleware_logs_method_path_and_status(caplog):
    client = TestClient(app)
    with caplog.at_level("INFO", logger="web.request"):
        client.get("/")
    messages = [r.message for r in caplog.records if r.name == "web.request"]
    assert any("GET" in m and "/" in m and "200" in m for m in messages)


def test_request_logging_middleware_does_not_swallow_the_response():
    """The middleware wraps every response -- it must return the SAME response, not a
    replacement, or every route's actual content/status would be lost."""
    client = TestClient(app)
    resp = client.get("/")
    assert resp.status_code == 200
    assert "Plate Cost" in resp.text


def test_request_logging_middleware_logs_a_line_for_requests_that_raise(caplog):
    """Regression for W7_review.md MINOR: the middleware used to log only AFTER call_next
    returned, so a downstream exception (e.g. an unhandled route error) skipped the structured
    log line entirely -- silently omitting exactly the requests a monitoring deliverable most
    needs. A tiny standalone Starlette app isolates this from web.app's own routes, none of
    which currently raise unhandled (their try/except already convert failures to a calm 503)."""

    async def boom(request):
        raise ValueError("boom")

    tiny_app = Starlette(routes=[Route("/boom", boom)])
    tiny_app.add_middleware(RequestLoggingMiddleware)
    client = StarletteTestClient(tiny_app, raise_server_exceptions=False)

    with caplog.at_level("ERROR", logger="web.request"):
        resp = client.get("/boom")

    assert resp.status_code == 500
    messages = [r.message for r in caplog.records if r.name == "web.request"]
    assert any("GET" in m and "/boom" in m and "500" in m for m in messages)


def test_configure_logging_writes_to_stdout_not_stderr(capsys):
    """Regression for W7_review.md MINOR: configure_logging's docstring (and the module
    docstring) promised stdout, but bare logging.StreamHandler() defaults to stderr."""
    root = logging.getLogger()
    original_handlers, original_level = root.handlers[:], root.level
    try:
        configure_logging(level="INFO")
        logging.getLogger("web.test.stdout_check").info("hello-stdout-check")
        captured = capsys.readouterr()
        assert "hello-stdout-check" in captured.out
        assert "hello-stdout-check" not in captured.err
    finally:
        root.handlers[:] = original_handlers
        root.setLevel(original_level)
