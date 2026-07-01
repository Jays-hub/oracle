# Reviewer report format — shared by `phase-reviewer` and `web-reviewer`

The one piece of the two adversarial reviewers that is genuinely byte-identical (verified,
efficiency_backlog.md #10) rather than domain-flavored paraphrase. Lives here once; both
`.claude/agents/phase-reviewer.md` and `.claude/agents/web-reviewer.md` point to it instead of
restating it, so a wording fix here reaches both reviewers at once.

Everything else in the two agent files — the hunt list, the severity-tier *definitions*, the
persona, the governance files to ground in — is deliberately domain-specific prose, not
duplication, and stays in each agent file. (Steps 0/1/3/4's surrounding text was checked
line-by-line and found to differ meaningfully per domain — forcing it into one shared block
would either genericize away the specificity that makes each reviewer good at its job, or need a
templating system this repo's plain-markdown agent format doesn't have. Recorded as a deliberate
scope decision, not an oversight.)

## Finding format (Step 4)

```
[SEVERITY] Short title
Location:       file / function / line
What's wrong:   the actual behavior
Why it matters: the consequence + the concept behind it (Jay is a beginner)
Fix:            concrete and minimal (you describe it; the builder applies it)
Confidence:     High / Medium / Low   (Low = inferred without running; High = you ran it)
```

## COMPREHENSION HANDOFF (part of Step 5's sign-off)

- **COMPREHENSION HANDOFF:** the 3-4 things about this phase Jay most needs to be able to explain for the
  review's comprehension exit gate to clear (`.claude/rules/00-process.md`) — the non-obvious *why*s, the
  failure mode the design guards against, and the chef-sentence-worthy ideas. You do not elicit or certify
  this (you're a cold-context subagent and cannot talk to Jay); you surface what the main thread should
  test him on. **Your verdict does not close the phase** — the phase is done only when Jay can explain the
  finished work in his own words back in the main thread.

## Rules opening line (part of Step 5)

**Rules:** No praise padding, no flattering summary; one line is enough if something is genuinely good.
