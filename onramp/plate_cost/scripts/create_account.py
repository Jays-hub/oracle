#!/usr/bin/env python
"""Invite-only account creation (W5).

There is no public "sign up" route in ``web/app.py`` — this script is the only way to create an
on-ramp account while the site has no hosting/identity-verification story yet
(``docs/website_production_overview.md`` W5 row: "invite-only account creation until hosted, no
public signup on localhost"). Run from ``onramp/plate_cost/``, after ``make migrate`` (or
``alembic upgrade head``) has created the app DB::

    python scripts/create_account.py --restaurant "Marco's Trattoria" --email chef@example.com

Prompts for the password via ``getpass`` rather than accepting it as a CLI argument — a
command-line argument would sit in plain text in shell history and any process listing (`ps`)
for as long as the shell session lives, which a live credential must never do.
"""
from __future__ import annotations

import argparse
import getpass
import sys
from pathlib import Path

_PLATE_COST_DIR = Path(__file__).resolve().parents[1]
if str(_PLATE_COST_DIR) not in sys.path:
    sys.path.insert(0, str(_PLATE_COST_DIR))

from src.auth.service import MIN_PASSWORD_LENGTH, create_account  # noqa: E402
from src.db.engine import SessionLocal  # noqa: E402


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--restaurant", required=True, help="Restaurant (tenant) name")
    parser.add_argument("--email", required=True, help="The new owner's login email")
    parser.add_argument("--role", default="owner", choices=["owner", "member"])
    args = parser.parse_args(argv)

    password = getpass.getpass("New account password: ")
    confirm = getpass.getpass("Confirm password: ")
    if password != confirm:
        print("Passwords did not match.", file=sys.stderr)
        return 1
    if len(password) < MIN_PASSWORD_LENGTH:
        print(f"Password must be at least {MIN_PASSWORD_LENGTH} characters.", file=sys.stderr)
        return 1

    db = SessionLocal()
    try:
        user = create_account(db, args.restaurant, args.email, password, role=args.role)
    except ValueError as e:
        print(f"Could not create account: {e}", file=sys.stderr)
        return 1
    finally:
        db.close()

    print(f"Created {user.email!r} at {args.restaurant!r} (role={args.role}).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
