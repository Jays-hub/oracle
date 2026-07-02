---
description: Adversarial, cold-context Opus audit of the agent toolbox itself — construction standard + per-turn token economics — via the toolbox-auditor subagent. Usage: /audit-toolbox
---

Launch the **`toolbox-auditor`** subagent (Opus; read-only over the repo, Write-scoped **only** to
`docs/agentic_workflow/toolbox_audit_<date>.md`) to run the **final** adversarial audit of this
project's agent apparatus — the `.claude/` machinery (rules, commands, subagents, hooks, memory) and its
standing per-turn token load.

Why a subagent, cold: the audit must run **cold to this chat** — it never saw how the toolbox was built
or rationalized here, so it forms its own view from the repo. Do not pre-summarize or pre-judge the
apparatus for it; let it measure and read for itself. It is scoped read-only (no `Edit`) precisely so a
"please stay read-only" prose instruction isn't the only thing protecting the tree — that structural
scoping is the standard this audit exists to check the *rest* of the toolbox against.

Before launching, run `git status --short` and `git log --oneline -5` and include the output so the
auditor knows the tree's starting state — and so a dirty tree afterward (anything but its one new
artifact) is itself visible.

Prompt to give the subagent:
> Run the **final** adversarial audit of this repo's agent toolbox per your full `toolbox-auditor`
> protocol. The claim under audit is Jay's belief that this toolbox — plus how he uses Claude going
> forward — makes him the #1 engineer in a random group of 100 CS students and working software
> engineers; decide with evidence whether it moves that goal or is a sophisticated instance of the drift
> this project warns against. Ground yourself in the repo, **measure the real per-turn token load and run
> the guard-teeth checks yourself** (don't estimate, don't trust prose), and hunt for guarantees that
> don't hold and pure ceremony. Do **not** grade on a curve. Leave the working tree exactly as you found
> it. **Before you return control, write your full deliverable — scorecard, ranked findings, the
> prose-vs-mechanism ledger, the token-savings table, the kill list, and the bottom line — to
> `docs/agentic_workflow/toolbox_audit_<date>.md`** (run `date +%F` for the date; this is the one and
> only path you may write to). Here is the tree state: {git output}.

When the subagent returns, confirm `docs/agentic_workflow/toolbox_audit_<date>.md` exists, print its
path and its `shasum` — that file, not this chat, is the authoritative report. Then **Read that file and
relay from the file itself, never from the subagent's in-chat return message**, reproducing its structure
verbatim (the scorecard, the ranked findings, the ledger, the token-savings table, the kill list, and
the bottom line) so Jay doesn't have to leave the conversation. **Do not soften or re-grade it** —
sourcing the relay from the artifact makes a relay-vs-file mismatch impossible by construction.

Then **do not auto-fix.** Present the findings and ask Jay how he wants to proceed. Acting on this audit
changes the workflow, so any resulting edit to `.claude/**` or the governance layer is a **workflow
change**: record it with a dated `docs/agentic_workflow/current_state.md` entry and update
`efficiency_backlog.md`, per that folder's maintenance convention (`README.md`). An unrecorded toolbox
change is the same drift this audit exists to catch.
