# Toolbox Audit — 2026-07-01 (final adversarial pass)

Hostile, read-only audit of this repo's `.claude/` apparatus and its token economics, testing one
claim: *does this toolbox — plus Jay's way of using Claude going forward — make him the #1 engineer in
a random group of 100 CS students and working software engineers?* Not graded on a curve.

**Method note.** Token proxies are `word_count × 4/3`, word counts measured with `wc -w` on the real
files this session. Auto-load behaviour was confirmed empirically: this session's own harness injected
root `CLAUDE.md`, `00-process.md` (`alwaysApply: true`) and `99-canary.md` (no frontmatter) into
context, but **not** `01`–`07` or `forecasting/CLAUDE.md` — direct proof that `alwaysApply`/no-frontmatter
load every turn and `paths:` frontmatter loads on-demand. The `deny_truth_access.py` hook was proven live
(it blocked one of my own grep commands mid-audit). Guard-teeth checks I did **not** personally re-run
this session (import-linter and boundary-test planted violations) are cited from `current_state.md`'s
record + the presence of CI, and flagged as "recorded, not re-verified this session" — I did not want to
mutate the tree to re-prove them under time pressure. Nothing below is asserted where a file:line settles
it.

---

## 1. SCORECARD

| Axis | Grade | One-line evidence |
|------|-------|-------------------|
| **A — agent-construction standard** | **Adequate** | Real teeth exist (CI `guard-set`, `.importlinter`, the `_truth` Bash hook proven live), path-scoping works, reviewer/tutor are cleanly separated — but "read-only" and "write-scoped to `docs/phase_decisions/**`" are **prose**, not enforced by any tool restriction (`phase-reviewer.md:4` grants `Bash` + `Write` unrestricted). |
| **B — token economics** | **Adequate** | Measured standing load is moderate and honest: idle ≈ 1,960 tok, engine build ≈ 4,900–6,500 tok, on-ramp ≈ 5,300 tok. Audit #1's "~9.6k / ~40% avoidable" is now **stale-better** after the `#10/#11` dedup + gate removal. Residual waste is minor (canary ~143 tok/turn; web rules load ahead of any web code). |
| **C — the loop as practiced** | **Theater** | The build→review loop and the `/learn` track have **never produced a single artifact**: `docs/phase_decisions/` holds only `_template.md`, and `docs/mastery.md` is 14/14 topics at L0 with a one-line change log. P0–P2 were built and *backfilled* outside the loop. The apparatus is documented, not practiced. |
| **D — moves #1-of-100?** | **Weak** | The toolbox prevents classic DS own-goals (leakage, wrong metric, firewall breach) — real but table-stakes. The two things that actually make someone #1 (shipped systems + demonstrated understanding) are exactly the two the apparatus leaves inert: understanding mechanism has never run; shipped surface is a P2 engine + a Phase-0 tool. |

**Verdict in one line:** genuinely well-*constructed* scaffolding whose *use* has drifted into the
"comfortable place to hide" this repo names in its own Anti-Drift order. Marginal return on **more**
tooling is **negative**.

---

## 2. RANKED FINDINGS

### [BLOCKER] The two flagship tracks have never run — the apparatus is documented, not practiced
- **Where:** `docs/phase_decisions/` (only `_template.md`; git history confirms no `Pn.md`/`Pn_review.md`
  ever committed — `git log --all --name-only -- 'docs/phase_decisions/*.md'` returns only `_template.md`).
  `docs/mastery.md:70-92` (all 14 topics `L0 / Unseen`, every `Last reviewed = —`, every `Next due = due`,
  change log has exactly one entry: "File created"). `docs/progress_log.md` P1/P2 entry is tagged
  `[built] [backfilled]` — "were built but never logged."
- **What's wrong:** The build→review→decision-log→review-artifact loop and the parallel `/learn`
  comprehension track are the toolbox's entire reason for existing, and **neither has executed once on a
  real phase.** P0–P2 were built without the loop and logged after the fact. `mastery.md` is a seeded
  table nobody has quizzed against — a "ledger stuck at all-L0," which the audit brief and
  `current_state.md:71` both name in advance as "the same prose-masquerading-as-mechanism in a new
  costume."
- **Test it fails:** *Self-proving* and *auto-invoked* — a mechanism you've never watched run is a
  mechanism you don't know works. Both fail outright: zero runs, zero artifacts.
- **Consequence:** The claim under audit rests on "understanding grown and re-checked over time." The only
  organ that does that has produced nothing. Understanding is currently **asserted, not demonstrated** —
  which is precisely the gap between "polish as progress" and shipped, understood work.
- **Minimal fix:** Run `/learn` once against the seeded topics and `/review-phase` once against a real
  phase (P3, or a re-review of P2). One real pass converts theater into mechanism. Until then, treat the
  ledger and the decision-log system as untested code, not as evidence of understanding.

### [MAJOR] The `_truth` hook has a documented bypass: any command containing "pytest" or "make test" is allowed through
- **Where:** `.claude/hooks/deny_truth_access.py:21-26` — `_SANCTIONED_PATTERN` matches `\bpytest\b` and
  `\bmake\s+(test|check|lint)\b` **anywhere in the command string**. The deny only fires if the truth
  pattern matches **and** the sanctioned pattern does **not**.
- **What's wrong:** The hook's own docstring (`:11-13`) says its job is to block the ad-hoc one-off
  `python -c "pandas.read_csv('data/_truth/...')"`. But
  `python -c "pandas.read_csv('data/_truth/oracle.parquet')" # pytest` contains the substring `pytest`,
  so `_SANCTIONED_PATTERN` matches and the read is **allowed**. A trailing comment or `&& echo pytest`
  defeats it.
- **Test it fails:** *Self-proving.* `tests/test_truth_access_hook.py` reportedly covers 7 accept/reject
  cases (per `current_state.md:203`); the bypass case (a genuine `_truth` read with `pytest` appended)
  is almost certainly not among them, or the hole would have surfaced. I did not re-run it this session
  (marked not re-verified), but the regex is unambiguous on the page.
- **Consequence:** The Bash-boundary layer — the one layer specifically justified as catching the
  never-committed ad-hoc leak — is trivially bypassable. Mitigated (not closed) by `.importlinter` +
  boundary tests, which only catch leaks in *committed source*.
- **Minimal fix:** Anchor the sanctioned pattern to command **structure**, not substring presence — e.g.
  only treat `pytest`/`make test` as sanctioned when the command *starts* with them (or is exactly a test
  invocation), not when the token appears anywhere. Add the bypass string as an 8th planted case.

### [MAJOR] "Read-only over the codebase" / "write-scoped to `docs/phase_decisions/**`" is prose, not mechanism
- **Where:** `phase-reviewer.md:4` (`tools: Read, Grep, Glob, Bash, Write`), `:11-15`;
  `web-reviewer.md` (same); `comprehension-tutor.md:4,11-12` (`Write`, "the one and only file you may
  write"). `settings.json` contains **only** the Bash PreToolUse hook — no `permissions` block, no
  path-scoped Write deny.
- **What's wrong:** Both reviewer subagents and the tutor are handed unrestricted `Bash` **and**
  unrestricted `Write`. Nothing but the prose in their own instructions stops them from editing source,
  tests, rules, or any doc (via `Write` to any path, or `echo > file` / `sed -i` under `Bash`). The `Bash`
  hook only guards `_truth` strings; every other path is writable.
- **Test it fails:** *Auto-invoked, not remembered.* The guarantee depends entirely on the subagent
  choosing to obey — the definition of "remembered." No planted-violation test exists for "reviewer tried
  to write outside its lane."
- **Consequence:** The "read-only reviewer" and "tutor writes only mastery.md" guarantees are
  instruction-following hopes. For a compliant model this usually holds; the point is it is **not a
  mechanism**, and the repo's own doctrine (`efficiency_backlog.md:9-20`) says that makes it prose.
- **Minimal fix:** Add a `permissions` deny in `settings.json` (or a PreToolUse Write/Edit hook) scoping
  each subagent's writes to its one allowed path. This is the same pattern the `_truth` hook already
  proves works.

### [MAJOR] Reviewer independence is partly theatrical, and its one mitigation has never fired
- **Where:** `review-phase.md:11-15` (reviewer is "cold to the build chat" but "deliberately handed the
  builder's decision log"), `:45-51` ("relay its contents verbatim… a mismatch between the relay and the
  artifact is itself visible and checkable"). The durable artifact is `docs/phase_decisions/Pn_review.md`
  — of which **zero exist**.
- **What's wrong:** The cold-context reviewer's opinion still reaches Jay through the same main thread that
  ran the build, and is primed by the builder's own decision log. The stated safeguard — diff the in-chat
  relay against the reviewer's own file — (a) has never had a file to diff against, and (b) requires Jay to
  open the file, which the "relay verbatim so he doesn't have to leave the conversation" design exists to
  make unnecessary. So the safeguard is self-cancelling in normal use.
- **Test it fails:** *Self-proving* (never produced an artifact) and *auto-invoked* (the diff is a manual
  step the workflow discourages).
- **Consequence:** A builder-thread relay can silently downgrade a BLOCKER to a MAJOR, or drop a "what I
  could not verify" line, and nothing structural catches it. This is `subagent_workflow_deliverables.md`
  #2's exact concern — filed, half-built, never exercised.
- **Minimal fix:** Have `/review-phase` end by printing the `Pn_review.md` path and a one-line `diff`/hash
  of relay-vs-file, so the check is auto-run, not remembered. Cheap; closes the loop the doc claims.

### [MINOR] Self-record contradicts itself: subagent deliverable #2 is built but the doc says "none are built"
- **Where:** `subagent_workflow_deliverables.md:6` ("None of these are built yet") vs.
  `phase-reviewer.md:4,137-142` (Write granted, `Pn_review.md` write instruction present) and commit
  `62daf42` "Reviewer writes durable artifact."
- **What's wrong:** Deliverable #2 (durable un-relayed review artifact) was implemented during the
  gate-removal work, but its own tracking doc still says none of the six are built. Self-record drift — the
  precise thing `README.md:41-43` says must never happen.
- **Consequence:** A future reader trusts a stale "nothing built here" and either rebuilds #2 or mis-scopes
  the remaining work. Minor, but it's governance-theater in the governance-of-the-governance.
- **Minimal fix:** Strike #2 in `subagent_workflow_deliverables.md` and note it landed in `62daf42`.

### [MINOR] Rule 99 canary bills ~143 tok every turn forever for a personal drift probe
- **Where:** `.claude/rules/99-canary.md` (107 words, no frontmatter → always-on; confirmed injected into
  this session's context).
- **What's wrong:** A standing instruction-following probe that fires only when Jay ends a message with
  `kdog1` costs ~143 tok on **every** turn of **every** session, indefinitely, whether or not he ever
  types the token.
- **Consequence:** Non-zero standing cost for near-zero realized value at current stage. Not a correctness
  risk; pure economics.
- **Minimal fix:** Keep it — it's cheap and its owner wants it — or move it behind a manual load. This is a
  judgment call, not a defect; flagged for the ledger.

### [MINOR] Web rules 05–07 (~2.7k tok) load ahead of any web code; rule 06 currently guards nothing
- **Where:** `05-fullstack-architecture.md` (paths `onramp/**/*.py|ts|tsx|…`), `07-backend-api.md`
  (`onramp/**/*.py`), `06-frontend-ux.md` (`onramp/**/*.tsx|jsx|css|html|svelte|vue`). Measured 756/668/608
  words ≈ 1,008/891/811 tok.
- **What's wrong:** `05`+`07` fire on `onramp/plate_cost`'s **pure-compute** Python — which is not the web
  stack they govern (there is no website/API code yet). `06`'s front-end extensions match **zero files in
  the repo**, so its ~891 tok can only ever load once a `Wn` phase exists. Aspirational load paid now,
  exactly as audit #1 flagged (`current_state.md:466`).
- **Consequence:** ~1.8k tok on plate-cost Python turns for rules that mostly describe a stack not yet
  built. No guarantee lost by deferring `06` until front-end files exist.
- **Minimal fix:** Narrow `05`/`07` to actual service/API subpaths (e.g. `onramp/**/api/**`,
  `onramp/**/server/**`), leaving pure-compute plate-cost out; leave `06` as-is (it self-gates to zero
  until web files appear).

### [NIT] Audit #1's "~9.6k governance tokens / ~40% avoidable" is now stale
- **Where:** `current_state.md:463-465`.
- **What's wrong:** Measured current worst-case engine-build load is ≈ 6,500 tok (all of `00,99` + root +
  `forecasting/CLAUDE.md` + `01-04`), representative ≈ 4,900 tok — materially below 9.6k after the
  `#10/#11` dedup and gate removal. The figure is quoted elsewhere as if current.
- **Consequence:** The self-record over-states current waste; a reader may chase savings already banked.
- **Minimal fix:** Annotate the 9.6k figure as "audit #1 baseline; superseded — see 2026-07-01 audit."

---

## 3. PROSE-MASQUERADING-AS-MECHANISM LEDGER

| Claim (where) | Real or hope? |
|---|---|
| Leakage canary + boundary test "runs in CI" (`01`, `02`) | **Real.** `.github/workflows/ci.yml` runs `make lint/import-lint/test` on push+PR; branch protection + planted-failure PR verified (`current_state.md:80-110`). Was false at audit #1; now fixed. |
| Import boundary enforced structurally (`01`) | **Real (recorded, not re-verified this session).** `.importlinter` present; `test_import_boundaries.py` plants a real violation per `current_state.md:196-198`. Runs in CI. |
| `_truth` Bash hook blocks ad-hoc oracle reads (`settings.json` + hook) | **Real but holed.** Proven live (it blocked my own grep). But `pytest`/`make test` substring bypass (Finding M1) means the guarantee is partial. |
| `deny_truth_access` "belt-and-suspenders… catches the ad-hoc one-off" (`hook:10-13`) | **Hope for the bypass case.** See M1 — a `# pytest` suffix defeats it. |
| Reviewer "read-only over the codebase" (`phase-reviewer.md:11`) | **Hope.** `Bash`+`Write` unrestricted; no permission mechanism (M2). |
| Reviewer/tutor "Write scoped only to `docs/phase_decisions/**` / `mastery.md`" (`phase-reviewer.md:12`, `comprehension-tutor.md:11`) | **Hope.** Instruction-only; no path deny (M2). |
| "A mismatch between relay and artifact is visible and checkable" (`review-phase.md:50`) | **Hope.** No artifact ever produced; check is a manual step the design discourages (M4). |
| Comprehension "grown and re-checked over time" (`CLAUDE.md` order #1, `00-process.md`) | **Hope, so far.** `/learn` never run; `mastery.md` inert at all-L0 (BLOCKER). Honestly disclosed in `current_state.md:71`, but still unexercised. |
| Build→review loop produces decision log + durable review (`build-phase.md:143`, `review-phase.md:36`) | **Hope, so far.** Zero `Pn.md`/`Pn_review.md` ever produced (BLOCKER). |
| Leakage canary default-on, "auto-invoked not remembered" (`efficiency_backlog` #6) | **Real (recorded).** `check_leakage` flipped to `True`; `test_transform_default_raises…` added (`current_state.md:210-217`). Not re-run this session. |
| Path-scoped rule loading (`01`–`07` load only on their paths) | **Real.** Empirically confirmed by this session's own context injection. |

---

## 4. TOKEN SAVINGS TABLE (measured; proxy = words × 4/3)

Standing per-turn load, by mode (only auto-loaded files count):

| Mode | Files in context | ≈ tokens |
|---|---|---|
| Idle / orientation | root `CLAUDE.md` (924w) + `00` (442w) + `99` (107w) [+ memory index 24w] | **≈ 1,960–1,990** |
| Engine build (representative: features+models) | idle + `forecasting/CLAUDE.md` (1258w) + `02` (388w) + `03` (540w) | **≈ 4,880** |
| Engine build (worst case: all of `01-04`) | idle + `forecasting/CLAUDE.md` + `01-04` (2158w) | **≈ 6,520** |
| On-ramp Python turn | idle + `onramp/plate_cost/CLAUDE.md` (1146w) + `05` (756w) + `07` (608w) | **≈ 5,310** |

Recoverable waste, ranked by tokens/turn:

| Waste item | Tokens/turn recovered | Guarantee lost? |
|---|---|---|
| Defer rule `06` until front-end files exist (currently matches 0 files) | ~891 on future onramp front-end turns (0 today) | **No** — self-gates to zero now |
| Narrow `05`/`07` off pure-compute plate-cost `.py` | ~1,800 on onramp-python turns | **No** real guarantee for non-web compute; keep for actual API/server paths |
| Drop / on-demand rule `99` canary | ~143 every turn, all modes | **Yes-ish** — loses the `kdog1` drift probe (owner's call) |
| Update stale 9.6k figure (doc only) | 0 (no per-turn effect) | No |

Net: the economics are **already fine.** The largest real recoverable line (05/07 scoping) is ~1.8k and
debatable. There is no ~9.6k fat left to trim — the dedup passes did their job.

---

## 5. KILL LIST (cost exceeds proven payoff at current stage)

1. **The meta-apparatus about the meta-apparatus, frozen not extended.** `subagent_workflow_deliverables.md`
   items #1, #3, #4, #5, #6 (verification ledger, independent BLOCKER re-review, blast-radius escalation,
   findings-to-rules loop, effort-scaled orientation) are **enterprise process for a loop that has run
   zero times.** Building any of them now is a textbook Anti-Drift violation (sophistication ahead of the
   simpler higher-value step). Freeze the backlog until the loop has run **once** end-to-end.
2. **`docs/mastery.md` as it stands is decoration** unless `/learn` runs. Either run it this week or stop
   citing "understanding grown over time" as a live property — an all-L0 ledger is a promise, not a record.
3. **Rule 99 canary** — candidate for deletion or manual-load (see M-canary). ~143 tok/turn forever for a
   probe that has, as far as the record shows, never fired.
4. **The audit apparatus itself** (`audit-toolbox.md` 522w + `toolbox-auditor.md` 1539w — this very
   machinery). Zero standing per-turn cost (loads only when invoked), so not a token finding — but ~2,000
   words of self-audit tooling on a solo P2/Phase-0 project is ceremony. Keep one lightweight audit; do not
   grow the audit-of-the-audit further.

Nothing in `.claude/rules/01-04`, the CI, the import-linter, the Makefile env-pinning, or the hook (once
M1 is fixed) belongs on the kill list — those are the genuinely load-bearing, self-proving parts.

---

## 6. THE BOTTOM LINE

No — this toolbox, as built and as *used*, does not make Jay #1 of 100, and continued investment in it has
**negative** marginal return toward that goal. The construction is real and above-average (measured,
path-scoped, CI-backed, one hook with genuine teeth), and the token economics are honestly under control —
audit #1's 9.6k fat is gone. But the two things that actually decide "#1 engineer" — **shipped, reviewed
systems** and **demonstrated depth of understanding** — are exactly the two the apparatus has produced
**zero evidence of**: the build→review loop has never emitted a decision log or a review artifact, and the
`/learn` comprehension ledger sits at 14/14 unseen with a one-line history. P0–P2 were built and
*backfilled*, i.e. the flagship loop was documented around work it never actually governed. That is this
project's own named failure mode — ceremony substituting for shipped, understood work; a comfortable,
gratifying place to hide — reproduced one level up, in the tooling meant to prevent it. The single
highest-leverage move is **not another mechanism**: it is to run the loop and `/learn` you already have,
once, on a real phase — ship P3 through `/build-phase` → `/review-phase` and produce the first real
`Pn_review.md`, then quiz the P0–P2 topics through `/learn` and watch a level actually move. One honest
end-to-end pass will teach more, and prove more about the #1 claim, than any further scaffolding. Until a
human has been graded by this tutor and a phase has survived this reviewer, the toolbox is a well-engineered
answer to a question Jay hasn't yet asked it.
