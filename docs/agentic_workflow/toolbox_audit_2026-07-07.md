# Toolbox Audit — 2026-07-07 (final adversarial pass)

Hostile, read-only audit of the `.claude/` apparatus, its token economics, and the loop as practiced,
testing one claim: *does this toolbox — plus Jay's way of using Claude going forward — make him the #1
engineer in a random group of 100 CS students and working software engineers?* Not graded on a curve.

**Method note.** Token proxy = `wc -w` × 4/3, measured on the real files this session. Auto-load was
confirmed empirically: this session's harness injected root `CLAUDE.md`, `00-process.md`
(`alwaysApply: true`), and `99-canary.md` (no frontmatter) — and **not** `01`–`07` or either peer
`CLAUDE.md` — direct proof the always-on set is exactly those three. Every guard-teeth claim below was
**run this session, against this auditor**, not cited from the record:

- `ls data/_truth/` → **denied** live by `deny_truth_access.py`.
- `cat data/_truth/demand.csv # pytest` (audit-#3's M1 bypass string) → **denied** — the structural fix is real.
- `touch <repo file>`, `git stash`, `echo probe > docs/...` as this subagent → **all denied** by
  `enforce_agent_write_scope.py`, proving the harness's `agent_type` plumbing is live, not asserted.
- **Neutered-hook test:** copied both hooks + their test files to scratch, lobotomized each
  (`_command_is_denied → False`, `_denial_reason → None`), re-ran: **24 planted-violation tests failed.**
  The guards are genuinely self-proving.
- `tests/` suite: 64/64 pass; full `make test`: **358 passed** in 11s; CI (`gh run list`): green on PRs
  #7–#11 including a real red run (P4 lockfile) that was fixed, not bypassed.
- **`Read` tool on `data/_truth/truth_demand.csv` → returned the oracle's contents, no deny.** See BLOCKER-1.

---

## 1. SCORECARD

| Axis | Grade | One-line evidence |
|------|-------|-------------------|
| **A — agent-construction standard** | **Strong, with one open door** | Every finding from the 2026-07-01 audit was closed with mechanism, not prose: write-scoping is a live hook that denied this auditor 5/5 probes; the `_truth` Bash bypass is closed live; 33+13 planted tests fail when the hooks are neutered (verified in scratch). The one hole: the oracle firewall matches only `Bash` — the `Read`/`Grep` tool path is wide open (BLOCKER-1). |
| **B — token economics** | **Adequate** | Measured: idle ≈ 2,050 tok; engine build ≈ 5,530 (representative) / 7,250 (worst, all of `01–04`); on-ramp web ≈ 5,460–6,350. No large fat. The one bad trend: `forecasting/CLAUDE.md` grew 1,258→1,681 words in 6 days by restating per-phase history that `progress_log.md` owns (~600 tok/engine-turn recoverable). |
| **C — the loop as practiced** | **Adequate** | Night-and-day vs. audit #3's "Theater": six real review artifacts (P2–P4, W0–W2), two of which **overturned the phase's headline dollar number** (P3's false-negative gate; P4's $15.6k/11.7% "win" corrected to $610.58/0.7%), remediation logged honestly, `/learn` ran twice and the ledger moved. Deductions: remediation re-enters as builder self-attestation (MAJOR-3), the last two days of the record — including the only proof `/learn` ever ran — are uncommitted (MINOR-4). |
| **D — moves #1-of-100?** | **Weak** | The toolbox now demonstrably produces shipped, honestly-reviewed systems — real, and above the median engineer's evidence trail. But the only direct measure of *Jay's own* capability is `docs/mastery.md`, and it reads: 7/14 topics unseen, 4 shaky (two graded on "I don't know"), 3 familiar, **zero at Solid or Mastered**, ledger coverage frozen at P0–P2 while the codebase moved five phases, and 1 of 6 questions attempted in the latest session. The instrument works; its readings say the claim is not on track. |

**Verdict in one line:** the scaffolding graduated from theater to a working instrument in six days —
and the instrument's own honest readings now show the bottleneck is no longer tooling, it is reps.

---

## 2. RANKED FINDINGS

### [BLOCKER] "Deny-by-default truth access" holds only for Bash — the Read/Grep tool path hands over the oracle with zero friction
- **Where:** `.claude/settings.json:3-16` (`deny_truth_access.py` registered under the `Bash` matcher
  only; the `Write|Edit|...` matcher runs only the write-scope hook; **no matcher covers
  `Read`/`Grep`/`Glob` at all**). Claim: `data/CONTRACT.md:19` ("Hidden ground truth… **Never a model
  input**"), commit `1a3cc69` ("Add **deny-by-default** truth-access hook"), hook docstring
  `deny_truth_access.py:19-24` ("catching the ad-hoc one-off command").
- **What's wrong:** This session I called the `Read` tool on `data/_truth/truth_demand.csv` and got the
  oracle's rows back instantly — no deny, no friction. The identical intent expressed as `cat` is blocked;
  expressed as `Read` (the agent's *most natural* tool) it sails through. `Grep`/`Glob` over `_truth/`
  are equally open. The hook's stated purpose is guarding the agent's own drift toward ad-hoc oracle
  peeks; half the ad-hoc surface — arguably the more likely half — is unguarded.
- **Test it fails:** *Auto-invoked* — the guard fires on one tool but not its siblings, so "deny by
  default" is false as stated. (The Bash half is genuinely self-proving; the Read half has no guard and
  no planted test.)
- **Consequence:** An agent can silently contaminate its own reasoning with ground truth (e.g. "checking"
  a model output against `_truth` mid-build), the exact epistemic leak the whole raw/truth architecture
  exists to prevent. Import-linter and boundary tests only catch leaks in committed source, not in-context peeks.
- **Minimal fix:** Register a hook for `Read|Grep|Glob` matching `_truth` in `file_path`/`path`/`pattern`
  (same sanctioning logic: allow when invoked by evaluate/simulate work — or simpler, deny always and let
  Jay run it himself), plus 2–3 planted tests. ~20 lines.

### [MAJOR] The comprehension ledger has no intake — coverage is frozen at the 2026-07-01 seed while the codebase moved five phases
- **Where:** `docs/mastery.md:65-85` (14 topics, all `Origin` ∈ P0–P2, seeded once);
  `comprehension-tutor.md:34-39` (Mode A only *selects* existing rows; Mode B only updates quizzed rows);
  `build-phase.md:75-76` (Step-0 orientation is "good raw material for `/learn` topics" — hope, no
  mechanism); no command or agent anywhere appends topics.
- **What's wrong:** P3 (censored-demand unconstraining), P4 (quantile regression, conformal/MAPIE
  calibration, PIT, newsvendor integrals — "the product in miniature"), and W0–W3 (auth, atomic seam
  writes, DuckDB wiring) shipped with **zero** ledger presence. The spaced-repetition track re-checks a
  shrinking fraction of what Jay is supposedly learning.
- **Test it fails:** *Auto-invoked, not remembered* — topic intake depends on someone remembering to
  hand-edit the ledger; nobody has, through five phases.
- **Consequence:** `CLAUDE.md` standing order #1's core promise — "understanding is grown and re-checked
  over time" — silently decays: the most sophisticated (and most examinable) work in the repo is
  invisible to the only organ that measures understanding.
- **Minimal fix:** One step appended to `/review-phase`/`/review-web`'s closing protocol: "propose 1–3
  candidate topics from this phase; on Jay's nod, the tutor appends them as L0 rows." The tutor already
  has the Write scope; this is ~4 lines of command prose plus its use.

### [MAJOR] Review findings re-enter as builder self-attestation — and the empirical record now shows why that matters
- **Where:** `review-phase.md:54-57` (greenlit fixes "hand back to a build pass… re-run the suite" — the
  same author, self-verified); `subagent_workflow_deliverables.md:66-83` (deliverable #3 names this
  exactly) frozen at `:10-14` "until the build→review loop has run **once** end-to-end";
  `efficiency_backlog.md:25` now reads "**None open**."
- **What's wrong:** The freeze's own unfreeze condition has been met several times over (P2–P4, W0–W2
  all ran the loop), yet the freeze was never revisited and the backlog reads empty. Meanwhile the base
  rate arrived: **2 of 2 engine reviews overturned the builder's headline dollar number** (P3
  BLOCKER-1: gate scored two arms against two different answer keys; P4 MAJOR-1: gate never touched the
  go-forward window). Both corrections — the +$1,499.91 and $610.58 figures now quoted in
  `forecasting/CLAUDE.md:137-159` as the phases' results — are outputs of **remediation code no reviewer
  ever saw**.
- **Test it fails:** *Self-proving* — "review closes on the code" is closed by the fix's own author writing
  the closing log entry; nothing independent confirms the fix fixed the finding rather than the symptom.
- **Consequence:** The loop's strongest results (catching mismeasured dollar gates) are certified by the
  exact process class that produced the mismeasurements. The next fold-placement-style bug lives in a
  remediation diff by construction.
- **Minimal fix:** Unfreeze deliverable **#3 only** (fresh cold reviewer scoped to the fix diff, for
  BLOCKER/MAJOR findings only), and make `efficiency_backlog.md` "Open" point at the unfreeze decision
  instead of reading "None open." Leave #1/#4/#5/#6 frozen — building those now would be the drift audit
  #3 named.

### [MINOR] Two days of the toolbox's own evidence — including the only proof `/learn` ever ran — sit uncommitted
- **Where:** `git log -1` = `d92eeb8` 2026-07-05 13:23; `git status` = 17 modified + 3 untracked files
  spanning the 07-06/07-07 `/learn` results (`docs/mastery.md`), the whole `/explain` track
  (`concept-explainer.md`, `explain.md`, `glossary.md`), the hook's new scope entry + 5 planted tests,
  and the `current_state.md`/backlog entries recording all of it.
- **What's wrong:** `current_state.md:40-44` calls the new guard "live now (33 tests pass)" — locally
  true (I measured 358 repo-wide), but CI has never seen any of it (CI runs on push), and a discarded
  worktree erases the only record that a mastery level ever moved. This is the repo's own doctrine leg 3
  ("recorded") and its #13 commit-granularity practice, violated by the toolbox about itself. Symptom of
  the skew: `forecasting/CLAUDE.md:160` says "353 tests"; the tree says 358.
- **Consequence:** The closed-out backlog #20 ("a level actually moved") is currently unfalsifiable from
  the repo of record.
- **Minimal fix:** `/ship` the pending work. Zero new machinery required.

### [MINOR] `forecasting/CLAUDE.md` is accreting per-phase history it explicitly disclaims owning — ~600 tok/turn and growing
- **Where:** `forecasting/CLAUDE.md:107-166` ("Current status": ~60 lines of per-phase modules, dollar
  figures, remediation narrative) vs. its own `:110-111` ("the running, authoritative history is always
  `docs/progress_log.md`, not this snapshot"). Measured growth: 1,258 → 1,681 words in six days (+560
  tok on **every** engine turn).
- **What's wrong:** Each phase close appends a paragraph that duplicates `progress_log.md` and the
  `Pn.md` decision logs. Extrapolated to P8, this always-on-for-engine-work file crosses 2.5k words.
- **Test it fails:** "dollars, not accuracy" applied to tokens — standing cost with no marginal guarantee
  (every fact is already in an on-demand file).
- **Minimal fix:** Cut Current status to one line per phase (name + headline dollar + pointer). Saves
  ~450–600 tok/engine-turn; loses nothing.

### [MINOR] The `/explain` track: right trigger, maximal build — the tooling reflex survived its own kill list
- **Where:** `current_state.md:8-44` — six days after an audit whose bottom line was "stop building
  tooling; run the loop," one round of real `/learn` feedback produced a new subagent (1,080 words), a
  new command (568), a 29-term pre-seeded glossary (1,073), tutor tiering, a hook entry, and 5 tests —
  in one uncommitted pass.
- **What's right (say it once):** the trigger was real use, the standing cost is ~zero (loads only on
  invocation), and the teach/grade separation is genuinely mechanized (explainer structurally cannot
  write the ledger — planted-tested).
- **What's wrong:** the minimal step that tests the diagnosis was the tutor-tiering edit *alone*
  ("questions pitched above my level" is a prompt problem); "Jay chose the full-track-plus-glossary
  option" is the sophistication-first reflex in miniature. Also `00-process.md:15-17`'s "only the
  comprehension-tutor writes `docs/mastery.md`" is mechanism against subagents but **hope against the
  main thread** (the hook passes main-thread writes untouched — `test_bash_main_thread_unrestricted`).
  Low stakes today (nothing unblocks on the ledger), worth one honest row in the ledger below.
- **Minimal fix:** None required now. Measure use: if `/explain` isn't invoked ~weekly by August, fold
  its prompt into `/learn` and delete the agent.

### [NIT] Write-scope hook friction and artifact-history scope
- Deny-leaning false positives on shell variables: `mkdir -p "$S/tests"` was denied this session because
  the unexpanded `$S` resolves inside the repo (`enforce_agent_write_scope.py:75-83`); `sed -i` is denied
  even on files *outside* the tree (`:173-174`). Right failure direction, real turn tax on scoped agents.
- Scoped agents can overwrite **past** artifacts: `P\d+[a-z]?_review\.md` lets a P5 reviewer clobber
  `P3_review.md`; my own pattern matches `toolbox_audit_2026-07-01.md`. Git tamper-evidence covers
  committed history; fine until it isn't. Fix someday: anchor patterns to the phase id passed in.

---

## 3. PROSE-MASQUERADING-AS-MECHANISM LEDGER

| Claim (where) | Real or hope? |
|---|---|
| Leakage canary + boundary tests "run in CI" (`02:12`, `01:13`) | **Real.** `ci.yml` runs `make lint/import-lint/test`; `gh run list` shows green runs on PRs #7–#11 and one honest red (P4 lockfile) that blocked until fixed. |
| Import boundary structural, not convention (`01:13`) | **Real.** `.importlinter` (2 contracts, 1 documented carve-out); `test_import_boundaries.py` self-plants a violation each run; in CI. |
| `_truth` deny-by-default at the tool boundary (`1a3cc69`, hook docstring) | **Real for Bash** (3 live denies on this auditor, incl. the old M1 bypass string); **false for Read/Grep/Glob** — I read the oracle this session (BLOCKER-1). |
| Subagent "read-only… scope is mechanism, not prose" (`phase-reviewer.md:15-17`, `comprehension-tutor.md:11-14`, `toolbox-auditor.md`, `concept-explainer.md:15-18`) | **Real.** `agent_type` plumbing proven live (5/5 probes denied on this auditor); 33 planted tests; 24 fail when the hook is neutered in scratch. |
| "Only the comprehension-tutor writes `docs/mastery.md`" (`00-process.md:15-17`) | **Mechanism vs. subagents; hope vs. the main thread** (hook deliberately passes main-thread through). Low stakes — nothing unblocks on the ledger — but the "never" is overstated. |
| Relay-vs-artifact "mismatch impossible by construction" (`review-phase.md:50-52`, `review-web`, `audit-toolbox`) | **Mostly real.** The durable artifact + printed shasum exist regardless of the relay; the "Read the file, relay from it" step is still instruction-trust, but Jay no longer depends on the relay at all. |
| Leakage canary default-on (`efficiency_backlog` #6) | **Real.** `pipeline.py:141` `check_leakage: bool = True`; default-raises planted test present. |
| "Comprehension grown and re-checked over time" (`CLAUDE.md` order #1) | **Real but decaying.** Ran twice, levels moved, honest grades ("I don't know" recorded as such). No topic intake since the seed (MAJOR-2); results uncommitted (MINOR-4). |
| "The loop ran for real" (`current_state.md` 07-02) | **Real.** Six review artifacts; two overturned headline numbers; remediation + PRs + CI all traceable in git. |
| Freeze banner "unfreeze by running the loop, not by editing this banner" (`subagent_workflow_deliverables.md:10-14`) | **Dormant prose.** Condition met repeatedly; nothing unfroze; backlog says "None open" (MAJOR-3). |
| "Suite: 353 tests, 353 pass" (`forecasting/CLAUDE.md:160`) | **Stale by 5** — measured 358 (uncommitted-work skew; exactly what `/session-start`'s drift check exists to catch, if run). |
| Canary "fired this very session" (`efficiency_backlog` #19) | **Unverifiable from artifacts;** owner's call, kept deliberately. Cheap. |

---

## 4. TOKEN SAVINGS TABLE (measured; proxy = words × 4/3)

Standing per-turn load by mode (only auto-loaded files count; confirmed empirically):

| Mode | In context | ≈ tokens |
|---|---|---|
| Idle / orientation | `CLAUDE.md` 945w + `00` 442w + `99` 107w + memory index | **≈ 2,050** |
| Engine build (representative, `02`+`03`) | + `forecasting/CLAUDE.md` 1,681w + 928w | **≈ 5,530** |
| Engine build (worst, `01–04`) | + 1,681w + 2,371w | **≈ 7,250** |
| On-ramp web turn (`05`+`07`, +`06` on front-end files) | + `onramp/plate_cost/CLAUDE.md` 1,146w + 1,412–2,080w | **≈ 5,460–6,350** |

| Waste item | Tokens/turn recovered | Guarantee lost? |
|---|---|---|
| Trim `forecasting/CLAUDE.md` Current status to one-liners + pointers | ~450–600 on every engine turn (and stops the per-phase growth trend) | **No** — every fact already lives in `progress_log.md`/`Pn.md` |
| Root `CLAUDE.md` Current-status paragraph duplicating the same phase status | ~100–150 every turn | No |
| Rule `99` canary | ~142 every turn, all modes | **Yes** — the owner's live drift probe; **considered and kept 2026-07-02 (owner's recorded call, not re-litigated here)** |
| Rules `05–07` | 0 — already narrowed to `web/api/server/routes` per audit #3; further cuts lose real coverage | — |
| `docs/agentic_workflow/` (11.8k words) | 0/turn — verified not auto-loaded (single reference in `CLAUDE.md:66` is the access rule itself) | — |

Net: economics remain honest. The only *growing* line is `forecasting/CLAUDE.md`; fix it before P5 adds
another paragraph.

---

## 5. KILL LIST (cost exceeds proven payoff at current stage)

1. **Further toolbox audits, until a mechanism materially changes.** This is the 4th hostile audit in
   8 days (06-30 ×2, 07-01, today). The remaining defects above are one-matcher, four-line-prose fixes —
   they do not need a fifth audit to find again. The audit apparatus found its BLOCKER; let it rest.
2. **`forecasting/CLAUDE.md`'s per-phase narrative** (the duplication, not the file) — the one standing
   token line that grows with every phase. Kill the restatement; keep the pointer.
3. **`subagent_workflow_deliverables.md` #1, #4, #5, #6 — keep frozen.** The loop has now run, so the
   letter of the freeze has expired — but only **#3** has earned its unfreeze with evidence (two
   overturned headline numbers whose fixes nobody re-reviewed). Building the verification ledger,
   blast-radius tiers, or findings-to-rules loops now is still process ahead of need.
4. **Nothing else.** The hooks, CI, import-linter, Makefile env-pinning, planted-test suites, the
   review loop, and the `/learn` ledger are load-bearing and proven — including against this auditor.
   Do not delete the canary (owner's recorded call) and do not delete `/explain` yet (measure use first).

---

## 6. THE BOTTOM LINE

No — the toolbox does not make Jay #1 of 100, and at this point it cannot: it has stopped being the
bottleneck. Six days ago this apparatus was a well-built theater set; today it is a working instrument —
the reviews are real and severe (they overturned both engine phases' headline dollar numbers), the
guards are live mechanism that denied this very auditor five times, and the economics are measured and
sane. That is genuinely above-average engineering infrastructure, and it should now be left almost
entirely alone. But read what the instrument itself reports: the mastery ledger — the only object in
this repo that measures *Jay* rather than the agent — shows zero topics at Solid or Mastered, "I don't
know" on the leakage canary and the Poisson objective, one of six questions attempted in the latest
session, and no coverage at all of the quantile/newsvendor turn that is supposedly the product in
miniature; he does not yet cold-recall what `q*` denotes while his repo ships conformal calibration of
it. The #1-of-100 ranking is decided by what an engineer can reconstruct, judge, and defend without the
agent — and every additional subagent widens the gap between what this repo demonstrates and what its
owner can demonstrate. The single highest-leverage move, instead of building more tooling: **commit the
pending work, then spend the next two weeks answering every due `/learn` question — 6 of 6, "I don't
know" allowed, skipping not — with `/explain` between sessions, until topics 2, 7, 10, and 13 sit at L3
and P4 has ledger rows of its own.** The toolbox's job was to make that practice cheap and honest. It
has. The rest is reps, and no hook can run them for him.
