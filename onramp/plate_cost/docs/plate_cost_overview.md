# Plate-Cost Tool — Documentation Index

**Scope:** the plate-cost on-ramp only. For the forecasting engine see `../../../forecasting/docs/`
(engine theory) and `../../../docs/` (platform method/strategy). Module governance lives in
`../CLAUDE.md`; the durable on-ramp mandate is `../../README.md`.

The plate-cost tool is the **current implementation of the on-ramp service** — the first concrete bet
on a *durable* company function (instant value + data capture in one act). It delivers a real margin
map, live in the chef sitdown, in exchange for the two data legs the forecasting engine needs: a
sales export and a confirmed BOM. The tool is a capture mechanism first, a product second — the
on-ramp *function* outlives whatever product implements it, so build this product thin and
replaceable, and treat the slot as first-class.

---

## This overview was split into focused docs (2026-06-25)

The original monolithic overview is now an index over single-concern files, so each topic is findable
and the new client-website vision has room to grow without bloating the spec.

| Doc | Covers |
|-----|--------|
| [purpose_and_phases.md](purpose_and_phases.md) | Why this tool exists, its position in the product stack, and the Phase 0→4 build map + which engine data leg each phase captures. |
| [data_model.md](data_model.md) | The five-entity data model and the core plate-cost / margin computation. |
| [seam_and_precision.md](seam_and_precision.md) | The data boundary with the forecasting engine (the seam) and the precision discipline (never false precision). |
| [website_vision.md](website_vision.md) | **The client-facing website** — the above-and-beyond vision for showing operators what we do with their data and what we find in it. A north star; the build stays phased and thin. |
| [website_production_overview.md](website_production_overview.md) | **PoC → production service** — the approved execution map (2026-07-13) from the W0–W3 proof of concept to a hosted website with a designated application database maintaining real user data. Extends the vision's §8 roadmap with W5–W10 (app DB, identity, costed views, hosting, the public face, seam tenancy, account completeness) and the two-store architecture. |

> The authoritative, full Phase 0→4 build detail lives in `../CLAUDE.md` ("Build phases"). The
> `phases` section below is the condensed data-leg view; CLAUDE.md governs the build.
