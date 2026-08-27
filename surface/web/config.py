"""Environment/production posture (W7) — read once from a single module, not scattered
``os.environ`` reads through route handlers (rule 07: config/secrets resolved in one place).

``ONRAMP_ENV`` defaults to ``"development"``: local ``python -m web`` over plain HTTP keeps
cookies non-``Secure`` (a browser silently drops a ``Secure`` cookie over HTTP, which would
break login on localhost) and skips the startup guardrails below. A real deploy sets
``ONRAMP_ENV=production`` explicitly — there is no way to "accidentally" land in production
posture.
"""
from __future__ import annotations

import os

ENV_VAR = "ONRAMP_ENV"
TRUSTED_PROXY_IPS_ENV = "ONRAMP_TRUSTED_PROXY_IPS"


def is_production() -> bool:
    return os.environ.get(ENV_VAR, "development") == "production"


def trusted_proxy_ips() -> frozenset[str]:
    """The socket peers allowed to hand us a client IP via ``X-Forwarded-For`` — empty by
    default, so a direct-TLS deploy (or dev/test) keeps trusting only ``request.client.host``.
    Set to the reverse proxy's own address(es) under this phase's recommended deploy topology
    (``ensure_safe_bind``'s reverse-proxy-in-front posture); without this, the rate limiter keys
    every real visitor on the proxy's address and collapses all tenants into one shared budget
    (review finding W7_review.md MAJOR-3). Comma-separated; unset or blank trusts nothing."""
    raw = os.environ.get(TRUSTED_PROXY_IPS_ENV, "")
    return frozenset(ip.strip() for ip in raw.split(",") if ip.strip())


def resolve_tls_files() -> tuple[str | None, str | None]:
    """``(certfile, keyfile)`` from ``ONRAMP_TLS_CERTFILE``/``ONRAMP_TLS_KEYFILE`` — both set
    (direct TLS) or both unset (``(None, None)``, TLS assumed terminated by a reverse proxy in
    front of a loopback bind). Raises if exactly one is set: a half-configured TLS pair is a
    startup mistake worth failing loudly on, not silently running plaintext."""
    certfile = os.environ.get("ONRAMP_TLS_CERTFILE")
    keyfile = os.environ.get("ONRAMP_TLS_KEYFILE")
    if (certfile is None) != (keyfile is None):
        raise SystemExit("ONRAMP_TLS_CERTFILE and ONRAMP_TLS_KEYFILE must both be set, or neither.")
    return certfile, keyfile


def ensure_safe_bind(host: str, certfile: str | None) -> None:
    """Refuses to bind past loopback with no TLS material configured at all. Direct TLS
    (``certfile`` set) is one valid answer; the other is keeping ``host`` at loopback and
    fronting it with a reverse proxy on the same host/network — this check can't see the proxy,
    so it only refuses the one case it CAN see is wrong."""
    if host not in ("127.0.0.1", "localhost") and not certfile:
        raise SystemExit(
            "Refusing to bind a non-loopback host without TLS. Set ONRAMP_TLS_CERTFILE/"
            "ONRAMP_TLS_KEYFILE for direct TLS, or keep ONRAMP_HOST at 127.0.0.1 and terminate "
            "TLS at a reverse proxy in front of it (docs/phase_decisions/W7.md)."
        )


def ensure_production_config() -> None:
    """Fail fast, before the server starts accepting traffic, if ``ONRAMP_ENV=production`` is
    set but the config a real deploy needs is missing. Cheaper to crash at startup with a named
    reason than to silently serve production traffic with dev-grade defaults (an unset,
    per-process-random session story was exactly W2's "restarts log everyone out" problem this
    phase closes for the DB itself — this closes the analogous gap for the *deploy* config).

    Only checks what W7 actually introduces: ``ONRAMP_DATABASE_URL`` (a real deploy must know
    exactly where its app DB lives, never the repo-relative dev default) and
    ``ONRAMP_SMTP_HOST`` (production must not fall back to logging a live password-reset token
    server-side — ``docs/phase_decisions/W5_review.md`` LOW-2). TLS itself is checked
    separately in ``web/__main__.py`` (it also depends on ``ONRAMP_HOST``, not just ``ONRAMP_ENV``).
    """
    if not is_production():
        return
    missing = [
        name for name in ("ONRAMP_DATABASE_URL", "ONRAMP_SMTP_HOST") if not os.environ.get(name)
    ]
    if missing:
        raise SystemExit(
            "ONRAMP_ENV=production requires " + ", ".join(missing) + " to be set "
            "(docs/phase_decisions/W7.md) — refusing to start with dev-grade defaults."
        )
