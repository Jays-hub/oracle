"""Session gate for the on-ramp's single operator account (W2).

FastAPI/Starlette glue only — the actual credential check is the pure
``src/auth/credentials.py`` (rule 05: business logic stays out of the web layer). Every
data-bearing route other than the public sample grid (``GET /``) requires a valid session;
enforced here, server-side, never left to the client (rule 06: "isolation is enforced in the
backend, never delegated to the front end").

Single-tenant today, structured for tomorrow: ``RESTAURANT_ID`` is the one seeded restaurant
every successful login is scoped to. There is exactly one tenant in the physical store
(``data/raw/`` is still a flat, unpartitioned directory — see ``docs/phase_decisions/W2.md``),
so this constant is a placeholder for where a real tenant id would flow once a second
restaurant exists, not a working multi-tenant partition.
"""
from fastapi import Request
from fastapi.responses import RedirectResponse

SESSION_KEY = "restaurant_id"
RESTAURANT_ID = "default"


def is_authenticated(request: Request) -> bool:
    return bool(request.session.get(SESSION_KEY))


def require_login(request: Request) -> RedirectResponse | None:
    """None if the session is authenticated; otherwise a redirect to /login.

    Called at the top of every protected route (``if (redirect := require_login(request)):
    return redirect``) — a plain function check, not a raised exception, to match this
    codebase's existing style of handling the not-OK path as an explicit early return rather
    than framework-level exception machinery.
    """
    if not is_authenticated(request):
        return RedirectResponse(url="/login", status_code=303)
    return None
