"""Raw/truth firewall — the static text-scan half (dependency-free).

Enforces data/CONTRACT.md's non-negotiable law: the hidden oracle under data/_truth/ is written
ONLY by `ingest/simulate/` and read ONLY by `evaluate/`. Nothing else in the repo — no layer of the
dependency chain, no shared module, no template that reaches a browser — may so much as name that
path.

**What the layer restructure changed here.** This file used to assert two peer rules as well
("onramp/ never imports forecasting/", and its mirror). Those are gone, not weakened: with the code
re-homed by layer, `.importlinter`'s `layer-direction` contract enforces the whole dependency
direction on the import graph, which is strictly more than the two peer arrows ever covered. What a
text scan still catches that the import graph does not is a *string* — a hardcoded path in a
docstring, a template, a stylesheet — so that is all this file does now.

`tests/platform/test_import_boundaries.py` is the other half: it proves the import-graph contract
actually fires, by planting a real violation and watching lint-imports go red.

Gate-4 (2026-06-25, Jay): tests confirm "the code is proper and able" — the head chef tasting the
sauce or braise during service before giving it the green light.
"""
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[2]

# Every package that is NOT sanctioned to touch the oracle. `ingest/simulate/` (writes it) and
# `evaluate/` (reads it for scoring) are the two exceptions, and are absent from this list by
# design — see data/CONTRACT.md.
_FIREWALLED_ROOTS = (
    "identity", "measures", "decide", "surface", "plays",
    "store", "db", "econ", "schemas", "scripts", "migrations",
)

# Extensions that actually reach the browser or execute at runtime — the surface a firewall
# guarantee has to cover. Deliberately excludes docs/markdown: governance files (CLAUDE.md,
# CONTRACT.md) legitimately *name* the hidden-oracle path in prose to describe the rule; a test
# about the rule must not fail on the file that documents it (W4_review.md LOW-1).
_SCANNED_SUFFIXES = (".py", ".html", ".css", ".js")


def _scanned_files(root: Path) -> list[Path]:
    if not root.exists():
        return []
    return [
        p for p in root.rglob("*")
        if p.suffix in _SCANNED_SUFFIXES and "__pycache__" not in p.parts
    ]


def _offenders(root: Path) -> list[str]:
    return [
        str(f.relative_to(_REPO_ROOT))
        for f in _scanned_files(root)
        if "_truth" in f.read_text(encoding="utf-8")
    ]


def test_no_unsanctioned_package_references_the_truth_path():
    """The whole firewall in one assertion: only ingest/simulate/ and evaluate/ may name it."""
    offenders = [name for root in _FIREWALLED_ROOTS for name in _offenders(_REPO_ROOT / root)]
    assert not offenders, (
        "only ingest/simulate/ (writes) and evaluate/ (reads) may reference data/_truth/ "
        f"— see data/CONTRACT.md: {offenders}"
    )


def test_ingest_outside_simulate_never_references_the_truth_path():
    """`ingest/` is split: simulate/ is the sanctioned writer, every other adapter is model-path
    code that must never see the oracle. Scanned separately so the exception stays surgical rather
    than exempting the whole L0 package."""
    offenders = [
        str(f.relative_to(_REPO_ROOT))
        for f in _scanned_files(_REPO_ROOT / "ingest")
        if "simulate" not in f.parts and "_truth" in f.read_text(encoding="utf-8")
    ]
    assert not offenders, (
        f"ingest/ adapters must never touch the hidden oracle (only ingest/simulate/): {offenders}"
    )


def test_web_asset_scan_would_catch_a_truth_reference_planted_in_a_template(tmp_path):
    """W4_review.md LOW-1 regression: before this fix the boundary scan covered *.py only, so a
    _truth reference in a template/CSS/JS file would pass CI unnoticed — exactly the gap W4
    opened by putting firewall prose in an .html template for the first time. Proves
    _scanned_files() actually surfaces a planted violation in a synthetic tree, without
    touching the real (clean) source tree."""
    (tmp_path / "templates").mkdir()
    offender = tmp_path / "templates" / "leaky.html"
    offender.write_text("{# never do this: data/_truth/oracle.parquet #}")
    (tmp_path / "clean.css").write_text("body { color: black; }")
    (tmp_path / "clean.txt").write_text("not a scanned suffix")

    found = _scanned_files(tmp_path)
    assert offender in found
    assert any("_truth" in f.read_text(encoding="utf-8") for f in found)
