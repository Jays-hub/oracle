# Plate-Cost: Purpose, Position, and Phase Map

**Part of the plate-cost docs.** Index: [plate_cost_overview.md](plate_cost_overview.md). Data model:
[data_model.md](data_model.md). The seam + precision discipline: [seam_and_precision.md](seam_and_precision.md).

---

## Purpose and position in the product stack

The plate-cost tool is the **current implementation of the on-ramp service** — the first concrete
bet on a *durable* company function (instant value + data capture in one act), governed by
`../../README.md`. It delivers instant value — a real margin map, live in the chef sitdown — in
exchange for two things the forecasting engine needs: a sales export and a confirmed BOM. The tool
is a capture mechanism first, a product second; the on-ramp *function* outlives whatever product
implements it, so build this product thin and replaceable.

Its strategic logic rests on a single insight: the BOM that powers plate-cost computation is the
same BOM `../../../forecasting/src/decision/ingredients.py` consumes for ingredient-level demand. One
recipe-confirmation session, zero duplicated asks.

---

## Phase map and data legs captured

| Phase | What it builds | Data leg captured for the forecasting engine |
|-------|---------------|----------------------------------------------|
| 0 | Static margin map from seed prices | BOM + POS sales export |
| 1 | Yield + unit conversion hardening | (refines BOM quality, no new leg) |
| GATE | POS-absorption competitive check | — |
| 2 | Invoice ingestion + entity resolution | Invoice / purchase history |
| 3 | Price monitoring + alerts | (real-time updates, no new leg) |
| 4 | Handoff | Forecasting engine switches on |

The one data leg NOT captured here: the 86 / stockout log. That is a separate, deliberately minimal
habit (tap a dish when it runs out → lost-sales dollar figure).

> This is the condensed, data-leg view. The full per-phase build detail — goals, "hardest part,"
> the pre-Phase-2 competitive gate, and the drift callouts — is the authoritative `../CLAUDE.md`
> ("Build phases").
