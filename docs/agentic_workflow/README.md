# Agentic Workflow — efficiency record (scoped, do-not-auto-load)

This folder documents the **agentic workflow itself** — the `.claude/` governance machinery
(`rules/`, `commands/`, `agents/`), the memory system, the Comprehension-Contract gate, and the
token economics of running this project with an agent. It is the workflow's own progress log +
backlog, the same pattern `docs/progress_log.md` and the memory system use for *product* work.

## Access rule (read this first)

> **An agent should open this folder ONLY when the task concerns the agentic workflow of this
> project** — i.e. editing `.claude/rules/**`, `.claude/commands/**`, `.claude/agents/**`, the
> memory system, the Comprehension-Contract gate, or the token/process efficiency of how the agent
> works. **Do not read it during ordinary product builds** (engine `Pn` phases, on-ramp `Wn` phases,
> bug fixes). Those tasks are governed by `CLAUDE.md` + `.claude/rules/` + `docs/progress_log.md` and
> never need this folder.

Why scoped: this folder exists to *reduce* per-turn token load, not add to it. It is reference, not
context — kept out of `CLAUDE.md` and out of `.claude/rules/` (which auto-load) on purpose. Loading
it on every turn would re-create the overhead it documents.

## Contents

- [`current_state.md`](current_state.md) — dated snapshot of what the workflow is and what's verified
  working vs. broken. Newest first, same convention as `docs/progress_log.md`.
- [`efficiency_backlog.md`](efficiency_backlog.md) — prioritized, actionable improvements to the
  workflow. Each item names the file to change and the expected payoff (token saving or risk
  reduction). Tick items off here when done and record the change in `current_state.md`.
- [`reviewer_report_format.md`](reviewer_report_format.md) — the one genuinely byte-identical piece
  shared by `phase-reviewer`/`web-reviewer` (finding format + comprehension-handoff wording), factored
  out so a wording fix reaches both reviewers at once (#10).
- [`subagent_workflow_deliverables.md`](subagent_workflow_deliverables.md) — deliverables + concrete
  solutions for the subagent/multi-agent-mechanics gaps logged in `current_state.md`'s 2026-06-30
  "Third pass" entry (build/review loop, cold-context handoffs). Same strike-and-record convention.

## Maintenance convention

- **When you change the workflow, update this folder in the same pass** — add a dated entry to
  `current_state.md` and move/strike the relevant `efficiency_backlog.md` item. A workflow change
  with no record here is the same drift this project flags everywhere else.
- **Product changes do not touch this folder.** A new engine phase or on-ramp view is product work;
  it belongs in `docs/progress_log.md`, not here.
- Keep entries terse. This folder polices its own bloat.
