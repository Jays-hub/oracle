"""Entry point: python -m web (from onramp/plate_cost/)."""
import sys
from pathlib import Path

# Ensure plate_cost/ is on sys.path so `from src...` imports resolve
# regardless of the working directory when the server is started.
_PLATE_COST = Path(__file__).resolve().parents[1]
if str(_PLATE_COST) not in sys.path:
    sys.path.insert(0, str(_PLATE_COST))

import uvicorn  # noqa: E402 (import after sys.path bootstrap)

from .app import app  # noqa: E402

uvicorn.run(app, host="127.0.0.1", port=8000)
