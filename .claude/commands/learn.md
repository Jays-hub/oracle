---
description: Run a spaced-repetition comprehension session via the comprehension-tutor subagent — quizzes due topics from docs/mastery.md, grades your answers, updates the ledger. Usage: /learn (optionally /learn <topic or phase to focus>)
argument-hint: <optional focus, e.g. P2, "leakage", or blank for whatever's due>
---

Run a **comprehension session** using the **`comprehension-tutor`** subagent (Opus; read-only over the
codebase, write-scoped only to `docs/mastery.md`). This is the project's **parallel learning track** —
it grows and re-checks Jay's understanding on a rolling spaced-repetition schedule. It **gates nothing**:
no build, review, or phase close depends on it. Never treat a `/learn` result as a sign-off.

The tutor is one-shot and can't hold a live back-and-forth with Jay, so **this thread orchestrates the
dialogue** in three beats: get the quiz → quiz Jay → relay his answers back for grading. Do not answer
the questions yourself, do not hint, and do not grade — you are the relay, the tutor is the examiner.

Optional focus: **`$ARGUMENTS`**. If present, tell the tutor to bias topic selection toward it (a phase
like `P2`, or a concept like "leakage"). If blank, the tutor picks whatever is due (plus any unseen L0).

### Beat 1 — get the quiz (tutor Mode A)

Launch the `comprehension-tutor` subagent with this prompt:
> **Mode A — generate the quiz.** Read `docs/mastery.md`, run `date +%F`, and select the topics whose
> `Next due` ≤ today plus any at L0, capped at 4–6 (most-overdue / lowest-level first). Ground every
> question in the real code or commit it comes from (open the file, cite it) and test across the `ds` /
> `seq` / `code` domains per the ledger. Emit a clean numbered quiz I can relay verbatim: topic
> number/name, domain(s), file/commit anchor, and the question — no answers, no grading. State which
> topics you selected and why (due-date / level). Focus bias, if any: {$ARGUMENTS or "none — whatever's
> due"}. If nothing is due and no L0 remains, say so and stop.

If the tutor reports nothing is due, tell Jay that plainly (with the next upcoming due date if it gave
one) and stop — a session with nothing due is a healthy outcome, not a reason to invent questions.

### Beat 2 — quiz Jay

Relay the tutor's numbered questions to Jay **verbatim**, and ask him to answer in his own words. Then
**stop and wait for his real answer** — do not proceed, do not fill anything in on his behalf. If he
answers only some, that's fine; carry through whatever he gives.

### Beat 3 — grade and update the ledger (tutor Mode B)

When Jay answers, continue the **same** tutor agent (use `SendMessage` to that agent so its Mode-A
context is intact — do **not** spawn a fresh one) with:
> **Mode B — grade and update.** Here are Jay's answers to the questions you posed, in order: {paste
> Jay's answers verbatim, matched to the question numbers}. Grade each across the domain(s) it tested —
> concretely, teaching each gap. Set each topic's new level (up one for a clean own-words answer, down
> one for shaky/wrong, floor L1 once seen; L4 only when he also connects it to the why-here-why-now and
> the failure mode). Recompute `Next due` = today + the level's interval and set `Last reviewed` = today.
> Write the updated rows and a dated Change-log line into `docs/mastery.md`, preserving all other rows
> and prose. Return a short per-topic old→new level + next-due summary and the 1–3 things to shore up.

When the tutor returns, confirm `docs/mastery.md` was updated and relay its grading summary to Jay
**verbatim in structure** (per-topic level moves, next-due dates, what to shore up). Do not soften or
re-grade it. Point Jay at `docs/mastery.md` as the durable ledger.

That's the whole session. Nothing here closes a phase, unblocks a merge, or writes to
`docs/progress_log.md` — comprehension lives on its own track now, and the only artifact it produces is
the updated `docs/mastery.md`.
