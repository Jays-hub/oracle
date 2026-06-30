"""Repo-root pytest bootstrap.

Puts the repo root on sys.path so platform-level tests can `import schemas` (the shared seam
definitions, owned by neither peer — see data/CONTRACT.md).
"""
import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))
