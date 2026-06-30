"""Plate-cost pytest bootstrap.

Puts the plate_cost dir on sys.path so tests can `import src...` (the package is run as
`python -m src.run`), and the repo root so the shared `schemas` package imports the same way the
runner wires it.
"""
import sys
from pathlib import Path

_PLATE_COST = Path(__file__).resolve().parent
_REPO_ROOT = _PLATE_COST.parent.parent
for _p in (_PLATE_COST, _REPO_ROOT):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))
