---
description: Orient to the current session — reads progress log, memory, and git state, then returns a 10-line brief.
---

Read the following sources directly (do not ask Jay to paste anything):

1. `docs/progress_log.md` — the three most recent dated entries (newest first)
2. `/Users/owner/.claude/projects/-Users-owner-Documents-restaurant-dev/memory/MEMORY.md` — the full memory index
3. Run `git branch --show-current` and `git status --short`
4. Read `~/.claude/settings.json` for the current model and effort level

Then return **exactly** this brief — 10 lines, no preamble, no trailing commentary:

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
```

No narrative. No offers to help further. Just the brief.
