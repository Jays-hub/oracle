"""Per-request CSRF protection (W7) — closes the placeholder the production overview names
("CSRF protection is same_site='lax' only", `docs/phase_decisions/W2_review.md` MINOR-3,
scheduled to W7 in `docs/website_production_overview.md` row 3).

A stateless double-submit cookie, not a session-scoped token: the middleware issues a random,
httponly ``csrf_token`` cookie on first contact and requires every state-changing request to
echo the same value back in its form body. A cross-site page can make the victim's browser
*attach* our cookie, but — because it is httponly and same-origin — can never *read* its value
to also forge a matching form field, so the two can only agree if the request actually
originated from a page we rendered. This needs no server-side token store and no signing
secret (W5 already retired the one prior signing secret entirely; this introduces no new one),
so it applies uniformly to pre-auth routes (``POST /login``) and post-auth routes alike — there
is no "logged in yet?" branch to get wrong.
"""
from __future__ import annotations

import secrets

from fastapi import Request
from fastapi.responses import PlainTextResponse
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.responses import Response

from .config import is_production

COOKIE_NAME = "csrf_token"
FIELD_NAME = "csrf_token"
_UNSAFE_METHODS = frozenset({"POST", "PUT", "PATCH", "DELETE"})

_REJECTION_MESSAGE = "Request rejected: missing or invalid CSRF token. Reload the page and try again."

# Generous headroom above the largest legitimate body today (the two-file /upload route, each
# capped at seam_upload.MAX_UPLOAD_BYTES = 700 KB, plus multipart boundary overhead) — every
# other route's form body is a few hundred bytes. Checked via Content-Length *before*
# verify_csrf_request's request.body() call, which otherwise buffers the whole body in memory
# ahead of any size/auth/token check (review finding W7_review.md MAJOR-1: an unauthenticated
# caller could force arbitrary-size in-memory buffering before the route's own size guard ever
# ran). A request with no Content-Length (chunked transfer) isn't caught here; that residual gap
# is the reverse proxy's own body-size cap under this phase's recommended deploy topology
# (web/config.py's reverse-proxy posture).
_MAX_REQUEST_BODY_BYTES = 3_000_000
_TOO_LARGE_MESSAGE = "Request body too large."


def _oversized_content_length(request: Request) -> bool:
    content_length = request.headers.get("content-length")
    if content_length is None:
        return False
    try:
        return int(content_length) > _MAX_REQUEST_BODY_BYTES
    except ValueError:
        return True  # an unparsable Content-Length is itself hostile input; reject, don't guess


async def verify_csrf_request(request: Request, cookie_token: str) -> bool:
    """True iff ``request``'s submitted ``csrf_token`` form field matches ``cookie_token``.

    A standalone module-level function (not inlined in the middleware) so a test can
    monkeypatch it directly — the same "read it fresh through the module" pattern
    ``src/db/engine.py::get_db`` documents for ``SessionLocal``.

    ``request.body()`` is read *before* ``request.form()`` on purpose, even though nothing here
    needs the raw bytes: it populates Starlette's ``Request._body`` cache, which is what lets
    ``BaseHTTPMiddleware``'s ``_CachedRequest`` replay the full body to the route handler that
    runs after this middleware. ``Request.form()`` alone drains the body via ``.stream()``
    without ever setting that cache — skip the ``.body()`` call and every downstream
    ``Form(...)``/``UploadFile`` dependency would see an empty body (verified live: every
    protected POST route 422'd with "field required" until this call was added).
    """
    await request.body()
    form = await request.form()
    submitted = form.get(FIELD_NAME)
    return bool(submitted) and secrets.compare_digest(cookie_token, str(submitted))


class CSRFMiddleware(BaseHTTPMiddleware):
    """Issues the double-submit cookie and enforces it on every unsafe-method request.

    Applies to **every** state-changing route, no exemptions — including ``POST
    /reset-password/{token}`` (its action is authorized by a URL-embedded bearer token, not by
    the ambient session cookie CSRF normally targets, but protecting it too removes an
    interpretation question and costs nothing; see `docs/phase_decisions/W7.md`).
    """

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        existing = request.cookies.get(COOKIE_NAME)
        token = existing or secrets.token_urlsafe(32)
        request.state.csrf_token = token
        needs_cookie = existing != token

        if request.method in _UNSAFE_METHODS:
            if _oversized_content_length(request):
                # Reject before verify_csrf_request's request.body() call would buffer it —
                # the size guard must run BEFORE the read, not after (MAJOR-1).
                response = PlainTextResponse(_TOO_LARGE_MESSAGE, status_code=413)
                if needs_cookie:
                    response.set_cookie(
                        COOKIE_NAME, token, httponly=True, samesite="lax", secure=is_production(),
                    )
                return response
            if not await verify_csrf_request(request, token):
                response: Response = PlainTextResponse(_REJECTION_MESSAGE, status_code=403)
                if needs_cookie:
                    response.set_cookie(
                        COOKIE_NAME, token, httponly=True, samesite="lax", secure=is_production(),
                    )
                return response

        response = await call_next(request)
        if needs_cookie:
            response.set_cookie(
                COOKIE_NAME, token, httponly=True, samesite="lax", secure=is_production(),
            )
        return response
