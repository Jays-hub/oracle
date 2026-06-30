"""Onramp-side seam boundary — enforced inside the plate_cost suite too.

The authoritative cross-module boundary test lives at the repo root
(``tests/test_module_boundaries.py``) and runs only in the full-repo suite. A developer working in
``onramp/plate_cost/`` runs ``pytest`` *here*, where that repo-root test is not collected — so the
seam law (onramp never imports the engine, never references the engine-only hidden-oracle layer; see
``data/CONTRACT.md``) would go unchecked in exactly the suite most likely to be run while editing
onramp code.

To avoid a second copy of the scan logic, this module loads the repo-root test by path and re-runs
every onramp-side check it defines (discovered by name, so a new check is picked up automatically).
One source of truth for the logic; two suites that enforce it. When the boundary rules proliferate,
both migrate to import-linter (``data/CONTRACT.md``, rule 05).

(This file deliberately never spells out the hidden-oracle path token: the repo-root text scan flags
any onramp file containing it, and a test *about* the rule must not trip the rule. That is why the
checks are discovered and called by name rather than referenced literally.)
"""
import importlib.util
from pathlib import Path

import pytest

# plate_cost/tests -> plate_cost -> onramp -> restaurant-dev (repo root that owns tests/ and data/).
_AUTHORITATIVE = Path(__file__).resolve().parents[3] / "tests" / "test_module_boundaries.py"


def _repo_boundary():
    assert _AUTHORITATIVE.exists(), (
        f"the authoritative boundary test is missing at {_AUTHORITATIVE} — the seam law's "
        "structural enforcement has been removed"
    )
    spec = importlib.util.spec_from_file_location("_repo_boundary", _AUTHORITATIVE)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


# Discovered at collection time so each authoritative onramp-side check gets its own test id.
_ONRAMP_CHECKS = sorted(n for n in dir(_repo_boundary()) if n.startswith("test_onramp"))


@pytest.mark.parametrize("check_name", _ONRAMP_CHECKS)
def test_onramp_seam_boundary(check_name):
    """Re-run each authoritative onramp-side boundary check inside the local suite."""
    getattr(_repo_boundary(), check_name)()
