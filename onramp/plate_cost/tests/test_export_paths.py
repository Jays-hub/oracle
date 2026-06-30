"""Regression test for the seam-export path bug (task #1).

The original `_REPO_ROOT = _PLATE_COST_DIR.parent.parent.parent` climbed one level too high (into
the parent of the repo), so the export silently landed outside the repo instead of in the shared
seam. This locks the resolution to the actual repo root.
"""
from pathlib import Path

from src import run

# tests -> plate_cost -> onramp -> repo root
_REPO_ROOT = Path(__file__).resolve().parents[3]


def test_repo_root_is_the_repo_not_its_parent():
    assert run._REPO_ROOT == _REPO_ROOT
    assert run._REPO_ROOT != _REPO_ROOT.parent
    # The repo root owns the shared seam and the shared schemas; its parent does not.
    assert (run._REPO_ROOT / "data" / "raw").is_dir()
    assert (run._REPO_ROOT / "schemas" / "seam.py").is_file()
