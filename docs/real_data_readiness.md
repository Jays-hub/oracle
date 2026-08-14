# Real-Data Readiness — what stands between this codebase and a real restaurant's export

**Status:** the governing build document as of 2026-08-13. Supersedes the phase ordering implied by
`forecasting/docs/construction_roadmap.md` (P5+) and `onramp/plate_cost/docs/purpose_and_phases.md`
(Phase 2+) — not the phases already built, which stand.

**The goal this document serves, stated once:** get this codebase to the point where it ingests a
**real POS export and a real stack of vendor invoices** from a real restaurant, and produces output
honest enough to be fed back to that operator. Everything below is measured against that, not against
test count or model sophistication.

Source of the method: `consulting_framework.md` (Parts 3–5 especially) and `learning_path.md`.
This file is where that method meets *this* code.

---

## 1. The layer stack, mapped onto this repo

The framework's central sequencing claim (`consulting_framework.md` §3.1) is that capability sits in
a dependency stack, and attempting a layer before its prerequisites exist produces **confident, wrong
output — which is worse than no output, because it gets trusted.** Mapped onto what is actually built
here:

| Layer | What it means | State in this repo |
|---|---|---|
| **L0 — Access** | POS export/API, invoice capture, payroll, counts | **Simulated only.** `forecasting/src/simulate/generator.py` writes a synthetic export; the web app accepts a CSV *the operator has already reshaped by hand*. No real export has ever entered this codebase. |
| **L0.5 — Recipe capture** | Documented recipes with quantities and yields | **Built, and genuinely reusable.** The recipe sitdown → `bom.parquet` is the one leg that survives contact with reality unchanged. |
| **L1 — Identity** | Canonicalization, entity resolution, unit algebra, yield factors, versioned item master | **Effectively absent.** Identity is `name.strip().casefold()` (`onramp/plate_cost/src/report/grid.py:5`). `onramp/plate_cost/src/ingestion/` — the module whose own docstring calls ER "the engineering wall" — contains **no code**. |
| **L2 — Derived measures** | Plate cost, contribution margin, theoretical vs. actual usage | **Built on top of an absent L1.** Plate cost, the margin grid, and price trends all compute correctly — *given* that names already match. That assumption holds for a chef's hand-typed sheet and dies on the first vendor invoice. |
| **L3 — Decision models** | Quantile forecasting, newsvendor, optimization | **Built and dollar-gated (P0–P4), on simulated data.** This is the most advanced layer in the repo and it sits on the least real foundation. |
| **L4 — Interface & habit** | Prep lists, flash P&L, alerts | **Built as a web surface (W0–W9)**, serving L2 output. No prep-list surface yet — L3's output has never reached a screen. |
| **L5 — Institutionalization** | SOPs, process mining, lineage | Not started. Correctly deferred. |

**The shape of the problem in one line:** this repo is strongest at L3 and weakest at L1, which is the
exact inversion of the dependency order. That is not a criticism of the work — P0–P4 are real and
dollar-gated — it is a statement of what the next phase has to be.

---

## 2. The five blockers, with evidence

Each is a specific, checkable claim about the code as it stands at commit `d465603`.

### B1 — There is no source-adapter layer. Ingestion requires a CSV the operator hand-shaped.

The capture funnel demands exact columns:

- Sales: `{dish_name, count, period_start, period_end}` — `onramp/plate_cost/src/capture/seam_upload.py:57`
- Invoices: `{ingredient_name, unit_price, source_invoice, observed_date}` — `onramp/plate_cost/src/capture/invoice_upload.py:46`

No Toast, Square, SpotOn, or Clover export has those columns, and no vendor invoice has them in any
form. Today the *operator* is the adapter — they are expected to reshape their own export by hand
before uploading. That is a new weekly ritual, which fails the project's own "no added work" gate
(`strategic_context.md`) and disqualifies the funnel under the framework's short-term-play criterion
#1 ("no operational change required to capture the value," §7.1).

### B2 — The sales leg is at the wrong grain to feed a forecast, and always was.

`SalesExportRow` (`schemas/seam.py:40`) is `dish_name, count, period_start, period_end` — **one
aggregate count over a date range.** "Braised Short Rib: 412, 2026-01-01 → 2026-03-31."

That is exactly right for the popularity axis of a menu-engineering grid, which is what plate-cost
needs. It is **structurally incapable of feeding a demand model**, which needs demand per item per
day. The engine's own loader builds a daily series (`forecasting/src/data/loader.py:88`
`build_observed_demand`).

So the on-ramp — chartered as "captures the data the engine needs" (`onramp/README.md`) — captures a
sales leg the engine could never use, at any level of wiring. The BOM leg is genuinely shared; the
sales leg is not. This is the single most consequential finding in this document, because the whole
"one act feeds two products" argument rests on it.

### B3 — Identity is a casefold. The ER module is an empty package.

`normalize_name()` is the entire identity strategy across both peers:

```python
def normalize_name(name: str) -> str:
    return name.strip().casefold()
```

Every `dish_id` and `ingredient_id` in the seam is a casefolded display name. This is the weakest
possible slice of the framework's Phase 1 (§4.2) — no abbreviation expansion, no noise-token
stripping, **no pack-notation parsing**, and nothing at all from Phases 2–6: no blocking, no
probabilistic matching, no clustering, no adjudication queue, no temporal validity.

`onramp/plate_cost/src/ingestion/__init__.py` has a docstring describing all of it and zero lines of
implementation, gated behind a "POS-absorption check" that has never been run.

Against a real invoice this fails immediately and silently: `TOMATO ROMA 25# CS`, `Tomatoes, Roma,
25 lb`, `Roma tomato`, and `4 oz diced` casefold to four distinct ids, so four price histories
accumulate for one tomato and every plate cost touching it is wrong — **confidently, with a clean
render.** That is the failure mode §3.3 names as the one that ends engagements.

### B4 — Unit algebra stops short of the part that matters for invoices.

`onramp/plate_cost/src/bom/units.py` is a correct, well-built weight/volume conversion table with
cross-family conversion properly refused. What it does not have is what invoices are actually written
in: **pack notation** (`25#`, `6/#10`, `4x5kg`, `CS`, `EA`), and count↔weight bridging via piece
weight or density. §4.2 is explicit that in restaurants this deterministic step buys more than
sophisticated matching does — and it is the step that is missing.

### B5 — The seam is contractually one-way but functionally disconnected.

`data/CONTRACT.md` specifies `onramp/` → `data/raw/` → `forecasting/`. In fact:

- The on-ramp writes `sales_export.parquet`, `bom.parquet`, `price_observations.parquet`, `food_cost.parquet`
- The engine reads `pos_sales.csv` (`forecasting/src/data/loader.py:82`) — the **simulator's** file

`grep -rn "sales_export\|price_observations\|food_cost" forecasting/` returns nothing. The two
writers into the shared store produce different shapes and the reader only understands the
simulator's. Even setting B2 aside, captured real data has no consumer today.

---

## 3. What the framework says to buy rather than build — and what that means here

`consulting_framework.md` §7.8.1 is a direct challenge to a large part of what is already built:
MarginEdge sells invoice extraction, recipe costing, and a daily controllable P&L at **~$350/month
per location to 11,000+ operators**, with the Fellegi–Sunter three-region review architecture already
shipped. Its conclusion: *"building the ER substrate from scratch for a 1–10 unit client is almost
always the wrong call."*

Read honestly, that lands on `onramp/plate_cost/`, which is a hand-built substrate slice (L0.5 → L1 →
L2) with nine phases of web app on top.

**But the conclusion does not transfer unchanged, because the goal is different.** §7.8.1 answers
*"what should I deploy at a client?"* This repo's goal is *"how do I get real data flowing into a
system I control, so I get real-world feedback?"* Those diverge in one specific way:

| | Buy (MarginEdge et al.) | Build here |
|---|---|---|
| Client gets working costing in weeks | ✅ | ❌ slower |
| **You get raw, item-level, item-master-versioned data you can model on** | ❌ their schema, their grain, export-limited | ✅ |
| Adjudication decisions are yours to learn from | ❌ | ✅ |
| Cost to the operator | $350/mo/location | your time |

The framework's own §7.8.2 concedes the split: what stays yours is **grain decisions, unit algebra
and yield modeling specific to the concept, adjudication quality, item-level quantile forecasts, and
cross-unit pooling.** Four of those five require you to hold the resolved data, not to query a
vendor's view of it.

**The resolution this document proposes, and the one real fork:**

- **R0–R1 below are unconditionally yours.** Nobody sells "get this operator's real export into my
  repo at daily grain." No buy decision removes this work.
- **R2–R5 (canonicalization → matching → clustering → adjudication) are the genuine buy-vs-build
  fork,** and it should be decided *after* R0, when a real export and a real invoice stack are on
  disk and the actual variance is measurable. Deciding it now, from either direction, is guessing.
- **R6 (temporal validity) is a requirement either way** — build it, or make it a vendor
  disqualifier. §4.7: retrofitting it is close to a rebuild, and every analysis produced before it
  is suspect.

---

## 4. The build order (R-phases)

A new phase series, sitting **before** the engine's P5 (exogenous fusion) and the on-ramp's W10+.
Ordering is not preference — each constraint below is forced by `consulting_framework.md` Part 5.

| Phase | Builds | Forced by |
|---|---|---|
| **R0** | **Grain + source audit.** Obtain one real POS export and one real invoice stack. Inventory every source system, its identifier scheme, and export rights. Measure actual variance. Run a spend Pareto. Determine required entity grains **from the operator's real decisions**. Gate: do documented recipes exist? | "Grain before build" — building before you know which decisions the entities serve guarantees schema-level rework (§4.1, Part 5) |
| **R1** | **Source adapters + daily grain.** A per-vendor adapter layer mapping a real export to the seam. Replace/extend `SalesExportRow` with a daily per-item row (fixes **B2**). Wire the engine's loader to read the on-ramp's legs (fixes **B5**). | Nothing downstream can be tested against reality until a real file loads. Fixes the two blockers no vendor purchase removes. |
| **R2** | **Canonicalization + unit algebra.** Pack-notation parser (`25#`, `6/#10`, `4x5kg`), abbreviation expansion, noise-token stripping, count↔weight bridging, yield factors (fixes **B4**). Deterministic and auditable only — no model. | "Deterministic before probabilistic": never spend model capacity on variance a rule eliminates (§4.2, Part 5) |
| **R3** | **Blocking + a hand-labeled recall audit.** Multi-pass keys, unioned. **Measure recall before proceeding.** | "Recall ceiling before precision tuning": blocking recall is a hard ceiling on system recall, and the failures are invisible downstream (§4.3) |
| **R4** | **Probabilistic matching**, emitting a calibrated probability, not a score. | "Calibration before thresholding": thresholds must derive from asymmetric loss (§4.4, Part 5) |
| **R5** | **Constrained clustering + adjudication queue.** Correlation clustering with must-link/cannot-link; three-region thresholds **biased toward splits**; queue ordered by expected information gain × dollars at stake. | "Clustering after pairing, never pairing alone": identity is transitive, similarity is not — skipping the projection invites chaining collapse (§4.5) |
| **R6** | **Temporal validity on the item master.** Validity intervals + provenance on every entity and link. | "Temporal model before history is trusted" (§4.7) |

**The measurement rule for every phase:** progress is **dollars of COGS resolved, not records
resolved** (§Part 5). Record counts reward long-tail work that doesn't matter and hide gaps in the
top-20 items that carry ~70% of spend.

**The value rule:** every phase ships something visible. A nine-month cleaning project with no output
loses the operator in month four (§Part 5, Part 6 "patience exhaustion").

---

## 5. What this changes about work already planned

- **Engine P5 (exogenous fusion) moves behind R0–R1.** Fusing weather and events into a model trained
  on simulated data adds sophistication to a system that has never seen a real row. This is the
  Anti-Drift Standing Order applied to the engine itself, not just the on-ramp.
- **The plate-cost "Phase 2 GATE" is resolved, and the answer is not the one it anticipated.** The
  gate asked "is Toast/Square about to bundle this for free?" §7.8.3 answers with 2026 market fact:
  Toast IQ shipped to all US Toast customers in late 2025; MarginEdge and four named peers already
  own the back-office layer; **ClearCOGS** (founded 2021, $3.8M seed 2025) is doing item-level prep
  forecasting directly. The gate should be closed as **answered**, not left standing.
- **The remaining unclaimed ground is narrower and should be stated as such:** item-level quantile
  forecasts at newsvendor-derived service levels, for sub-10-unit independents (§7.8.2, "the open
  technical claim"). That is what P0–P4 already built. It survives the pivot; it just cannot be
  validated on simulated data.
- **The discovery findings and the framework converge, independently.** Wes's cold-start problem
  (`docs/discovery/2026-08-12_wes.md` §8) — pain and history inversely distributed — is precisely what
  §2.1 says hierarchical partial pooling solves: a new location inherits the group prior on day one.
  And Wes's par sheet is the framework's naive baseline (§7.3: "always against a naive baseline of
  same-weekday-last-week — that baseline *is* their current implicit forecast"). Two independent
  sources reached the same place. That is the strongest signal in this document.

---

## 6. Open decisions (not made here)

1. **Buy vs. build for R2–R5.** Recommended: decide after R0, on measured variance. Not before.
2. **What happens to the W0–W9 web app.** It currently serves L2 views over an absent L1. It is not
   wasted — it is the L4 habit surface and the capture funnel — but its plate-cost-specific views are
   provisional (as `onramp/README.md` already says) and the prep-list surface L3 needs does not exist.
3. **Whether `onramp/`'s charter language survives.** "The on-ramp service, the means; the engine, the
   end" describes a product funnel. The stack framing describes a dependency chain. They are
   compatible but not identical, and the charter should say one thing.
4. **Whose real data comes first.** The discovery thread (`docs/discovery/`) has a warm, willing
   contact in the right seat. R0 is gated on an actual export, and §7 of the Wes decode already names
   the ask: POS name, history depth, who pulls the export, whether run-outs are recorded.
