# The On-Ramp Website — Production Overview (proof of concept → full service)

**Status:** approved execution map (Jay, 2026-07-13). This doc extends the phased roadmap in
[website_vision.md](website_vision.md) §8 beyond W4: it takes the website from the fast, thin
proof of concept built in W0–W3 to a **fully fledged, hosted service with a designated application
database that creates and maintains real user data**. The vision doc stays the north star for *what
the surfaces are*; this doc is the map for *how the service underneath them becomes real*.

**This is sanctioned on-ramp-function investment, not drift.** The platform charter
(`../../../CLAUDE.md`) already names the website as the on-ramp's next surface, and the durable
mandate (`../../README.md`) is explicit that the acquisition + data-capture rail is permanent and
load-bearing. What this overview schedules — identity, storage, hosting, tenancy — is the **durable
chrome** of that rail (`.claude/rules/05`, "Thin Product, Durable Slot"): it survives even if
discovery swaps the plate-cost product out of the slot. Recorded per Jay's directive, 2026-07-13.
The Anti-Drift Standing Order still holds unchanged: none of this moves the moat, which lives in
`forecasting/`. The prep engine is the end; this service is the means — now built to production
grade because the means is how the company reaches a kitchen.

**Part of the plate-cost docs.** Index: [plate_cost_overview.md](plate_cost_overview.md).
Governance: `../CLAUDE.md` · full-stack rules `../../../.claude/rules/05–07` · seam contract
`../../../data/CONTRACT.md`. Every phase below is a normal gated phase: build freely, adversarial
review (`/review-web`) closes on the code, log entry in `docs/progress_log.md`
(`.claude/rules/00-process.md`).

---

## 1. Where the build stands (service review, 2026-07-13)

W0–W3 delivered a working, tested, seam-correct proof of concept:

- **W0** — the public read-only reveal (`GET /`): the popularity × margin grid over sample data,
  the "show a client in 60s" artifact.
- **W1** — the self-serve capture funnel (`/upload` → `/confirm`): POS export + recipe sheet in,
  validated through `schemas/seam.py`, written atomically to `data/raw/` (sales + BOM legs).
- **W2** — session login gating every data-bearing route, `/your-data` transparency counts +
  one-click CSV export, `src/store.py` (DuckDB-over-Parquet, structurally raw-only) wired into the
  web layer.
- **W3** — invoice capture (`/invoice/upload` → `/invoice/confirm`, appending the
  `price_observations` leg) and `/insights` (dollar-quantified price-move findings, honestly
  margin-free because the seam carries no menu prices).

The layering is right and stays: pure compute in `src/`, thin FastAPI glue in `web/`, server-rendered
Jinja2, no JS framework, every seam write through `schemas/`, boundary tests green. What makes it a
*proof of concept* rather than a service is a set of deliberate placeholder seams, each one recorded
at build time as "deferred until a real deploy/tenant exists." This overview is the plan that picks
them up:

| # | Proof-of-concept seam (today) | Production answer | Phase |
|---|---|---|---|
| 1 | Identity is one env-configured credential (`ONRAMP_AUTH_USERNAME` + SHA-256 hash); the tenant is the constant `RESTAURANT_ID = "default"` (`web/auth.py`) | Real user + restaurant records in the app DB; slow KDF (argon2/bcrypt); invite/signup, password reset | **W5** |
| 2 | Session secret is ephemeral per process unless `ONRAMP_SESSION_SECRET` is set; restarts log everyone out | Persistent, managed secrets; session records the app DB can list and revoke | **W5/W7** |
| 3 | CSRF protection is `same_site="lax"` only (recorded, not resolved — `W2_review.md` MINOR-3) | Per-request CSRF token on every state-changing POST | **W7** |
| 4 | No hosting story: `web/__main__.py` binds `127.0.0.1`, plain HTTP (`W0.md` focus area, still open) | TLS, a real deploy target, backups, monitoring | **W7** |
| 5 | Upload staging state round-trips through hidden base64 form fields (stateless, but size-bound and re-parsed twice) | Staged-upload rows in the app DB with expiry; confirm references a staging id | **W5** |
| 6 | A logged-in operator sees only *counts* at `/your-data` — no costed view of their own data exists, because no menu price is captured anywhere | Menu-price capture + the costed grid/dish detail over the tenant's own data | **W6** |
| 7 | `data/raw/` is flat and single-tenant; no `restaurant_id` anywhere in `schemas/seam.py` (CONTRACT forward note, W2) | Tenant-partitioned seam — a gated, cross-peer contract change | **W9** |
| 8 | `Co` provenance unresolved: the engine's overage cost is a hand-typed `config/items.yaml` placeholder because the seam can't reconstruct a plate cost (CONTRACT forward note) | The derived `food_cost` seam leg, written from the on-ramp's own computation | **W6** |
| 9 | Name-based joins across the seam (`normalize_name()` defends them; CONTRACT forward note, issue #4) | Stable `item_id` carried across the seam | **W6/W9** |
| 10 | `price_observations.parquet` accumulates forever, no retention policy (`W3.md`) | Recorded retention/versioning policy with the ops story | **W7** |
| 11 | The only public surface is the sample-data demo grid at `GET /` — there is no storefront a prospect can find on their own; vision §5's design direction and rule 06's responsive + WCAG-AA mandates have never had a scheduled pass | The public storefront + design & accessibility pass | **W8** |

Nothing in this table is a defect — each was the correct thin choice for its phase, recorded as
deferred. The service review's conclusion is simply that **the deferrals now have a schedule.**

---

## 2. Target state (what "fully fledged" means here)

A hosted website where a restaurant operator can:

1. **Have an account** — sign in with their own credentials, reset a password, exist as a real user
   row attached to a real restaurant row, with their session state maintained across restarts.
2. **See their own numbers** — the costed grid, dish detail, and opportunities computed from *their*
   captured data (not the sample dataset), which requires capturing the one input the PoC never
   asked for: menu prices.
3. **Keep feeding it without ritual** — the existing capture funnels (POS export, recipes, invoices),
   now staging through the app DB, still writing the engine's legs through `schemas/` to `data/raw/`.
4. **Trust it** — the transparency surfaces (W4), export *and deletion* of their data, TLS, CSRF,
   and tenant isolation enforced in the backend.
5. **Coexist** — a second restaurant can onboard without seeing or corrupting the first. **Not yet
   true as of W5:** the app DB gained real multi-restaurant tenancy machinery, but `data/raw/` stays
   global/unpartitioned until W9 — so a second restaurant today would read and write the *same* seam
   files as the first (demonstrated live by `/review-web W5`, `docs/phase_decisions/W5_review.md`
   BLOCKER-1). W5 therefore fences `create_account` to exactly one restaurant; the fence lifts only
   when W9 lands physical seam partitioning, at which point this line becomes true.
6. **Be met as a stranger** — a public storefront a prospect can find and judge without us in the
   room, designed to vision §5's direction, responsive and accessible per rule 06 (W8).

The engine's contract is unchanged throughout: it still reads exactly the `data/raw/**` legs and
nothing else.

---

## 3. The two-store architecture (the designated database)

This is the load-bearing design decision of the whole map. The service gets a **second store**, and
the two stores have non-overlapping jobs:

```
                    ┌───────────────────────────────┐
   operator ──────► │  on-ramp web service          │
                    │                               │
                    │  APP DB (new, on-ramp-private)│   users, restaurants, credentials,
                    │  SQLite → Postgres            │   sessions, staged uploads, menu
                    │  via ONRAMP_DATABASE_URL      │   prices, audit log
                    │                               │
                    │  confirmed captures only      │
                    │  ▼ through schemas/seam.py ▼  │
                    └───────────────┬───────────────┘
                                    │  one-way seam (unchanged)
                            data/raw/**  (Parquet + DuckDB query layer)
                                    │
                              forecasting/  (reads raw only; never sees the app DB)
```

**The application database (the "designated database").**
- **What it holds:** everything that is *user/operational* data rather than an engine input —
  accounts, restaurants (tenants), credential hashes, sessions, staged uploads awaiting
  confirmation, menu prices and the ingredient/dish catalog as the operator maintains it, audit
  events. This is data the seam was never designed to carry and must never carry.
- **Technology, designated:** SQLAlchemy + Alembic migrations from day one; **SQLite** as the
  engine first (embedded, zero-ops, transactional — the same thin-store discipline as
  DuckDB-over-Parquet), behind `ONRAMP_DATABASE_URL` (env-configured, rule 07; default a local
  gitignored file, **never under `data/`** — `data/` is the platform seam, owned by neither peer).
  The **swap to Postgres is a connection-string + migration change executed in W7** if and when
  hosted concurrency demands it — that is the "server-class DB" decision rules 05 and
  `common_base_reconciliation.md` §6.6 explicitly deferred to a recorded moment; W7 is that
  recorded moment.
- **Ownership:** on-ramp-private. `forecasting/` never reads it, never knows it exists; it is not
  part of the seam and adds **no** new coupling between the peers.

**The seam (unchanged in role).** `data/raw/**` remains exactly what `data/CONTRACT.md` says: the
only engine input, the firewall, written only through `schemas/`. DuckDB stays its query layer.

**The three laws of the two-store split:**
1. **User data never crosses the seam.** No account, credential, session, or billing fact ever
   lands in `data/raw/` — the engine has no business with it.
2. **Engine inputs never live *only* in the app DB.** A captured leg isn't captured until it is
   validated through `schemas/` and written to `data/raw/`. The app DB may stage or mirror it for
   the UI; the seam file is the artifact of record for the engine.
3. **Derived values flow app → seam through the same gate.** When W6 writes the `food_cost` leg,
   it is computed from app-DB inputs but crosses into `data/raw/` through a `schemas/` definition
   like every other leg — one source of truth, never re-typed.

**Initial app-DB schema sketch** (the W5 build decides finally; this fixes the shape, not the DDL):
`restaurants` · `users` · `memberships` (user↔restaurant, role) · `credentials` (argon2 hash,
reset tokens) · `sessions` (revocable) · `staged_uploads` (payload, kind, expiry — replaces the
hidden-field round-trip) · `dishes` / `menu_prices` (the operator-maintained catalog, priced) ·
`audit_log` (logins, seam writes, exports, deletions).

---

## 4. The phase ladder (W4 → W10)

W0–W3 are built and reviewed. W4 is unchanged from the vision's §8 map; W5–W10 are new. Each row is
a separate gated phase — do **not** batch them. "Trigger" marks phases that should wait for a
real-world signal rather than being built on spec.

| Phase | Slice | Delivers | Durable vs. provisional | Trigger |
|---|---|---|---|---|
| **W4** | Transparency + bridge *(as already planned)* | The full "your data" transparency view and the forecasting "what's next" panel. | Durable framing, provisional content | none — next in line |
| **W5** | **The designated app DB + real identity** | Stand up the application database (SQLAlchemy + Alembic, SQLite, `ONRAMP_DATABASE_URL`). Users, restaurants, memberships, argon2 credentials, password reset, revocable sessions; the env-credential and `RESTAURANT_ID = "default"` retired; staged uploads move into the DB. Invite-only account creation until hosted (no public signup on localhost). `create_account` is fenced to exactly one restaurant (`docs/phase_decisions/W5_review.md` BLOCKER-1) — `data/raw/` stays global until W9, so a second tenant cannot yet coexist safely; the fence lifts when W9 lands. | **Durable** (survives any product swap) | none — the foundation for "maintain user data" |
| **W6** | The costed reveal over the tenant's own data | Menu-price capture into the app DB (the one missing input); the grid, dish detail, and opportunities computed from the operator's *own* captured legs + prices, replacing counts-only `/your-data` and the sample-only value surfaces; the derived **`food_cost` seam leg** written through a new `schemas/` definition (closes the `Co`-provenance forward note in `data/CONTRACT.md`); stable `item_id` introduced app-side. | Mixed — plumbing durable, plate-cost views provisional | none — this is the biggest dollar-legible unlock and the reason a tenant returns |
| **W7** | Production hosting + security hardening | TLS, real deploy target, per-request CSRF tokens, managed persistent secrets, rate limiting on the funnels, backups (app DB + `data/raw/`), monitoring/structured logs, the price-history retention policy, real email transport for password-reset links (redacting the W5 stopgap that logs the raw reset token server-side — `docs/phase_decisions/W5_review.md` LOW-2 — the moment this lands), and the **recorded Postgres decision** (execute the swap iff hosted concurrency demands it). Closes the W0/W2 pre-deploy bundle. | **Durable** | the first remote user / pilot deploy |
| **W8** | **The public face** (storefront + design & accessibility pass) | The public storefront: a landing surface a prospect can find and judge without us in the room, making the site's own one-sentence pitch (vision §1) — with the sample grid kept inside it as the clearly-labeled live demo. The vision §5 design pass across every existing screen (calm, restaurant-appropriate, one accent reserved for "this is money"); responsive tablet/phone layouts and the WCAG-AA accessibility audit rule 06 mandates (kitchen-hostile defaults: contrast, semantics, keyboard); onboarding UX polish — the recipe-sitdown progress meter and visible "good enough to show value" threshold (vision §3A). Still server-rendered, no JS framework: a design-and-markup pass, not a stack change. The review closes on the rule-06 trust law — honest precision, reconciles-by-eye, labeled sample data, AA contrast on money figures — which a redesign can silently break. | **Durable** (the storefront and design system survive a product swap; only the screenshots and copy change) | same as W7 — the first remote user; build back-to-back with W7 so the site is presentable the day it is reachable |
| **W9** | Multi-tenancy across the seam | `restaurant_id` crosses the seam (per-tenant subdirectories or a column — decided then): a **gated, cross-peer `data/CONTRACT.md` change** coordinated with `forecasting/src/data/loader.py` and `forecasting/src/simulate/generator.py`; `src/store.py` and the capture writers become tenant-scoped; stable `item_id` carried into the seam schemas. Closes the W2 partitioning forward note. | **Durable** | a second *real* tenant's data needing to coexist |
| **W10** | Account completeness | Team access + roles (the `memberships` table earns its keep), profile management, data **deletion**/offboarding (export already exists — trust demands the reverse), billing scaffolding when there is something to bill. | **Durable** | validated demand (a second seat, a first invoice) |

**Ordering rationale.** W5 before everything because every later phase writes to or reads from the
app DB. W6 before hosting because it is pure value — the reason the site is a *living surface* an
operator returns to — and needs no infrastructure the PoC lacks. W7 gates on a real deploy because
hardening `127.0.0.1` is motion without progress. W8 shares W7's trigger and sits *after* W5/W6
deliberately: a design pass repaints every screen it touches, so it lands once the screens it
polishes exist — W4–W6 ship their surfaces functional under the existing styles, and the pass makes
them presentable to strangers exactly when strangers can first arrive. W9 gates on a second tenant
because partitioning a store that holds one restaurant is speculative — and it is the one phase
that touches both peers, so it must not ride along inside an on-ramp-only build. If discovery lands
a hosted pilot before menu prices matter to that pilot, W6 and W7/W8 swap — the ladder is a
dependency order, not a vow.

---

## 5. Invariants that do not move (any phase, any order)

1. **The seam law.** One-way flow `onramp/` → `data/raw/` → `forecasting/`; every seam write
   through `schemas/`; never `_truth/`, never `interim/`/`processed/`, never an import across the
   peers. The boundary tests must stay green through every phase above (`data/CONTRACT.md`,
   rules 05/07).
2. **Compute stays pure.** The app DB and the web layer are glue and storage; plate-cost math stays
   in `src/`, framework-agnostic and unit-tested. The website never becomes the only way to run a
   plate-cost.
3. **Honest precision.** Costed views from real tenant data obey the same discipline as the sample
   grid: rounded dollars, reconciles by eye, no margin claim the captured inputs can't support.
4. **Thin controllers, validation at the boundary, hostile-until-validated input, secrets in env**
   — rules 06/07 apply to every new route and every migration exactly as they applied to W1–W3.
5. **Dollars, not polish.** Each phase's review asks what an operator can now do that they couldn't
   — W5's answer is "exist as a real user," W6's is "see their own money," W8's is "a prospect can
   find and judge this without us in the room." A phase with no such answer is drift wearing
   infrastructure's clothes.
6. **Process.** Build freely; `/review-web` closes each phase on the code; `docs/progress_log.md`
   gets the entry; comprehension runs in parallel on `/learn` and gates nothing.

---

## 6. Decisions this overview records vs. defers

**Recorded here (2026-07-13):**
- The website goes from PoC to production service; this is on-ramp-function investment, sanctioned,
  not drift (Jay's directive).
- The service gets a **designated application database**, separate from the seam: SQLAlchemy +
  Alembic, SQLite first, env-configured, on-ramp-private, never under `data/`.
- The Postgres swap is scheduled as a W7 decision point — the previously deferred "server-class DB"
  decision now has its recorded moment (satisfying rule 05 and `common_base_reconciliation.md` §6.6).
- The two-store laws in §3 (user data never crosses the seam; legs aren't captured until they're in
  `data/raw/`; derived values cross through `schemas/`).

**Deferred to the phase that builds them (with their triggers, §4):**
- Exact app-DB DDL and the session mechanism details (W5).
- The `food_cost` schema definition and `item_id` format (W6, seam-side confirmed in W9).
- Hosting target, Postgres yes/no, retention policy specifics (W7).
- Storefront copy, the concrete visual design system, and whether the demo grid stays embedded on
  the landing page (W8).
- Column-vs-subdirectory tenant partitioning of `data/raw/` — a cross-peer `data/CONTRACT.md`
  amendment, never a unilateral on-ramp change (W9).
- The 86/stockout log's capture surface (the fourth leg) — still a deliberately separate tiny habit,
  not scheduled on this map; whether it ever becomes a website surface is a discovery question.

---

## 7. What this overview is not

- **Not a relocation of the moat.** Defensibility still lives in `forecasting/`. This map builds the
  rail to it — to production grade, because there is no path onto the engine that doesn't cross
  this bridge — but the engine remains the end.
- **Not a validation of plate-cost.** Discovery still decides the product in the slot. That is
  precisely why W5/W7/W8/W9/W10 are scoped to the durable chrome (identity, storage, hosting, the
  public face, tenancy, trust) that a product swap keeps, while the plate-cost-specific views stay
  swappable.
- **Not a license to batch.** Seven phases, seven reviews, seven log entries. The thin-first
  discipline survives the destination getting bigger.
