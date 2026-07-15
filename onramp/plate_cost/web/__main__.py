"""Entry point: python -m web (from onramp/plate_cost/)."""
import os
import sys
from pathlib import Path

# Ensure plate_cost/ is on sys.path so `from src...` imports resolve
# regardless of the working directory when the server is started.
_PLATE_COST = Path(__file__).resolve().parents[1]
if str(_PLATE_COST) not in sys.path:
    sys.path.insert(0, str(_PLATE_COST))

import uvicorn  # noqa: E402 (import after sys.path bootstrap)

from .app import app  # noqa: E402
from .config import ensure_production_config, ensure_safe_bind, resolve_tls_files  # noqa: E402
from .observability import configure_logging  # noqa: E402

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
