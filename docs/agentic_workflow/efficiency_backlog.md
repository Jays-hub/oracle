# Agentic Workflow — efficiency backlog

Prioritized, actionable fixes to the workflow, ranked most→least important by **risk × leverage ×
sequencing** — a fix that unblocks or de-risks others outranks a bigger-blast-radius fix that stands
alone. This list supersedes the prior P0/P1/P2 version (audit #1, 2026-06-30); every still-open item
from it is folded in below so nothing was dropped. When you finish one, strike it here and add a
dated entry to `current_state.md`. Scope + access rule: `README.md`.

## The robustness doctrine (every fix below must satisfy all three)

This repo's recurring failure is **prose masquerading as mechanism** — "runs in CI" was false; the
comprehension gate self-certified with no artifact. So no item is "done" when a markdown file asserts
it. A fix is done only when it is:

1. **Auto-invoked, not remembered** — it fires on push / on tool-call / on the default code path,
   never depending on an agent or human *choosing* to run it.
2. **Self-proving** — it ships with a *planted-violation test*: a deliberate breach that makes the
   guard fail. A guard you have never watched fail is a guard you do not know works.
3. **Recorded** — a dated `current_state.md` entry + this strike, per `README.md`. An unrecorded
   workflow change is the same drift this project flags everywhere else.

Tiers: **[1–4] control-system foundation** (convert theater → enforcement) · **[5–9] silent-failure
closure** · **[10–13] hygiene**.

---

## [1–4] Control-system foundation

- [x] **1. Canonicalize the test environment.** *Done 2026-07-01.* *Foundation — every "run the tests" step depends on it.*
      **Forecloses:** reviewer/builder running `python -m pytest` in `base` (→ `No module named
      pytest`) and silently degrading to read-only review. pytest 9.1.1 / ruff 0.15.18 live **only**
      in `conda run -n restaurant-dev`; no workflow file names that env.
      **Robust fix:** commit a `Makefile` whose `test`/`lint` targets hard-code
      `conda run -n restaurant-dev`, so the wrong env is *structurally* unavailable. Point CI,
      `build-phase.md` Step 2, and `phase-reviewer.md`/`web-reviewer.md` Step 1 at `make test`/`make
      lint`. Replace the bare-`pytest` allowlist entry in `settings.local.json` with `Bash(make *)`.
      One line in `forecasting/CLAUDE.md` Stack.
      **Done when:** `make test` works from a fresh shell; no bare `python -m pytest` remains in any
      command/agent/settings file.

- [x] **2. Resolve the red `test_lag_7_equals_same_weekday_last_week`.** *Done 2026-07-01.* *Sequencing precondition for #3.*
      **Forecloses:** standing up CI while a test is red — which trains everyone to ignore red CI.
      Confirmed still failing (`Obtained 0.0, Expected 1.0`).
      **Robust fix:** fix it, or `@pytest.mark.xfail(strict=True, reason=…)` with a
      `construction_roadmap.md` note. `strict=True` flips CI red the moment it is *accidentally*
      fixed, so the xfail can't rot into a silent pass.
      **Done when:** the suite is green-or-strict-xfail; CI can treat red as a real signal.

- [x] **3. Stand up CI running the whole guard set in that env.** *Done 2026-07-01 (workflow file
      committed; a real PR-goes-red + branch-protection verification still needs a push — see
      current_state.md).* *Highest single leverage.*
      **Forecloses:** the signature lie — rules `01:13` and `02:12` say checks "run in CI"; there is
      no CI, so every guard fires only if a human remembers to.
      **Robust fix:** `.github/workflows/ci.yml` on push/PR — build the env from
      `requirements.lock.txt`, run `make test` + `make lint` + import-linter (#4), fail on any
      non-zero. Make it a **required status check** so a red `main` cannot merge.
      **Done when:** a PR with a planted breach or leak goes red automatically, and `main` cannot
      merge red.

- [x] **4. Make the firewall check an import-boundary check, not a substring grep.** *Done 2026-07-01.*
      *Imminent — P3 triggers it.*
      **Forecloses:** P3 landing the first `_truth` reader in `evaluate/`, then a model path reading
      the oracle via `from …evaluate import load_truth` — no `_truth` string, so all four boundary
      tests stay green while the firewall is breached. This leak class already happened once (the
      truth-tainted $159,435 floor).
      **Robust fix:** adopt `import-linter` (rule `01:13` already names it): a *forbidden* contract
      that `forecasting.src.{data,features,models,decision,report}` cannot import
      `forecasting.src.evaluate` / the truth loader. Keep the text-scan as belt-and-suspenders. Ship
      the planted-violation test. Run in CI (#3).
      **Done when:** a planted truth-import fails CI, and the check is import-graph-based, not
      string-based.

## [5–9] Silent-failure closure

- [x] **5. Deny-by-default firewall hook + narrow the auto-approve surface.** *Done 2026-07-01 (hook
      built + tested; `Bash(python *)` deliberately left broad — see current_state.md for why).*
      **Forecloses:** an auto-approved `python -c "pandas.read_csv('data/_truth/…')"` reading the
      oracle with no prompt and nothing to catch it — the boundary test never sees ad-hoc commands,
      and `settings.local.json` auto-approves arbitrary Python.
      **Robust fix:** create `.claude/settings.json` (shared/committed) with a `PreToolUse` Bash hook
      that **denies** any command touching `data/_truth/` unless it resolves into
      `forecasting/src/{simulate,evaluate}`. Narrow `Bash(python *)` to safe forms; move personal
      broad grants to an **un-tracked** `settings.local.json` (it is committed today — add to
      `.gitignore`).
      **Done when:** a Bash `_truth/` read from outside the sanctioned modules is blocked
      pre-execution, verified by trying one.

- [x] **6. Flip the leakage canary to default-on.** *Done 2026-07-01.*
      **Forecloses:** `pipeline.transform(df)` running with `check_leakage=False` (the default,
      `pipeline.py:136`) on a leaky window — the guard rule `02:12` calls mandatory is opt-in and off
      on the production path.
      **Robust fix:** default `check_leakage=True`; allow an explicit opt-*out* only for the one
      legitimate training self-transform, with a comment naming why. Add a test that the **default**
      call raises on an overlapping window.
      **Done when:** a leaky transform raises without anyone passing a flag.

- [x] **7. Reviewer verdict → durable, un-relayable artifact.** *Done 2026-07-01.*
      **Forecloses:** a BLOCKER softened to MINOR or dropped as the builder's own main thread relays
      free-text findings, unverifiably; plus the false "never saw the builder's justifications" claim
      while the decision log is fed in.
      **Robust fix:** `/review-phase` + `/review-web` instruct the subagent to **write findings to
      `docs/phase_decisions/Pn_review.md`**; Jay reads it directly, bypassing the relay. Constrain to
      the severity-tiered block so a downgrade is visible against the artifact. Reword the
      cold-context claim to the truth ("cold to the build chat; decision log deliberately provided").
      **Done when:** every review leaves a committed `Pn_review.md`; closing a phase without one is
      impossible (ties #8).

- [ ] **8. Give the gate teeth + dry-run it before real work.** *Mechanism built + CI-checked
      2026-07-01 (see current_state.md); the live dry-run itself still needs Jay's real, unedited
      comprehension explanation — cannot be done by the agent without recreating the exact
      ghost-writing failure mode this item exists to prevent.*
      **Forecloses:** (a) `build-phase.md:141` mandates a `Pn.md` decision log that P0/P1/P2 produced
      **zero** of → the gate is self-certified; (b) an agent can **ghost-write "Jay's verbatim"
      explanation**, and the inverted exit gate has **never been exercised**.
      **Robust fix:** `/review-phase` refuses the closing `[done]` entry unless
      `docs/phase_decisions/Pn.md` exists with its Comprehension Capture filled; CI checks a merged
      phase carries its `Pn.md`. The capture must be a fenced `JAY-VERBATIM (paste, unedited)` block,
      and the agent must **quote which sentence satisfies each of the four parts**, so a missing
      domain is visibly empty rather than silently completed. **Run one dry-run phase end-to-end
      before P3** — the lag-7 fix (#2) is the vehicle.
      **Done when:** no phase closes without a filled `Pn.md`, and the loop has been run once for real.

- [x] **9. Demote memory to a pointer + add a self-check.** *Done 2026-07-01.*
      **Forecloses:** `project_status.md` claiming "149 tests" when reality is 164 (163 pass / 1
      fail) — stale again, with no reconciliation mechanism.
      **Robust fix:** replace the `project_status.md` body with a 3-line pointer to
      `docs/progress_log.md` + `forecasting/CLAUDE.md` Current status (both versioned and currently
      correct). `/session-start` runs the collect count and **diffs it against any number the brief
      quotes**, flagging drift.
      **Done when:** memory holds no free-floating counts; `/session-start` warns on doc-vs-reality
      drift.

## [10–13] Hygiene

- [x] **10. De-duplicate reviewer/command prose.** *Done 2026-07-01 (partial by design — see
      current_state.md for what was extracted vs. deliberately left domain-specific).* *Flag, don't
      crash-fix.*
      **Forecloses:** `phase-reviewer` ≈ `web-reviewer` and `review-phase` ≈ `review-web` drifting
      independently (the 2026-06-30 split added ~3k words of near-verbatim duplication — a sharpening
      of one reviewer silently never reaches the other).
      **Robust fix:** extract the shared Steps 0/1/3/4/5 + comprehension-gate text into one referenced
      block; leave only the domain-specific hunt list per file.
      **Done when:** the shared scaffolding lives in exactly one place.

- [x] **11. Collapse restated governance laws to one home + pointers.** *Done 2026-07-01 (bounded — see
      current_state.md; most restatements were already pointers, a handful of genuine repeats fixed).*
      *(carried from audit #1)*
      **Forecloses:** the firewall law restated in ~9 files (dollars-not-accuracy ~6×, anti-drift
      ~6×) drifting out of sync; ~3–4k avoidable tokens on a typical turn.
      **Robust fix:** keep the firewall authority in `data/CONTRACT.md` + rule `01`; replace the full
      restatements in `CLAUDE.md`, `forecasting/CLAUDE.md`, `onramp/plate_cost/CLAUDE.md`, rules
      `05`+`07` with one-line pointers. Same for dollars (canonical rule `03`) and anti-drift (rule
      `00` + `CLAUDE.md`). Model: `forecasting/CLAUDE.md` already says the gate is "defined once… not
      re-listed."
      **Done when:** each law has one canonical statement; the rest are pointers.

- [x] **12. Re-scope the stale "aspirational web stack" item.** *Retired 2026-07-01 (#10 landed).*
      *(corrects audit #1)*
      **Forecloses:** the backlog mis-guiding work — audit #1 called rules `05/06/07` aspirational,
      but `onramp/plate_cost/web/` (Flask app, templates, `test_web.py`) exists and those rules govern
      real edits. The live waste is the duplication in #10, not the rule load.
      **Robust fix:** strike the "defer aspirational load" framing; note the web rules govern shipped
      code.
      **Done when:** the backlog reflects reality (done here — retire this item once #10 lands).

- [ ] **13. Commit at phase granularity.** *Practice adopted 2026-07-01 as the going-forward convention
      (current_state.md); items 1-12's changes are proposed as a scoped multi-commit split pending
      Jay's go-ahead — the agent does not commit without being asked.* *(carried from audit #1)*
      **Forecloses:** the git trail not corroborating the narrated gate discipline (3 commits cover
      many phases; no per-phase trail, so "the review ran" is unverifiable from git).
      **Robust fix:** one commit per gated phase (or per review pass), so the process is auditable
      from git, not just prose.
      **Done when:** each phase's build / review / close maps to distinct commits.

---

**Critical path:** 1 → 2 → 3 → 4 (CI born green and leak-tight), then 5–6 in parallel, then 7–8
(sharing the lag-7 dry-run), then 9, then 10–13. Items 1–4 convert this workflow from governance
theater into an actual control system; 5–9 close the silent-failure paths; 10–13 are cleanup.
