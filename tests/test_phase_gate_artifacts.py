"""CI-enforced teeth for the Comprehension Contract's review-exit gate.

`.claude/rules/00-process.md` says a phase's review may not close ("done"/"reviewed") until
Jay's verbatim comprehension explanation is captured in `docs/phase_decisions/Pn.md`. Before
this file, that was an honor-system instruction to the agent -- nothing stopped a
`docs/progress_log.md` entry claiming `[done]` from existing without a matching, filled
decision log. This test makes that combination a build failure.

Convention this test enforces going forward: a closing progress_log.md heading tagged
`` `[done]` `` or `` `[reviewed]` `` must name its phase's bare token (P0, P1, ..., W0, W1, ...)
somewhere in the heading line, e.g. "## 2026-07-01 -- P3 reviewed: censored-demand
unconstraining `[reviewed]`". `/review-phase` and `/review-web` are instructed to write closing
entries this way (efficiency_backlog.md #8).
"""
import re
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[1]
_PROGRESS_LOG = _REPO_ROOT / "docs" / "progress_log.md"
_PHASE_DECISIONS_DIR = _REPO_ROOT / "docs" / "phase_decisions"

_CLOSING_TAG_RE = re.compile(r"`\[(done|reviewed)\]`")
_PHASE_TOKEN_RE = re.compile(r"\b([PW]\d+)\b")
_PLACEHOLDER_MARKER = "<paste Jay's full explanation here"
_MISSING_MARKER = "MISSING — ask again"
_MISSING_MARKER_ASCII = "MISSING -- ask again"


def find_ungated_closed_phases(progress_log_text: str, phase_decisions_dir: Path) -> list[str]:
    """Return one violation string per closing heading that lacks a properly-filled
    Pn.md/Wn.md Comprehension Capture -- empty list means every closed phase is gated."""
    violations = []
    for line in progress_log_text.splitlines():
        if not line.startswith("## ") or not _CLOSING_TAG_RE.search(line):
            continue
        token_match = _PHASE_TOKEN_RE.search(line)
        if not token_match:
            violations.append(
                f"closing heading has no phase token (P#/W#) to check against a decision log: {line!r}"
            )
            continue
        token = token_match.group(1)
        decision_log = phase_decisions_dir / f"{token}.md"
        if not decision_log.exists():
            violations.append(
                f"{token}: closed in progress_log.md ({line!r}) but "
                f"docs/phase_decisions/{token}.md does not exist"
            )
            continue
        text = decision_log.read_text(encoding="utf-8")
        if _PLACEHOLDER_MARKER in text:
            violations.append(f"{token}: {decision_log.name} still has the unfilled placeholder block")
        elif _MISSING_MARKER in text or _MISSING_MARKER_ASCII in text:
            violations.append(f"{token}: {decision_log.name} has a MISSING citation")
    return violations


def test_no_ungated_closed_phases_in_the_real_repo():
    """Sanity check against the actual repo state (vacuously true until the first
    phase is ever closed -- the moment one is, this stops being vacuous)."""
    text = _PROGRESS_LOG.read_text(encoding="utf-8")
    violations = find_ungated_closed_phases(text, _PHASE_DECISIONS_DIR)
    assert not violations, f"phase(s) closed without a gated decision log: {violations}"


def test_detects_planted_close_with_no_decision_log(tmp_path):
    """Plant the exact failure mode this file exists to catch: a [done] entry with no
    matching Pn.md at all."""
    fake_log = "## 2026-07-01 — P99 reviewed: fake phase for the planted test `[done]`\n"
    violations = find_ungated_closed_phases(fake_log, tmp_path)
    assert len(violations) == 1
    assert "P99" in violations[0]
    assert "does not exist" in violations[0]


def test_detects_planted_close_with_unfilled_placeholder(tmp_path):
    """Plant a Pn.md that exists but still carries the unfilled template placeholder."""
    (tmp_path / "P99.md").write_text(
        "## Comprehension Capture\n\n"
        "**JAY-VERBATIM (paste, unedited):**\n```\n"
        "<paste Jay's full explanation here exactly as he wrote it — do not summarize>\n"
        "```\n",
        encoding="utf-8",
    )
    fake_log = "## 2026-07-01 — P99 reviewed `[done]`\n"
    violations = find_ungated_closed_phases(fake_log, tmp_path)
    assert len(violations) == 1
    assert "placeholder" in violations[0]


def test_detects_planted_close_with_missing_citation(tmp_path):
    """Plant a Pn.md with a real paste but a citation left as MISSING."""
    (tmp_path / "P99.md").write_text(
        "## Comprehension Capture\n\n"
        "**JAY-VERBATIM (paste, unedited):**\n```\nJay's real words go here.\n```\n\n"
        "1. **What & why:** \"Jay's real words go here.\"\n"
        "2. **Codebase impact:** MISSING — ask again\n",
        encoding="utf-8",
    )
    fake_log = "## 2026-07-01 — P99 reviewed `[done]`\n"
    violations = find_ungated_closed_phases(fake_log, tmp_path)
    assert len(violations) == 1
    assert "MISSING" in violations[0]


def test_allows_a_properly_filled_close(tmp_path):
    """A genuinely filled decision log must NOT be flagged -- confirms the guard doesn't
    just reject everything."""
    (tmp_path / "P99.md").write_text(
        "## Comprehension Capture\n\n"
        "**JAY-VERBATIM (paste, unedited):**\n```\nJay's real explanation, all four parts.\n```\n\n"
        "1. **What & why:** \"Jay's real explanation\"\n"
        "2. **Codebase impact:** \"all four parts\"\n"
        "3. **Practices:** \"Jay's real explanation\"\n"
        "4. **Review delta + failure mode:** \"The failure mode this guards against is drift.\"\n",
        encoding="utf-8",
    )
    fake_log = "## 2026-07-01 — P99 reviewed `[done]`\n"
    violations = find_ungated_closed_phases(fake_log, tmp_path)
    assert violations == []


def test_flags_a_closing_heading_missing_any_phase_token(tmp_path):
    """A [done] heading that never names its phase can't be checked at all -- that's
    itself a violation, not a silent pass."""
    fake_log = "## 2026-07-01 — Something got reviewed `[reviewed]`\n"
    violations = find_ungated_closed_phases(fake_log, tmp_path)
    assert len(violations) == 1
    assert "no phase token" in violations[0]
