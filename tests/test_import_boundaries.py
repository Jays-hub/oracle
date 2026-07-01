"""Import-graph boundary test — the import-linter half of the seam firewall.

`test_module_boundaries.py` is a text/AST substring scan: it catches a literal `_truth` string
but is blind to import indirection (a model path doing `from forecasting.src.evaluate import
load_truth` carries no `_truth` string and would sail through it green). `.importlinter`
(repo root) defines the real import-graph contract; this test proves the contract actually has
teeth by planting a real violation, in real source, and confirming `lint-imports` catches it —
per docs/agentic_workflow/efficiency_backlog.md #4's "ship the planted-violation test" doctrine.
A guard you have never watched fail is a guard you do not know works.
"""
import subprocess
import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[1]

# The exact leak class backlog #4 names: a model-path module reaching a truth-adjacent
# submodule of evaluate/ through an ordinary import, with no "_truth" substring anywhere.
_PLANTED_VIOLATION = _REPO_ROOT / "forecasting" / "src" / "models" / "_planted_violation_tmp.py"
_PLANTED_VIOLATION_SOURCE = (
    "# Planted by tests/test_import_boundaries.py — must never survive a test run.\n"
    "from forecasting.src.evaluate.backtest import RollingOriginBacktest  # noqa: F401\n"
)


def _run_lint_imports() -> subprocess.CompletedProcess:
    return subprocess.run(
        ["lint-imports"],
        cwd=_REPO_ROOT,
        capture_output=True,
        text=True,
    )


def test_import_linter_contract_currently_passes():
    """Sanity check: the real, unmodified repo satisfies its own import contract."""
    result = _run_lint_imports()
    assert result.returncode == 0, (
        f"`.importlinter` contract is broken on a clean checkout:\n{result.stdout}\n{result.stderr}"
    )


def test_import_linter_catches_planted_truth_import():
    """Plant a real model-path -> evaluate.backtest import, confirm lint-imports goes red,
    then remove it and confirm the repo is clean again. Proves the import-graph contract
    (not just the substring scan) would catch the exact indirection leak class this project
    already suffered once (the truth-tainted $159,435 floor)."""
    assert not _PLANTED_VIOLATION.exists(), (
        f"stale planted-violation fixture left behind: {_PLANTED_VIOLATION}"
    )
    try:
        _PLANTED_VIOLATION.write_text(_PLANTED_VIOLATION_SOURCE, encoding="utf-8")
        result = _run_lint_imports()
        assert result.returncode != 0, (
            "lint-imports did not flag a planted forecasting.src.models -> "
            f"forecasting.src.evaluate.backtest import:\n{result.stdout}"
        )
        assert "BROKEN" in result.stdout
    finally:
        _PLANTED_VIOLATION.unlink(missing_ok=True)
        for pyc in _PLANTED_VIOLATION.parent.glob("__pycache__/_planted_violation_tmp*"):
            pyc.unlink(missing_ok=True)

    # The guard is silent again once the planted file is gone.
    result = _run_lint_imports()
    assert result.returncode == 0, (
        f"repo did not return to a clean import-lint state after cleanup:\n{result.stdout}"
    )


def test_python_executable_is_the_pinned_env():
    """Guard the guard: if this ever runs under a python without lint-imports on PATH
    (e.g. `base` instead of `restaurant-dev`), fail loud rather than silently pass because
    the subprocess call itself errored before reaching an assertion."""
    result = subprocess.run(["which", "lint-imports"], capture_output=True, text=True)
    assert result.returncode == 0, (
        "lint-imports is not on PATH — this suite must run via `make test` "
        f"(conda env restaurant-dev), not a bare {sys.executable}"
    )
