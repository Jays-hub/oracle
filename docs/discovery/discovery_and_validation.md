# Discovery & Validation (the "Marco" data source + the question set)

Two things live here: (1) the **annotated onboarding conversation** that the simulated data's realism
is modeled on (`forecasting/docs/simulated_data`) and that the strategic assumptions (`docs/strategic_context`) must be validated against, and
(2) the **cold-discovery question set** for real operator interviews. Everything strategic in this
project is a hypothesis until real operators confirm it — this is how that confirmation gets done.

**Two conversation types — don't confuse them:**
- **Cold discovery** (the question set, below): never pitch; excavate whether the pain is real.
- **Willing-partner onboarding** (the Marco transcript): someone already said yes; extract the specific
  inputs the model needs to exist.

The rule across both: **ask about specific, recent, concrete events — never hypotheticals.** "Walk me
through yesterday" → facts. "Would this help?" → politeness. Three mechanics make the questions work:
(1) keep your idea in your pocket — mentioning a solution contaminates every later answer; (2) anchor to
a recent specific instance; (3) talk less — after they answer, wait three seconds; the second half is
where the pain is.

## The Marco onboarding — source of the simulated "first data dump"
A worked onboarding with chef-owner "Marco" (70-seat full-service, 1 location, on Toast; 8 yrs;
seasonal American; menu changes ~4×/yr; 180–190 covers Sat vs. ~50 slow Tue; sous "Dani" sets prep,
owner overrides on weird weeks). **These are plausible placeholders, not validated facts** — but they
are the spec the synthetic data (`forecasting/docs/simulated_data`) is built to mirror. What the conversation produced:

**The two costs (two critical ratios, in his words).**
- **Short rib → `Co` (overage).** Braised 30 for an expected-huge Saturday; it rained (120 covers, not
  180); 14 left, a few ran as a Sunday special, the rest binned — ~$10 protein/portion → ~$100 in the
  trash. So `Co` ≈ food cost/portion, salvage ≈ 0 (the Sunday special = partial salvage to fold in).
  Prep this *lean* (low quantile).
- **Salmon → `Cu` (underage).** Sold through by 8pm; 8–10 tables wanted it after; best-margin dish
  (~$18 margin). "The one I most want to *not* run out of." So `Cu` ≈ margin + the intangible
  angry-table cost. Prep this *heavy* (high quantile).

**Censored demand (the silent killer).** "Does running out get recorded? Would Toast know you ran out
at 8?" — "No. Toast shows 22 sold. Dani 86'd it on the board; by morning the board's wiped." True
demand was 30+; train on 22 and you under-forecast your highest-margin dish forever, and the correction
data evaporates each morning. So **capture 86 events from day one** (Hard Truth #1, `forecasting/docs/data_hard_truths`).

**Exogenous swings (all POS-blind, all gettable).** Amphitheater 8 blocks away (concert nights slam
5:30, die 7:30 — currently caught only because "Dani's boyfriend works security"); the first warm
Saturday after a cold stretch is a different restaurant (→ engineer weather as a **delta, not a
level**); the Resy forward book (~60% reserved on weeknights = a real leading indicator; ~50% walk-in
on weekends → the book's predictive weight should itself vary by day of week). The forward book is the
**single strongest next-day feature** and is exportable today.

**The ordering decision (a second clock).** Protein/dry goods ordered Sun & Wed (US Foods, next-day);
produce 3×/wk. Over-order perishables → "slime by Thursday"; under-order → an emergency Restaurant Depot
run at retail (= `Cu` at the *ordering* horizon). Same demand engine, two horizons + two granularities
(prep ≈ 1-day, dish-level; ordering ≈ 2–4-day, ingredient-level). A second waste channel surfaced:
over-*ordering*, distinct from over-*prep*.

**The close (setup + data access).** One-time recipe confirmation for the ~15 big items ("an afternoon,
sure" — but "I'm *not* updating a spreadsheet every time I tweak a dish" → setup must be genuinely
one-time, and the system must tolerate recipe drift). Data access: ~2.5 yrs of Toast history, but **the
owner's yes ≠ the access path** — bookkeeper "Sarah" pulls the export. Always specify **line-item,
timestamped, by daypart** (not the daily summary). 86-board photos + a Resy CSV agreed instantly (free).
Referrals: "Theo" (3 spots — tests the product-vs-consulting fork) and a "drowning" place (corrects the
insider-halo bias).

**The discipline.** Marco is warm, well-run, and insider-sourced — the **easiest case and most biased
sample at once.** His yes proves **data access is feasible with a cooperative operator** and proves
**nothing** about saturation or whether the pain is widespread.

## The cold-discovery question set
**Purpose:** surface *organic, unprompted* mentions of addressable pain, and test the venture's
assumptions — without leading the witness. The strongest possible outcome is an operator describing your
wedge back to you before you've said a word. Talk to the **decision-maker for prep/ordering**; target
**1–10-location** operators; 20–35 min; capture **exact quotes**. Bring no slides or demo. Frame it as
"I'm trying to understand how kitchens make decisions," **not** "my friend is building a tool."

**Real signal vs. polite signal.** Real: a specific story, a number they reach for, a self-built
workaround, an emotional spike, money already spent, a tool they bought and *abandoned*. Worthless: "that
sounds useful," "I'd try that," any compliment — compliments are the failure mode of discovery.

The arc (anchor every question to a recent specific event):

1. **Opening / context** — concept; covers busy vs. slow + how predictable; who makes the calls; the
   opening-shift routine; what systems they run (let them list; don't prompt brand names).
2. **Day-in-the-life excavation** — walk me through yesterday; most annoying repetitive task; last time
   service went sideways; what was left over at close and what happened to it; *the last thing thrown
   out that made you wince (don't say "waste" first — see if they do)*; the last run-out and what it
   cost; where money leaks that shouldn't.
3. **Decision archaeology (prep & ordering)** — how the prep number gets set and by whom (the saturation
   read); the last big over-prep and under-prep; how a holiday/event/weird-weather/big-reservation
   changes prep (the organic exogenous test); how ordering is decided; what a new cook would get wrong
   (surfaces the tacit forecasting).
4. **Tool / workflow audit** — which tool they open daily vs. ignore; what the POS/inventory tool says
   about tomorrow; **THE saturation question (ask only after the above):** *"Does any tool you have tell
   you something like 'make this many portions of this dish tomorrow,' or does it stop at 'tomorrow will
   be busy / do about $X'?"* — the single most important confirm-or-kill (capture exact words); where
   tools let them down; whether a tool disappearing would change anything (the shelfware test).
5. **Money & value** — what they pay for monthly and resent; a tool they abandoned and why; what they've
   tried for food cost / over-ordering; the last time they spent real money on an ops headache.
6. **No-added-work** — did the last new system stick, and why/why not; what they should track but don't
   (too much hassle); what an adopted tool rode on top of; patience for a setup that pays off in weeks
   (probes the one-time recipe mapping).
7. **Targeted probes (late, optional)** — *if you'd been handed the exact right quantity per item the
   night before, no work on your end, would you have done anything differently?* (the "is the number the
   decision?" probe — listen for "I'd just make that" vs. "depends on staffing / the walk-in"); do they
   put a dollar figure on over-prep/run-outs; the one thing that, 20% better, they'd actually notice
   (forces them to rank prep/waste against labor, supply chain, etc.).
8. **Logistics** — can I see a real prep list / par sheet / sales export; would you share a few weeks of
   data; who else should I talk to (incl. someone *drowning*); can I come back.

## The assumption decoder (score what you heard *organically*)
After each interview, map what they volunteered (not what you asked) to the venture's assumptions — to
catch yourself manufacturing confirmation:

| # | Assumption | Confirms it (organic) | Kills / weakens it |
|---|---|---|---|
| A1 | Prep-item forecasting is **unsaturated** | Tools stop at covers/$; prep set by gut/spreadsheet | A tool already outputs per-item prep, or they don't care per-item |
| A2 | The **number is the decision** | "I'd just prep that" | "Depends on staffing / the walk-in" — hidden judgment layer |
| A3 | Output is **dollar-legible** | Reaches for $ figures on waste/stockouts unprompted | Shrugged off as cost of doing business |
| A4 | **Exogenous signals** matter & are gettable | Events/weather/reservations already swing prep, by gut | "Every day's basically the same" |
| A5 | **No added work** is satisfiable | Adopted tools rode on existing data/rituals | Even small new steps get abandoned |
| A6 | One-time **recipe mapping** is tolerable | Willing to sit once for a setup that then runs | Zero patience, or recipes change constantly |
| A7 | The **core pain** is real & acute | Spontaneous, emotional, specific stories | Calm, "we've got it handled" |
| A8 | **Decision layer** underserved, not analytics | "Plenty of data, don't know what to *do* with it" | "I just need better reports" |
| A9 | **1–10 location** zone is the buyer | Feels pain + has budget + no internal analyst | Tiny indie at capacity, or has an analyst |
| A10 | They'd **pay** | History of paying to fix ops pain | Only free tools; cancels anything paid |
| A11 | **Product vs. consulting** | Needs resemble other operators' (reusable) | Every need wildly bespoke (consulting) |
| A12 | **Data access** is feasible | Willing to share sales/ordering data | Guarded, won't / can't export |
| A13 | **POS access** path | Known-API POS (Toast/Square/…) | Locked-down or obscure POS |

## The traps and the reusable template
**Three traps to keep flagged:** *aggregated-data* ("I'll send my reports" → daily summaries; always
specify line-item, timestamped); *gatekeeper* (the decision-maker's yes ≠ data access — always ask "who
pulls it?"); *halo* (a warm, well-run, insider-sourced yes biases pain down and politeness up —
deliberately interview strugglers).

**To build any discovery question, work backward from the model:** (1) name the model input (e.g. `Co`
for the short rib); (2) find the recent event that reveals it (the last over-prep); (3) phrase as past +
specific, never future + general; (4) go silent after; (5) decode against an assumption (A1–A13). Every
onboarding must walk out with: the ~15 items + each one's decision unit (batch count vs. ingredient par)
+ rough `Cu`/`Co`; the POS, history depth, *who exports it*, and whether 86s are logged; a bounded
one-time recipe commitment; the real exogenous swings and which feeds are gettable; and a referral that
extends *past* the insider's circle (especially toward strugglers).
