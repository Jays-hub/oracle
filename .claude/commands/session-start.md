---
description: Orient to the current session — reads progress log, memory, and git state, then returns a 10-line brief.
---

Read the following sources directly (do not ask Jay to paste anything):

1. `docs/progress_log.md` — the three most recent dated entries (newest first)
2. `/Users/owner/.claude/projects/-Users-owner-Documents-restaurant-dev/memory/MEMORY.md` — the full memory index (and any memory file it points to that looks relevant)
3. Run `git branch --show-current` and `git status --short`
4. Read `~/.claude/settings.json` for the current model and effort level
5. **Drift self-check** (`efficiency_backlog.md` #9 — memory holds no free-floating counts, so this is
   what actually catches staleness): run `make test` for the real, current pass/fail count. Extract
   every test-count claim ("NNN tests", "NNN pass", "N fail") mentioned in the progress_log.md entries
   you read, `forecasting/CLAUDE.md` "Current status", and any memory file surfaced in step 2. If the
   real count disagrees with a quoted one, that's drift — note it. If everything agrees (or nothing
   quotes a count), there's nothing to flag.

Then return **exactly** this brief — no preamble, no trailing commentary. It is 10 lines in the normal
case; append an 11th `Drift:` line **only** when step 5 found a real mismatch (omit it entirely
otherwise — don't pad a clean run with "Drift: none"):

```
Branch:      <current branch name>
Open phase:  <phase actively in progress, e.g. "P2", or "none">
Last log:    <date + one-line summary of the newest progress_log.md entry>
Last decide: <date + one-line of the most recent [decided] entry, if different from above; else "same as above">
Next step:   <the single most concrete pending action named in the log or memory>
Uncommitted: <count of modified + untracked files from git status, e.g. "4 files", or "clean">
Memory:      <any memory item directly relevant to the current branch or phase; else "none">
Model:       <model value from settings.json>
Effort:      <effortLevel value from settings.json>
Ready:       Yes — /build-phase <Pn> to proceed, or ask a question.
Drift:       <only if step 5 found one — e.g. "forecasting/CLAUDE.md says 164 pass; make test shows 181">
```

No narrative. No offers to help further. Just the brief.
