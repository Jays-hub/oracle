"""Outbound email (W7) — currently just the password-reset link, the one transactional email
the app sends today. DB- and framework-agnostic (rule 05: no FastAPI import); ``web/app.py`` is
the only caller that knows this exists.

Env-configured SMTP (rule 07: secrets/connection details live in env). When
``ONRAMP_SMTP_HOST`` is unset — local dev, and every test in this suite — sending is a no-op
that returns ``False`` without attempting a network connection; the caller falls back to W5's
log-the-link stand-in *only* in that case. The moment SMTP **is** configured, the caller must
stop logging the raw token (closes ``docs/phase_decisions/W5_review.md`` LOW-2 — "a reset token
... must not survive to any shared/hosted environment").
"""
from __future__ import annotations

import logging
import os
import smtplib
from email.message import EmailMessage

_log = logging.getLogger(__name__)

SMTP_HOST_ENV = "ONRAMP_SMTP_HOST"
SMTP_PORT_ENV = "ONRAMP_SMTP_PORT"
SMTP_USERNAME_ENV = "ONRAMP_SMTP_USERNAME"
SMTP_PASSWORD_ENV = "ONRAMP_SMTP_PASSWORD"
SMTP_FROM_ENV = "ONRAMP_SMTP_FROM"

_DEFAULT_PORT = 587
_DEFAULT_FROM = "no-reply@plate-cost.local"
_TIMEOUT_SECONDS = 10


def is_configured() -> bool:
    return bool(os.environ.get(SMTP_HOST_ENV))


def send_password_reset_email(to_email: str, reset_link: str) -> bool:
    """``True`` iff the message was handed off to the SMTP server. ``False`` iff SMTP isn't
    configured at all — the expected dev/test state, not an error. If ``ONRAMP_SMTP_HOST`` *is*
    set, an SMTP failure raises rather than silently returning ``False``: a misconfigured
    production deploy must fail loudly, never quietly revert to the log-the-token fallback that
    is only acceptable when there is no email transport at all.
    """
    if not is_configured():
        return False

    message = EmailMessage()
    message["Subject"] = "Reset your Plate Cost password"
    message["From"] = os.environ.get(SMTP_FROM_ENV, _DEFAULT_FROM)
    message["To"] = to_email
    message.set_content(
        "Reset your password using the link below. This link expires in 1 hour.\n\n"
        f"{reset_link}\n\n"
        "If you did not request this, you can safely ignore this email."
    )

    host = os.environ[SMTP_HOST_ENV]
    port = int(os.environ.get(SMTP_PORT_ENV, _DEFAULT_PORT))
    username = os.environ.get(SMTP_USERNAME_ENV)
    password = os.environ.get(SMTP_PASSWORD_ENV)

    with smtplib.SMTP(host, port, timeout=_TIMEOUT_SECONDS) as client:
        client.starttls()
        if username and password:
            client.login(username, password)
        client.send_message(message)
    _log.info("password reset email sent to %s", to_email)
    return True
