# Progress Log — platform milestones & decisions

A dated, append-only record of what has been built and what has been *decided* (with the reasoning,
or a pointer to the decision record). Distinct from `../docs_archive/ARCHITECTURE_REVIEW.md` (a
point-in-time audit, superseded and archived) and `CLAUDE.md` "Current status" (a thin live
snapshot): this is the running history. Newest first.

Convention: each entry is dated, tagged `[built]` / `[decided]` / `[gated]` / `[docs]`, and names the
artifacts touched. Decisions link their record rather than restating it.

---

## 2026-07-15 — W8 hardening: fixed all `W8_review.md` findings `[built]`

`/review-web W8`'s verdict was **"Yes"** — no blockers, but the reviewer flagged one real
regression (MINOR-1) and one honesty gap (MINOR-2) worth landing before this is shown to a real
stranger, plus 3 NITs. Jay greenlit all 5. `docs/phase_decisions/W8.md`/`W8_review.md` are left as
the frozen build-time/review-time record (same convention as the W4–W7 hardening entries); this
entry is the remediation record.

- **MINOR-1 — the global link restyle made inline prose links near-invisible.** `style.css`'s
  `a { text-decoration-color: var(--border); }` produced a ~1.3:1 underline — effectively gone,
  most consequentially on `success.html`'s post-save "set your menu prices / your dishes" CTA, the
  storefront's own guided next step at the highest-trust moment. Now uses `var(--text-muted)`
  (independently contrast-verified >5:1); hover strengthens to `var(--text)`.
- **MINOR-2 — the "good enough to show value" badge counted the wrong dishes.** It gated on
  `summary.dish_count` (raw BOM-distinct names), which can include a dish present in only one file
  (already surfaced separately as `only_in_bom`/`only_in_sales`) and therefore won't actually cost
  on `/dishes`. New `web/upload.py::build_summary` field `costable_dish_count` joins BOM ∩ sales on
  the same `normalize_name()` key `cross_reference_dishes` already uses — `confirm.html` now gates
  on that, not the inflated raw count. The displayed "Dishes" row is untouched (still the honest
  raw count).
- **NIT — `_progress_meter.html` had no fallback for a missing `step`.** An includer that forgot
  `{% set step %}` would 500 (Jinja's default `Undefined` raises on the `<` comparison). Now
  `{% set step = step | default(0) %}` degrades to every step reading as not-yet-reached instead.
- **NIT — a logged-in operator saw a contradictory "Log in" CTA in the hero.** `grid.html`'s hero
  now shows "Go to your dishes" instead when `logged_in` is true.
- **NIT — two test names claimed "every page" but only asserted against `GET /`.**
  `test_skip_link_present_on_every_page` and the focus-target test now also exercise `/login`.
- **Tests: 615 pass, up from 611** — 4 new (one per finding except the two NITs sharing the
  every-page test rewrite): `test_content_link_underline_is_a_visible_color_not_the_near_
  invisible_border_tint`, `test_progress_meter_partial_renders_safely_without_step_set`,
  `test_landing_page_shows_a_real_next_step_when_already_logged_in`,
  `test_confirm_page_threshold_ignores_dishes_that_only_appear_in_one_file` (reproduces MINOR-2:
  raw dish_count=3 but only 2 dishes match across files, so the badge must read not-met). `ruff
  check .`: clean. `lint-imports`: 2 contracts kept, 0 broken. Boundary test green.
- W8 is now done: build closed in the entry below, review closed on this entry — per
  `00-process.md`, no comprehension step required.

---

## 2026-07-15 — W8 built: the public face — storefront + design & accessibility pass `[built]`

Built `website_production_overview.md` §4's W8 slice: a public storefront making the site's own
one-sentence pitch (vision §1) with the sample grid kept embedded as a clearly-labeled live demo,
a keyboard/screen-reader accessibility pass (skip link, focus-visible rings, active-nav marking)
and a responsive breakpoint across every existing screen, and onboarding UX polish — a progress
meter + "good enough to show value" threshold on the sales+BOM capture funnel (vision §3A). Pure
presentation: no new routes, no new `src/` compute, no seam/schema changes. Full reasoning, load-
bearing assumptions, and design decisions: `docs/phase_decisions/W8.md`. Not marked done here —
per `00-process.md`, that happens when `/review-phase W8` (or `/review-web W8`) closes on the code.

- **`web/static/style.css`** — a new `--focus` token + global `:focus-visible` outlines on every
  interactive element; a `.skip-link` (visually hidden until focused); restrained link styling
  (underline-on-text-color, keeping `--money` the palette's only saturated accent per rule 06);
  `.hero`/`.progress-meter`/`.value-threshold` components; a 768px tablet breakpoint alongside the
  existing 480px phone one; nav `flex-wrap` for narrow viewports (no JS hamburger — the spec is
  explicit that this stays a markup pass, not a stack change).
- **`web/templates/base.html`** — a skip link to `id="main-content"` (`tabindex="-1"` so it's
  programmatically focusable); `aria-current="page"` on whichever nav link matches
  `request.url.path`.
- **`web/templates/grid.html`** — a new `<section class="hero">` above the existing sample grid
  carrying vision §1's pitch verbatim and two CTAs ("See the live demo" anchor, "Log in" — no
  "sign up" link exists since account creation is invite-only until W10); the grid itself now
  lives inside `<section id="live-demo">`, labeled "Live demo — sample menu."
  `GET /` stays the one public route — the hero was added to the existing template rather than
  splitting off a new landing route/page.
- **New `web/templates/_progress_meter.html`** — a shared 3-step onboarding indicator ("Connect
  your data" → "Review" → "Saved"), included (not duplicated) from `upload.html`, `confirm.html`,
  `success.html`.
- **`web/templates/confirm.html`** — the "good enough to show value" badge, gated on
  `summary.dish_count >= 3` (a documented, deliberately simple UI constant, not a `src/`
  computation — `summary.dish_count` is `web/upload.py::build_summary`'s existing BOM-distinct-
  dish count, already exactly "how far through the recipe-sitdown" a chef is).
- **`web/templates/success.html`** — fixed stale copy: it previously told the chef their own
  margin grid "arrives in a later phase," which stopped being true the moment W6 shipped
  `/menu-prices` + `/dishes`. Now points onward to both. Not in the original W8 punch-list
  verbatim, but squarely inside "the design pass across every existing screen" + rule 06 honesty.
- **Contrast verified, not changed.** Every color pairing already in the palette (money-on-
  white/bg, text-muted, all three tier badges, the sample-banner, `.btn-primary`'s white-on-money)
  was hand-checked against the WCAG relative-luminance formula — all pass AA with margin (tightest
  5.07:1 vs. a 4.5:1 floor). No token needed to change. No automated checker (axe/Lighthouse) was
  available in this environment to cross-verify the hand calculation — flagged as a reviewer focus
  area in `W8.md`.
- **Tests: 611 pass, up from 599** — 12 new in `tests/test_web_landing.py`: the hero pitch text
  and demo anchor render on `GET /`, the sample grid stays embedded and labeled, the skip link +
  `main-content` focus target are present on every page, `aria-current` marks the active nav link
  both unauthenticated (`/login`) and authenticated (`/invoice/upload`, plus proving a *different*
  nav link on the same render is NOT marked current), the progress meter renders on all three
  funnel steps with the right step `aria-current="step"` and prior steps `is-done`, the value-
  threshold badge flips at exactly 3 dishes (both directions tested), and `success.html` no longer
  claims the tenant grid "arrives in a later phase." `ruff check .`: clean. `lint-imports`: 2
  contracts kept, 0 broken. Boundary test green. Verified end-to-end via `TestClient(app)` (the
  real ASGI app, middleware stack, and Jinja templates) — a real socket-bound `python -m web` live
  smoke test was not run this session (blocked by the auto-mode classifier refusing to disarm
  W7's `ensure_safe_bind` guard without explicit authorization; see `W8.md` Constraints). No
  browser/screenshot tool was available to visually render the CSS — say so rather than claim a
  visual check that didn't happen.

---

## 2026-07-15 — W7 hardening: fixed all `W7_review.md` findings `[built]`

`/review-web W7`'s verdict was **"No, not as it stands"** — three MAJOR findings meant the hardening
bundle didn't yet do its job, even though every named artifact was present and the seam/layering
invariants held. All findings (3 MAJOR + 2 MINOR + 1 NIT) are fixed in this pass. `docs/phase_decisions/
W7.md`/`W7_review.md` are left as the frozen build-time/review-time record (same convention as the
2026-07-13 W4 hardening entry); this entry is the remediation record.

- **MAJOR-1 — the CSRF middleware buffered the entire request body in memory before any size/auth/
  token check.** `verify_csrf_request`'s `request.body()` priming call (needed to keep the body alive
  for downstream `Form(...)`/`UploadFile` dependencies — a real, separately-verified fix) ran
  unconditionally ahead of the route's own 700 KB size guard, so an unauthenticated caller with no
  valid CSRF token could force arbitrary-size in-memory buffering (reviewer verified: an 8 MB-per-file/
  16 MB upload — 23× the cap — was fully buffered, 56.1 MB peak heap, before the 422 ever fired).
  `web/csrf.py::CSRFMiddleware` now checks `Content-Length` against a 3 MB cap and 413s *before*
  `verify_csrf_request` is called at all — comfortably above the largest legitimate body (the two-file
  `/upload` route) but far below a hostile payload. A malformed/unparsable `Content-Length` is rejected
  the same way (hostile input, not guessed at).
- **MAJOR-2 — the reset-password route leaked account existence and 500'd under any SMTP failure.**
  `send_password_reset_email` raises (by design) when SMTP is configured but the send fails; with no
  try/except around it, that raise only happened when the account existed (a non-existent email never
  reaches the sender at all) — an unhandled 500 vs. a normal 200 is a textbook enumeration oracle,
  contradicting the route's own "identical response" comment. `web/app.py::reset_password_request_
  submit` now wraps the send in try/except: on failure it logs server-side with a correlation id and
  falls through to the exact same "submitted" response as every other path — without reverting to the
  W5 raw-token-in-logs fallback, which would have silently resurrected `W5_review.md` LOW-2 the moment
  SMTP looked configured.
- **MAJOR-3 — the rate limiter keyed on the proxy's IP under the phase's own recommended reverse-proxy
  deploy.** `_client_ip` read `request.client.host` (the TCP peer); with no proxy-header handling
  anywhere, every real visitor behind the recommended "reverse proxy in front of a loopback bind"
  topology would collapse onto the proxy's one address, throttling the 11th distinct chef in a minute
  while leaving a real attacker indistinguishable. New `web/config.py::trusted_proxy_ips()` reads
  `ONRAMP_TRUSTED_PROXY_IPS` (comma-separated, empty/unset by default); `web/rate_limit.py::_client_ip`
  now reads the first `X-Forwarded-For` entry *only* when the socket peer is in that allowlist,
  otherwise falls back to the socket peer exactly as before — so today's direct dev/test behavior is
  unchanged, and a real reverse-proxy deploy just has to name its own address.
- **MINOR — `RequestLoggingMiddleware` skipped the log line for any request that raised**, silently
  omitting exactly the failures a "monitoring" deliverable most needs to surface. `dispatch` now wraps
  `call_next` in try/except, logs method/path/duration at ERROR with status 500 on an exception, then
  re-raises so normal error handling (`ServerErrorMiddleware`, route-level try/except) still runs.
- **MINOR — `configure_logging`'s docstring promised stdout; bare `logging.StreamHandler()` defaults to
  stderr.** Now passes `sys.stdout` explicitly so behavior matches the documented contract.
- **NIT — `POST /reset-password/{token}` (token consumption) had no rate limit at all.** Added a
  `reset-confirm` bucket (budget 10/60s) alongside the existing four.
- **Tests: 599 pass, up from 591** — 8 new, one per finding except the two paired with the same fix
  (`test_oversized_post_is_rejected_before_the_body_is_buffered` + `test_reasonable_sized_multipart_
  upload_is_unaffected_by_the_size_guard` prove MAJOR-1 both ways; `test_reset_password_request_
  identical_response_when_smtp_configured_but_send_fails` reproduces MAJOR-2; `test_client_ip_ignores_
  forwarded_header_from_an_untrusted_peer` + `test_client_ip_reads_forwarded_header_only_from_a_
  trusted_proxy` prove MAJOR-3 both ways; `test_request_logging_middleware_logs_a_line_for_requests_
  that_raise` + `test_configure_logging_writes_to_stdout_not_stderr` cover the two MINORs;
  `test_reset_confirm_endpoint_429s_after_its_configured_budget` covers the NIT). All three fixes also
  verified live against a real `TestClient` run (not just the new unit tests) before being written up
  as permanent tests. `ruff check .`: clean. `lint-imports`: 2 contracts kept, 0 broken. Boundary test
  green.
- W7 is now done: build closed below, review closed on this entry — per `00-process.md`, no
  comprehension step required.

---

## 2026-07-14 — W7 built: production hosting + security hardening `[built]`

Built `website_production_overview.md` §4's W7 slice: per-request CSRF protection, rate limiting on
the funnels, structured logging, backup + retention mechanics, real SMTP for password resets, and TLS
*support* — the code and config that make a real deploy safe the day one happens, without provisioning
any actual cloud infrastructure or picking a hosting platform (no pilot deploy or platform choice
exists yet to encode). Full reasoning, load-bearing assumptions, and design decisions:
`docs/phase_decisions/W7.md`. Not marked done here — per `00-process.md`, that happens when
`/review-phase W7` closes on the code.

- **New `web/csrf.py`** — a stateless double-submit-cookie `CSRFMiddleware`, applied to every
  state-changing route with no exemptions. Closes the `same_site="lax"`-only placeholder
  `docs/phase_decisions/W2_review.md` MINOR-3 flagged. Every POST template gained a hidden
  `csrf_token` field via `_nav_context`. Hit and fixed a real Starlette `BaseHTTPMiddleware` gotcha
  mid-build: reading `request.form()` in middleware silently empties the body for every downstream
  `Form(...)`/`UploadFile` dependency unless `request.body()` is read first (see `W7.md` Constraints);
  verified fixed with a live multipart upload through the real middleware, not just unit tests.
- **New `web/rate_limit.py`** — an in-process fixed-window limiter on `POST /login` (anti-brute-force),
  `POST /reset-password`, `POST /upload`, and `POST /invoice/upload` (the funnels), independent budgets
  per client IP per route.
- **New `web/observability.py`** — JSON-structured logging (`configure_logging`, called from
  `web/__main__.py`, deliberately not at import time so `caplog`-based tests are unaffected) plus a
  `RequestLoggingMiddleware` logging method/path/status/duration for every request. Verified live via a
  real programmatic `uvicorn.Server` HTTP round trip after an unrelated shell-output-capture quirk in
  this dev sandbox made two earlier smoke-test attempts misleadingly look silent.
- **New `web/config.py`** — `ONRAMP_ENV`-driven production posture in one place: `is_production()`
  (the session + CSRF cookies are now `Secure` in production, was hardcoded `False`),
  `ensure_production_config()` (fails fast at startup if `ONRAMP_ENV=production` is missing
  `ONRAMP_DATABASE_URL`/`ONRAMP_SMTP_HOST`), and `resolve_tls_files`/`ensure_safe_bind` (refuses to
  bind past loopback with no TLS material configured — `web/__main__.py` now enforces this).
- **New `src/email/sender.py`** — real SMTP (stdlib `smtplib`, no new dependency) for the
  password-reset link; `web/app.py` now only logs the raw reset token when SMTP isn't configured at
  all, closing `docs/phase_decisions/W5_review.md` LOW-2 ("a reset token ... must not survive to any
  shared/hosted environment"). An SMTP failure with a host configured raises rather than silently
  falling back to logging, so a misconfigured production deploy fails loudly.
- **New `src/pricing/retention.py` + `scripts/apply_retention.py`** — a 400-day retention policy for
  the ever-accumulating `price_observations.parquet` leg (production-overview row 10), always keeping
  the latest observation per ingredient regardless of age so the grid never silently loses its only
  price for an ingredient. A periodic maintenance script, deliberately not run inline on
  `/invoice/confirm`.
- **New `scripts/backup.py`** — snapshots the app DB (SQLite's own online backup API, not a raw file
  copy) and every file under `data/raw/` into `ONRAMP_BACKUP_DIR/<timestamp>/`. Local-disk mechanics
  only; shipping off-box is a real deploy's job (needs infra credentials this environment doesn't
  have).
- **New `Dockerfile`** — a generic, platform-agnostic container image, the "real deploy target"
  artifact without committing to a specific unvalidated hosting platform.
- **Deliberately not built:** the Postgres swap (recorded as "iff hosted concurrency demands it" —
  none exists yet), any platform-specific deploy config, actual TLS certificate provisioning, and a
  scheduler for the two new ops scripts — see `W7.md` Explicitly Deferred for the complete list and
  why each waits on a real pilot deploy or platform choice rather than being invented here.
- **Tests: 591 pass, up from 531** — 60 new: `test_web_csrf.py` (10, overrides conftest's new autouse
  CSRF bypass to test the real enforcement end-to-end, including a live multipart-upload regression
  test for the body-caching fix), `test_rate_limit.py` (6), `test_pricing_retention.py` (9),
  `test_email_sender.py` (6), `test_backup_script.py` (10), `test_web_config.py` (14),
  `test_web_observability.py` (4), plus 1 SMTP-integration test appended to `test_web_auth.py`.
  `conftest.py` gained two autouse fixtures (`_bypass_csrf_by_default`, `_reset_rate_limits`) so none
  of the 46 pre-existing `client.post(...)` call sites across five test files needed editing. `ruff
  check .`: clean. `lint-imports`: 2 contracts kept, 0 broken. Boundary test green. Also smoke-tested
  live: `python -m web`, `scripts/backup.py`, and `scripts/apply_retention.py` all run as real CLI
  processes against isolated tmp state.

---

## 2026-07-14 — W6 hardening: fixed all `W6_review.md` findings `[built]`

`/review-web W6`'s verdict was **"No"** — a BLOCKER: the grid and the dish-detail page showed a
*different* plate cost and margin for the same dish, because two independently-rounded
implementations of the same formula disagreed. Jay greenlit every finding. `docs/phase_decisions/
W6.md`/`W6_review.md` are left as the frozen build-time/review-time record (same convention as the
W5/W4 hardening entries); this entry is the remediation record.

- **BLOCKER-1 + MAJOR-2 — grid/detail cost divergence, fixed at the root.** `web/dishes.py::
  build_dish_detail` re-implemented the plate-cost formula a third time, rounding each ingredient
  line to the $0.25 grid THEN summing — not distributive, so a multi-ingredient dish's total could
  silently inflate (reproduced: a $0.32 real dish showed $0.00 summed-from-rounded-lines vs. $0.25
  rounded once, on the aggregate). New `src/costing/tenant_grid.py::build_dish_line_items` is now
  the one shared function both the grid (via `dish_ingredient_cost`) and the detail page draw
  from: per-line costs at real cents (an honest audit trail), the displayed total rounded ONCE on
  the raw aggregate — the two screens are now structurally guaranteed to agree for the same dish.
- **MAJOR-1 — `/your-data` now discloses the `food_cost` leg.** W6 started writing
  `data/raw/food_cost.parquet` to the engine but never updated the transparency page, so
  `menu_prices.html`'s "see your data for what we send the forecasting engine" pointed at a page
  that omitted it. Added `store.read_food_cost()`, a fourth ledger row (dish count only — never
  the menu price itself), and a CSV export at `/your-data/export/food_cost`.
- **MINOR — food-cost % could contradict its own tier label at the boundary.** The displayed
  percent was rounded for display but the tier was binned from the unrounded fraction (e.g. "25%
  (strong)" when the chef's own rule says <25% is strong, 25–35% is "ok"). New
  `src/report/grid.py::food_cost_pct_display` rounds once; both the shown number and the tier bin
  now read off that same rounded value.
- **MINOR — the `food_cost` leg went stale after an invoice-driven price change.** Recompute was
  tied only to the menu-price save action. Extracted `web/menu_prices.py::
  recompute_and_write_food_cost`, now called from both the menu-price save and
  `invoice_confirm_submit` (best-effort/non-blocking on the invoice path — no consumer reads this
  leg yet, so a recompute failure must never fail the invoice confirmation itself). `data/
  CONTRACT.md`'s Co-provenance note updated to name both triggers.
- **LOW — a stale `food_cost.parquet` was never cleared when zero dishes were costable.** New
  `clear_food_cost()` removes the file instead of silently leaving a prior snapshot when a
  recompute yields no rows.
- **MINOR — a dish rename could silently collapse two catalog rows to one price.**
  `Dish` is unique on the exact name, joined to the seam by the normalized name — a collision now
  resolves deterministically to the most-recently-updated price
  (`menu_prices_by_seam_key` orders the query by `updated_at`), not an arbitrary query order.
- **NIT — validation errors now name the dish, not its internal seam key** ("Caesar Salad: ..."
  instead of "caesar salad: ..."). **NIT — `build_grid`'s stale `UUID`-only type hint widened** to
  `UUID | str`, matching what the tenant path actually passes.
- **Tests: 531 pass, up from 521** — 10 new: 5 in `test_costing_tenant_grid.py` (`build_dish_
  line_items` reconciles with the grid / shows real-cent per-line precision / degrades honestly on
  a missing price, plus `clear_food_cost` removes-existing and no-op cases); 1 multi-ingredient
  reconciliation test in `test_web_dishes.py` (the fixture the bug actually breaks — the prior
  single-ingredient test structurally couldn't catch it); 2 in `test_web_invoice.py` (recompute on
  confirm, and a no-BOM-yet no-op); 1 in `test_web_menu_prices.py` (stale-file clearing); 1 in
  `test_costing_menu_prices.py` (normalize-collision resolution). `ruff check .`: clean.
  `lint-imports`: 2 contracts kept, 0 broken.
- W6 is now done: build closed in the entry below, review closed on this entry — per
  `00-process.md`, no comprehension step required.

---

## 2026-07-14 — W6 built: the costed reveal over the tenant's own data `[built]`

Built `website_production_overview.md` §4's W6 slice: menu-price capture into the app DB (the one
seam input the PoC never asked for), the real-tenant popularity×margin grid and dish detail
replacing `/your-data`'s counts-only view, and the derived `food_cost` seam leg that closes
`data/CONTRACT.md`'s long-open "Co provenance" forward note. Full reasoning, load-bearing
assumptions, and design decisions: `docs/phase_decisions/W6.md`. Not marked done here — per
`00-process.md`, that happens when `/review-phase W6` closes on the code.

- **New app-DB table `dishes`** (`onramp/plate_cost/src/db/models.py::Dish`,
  `migrations/versions/0002_add_dishes_table.py`) — the operator-maintained menu-price catalog,
  keyed `(restaurant_id, dish_name)`. Menu price itself never crosses the seam (the two-store
  laws); its UUID primary key is the "stable `item_id` introduced app-side"
  `website_production_overview.md` §6 calls for — carrying it into the seam schemas is W9's job.
- **New seam schema `FoodCostRow`** (`schemas/seam.py`) — `dish_id, dish_name, food_cost,
  computed_at`. Deliberately carries no `menu_price` (user/operational data stays app-DB-only);
  the cost math itself doesn't need one either — `Co` is pure ingredient cost.
- **New package `src/costing/`** — `menu_prices.py` (DB-aware catalog upsert/read, no FastAPI
  import) and `tenant_grid.py` (pure compute: `build_tenant_grid` reuses W3's
  `dish_ingredient_cost` + the existing `report/grid.py::build_grid` rather than forking a third
  cost-summing implementation; `build_food_cost_rows` + `write_food_cost_atomic` derive and
  full-replace-write the new leg, reusing `seam_upload._stage_parquet`'s atomic-write primitive).
- **Web layer:** `GET/POST /menu-prices` (save a price; also recomputes + writes
  `data/raw/food_cost.parquet` — "one recipe-confirmation act feeds two products," now also true
  of one menu-price save) and `GET /dishes` + `GET /dishes/{dish_id}` (the real-tenant grid and
  line-by-line ingredient breakdown), all login-gated, calm-fallback error handling matching every
  sibling route. A dish missing a price or a costable ingredient is named as unpriced, never
  dropped silently.
- **Deliberately deferred:** `/insights` (W3) does NOT gain a margin/food-cost-tier claim this
  phase, even though menu prices now exist — W3's own regression tests structurally guard against
  exactly that (`hasattr`-based, not just behavioral), and lifting them correctly deserves its own
  scoped review rather than riding inside this already-large phase. See `W6.md` Explicitly
  Deferred for the full list (engine-side `Co` consumption, `store.read_food_cost()`, menu-price
  history — none built this phase).
- **Tests: 521 pass, up from 473** — 48 new across `test_costing_menu_prices.py` (8),
  `test_costing_tenant_grid.py` (10), `test_web_menu_prices.py` (10), `test_web_dishes.py` (10),
  `test_seam_schemas.py` (+6 `FoodCostRow` cases), plus `test_db_engine.py`'s expected-table set
  and `test_web_auth.py`'s protected-routes list extended (+4 parametrized cases). `ruff check .`:
  clean. `lint-imports`: 2 contracts kept, 0 broken. Boundary test green.

---

## 2026-07-14 — W5 hardening: fixed all `W5_review.md` findings `[built]`

`/review-web W5`'s verdict was **"No (not yet)"** — a BLOCKER: real multi-restaurant account
creation shipped over a still-global `data/raw/`, so the reviewer created two accounts, seeded the
shared store with Restaurant A's data, and logged in as B to read *and export* A's BOM. Jay
greenlit every finding, choosing the reviewer's own "thinner, W5-appropriate" option for the
BLOCKER — fence single-tenant now, do the real cross-peer seam partitioning on schedule at W9 —
over pulling W9's `data/CONTRACT.md` amendment forward unilaterally. `docs/phase_decisions/W5.md`/
`W5_review.md` are left as the frozen build-time/review-time record (same convention as the
2026-07-13 W4 hardening entry); this entry is the remediation record.

- **BLOCKER-1 — cross-tenant leak, fenced.** `src/auth/service.py::create_account` now raises
  `ValueError` if any `Restaurant` row already exists — a real DB constraint, not an unenforced
  convention, so "exactly one tenant" holds until W9 partitions the seam. Verified live against a
  real migrated SQLite file (not just the unit test): a second `create_account` call is rejected
  with a named error instead of silently creating a second tenant that reads/writes the first
  one's `data/raw/` files. `website_production_overview.md` §2.5 and the W5 phase-ladder row were
  corrected — they had claimed W5 already let a second restaurant coexist safely, which the
  reviewer's live reproduction disproved.
- **MINOR-1 — login timing enumeration.** `authenticate()` returned instantly on an unknown email
  without ever running argon2, so an attacker could distinguish "email exists" from "email doesn't"
  by latency even though the response message was identical. `src/auth/credentials.py` now carries
  a fixed `DUMMY_PASSWORD_HASH`; `authenticate()` verifies against it on the absent-user path so
  both branches pay the same KDF cost.
- **MINOR-2 — migration/ORM drift guard was table-names-only.** The whole suite built its schema
  via `Base.metadata.create_all`, never the actual Alembic migration, and the one test that did run
  the migration checked table names only — a dropped column or constraint could drift silently.
  Added `test_migrated_schema_matches_orm_metadata_exactly` (`tests/test_db_engine.py`), which runs
  `alembic upgrade head` against a throwaway DB and asserts `compare_metadata` returns an empty diff.
- **MINOR-4 — the decision log misdescribed the shipped code.** `docs/phase_decisions/W5.md` claimed
  `require_login`/`current_identity` let a DB error propagate to a 500; the shipped
  `web/auth.py::_identity()` actually catches `SQLAlchemyError` for all three call sites uniformly
  (a DB outage fail-closes to `/login`, not a crash) — the *safer* behavior, but the opposite of
  what the record said. Corrected in place (struck through + annotated, not silently rewritten) so
  a future reader isn't misled into "fixing" a propagation path that never existed.
- **LOW-1 — staged-upload consume was check-then-set.** `src/capture/staging.py::take_staged_upload`
  now claims a row with one atomic `UPDATE ... WHERE consumed_at IS NULL`, checking `rowcount`
  instead of reading `consumed_at` then writing it in a separate step — closes a genuine concurrent
  double-submit TOCTOU (an invoice's price rows are appended, not replaced, so a raced double-take
  would have duplicated them). Proven with real threads/real sessions against a dedicated
  busy-timeout'd SQLite engine (`test_take_staged_upload_is_atomic_under_concurrent_race`): 8
  concurrent callers, exactly 1 winner, every run.
- **LOW-2 — reset-token-in-logs, tracked forward.** Kept as-is for localhost (correctly never in the
  HTTP response), but now explicitly named in `website_production_overview.md`'s W7 row and
  `W5.md`'s Explicitly Deferred table so it can't be forgotten once real email transport or remote
  logging exists.
- **LOW-3 — SQLite foreign keys were declared but not enforced.** `src/db/engine.py::build_engine`
  now runs `PRAGMA foreign_keys=ON` on every SQLite connection via a `connect` event listener.
  `test_build_engine_enables_sqlite_foreign_key_enforcement` proves an orphaned `Membership` insert
  now raises `IntegrityError` instead of silently succeeding.
- **NIT — `reset_password`'s self-contradicting docstring** ("cleared on success either way")
  reworded to state plainly that only the success path clears the token.
- **Tests: 473 pass, up from 468** — 5 new (`test_create_account_rejects_a_second_restaurant`,
  `test_authenticate_unknown_email_still_pays_argon2_cost`,
  `test_migrated_schema_matches_orm_metadata_exactly`,
  `test_build_engine_enables_sqlite_foreign_key_enforcement`,
  `test_take_staged_upload_is_atomic_under_concurrent_race`). `ruff check`: clean. `lint-imports`:
  2 contracts kept, 0 broken.
- W5 is now done: build closed in the entry below, review closed on this entry — per
  `00-process.md`, no comprehension step required.

---

## 2026-07-14 — W5 built: the designated app DB + real identity `[built]`

Built `website_production_overview.md` §4's W5 slice: a real on-ramp-private application database
(SQLAlchemy + Alembic, SQLite via `ONRAMP_DATABASE_URL`) replaces W2's single env-configured operator
credential and the `RESTAURANT_ID = "default"` placeholder. Full reasoning, load-bearing assumptions,
and design decisions: `docs/phase_decisions/W5.md`. Not marked done here — per `00-process.md`, that
happens when `/review-web W5` closes on the code.

- **Six new tables** (`onramp/plate_cost/src/db/models.py`, one Alembic migration
  `migrations/versions/0001_initial_schema.py`): `restaurants`, `users`, `memberships`,
  `credentials` (argon2id hash + a single pending reset token), `sessions` (revocable, DB-listed),
  `staged_uploads` (payload/kind/expiry). `audit_log`, named in the production overview's schema
  sketch, is deliberately not built — nothing reads or writes one yet.
- **Real identity replaces the env credential.** `src/auth/credentials.py` now hashes passwords with
  argon2id (was a deterministic SHA-256 placeholder); `src/auth/service.py` is the new DB-aware layer
  (`create_account`, `authenticate`, `create_session`, `resolve_session`, `revoke_session`,
  `request_password_reset`, `reset_password`) that `web/auth.py` calls. Login/logout, `/your-data` and
  every other protected route, and the nav's `logged_in` flag all move onto this — 9 call sites in
  `web/app.py` gained a `db: Session = Depends(get_db)` dependency.
- **Sessions are DB-backed and revocable, not client-signed.** Starlette's `SessionMiddleware`
  (itsdangerous) is retired entirely; the cookie now carries only an opaque random token, hashed and
  looked up against the `sessions` table on every request. Logout revokes the row server-side — a
  presented stale cookie no longer authenticates, which a signed-cookie scheme could never guarantee.
  This also resolves the W2→W5 "ephemeral session secret" forward note in the production overview more
  completely than persisting `ONRAMP_SESSION_SECRET` would have: there is no signing secret left to
  manage at all.
- **Staged uploads move server-side.** `/upload` and `/invoice/upload` used to round-trip the raw
  uploaded bytes back to the browser as base64 hidden form fields; `src/capture/staging.py`'s
  `stage_upload`/`take_staged_upload` now persist that payload in `staged_uploads` and hand the client
  back only an opaque id, single-use and expiring after 30 minutes. `/confirm` and `/invoice/confirm`
  still fully re-validate whatever they find staged (rule 07) — the mechanism changed, the
  never-trust-the-round-trip discipline didn't.
- **Invite-only account creation + password reset.** `scripts/create_account.py` (a `getpass`-gated
  CLI, the only account-creation path — there is still no public `/signup` route) is the whole
  "invite" act. `GET`/`POST /reset-password` and `GET`/`POST /reset-password/{token}` are new routes;
  W5 has no email transport yet, so the reset link is written to the server log rather than sent
  anywhere — recorded as a deliberate, honestly-scoped gap, not an oversight.
- **Two build-time bugs worth flagging for the reviewer:** SQLite silently round-trips a plain
  `DateTime` column as timezone-naive even when a timezone-aware value was written, which broke every
  session/token-expiry comparison until every `_utcnow()` in this phase's new modules was made
  naive-but-UTC consistently; and Alembic's `env.py` calling `fileConfig()` with its default
  `disable_existing_loggers=True` silently disabled `web.app`'s logger for the rest of the process the
  first time a test ran a migration in-process, breaking an unrelated `caplog`-based assertion later in
  the same suite run — fixed with `disable_existing_loggers=False`. Both are recorded in
  `docs/phase_decisions/W5.md`'s Constraints section.
- **Tests: 468 pass, up from 434** — net +34 across four new test files
  (`test_auth_service.py`, `test_staging.py`, `test_db_engine.py`, `test_create_account_script.py`)
  plus `test_auth_credentials.py`, `test_web_auth.py`, `test_web_upload.py`, `test_web_invoice.py`
  rewritten for the new identity/staging contracts (exact per-file deltas in the decision log).
  `ruff check`: clean. `lint-imports`: 2 contracts kept, 0 broken. Boundary test green. Also
  smoke-tested live over real HTTP (migrate → create an account → start the server → exercise
  `/`, `/login`, `/your-data`, `/reset-password`) before tearing the process down.

---

## 2026-07-13 — W4 hardening: fixed all `W4_review.md` findings `[built]`

`/review-web W4`'s verdict was **"Yes, with one MAJOR to fix first"** — the transparency page
contradicted itself in a reachable state. All findings — the MAJOR plus one MINOR and one LOW (both
NITs also addressed) — are fixed in this pass, closing out the review. `docs/phase_decisions/W4.md`/
`W4_review.md` are left as the frozen build-time/review-time record (same convention as the
2026-07-06 W3 hardening entry); this entry is the remediation record.

- **MAJOR-1 — "only invoices captured" rendered a self-contradicting trust page.** The price-leg
  ledger row, counts, and export link were all nested inside `{% if summary.has_data %}` (BOM+sales
  only), so an operator who'd uploaded invoices but not yet BOM/sales saw "Nothing captured yet" while
  the always-shown firewall paragraph above it claimed we held their invoice prices — and the operator
  couldn't export the data they *had* given us. `your_data.html`'s outer gate is now
  `{% if summary.has_data or summary.has_price_data or summary.price_leg_error %}`, with each of the
  three legs (BOM, sales, price history) rendering its own connected/not-connected state
  independently in the ledger and its own conditional export link — no leg's presence is any longer
  collapsed into a single combined flag. The bridge panel stays gated on `has_data` specifically
  (its copy is a claim about sales history + recipes, which invoices alone don't satisfy).
- **MINOR-1 — no calm-fallback wrapper on `/your-data`; a corrupt price leg could 500 the whole
  trust page.** Went beyond the reviewer's minimal suggestion: `_price_leg_stats()`
  (`web/your_data.py`) now catches any read failure beyond `FileNotFoundError` and returns a new
  explicit `price_leg_error` state — the page shows "Temporarily unavailable" for that one leg,
  honestly distinct from "not connected yet," while BOM/sales and the rest of the page render
  normally. `your_data()` and `your_data_export()` (`web/app.py`) also gained the same
  try/except → calm error (503 + correlation id / legible message) every sibling route already
  has, as defense-in-depth for anything unexpected in the BOM/sales path.
- **LOW-1 — the `_truth` boundary grep was `.py`-only, and W4 was the first phase to put firewall
  prose in a template.** `tests/test_module_boundaries.py` now also scans `onramp/**/*.{html,css,js}`
  (`_web_asset_files()`), deliberately excluding docs/markdown since governance files legitimately
  name the hidden-oracle path in prose to describe the rule itself.
- **NITs — trust-section `<h2>`s no longer use the muted `.page-meta` utility** (titles read as
  titles, not fine print, matching `insights.html`'s bare-`<h2>` convention); **bridge-panel copy**
  now reads "validated against simulated test data" rather than the more confident "validated on test
  data," matching the platform's own standing caveat on simulation figures.
- **Tests: 434 pass, up from 429** — 5 new (`test_your_data_shows_price_leg_and_export_when_only_
  invoices_captured` reproduces MAJOR-1 and proves the fix; `test_your_data_degrades_price_leg_
  without_crashing_when_price_file_corrupt` and `test_export_prices_returns_503_not_a_crash_when_
  price_file_corrupt` reproduce MINOR-1 on both the page and export routes; `test_your_data_returns_
  calm_503_when_bom_read_fails_unexpectedly` covers the route-level wrapper; `test_web_asset_scan_
  would_catch_a_truth_reference_planted_in_a_template` proves LOW-1's new glob actually catches a
  planted violation in a synthetic tree). `ruff check`: clean. `lint-imports`: 2 contracts kept, 0
  broken. Boundary test green (4 checks, `.py` + web-asset scan).
- W4 is now done: build closed above (entry below), review closed on this entry — per
  `00-process.md`, no comprehension step required.

---

## 2026-07-13 — W4 built: transparency + bridge (`/your-data` deepened) `[built]`

Built `website_vision.md` §8's W4 slice: `/your-data` deepens from W2's counts-only state into the
full transparency view, plus the new forecasting "what's next" bridge panel. Both landed as sections
on the existing page rather than a new route — a design judgment call, flagged for review. Full
reasoning, load-bearing assumptions, and design decisions: `docs/phase_decisions/W4.md`. Not marked
done here — per `00-process.md`, that happens when `/review-web W4` closes on the code.

- **Three-leg ledger.** `/your-data` now enumerates all three captured seam legs — BOM, sales, and
  the invoice/price-history leg W3 added but W2's page never picked up. `web/your_data.py` gained
  `_price_leg_stats()` (row/ingredient counts, read independently of whether BOM/sales exist — the
  invoice funnel has its own timing) and `export_price_observations_csv()`; CSV export
  (`/your-data/export/{leg}`) gained a `"prices"` leg, closing a real gap (export previously covered
  only 2 of 3 captured legs).
- **The firewall, in plain English.** A new "What we never touch" section explains the raw-data vs.
  hidden-testing-lab split and today's one-tenant honesty (login-gated, not yet physically
  partitioned — W9), shown unconditionally since it's static trust content, not gated on captured
  data (rule 06: transparency is a first-class surface).
- **The "what this unlocks next" bridge panel.** Describes the engine's prep-quantity mechanism
  honestly, without citing any of the simulation-only dollar figures as this operator's numbers and
  stating plainly the engine hasn't run on real data yet — the same anti-overclaiming discipline
  `/insights` already applies to price-move estimates.
- **Mid-build catch:** the structural boundary check greps for the literal `_truth` substring in
  comments too, not just code paths — an early docstring draft ("raw/`_truth` firewall") tripped it;
  reworded to "hidden-oracle firewall" language throughout.
- **Tests: 429 pass, up from 422** — 7 new/changed in `test_web_auth.py` (price-leg ledger + export
  coverage, the firewall/bridge-panel presence checks, the auth-redirect parametrize list extended
  for the new export leg) plus repointing one test whose "unknown leg" example became a real leg.
  `ruff check`: clean. `lint-imports`: 2 contracts kept, 0 broken. Boundary test green.

---

## 2026-07-13 — On-ramp website: PoC → production execution map approved `[decided]`

Jay directed that the on-ramp website graduate from the W0–W3 proof of concept to a fully fledged
service with a **designated application database maintaining real user data**, and named it
explicitly *not drift* — it is investment in the durable on-ramp function (capture funnel, storage,
identity, trust) the platform charter already sanctions. The decision record is
**`onramp/plate_cost/docs/website_production_overview.md`** (new); this entry links it rather than
restating it (per this log's convention). In brief:

- **Two-store architecture recorded:** a new on-ramp-private **app DB** (SQLAlchemy + Alembic,
  SQLite first via `ONRAMP_DATABASE_URL`, Postgres decision scheduled at the hosting phase — the
  "server-class DB" moment rules 05 / `common_base_reconciliation.md` §6.6 deferred) for users,
  restaurants, credentials, sessions, staged uploads, menu prices, audit log. The seam
  (`data/raw/**`, DuckDB-over-Parquet) is unchanged in role: still the only engine input, still the
  firewall. Laws: user data never crosses the seam; a leg isn't captured until it's in `data/raw/`
  through `schemas/`; derived values (the future `food_cost` leg) cross through the same gate.
- **Phase ladder extended W5–W10** (W4 transparency + bridge unchanged from `website_vision.md` §8):
  W5 app DB + real identity → W6 menu-price capture + costed views over the tenant's own data +
  the derived `food_cost` seam leg (closes the `Co`-provenance forward note) → W7 hosting +
  security hardening (trigger: first remote user; closes the W0/W2 pre-deploy bundle) → W8 the
  public face (storefront + the vision-§5 / rule-06 design & accessibility pass; same trigger as
  W7, built back-to-back with it) → W9 seam-level multi-tenancy (trigger: second real tenant;
  cross-peer `data/CONTRACT.md` change) → W10 team/roles/deletion/billing. Each is a separate
  gated phase with its own `/review-web`.
- **Docs touched:** `website_production_overview.md` (new), pointers added in
  `plate_cost_overview.md`, `website_vision.md` §8, and `onramp/plate_cost/CLAUDE.md` (web-stack
  paragraph). No code changed; nothing is built yet — W4/W5 are the next build slices.

---

## 2026-07-06 — W3 hardening: fixed all `W3_review.md` findings `[built]`

`/review-phase W3`'s verdict was **"No — not yet"** on one MAJOR (a bare 500 on `GET /insights`);
all findings — the MAJOR plus four MINORs and one LOW — are fixed in this pass, closing out the
review. `docs/phase_decisions/W3.md`/`W3_review.md` are left as the frozen build-time/review-time
record (same convention as the 2026-06-29 post-P0 hardening entries below); this entry is the
remediation record.

- **MAJOR-1 — `GET /insights` bare 500 on a non-convertible unit pair.** `BomRow` doesn't restrict
  `recipe_unit`/`canonical_unit` to the convertible set, so a stray pair (e.g. `each` -> `g`) made
  `src/bom/units.py::convert` raise straight through the route. Two-layer fix: `dish_ingredient_cost`
  (`src/insights/opportunities.py`) now catches that `ValueError` and drops the dish the same way it
  already drops one with a missing price (not a fabricated partial cost); `GET /insights`
  (`web/app.py`) also gained the same try/except -> `error.html` + correlation id + 503 every
  sibling route already has, as defense-in-depth.
- **MINOR-2 — headline hardcoded "this week" regardless of the real gap.** `price_trend`
  (`src/pricing/trends.py`) now carries `current_observed_date`/`prior_observed_date` through to
  `Opportunity.days_span`; the headline says "this week" only when the gap is plausibly one
  (<=10 days), else states the real span ("over the last 46 days").
- **MINOR-3 — prior/new dish costs read as historical fact, not the ceteris-paribus estimate they
  are.** `insights.html` now leads with the delta (`.delta-figure`, the money accent) and labels the
  absolute figures "est. ... other ingredients held at today's price," with a one-line caption on
  the card explaining why.
- **MINOR-4 — "N dishes affected" silently undercounted when a dish had an unpriced/unconvertible
  sibling ingredient.** `Opportunity` gained `uncosted_dish_count`; the headline now states the true
  total dishes the BOM says use the ingredient, with a "(k not yet fully priced)" note when the
  costed count is smaller, instead of quietly reporting only the costed subset.
- **MINOR-5 — concurrent-writer lost update on `price_observations.parquet`.** The read-modify-write
  in `write_price_observations_atomic` (`src/capture/invoice_upload.py`) is now serialized by a
  per-file `fcntl.flock` advisory lock (POSIX-only; fine for this repo's Darwin-dev/ubuntu-CI
  reality) around the whole read-combine-write-rename sequence, not just the final rename.
- **LOW-1 — two independent `_RAW_DIR` constants (read vs. write) that had to be monkeypatched
  separately.** `src/store.py`'s `RAW_DIR` is now the ONE canonical definition; `seam_upload.py`
  re-exports it (`from ..store import RAW_DIR as RAW_DIR`) instead of computing its own copy, and
  `web/app.py`'s write routes call `store.RAW_DIR` directly instead of keeping a module-level alias.
  One test (`test_invoice_upload_flags_ingredient_not_in_bom`) that previously needed two
  independent patches to stay isolated now needs one.
- **LOW-2 (provenance drill-down), LOW-3 (POS-absorption gate skip), LOW-4 (tenant scoping)** are
  unchanged — the review itself judged these acceptable to defer (to W4, to the still-pending
  competitive check, and to the existing W2 multi-tenant deferral, respectively); nothing here
  removes them from `W3.md`'s Explicitly Deferred table.
- **Tests: 406 pass, up from 400** — 6 new (`test_dish_ingredient_cost_excludes_dish_with_
  unconvertible_units`, `test_opportunity_headline_shows_real_span_when_older_than_a_week`,
  `test_opportunity_headline_notes_uncosted_dishes`, `test_insights_survives_non_convertible_unit_
  without_crashing`, `test_insights_unexpected_failure_returns_legible_error`,
  `test_write_price_observations_atomic_serializes_concurrent_writers` — the last one verified
  against a real regression: with the lock temporarily neutralized, the same test reproduces the
  lost update it guards against). `ruff check .`: clean. `lint-imports`: 2 contracts kept, 0 broken.

---

## 2026-07-05 — P4 review remediation: dollar gate never scored the go-forward window — corrected result PASSES, thinner than reported `[built]`

`/review-phase P4` (`docs/phase_decisions/P4_review.md`) found the P4 dollar gate's reported
$15,585.09/11.7% win was computed on a gate that never touched the go-forward/censored window at all —
the exact same fold-placement bug P3's own review found one phase earlier. Closed all 6 findings (1
MAJOR, 4 MINOR, 1 NIT); full evidence and reasoning: `docs/phase_decisions/P4.md` "Remediation" section
(this entry is the log pointer).

- **MAJOR-1 — the dollar gate's 4 folds all sat in spring 2022, never the 2024 go-forward/censored
  window.** `RollingOriginBacktest.run()` anchors every fold at the series START; on this ~2.5-year
  series that clustered all 4 folds far from the only window where P3's unconstraining does anything.
  Fixed via two new free functions in `backtest.py` — `min_train_weeks_reaching_tail` +
  `splits_with_full_tail_coverage` — the same fix `unconstrain_floor.py` already uses for the identical
  problem, applied here without touching `RollingOriginBacktest`'s own default behavior (so
  `point_floor.py`/`baseline_floor.py`'s already-logged numbers don't move). `newsvendor_floor.py` now
  runs its own manual per-fold loop against the end-anchored splits instead of calling
  `RollingOriginBacktest.run()` directly.
- **MINOR-3 — made_to_order items were getting a dish-count prep quantity.** Rule 04-deployment.md is
  explicit that the newsvendor-on-dishes math never applies to made_to_order items (they route to
  ingredient pars in Phase 7). New `decision.newsvendor.route_batch_items()` filters to the 7
  `prep_type=batch` items; `newsvendor_floor.py` now trains on the full 11-item signal but predicts/
  reports on batch items only.
- **MINOR-5 + MINOR-2 — calibration was a single tail holdout, pooled across items, with an unremarked
  upper-tail under-coverage.** `calibration.py` now refits across the same 4 end-anchored rolling-origin
  folds the dollar gate uses, adds a per-item underage-at-q* breakdown (rule 03), and `main()` prints an
  explicit caveat when upper quantile levels under-cover.
- **MINOR-4 — `expected_stockout`'s top-anchor truncation bias was undocumented.** Docstring now states
  the bias direction/magnitude explicitly; no math change (no operator-facing surface exists yet).
- **NIT — `critical_ratio` duplication.** Reviewer agreed with the original call; no action.
- **Corrected result: quantile+newsvendor $85,312.82 vs. point-model-as-mean $85,923.40 — the dollar
  gate PASSES, but by $610.58 (~0.7%), not the original $15,585.09 (~11.7%), and the newsvendor arm now
  wins only 2 of 4 folds (loses folds 2–3).** This is scored on batch items only, over folds that now
  correctly reach the series' true end (2024-06-30). Read honestly: the win is real but thin, not the
  decisive, all-folds-positive result originally reported — that result was never actually testing this
  window or this item set. Calibration still PASSES (worst pooled deviation ~0.105; MAPIE CQR 0.748 at a
  0.80 target); the new per-item breakdown surfaced real spread the old pooled number hid —
  `house_burger` and `ribeye_steak_12oz` both run meaningfully hotter (more real underage) than their own
  critical ratio predicts.
- **New regression tests: 316 → 353 (+37)** across `test_backtest.py` (+6), `test_newsvendor.py` (+3),
  `test_newsvendor_floor.py` (+1), `test_calibration.py` (net +3 after removing 2 dead tests for the
  superseded `_train_test_tail_split`). `make check`: lint clean, both import-linter contracts kept.
- P4 is now done: build closed 2026-07-04 (entry below), review closed on this entry — per
  `00-process.md`, no comprehension step required.

---

## 2026-07-05 — W3 built: insight & price (invoice capture, price trends, opportunities surface) `[built]`

Built `onramp/plate_cost/docs/website_vision.md` §8's W3 slice: a digital-feed invoice upload that
appends to a new, accumulating `price_observations.csv` seam leg, week-over-week price-trend
detection, and an "opportunities" surface reporting dollar-quantified findings from significant
ingredient price moves. Full reasoning, load-bearing assumptions, and design decisions:
`docs/phase_decisions/W3.md`. Not marked done here — per `00-process.md`, that happens when
`/review-phase W3` closes on the code.

- **Gate note:** `plate_cost/CLAUDE.md`'s POS-absorption competitive check (the gate in front of
  invoice ingestion) remains unresolved anywhere in the repo. Jay explicitly directed building this
  phase anyway ("skip the gate, build W3 as scoped") after the gate was surfaced — a recorded
  business decision, not a silent bypass. See `W3.md`'s Load-Bearing Assumptions.
- **New seam schema `PriceObservationRow`** (`schemas/seam.py`) — the invoice/price-history leg
  `data/CONTRACT.md` had already named but left unbuilt. Denormalized like `BomRow`: `ingredient_id`
  is name-derived (`normalize_name()`), not the CLI-internal UUID `PriceObservation` model uses, so a
  price observation joins to a recipe ingredient without a separate entity-resolution table.
- **New module `src/capture/invoice_upload.py`** — the digital-feed half of Phase 2's "invoice
  capture (photo + OCR, **or digital vendor feed**)"; deliberately does not touch `src/ingestion/`,
  which stays reserved (and untouched) for the heavier OCR + learned-mapping path behind the same
  gate. Reuses `seam_upload.py`'s parse/stage helpers rather than forking a copy. Unlike BOM/sales'
  full-replace model, writes **accumulate**: each confirmed invoice appends rows, de-duplicated and
  idempotent on `(ingredient_id, observed_date, unit_price, source_invoice)`.
- **New module `src/pricing/trends.py`** — pure pandas price-trend detection over the seam shape
  (`latest_price_per_ingredient`, `price_trend`, `significant_moves`), independent of
  `src/pricing/compute.py`'s UUID-keyed CLI models.
- **New module `src/insights/opportunities.py`** — the "opportunities" surface: dollar-quantified
  findings per significant price move, ranked by total dollar impact across affected dishes.
  **Deliberately reports an ingredient-cost delta only, never a margin/food-cost-tier claim** — the
  seam still carries no `menu_price` (the "Co provenance" forward note in `data/CONTRACT.md`, still
  not built), the same constraint that already kept `/` (W0) and `/your-data` (W2) from showing a
  costed view of real captured data.
- **Web layer:** `GET/POST /invoice/upload` + `POST /invoice/confirm` (the upload/confirm funnel,
  mirroring W1's shape) and `GET /insights` (the findings page), all login-gated; added to
  `test_web_auth.py`'s protected-routes list. `src/store.py` gained `read_price_observations()`.
- **Suite: 400 tests, 400 pass** (`make check`: lint clean, both import-linter contracts kept). Up
  from 342 — net +58 across `test_invoice_upload.py` (15), `test_trends.py` (11),
  `test_opportunities.py` (9), `test_web_invoice.py` (12), `test_web_insights.py` (6), plus additions
  to `test_store.py` (2) and 3 new parametrized cases in `test_web_auth.py`'s protected-routes list.

---

## 2026-07-04 — P4 built: distribution + the newsvendor turn `[built]`

Built `forecasting/docs/construction_roadmap.md`'s Phase 4 slice: a calibrated predictive distribution
per item (quantile regression), converted to a prep quantity via each item's newsvendor critical ratio,
plus waste/stockout as integrals of that distribution — "the product in miniature." Full reasoning, load-
bearing assumptions, and design decisions: `docs/phase_decisions/P4.md`. Not marked done here — per
`00-process.md`, that happens when `/review-phase P4` closes on the code.

- **New module `forecasting/src/models/quantile.py`** — `QuantileGBMModel`: one LightGBM quantile
  regressor (`objective="quantile"`, sklearn API) per requested level, global across items, mirroring
  `point.py`'s `GlobalLGBMModel` structure (same `FeaturePipeline`, same item_id-as-native-categorical
  boundary). Non-crossing enforced via post-hoc rearrangement (sort each row's predictions across the
  quantile axis) per rule 03. Uses the sklearn API (not `point.py`'s raw `Dataset`/`lgb.train()`)
  specifically because `evaluate/calibration.py`'s MAPIE wrapper requires it.
- **New module `forecasting/src/decision/newsvendor.py`** — pure policy math, zero model/data
  dependencies: `critical_ratio` (a deliberate local reimplementation of `objective.py`'s function of the
  same name — `decision/` is structurally forbidden from importing `evaluate/`, and extending the one
  existing import-linter carve-out for a one-line formula was judged a bigger change than duplicating it),
  `required_quantile_levels` (unions a standard grid with every item's own critical ratio, per rule 03's
  explicit "[0.10, 0.25, 0.50, 0.75, 0.90, q*]" requirement), `quantile_curve`/`prep_quantity` (the
  `F⁻¹(q*)` read-off, exact at each item's own critical ratio, interpolated elsewhere), and
  `expected_waste`/`expected_stockout` (trapezoidal integrals over the piecewise-linear quantile curve —
  hand-verified against the closed-form Uniform(0,100) newsvendor identities in `test_newsvendor.py`).
- **New module `forecasting/src/evaluate/calibration.py`** — the calibration checkpoint: empirical
  coverage per fitted quantile level + PIT values against `data/_truth/truth_demand.csv` (one of
  evaluate/'s sanctioned oracle readers), plus an INDEPENDENT MAPIE conformalized-quantile-regression
  (CQR) cross-check — fits its own from-scratch pair of models rather than reusing `QuantileGBMModel`'s
  fitted estimators, so a bug in the production model can't hide from the very check meant to catch it.
- **New module `forecasting/src/evaluate/newsvendor_floor.py`** — the dollar gate: `_NewsvendorAdapter`
  wraps `QuantileGBMModel` + the newsvendor read-off behind the existing `BaseBaseline` contract, so it
  drops into `RollingOriginBacktest` unchanged, scored against the Phase-2/3 point model used as the mean.
  Both arms train on the identical `unconstrain_demand(clean_demand())` target, so (unlike P3's
  `unconstrain_floor.py`) no oracle-anchored common ruler was needed — the harness's own shared `test_df`
  per fold already is one.
- **Verified against real generated data, not just synthetic fixtures:**
  - **Dollar gate PASS:** quantile+newsvendor **$117,536.08** vs. point-model-as-mean **$133,121.17** — a
    **$15,585.09** improvement (~11.7%), positive in all 4 folds. The point-as-mean total reproduces
    `forecasting/CLAUDE.md`'s previously-logged P2 point-model number exactly.
  - **Calibration PASS:** empirical coverage tracks nominal at all 19 fitted quantile levels (worst
    deviation ~0.09); PIT mean 0.499, std 0.323 (targets 0.5/0.289); independent MAPIE CQR check at
    confidence_level=0.80 gives empirical coverage 0.786.
- **New dependency:** `mapie` (conformal prediction) + `scikit-learn` (mapie's dependency; also the
  sklearn Estimator API `lightgbm.LGBMRegressor` implements) — both were commented-out placeholders in
  `requirements.txt` since P0, now promoted to real, installed dependencies. `requirements.lock.txt`
  regenerated.
- **Suite: 316 tests, 316 pass** (`make check`: lint clean, both import-linter contracts kept). Up from
  271 — net +45 across `test_newsvendor.py` (22), `test_quantile.py` (10), `test_calibration.py` (8),
  `test_newsvendor_floor.py` (5).

## 2026-07-04 — W2 review closed: 1 MAJOR + 4 MINOR findings addressed `[built]`

Closed the adversarial review of W2 (`docs/phase_decisions/W2_review.md`, verdict "Yes,
conditionally"). All 5 non-NIT findings greenlit by Jay; 3 were real code fixes, 2 were
already-correct deferrals confirmed/recorded rather than built early (Anti-Drift).

- **MAJOR-1 fixed** — `src/auth/credentials.py`'s `verify_credentials` fed the raw submitted
  username straight into `hmac.compare_digest`, which raises `TypeError` on any non-ASCII
  string, turning a login attempt with an accented username into a bare 500 instead of a clean
  401. Fixed by encoding both operands to UTF-8 bytes before the compare (bytes have no such
  ASCII restriction). Verified end-to-end: `POST /login {username:"café"}` now returns 401.
  Regression test added: `test_non_ascii_username_rejected_not_raised`.
- **MINOR-2 fixed** — `/your-data`'s period rendered as `2026-06-01 00:00:00` (a spurious
  midnight timestamp on the trust/transparency surface) because `SalesExportRow`'s pydantic
  `date` fields round-trip through Parquet/DuckDB as `datetime64` Timestamps. Fixed in
  `web/your_data.py` by routing through `pd.Timestamp(...).date()` before stringifying.
  Regression test added: `test_your_data_period_renders_as_plain_date_not_timestamp`.
- **MINOR-3 addressed proportionately** — the CSRF finding's own recommended fix was "no code
  change needed for the current local-only reality, gate a real token before deploy." Rather than
  building CSRF-token machinery a single-operator localhost tool doesn't need yet (Anti-Drift),
  made the one honest one-line change: `SessionMiddleware` now sets `same_site="lax"` explicitly
  in `web/app.py` (converting an implicit framework default into a stated decision) and the real
  per-request token is recorded as an explicit pre-deploy gate item in
  `docs/phase_decisions/W2.md`'s Explicitly Deferred table, alongside the existing TLS/session-
  secret item.
- **MINOR-1 (tenant isolation) and the ephemeral-session-secret finding** — both were already
  correctly deferred by the builder with the reasoning the reviewer endorsed; no code change,
  confirmed still accurately recorded in `data/CONTRACT.md` Forward notes and W2.md's Explicitly
  Deferred table respectively. Nothing to build now.
- Not addressed (Jay didn't greenlight it, and reviewer confidence was "near-zero risk"): the
  NIT on CSV formula-injection neutralization.
- **Suite: 297 tests, 297 pass** (`make check`: ruff clean, both import-linter contracts kept).
  Up from 295 — net +2 (`test_auth_credentials.py`, `test_web_auth.py`).

---

## 2026-07-04 — W2 built: account + persistence (session login, /your-data, DuckDB wired in) `[built]`

Built `onramp/plate_cost/docs/website_vision.md` §8's W2 slice: session-based login now gates the
capture funnel, and a new `/your-data` page is the web layer's first real caller of the
DuckDB-over-Parquet store (`src/store.py`), reading an operator's own captured seam data back with a
one-click CSV export. Full reasoning, load-bearing assumptions, and design decisions:
`docs/phase_decisions/W2.md`. Not marked done here — per `00-process.md`, that happens when
`/review-phase W2` closes on the code.

- **New pure module `src/auth/credentials.py`** (no FastAPI import — rule 05): `verify_credentials`
  checks a single operator username/SHA-256-password-hash pair configured entirely via
  `ONRAMP_AUTH_USERNAME`/`ONRAMP_AUTH_PASSWORD_HASH` env vars (rule 07 — secrets in env, never in
  code) and **fails closed** if either is unset. Deliberately a single credential, not a user table —
  nothing has validated a need for more than one operator account yet (see W2.md's decision log).
- **New `web/auth.py`** — `require_login(request)` returns a redirect to `/login` when the session
  (Starlette `SessionMiddleware`) isn't authenticated, else `None`; called at the top of every
  protected route, matching this codebase's existing manual early-return style rather than FastAPI's
  `Depends()` + exception pattern.
- **`web/app.py`**: wired `SessionMiddleware` (secret from `ONRAMP_SESSION_SECRET` or a per-process
  random fallback), added `GET/POST /login`, `POST /logout`, and gated `/upload` (GET+POST) and
  `/confirm` behind `require_login`. `GET /` stays public and unauthenticated on purpose — it shows
  only the shared illustrative sample grid (W0), never a tenant's real data, so there's nothing to
  isolate there and gating it would break the "show a client in 60s, no account needed" pitch.
- **New `web/your_data.py` + `/your-data`, `/your-data/export/{bom,sales}`** — the first web-layer
  caller of `src/store.py`'s `read_bom()`/`read_sales()`. Shows aggregate counts (dishes, recipe
  lines, sales rows, covers, period) read back from the operator's own captured seam data, with a
  graceful "nothing captured yet" state, and offers a one-click CSV download of each seam leg (the
  "your data is yours, no lock-in" transparency promise from `website_vision.md` §4). Does **not**
  show a costed margin grid from real captured data — the seam still carries no prices, so that
  remains `web/compute.py`'s sample-data job at `/` until a priced seam leg exists.
- **Single-tenant isolation, not a physical multi-tenant partition.** `data/raw/` stays flat and
  unpartitioned — isolation is enforced entirely at the auth layer (every data-bearing route requires
  a session), not by a `restaurant_id` column or per-tenant subdirectory. This matches
  `05-fullstack-architecture.md`'s "essentially single-tenant tool" framing and `website_vision.md`
  §9's explicit "not a mandate to build a multi-tenant platform now" — and avoids a unilateral,
  on-ramp-only change to a seam layout the forecasting engine's loader/simulator also hard-code flat.
  Recorded as a forward note in `data/CONTRACT.md` for when a second real tenant needs the seam
  partitioned. **Flagged as the phase's biggest architectural call — see W2.md Reviewer Focus Areas.**
- New dependency: `itsdangerous` (required by Starlette's `SessionMiddleware`), added to
  `requirements.txt`/`requirements.lock.txt` (mirrors the W1 `python-multipart` precedent).
- **Suite: 295 tests, 295 pass** (`make check`: lint clean, both import-linter contracts kept). Up
  from 271 — net +24 (`tests/test_auth_credentials.py` ×7, `tests/test_web_auth.py` ×17).

---

## 2026-07-02 — W1 review closed: MAJOR + 2 MINOR findings fixed `[built]`

Closed every actionable finding in `docs/phase_decisions/W1_review.md` (the web-reviewer's
adversarial pass on W1, verdict "Yes, with one MAJOR fix" — no BLOCKER). Full reasoning, code
pointers, and the two findings deliberately left unfixed (per the reviewer's own "none required"
call) live in `docs/phase_decisions/W1.md`'s new "Post-Review Remediation" section; this entry is
the log pointer.

- **MAJOR — the sample-data banner no longer renders over the operator's own captured data.** The
  review caught the confirm page showing "Sample data — illustrative only, not your restaurant's
  numbers" directly above the chef's real dish names and covers — the exact opposite of what the
  banner should ever claim about a page displaying real captured data. `base.html`'s banner is now
  an overridable `{% block sample_banner %}`; `upload.html`/`confirm.html`/`success.html` override
  it empty, `grid.html` needed no change. +1 test.
- **MINOR — `/confirm` now enforces its own upload-size policy instead of relying on an incidental
  framework limit.** The review found that `/confirm`'s hidden-field form (no `enctype`, so
  `application/x-www-form-urlencoded`) hits Starlette's default 1,048,576-byte-per-field cap before
  our own `MAX_UPLOAD_BYTES` check ever ran there — so a file under our stated 1 MB limit could pass
  `/upload` and then dead-end at `/confirm` with a raw framework JSON error. `MAX_UPLOAD_BYTES`
  lowered from 1,000,000 to 700,000 (base64-inflated, it now always stays safely under Starlette's
  cap), and the same size check now runs explicitly inside `confirm_submit` too — `/confirm` is
  directly POST-able and must not assume `/upload` already validated it. +2 tests, including a
  policy-invariant test that fails if the constant is ever raised without re-checking the math.
- **MINOR — the seam write is now jointly atomic across the bom/sales pair, not just per file.**
  The review reproduced a real mismatched-pair bug: failing the second `to_parquet` call mid-write
  left a freshly-committed `bom.parquet` paired with a stale `sales_export.parquet`. `write_seam_atomic`
  now stages both files to temp before renaming either into place, so a write failure can no longer
  leave a mixed old/new pair — only the (near-instant, two-syscall) gap between the two renames
  remains a window, down from the full duration of a DataFrame serialization. +1 test reproducing the
  review's exact repro, plus the existing atomicity test strengthened to check both files (it
  previously only checked one side and so hadn't caught this).
- **Left unfixed, per the reviewer's own call:** mutable-name-derived seam ids (explicitly "none
  required for W1," tracked under `data/CONTRACT.md`'s existing stable-item-id forward note) and two
  NITs (import-time `sys.path` mutation mirroring an existing deliberate pattern; row-number citation
  on multi-line CSV fields, correct for the realistic spreadsheet-editing case).
- **Suite: 253 tests, 253 pass** (`make check`: lint clean, both import-linter contracts kept). Up
  from 249 — net +4 across `test_seam_upload.py` and `test_web_upload.py`.

---

## 2026-07-02 — W1 built: self-serve capture funnel (POS upload + recipe confirmation) `[built]`

Built `onramp/plate_cost/docs/website_vision.md` §8's W1 slice: a chef can now upload a sales
export and a recipe (BOM) sheet through the browser, review a summary, confirm, and have both seam
legs written to `data/raw/` — no CLI run required. Full reasoning, load-bearing assumptions, and
design decisions: `docs/phase_decisions/W1.md`. Not marked done here — per `00-process.md`, that
happens when `/review-web W1` closes on the code.

- **New pure module `onramp/plate_cost/src/capture/seam_upload.py`** (framework-agnostic, no
  FastAPI import — rule 05): `parse_sales_csv()` / `parse_bom_csv()` validate an uploaded CSV
  against the existing `schemas/seam.py` (`BomRow`, `SalesExportRow`), accumulating **every** row
  error instead of failing fast on the first one; `cross_reference_dishes()` flags dish names
  present in one file but not the other (a likely typo, non-blocking — mirrors
  `report/grid.py`'s existing `covers_join_report` honesty pattern); `write_seam_atomic()` writes
  both Parquet files via temp-file-then-`os.replace` so a crash mid-write can never leave a
  truncated seam file (rule 07) — the first atomic-write helper in the repo. The self-serve BOM
  upload format is a flat sheet (`dish_name, ingredient_name, qty, recipe_unit, canonical_unit,
  yield_factor`); `dish_id`/`ingredient_id` are derived from the names via the grid's existing
  `normalize_name()`, not hand-authored UUIDs — a real simplification of the capture act versus the
  CLI's normalized 3-file model.
- **`src/run.py` refactored, not just extended:** `_export_to_raw` now builds its `BomRow`/
  `SalesExportRow` lists exactly as before but calls the new shared `write_seam_atomic()` to
  persist, instead of two bare `to_parquet()` calls. One writer, two producers (CLI + web) — the
  CLI gets atomicity for free and there is exactly one place that can drift on how the seam is
  persisted.
- **New web routes** (`onramp/plate_cost/web/app.py`): `GET/POST /upload`, `POST /confirm`. The
  upload→confirm handoff is fully stateless (rule 07) — no server-side session or staging directory;
  the confirm page round-trips the original uploaded bytes through base64-encoded hidden form
  fields, and `/confirm` **re-validates from scratch** rather than trusting the round-trip (tested).
  Oversized uploads (>1 MB, an invented-and-documented limit — no prior convention existed to reuse)
  are rejected before parsing. `web/upload.py` is the new thin presentation-glue sibling to
  `web/compute.py`. Three new templates (`upload.html`, `confirm.html`, `success.html`) plus a
  handful of new CSS rules in the existing `style.css`.
- **Deliberately honest gap, stated on the page itself:** `success.html` does not imply the grid at
  `/` now shows the just-uploaded data — it still doesn't (W0's `/` reads local sample CSVs, not
  the seam, by design). Wiring a tenant's own data back into a dashboard view is W2's job.
- **Verified against the real server, not just `TestClient`:** started `python -m web` and drove
  the full upload → confirm → save flow with `curl` against the live socket, confirmed the correct
  Parquet landed in `data/raw/`, then regenerated `data/raw/` from the CLI's sample data to leave it
  as found (`data/raw/*` is gitignored, regenerable output — not a durable-state concern).
- **Suite: 249 tests, 249 pass** (`make check`: lint clean, both import-linter contracts kept). Up
  from 222 — net +27 (`tests/test_seam_upload.py` ×17, `tests/test_web_upload.py` ×10). Added
  `python-multipart` (required by FastAPI for `UploadFile`/`Form`, previously absent from the repo
  entirely) to `requirements.txt` and `requirements.lock.txt`.

---

## 2026-07-02 — W0 review closed: all 6 findings addressed `[built]`

Closed every finding in `docs/phase_decisions/W0_review.md` (the web-reviewer's adversarial pass on
W0, verdict "Yes, with one caveat" — no BLOCKER/MAJOR). Full reasoning lives in that file and in
`docs/phase_decisions/W0.md`'s updated Explicitly Deferred table; this entry is the log pointer.

- **MINOR-2 — food-cost % now reconciles with the displayed rounded cost.** The card derived
  `margin_display` from the rounded `~Cost` (correct) but printed `food_cost_pct` from the *unrounded*
  cost, so the two numbers on the same card could disagree (Pan-Seared Salmon read "27%" against a
  ~Cost that computes to 26%; House Burger read "21%" against 20%). `src/report/grid.py`'s
  `_food_cost_tier` is now the public `food_cost_tier`, and `web/compute.py` derives both
  `food_cost_pct` and `food_cost_tier` from the same rounded `cost_q` used for `~Cost`/margin. +1 test
  (`test_food_cost_pct_reconciles_with_rounded_cost`).
- **MINOR-3 — web path now ports the CLI's covers-join honesty.** `web/compute.py` silently scored an
  unmatched menu dish 0 covers with no alert and dropped orphaned sales rows from the "covers on
  record" headline (both latent on the clean sample, real once W1 feeds dirty POS exports). Extracted
  the CLI's join-check (`src/run.py`'s old `_report_covers_join`) into a shared
  `src/report/grid.covers_join_report()` used by both the CLI (prints) and the web path (renders a
  `covers_warnings` banner beside the existing skipped-dish notice in `grid.html`). The "covers on
  record" headline now sums raw sales counts, not just sales attached to a costed, matched dish, so it
  can no longer understate the true total. +1 test
  (`test_covers_join_surfaces_mismatches_and_total_uses_raw_sales`).
- **NIT — `/openapi.json` no longer served.** `docs_url`/`redoc_url` were disabled but the machine-
  readable schema was still reachable by default; `web/app.py` now also passes `openapi_url=None`.
- **NIT — durable chrome decoupled from plate-cost copy.** `base.html`'s footer hard-coded
  plate-cost-specific text ("Margin = Menu − ~Cost", "$0.25") into the shell every future on-ramp
  product would inherit. `base.html` now exposes an empty `{% block footer %}`; the plate-cost copy
  moved into `grid.html`'s override.
- **MINOR-1 — "hosted" gap recorded, not built.** W0's page binds `127.0.0.1` only with no deploy
  artifact, unmet against §8's literal "hosted" wording. Judged W1/W2's problem (first point a real
  deploy target exists), not a W0 blocker — now an explicit row in `W0.md`'s Explicitly Deferred table
  instead of an unscheduled gap.
- **MINOR-4 — provenance drill-down recorded as scope, not a defect.** Rule 06 wants any displayed
  cost expandable to its recipe-line inputs; W0's "grid + dish list" slice doesn't do this, but
  `website_vision.md` §3 already schedules "Dish detail" as its own later surface. Recorded as an
  explicit deferred row in `W0.md` rather than left as a silent rule-vs-scope tension.
- **NIT — quadrant dollar-margin axis flagged as an open roadmap question, not edited.** Pre-existing
  Phase-0 property (`src/report/grid.py` classifies on absolute dollar margin, not food-cost ratio),
  out of W0's code scope but newly client-facing. Recorded in a new "Open Roadmap Question Carried
  Forward" section of `W0.md` for whoever next touches the grid's axis definition.
- **Suite: 222 tests, 222 pass** (`make check`: lint clean, both import-linter contracts kept). Up
  from 220 — net +2 in `onramp/plate_cost/tests/test_web.py`.


## 2026-07-02 — P3 review remediation: dollar gate's false failure was a measurement bug — corrected result PASSES `[built]`

`/review-phase P3` (`docs/phase_decisions/P3_review.md`) found the P3 dollar gate's reported
−$3,533.87 "regression" was a false negative, not a real result. Closed all 3 findings; full evidence
and reasoning: `docs/phase_decisions/P3.md` "Remediation" section (this entry is the log pointer).

- **BLOCKER-1 — `unconstrain_floor.py` scored its two arms against two different answer keys.** The
  clean arm was scored against `clean_demand()`'s capped actual; the unconstrained arm was scored against
  its own corrected actual. On the censored test days, that mechanically raised the bar for the
  unconstrained arm alone, fabricating a regression. Rewritten so both arms train on their own target
  (that's the point of the comparison) but are SCORED against one fixed ruler
  (`_oracle_actual`: `clean_demand()`'s observed series with observably-censored rows raised to their
  real `true_demand` from the oracle — sanctioned, `unconstrain_floor.py` lives in `evaluate/`).
  **Corrected result: popular-item dollar cost, clean $112,428.46 → unconstrained $110,928.54, a
  +$1,499.91 improvement — the dollar gate now PASSES.** Both halves of the phase's "done when" are
  legitimately met: recovered demand tracks truth on capped days (MAE 5.076 → 3.090) *and* popular-item
  dollar cost improves vs. Phase 2.
- **MINOR-1 — 2 of 66 observable censored rows fell outside every backtest fold.**
  `RollingOriginBacktest`'s week-granularity test windows left the last fold's end 2 days short of the
  series' true final date (2024-06-28 vs. 2024-06-30). Fixed surgically with
  `_splits_with_full_tail_coverage`, which extends only the LAST fold's test window to the series' true
  end, touching no other fold's boundaries. A first attempt instead trimmed days off the series' START so
  the fold math divided evenly — rejected after it shifted every fold's date boundaries and materially
  changed the dollar result along with the coverage (confirmed by reproducing the reviewer's own
  spot-check number, +$1,507.15, using the *old* fold placement — a fix for a 2-day tail gap should not
  perturb the other three folds, and the surgical version doesn't; the ~$7 gap between +$1,499.91 and
  +$1,507.15 is exactly the now-included tail days).
- **NIT-1 — stale MAE numbers.** `unconstrain.py`'s docstring and `P3.md` quoted "MAE 5.28 → 3.09,
  bias −5.08 → −1.70"; the real run shows 5.076 → 3.090, bias −5.076 → −1.699 (MAE must equal |bias| here
  since every capped error has the same sign — the original numbers were internally inconsistent).
  Refreshed in both places.
- **`forecasting/tests/test_unconstrain_floor.py` (new, +6 tests):** guards both fixes directly against
  regressing back — the ruler function takes no per-arm parameter (structurally can't diverge between
  arms again), a missing truth row raises loudly, and the tail-extension helper is asserted to leave
  every fold except the last byte-identical to `RollingOriginBacktest`'s own output.
- **Suite: 238 tests, 238 pass** (`make check`: lint clean, both import-linter contracts kept). Up from
  232 — net +6, all in `test_unconstrain_floor.py`.
- P3 is now done: build closed on `docs/progress_log.md` (2026-07-02 build entry below), review closed on
  this entry — per `00-process.md`, no comprehension step required.

---

## 2026-07-02 — P3: censored-demand unconstraining built — truth-check passes, dollar gate fails honestly `[built]`

`/build-phase P3` — recovers true demand on sold-out (censored) day-items so the point model's training
target stops silently understating popular dishes. Full reasoning, evidence, and the two open judgment
calls a reviewer should weigh in on: **`docs/phase_decisions/P3.md`**. Not marked done here — per
`00-process.md`, that happens when `/review-phase P3` closes on the code.

- **`forecasting/src/models/unconstrain.py` (new) — `unconstrain_demand(demand_df, min_history=8)`.**
  Fits a Negative Binomial (falling back to Poisson when the sample isn't overdispersed) via method of
  moments to each item's own uncensored history — expanding-window, strictly-prior-only, same
  shift-then-roll discipline `FeaturePipeline`'s lag features already use — then takes the **conditional
  expectation above the observed cap**, `E[D | D > cap]`, not the unconditional mean. That distinction is
  the whole result: a first version using the plain historical mean corrected essentially nothing (avg
  lift +0.00 across 66 real censoring events, because a censored day is by definition an above-average
  day, and averaging it with ordinary days regresses back toward typical). The tail-expectation version
  lifted the same 66 rows by an average of +3.38 and cut MAE against the hidden truth stockout log from
  **5.28 → 3.09** (bias −5.08 → −1.70). `max(observed, estimate)` enforces the one hard constraint
  structurally: a censored observation is a lower bound, recovery can only raise the target.
- **`forecasting/src/evaluate/unconstrain_check.py` (new)** — the phase's own literal checkpoint ("does
  recovered demand match truth_demand on truth_stockouts days?"), the second sanctioned oracle reader
  alongside `cleaning_check.py`. Scoped to the 66 of 713 true censoring events that were actually
  *observable* (go-forward window only — `eightysix_log.csv` isn't populated for historical dates, the
  "86-board reality" named in the roadmap's own Practices list) rather than diluting the check against
  the ~90% of censoring history no method can see. **PASS.**
- **`forecasting/src/evaluate/unconstrain_floor.py` (new)** — the dollar gate: point model trained (and
  scored) on the unconstrained target vs. Phase 2's clean target, on the items that actually sold out.
  **FAILS, honestly reported, not hidden:** popular-item cost $102,050.21 (clean) → $105,584.08
  (unconstrained), a $3,533.87 regression. The script's own fold-decomposition shows this is concentrated
  entirely in the (fold, item) windows that actually contain a censored test day — consistent with
  `GlobalLGBMModel` being a mean-seeking point forecast asked to hit a now-honestly-higher target on a
  right-skewed spike day, exactly the limitation Phase 4's quantile/newsvendor read-off exists to close
  ("a point forecast can't produce the right prep quantity," construction_roadmap.md Phase 4). Verified
  directly that scoring the same predictions against the old, still-capped actual makes the number look
  better but is the wrong comparison — it would charge overage for correctly predicting demand that was
  genuinely there. **Left as a flagged, unresolved tension for `/review-phase P3`, not papered over.**
- **Fold-placement bug caught mid-build, not shipped:** `RollingOriginBacktest.splits()` anchors every
  fold at the *first* date of whatever series it's given, not a sliding recent window. On this project's
  ~2.5-year data, `point_floor.py`-style default fold placement only ever scores 2022-03-26..2022-07-15 —
  nowhere near the observable censored window (2024-04-05..2024-06-30). Before catching this,
  `unconstrain_floor.py` silently reported a **0.00 "improvement"** (identical dollar cost to the cent —
  the two training targets never differed inside any scored fold). Fixed locally inside
  `unconstrain_floor.py` (`_min_train_weeks_reaching_tail`, a dynamic fold-placement helper) rather than
  touching the shared `backtest.py` harness, which `baseline_floor.py`/`point_floor.py`/`day_ahead_eval.py`
  already cite numbers against. Worth knowing: `point_floor.py`'s own "$133,121.17" is therefore scored
  entirely on 2022 data and never touches a single censored row, clean or corrected.
- **`.claude` firewall note:** the substring-scan boundary test (`test_module_boundaries.py`) flagged the
  literal string `_truth` inside `unconstrain.py`'s own docstring — written while *explaining* that the
  module never touches the hidden ground-truth store. Reworded to match `cleaner.py`'s existing
  "oracle"/"hidden ground-truth store" vocabulary. A real, if slightly ironic, catch.
- **`forecasting/tests/test_unconstrain.py` (new, +12 tests):** hand-computed correctness (fine-grain and
  coarse-fallback cases, each independently re-derived via scipy rather than calling the module's own
  helper), Poisson-fallback and extreme-cap edge cases, cold start, the `recovered >= observed` structural
  invariant across a randomized series, reproducibility, and `test_correction_is_prefix_stable` — proves
  a row's correction is a function of only its own past by construction, not just by inspection.
- **`requirements.txt`:** comment updated — scipy is now a *direct* dependency (the NegBin/Poisson fit),
  not just lightgbm's transitive one.
- **Suite: 232 tests, 232 pass** (`make check`: lint clean, both import-linter contracts kept). Up from
  220 — net +12, all in `test_unconstrain.py`.

---

## 2026-07-02 — P2 review remediation: dollar-gate evidence committed + comp-exclusion bug found & fixed `[built]`

Closed all 7 findings in `docs/phase_decisions/P2_review.md` (the phase-reviewer's adversarial pass on
P2). Full detail, evidence, and code pointers live in that file and in the module docstrings/rule
edits it references; this entry is the log pointer.

- **BLOCKER-1 — the dollar gate is now a committed, runnable artifact, not a review-time ad hoc
  check.** `forecasting/src/evaluate/point_floor.py` runs `GlobalLGBMModel` through the same
  `RollingOriginBacktest` as the three baselines and asserts the win; `forecasting/src/evaluate/
  cleaning_check.py` (the second sanctioned `_truth/` reader) verifies the cleaned demand series is
  closer to ground truth than raw. `forecasting/tests/test_point.py` (+5 tests) covers the fit/predict
  contract and a non-regression backtest guard.
- **Found while building the truth check, not part of the original review: `cleaner.py`'s
  comp-exclusion was actively wrong.** Comp-flagged rows tag real, fulfilled guest orders (comped on
  the bill after the kitchen prepped and served them) — not phantom demand like staff meals. Excluding
  them moved observed demand *further* from `_truth/truth_demand.csv` (MAE 0.522 vs. 0.472 raw) because
  observed demand is already censored at or below the true series, so removing any real-demand subset
  can only widen that gap. Fixed: `cleaner.py` now excludes only voids + staff meals; comps stay in
  (MAE 0.302). This also corrects the stale claim in the 2026-06-30 backfill entry below and in the old
  `CLAUDE.md` "Current status", which described `point.py` as the three baselines — it is
  `GlobalLGBMModel` (global LightGBM Poisson). `.claude/rules/01-data-ingestion.md`'s "Restaurant-
  Specific Signal Cleaning" section updated to match (previously said "tag and exclude comps").
  Dollar floor moved with the corrected cleaning: clean floor $147,584.42 (was $144,789, computed on
  the over-stripped series); point model still wins clean, $133,121.17 (a $14,463.25 margin).
- **MAJOR-3 — lag-feature skew in the block backtest documented, not silently left implicit.**
  `RollingOriginBacktest` scores a whole test window in one `predict()` call, so lag features deep in
  the window are mostly NaN (symmetric across baselines and the GBM, so the dollar comparison stays
  fair — see `point.py` docstring). Added `FeaturePipeline.extend_history()` (+2 tests) and
  `forecasting/src/evaluate/day_ahead_eval.py`, a non-gating diagnostic that replays the real
  day-ahead regime (reveal each day's actual before scoring the next): lag fill rate goes from ~4-25%
  to 100%. Restructuring the shared backtest harness itself was judged out of scope for a remediation
  pass (Anti-Drift).
- **MINOR-4 — censored tag now scoped to `service_period`.** Was keyed on `(date, item_id)` only, so a
  dinner 86 wrongly censored that day's lunch row too. Now derives `service_period` from `time_86d`
  the same way `loader.py` does for POS sales. +1 test (`test_dinner_86_leaves_lunch_uncensored`).
- **MINOR-5 — two rule-01 requirements added to `cleaner.py`:** a missingness report (null count/% per
  column, printed before any exclusion) and a qty==0-with-no-void/comp-flag quarantine (a data-quality
  anomaly, not censored demand — no numeric effect on demand values, since such a row already
  contributed 0 to the aggregate; this closes an observability gap). +3 tests.
- **MINOR-6 — `GlobalLGBMModel.fit()` now logs rule-03 diagnostics:** a per-item predicted-vs-actual
  mean table (`self.item_bias_`) and feature importances (`self.feature_importances_`), the check that
  would surface censored-row contamination as per-item bias. MLflow logging stays parked (premature
  infra). +1 test.
- **NIT — dtype convention (Python `date`/object-dtype ids vs. rule 01's `datetime64`/`Categorical`
  letter) recorded as deliberate in `.claude/rules/01-data-ingestion.md` rather than refactored — no
  measured correctness or perf cost, internally consistent across every consumer.**
- **Suite: 220 tests, 220 pass** (`make check`: lint clean, both import-linter contracts kept). Up
  from 209 — net +11 across `test_point.py`, `test_features.py` (`extend_history`), and `test_cleaner.py`
  (comp/censoring/data-quality cases).

---

## 2026-07-02 — Backfill: W0 (read-only reveal) was built but never logged or reviewed `[built]` `[backfilled]`

`/build-phase W0` was invoked to build the on-ramp's first web phase; exploration found it **already
built** — `onramp/plate_cost/web/` (FastAPI app, Jinja2 templates, static CSS) exists, matches the
`website_vision.md` §8 W0 spec, and its test suite passes. Like the 2026-06-30 P1/P2 backfill, this
landed in the squashed `a66f85a` initial commit (2026-06-30) from work actually done earlier — the
only prior trace is an oblique "2026-06-25 W0 hardening pass" mention in this log's 2026-06-29 entry.
No `docs/phase_decisions/W0.md` existed and `/review-web W0` has never run. Jay chose to backfill the
missing artifacts rather than rebuild working code.

- **What's built:** `web/app.py` — single `GET /` route, sync handler (blocking I/O runs in
  FastAPI's threadpool), calm 503 + correlation-id on failure (no stack trace to the client).
  `web/compute.py` — thin glue running the same chain as `src/run.py` (`src/bom/loader.py` →
  `src/pricing/compute.py` → `src/report/grid.py`) against local `onramp/plate_cost/data/sample_*.csv`
  — **not** the seam (`data/raw/`), because the seam carries only BOM+sales and can't reconstruct
  margins. `web/templates/{base,grid,error}.html` — server-rendered Jinja2, no JS framework, sample-data
  banner, quadrant grid, dollar figures rounded to the $0.25 grid with margin derived from the
  *rounded* cost (rule 06 reconciliation discipline). `web/__main__.py` — `python -m web`, binds
  `127.0.0.1:8000` only.
- **Tests: 10/10 pass** (`onramp/plate_cost/tests/test_web.py`) — 200 status, quadrant sections
  present, dollar figures, sample banner, margin-reconciles-with-rounded-cost, static file reachable,
  empty `skipped` on clean data, `DishRow` contract match, legible 503 on simulated failure,
  uncostable dish surfaced not dropped (not silently dropped). `ruff check` clean. Full-repo
  `make test`: 209 passed (unchanged — no code was added).
- **Boundary firewall holds:** `tests/test_module_boundaries.py` already `rglob`s all of `onramp/`,
  so `web/` is covered — no `forecasting/` import, no `_truth` path.
- **Gap flagged, not fixed:** no deployment/hosting artifact exists anywhere (no Dockerfile, no prod
  ASGI config) despite the spec calling W0 "a single hosted page" / "show a client in 60s." Not
  recorded as deferred to any later phase — an open question for `/review-web W0` to weigh in on.
  Full reasoning, design decisions, and load-bearing assumptions: **`docs/phase_decisions/W0.md`**
  (itself a reconstructed, not contemporaneous, decision log — flagged as such in its own Reviewer
  Focus Areas).
- Not marked done here — per `00-process.md`, that happens when `/review-web W0` closes on the code.

---

## 2026-06-30 — Documentation-relevance review: `docs_archive/` created `[docs]`

Read every authored doc in the repo (~31 files across `docs/`, `forecasting/docs/`,
`onramp/plate_cost/docs/`, and the root/module `CLAUDE.md`/`README.md`s — `.claude/rules|agents|commands`
excluded as live config, not historical record) and assessed each for whether it still governs current
work or has already been absorbed elsewhere. Result: only 2 of ~31 had actually served their purpose;
this repo's non-redundant-by-design doc discipline means almost everything found is either an active
governance file, an open backlog/spec, or a directly cross-referenced authoritative source.

- **`ARCHITECTURE_REVIEW.md` → `docs_archive/ARCHITECTURE_REVIEW.md`.** A 2026-06-22 audit whose own
  header already marks its core recommendation superseded; the adopted decision is now fully captured
  in `CLAUDE.md`, `../onramp/README.md`, `../data/CONTRACT.md`, and `common_base_reconciliation.md`.
- **`progress_log_archive.md` → `docs_archive/progress_log_archive.md`.** Already-archived entries
  (2026-06-25 and earlier); relocated so there's one archive location instead of two.
- **`docs_archive/README.md` (new)** — explains why each archived file was retired and points back to
  its current authority, same convention as every other folder's index doc.
- Repointed this file's two references to the new paths (the intro line and the "older history"
  pointer below).

No code or governance content changed — a pure documentation-hygiene pass, so the Comprehension
Contract gate did not trigger (mechanical, per `00-process.md`'s carve-out).

---

## 2026-06-30 — Project-state snapshot from a workflow audit `[audit]`

A full audit of the agentic workflow (recorded in `docs/agentic_workflow/current_state.md`) also
exercised the actual codebase along the way. Project-state facts it surfaced, captured here since
they're product status, not workflow status:

- **Suite: 164 tests, 163 pass / 1 FAIL** in the `restaurant-dev` conda env.
- **Known failing test:** `forecasting/tests/test_features.py::test_lag_7_equals_same_weekday_last_week`
  — a leakage-adjacent lag-7 test, currently red. Flagged as an open issue in
  `forecasting/docs/construction_roadmap.md` (Phase 2). Not yet fixed.
- **Seam firewall verified holding in code:** no `_truth` reference under
  `forecasting/src/{data,features,models,decision,report}`; no real `forecasting` import in
  `onramp/` (doc/comment mentions only). `tests/test_module_boundaries.py` passes.
- **Dollar-metric discipline verified reproducible:** raw-only baseline floor of $144,789 (clean) /
  $148,882 (dirty) via `python -m forecasting.src.evaluate.baseline_floor`.

---

## 2026-06-30 — Backfill: P1 + P2 were built but never logged `[built]` `[backfilled]`

Git/file-state inspection (prompted by the workflow audit above) found `forecasting/` is **not**
"package skeleton, nothing built" as `CLAUDE.md`/`forecasting/CLAUDE.md` claimed — P1 and P2 are
both substantially built and committed. They were built across the squashed `a66f85a` ("Initial
commit") and `2698401` ("Add P2 feature pipeline...") commits without a progress-log entry at the
time. Backfilling now; `CLAUDE.md` and `forecasting/CLAUDE.md` Current status updated to match.

- **P1 — simulated data + honest baselines + backtest harness** (in `a66f85a`, mislabeled in its own
  commit message as "P0 (decision frame)" only):
  - `forecasting/src/simulate/generator.py` — the synthetic-restaurant generator writing
    `data/raw/` (messy export) + `data/_truth/` (ground truth) per `forecasting/docs/simulated_data.md`.
  - `forecasting/src/models/baselines.py` — seasonal-naive, same-weekday rolling mean, Croston
    (intermittent demand).
  - `forecasting/src/evaluate/backtest.py` — rolling-origin CV harness.
  - `forecasting/src/evaluate/baseline_floor.py` + `forecasting/src/data/loader.py`.
  - Reproducible raw-only baseline floor: **$144,789 clean / $148,882 dirty**.
  - Tests: `test_simulator.py`, `test_baselines.py`, `test_backtest.py`, `test_loader.py`,
    `test_cleaner.py` (an earlier cleaner version also landed in this commit).
- **P2 — clean the polluted signal + per-item point model** (in `2698401`):
  - `forecasting/src/data/cleaner.py` (extended) — pollution stripping, menu-era tagging.
  - `forecasting/src/features/pipeline.py` — calendar/lag/rolling-stat features, walk-forward CV,
    a leakage canary.
  - `forecasting/src/models/point.py` — point-forecast baselines (lag-7, rolling-28, gut-proxy).
  - Tests: `test_features.py` (288 lines) — **one test is currently red**,
    `test_lag_7_equals_same_weekday_last_week` (see the audit entry above and
    `forecasting/docs/construction_roadmap.md` Phase 2). P2 is not clean until this is resolved.
- **No Comprehension Contract exit was exercised for either phase** — both were built and committed
  under the old pre-code gate model (before the 2026-06-30 gate inversion, also same day) without a
  `docs/phase_decisions/Pn.md` artifact. This is the same gap `efficiency_backlog.md` already tracks
  ("no gate artifacts produced"); noted here so the backfill doesn't imply the gate was cleared.

---

## 2026-06-29 — Forward notes: Co provenance (#3) + cross-seam join key (#4) `[decided]`

The two conceptual items from the post-P0 review are about the engine↔seam boundary, which the
engine hasn't built yet (P1/P2 work). Building them now would mean standing up engine ingestion
ahead of its phase (Anti-Drift). Decision: **record both as forward design notes and defer the build
to its proper phase**, rather than gate them out-of-phase.

- **#3 — Co should derive from the on-ramp's computed plate cost, not be hand-typed.** Blocked today:
  the seam carries no prices, so the engine can't reconstruct a plate cost from `data/raw/`. Decided
  approach: a **derived food-cost seam leg** the on-ramp writes (one source of truth); deferred to the
  on-ramp's invoice/handoff phase; a gated step touching `data/CONTRACT.md` + `schemas/`. Recorded in
  **`data/CONTRACT.md` → Forward notes**.
- **#4 — config `name` ↔ seam `dish_name` is the only cross-artifact join key, and nothing enforces
  it.** Belongs in **P2 engine ingestion**, where `clean.py` already plans "reconcile item-name
  drift." Recorded as a note in **`forecasting/docs/construction_roadmap.md` Phase 2**: reconcile
  config names against the seam and fail loud on drift (reuse the local trim+casefold in
  `forecasting/src/config.py`; no on-ramp import). Durable fix (a stable `item_id` across the seam)
  also recorded in `data/CONTRACT.md`.

No code changed; docs only. This closes the post-P0 review: #1 built (config gate), #2/#5/#6/#7 built
(mechanical hardening), #3/#4 recorded and deferred to phase.

---

## 2026-06-29 — Review hardening: 4 mechanical fixes (#2, #5, #6, #7) `[built]`

The remaining mechanical items from the post-P0 review, fixed in one pass. Reuse of already-gated
disciplines — no new step, so the Comprehension Contract gate did not re-trigger (`00-process.md`
carve-out), same as the 2026-06-25 W0 hardening pass.

- **#2 — Co/Cu guard centralized (`forecasting/src/evaluate/objective.py`).** `critical_ratio`
  rejected non-positive costs but `dollar_loss` did not — so `dollar_loss(co=-14, …)` silently
  returned a negative "cost" straight into the ship/no-ship verdict. Extracted
  `_require_positive_costs(co, cu)` and call it from both `dollar_loss` and `critical_ratio`
  (`total_realized_cost` inherits it via `dollar_loss`). One gate, applied consistently.
- **#7 — scalar return type (`objective.py`).** A scalar `dollar_loss(...)` call returned
  `np.float64` (a 0-d result) despite the `float` annotation. Now returns a plain `float` for scalar
  inputs, `ndarray` for array inputs — `float(loss) if np.ndim(loss) == 0 else loss`.
- **#5 — store helper hardened (`onramp/plate_cost/src/store.py`).** Replaced the f-string SQL
  (`read_parquet('{path}')`) with a parameterized bind (`read_parquet(?)`); a missing seam file now
  raises a legible `FileNotFoundError` with a "run the export" hint instead of a raw DuckDB IO error
  (rule 07); the connection is context-managed (closed on error). Shared `_read_raw_parquet(filename)`
  takes a bare filename (+ a traversal assert) so the helper stays structurally confined to data/raw/.
- **#6 — deterministic price tie-break (`onramp/plate_cost/src/pricing/compute.py`).** `latest_prices`
  used a strict `>` (silent first-wins on equal dates); now `>=` with a documented rule — on an equal
  `observed_date`, the last observation in input order supersedes (a same-day re-entry wins).
- Tests added: scalar-`float` return, `dollar_loss`/`total_realized_cost` reject non-positive costs,
  store missing-file legible error, same-date tie-break.
- Verified: **84 tests pass (full-repo); ruff clean.** (+5 tests; no regressions.)

---

## 2026-06-29 — Forecasting P0 hardening: the config gate `[built]`

A post-P0 review found `config/items.yaml` — the engine's load-bearing economics — had **no
loader, no schema, and no test**: a typo (`prep_type: Batch`), a sign error (`co: -14`), or a
stray key would pass silently and quietly corrupt the dollar verdict (`q* = Cu/(Co+Cu)`). The seam
already had its head-chef gate (`schemas/seam.py`); the engine's own config did not. This closes
that gap — finishing P0 properly before P1 consumes the economics.

Gate 4 cleared (Jay): "By preventing silent failures, we are creating a PrepType enum and a pydantic
model that fail loudly when an unseen instance appears. In chef's terms, we are creating guards in
the kitchen that prevent taste and flavor from drifting even if the dish looks exactly the same."
(Failure mode: a config that *looks* fine but carries a wrong value, silently mis-routing an item or
producing a wrong dollar number.)

- **`forecasting/src/config.py`** — the validated load path. `PrepType` enum (`batch` /
  `made_to_order`); `ItemEconomics` pydantic model (`co>0`, `cu>0`, `lead_time_days>=1`,
  enum-constrained `prep_type`, `extra="forbid"` to catch typo'd keys); `load_items()` keyed by
  `id`, rejecting duplicate ids/names and structurally-wrong files with a **named** `ValueError`
  (which item, which field). Lives at `src/` top level on purpose — NOT `src/data/`, whose contract
  is "reads ONLY data/raw/"; this reads `config/`. Engine-only (not a seam artifact) so it does NOT
  go in the shared `schemas/`.
- **`forecasting/tests/test_items_config.py`** — 19 tests (accept/reject pattern from
  `test_seam_schemas.py`): shipped config loads all 11 items with the batch/made-to-order fork
  preserved; wrong-case/unknown `prep_type`, non-positive `co`/`cu`, `lead_time<1`, empty
  `id`/`name`, and typo'd keys rejected; duplicate id and normalized-duplicate name rejected;
  missing-file and structurally-wrong YAML rejected.
- **`requirements.txt`** — declared `PyYAML` (the loader) and `numpy` (already imported by
  `objective.py` since P0) as direct deps; both were transitive-only. Already pinned in the lock
  (PyYAML 6.0.3, numpy 2.5.0) — no install, lock unchanged.
- **Scope held:** the seam name-reconciliation (config `name` ↔ `data/raw` `dish_name`) is a
  separate finding (#4) and was deliberately NOT bundled here.
- Verified: **79 tests pass (full-repo); ruff clean.** (+19 engine tests; no regressions.)

---

## 2026-06-29 — Forecasting P0: decision frame `[built]`

Gate 4 cleared (Jay): "P0 builds metrics that are more important and interpretable than MAPE or RMSE
— using the right garnishes for the right meals so everything actually has meaning and fits together."
(Failure mode: optimizing accuracy on a target whose errors don't cost what was assumed.)

- **`config/items.yaml`** — per-item economic parameters (Co/Cu/prep_type/lead_time) for all 11
  items from the Marco menu. Batch items (7): Braised Short Rib, Pan-Seared Salmon, Half Roast
  Chicken, House Burger, Ribeye Steak 12oz, Duck Confit, Butter Poached Cod. Made-to-order (4):
  Wild Mushroom Risotto, Classic Caesar Salad, Pappardelle Bolognese, Tuna Tartare. Config carries
  the chef-set economic reality (food-cost-based Co; contribution-margin-based Cu); marked PLACEHOLDER
  pending real discovery. `q*` and `prep_qty` are derived downstream, never stored here.
- **`forecasting/src/evaluate/objective.py`** — three pure functions:
  - `dollar_loss(prep, demand, co, cu)` — scalar or vectorized; the verdict for every evaluation
  - `critical_ratio(co, cu)` → q* = Cu/(Co+Cu); the service level that minimises expected dollar_loss
  - `total_realized_cost(preps, demands, co, cu)` — sum across a backtest window; the bottom line
- **`forecasting/tests/test_objective.py`** — 13 tests: exact prep costs nothing; asymmetry
  (underage costlier than overage when Cu>Co); vectorized array output; q* math for real items;
  symmetric case → 0.5; rejects zero/negative Co or Cu; total cost sums correctly.
- **Done-when met**: objective runs on a dummy forecast and returns a dollar number; all 13 pass.
- Verified: **60 tests pass (full-repo); ruff clean.** (+13 new engine tests; no regressions.)

---

> **Older history archived.** Entries dated 2026-06-25 and earlier live in
> [`../docs_archive/progress_log_archive.md`](../docs_archive/progress_log_archive.md) so this active
> log stays small for per-build reads. Move an entry there once it is no longer current-era context.
