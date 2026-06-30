# Agentic Workflow — efficiency backlog

Prioritized, actionable improvements to the workflow. Ordered by payoff (risk reduction first, then
token saving). Each item names the file(s) to change and the expected effect. When you do one, strike
it here and add a dated entry to `current_state.md`. Scope + access rule: `README.md`.

Priority key: **P0** = correctness/false-guarantee (do first) · **P1** = real token/process win ·
**P2** = hygiene/nice-to-have.

---

## P0 — close the false-enforcement gap

- [ ] **Make "runs in CI" true.** Add `.github/workflows/ci.yml` (or `.pre-commit-config.yaml`)
      running `pytest -q` + `ruff check` on push/PR. Until it exists, rules `01` and `02` assert
      enforcement that isn't there.
      *Effect: turns the most-repeated structural guarantee from prose into fact; catches firewall
      and leakage regressions automatically.*
- [ ] **Fix the red test.** `forecasting/tests/test_features.py::`
      `test_lag_7_equals_same_weekday_last_week` is failing. Decide whether the lag-7 selection in
      `forecasting/src/features/pipeline.py` is wrong or the test's day-index arithmetic is (its
      comment is self-inconsistent). Do not record P2 progress over a red leakage-class test.
      *Effect: removes a live failure in the exact defect class the workflow exists to prevent.*

## P1 — reclaim avoidable tokens & tighten process

- [ ] **Collapse the four restated laws to one home + pointers.** Keep the firewall authority in
      `data/CONTRACT.md` + `.claude/rules/01`; replace the full restatements in `CLAUDE.md`,
      `forecasting/CLAUDE.md`, `onramp/plate_cost/CLAUDE.md`, rules `05`+`07` with one-line pointers.
      Same for dollars-not-accuracy (canonical: rule `03`) and anti-drift (canonical: rule `00` +
      `CLAUDE.md`). Cut the verbatim four-gate re-list in `.claude/commands/build-phase.md` to a
      pointer (the file already says "obey, don't restate").
      *Effect: ~3–4k fewer tokens on a typical build turn, zero constraint lost. Model: the one place
      already disciplined — `forecasting/CLAUDE.md` says the gate is "defined once… not re-listed."*
- [ ] **Demote stale memory to a pointer.** Replace the body of memory `project_status.md` with ~3
      lines pointing at `docs/progress_log.md` as the authoritative, versioned source. Keep
      `user_profile.md` (it earns its keep). *Effect: removes ~1.4k tok/session of recalled content
      that is already wrong (claims 149 tests) and kills the stale-memory failure mode.*
- [ ] **Produce the gate artifact the contract mandates.** For each built phase write
      `docs/phase_decisions/Pn.md` from `_template.md` with Gate 4 verbatim. Backfill P0/P1/P2 or
      decide the progress-log quote suffices and amend `build-phase.md` to stop requiring a separate
      artifact. *Effect: makes the gate auditable instead of self-certified.*

## P2 — hygiene

- [ ] **Defer aspirational rule load.** Rules `05/06/07` (web stack) and `04`'s registry/drift
      machinery target code that doesn't exist. Consider gating them behind a "web phase active" flag
      or trimming to a stub + pointer until the matching code lands. *Effect: stops paying ~2.4k tok
      on on-ramp `.py` edits for a web stack that isn't built.*
- [ ] **Add a memory-vs-reality check to `/session-start`.** Have it diff the memory's claimed test
      count against an actual `pytest` collect/run and flag drift. *Effect: self-correcting memory.*
- [ ] **Commit at phase granularity.** One commit per gated phase (or per audit pass) so the git
      trail corroborates the narrated gate discipline. *Effect: the process becomes auditable from
      git, not just prose.*
- [ ] **Record reviewer output.** Save each `/review-phase` result (or a pointer) so it's verifiable
      the adversarial review actually ran. *Effect: closes the "self-review dressed as review" risk.*
