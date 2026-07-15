"""In-process rate limiting for the on-ramp's most-exposed routes (W7) — login (anti-brute-
force) and the capture funnels (anti-abuse on upload endpoints), per
``docs/website_production_overview.md`` row 3's "rate limiting on the funnels."

A fixed-window counter keyed by ``(client ip, bucket name)``, held in process memory — the same
"no premature server-class DB" discipline as everywhere else in this codebase (rule 05):
correct for the current single-instance deploy, and **deliberately not shared** across multiple
worker processes or hosts (each would keep its own counters, so the real budget under N
processes is N times the configured number) — see ``docs/phase_decisions/W7.md`` Explicitly
Deferred for when that stops being good enough.
"""
from __future__ import annotations

import time

from fastapi import Request
from fastapi.responses import PlainTextResponse

from .config import trusted_proxy_ips

_WINDOW_SECONDS = 60.0

# (client_ip, bucket_name) -> (count_in_window, window_start_monotonic)
_buckets: dict[tuple[str, str], tuple[int, float]] = {}


def reset_rate_limits() -> None:
    """Test-only: clears every counter. Every test gets a fresh budget regardless of what ran
    before it (mirrors ``src/capture/staging.py``'s per-test isolation concern) — without this,
    tests sharing the TestClient's fixed fake IP would eventually 429 each other."""
    _buckets.clear()


def _client_ip(request: Request) -> str:
    """The socket peer, UNLESS that peer is a configured-trusted reverse proxy — in which case
    the real client address is read from ``X-Forwarded-For`` instead (``config.py::
    trusted_proxy_ips``). Without the allowlist gate, blindly trusting the header would let any
    caller forge its own IP to dodge its budget; without the header read at all, every visitor
    behind the recommended reverse-proxy deploy collapses onto the proxy's one address (review
    finding W7_review.md MAJOR-3). Untrusted by default (empty allowlist), so today's direct
    dev/test behavior is unchanged."""
    peer = request.client.host if request.client else "unknown"
    if peer in trusted_proxy_ips():
        forwarded = request.headers.get("x-forwarded-for")
        if forwarded:
            return forwarded.split(",")[0].strip()
    return peer


def check_rate_limit(request: Request, name: str, max_requests: int) -> PlainTextResponse | None:
    """``None`` if this request is within budget for bucket ``name``; otherwise a 429. Each
    named bucket has its own budget — a chef's own login attempts never burn their upload
    budget, and vice versa."""
    key = (_client_ip(request), name)
    now = time.monotonic()
    count, window_start = _buckets.get(key, (0, now))
    if now - window_start >= _WINDOW_SECONDS:
        count, window_start = 0, now
    count += 1
    _buckets[key] = (count, window_start)
    if count > max_requests:
        return PlainTextResponse(
            "Too many requests. Please wait a moment and try again.",
            status_code=429,
            headers={"Retry-After": str(int(_WINDOW_SECONDS))},
        )
    return None
