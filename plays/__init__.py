"""plays/ — one-off analyses, deliberately outside the dependency chain (⊥).

Home for the §7.1 detective plays: merchant-processing audits, contract audits, modifier-gap
analysis, delivery reconciliation. Each reads the store, emits a report, and ends.

**Empty by design.** No play has been built; this package exists so the boundary exists before the
first one arrives, and so `.importlinter`'s `plays-are-terminal` contract has something to point at.

Why the isolation is structural rather than a convention (docs/repo_architecture.md §5.3): these
are *stock, not flow* — one-time extractions from a finite pool, detective rather than
prescriptive. They fund and de-risk the substrate, and they must never become a dependency of it,
or their commoditized, non-compounding nature infects the part that does compound. Plays may import
any layer; nothing may import a play.
"""
