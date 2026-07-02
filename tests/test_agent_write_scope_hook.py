"""Planted-violation tests for the per-subagent write-scope PreToolUse hook.

.claude/hooks/enforce_agent_write_scope.py turns the "read-only over the codebase /
Write granted only for one artifact" prose in the subagent definitions into a
mechanism (toolbox_audit_2026-07-01.md finding M2). These tests invoke the hook the
same way the harness does -- JSON on stdin (with the `agent_type` field the harness
adds for subagent tool calls), JSON out -- planting the exact violations the audit
warned nothing structural would catch: a reviewer editing source, a tutor writing
outside its ledger, Bash-level mutation escapes (`sed -i`, redirects, mutating git).
"""
import json
import subprocess
import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[1]
_HOOK = _REPO_ROOT / ".claude" / "hooks" / "enforce_agent_write_scope.py"


def _run_hook(payload_overrides: dict) -> dict:
    payload = {"cwd": str(_REPO_ROOT), "hook_event_name": "PreToolUse"}
    payload.update(payload_overrides)
    result = subprocess.run(
        [sys.executable, str(_HOOK)],
        input=json.dumps(payload),
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, f"hook itself errored: {result.stderr}"
    return json.loads(result.stdout) if result.stdout.strip() else {}


def _decision(out: dict) -> str:
    return out.get("hookSpecificOutput", {}).get("permissionDecision", "")


def _write(agent, path, tool="Write"):
    return _run_hook({
        "agent_type": agent,
        "tool_name": tool,
        "tool_input": {"file_path": path},
    })


def _bash(agent, command):
    return _run_hook({
        "agent_type": agent,
        "tool_name": "Bash",
        "tool_input": {"command": command},
    })


# --- File tools: each agent writes ONLY its own artifact ---------------------------


def test_reviewer_denied_writing_source():
    out = _write("phase-reviewer", "forecasting/src/models/point_model.py")
    assert _decision(out) == "deny"


def test_reviewer_denied_editing_tests():
    out = _write("phase-reviewer", "tests/test_seam_schemas.py", tool="Edit")
    assert _decision(out) == "deny"


def test_reviewer_denied_writing_rules():
    out = _write("phase-reviewer", ".claude/rules/00-process.md")
    assert _decision(out) == "deny"


def test_reviewer_allowed_its_review_artifact():
    out = _write("phase-reviewer", "docs/phase_decisions/P2_review.md")
    assert out == {}


def test_reviewer_denied_web_review_artifact():
    """Lanes don't cross: the engine reviewer may not write the web reviewer's file."""
    out = _write("phase-reviewer", "docs/phase_decisions/W1_review.md")
    assert _decision(out) == "deny"


def test_web_reviewer_allowed_its_review_artifact():
    out = _write("web-reviewer", "docs/phase_decisions/W1_review.md")
    assert out == {}


def test_tutor_allowed_mastery_ledger():
    out = _write("comprehension-tutor", "docs/mastery.md")
    assert out == {}


def test_tutor_denied_progress_log():
    out = _write("comprehension-tutor", "docs/progress_log.md")
    assert _decision(out) == "deny"


def test_auditor_allowed_dated_audit_artifact():
    out = _write("toolbox-auditor", "docs/agentic_workflow/toolbox_audit_2026-07-01.md")
    assert out == {}


def test_auditor_denied_current_state():
    out = _write("toolbox-auditor", "docs/agentic_workflow/current_state.md")
    assert _decision(out) == "deny"


def test_scratchpad_and_tmp_writes_stay_allowed():
    """The guarantee protects the repo tree; scratch space outside it is fine."""
    out = _write("phase-reviewer", "/tmp/scratch/review_notes.md")
    assert out == {}


def test_traversal_out_of_allowed_dir_is_still_denied():
    out = _write("phase-reviewer", "docs/phase_decisions/../../Makefile")
    assert _decision(out) == "deny"


def test_main_thread_unrestricted():
    out = _run_hook({"tool_name": "Write", "tool_input": {"file_path": "forecasting/src/models/point_model.py"}})
    assert out == {}


def test_unscoped_agents_unrestricted():
    out = _write("general-purpose", "forecasting/src/models/point_model.py")
    assert out == {}


# --- Bash: the mutation escape hatches the audit named -----------------------------


def test_bash_denies_sed_in_place_on_source():
    out = _bash("phase-reviewer", "sed -i 's/old/new/' forecasting/src/models/point_model.py")
    assert _decision(out) == "deny"


def test_bash_denies_redirect_into_repo():
    out = _bash("phase-reviewer", "echo 'fixed' > forecasting/src/models/point_model.py")
    assert _decision(out) == "deny"


def test_bash_allows_redirect_to_tmp():
    out = _bash("phase-reviewer", "pytest -q > /tmp/pytest_out.txt")
    assert out == {}


def test_bash_allows_fd_dup_and_pipes():
    """The reviewer's bread and butter must not be collateral damage."""
    out = _bash("phase-reviewer", "conda run -n restaurant-dev python -m pytest -q 2>&1 | tail -20")
    assert out == {}


def test_bash_denies_rm_in_repo():
    out = _bash("comprehension-tutor", "rm -rf docs/phase_decisions")
    assert _decision(out) == "deny"


def test_bash_denies_xargs_fed_mutator():
    out = _bash("phase-reviewer", "git ls-files | xargs rm")
    assert _decision(out) == "deny"


def test_bash_denies_mutating_git():
    out = _bash("phase-reviewer", "git checkout -- forecasting/")
    assert _decision(out) == "deny"


def test_bash_denies_git_stash():
    out = _bash("toolbox-auditor", "git stash")
    assert _decision(out) == "deny"


def test_bash_allows_readonly_git():
    out = _bash("phase-reviewer", "git log --oneline -10 && git diff main...HEAD --stat")
    assert out == {}


def test_bash_allows_scratch_copy_out_of_repo():
    """The auditor's sanctioned guard-teeth flow: copy OUT, mutate the copy outside."""
    out = _bash("toolbox-auditor", "mkdir -p /tmp/scratch && cp forecasting/src/models/point_model.py /tmp/scratch/")
    assert out == {}


def test_bash_denies_copy_into_repo():
    out = _bash("toolbox-auditor", "cp /tmp/scratch/point_model.py forecasting/src/models/point_model.py")
    assert _decision(out) == "deny"


def test_bash_allows_reviewer_writing_its_artifact_via_redirect():
    out = _bash("phase-reviewer", "cat /tmp/draft.md > docs/phase_decisions/P3_review.md")
    assert out == {}


def test_bash_allows_plain_reads():
    out = _bash("web-reviewer", "grep -rn 'plate_cost' onramp/ && wc -l onramp/plate_cost/src/*.py")
    assert out == {}


def test_bash_main_thread_unrestricted():
    out = _run_hook({"tool_name": "Bash", "tool_input": {"command": "rm -rf forecasting/src/models"}})
    assert out == {}
