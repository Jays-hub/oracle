"""
ingestion — Entity Resolution: the L1 identity layer
=====================================================
**Empty by design until R2. This docstring is the spec, not a description of code below it.**

Turns raw invoice and POS lines into resolved entities that every downstream number can be
denominated in. Governed by ``docs/real_data_readiness.md`` §4 (the R0-R6 order) and
``docs/consulting_framework.md`` Part 4 (the method).

Why this package matters more than its line count suggests
----------------------------------------------------------
Identity across both peers is currently ``name.strip().casefold()``
(``src/report/grid.py::normalize_name``). That is correct for a chef's hand-typed recipe sheet and
fails silently on the first real invoice: ``TOMATO ROMA 25# CS``, ``Tomatoes, Roma, 25 lb``,
``Roma tomato`` and ``4 oz diced`` casefold to four distinct ids, so four price histories accumulate
for one tomato and every plate cost touching it is wrong -- confidently, with a clean render.

The chain that must be traversed for any costing question, where every arrow is an identity match
composed with a unit conversion and a yield factor::

    POS sale -> menu item -> modifiers -> recipe -> ingredient -> purchase unit -> invoice line -> price

Identity is not observable; only similarity is. Entity resolution is the inference from the second
to the first.

The phase order, and why each step cannot be moved
---------------------------------------------------
R2  Canonicalization (deterministic, auditable, no model)
      Case/punctuation/abbreviation normalization, noise-token stripping, and the step that buys
      the most in this domain: **pack-notation parsing** (``25#``, ``6/#10``, ``4x5kg``, ``CS``,
      ``EA``) into structured (count, size, unit), plus count<->weight bridging via piece weight or
      density, plus trim/cook yield factors. Extends ``src/bom/units.py``, which today handles
      weight and volume families correctly but knows nothing of pack notation.
      *Forced first:* never spend model capacity on variance a rule can eliminate. Rules are
      cheaper, auditable, and consume no training data.

R3  Blocking / candidate generation
      Multi-pass keys unioned (normalized head noun; pack-size band; vendor + category; character
      n-gram LSH). **Measure blocking recall against a hand-labeled sample before proceeding.**
      *Forced here:* blocking recall is a hard ceiling on total system recall -- a pair never
      compared can never be matched, and the failure is invisible downstream. No matcher tuning
      recovers it.

R4  Probabilistic matching
      Frequency-weighted attribute agreement (Fellegi-Sunter m/u log-odds) + embedding similarity
      over descriptions, combined into a **calibrated probability, not a raw score**. Evidential
      weight is inverse to frequency: agreement on "case" says nothing, agreement on "piquillo
      pepper, 2.2kg tin" is nearly decisive.
      *Forced before R5:* thresholds must derive from an asymmetric loss function, which requires
      a real probability.

R5  Constrained clustering + human adjudication
      Identity is an equivalence relation -- reflexive, symmetric, **transitive**. Similarity
      satisfies the first two and violates the third, so pairwise scores must be projected onto a
      valid equivalence relation (correlation clustering, or hierarchical agglomerative with a
      principled stopping rule) under must-link (identical vendor + SKU + pack) and cannot-link
      (allergen conflict, incompatible UOM class) constraints.
      *The failure this prevents:* naive transitive closure produces **chaining** -- a path of
      individually plausible weak links silently merges half the catalog, invisible until someone
      notices "produce" now costs $40k a week.
      Adjudication is three-region (auto-link above tau_hi, auto-reject below tau_lo, route the
      middle to review), with the queue ordered by **expected information gain x dollars at stake**,
      never by score alone. Every adjudication becomes both a training label and a hard constraint
      fed back to clustering.
      *Thresholds are asymmetric -- bias toward splits.* A false merge conflates distinct things,
      corrupts aggregates invisibly, and is often irreversible once consumed downstream. A false
      split leaves duplicates: visible, annoying, recoverable. The operating point is not 0.5.
      (Structurally the same argument as the newsvendor quantile in ``forecasting/``: asymmetric
      costs mean the optimal operating point is never the point estimate.)

R6  Multi-grain, temporally-valid item master
      Resolve at several grains **simultaneously** (lot -> vendor SKU -> generic ingredient concept
      -> category), because the correct grain is defined by the decision, not by metaphysics: for
      recipe costing Vendor A's Roma and Vendor B's Roma are the same entity; for vendor price
      comparison they are not; for traceability emphatically not. Validity intervals on every
      entity and link (SCD Type 2), plus provenance: which rule or model asserted it, at what
      confidence, adjudicated by whom and when.
      *Forced before any trend analysis:* without versioning, historical comparisons silently
      become false while continuing to render cleanly, and retrofitting temporality onto a flat
      master is close to a rebuild.

Continuous operation (not a batch job with a completion date)
--------------------------------------------------------------
New-item detection on every invoice ingest -- nothing enters costing unresolved. Drift monitoring on
match rate, review-queue depth, and **unmatched share of spend**. Scheduled re-clustering; never
patch clusters incrementally forever. Treat an absent attribute as *uninformative*, never as
disagreement, or sparse records get systematically split.

Measurement rule
-----------------
Progress is **dollars of COGS resolved, not records resolved**. ~20% of items carry ~70% of spend;
resolve the top items by spend first, keep precision high on proteins and produce, and let the long
tail stay coarse or deferred. Record-count metrics reward work that doesn't matter and disguise gaps
in the items that do.

Status of the old Phase-2 GATE: ANSWERED (2026-08-13), not pending
-------------------------------------------------------------------
``plate_cost/CLAUDE.md`` gated this module behind a "POS-absorption check" -- *is Toast/Square about
to bundle this for free?* ``docs/consulting_framework.md`` §7.8.1 and §7.8.3 answer it with 2026
market fact: Toast IQ shipped to all US Toast customers in late 2025; MarginEdge sells invoice
extraction + recipe costing + a daily controllable P&L at ~$350/month per location to 11,000+
operators, with the three-region review architecture already shipped; Restaurant365, Craftable,
MarketMan, Crunchtime and Fourth hold adjacent ground; ClearCOGS is doing item-level prep forecasting
directly.

So the substrate is largely **purchasable**, and for a client deployment buying it is usually right.
That does not settle it for *this* repo, whose goal is holding raw, item-level, version-tracked data
it can model on and learn adjudication from -- which a vendor's export-limited view of their own
schema does not provide. The fork (build R2-R5 here vs. buy and own only the grain/adjudication
judgment) is deliberately **left open until R0** puts a real export and a real invoice stack on disk
and the actual variance is measurable. See ``docs/real_data_readiness.md`` §3.

Do not implement R2 before R0 and R1 exist: grain is determined by the operator's real decisions, and
building before you know which decisions the entities serve guarantees schema-level rework.
"""
