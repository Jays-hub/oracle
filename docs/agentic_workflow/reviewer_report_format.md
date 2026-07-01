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

Both reviewers review **build progress only.** Comprehension is a separate, parallel track (`/learn` +
`docs/mastery.md`) that no reviewer touches and no finding gates — so there is no comprehension handoff
in the sign-off. (This section formerly defined one; it was removed when the comprehension exit gate was
retired, 2026-07-01.)

## Rules opening line (part of Step 5)

**Rules:** No praise padding, no flattering summary; one line is enough if something is genuinely good.
