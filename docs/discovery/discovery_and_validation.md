# Discovery & Validation (the "Marco" data source + the question set)

Two things live here: (1) the **annotated onboarding conversation** that the simulated data's realism
is modeled on (`docs/engine/simulated_data`) and that the strategic assumptions (`docs/strategic_context`) must be validated against, and
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
are the spec the synthetic data (`docs/engine/simulated_data`) is built to mirror. What the conversation produced:

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
data evaporates each morning. So **capture 86 events from day one** (Hard Truth #1, `docs/engine/data_hard_truths`).

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

**Before you book — the seat check (30 seconds, saves the whole call).** Ask whoever is making the
intro, or the operator in the scheduling message: *"who decides how much of each thing gets prepped or
made for tomorrow?"* Interview **that** person. Warm intros arrive attached to whoever is most sociable
or most senior, which correlates with the wedge decision only by accident — a multi-unit owner may own
front-of-house and bar while a partner owns everything perishable.

**Ask the seat check per *site*, not per operator — the seat moves as a location matures.** At a new
restaurant the chef-owner usually sets prep himself; at his established one the same decision has almost
always been **delegated to a kitchen manager** who is not in the room and whose counts the owner now
simply receives. The same person can therefore be the right seat for one of his restaurants and the wrong
seat for the other, *in the same conversation*. Two consequences: score the wedge assumptions per site
(below), and note that the **delegated par-setter at the mature site is usually the higher-value
interview** — that site is where the history lives.

**If you can't redirect** (the intro is a gift, the meeting is already set, or the seat is only apparent
mid-call): run it, but **re-budget the call in real time** from discovery to *referral-generation*. Stop
spending questions on assumptions this person can't answer, and spend them on getting a committed, dated
intro to the person who can. A wrong-seat call that walks out with the right-seat referral is a success;
one that walks out with rapport alone is not.

**The maturity check (same message, one more line).** *"How long has this location been open, and how
long has the current menu been running?"* This is not small talk — it decides whether the operator is even
addressable. **Pain and data are inversely distributed.** A new opening has acute, genuine demand anxiety
and no history for anyone to learn from — including us. A mature site has years of history and an operator
who has already mined it into pars he trusts. The wedge is strongest exactly where the pain is dullest.
Record the answer per site and let it qualify every A1/A7 score: "unsaturated and painful" claimed at a
two-week-old restaurant is a statement about a **cold-start** problem, not about our product's opening.

**The money check.** The seat check finds who makes the *prep* decision; it says nothing about who makes
the *purchase* decision. Ask: *"if you wanted a new tool for the kitchen, who signs off?"* In partnerships
these are routinely different people — one partner owns every perishable decision and no money decision,
the other holds leases, lawyers, and spend while never touching prep. **A10 can only be scored by the
money seat**, and a product that needs the user's love *and* the partner's wallet has two independent
failure points. Find out early whether you are talking to one seat or both.

**Protect the gating pulls — a warm call is the dangerous one.** The seat check gets you the right person;
it does not get you the answers. A conversation that is going *beautifully* — generous, philosophical,
personally enjoyable — is the one where the two pulls (saturation, data access) feel rude and quietly get
dropped, and you leave with rapport and no confirm-or-kill. **Budget the last ten minutes for them and
spend them regardless of how the call is going.** Rapport is banked and reusable across visits; an
unasked gating question costs you the entire interview.

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
   be busy / do about $X'?"* — the single most important confirm-or-kill (capture exact words). Then,
   immediately, the **belief half** — the answer to "does it exist" is worthless without it: *"If that
   number showed up tomorrow morning, no work on your end — would you use it? What would have to be true
   for you to believe it?"* Listen for which barrier they name: **absence** ("nothing does that"),
   **belief** ("I wouldn't trust a computer to know my Saturday"), or **irrelevance** ("I already know").
   Absence is a build problem, belief is a product-surface problem, irrelevance is a wedge problem — and
   they are not interchangeable. The barrier they name is more informative than the yes/no that precedes
   it. Then the **incumbent half**, which the other two still miss: *"So how do you land on that number
   today — how do you know how many to make?"* **"No tool does that" is not the same as "that decision is
   unsolved."** The usual incumbent is a **par**: a remembered or written per-item quantity the operator
   derived by looking back over his own history ("I know we should have this many sandwiches prepped for a
   Tuesday"). It is free, instant, zero-maintenance and completely trusted, and it does not appear in any
   software audit — so a question that only asks about *tools* will report an open field that is in fact
   occupied. Capture the par: which items have one, where it came from, **who owns it now** (see the seat
   check — at mature sites it has often been delegated), and what it does on an abnormal day. That last
   part is the crack worth widening: a par is a constant, and demand is not. Then: where tools let them
   down; whether a tool disappearing would change anything (the shelfware test).
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
| A1 | Prep-item forecasting is **unsaturated** | Tools stop at covers/$; prep is genuinely unsolved — *and* the named barrier is **absence** | A tool already outputs per-item prep, or they don't care per-item. **Score the barrier they name, not the yes/no** — two further non-confirming states: **trust** (no tool does it, but the concept is familiar/DIY'd and the barrier is credibility → *Mixed*; adoption moves from capability to credibility) and **par** (no tool does it, but a remembered/written par already answers it free, instantly and trusted → *Weaken*; the incumbent is the operator's memory, so **the par sheet, not a naive mean, is the baseline to beat in realized dollars**) |
| A2 | The **number is the decision** | "I'd just prep that" | "Depends on staffing / the walk-in" — hidden judgment layer. **Also watch for an override that dominates the ratio:** a quality floor on signature items, or a reputation floor at a new opening ("I don't want to disappoint somebody in the early days and lose their business forever"). There the operator is deliberately running a service level near 1 for reasons `Cu/Co` does not contain — score *partial confirm*: the number is the unit of decision, but its target is set by brand risk, not by the cost ratio |
| A3 | Output is **dollar-legible** | Reaches for $ figures on waste/stockouts unprompted | Shrugged off as cost of doing business |
| A4 | **Exogenous signals** matter & are gettable | Events/weather/reservations already swing prep, by gut | "Every day's basically the same" |
| A5 | **No added work** is satisfiable | Adopted tools rode on existing data/rituals | Even small new steps get abandoned |
| A6 | One-time **recipe mapping** is tolerable | Willing to sit once for a setup that then runs | Zero patience, or recipes change constantly |
| A7 | The **core pain** is real & acute | Spontaneous, emotional, specific stories | Calm, "we've got it handled." **Score per site, not per operator** (see the maturity check): the same person is often calm about a mature location and genuinely anxious about a new one. And check *which layer* the anxiety sits at — "are people going to come?" is acute demand pain at the **covers** level, which existing tools already serve. Acute-but-wrong-layer is not a confirm |
| A8 | **Decision layer** underserved, not analytics | "Plenty of data, don't know what to *do* with it" | "I just need better reports" |
| A9 | **1–10 location** zone is the buyer | Feels pain + has budget + no internal analyst | Tiny indie at capacity, or has an analyst. **In partnerships, check that the person who feels the pain is the person who spends** (the money check) — demographic fit means nothing if the user seat and the buying seat are two people |
| A10 | They'd **pay** | History of paying to fix ops pain | Only free tools; cancels anything paid. **Only the money seat can move this row** — enthusiasm from a user-seat operator who doesn't sign is *no-signal*, not a confirm |
| A11 | **Product vs. consulting** | Needs resemble other operators' (reusable) | Every need wildly bespoke (consulting) |
| A12 | **Data access** is feasible | Willing to share sales/ordering data | Guarded, won't / can't export |
| A13 | **POS access** path | Known-API POS (Toast/Square/…) | Locked-down or obscure POS |

## The traps and the reusable template
**Three traps to keep flagged:** *aggregated-data* ("I'll send my reports" → daily summaries; always
specify line-item, timestamped); *gatekeeper* (**two species — check both**, see below); *halo* (a warm,
well-run, insider-sourced yes biases pain down and politeness up — deliberately interview strugglers).

**The gatekeeper trap, both species.** (a) **Wrong seat:** the enthusiastic person may not own the
decision you're modeling. An owner can be fluent, generous, and completely outside the prep/perishables
call — that belongs to a partner, chef, or sous who wasn't in the room. Their enthusiasm is not access
to the decision. (b) **Wrong hands:** even in the right seat, their yes ≠ the export — always ask "who
physically pulls it?" Species (a) is the more expensive of the two: it costs you the entire
conversation, and it is invisible unless you check *before* booking (the seat check, above). Note that
(a) recurs *within* a single operator as his sites mature — solving it once does not solve it for the
next restaurant he owns.

**The halo trap, two amplifiers to watch for.** (1) **Don't transact.** If you book an event, buy a
meal at scale, or otherwise become a customer during a discovery call, every answer after that moment —
and every answer in every later conversation — carries a commercial relationship behind it. If it
happens, record it in the decode and discount accordingly; better, keep the transaction to a separate
message on a separate day. (2) **Count businesses, not conversations.** Two interviews inside one
ownership group are *one business sampled twice*, however different the two seats are, and they share
one set of suppliers, one city, one balance sheet, and one opinion of you. The scoreboard must record
them as such or n=1 will read as n=2 — which is precisely the arithmetic the folder's one statistical
rule exists to prevent.

**To build any discovery question, work backward from the model:** (1) name the model input (e.g. `Co`
for the short rib); (2) find the recent event that reveals it (the last over-prep); (3) phrase as past +
specific, never future + general; (4) go silent after; (5) decode against an assumption (A1–A13). Every
onboarding must walk out with: the ~15 items + each one's decision unit (batch count vs. ingredient par)
**+ its lead time and whether a buffer already absorbs the error** — a smoked brisket is committed 12–24h
before service against a hard supplier cutoff, and an operator who holds spare raw and stays "seven or
eight hours ahead" has already bought himself a cheap answer to run-outs that no forecast improves on;
**+ the existing par for each item and who owns it now**; + rough `Cu`/`Co`; the POS, history depth,
*who exports it*, and whether 86s are logged; a bounded one-time recipe commitment; the real exogenous
swings and which feeds are gettable; **the age of each site** (the maturity check); **who signs off on
spend** (the money check); and a referral that extends *past* the insider's circle — past the ownership
group entirely, and especially toward strugglers.
