#!/usr/bin/env python3
"""PreToolUse Bash hook -- deny_truth_access.

Denies any Bash command whose literal text references a data/_truth/ path unless the
same command also resolves into one of the two sanctioned modules (data/CONTRACT.md):
forecasting/src/simulate (writes the oracle) or forecasting/src/evaluate (reads it for
scoring), or is a pytest/make run (the existing, already-reviewed firewall tests read
_truth/ deliberately, e.g. test_simulator.py::test_truth_firewall).

Belt-and-suspenders alongside tests/test_module_boundaries.py and .importlinter --
those catch a leak once it's in committed source; this blocks BEFORE execution, at
the Bash-tool boundary itself, catching the ad-hoc one-off command that never touches
a file at all (e.g. `python -c "pandas.read_csv('data/_truth/...')"`).
See docs/agentic_workflow/efficiency_backlog.md #5.
"""
import json
import re
import sys

_TRUTH_PATTERN = re.compile(r"data[/\\]_truth\b|(?<![\w.])_truth[/\\]")
_SANCTIONED_PATTERN = re.compile(
    r"forecasting[/.]src[/.]simulate"
    r"|forecasting[/.]src[/.]evaluate"
    r"|\bpytest\b"
    r"|\bmake\s+(test|check|lint)\b"
)


def main() -> None:
    payload = json.load(sys.stdin)
    command = payload.get("tool_input", {}).get("command", "")

    if _TRUTH_PATTERN.search(command) and not _SANCTIONED_PATTERN.search(command):
        print(json.dumps({
            "hookSpecificOutput": {
                "hookEventName": "PreToolUse",
                "permissionDecision": "deny",
                "permissionDecisionReason": (
                    "Blocked by .claude/hooks/deny_truth_access.py: this command "
                    "references data/_truth/ (the hidden oracle) without resolving into "
                    "forecasting/src/simulate/ or forecasting/src/evaluate/ -- the only "
                    "two sanctioned modules (data/CONTRACT.md). Read data/_truth/ only "
                    "through those modules (or make test/pytest, which run the reviewed "
                    "firewall tests), or ask Jay to run this command himself."
                ),
            }
        }))
    sys.exit(0)


if __name__ == "__main__":
    main()
