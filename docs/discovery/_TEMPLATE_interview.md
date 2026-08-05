---
date: YYYY-MM-DD              # interview date
operator: <pseudonym>        # NOT the real name — this repo is public
restaurant: <pseudonym>      # e.g. "70-seat full-service, seasonal American, 1 loc"
conversation_type: <cold | willing-partner>   # cold discovery excavates pain; onboarding extracts model inputs. Don't confuse them.
sourced: <cold-outreach | warm-intro | referral-from:X>   # halo bias rises with warmth
length_min: <n>
transcriber: whisperx
raw_file: _raw/YYYY-MM-DD.md   # gitignored; full verbatim lives there
---

# Discovery decode — <pseudonym>, YYYY-MM-DD

> **Decode discipline (read before scoring).** Score only what the operator raised **organically**.
> If *you* introduced a topic (said "waste," named a competitor, described the wedge), their reply is
> **no signal** — not a confirm. Compliments ("that sounds useful," "I'd try that") are the failure
> mode of discovery, never evidence. A single warm conversation can *kill* an assumption but cannot
> *confirm* one. Fill every quote **verbatim** from `_raw/`.

## 1. Conversation type & sourcing bias

- **Type:** _(cold discovery / willing-partner onboarding — and why it matters here)_
- **Sourced:** _(how you got to them; if warm/insider, name the halo bias — pain reads low, politeness reads high)_
- **One-line read of the room:** _(where they got animated, where they went vague, what they dodged — write this from memory now, it decays fast)_

## 2. The two gating pulls (do these first)

**A1 — saturation (the lead confirm-or-kill).** Did any tool they *already have* output per-item prep
quantities ("prep 18 short ribs"), or does it stop at covers/dollars ("Thursday will do $8,400")?

> _(verbatim quote — their exact words)_

**A12 / A13 — data access reality.** Not "would you share data" but **who physically pulls the
export**, from which POS, how far back, and whether 86s/run-outs are logged anywhere.

> _(verbatim — POS name, history depth, WHO exports it, are 86s recorded)_

## 3. A1–A13 scoreboard

Verdict: **Confirm** (organic, specific) · **Weaken** · **Kill** · **No-signal** (never came up organically).
Organic? = did *they* raise it unprompted (Y) or did you (N → downgrade to no-signal).

| # | Assumption | Verdict | Organic? | Verbatim quote | Notes |
|---|---|---|---|---|---|
| A1 | Prep-item forecasting is **unsaturated** | | | | |
| A2 | The **number is the decision** (not a judgment layer) | | | | |
| A3 | Output is **dollar-legible** (reaches for $ on waste/stockouts) | | | | |
| A4 | **Exogenous signals** matter & are gettable | | | | |
| A5 | **No added work** is satisfiable | | | | |
| A6 | One-time **recipe mapping** is tolerable | | | | |
| A7 | The **core pain** is real & acute | | | | |
| A8 | **Decision layer** underserved, not analytics | | | | |
| A9 | **1–10 location** zone is the buyer | | | | |
| A10 | They'd **pay** | | | | |
| A11 | **Product**, not consulting (needs generalize) | | | | |
| A12 | **Data access** is feasible | | | | |
| A13 | **POS access** path (known API) | | | | |

## 4. Marco-placeholder diff (these have live code consequences)

Mark each: **survived** / **revised** / **killed** / **no-signal**. Where revised, give the new value —
these feed real modules, so a change here is a change to the engine's assumptions.

| Placeholder (Marco's value) | This operator | Verdict | Code consequence if it changed |
|---|---|---|---|
| `Co`/`Cu` structure & magnitudes (short rib ~$100 waste; salmon ~$18 margin) | | | Newsvendor quantile per dish (P4) |
| 86s unrecorded, board wiped by morning | | | Censored-demand unconstraining is only justified if true (P3, Hard Truth #1) |
| Forward reservation book = strongest next-day feature | | | The exogenous layer's anchor signal (P5) |
| ~15 big items + one-time recipe confirm tolerated | | | The on-ramp capture funnel's core bet |
| Exogenous swings real & POS-blind (events, weather-delta, reservation depth) | | | Whether the differentiation layer is worth building |
| Ordering = a second horizon (2–4 day, ingredient-level) | | | A second waste channel / product surface |

## 5. The three traps — did any bite?

- **Aggregated-data trap** _(did they offer "reports"/daily summaries? did you pin down line-item, timestamped, by-daypart?)_
- **Gatekeeper trap** _(decision-maker's yes ≠ access path — who actually pulls it?)_
- **Halo trap** _(warm/well-run/insider → pain reads low, politeness high — discount accordingly)_

## 6. Referral

- **Who:** _(name/pseudonym)_ — **past the insider circle?** _(Y/N)_ — **toward a struggler?** _(the drowning place corrects the halo bias)_

## 7. Verdict & next actions

- **What this conversation killed / weakened / left standing:** _(be honest; n=1 confirms little)_
- **Next:** _(the single most concrete follow-up — a data pull, a second interview aimed at a struggler, a placeholder to revise in code)_
- **Roll into `assumption_scoreboard.md`:** _(once ≥2 interviews exist)_
