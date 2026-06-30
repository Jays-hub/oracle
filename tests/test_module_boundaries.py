"""Cross-module seam boundary test (static, dependency-free).

Enforces data/CONTRACT.md's non-negotiable law that the two peers couple ONLY through data/raw/:
  - onramp/ never imports forecasting/ (and vice versa)
  - onramp/ never references a data/_truth/ path (the hidden oracle is engine-only)

Implementation is a static AST + text scan, kept dependency-free for now. When these boundary
rules proliferate -- notably once the engine lands and .claude/rules/01-data-ingestion.md's
engine-INTERNAL import-boundary needs enforcing too -- migrate to import-linter (see
data/CONTRACT.md "Enforcement status (Phase 0)").

Gate-4 (2026-06-25, Jay): tests confirm "the code is proper and able" -- the head chef tasting the
sauce or braise during service before giving it the green light.
"""
import ast
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[1]


def _py_files(root: Path) -> list[Path]:
    if not root.exists():
        return []
    return [p for p in root.rglob("*.py") if "__pycache__" not in p.parts]


def _imported_roots(py_file: Path) -> set[str]:
    """Top-level module names absolutely-imported by a file (e.g. 'forecasting', 'schemas')."""
    tree = ast.parse(py_file.read_text(encoding="utf-8"), filename=str(py_file))
    roots: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                roots.add(alias.name.split(".")[0])
        elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
            roots.add(node.module.split(".")[0])
    return roots


def test_onramp_never_imports_forecasting():
    offenders = [
        str(f.relative_to(_REPO_ROOT))
        for f in _py_files(_REPO_ROOT / "onramp")
        if "forecasting" in _imported_roots(f)
    ]
    assert not offenders, f"onramp/ must not import the engine: {offenders}"


def test_forecasting_never_imports_onramp():
    offenders = [
        str(f.relative_to(_REPO_ROOT))
        for f in _py_files(_REPO_ROOT / "forecasting" / "src")
        if "onramp" in _imported_roots(f)
    ]
    assert not offenders, f"forecasting/ must not import the on-ramp: {offenders}"


def test_onramp_never_references_truth_path():
    offenders = [
        str(f.relative_to(_REPO_ROOT))
        for f in _py_files(_REPO_ROOT / "onramp")
        if "_truth" in f.read_text(encoding="utf-8")
    ]
    assert not offenders, f"onramp/ must never touch the hidden oracle (data/_truth/): {offenders}"


_ENGINE_MODEL_PATH_DIRS = ("data", "features", "models", "decision", "report")


def test_engine_model_path_never_references_truth():
    """rule 01-data-ingestion: nothing under
    forecasting/src/{data,features,models,decision,report} may reference a data/_truth/
    path. Only simulate/ writes the oracle and evaluate/ reads it. This is the structural
    first line of defense — it catches a leak at build time, before the runtime path
    assertion inside a loader ever has to fire. (Migrate to import-linter alongside the
    onramp checks when the truth loader lands and the import-level rule needs teeth.)
    """
    base = _REPO_ROOT / "forecasting" / "src"
    offenders = [
        str(f.relative_to(_REPO_ROOT))
        for sub in _ENGINE_MODEL_PATH_DIRS
        for f in _py_files(base / sub)
        if "_truth" in f.read_text(encoding="utf-8")
    ]
    assert not offenders, (
        f"engine model-path code must never touch data/_truth/ (rule 01): {offenders}"
    )
