# W7 Adversarial Review — Production Hosting + Security Hardening

**Reviewer:** web-reviewer (adversarial, read-only over code; Write scoped to this file only)
**Date:** 2026-07-14
**Scope reviewed:** working-tree changes layered on `fa03e15` (branch `onramp/w6-costed-reveal`).
Diff base per prompt: uncommitted W7 work (new `web/csrf.py`, `web/rate_limit.py`, `web/config.py`,
`web/observability.py`, `src/email/sender.py`, `src/pricing/retention.py`, `scripts/backup.py`,
`scripts/apply_retention.py`, `Dockerfile`, nine test files; rewrites of `web/app.py`,
`web/__main__.py`, eight templates, `conftest.py`).
**Acceptance criteria:** `website_production_overview.md` §4 W7 row + `website_vision.md` §8, read
against `onramp/README.md` and rules 05/06/07 + `data/CONTRACT.md`.

---

## Step 0 — What this phase had to deliver ("done when")

- Per `website_production_overview.md` §4 (W7 row), deliver the pre-deploy hardening bundle: **TLS
  support**, a **deploy target artifact**, **per-request CSRF** on every state-changing POST,
  **managed/persistent secrets**, **rate limiting on the funnels**, **backups (app DB + `data/raw/`)**,
  **monitoring/structured logs**, the **price-history retention policy**, **real email transport** for
  password resets (redacting W5's raw-token-in-logs stopgap once live), and the **recorded (not
  executed) Postgres decision**.
- "Done when" is bounded by what a credential-less coding agent can build and test without live infra:
  *code + config that makes a real deploy safe*, not an actual provisioned deploy. The builder's line
  between built vs. recorded-only (Decision Log "Explicitly Deferred") is a legitimate reading of the
  spec — no spec/intent conflict to stop on.
- Invariants that must survive (overview §5): seam law green, compute stays pure, honest precision,
  hostile-until-validated input, secrets in env. W7 changes **no displayed number**, so the
  reconcile-by-eye / false-precision trust laws are not in play this phase.

**No spec-vs-code conflict found at the intent level.** Every built artifact maps to a named W7 row
item; nothing over-reaches into W8/W9 (no cloud platform picked, Postgres not executed). Anti-Drift is
clean.

---

## Step 2 — Hunt list

**Seam firewall (highest priority):** PASS / verified-by-running.
- No new `forecasting/` import, no `_truth`/`interim`/`processed` path in any W7 file (grep clean; the
  only "forecasting" hit is prose in `retention.py`'s docstring). `tests/test_module_boundaries.py`
  passes (5/5) and its self-tests confirm it would catch a planted violation. Retention writes only
  `data/raw/price_observations.parquet` through the same `_stage_parquet` + `fcntl.flock` path the seam
  writer uses; backup script *reads* `data/raw/` (copy-out) and never touches `_truth/`. Seam writes
  still route through `schemas/` (retention re-serializes already-validated rows; no new bypass).

**Architecture & layering (05):** PASS.
- `src/email/sender.py` and `src/pricing/retention.py` are pure (no FastAPI import); the web-only
  concerns (CSRF, rate limit, config posture, observability) live in `web/`. Compute stays runnable
  without the web layer. No premature server-class DB (Postgres correctly recorded-not-executed).
  Middleware centralizes cross-cutting concerns rather than threading `Depends` — good craft.

**Front-end / UX trust (06):** PASS (nothing numeric changed).
- All nine POST-form templates carry the hidden `csrf_token` field (verified: 1 field per POST form,
  all present). No sample/placeholder data, no provenance change, no money figures touched. No firewall
  data reaches markup.

**Backend / API correctness (07):** CONCERN → three FAILs (see findings).
- Boundary validation still enforced (`/confirm` and `/invoice/confirm` re-parse through `schemas/`).
- **FAIL:** CSRF middleware buffers the entire request body in memory before any size/auth/token check
  (MAJOR-1, verified by running).
- **FAIL:** password-reset route leaks account existence + fully breaks under any SMTP failure
  (MAJOR-2).
- **FAIL:** rate limiter keys on `request.client.host`, which is the proxy IP under the phase's own
  recommended reverse-proxy deploy (MAJOR-3).
- Error handling otherwise good (named 4xx, correlation ids, no traceback to client).

**Software engineering:** tests are meaningful and green (591 passed). CSRF, rate-limit, email,
retention, config, backup, observability each have dedicated unit + one e2e test. Gaps: the enumeration
side channel and the memory-buffering path are untested (findings below).

---

## Step 3 — Riskiest spots, looked at deliberately

1. **`web/csrf.py::verify_csrf_request` — the `request.body()`-before-`request.form()` fix.** The fix
   itself is *correct* (confirmed against Starlette 1.3.1 `BaseHTTPMiddleware`/`_CachedRequest` replay
   semantics and by running a live multipart POST — `test_multipart_post_form_fields_survive...`
   passes). But looking there deliberately surfaced the real defect: that same unconditional
   `await request.body()` runs on **every** unsafe-method request *before* the token is compared and
   *before* the route's `read(MAX_UPLOAD_BYTES+1)` guard — so it buffers the whole body in memory.
   See MAJOR-1.
2. **`web/rate_limit.py` client-IP source + the reverse-proxy topology the config module recommends.**
   The limiter is correct in isolation (fixed-window, per-bucket, tested) but keys on the wrong address
   under the deploy `web/config.py` itself recommends. See MAJOR-3.
3. **The reset-password route's new SMTP call interacting with W5's enumeration defense.** Building
   "fail loudly on SMTP error" collided with "identical response whether or not the account exists."
   See MAJOR-2.

---

## Step 4 — Findings

```
[MAJOR] CSRF middleware buffers the entire request body in memory before any size/auth/token check
Location:       onramp/plate_cost/web/csrf.py::verify_csrf_request (line 48: `await request.body()`),
                run on every POST via CSRFMiddleware.dispatch; interacts with
                web/app.py::upload_submit / invoice_upload_submit size guards.
What's wrong:   verify_csrf_request calls `await request.body()` as its FIRST action for every
                unsafe-method request. Starlette's Request.body() accumulates the whole stream into a
                single in-memory bytes object (confirmed against starlette 1.3.1 source). This runs
                before the CSRF token is compared, before the route's auth check, and before the
                route's `sales_file.read(MAX_UPLOAD_BYTES + 1)` size guard. So the 700 KB upload cap
                no longer bounds memory: the full payload is already resident before anything can
                reject it. Pre-W7 the multipart parser spooled parts >1 MB to disk (bounded RAM); W7's
                middleware converts that into a contiguous in-memory buffer for every POST.
Why it matters: This is a hostile-input / DoS gap (rule 07: "Size-limit uploads ... the capture funnel
                is the most-exposed surface"). An attacker needs no account and no valid CSRF token —
                the body is read before both checks — so anyone reachable at the socket can force the
                server to buffer arbitrarily large bodies in RAM, then receive a 403/redirect. The
                route's careful size guard gives false confidence because it fires after the damage.
                Concept: middleware runs outside the handler, so a size limit enforced inside the
                handler cannot protect anything the middleware already read.
Fix:            Reject oversized requests before reading the body: in the CSRF middleware (or a small
                dedicated middleware ahead of it) check Content-Length against a hard cap and return
                413 before `request.body()`; and/or read the body with a bounded cap. A server-level
                max-body-size (proxy or uvicorn `--limit-max-requests`-style guard) is the belt-and-
                suspenders answer for a real deploy.
Confidence:     High (ran it: an 8 MB-per-file upload — 16 MB total, limit is 0.7 MB — was fully
                buffered; peak Python heap 56.1 MB for one request before the 422 size error returned).
```

```
[MAJOR] Password-reset route leaks account existence and fully breaks under any SMTP failure
Location:       onramp/plate_cost/web/app.py::reset_password_request_submit (lines ~229-243);
                src/email/sender.py::send_password_reset_email (raises on SMTP failure when configured).
What's wrong:   The route calls send_password_reset_email() only when request_password_reset() returned
                a token (i.e. the account EXISTS). There is no try/except around that call. Per its own
                docstring, send_password_reset_email raises (does not return False) if ONRAMP_SMTP_HOST
                is set but the send fails. So: account exists + SMTP down/misconfigured -> unhandled
                exception -> 500; account does NOT exist -> token is None -> email never attempted ->
                normal 200 "submitted" page. An attacker toggling emails observes 500 vs 200 and
                enumerates which addresses have accounts — directly contradicting the route's own
                comment ("Identical response whether or not the account exists ... enumeration defense")
                and request_password_reset's docstring ("never let this ... leak which emails have
                accounts"). Secondarily, any transient SMTP outage 500s password reset for real users
                instead of degrading legibly (rules 06/07: "fail legibly," never a bare crash to the
                operator).
Why it matters: Account enumeration is a real auth information leak; a working reset flow is trust-
                critical. The builder deliberately chose "fail loudly" for SMTP errors but did not
                notice the loud failure is account-existence-conditional, which turns a safety choice
                into a side channel. Concept: enumeration defenses require the response to be identical
                on both branches — including the error branch.
Fix:            Wrap the send in try/except inside the route: on send failure, log server-side with a
                correlation id and still render the same 200 "submitted" page (or the same generic
                error page) regardless of whether the account existed. Keep sender.py's raise (loud at
                the transport layer); make the route absorb it into a uniform response. Add a route-
                level test: SMTP configured + failing must return the same status/page for an existing
                and a non-existing email.
Confidence:     High (read the route + sender + request_password_reset; the None-on-missing-account and
                raise-on-failure behaviors are both confirmed in source; no test covers the route-level
                response under SMTP failure).
```

```
[MAJOR] Rate limiter keys on the proxy IP under the phase's own recommended reverse-proxy deploy
Location:       onramp/plate_cost/web/rate_limit.py::_client_ip / check_rate_limit;
                web/__main__.py (uvicorn.run started without proxy-header handling);
                web/config.py docstrings recommend "terminate TLS at a reverse proxy in front of a
                loopback bind" as the default production posture.
What's wrong:   _client_ip returns request.client.host (the TCP peer). Under the reverse-proxy topology
                web/config.py recommends, that peer is the proxy — the same address (e.g. 127.0.0.1)
                for every real user, because uvicorn is launched with no proxy_headers / trusted-proxy
                config and nothing reads X-Forwarded-For (grep: no proxy-header handling anywhere).
                So all tenants collapse into one shared bucket. The login budget (10/min) and upload
                budget (20/min) then apply collectively: the 11th distinct chef logging in within a
                minute gets 429, and a single attacker is indistinguishable from legitimate traffic.
Why it matters: The security control is simultaneously ineffective (can't isolate an attacker) and an
                availability foot-gun (throttles unrelated tenants), and it fails silently in exactly
                the deployment this phase recommends. test_rate_limit.py's own e2e test relies on the
                fixed shared "testclient" IP to force a 429 — inadvertently demonstrating the collapse
                as if it were the intended behavior. Concept: behind a proxy, the real client address
                lives in a forwarded header, not the socket peer; keying on the peer defeats per-client
                limiting.
Fix:            When behind a trusted proxy, derive the client IP from X-Forwarded-For with a trusted-
                proxy allowlist (or run uvicorn with proxy_headers=True + forwarded_allow_ips and read
                request.client after ProxyHeadersMiddleware normalizes it). Gate this on config so
                direct-TLS deploys keep using the socket peer. At minimum, record the limitation as a
                deploy-time requirement, not silently.
Confidence:     High for the mechanism (confirmed no proxy-header handling exists and __main__ passes
                no proxy flags); Medium that it bites in practice, since it is latent until a real
                reverse-proxy deploy — but that deploy is the phase's stated recommendation.
```

```
[MINOR] Structured request log skips the requests you most want to see — the ones that raise
Location:       onramp/plate_cost/web/observability.py::RequestLoggingMiddleware.dispatch
What's wrong:   dispatch logs only after `response = await call_next(request)` returns. If a downstream
                handler raises (e.g. the MAJOR-2 SMTP 500, or any unhandled error), call_next raises,
                the _log.info line never runs, and no structured request line is emitted for that
                request. Starlette's ServerErrorMiddleware still logs a traceback, so it is not fully
                lost, but the phase's own "monitoring/structured logs" deliverable misses exactly the
                failures worth alerting on, and duration/status are absent for them.
Why it matters: Monitoring that omits 500s under-reports the incidents that matter. Concept: to observe
                failures, the logging wrapper must catch the exception (log, then re-raise), not sit
                only on the success path.
Fix:            Wrap call_next in try/except: on exception, log method/path/duration with status 500
                (or "error"), then re-raise so the normal error handling still runs.
Confidence:     High (read the middleware; the early-return-on-raise behavior is structural).
```

```
[MINOR] configure_logging docstring says stdout; logging.StreamHandler() defaults to stderr
Location:       onramp/plate_cost/web/observability.py::configure_logging (docstring vs. handler)
What's wrong:   The docstring says "Replaces the root logger's handlers with a single stdout stream in
                JSON," and the module docstring says "to stdout/stderr," but logging.StreamHandler()
                with no argument writes to sys.stderr. Logs actually go to stderr.
Why it matters: A real deploy's log shipping is often stream-specific (some collectors treat stderr as
                error-level). A comment that disagrees with behavior is a future foot-gun (rule: the
                code is truth; the mismatch is a finding).
Fix:            Either pass sys.stdout explicitly to StreamHandler(...) if stdout is intended, or
                correct the docstring to say stderr. Pick one and make them agree.
Confidence:     High (StreamHandler default stream is documented/known; trivially verifiable).
```

```
[NIT] POST /reset-password/{token} (token submission) is not rate-limited
Location:       onramp/plate_cost/web/app.py::reset_password_submit
What's wrong:   Only /login, /reset-password (request), /upload, /invoice/upload have buckets. The
                reset-confirm endpoint that consumes a token has no throttle, so token submission is
                unbounded.
Why it matters: Low risk today because reset tokens are long random values (generate_token), but a
                brute-force-a-token attempt has no friction. Cheap to close given the bucket machinery
                already exists.
Fix:            Add a small bucket (e.g. "reset-confirm") to reset_password_submit, or note explicitly
                why it is out of scope.
Confidence:     High (read the route; no check_rate_limit call present).
```

---

## Reviewer Focus Areas (from the Decision Log)

**1. The CSRF `request.body()`-before-`request.form()` fix — is the reasoning correct or just
coincidentally working?** *Correct.* Confirmed against Starlette 1.3.1: `Request.body()` accumulates
`self._body`, which is what `BaseHTTPMiddleware`'s `_CachedRequest.wrapped_receive` replays downstream;
`Request.form()` alone drains `.stream()` without populating `_body`, so a downstream `Form(...)` sees
an empty body. The live multipart e2e test (`test_multipart_post_form_fields_survive_csrf_verification`)
passes and proves the body survives. The docstring's warning that a future "simplifying" refactor
removing the `.body()` call would reopen the 422 is accurate and worth keeping. **However**, that same
correct-but-unconditional `.body()` call is the root of MAJOR-1: it also buffers the *entire* body in
memory for every POST before the size/auth/token checks. The fix is right; its blast radius on the
upload funnels was not considered.

**2. Rate-limiter process-local state + the CSRF-bypass conftest fixture's blast radius.**
- *Rate-limiter state:* correct and honestly documented as single-instance (N-process = N×budget). The
  real defect is not the in-memory store but the client-IP source under the recommended proxy deploy
  (MAJOR-3) — a different axis than the one the builder flagged.
- *CSRF-bypass fixture scope:* the builder's Decision Log calls it "repo-wide"; it is actually scoped to
  `onramp/plate_cost/tests/` (a conftest applies to its own subtree), which is *tighter* than claimed —
  fine, not a defect. The concern that a real CSRF regression elsewhere could hide behind the autouse
  bypass is adequately closed: `test_web_csrf.py` shadows the fixture (module-local, same name) and
  exercises real enforcement end-to-end (cookie issuance, httponly, missing/mismatched/matching token,
  cold-client rejection, live multipart through the real middleware). The bypass removes CSRF as a
  *variable* from unrelated tests without masking its enforcement. PASS.

---

## Step 5 — Sign-off

- **VERDICT: No — not as it stands.** The phase delivers every named W7 artifact and the seam/layering
  invariants hold, but three MAJOR backend-hardening defects mean the security bundle does not yet do
  what W7 exists to do: MAJOR-1 (upload size guard defeated by full in-memory body buffering) and
  MAJOR-3 (rate limiter collapses all tenants into one bucket under the phase's own recommended deploy)
  are hardening items that are present but not effective; MAJOR-2 (reset-password enumeration + outage
  under SMTP failure) is a real auth leak and a trust regression. These are fixable without rework of
  the architecture — the shapes are right, three seams need closing before "makes a real deploy safe"
  is true.
- **TEST + LINT (observed):**
  - `make test` → **591 passed**, 4 warnings, ~19s (conda `restaurant-dev`, repo-root pytest incl.
    `onramp/plate_cost/tests/`).
  - `make lint` (`ruff check .`) → **All checks passed.**
  - `make import-lint` (`lint-imports`) → **2 contracts kept, 0 broken.**
  - Boundary test `tests/test_module_boundaries.py` → **5 passed**; self-tests confirm it would catch a
    planted `_truth`/`forecasting` violation.
- **TOP 3 FIXES (priority order):**
  1. MAJOR-1 — cap request size before `request.body()` (Content-Length/413 in a front middleware);
     the upload cap must bound memory, not just reject after buffering.
  2. MAJOR-2 — wrap the SMTP send in the reset route; return an identical response for existing and
     non-existing accounts on send failure; add the enumeration test.
  3. MAJOR-3 — derive client IP from a trusted forwarded header (or run uvicorn with proxy headers) so
     the rate limiter survives the recommended reverse-proxy deploy.
- **WHAT I COULD NOT VERIFY (even after trying):**
  - No live deploy exists, so TLS termination, real SMTP delivery, and the reverse-proxy IP collapse
    could only be reasoned/statically confirmed (no proxy-header handling; uvicorn passes no proxy
    flags), not exercised against a real proxy. MAJOR-3's *mechanism* is confirmed; its *field impact*
    is inferred from the phase's own recommended topology.
  - The backup script's SQLite online-backup path was read, not run against a live app DB (Postgres
    branch is intentionally unbuilt).
  - Whether an off-repo ASGI/proxy layer in the eventual deploy imposes its own body-size cap (would
    mitigate MAJOR-1) is unknowable from this tree; the in-repo path has no cap.
- **SINGLE BIGGEST RISK:** The CSRF middleware reads the full request body into memory on every POST
  before the size, auth, or token check — so the on-ramp's most-exposed surface (the upload funnels)
  can be made to buffer arbitrarily large payloads by an unauthenticated caller, and the 700 KB guard
  that looks like protection fires only after the memory is already spent.
```
```
