"""Planted-violation test for the PreToolUse deny-by-default firewall hook.

.claude/hooks/deny_truth_access.py runs before every Bash tool call and must deny any
command that references data/_truth/ unless it resolves into forecasting/src/simulate/
or forecasting/src/evaluate/ (data/CONTRACT.md). This test invokes the hook script the
same way the harness does -- JSON on stdin, JSON out -- so a regression here is caught
by `make test`, not just discovered the next time someone tries the exploit for real.
See docs/agentic_workflow/efficiency_backlog.md #5.
"""
import json
import subprocess
import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[1]
_HOOK = _REPO_ROOT / ".claude" / "hooks" / "deny_truth_access.py"


def _run_hook(command: str) -> dict:
    payload = json.dumps({"tool_name": "Bash", "tool_input": {"command": command}})
    result = subprocess.run(
        [sys.executable, str(_HOOK)],
        input=payload,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, f"hook itself errored: {result.stderr}"
    return json.loads(result.stdout) if result.stdout.strip() else {}


def test_denies_planted_adhoc_truth_read():
    """The exact leak class named in the backlog: an ad-hoc python -c reading the oracle."""
    out = _run_hook("python -c \"import pandas as pd; pd.read_csv('data/_truth/truth_demand.csv')\"")
    decision = out.get("hookSpecificOutput", {})
    assert decision.get("permissionDecision") == "deny"
    assert "data/_truth" in decision.get("permissionDecisionReason", "")


def test_denies_plain_cat_of_truth_file():
    out = _run_hook("cat data/_truth/truth_params.yaml")
    assert out.get("hookSpecificOutput", {}).get("permissionDecision") == "deny"


def test_allows_sanctioned_evaluate_module():
    out = _run_hook("conda run -n restaurant-dev python -m forecasting.src.evaluate.baseline_floor")
    assert out == {}


def test_allows_sanctioned_simulate_module():
    out = _run_hook("python forecasting/src/simulate/generator.py")
    assert out == {}


def test_allows_make_test():
    out = _run_hook("make test")
    assert out == {}


def test_allows_pytest_running_the_firewall_test():
    out = _run_hook("conda run -n restaurant-dev python -m pytest forecasting/tests/test_simulator.py -k truth_firewall")
    assert out == {}


def test_allows_unrelated_commands():
    out = _run_hook("git status")
    assert out == {}
