# Restaurant Technology Consulting: Buying Triggers, Enabling Techniques, and the Entity Resolution Roadmap

**Target segment:** independent operators running 1–10 locations
**Scope:** what owners actually buy, which computer science concepts serve each motive, what must be true before any of it works, and how to build the data substrate underneath it all

---

## Part 1 — The Four Buying Triggers

An owner never buys "machine learning." They buy relief from one of four conditions. The trigger determines the pitch, the deliverable, the pricing basis, and the sequence of work.

| Trigger | What the owner actually says | What they are buying | Pricing basis | Time to felt value |
|---|---|---|---|---|
| **Margin recovery** | "I'm busy every night and still not making money" | Points of prime cost | % of recovered margin, or fee vs. quantified annual savings | 3–12 months |
| **Time savings** | "I'm doing invoices at midnight on Sunday" | Hours returned | Hours eliminated × their effective hourly value | 2–8 weeks |
| **Stress reduction** | "I never know what's coming until it's already happened" | Predictability; absence of surprise | Subscription/retainer — it's an ongoing state, not an event | 1–6 months |
| **Exit valuation** | "I want to sell in three years" | A business that runs without them | % of valuation delta, or project fee against multiple expansion | 18–36 months |

**Why the distinction matters more than it looks:**

- **Time savings is a throughput problem. Stress reduction is a variance problem.** They feel similar to the owner and require completely different engineering. Automation solves the first. Uncertainty quantification and alert discipline solve the second. Confusing them produces systems that save time while *increasing* anxiety — the classic dashboard that generates 40 alerts a week and gets muted.
- **Margin recovery is an optimization problem. Exit valuation is a knowledge-externalization problem.** Margin work makes the business earn more. Exit work makes the earnings transferable to someone who isn't the owner. A business can be highly optimized and still un-sellable because the optimization lives in the owner's head.
- **Prerequisite depth varies enormously by trigger** (see Part 3). This is what should drive engagement sequencing, not client enthusiasm.

---

## Part 2 — Techniques by Trigger

Ranked within each trigger by contribution to the outcome.

### 2.1 Margin Recovery

Prime cost (COGS + labor) is 60–65% of revenue against a 3–9% net margin. One point of prime cost is worth 15–30% of net profit. Everything here targets that line.

**1. Hierarchical / partial pooling with forecast reconciliation** *(highest leverage)*

Item × location × daypart slicing turns two years of history into hundreds of sparse, noisy series. Partial pooling models each series' parameters as draws from a shared distribution, so estimates shrink toward the group by an amount the data determines — heavy shrinkage for thin series, almost none for high-volume ones.

- Degrades gracefully from 1 unit (pool across items, dayparts, weekdays) to 10 units (pool across locations too)
- Solves **cold start** outright: a new location inherits the group prior on day one, which independent models cannot do at all
- Reconciliation (MinT and relatives) across total → location → category → item doesn't merely enforce arithmetic coherence — it *reduces error at every level* by pushing the better signal-to-noise of aggregate levels down into sparse leaves

**2. Quantile / newsvendor loss instead of mean forecasts**

MSE- or MAPE-optimized models return the conditional mean. The mean is not the decision. Prep and order quantities carry asymmetric costs.

For a $19 entrée at $5 food cost:
- Overage cost C₀ ≈ $5 (unsold prepped portion)
- Underage cost Cᵤ ≈ $14 (forgone contribution, before guest dissatisfaction)
- Optimal service level q\* = Cᵤ / (Cᵤ + C₀) = 14/19 ≈ **0.74**

Prep to the 74th percentile, not the mean — on right-skewed daily demand that is often 25–40% higher. The implication is the whole argument: an operator running an "accurate" mean forecast is **systematically under-prepping high-margin items and over-prepping low-margin ones every single day.** That's a persistent bias, not noise, which is why it compounds into real money.

q\* is item-specific: a three-day-shelf-life dessert has low C₀ and a high optimal quantile; fresh fish is a total loss and sits lower. Train on pinball loss at the target quantile directly rather than fitting a mean and applying a fudge factor.

**3. Constrained optimization (mixed-integer programming)**

Forecasts don't save money — order quantities, prep lists, and schedules do. The optimization layer converting distribution to decision (subject to pack sizes, minimum orders, shift lengths, skill coverage, overtime thresholds) is usually the missing half of a deployment.

**4. Causal inference — synthetic control, difference-in-differences, switchback designs**

Price and promo decisions require causal estimates; correlational ML will confidently mislead. With 5–10 units you can use untreated locations as donors and construct genuine counterfactuals. Switchback designs work at daypart granularity for a single unit.

**5. Contextual bandits (Thompson sampling)**

Traffic is the scarce resource, so sample efficiency is the binding constraint on menu and price testing. Bandits deliver answers in weeks where fixed-horizon A/B tests need quarters.

**6. Anomaly and change point detection**

Surfaces theoretical-vs-actual variance, comp/void patterns, and portioning drift.

> **Non-CS quick win worth sequencing first:** payment processing / interchange rate audit. Near-zero implementation cost, no behavior change, frequently $500–3,000/month per location. Weak on leverage, exceptional on trust-building.

### 2.2 Time Savings

The binding constraint at this scale is owner attention, not capital. Techniques that *remove* work beat techniques that add a habit.

**1. Entity resolution / record linkage** *(the substrate — see Part 4)*
Linking POS items → recipes → ingredients → purchase units → invoice lines. This is where the manual hours physically are.

**2. LLM structured extraction with constrained decoding**
Vendor invoices arriving as PDFs, scans, and faxes → typed line items with confidence scores. Unattended above a confidence threshold, queued below it.

**3. Unit algebra and yield modeling**
Case → pound → ounce → portion, with trim and cook loss. Inseparable from ER in this domain.

**4. Agentic tool-use loops**
Draft purchase orders, draft schedules, draft review responses. Owner approves rather than authors — a 10× reduction in cognitive cost even when time saved is modest.

**5. Idempotent, event-driven integration**
Unglamorous. Replay and reconciliation semantics are the difference between an integration that runs for two years and one that silently drifts in month four.

**6. ASR + intent parsing** — phone-order capture for takeout-heavy concepts.

### 2.3 Stress Reduction

Stress comes from *surprise*, not from bad numbers. Every technique here targets variance and calibration rather than throughput.

**1. Multiple-hypothesis correction on alerting** *(the most neglected item on this entire document)*

Monitoring 200 menu items daily generates dozens of spurious "anomalies" per week by chance alone. Benjamini–Hochberg FDR control or sequential testing converts an alert stream from noise into signal. **Precision matters far more than recall when the recipient is one exhausted person.** This single omission is why most restaurant ops dashboards get ignored within six weeks.

**2. Change point detection (CUSUM, Bayesian online changepoint)**

Owners care about *regime shifts* — a vendor quietly walking prices up, a new cook running heavy portions — not single-day excursions. Threshold alarms fire on noise; changepoint methods fire on structure.

**3. Conformal prediction / calibrated intervals**

Distribution-free coverage guarantees, which is exactly right when thin data prevents validating a parametric model. A range that holds 90% of the time reduces anxiety more than a point estimate that is occasionally spectacularly wrong.

**4. Exception-based reporting**

Framed information-theoretically: surface only what diverges from expectation, rank by surprisal, suppress the rest. Replaces the dashboard rather than adding to it.

**5. Shrinkage-stabilized recommendations**

A useful side effect of partial pooling: the model doesn't chase noise, so one strange Tuesday doesn't swing tomorrow's prep list. **Erratic recommendations destroy trust faster than mediocre ones.**

### 2.4 Exit Valuation

The valuation problem is that the business runs on undocumented knowledge in the owner's head, so a buyer discounts the earnings for key-person risk.

**1. Process mining (conformance checking, variant analysis)** *(best fit, least obvious)*

Discover the *actual* operating process from POS, KDS, and labor event logs rather than from what anyone says they do. A mature field almost never pointed at restaurants. Converts undocumented practice into documented, transferable SOPs — directly attacking the key-person discount.

**2. Data lineage, provenance, and reproducible reporting**

Quality-of-earnings diligence punishes numbers that can't be traced. Immutable event logs plus deterministic re-derivation of any historical report is a direct valuation input, not merely hygiene.

**3. Retrieval-grounded knowledge systems over SOPs**

So a new GM can answer what the owner would have answered.

**4. Discrete event simulation / digital twin**

Proves unit economics transfer to a new site. De-risks expansion for a buyer and makes the growth story credible rather than aspirational.

---

## Part 3 — Prerequisites: What Must Be True First, and Why

Capability sits in a dependency stack. Attempting a trigger before its prerequisites exist produces confident, wrong output — which is worse than no output, because it gets trusted.

### 3.1 The layer stack

| Layer | Contents | Why nothing above it works without it |
|---|---|---|
| **L0 — Access** | POS export/API, invoice capture, payroll, inventory counts, labor event logs | You cannot analyze data you cannot extract. Frequently the true blocker; some POS contracts restrict export. |
| **L0.5 — Recipe capture** | Documented recipes with quantities and yields | **The real step zero for many clients, and it is manual.** No recipes means no plate cost, no theoretical usage, no item margin. Scope this before quoting anything. |
| **L1 — Identity** | Canonicalization, entity resolution, unit algebra, yield factors → versioned item master | Every downstream number is denominated in an entity and a unit. Wrong identity or wrong conversion produces confidently wrong results. |
| **L2 — Derived measures** | Plate cost, contribution margin, theoretical usage, actual usage, variance | These are *computed*, not observed. They exist only once L1 exists. |
| **L3 — Decision models** | Hierarchical/quantile forecasting, MIP optimization, causal estimation | Requires L2 for the cost asymmetries (C₀, Cᵤ) that define the objective function. |
| **L4 — Interface & habit** | Prep lists, weekly flash P&L, FDR-controlled alerts | Value is only realized through a decision someone actually makes. Unused output is worth zero. |
| **L5 — Institutionalization** | SOPs, process mining, temporal integrity, lineage | Converts a working system into a transferable asset. |

### 3.2 Prerequisite depth by trigger

| Trigger | Requires | Depth | Consequence for sequencing |
|---|---|---|---|
| **Time savings** | L0 → L1 | **Shallowest** | Fastest path to visible value. Lead here. |
| **Stress reduction** | L0 → L1 → L3 → L4 | Medium | Needs calibration and alert discipline; needs earned trust. |
| **Margin recovery** | L0 → L0.5 → L1 → L2 → L3 → L4 | **Deepest** | Highest value, longest runway. Bridge with quick wins that bypass the stack. |
| **Exit valuation** | All of the above + L5 | Deepest + longest | Multi-year. Only credible with a client already through the earlier layers. |

### 3.3 The three implications that should govern engagement design

**1. Entity resolution pays for itself on *time savings* long before it pays off on *margin*.**
Margin recovery is what the owner most wants and what takes longest to deliver. ER is a prerequisite for margin but produces immediate, felt time savings the moment invoice processing is automated. This is the single most important sequencing fact in the document: **ER is funded by the trigger with the shallowest prerequisites and harvested by the trigger with the deepest.**

**2. Quick wins must bridge the gap to the deep stack.**
Payment processing audits and POS-only menu price analysis require almost none of the stack and produce cash in weeks. Use them to fund and de-risk the L1 build. Without a bridge, you are asking for months of patience from someone at 5% net margin.

**3. Never deliver a number whose lineage you haven't validated.**
The failure mode that ends engagements is not a mediocre model — it's a confident figure the owner acts on that turns out to rest on a bad unit conversion or a false merge. Credibility is not recoverable at this scale, because the client population is small and talks to each other.

---

## Part 4 — Entity Resolution: Implementation Roadmap for Restaurants

> **Read this alongside §7.8.1.** As of 2026 the ER substrate is largely purchasable (MarginEdge and peers), so for a 1–10 unit client this section is usually **an evaluation and configuration standard, not a build plan.** The phases below become the criteria by which you judge and correct a vendor's implementation. Build from scratch only when no vendor supports the grain the client's decisions require.

### 4.0 What the problem actually is

Information systems don't contain things; they contain descriptions of things. There is no guaranteed mapping between records and referents. **Identity is not observable — only similarity is.** Entity resolution is the inference from the second to the first.

The chain that must be traversed for any real costing question:

> POS sale → menu item → modifiers → recipe → ingredient → purchase unit → invoice line → price

Every arrow is an identity-matching problem *composed with* a unit conversion and a yield factor. The same tomato appears as `TOMATO ROMA 25# CS`, `Tomatoes, Roma, 25 lb`, `Roma tomato`, and `4 oz diced` across four systems, none of which share a key.

### 4.1 Phase 0 — Assessment and scoping *(1–2 weeks)*

**Do:**
- Inventory every source system and its identifier scheme; confirm export rights
- Pull a record sample from each; measure the actual variance (it's usually worse than the client believes)
- Run a **spend Pareto** — typically 20% of items carry 70% of COGS
- Determine required **entity grains from the client's actual decisions** (see 4.7)
- **Gate check:** do documented recipes exist? If not, recipe capture is the real first project and must be scoped and priced separately

**Why first:** grain and scope are determined by the client's decisions, not by the data. Building before you know which decisions the entities serve guarantees rework.

### 4.2 Phase 1 — Canonicalization *(2–3 weeks)*

**Do:**
- Deterministic normalization: case, punctuation, abbreviation expansion, noise-token stripping
- **Pack notation parsing** — `25#`, `25 lb`, `6/#10`, `4x5kg` into structured (count, size, unit)
- Unit-of-measure conversion tables, including count↔weight via item density/piece weight
- Yield factors for trim and cook loss

**Why here:** much apparent dissimilarity is *representational*, not semantic. Every unit of variance removed by a deterministic rule is variance the probabilistic layer never has to absorb statistically, expensively, and imperfectly. It is also fully auditable, which matters for early trust.

**Domain note:** in restaurants, unit and pack normalization buys more than sophisticated embeddings do. Do the boring part first.

### 4.3 Phase 2 — Blocking / candidate generation *(1–2 weeks)*

**Do:**
- Multi-pass blocking keys (normalized head noun; pack-size band; vendor + category; character n-gram LSH), unioned
- **Measure blocking recall against a hand-labeled sample before proceeding**

**Why here:** n records give n(n−1)/2 pairs — 100k invoice lines is 5 billion comparisons. But the match relation is extremely sparse, so you spend compute only where a match is plausible. Blocking is a cheap *necessary* condition.

**Why the measurement is non-negotiable:** blocking recall is a **hard ceiling on total system recall**. A pair never compared can never be matched, no matter how good the model is. These failures are invisible in downstream metrics unless you deliberately audit for them, and no amount of matcher tuning recovers them.

### 4.4 Phase 3 — Probabilistic matching *(2–4 weeks)*

**Do:**
- Frequency-weighted attribute agreement — per-field likelihood ratios m/u accumulated as log-odds (Fellegi–Sunter)
- Embedding similarity over descriptions for semantic variation
- A learned combiner over both, emitting a **calibrated probability**, not a raw score

**Why frequency weighting:** evidential weight is inverse to frequency. Agreement on "case" says nothing; agreement on "piquillo pepper, 2.2kg tin" is nearly decisive. The *u* term is the probability of coincidental agreement, governed by value rarity. This is surprisal (−log p), the same principle underneath TF-IDF.

**Why calibration specifically:** thresholds must be derivable from an asymmetric loss function (4.6), which is only possible if the score is a real probability.

### 4.5 Phase 4 — Constrained clustering *(2–3 weeks)*

**Do:**
- Correlation-clustering approximation, or hierarchical agglomerative with a principled stopping rule
- Must-link constraints (identical vendor + SKU + pack) and cannot-link constraints (allergen conflict, incompatible UOM class)
- Re-cluster on a schedule; never patch clusters incrementally forever

**Why this phase exists at all:** identity is an equivalence relation — reflexive, symmetric, and **transitive**. Similarity satisfies the first two and violates the third. A ≈ B and B ≈ C does not give A ≈ C. So pairwise scores form a relation that is logically inconsistent with being an identity relation, and must be projected onto valid equivalence relations.

**The failure this prevents:** naive transitive closure over pairwise matches produces **chaining** — a path of individually plausible weak links silently merges half the catalog into one entity. This is the dominant catastrophic failure mode in real deployments, and it is invisible until someone notices that "produce" now costs $40k a week. **The decision about any pair depends on the structure of the whole graph.**

### 4.6 Phase 5 — Human adjudication loop *(ongoing, front-loaded)*

**Do:**
- Three-region thresholds: auto-link above τ_hi, auto-reject below τ_lo, route the middle to review (Fellegi & Sunter, 1969 — still the correct architecture)
- Order the review queue by **expected information gain × dollars at stake**, not by score alone
- Every adjudication becomes both a training label and a hard constraint fed back to Phase 4

**Why the thresholds are asymmetric:** a **false merge** conflates distinct things — it corrupts aggregates invisibly, is hard to detect after the fact, and is often irreversible once downstream systems consume it. A **false split** leaves duplicates — visible, annoying, recoverable. The losses are not symmetric, so the operating point is not 0.5. **Bias toward splits.**

> Note the structural echo: this is the same reasoning as the newsvendor quantile in §2.1. Asymmetric costs mean the optimal operating point is never the point estimate. The pattern recurs throughout this work.

**Why humans are irreducible:** identity is not observable, so a domain expert is the only ground truth generator. They are expensive, so allocate their attention by expected information gain. The queue shrinks over time as adjudications accumulate.

### 4.7 Phase 6 — Multi-grain, temporally-valid item master *(2–3 weeks)*

**Do:**
- Resolve at **multiple grains simultaneously**: lot → vendor SKU → generic ingredient concept → category
- Validity intervals on every entity and every link (SCD Type 2; bitemporal if you must reconstruct prior beliefs)
- Provenance on every link: which rule or model asserted it, at what confidence, adjudicated by whom and when

**Why multiple grains:** the correct granularity is defined by the decision, not by metaphysics.

| Decision | Is Vendor A's Roma the same entity as Vendor B's? |
|---|---|
| Recipe costing | **Yes** — interchangeable inputs |
| Vendor price comparison | **No** — distinct, but linked to a shared concept |
| Food safety traceability | **Emphatically no** — different lots, different recalls |

There is no purpose-independent ground truth about grain. Forcing one flat resolution guarantees you are wrong for some of the client's decisions. *This is also precisely why generic ER products underperform here — the correct grain is a function of the client's decisions, which is consulting work, not configuration.*

**Why temporal validity:** identity persists through change (Ship of Theseus, with a P&L attached). "Farm Salad" renamed to "Garden Salad" with the same recipe is the same entity; the same name with chicken swapped for tofu is arguably a different one for costing. A SKU whose pack drops from 25# to 20# is the same product with a different purchase unit. **Without versioning, historical comparisons silently become false while continuing to render cleanly** — and retrofitting temporality onto a flat master is close to a rebuild.

### 4.8 Phase 7 — Continuous operation

**Do:**
- New-item detection on every invoice ingest; nothing enters costing unresolved
- Drift monitoring: match rate, review queue depth, **unmatched share of spend**
- Scheduled re-clustering as the catalog grows

**Why:** the world is open. New entities arrive continuously and vendors change descriptions without notice. ER is a running process, not a batch job with a completion date. Treat absence of an attribute as *uninformative*, never as disagreement — otherwise sparse records get systematically split.

---

## Part 5 — Why This Specific Structure Is Necessary

The phase order is not stylistic preference. Each ordering constraint is forced.

| Ordering constraint | Why it cannot be inverted |
|---|---|
| **Grain before build** (P0 → all) | Entity granularity is determined by the client's decisions. Building first guarantees rework at the schema level. |
| **Deterministic before probabilistic** (P1 → P3) | Never spend model capacity on variance a rule can eliminate. Rules are cheaper, auditable, and don't consume training data. |
| **Recall ceiling before precision tuning** (P2 → P3) | Blocking recall caps system recall absolutely. Tuning a matcher against a blocked-out pair is unfalsifiable effort. |
| **Calibration before thresholding** (P3 → P5) | Thresholds must be derived from asymmetric loss. That requires probabilities, not scores. |
| **Clustering after pairing, but never pairing alone** (P3 → P4) | Identity is transitive, similarity isn't. Skipping the projection step invites chaining collapse. |
| **Temporal model before history is trusted** (P6 → any trend analysis) | Retrofitting validity intervals onto a flat master is a rebuild, and every analysis produced before it is suspect. |
| **Value in every phase, spend-weighted** (all) | A nine-month cleaning project with no visible output loses the client in month four. |

### The economics that make phasing viable

Value is **Pareto-distributed**: ~20% of items carry ~70% of spend. This is what makes an incremental rollout legitimate rather than a compromise.

- Resolve the **top 20 items by spend first** and begin forecasting on those immediately
- Precision must be high on proteins and produce; the long tail can be coarse or deferred indefinitely
- **Measure progress in *dollars of COGS resolved*, not records resolved.** Record-count metrics reward long-tail work that doesn't matter and disguise gaps in the items that do.

### Suggested engagement arc

| Stage | Work | Trigger served | Purpose |
|---|---|---|---|
| **0–4 weeks** | Payment processing audit; POS-only menu margin analysis | Margin (quick win) | Found money, near-zero risk, buys credibility |
| **1–3 months** | ER Phases 0–3 on top-20 spend; invoice extraction | **Time savings** | Felt relief; funds the substrate |
| **3–6 months** | ER Phases 4–6; theoretical-vs-actual variance; weekly flash P&L | Margin + Stress | First real margin movement |
| **6–12 months** | Hierarchical + quantile forecasting; prep lists; labor scheduling; FDR-controlled alerts | Margin + Stress | The differentiated capability lands |
| **12 months+** | Process mining; SOP codification; lineage and reproducible reporting | **Exit valuation** | Converts the system into a transferable asset |

---

## Part 6 — Failure Modes to Design Against

| Failure | Mechanism | Guard |
|---|---|---|
| **Chaining collapse** | Transitive closure over weak pairwise links merges unrelated entities | Constrained clustering with cannot-link rules; monitor max cluster size and cluster spend |
| **Silent blocking loss** | True matches never compared; invisible downstream | Hand-labeled blocking recall audit before matcher tuning |
| **Confidently wrong units** | Correct identity, wrong conversion or missing yield factor | Unit algebra as a typed layer with dimensional checks; reconcile against physical counts |
| **Alert fatigue** | Uncorrected multiple testing floods the owner with false positives | FDR control; changepoint rather than threshold logic; exception-only reporting |
| **Historical drift** | Renames and re-specs invalidate prior periods | Validity intervals from Phase 6 onward, not retrofitted |
| **Habit failure** | Output produced, no decision changed | Every deliverable attached to a named recurring decision and a named owner |
| **Patience exhaustion** | Long substrate build with no visible output | Spend-weighted incremental delivery; quick-win bridge |
| **Heterogeneity misfit** | Pooling across genuinely dissimilar concepts degrades forecasts | Test pooling gains empirically; hyperprior variance should widen — verify it does |

---

## Part 7 — The Short-Term Play Book

Findings deliverable in days, before you have authority, access, or a substrate. These are what earn the right to build everything in Parts 3–5.

**Reference case throughout: 5 units, $10M total revenue, meaningful delivery volume.** All dollar figures are planning estimates across all five units, not guarantees.

### 7.1 Qualification criteria

A play belongs in this section only if it satisfies all five:

1. **No operational change required to capture the value.** A POS configuration edit, a portal change, or a contract renegotiation qualifies. A new weekly staff habit does not.
2. **Low data friction.** Obtainable from a stranger. A POS export and a PDF, not payroll and AP ledgers.
3. **Deliverable in hours or days**, not months.
4. **Dollar-quantifiable, or capability-proving.** One or the other, explicitly.
5. **Emotionally safe.** See below.

A sixth criterion, less obvious and arguably the most important early on:

> **Who does the finding implicate?** Most analysis implicitly says *you have been doing something wrong.* A few say *someone else has been taking your money.* The second creates alliance instead of defensiveness. In a first engagement that difference is worth more than the dollar value.

### 7.2 Non-CS plays — document review, domain knowledge, negotiation

No code, no pipeline. A statement, a rate table, and a phone call.

| Play | Input | Effort | Value/unit/yr | Knowledge required |
|---|---|---|---|---|
| **Merchant processing audit** | 3 monthly statements | 3–4 hrs | $8–15K | Interchange structure, pricing models, junk-fee taxonomy |
| **Waste, linen, hood, pest contracts** | Contracts + 12 mo invoices | 2–4 hrs each | $3–10K | Market rates, evergreen/auto-renew terms |
| **Utility tariff review** | 12 mo utility bills | 2–3 hrs | $2–6K | Commercial rate classes, demand charges |
| **Workers' comp classification** | Policy + payroll summary | 2–3 hrs | $3–12K | Class codes, experience mod |
| **CAM reconciliation** | Lease + landlord statements | 4–8 hrs | $2–15K | Commercial lease structures |
| **Tax credit flags** (e.g. FICA tip credit) | Payroll summary, prior return | 1–2 hrs | Varies, often large | Enough to spot it — then refer to their CPA |

**Merchant processing — the analytical core.** Transaction cost decomposes into interchange (paid to the issuing bank, non-negotiable), assessments (paid to the networks, non-negotiable), and **processor markup — the only negotiable component.** Pull current interchange schedules from Visa's and Mastercard's published US tables directly; they revise twice yearly and secondhand figures go stale.

The one number: **effective rate = total card fees ÷ total card volume**, summing *every* fee line including monthly items and equipment lease.

| Effective rate | Read |
|---|---|
| 2.2–2.5% | Well negotiated |
| 2.7–3.2% | Typical |
| 3.5%+ | Being fleeced |

At $2M revenue and 85% card volume, each 0.25 points ≈ $4,250/yr. Moving 3.4% → 2.5% is ~$15,300/yr per unit.

Watch specifically for: tiered pricing (where the processor defines the "qualified" buckets and keeps the spread), PCI **non**-compliance fees charged solely because nobody completed a 20-minute questionnaire, and non-cancellable 48-month terminal leases written through a separate leasing entity so that switching processors doesn't end them.

> **Never accept a referral commission from a processor.** It is standard practice in that industry and it is disqualifying for an advisor. The moment your income depends on which processor they choose, you are a broker. State the prohibition unprompted in the first meeting — it differentiates you from everyone else who has ever cold-called them about payments.

### 7.3 CS plays — computation over data

| Play | Data | Technique | Effort | Value (5 units) |
|---|---|---|---|---|
| **Modifier pricing gaps** | POS item + modifier export | Aggregation, cost join | 4–6 hrs | **$75–200K** |
| **Price integrity audit** | POS price table + menu source | Diff/join | 2–3 hrs | $25–100K |
| **Void/comp/discount analysis** | POS transaction log | Exposure-adjusted rates, outlier detection with FDR control | 1–2 days | $20–40K |
| **Open/unclosed checks** | POS transaction log | Query | 1–2 hrs | $10–40K |
| **Labor-to-demand overlay** | POS 15-min sales + payroll punches | Interval alignment | 1 day | Sizes a $50–150K prize |
| **Server check-average variance** | POS with server ID, party size | Regression with controls | 1–2 days | Sizes training opportunity |
| **Speed-of-service distribution** | KDS event log | Tail/distributional analysis | 1 day | Diagnostic only |
| **13-week cash forecast** | POS + AP + payroll | Time series | 2–3 days | No direct $ — stress trigger |
| **Holdout backtest + variance decomposition** | 12–24 mo POS | Hierarchical forecasting, decomposition | 3–5 days | Sizes the labor engagement |
| **Cross-unit benchmarking** | All units' P&L + POS | Like-for-like normalization | 2–3 days | $50–150K identified |
| **Menu price dispersion** | POS price list | Descriptive stats | 1 hr | Gates menu work |

**Modifier gaps** are the highest dollars-per-hour item on the entire list. Count incidence of give-away modifiers — extra cheese, add avocado, protein substitutions — and multiply by ingredient cost. Routinely $15–40K per unit, and perfectly invisible because no single instance is large enough to notice. Fix is a POS configuration change.

**Holdout backtest** — withhold the most recent 4–8 weeks, fit on the remainder, predict the holdout. Report **WAPE, not MAPE** (MAPE misbehaves on low-count items), at the level the decision is made (daily, daypart, top-20 items), and **always against a naive baseline** of same-weekday-last-week. That baseline *is* their current implicit forecast; if you can't beat it you have nothing.

The real payload is the variance decomposition — day of week, seasonality, weather, local events, holidays, and irreducible residual. The line that lands:

> *"Seventy-eight percent of your daily variation is predictable. You're staffing as though it's random."*

**Never tune on the holdout.** Use a separate validation split. A demo tuned until it looks good is a lie you told yourself, and it will fail visibly in production.

**Cross-unit benchmarking** is uniquely powerful for the 3–10 unit segment because the client is their own control group. Same menu, same brand, same ownership — the variance between their own locations cannot be dismissed as a different business. *"Location C runs 3.8 points better on labor than Location A at similar volume. If A performed like C, that's $76,000 a year."*

### 7.4 The two hybrids

Both combine a CS mechanism with a non-CS payoff. They are the best demonstrations that you are neither a pure analyst nor a pure auditor.

#### Delivery marketplace reconciliation

**The CS half — entity resolution in miniature.** Match platform order records to POS records across bad join keys: order IDs differ between systems, timestamps differ by 5–20 minutes (placed vs. fired vs. closed), totals differ because of delivery markup and layered fees, customer identity is a first name, and some orders never reach the POS at all. Block on date + time window + total band, then fuzzy match on **item composition** — three specific items in specific quantities is nearly a fingerprint and is far stronger evidence than totals or timestamps.

**The seven leakages:**

| Leak | Detection |
|---|---|
| **Misattributed refunds** | Refund rate by cause code vs. contractual attribution. Platforms default to charging the restaurant regardless of fault. |
| **Sales tax double-payment** | Marketplace facilitator laws require the *platform* to remit. Compare filed taxable sales against taxable sales net of marketplace orders. Look-back often 3 years. **Quantify and hand to their CPA.** |
| **Promo cost misallocation** | Line-by-line promo charges against signed funding-split terms |
| **Commission rate and base drift** | Verify tier rate *and* base — commission belongs on food subtotal, never on tax, fees, or tips |
| **Missing orders** | Platform orders with no POS counterpart — understated revenue, or food out the door unrecorded |
| **Price parity failure** | Item-level check that delivery markups are actually applied across all platforms |
| **True contribution margin** | Menu price − food cost − commission − **packaging** ($0.50–1.50/order, routinely omitted) |

**Why it opens doors:** operators already resent the platforms. You are not delivering uncomfortable news about their judgment — you are confirming a grievance they already hold and handing them evidence. That is an entirely different rapport dynamic from any other finding available to you, and every corrective action is a portal edit or a dispute filing.

#### Capacity vs. demand diagnostic

**The question:** is revenue limited by how many people want to come, or by how many you can serve? The prescriptions are opposite and getting it backwards destroys value.

**Method:**

1. Build the demand curve — sales and covers by **15-minute interval**, averaged by day of week over 8–12 weeks. Daily totals hide the entire phenomenon.
2. Identify candidate constraints: seats × achievable turns, kitchen throughput, server stations, expo pass, order-taking, queue/parking space. Only one binds at a time and it moves with volume.
3. Look for the **statistical signatures of a binding constraint**:
   - **Distribution truncation** — a suspiciously tight upper bound at peak
   - **Variance collapse at peak** — *the cleanest single signal.* Demand is variable; capacity is not. Plot coefficient of variation of covers by interval; where it collapses, you are constrained. Works even when turnaways are unobservable.
   - **Nonlinear ticket-time inflation** — queueing theory: wait time → ∞ as utilization → 1. Plot KDS ticket time against concurrent open orders; the knee is *effective* capacity, typically 70–85% of theoretical.
   - Digital order abandonment and declined reservations during peak windows
4. Quantify. If constrained, this is a **censored data problem** — fit the demand distribution from unconstrained comparable periods and estimate the censored mass above the observed ceiling (Tobit or a survival framing). If unconstrained, compute idle seat-hours × contribution per cover.

**The opposite prescriptions:**

| | Capacity-constrained | Demand-constrained |
|---|---|---|
| **Marketing spend** | **Actively destructive** — buys demand you then fail, and a failed first visit costs lifetime value | The correct lever |
| **Right action** | Throughput: turn time, prep-ahead, peak menu simplification, staff the bottleneck specifically, pre-bussing | Traffic: local search, reputation, catering, daypart offers |
| **Pricing** | **Raise peak prices** | Promotional pricing, off-peak only |
| **Technology** | KDS pacing, order throttling, throughput analytics | Demand generation, loyalty, channel expansion |

The pricing row is the least intuitive and the most valuable: **a queue is a rationing mechanism that captures no value.** The waiting is a cost paid by the guest and collected by nobody. If you are turning people away at 7pm Friday, that is precisely when to charge more — price rations the same demand while capturing the value instead of burning it.

**The non-CS half:** you must walk the building at peak. No dataset will tell you the expo window is too small, that the dish pit starves the line of plates, or that a single host-stand terminal caps seating. Data tells you *that* you are constrained; observation tells you *where*.

**Deliver as a grid — day × daypart, shaded by binding constraint** — with suppressed demand in constrained cells and idle capacity in empty ones. Constraint status varies by daypart; the same restaurant is capacity-constrained Friday dinner and demand-constrained Tuesday lunch. A single blanket verdict is almost always wrong.

### 7.5 Ranking and the shippable package

**Tier 1 — run first, in this order**

1. **Delivery reconciliation** — the only play scoring well on every dimension: real dollars, no operational change, genuine CS in the matching, and the unique alliance dynamic.
2. **Modifier gaps** (bundle price integrity into the same pass — same export, three more hours) — highest dollars-per-hour on the list.
3. **Holdout backtest** — recovers nothing, takes the most time, still belongs in the top three. Lowest data friction of anything here (one POS export, no financials, no payroll) and the **only play that proves you are not a generic auditor.**

**Tier 2 — high value, more friction:** capacity vs. demand grid (needs a site visit; peak pricing is directly collectible); cross-unit benchmarking (needs unit financials, so gated on trust).

**Tier 3 — gated on access or discipline:** labor overlay (needs payroll; pairs with the backtest); void/comp analysis (capture requires management discipline; carries blame risk); 13-week cash forecast (needs AP access — a retention play, not an opener).

**Bundle rather than run standalone:** open/unclosed checks, refund concentration (subsumed by delivery reconciliation), menu price dispersion (a gate, not a project). **Defer:** speed-of-service — most independents lack KDS event data.

> **The divergence that matters.** Ranked by dollars alone: modifier gaps, price integrity, delivery reconciliation, void analysis — with the backtest dead last at zero. Ranked by *what to run first*, the backtest moves to third. That gap is the strategy. High-dollar plays buy the meeting but don't distinguish you and don't lead anywhere. The backtest is the only artifact that converts a one-time audit relationship into the forecasting engagement — where the recurring revenue and the ER build live.

**The package:** Tier 1 is roughly **one week of your time** and exactly **two data pulls** — an item-and-modifier-level POS export, and platform statements. That is a cold offer you can actually make:

> *"Send me two files. In a week I'll show you six figures you're currently leaking, and prove I can predict your sales better than your own experience can."*

*Dependency:* this ranking assumes meaningful delivery volume. For a dine-in-only operator, #1 drops out and modifier gaps become the opener — which changes both the data ask and the pitch.

### 7.6 Trigger coverage — and the gap it reveals

| Play | Money | Time | Stress |
|---|---|---|---|
| Merchant processing audit | ●●● | — | ○ |
| Vendor/utility/comp contracts | ●●● | — | ○ |
| Delivery reconciliation | ●●● | ○ | ○ |
| Modifier gaps / price integrity | ●●● | — | — |
| Void/comp analysis | ●● | — | ○ |
| Cross-unit benchmarking | ●● | — | ○ |
| Capacity vs. demand grid | ●● | — | ●● |
| Variance decomposition | — | — | ●●● |
| 13-week cash forecast | — | — | ●●● |
| Automate their existing manual weekly report | — | ●●● | ●● |

**The gap is the point.** Short-term plays are overwhelmingly **money** plays. Stress is partially servable — the cash forecast and the variance decomposition both reduce anxiety by converting perceived chaos into known structure, and neither requires an operational change. But **time savings is nearly absent from the short-term column**, with one exception: asking *"what do you do manually every Sunday?"* and automating that single workflow.

This is not an accident. **Time savings is structurally gated on the entity resolution substrate** (Part 3.2) — the hours are in invoice processing, inventory reconciliation, and recipe costing, none of which can be automated before identity is resolved. That is precisely why ER is funded by money plays and harvested as time and margin later.

**There is no short-term exit-valuation play.** By definition: exit value comes from durable, transferable, documented operations, which cannot be manufactured in weeks. The most you can offer early is a readiness baseline.

### 7.7 Operating notes

**1. The money is in the non-CS column; the moat is in the CS column.** Non-CS plays will usually out-earn CS plays in year one with far more certainty — and every one is replicable by any competent auditor, so they commoditize instantly. The CS column is the only reason anyone hires *you* specifically.

**2. The inversion nobody expects: the non-CS column is your steeper learning curve.** You already know how to build a variance decomposition. You do not know interchange qualification tiers, workers' comp class codes, or CAM escalation structures. **The "simple" column is where your actual gap is.** Each is roughly a weekend of study plus a reusable template. Learn processing and delivery reconciliation first — highest value, most transferable across clients.

**3. Non-CS is delegable; CS is you.** Every non-CS play reduces to a checklist and a template after the second run. Hand them to a junior analyst or a specialist partner on revenue share. Don't let them permanently consume your capacity — they don't compound and they don't lead anywhere.

**4. Two CS plays point at named individuals — handle with rigor or don't run them.** Void/comp analysis and server check-average variance both produce output that implicates people. Run naively — raw counts without adjusting for shifts worked, or flagging "outliers" across forty employees with no multiple-comparison correction — and you will finger innocent people at a false-positive rate approaching certainty. Someone gets fired over your chart. Report **exposure-adjusted rates**, apply **FDR control**, and present **distributions rather than names.** Let the operator decide who to look at; they know context you don't.

**5. The pairing rule.** Ship one play from each column in every early engagement. **The non-CS finding pays for the meeting; the CS finding earns the next one.** Neither does both jobs alone.

### 7.8 Short-term plays vs. post-ER capability

Three distinctions explain the difference:

- **Stock vs. flow.** Short-term findings are one-time extractions from a finite pool. You audit the processor exactly once. Post-ER capability produces a recurring stream.
- **Detective vs. prescriptive.** Short-term work finds errors in the past, and that backlog is finite — typically exhausted within two quarters. Post-ER work shapes future decisions, and that backlog is unbounded.
- **Subtractive vs. optimizing.** And this is load-bearing:

> **The ceiling on error correction is the size of the error. The ceiling on optimization is the size of the business.**

| | Short-term plays | Post-substrate capability |
|---|---|---|
| **Time to value** | 2–8 weeks | 4–9 months if **built**; **6–10 weeks if bought** (see 7.8.1) |
| **Repeatable?** | No — depleting pool | Yes — recurring weekly |
| **Compounds?** | No | **Yes** — each week of clean data improves forecasts; each adjudication improves the matcher; each new location strengthens pooling |
| **Enables other work?** | No — each finding isolated | **Yes** — one substrate unlocks menu margin, theoretical-vs-actual, vendor negotiation, forecasting, prep, and scheduling *simultaneously* |
| **Defensible?** | No — any competent auditor replicates it | **Partly.** The substrate itself is purchasable. The grain decisions, adjudication quality, cross-unit judgment, and adoption work are not. |
| **Execution risk** | Very low | Build risk if built (chaining, unit errors); vendor and integration risk if bought. **Adoption risk either way.** |
| **Triggers served** | Money, partially stress | Money + Time + Stress, then Exit |
| **Your revenue model** | Project fee or contingency | **Retainer** |
| **Relationship** | Transactional — ends when the pool empties | Structural — you are in the operating loop |

**Dollar comparison, 5 units / $10M, planning figures:**

- **Short-term, cumulative:** processing $50–75K, delivery reconciliation and pricing $30–60K, vendor contracts $15–30K, modifier and price integrity $25–50K, comp tightening $20–40K → **$140–255K, essentially once.**
- **Post-ER, annually recurring:** food cost variance closure ~2 points of sales ($200K), labor scheduling to forecast 0.5–1.5 points ($50–150K), menu margin optimization 1–3 points ($100–300K), vendor negotiation on normalized price history ($30–60K) → **$380–710K per year.**

Over three years: roughly **$200K vs. $1.2–2.1M** — and the gap widens annually because one side compounds and the other doesn't.

**What ER actually changes, stated precisely:** it is not that ER answers any single question better. It is that **it collapses the marginal cost of asking questions.** Before ER, every question — *what's our margin on the short rib, has beef crept since March, which location wastes the most produce* — requires a bespoke manual analysis. Cost is linear in the number of questions. After ER, they become queries: high fixed cost, near-zero marginal cost.

#### 7.8.1 Market reality — the substrate is largely purchasable

*Corrective to Part 4. Verified August 2026.*

**MarginEdge** sells invoice extraction, recipe costing, and a daily controllable P&L at **~$350/month per location, flat, to 11,000+ operators** — with invoice processing handled by automation *plus human verification*. That is the Fellegi–Sunter three-region architecture (auto-accept / clerical review / auto-reject) already shipped at scale. Restaurant365, Craftable, MarketMan, Crunchtime, and Fourth occupy adjacent positions.

**The implication is direct: building the ER substrate from scratch for a 1–10 unit client is almost always the wrong call.** You would be spending four months competing with a mature product that costs less than four hours of your billable time per month.

**Buy the substrate. Own the judgment.**

This is better news than it appears. It compresses Part 4 from a four-month build into a **3–6 week evaluation, configuration, and adjudication engagement**, which:

- gets you to differentiated work (forecasting, optimization) far sooner
- sharply reduces execution risk and patience exhaustion, the two failure modes most likely to end the engagement (Part 6)
- lowers the capital the client must front before seeing analytical output

**Part 4 should now be read as an evaluation and configuration standard rather than a build plan.** Its phases become the criteria by which you judge a vendor's implementation and correct it: is the grain right for *this* client's decisions (4.7)? Is pack-size and yield normalization actually correct (4.2)? Is the review queue prioritized by spend rather than record count (4.6)? Is there temporal validity on the item master, or will their history silently rot (4.7)?

#### 7.8.2 What survives as moat

| Commoditized — buy it | Still yours — services |
|---|---|
| Invoice OCR and extraction | **Grain decisions.** Vendors resolve to *their* schema for *their* purpose (costing). Nobody resolves for costing + vendor negotiation + traceability simultaneously. |
| Generic item matching | **Unit algebra and yield modeling** specific to the concept — BBQ protein yield is not a solved product feature |
| Baseline recipe costing | **Adjudication quality** — whether the top-spend items are resolved correctly, which determines whether every downstream number is true |
| Store-level dollar forecasts | **Item-level quantile forecasts** at newsvendor-derived service levels |
| Basic labor scheduling | **Hierarchical pooling across the client's own units**; cold-start priors for new locations |
| Dashboards | **Adoption** — the habit loop without which none of it changes a decision |

**The open technical claim.** POS-native and most vendor forecasting is *store-level and historical* — it reports what happened and roughly what next week looks like in dollars. It rarely says how much of each item to prep or how to staff to it. The gap between a mean revenue forecast and an item-level quantile forecast is real, and for the sub-10-unit independent it appears unclaimed.

#### 7.8.3 The competitive map

| Layer | Incumbents | Note |
|---|---|---|
| **POS** | Toast, Square | Toast IQ shipped to all US Toast customers late 2025 — plain-English Q&A on sales/labor/menus, and it acts. Bundled and free at the margin. |
| **Back office / food cost** | MarginEdge, Restaurant365, Craftable, MarketMan | The ER substrate, productized |
| **Forecasting** | **ClearCOGS**, Praedixa, Tenzo, Crunchtime, Fourth | ClearCOGS is the closest analogue to this framework's thesis — founded 2021, $3.8M seed in 2025, item-level prep forecasting. Customer base skews to franchise brands and volume concepts. |
| **Labor scheduling** | 7shifts, Sling, Toast native | Priced for independents |
| **Cost recovery** | P3 Cost Analysts (since 1991, national franchise network), The SALT Group, Prescient, XRS | **The entire non-CS column of 7.2 is a mature industry.** Refer or white-label; do not build here. |
| **Traditional consulting** | Aaron Allen, RSM, boutiques | Concept, brand, ops, investor-facing — not data |

**The threat to watch is Toast.** They bundle, they own the data, and they ship AI features to the entire installed base at once. Anything commoditizable will eventually be commoditized. Defensibility must therefore live in what a product company structurally *cannot* do at scale: sit with a chef for two hours adjudicating item matches, watch the expo window at Friday peak to find the real bottleneck, and decide the entity grain for one operator's specific questions.

**This is a services moat, not a software moat.** Plan accordingly — the deliverable is judgment and adoption, and the software is an input you procure.

#### 7.8.4 What this changes about sequencing

Short-term plays now fund a *shorter* substrate engagement, which strengthens rather than weakens the case for them. The arc compresses:

| Old assumption | Revised |
|---|---|
| Months 1–3: short-term plays fund a 4-month ER build | Months 1–2: short-term plays fund a 3–6 week vendor implementation |
| Differentiated forecasting at month 6–12 | Differentiated forecasting at **month 3–4** |
| Moat = the substrate you built | Moat = grain, adjudication, pooling, and adoption |

**The client-selection corollary:** the value of a resolved substrate scales with the number of questions the client will ever ask. For an owner who wants one answer and then to be left alone, ER is a bad investment — sell them the audits and leave. For an owner who will run this business for a decade and is curious about it, it is transformative. Ask enough questions during the diagnostic to tell which one is sitting across from you.

**Why short-term plays are not inferior.** They serve a different function, and framing this as a competition is the mistake. They fund the ER build out of recovered cash rather than thin working capital; they buy the access — invoices, recipes, payroll — that nobody hands a stranger; they prove you are worth listening to *before* you ask for six months of patience; and they de-risk the decision for someone at 5% net margin who cannot afford to be wrong about you.

> **Short-term findings buy you the right to build the long-term asset.**

Lead with them, be excellent at them, and tell the client explicitly that they are the opening act. Saying out loud that the audits are finite and the real work comes after is itself a credibility move — it is what someone playing a long game says, and it separates you from the people who only have the audits.

---

## Appendix — Foundational References

- Newcombe et al. (1959), *Automatic Linkage of Vital Records* — origin of probabilistic record linkage
- Fellegi & Sunter (1969), *A Theory for Record Linkage*, JASA — m/u weights, three-region decision architecture
- Bansal, Blum & Chawla (2004), *Correlation Clustering* — the transitivity projection problem and its hardness
- Wickramasuriya, Athanasopoulos & Hyndman (2019), *Optimal Forecast Reconciliation* (MinT)
- Gelman & Hill, *Data Analysis Using Regression and Multilevel/Hierarchical Models* — partial pooling
- Benjamini & Hochberg (1995), *Controlling the False Discovery Rate*
- Angelopoulos & Bates, *A Gentle Introduction to Conformal Prediction*
- van der Aalst, *Process Mining: Data Science in Action*
- Abadie, Diamond & Hainmueller (2010), *Synthetic Control Methods*
- Tobin (1958), *Estimation of Relationships for Limited Dependent Variables* — censored estimation, used for suppressed demand under a capacity ceiling
- Kasavana & Smith (1982), *Menu Engineering* — the popularity × contribution margin classification
- Little (1961), *A Proof for the Queuing Formula L = λW* — the queueing basis for ticket-time inflation near capacity
