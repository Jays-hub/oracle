"""Entry point: python -m surface.web (from the repo root).

No sys.path bootstrap: every layer package (identity/, ingest/, measures/, store/, db/, schemas/)
now lives at the repo root, so running the module at all means the root is already importable.
"""
import os

import uvicorn

from .app import app
from .config import ensure_production_config, ensure_safe_bind, resolve_tls_files
from .observability import configure_logging

configure_logging()
ensure_production_config()

# W7: TLS. The startup guards below live in web/config.py (pure functions, unit-tested there) —
# this entry point stays a thin sequence of "resolve config, validate it, run" (rule 07: thin
# controllers), not a place to hand-test raise/SystemExit branches against a live uvicorn.run().
_certfile, _keyfile = resolve_tls_files()
_host = os.environ.get("ONRAMP_HOST", "127.0.0.1")
_port = int(os.environ.get("ONRAMP_PORT", "8000"))
ensure_safe_bind(_host, _certfile)

uvicorn.run(app, host=_host, port=_port, ssl_certfile=_certfile, ssl_keyfile=_keyfile)
