---
description: Get a top-down, vocabulary-first explanation of a concept in this codebase via the concept-explainer subagent — taught from the dollar goal down to the real code, *before* you're expected to retrieve it. Ungraded; never touches the mastery ledger. Usage: /explain <a topic like "topic 10" or "leakage", a concept, or paste the quiz question you're stuck on>
argument-hint: <topic/concept, or the quiz question you want unpacked>
---

Run the **acquisition beat** using the **`concept-explainer`** subagent (Opus; read-only over the
codebase, write-scoped only to `docs/glossary.md`). This is the *learn-first* companion to `/learn`:
where `/learn` **tests** whether a concept stuck, `/explain` **delivers** it — top-down, every term
defined, grounded in the real code. It **gates nothing**, grades nothing, and **never writes
`docs/mastery.md`**. The natural rhythm is **`/explain` to acquire, then `/learn` to verify.**

Focus to teach: **`$ARGUMENTS`** — a mastery-ledger topic (`topic 10`, `the critical ratio`), a bare
concept (`leakage`, `why Poisson`), or the exact quiz question Jay is stuck on, pasted verbatim.

### Integrity — why this never inflates the ledger

If Jay is using this on a question **mid-`/learn`**, do not let the explanation contaminate his score.
A level in `docs/mastery.md` must always mean he retrieved it *cold*. So the clean flow is:

> In `/learn`, answer **"I don't know"** to anything he can't yet reason through → the tutor records a
> **no-show** (level held, topic stays due) → *then* run `/explain` on it → it resurfaces next `/learn`
> as a genuine cold retest.

Explaining a concept never shortcuts a level; it just moves Jay from "can't retrieve" to "can retrieve
next time." Never present an `/explain` result as comprehension sign-off — it is teaching, not grading.

### How the command runs

1. **Launch the `concept-explainer` subagent** with this prompt:
   > **Teach this, top-down.** Focus: {`$ARGUMENTS`, or if blank ask Jay what he wants explained and
   > stop}. Read the real code/commit it lives in (open the file, cite `file:line`); if the focus names
   > a `docs/mastery.md` topic, read that row's Notes to aim at the real gap. Teach in order: the
   > dollar goal (Marco / prep sheet / `Co` vs `Cu`) → every term defined inline in plain language →
   > the mechanism walked in the actual code with one worked number → why-here-why-now + the dollar
   > failure mode it guards against → if a quiz question was given, the reasoning path to its answer
   > (not a memorizable one-liner). Assume no graduate vocabulary. Then append any genuinely new terms
   > to `docs/glossary.md` (read it first; don't duplicate; that is your only writable file). Do not
   > grade, do not set any level, do not touch `docs/mastery.md`.

2. **Relay the explanation to Jay in full.** It is long by design — that is the point; do not summarize
   away the scaffolding or the worked example. Present the teacher's words; add nothing of your own and,
   as with `/learn`, do not grade or certify.

3. **Point Jay at the durable term-bank.** Tell him whether `docs/glossary.md` gained terms and that it
   is the growing plain-language reference he can reread anytime. If he now wants to *test* the concept,
   that's `/learn` — ideally a later session, for a real cold check.

That's the whole command. Nothing here closes a phase, unblocks a merge, moves a mastery level, or
writes to `docs/progress_log.md`. The only artifact it can produce is a few new lines in
`docs/glossary.md`.
