"""Tests for the W8 design-and-markup pass: the public storefront on GET /, the shared skip
link + keyboard-focus + active-nav markup in base.html, and the onboarding progress meter +
"good enough to show value" threshold on the W1 capture funnel (vision §3A).

Pure presentation — no new routes, no new seam writes. These tests exist because a redesign can
silently break rule 06's trust law (honest precision, reconciles-by-eye, labeled sample data) or
strand a keyboard user; `test_web.py`'s existing grid tests already cover the compute/reconcile
side and are left untouched.
"""
from fastapi.testclient import TestClient

import web.app as appmod
from src.auth.service import Identity
from web.app import app

_client = TestClient(app)

_FAKE_IDENTITY = Identity(
    session_id="s1", user_id="u1", email="chef@example.com",
    restaurant_id="r1", restaurant_name="Test Kitchen",
)


def _bypass_login(monkeypatch):
    monkeypatch.setattr(appmod, "require_login", lambda request, db: None)
    monkeypatch.setattr(appmod, "current_identity", lambda request, db: _FAKE_IDENTITY)
    # _nav_context checks is_authenticated independently of the route gate above (it's cosmetic
    # only per app.py's own comment) — patch it too so the nav's logged-in branch renders.
    monkeypatch.setattr(appmod, "is_authenticated", lambda request: True)


# ── the public storefront (GET /) ──

def test_landing_page_makes_the_sites_own_pitch():
    """Vision §1's one-sentence pitch must be the storefront's headline — the "prospect can
    judge this without us in the room" requirement (production overview §5 invariant 5)."""
    resp = _client.get("/")
    assert resp.status_code == 200
    assert "Connect your POS and confirm your recipes once" in resp.text


def test_landing_page_keeps_the_sample_grid_embedded_and_labeled():
    """The demo grid stays inside the storefront, clearly labeled as a live demo (production
    overview §6) — not hidden behind a separate route, not dressed as the operator's own data."""
    resp = _client.get("/")
    assert 'id="live-demo"' in resp.text
    assert "Live demo" in resp.text
    # The existing sample-data disclaimer (rule 06 "label placeholder/sample data") still fires.
    assert "sample" in resp.text.lower()
    # And the grid content itself (quadrants) is still there, unchanged by the redesign.
    assert any(label in resp.text for label in ("Stars", "Plowhorses", "Puzzles", "Dogs"))


def test_landing_page_has_a_working_anchor_to_the_demo():
    resp = _client.get("/")
    assert 'href="#live-demo"' in resp.text


def test_landing_page_shows_a_real_next_step_when_already_logged_in(monkeypatch):
    """Regression for W8_review.md NIT: a logged-in operator previously saw a contradictory
    "Log in" CTA in the hero right beside the nav's own logged-in links."""
    _bypass_login(monkeypatch)
    resp = _client.get("/")
    assert 'href="/dishes" class="btn-secondary"' in resp.text
    assert 'href="/login" class="btn-secondary"' not in resp.text


# ── accessibility: skip link, focus target, keyboard path (rule 06) ──
# base.html renders these unconditionally for every extending template, so both checks are run
# against two unrelated pages (the public landing page and the login page) — proving the "every
# page" claim in the test name, not just asserting it once against / (W8_review.md NIT).

def test_skip_link_present_on_every_page():
    for path in ("/", "/login"):
        resp = _client.get(path)
        assert 'class="skip-link"' in resp.text
        assert 'href="#main-content"' in resp.text


def test_main_landmark_is_the_skip_links_target_and_focusable_on_every_page():
    for path in ("/", "/login"):
        resp = _client.get(path)
        assert 'id="main-content"' in resp.text
        assert 'tabindex="-1"' in resp.text


def test_content_link_underline_is_a_visible_color_not_the_near_invisible_border_tint():
    """Regression for W8_review.md MINOR-1: the global link restyle originally used --border
    (#e4ddd6, ~1.3:1 against the page) as the underline color, making every inline prose link —
    most consequentially success.html's post-save "set your menu prices" CTA — visually
    indistinguishable from body text. --text-muted (independently contrast-verified >5:1) fixes it."""
    resp = _client.get("/static/style.css")
    assert "a {" in resp.text
    assert "text-decoration-color: var(--text-muted)" in resp.text
    assert "text-decoration-color: var(--border)" not in resp.text


def test_progress_meter_partial_renders_safely_without_step_set():
    """Regression for W8_review.md NIT: an includer that forgets `{% set step %}` must not 500
    the page — the partial degrades to every step reading as not-yet-reached instead of raising."""
    html = appmod._templates.env.get_template("_progress_meter.html").render()
    assert "progress-meter" in html
    assert "is-current" not in html
    assert "is-done" not in html


# ── active-page nav marker (keyboard/screen-reader orientation) ──

def test_nav_marks_the_current_page_unauthenticated():
    resp = _client.get("/login")
    assert 'href="/login" aria-current="page"' in resp.text


def test_nav_marks_the_current_page_authenticated(monkeypatch):
    _bypass_login(monkeypatch)
    resp = _client.get("/invoice/upload")
    assert 'href="/invoice/upload" aria-current="page"' in resp.text
    # A different nav link on the same authenticated render must NOT be marked current.
    assert 'href="/dishes" aria-current="page"' not in resp.text


# ── onboarding progress meter (vision §3A) ──

def test_upload_page_shows_progress_meter_on_step_one(monkeypatch):
    _bypass_login(monkeypatch)
    resp = _client.get("/upload")
    assert 'class="progress-meter"' in resp.text
    assert 'aria-current="step"' in resp.text
    # Step 1 ("Connect your data") is current; step 2/3 are not yet reached (no "is-done" yet).
    assert "is-done" not in resp.text


_SALES_3_DISHES = (
    b"dish_name,count,period_start,period_end\n"
    b"Burger,120,2026-06-01,2026-06-07\n"
    b"Salad,40,2026-06-01,2026-06-07\n"
    b"Soup,30,2026-06-01,2026-06-07\n"
)
_BOM_3_DISHES = (
    b"dish_name,ingredient_name,qty,recipe_unit,canonical_unit,yield_factor\n"
    b"Burger,beef patty,6,oz,oz,0.9\n"
    b"Salad,romaine,4,oz,oz,0.85\n"
    b"Soup,broth,10,oz,oz,1.0\n"
)
_SALES_2_DISHES = (
    b"dish_name,count,period_start,period_end\n"
    b"Burger,120,2026-06-01,2026-06-07\n"
    b"Salad,40,2026-06-01,2026-06-07\n"
)
_BOM_2_DISHES = (
    b"dish_name,ingredient_name,qty,recipe_unit,canonical_unit,yield_factor\n"
    b"Burger,beef patty,6,oz,oz,0.9\n"
    b"Salad,romaine,4,oz,oz,0.85\n"
)


def _post_upload(sales, bom, monkeypatch):
    _bypass_login(monkeypatch)
    return _client.post(
        "/upload",
        files={
            "sales_file": ("sales.csv", sales, "text/csv"),
            "bom_file": ("bom.csv", bom, "text/csv"),
        },
    )


def test_confirm_page_shows_progress_meter_on_step_two_done_step_one(monkeypatch):
    resp = _post_upload(_SALES_2_DISHES, _BOM_2_DISHES, monkeypatch)
    assert resp.status_code == 200
    assert 'class="progress-meter"' in resp.text
    assert 'aria-current="step"' in resp.text
    assert "is-done" in resp.text  # step 1 is now behind the chef


def test_confirm_page_shows_value_threshold_met_at_three_dishes(monkeypatch):
    resp = _post_upload(_SALES_3_DISHES, _BOM_3_DISHES, monkeypatch)
    assert resp.status_code == 200
    assert "value-threshold--met" in resp.text
    assert "enough dishes to show value" in resp.text.lower()


def test_confirm_page_shows_value_threshold_not_met_below_three_dishes(monkeypatch):
    resp = _post_upload(_SALES_2_DISHES, _BOM_2_DISHES, monkeypatch)
    assert resp.status_code == 200
    assert "value-threshold--not-met" in resp.text
    assert "value-threshold--met" not in resp.text


_SALES_2_MATCH_1_UNMATCHED = (
    b"dish_name,count,period_start,period_end\n"
    b"Burger,120,2026-06-01,2026-06-07\n"
    b"Salad,40,2026-06-01,2026-06-07\n"
    b"Fries,15,2026-06-01,2026-06-07\n"
)


def test_confirm_page_threshold_ignores_dishes_that_only_appear_in_one_file(monkeypatch):
    """Regression for W8_review.md MINOR-2: the raw BOM-distinct dish_count is 3 here (Burger,
    Salad, Soup) — enough to have wrongly shown "met" under the old logic — but Soup has no
    matching sales row and Fries has no matching recipe, so only 2 dishes will actually cost on
    /dishes. The badge must gate on that costable count, not the inflated raw one."""
    resp = _post_upload(_SALES_2_MATCH_1_UNMATCHED, _BOM_3_DISHES, monkeypatch)
    assert resp.status_code == 200
    assert "3" in resp.text  # the raw "Dishes" row still honestly shows all 3 BOM dishes
    assert "value-threshold--not-met" in resp.text
    assert "value-threshold--met" not in resp.text


def test_success_page_no_longer_claims_the_costed_grid_is_a_later_phase(tmp_path, monkeypatch):
    """Regression: success.html previously said the tenant's own margin grid "arrives in a later
    phase" — stale since W6 built /dishes + /menu-prices. The redesign must point onward to the
    real flow, not repeat a claim that's no longer true."""
    import src.store as store_mod

    monkeypatch.setattr(store_mod, "RAW_DIR", tmp_path)
    upload_resp = _post_upload(_SALES_2_DISHES, _BOM_2_DISHES, monkeypatch)
    import re
    staged_id = re.search(r'name="staged_upload_id" value="([^"]*)"', upload_resp.text).group(1)

    success_resp = _client.post("/confirm", data={"staged_upload_id": staged_id})
    assert success_resp.status_code == 200
    assert "arrives in a later phase" not in success_resp.text
    assert 'href="/menu-prices"' in success_resp.text
    assert 'href="/dishes"' in success_resp.text
    assert 'class="progress-meter"' in success_resp.text
