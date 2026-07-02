#!/usr/bin/env python3
"""PreToolUse Bash hook -- deny_truth_access.

Denies any Bash command whose literal text references a data/_truth/ path unless the
referencing segment is itself sanctioned (data/CONTRACT.md): it resolves into
forecasting/src/simulate (writes the oracle) or forecasting/src/evaluate (reads it
for scoring), or it IS a pytest / make test|check|lint invocation (the existing,
already-reviewed firewall tests read _truth/ deliberately, e.g.
test_simulator.py::test_truth_firewall).

Sanctioning is structural, not substring presence: unquoted #-comments are stripped,
the command is split on unquoted shell separators (;, &, |, newlines), and a test
invocation sanctions only the segment it *leads* -- env-var assignments and the usual
runner prefixes (conda run, python -m, uv run) may precede it. A `pytest` appearing
anywhere else (a trailing comment, an echo, a chained afterthought) sanctions
nothing: `cat data/_truth/x  # pytest` is denied. The failure mode is deny-leaning;
the deny message names the sanctioned routes.

Belt-and-suspenders alongside tests/test_module_boundaries.py and .importlinter --
those catch a leak once it's in committed source; this blocks BEFORE execution, at
the Bash-tool boundary itself, catching the ad-hoc one-off command that never touches
a file at all (e.g. `python -c "pandas.read_csv('data/_truth/...')"`). It guards
against the agent's own drift, not a determined adversary (no bash-level text filter
can). See docs/agentic_workflow/efficiency_backlog.md #5; substring bypass closed per
docs/agentic_workflow/toolbox_audit_2026-07-01.md finding M1.
"""
import json
import re
import sys

import shell_lex

_TRUTH_PATTERN = re.compile(r"data[/\\]_truth\b|(?<![\w.])_truth[/\\]")

_SANCTIONED_MODULE_PATTERN = re.compile(
    r"forecasting[/.]src[/.]simulate"
    r"|forecasting[/.]src[/.]evaluate"
)

# Matches only when the test invocation LEADS the segment: optional env-var
# assignments, then optional runner prefixes, then pytest or make test|check|lint.
_SANCTIONED_INVOCATION_PATTERN = re.compile(
    r"^(?:[\w.]+=\S*\s+)*"                              # FOO=bar env assignments
    r"(?:conda\s+run\s+(?:(?:-n|--name)\s+\S+\s+)?)?"   # conda run [-n env]
    r"(?:uv\s+run\s+)?"                                 # uv run
    r"(?:python[0-9.]*\s+-m\s+)?"                       # python -m
    r"(?:pytest\b|make\s+(?:test|check|lint)\b)"
)

def _segment_is_sanctioned(segment: str) -> bool:
    return bool(
        _SANCTIONED_MODULE_PATTERN.search(segment)
        or _SANCTIONED_INVOCATION_PATTERN.match(segment.lstrip(" \t("))
    )


def _command_is_denied(command: str) -> bool:
    return any(
        _TRUTH_PATTERN.search(segment) and not _segment_is_sanctioned(segment)
        for segment in shell_lex.split_segments(command)
    )


def main() -> None:
    payload = json.load(sys.stdin)
    command = payload.get("tool_input", {}).get("command", "")

    if _command_is_denied(command):
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
