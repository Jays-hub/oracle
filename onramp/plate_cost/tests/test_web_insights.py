"""Tests for the W3 /insights page (web/insights.py + the GET /insights route).

Covers: the "nothing captured yet" calm state (no BOM/no invoices), the "not enough of a move yet"
state, and the happy path showing a dollar-quantified opportunity — including that costs are
rounded to the $0.25 grid and that margin/food-cost-tier language never appears (the seam carries
no menu_price yet).
"""
import pandas as pd
import pytest
from fastapi.testclient import TestClient

import src.store as store_mod
import web.app as appmod
from web.app import app

_client = TestClient(app)


@pytest.fixture(autouse=True)
def _bypass_login(monkeypatch):
    monkeypatch.setattr(appmod, "require_login", lambda request: None)


def _write_bom(raw_dir):
    pd.DataFrame([
        {"dish_id": "short-rib", "dish_name": "Short Rib", "ingredient_id": "beef",
         "ingredient_name": "beef", "qty": 8.0, "recipe_unit": "oz", "canonical_unit": "oz",
         "yield_factor": 1.0},
    ]).to_parquet(raw_dir / "bom.parquet", index=False, engine="pyarrow")


def _write_prices(raw_dir, rows):
    pd.DataFrame(rows).to_parquet(raw_dir / "price_observations.parquet", index=False, engine="pyarrow")


def test_insights_with_no_data_shows_calm_empty_state(tmp_path, monkeypatch):
    monkeypatch.setattr(store_mod, "RAW_DIR", tmp_path)
    resp = _client.get("/insights")
    assert resp.status_code == 200
    assert "Nothing to show yet" in resp.text


def test_insights_with_bom_but_no_invoice_shows_calm_empty_state(tmp_path, monkeypatch):
    monkeypatch.setattr(store_mod, "RAW_DIR", tmp_path)
    _write_bom(tmp_path)
    resp = _client.get("/insights")
    assert resp.status_code == 200
    assert "Nothing to show yet" in resp.text


def test_insights_with_no_significant_move_says_so(tmp_path, monkeypatch):
    monkeypatch.setattr(store_mod, "RAW_DIR", tmp_path)
    _write_bom(tmp_path)
    _write_prices(tmp_path, [
        {"ingredient_id": "beef", "ingredient_name": "beef", "unit_price": 3.00,
         "source_invoice": "INV-1", "observed_date": "2026-06-01"},
        {"ingredient_id": "beef", "ingredient_name": "beef", "unit_price": 3.05,
         "source_invoice": "INV-2", "observed_date": "2026-06-08"},
    ])
    resp = _client.get("/insights")
    assert resp.status_code == 200
    assert "No ingredient has moved" in resp.text


def test_insights_shows_dollar_quantified_opportunity(tmp_path, monkeypatch):
    monkeypatch.setattr(store_mod, "RAW_DIR", tmp_path)
    _write_bom(tmp_path)
    _write_prices(tmp_path, [
        {"ingredient_id": "beef", "ingredient_name": "beef", "unit_price": 3.00,
         "source_invoice": "INV-1", "observed_date": "2026-06-01"},
        {"ingredient_id": "beef", "ingredient_name": "beef", "unit_price": 3.48,
         "source_invoice": "INV-2", "observed_date": "2026-06-08"},
    ])
    resp = _client.get("/insights")
    assert resp.status_code == 200
    assert "Beef" in resp.text
    assert "Short Rib" in resp.text
    assert "16%" in resp.text


def test_insights_never_claims_margin_or_food_cost_tier(tmp_path, monkeypatch):
    """The seam carries no menu_price — this page must state the ingredient-cost-only disclaimer
    (which legitimately uses the word "margin" to explain what it can't show) but must never
    render an actual tier/margin FINDING: no tier CSS class, no "strong/ok/thin" label, no dollar
    figure claimed as a margin (rule 06 false-precision guard)."""
    monkeypatch.setattr(store_mod, "RAW_DIR", tmp_path)
    _write_bom(tmp_path)
    _write_prices(tmp_path, [
        {"ingredient_id": "beef", "ingredient_name": "beef", "unit_price": 3.00,
         "source_invoice": "INV-1", "observed_date": "2026-06-01"},
        {"ingredient_id": "beef", "ingredient_name": "beef", "unit_price": 3.48,
         "source_invoice": "INV-2", "observed_date": "2026-06-08"},
    ])
    resp = _client.get("/insights")
    assert "doesn't yet know your menu prices" in resp.text
    assert 'class="tier' not in resp.text
    for tier_label in ("strong", "ok", "thin"):
        assert tier_label not in resp.text.lower()


def test_insights_survives_non_convertible_unit_without_crashing(tmp_path, monkeypatch):
    """A schema-valid BOM with a non-convertible unit pair (e.g. each -> g) must not 500 the whole
    page (W3_review.md MAJOR-1) — the affected dish silently drops out of costing, exactly like a
    missing price, instead of the ValueError propagating to a bare crash."""
    monkeypatch.setattr(store_mod, "RAW_DIR", tmp_path)
    pd.DataFrame([
        {"dish_id": "weird", "dish_name": "Weird Dish", "ingredient_id": "beef",
         "ingredient_name": "beef", "qty": 1.0, "recipe_unit": "each", "canonical_unit": "g",
         "yield_factor": 1.0},
    ]).to_parquet(tmp_path / "bom.parquet", index=False, engine="pyarrow")
    _write_prices(tmp_path, [
        {"ingredient_id": "beef", "ingredient_name": "beef", "unit_price": 3.00,
         "source_invoice": "INV-1", "observed_date": "2026-06-01"},
        {"ingredient_id": "beef", "ingredient_name": "beef", "unit_price": 3.48,
         "source_invoice": "INV-2", "observed_date": "2026-06-08"},
    ])
    resp = _client.get("/insights")
    assert resp.status_code == 200
    assert "Traceback" not in resp.text
    # The move is real (beef +16%), but the only dish using beef can't be costed (non-convertible
    # unit), so there is no opportunity left to show for it.
    assert "Weird Dish" not in resp.text


def test_insights_unexpected_failure_returns_legible_error(monkeypatch):
    """Any OTHER unexpected failure in build_insights_summary must still fail legibly (rules
    06/07): a calm 503 + correlation id, never a stack trace — mirrors test_web.py's grid-route
    regression test. dish_ingredient_cost's own degrade-gracefully fix covers the KNOWN failure
    mode; this covers everything else, the way every sibling route already does."""
    def boom():
        raise RuntimeError("simulated: something broke at /secret/internal/path")

    monkeypatch.setattr(appmod, "build_insights_summary", boom)
    resp = _client.get("/insights")
    assert resp.status_code == 503
    assert "Reference:" in resp.text
    assert "simulated" not in resp.text
    assert "/secret/internal/path" not in resp.text
    assert "Traceback" not in resp.text


def test_insights_costs_round_to_quarter_grid():
    """Rule 06: costs shown must be on the $0.25 grid, not raw penny-precision floats."""
    from web.insights import _display_opportunity
    from src.insights.opportunities import AffectedDish, Opportunity

    opp = Opportunity(
        ingredient_name="beef", pct_change=0.16, direction="up",
        current_price=3.48, prior_price=3.00, days_span=7,
        affected_dishes=[AffectedDish(dish_name="Short Rib", prior_cost=24.03, new_cost=27.90)],
    )
    display = _display_opportunity(opp)
    dish = display["affected_dishes"][0]
    assert dish["prior_cost"] == pytest.approx(24.0)   # 24.03 -> nearest $0.25
    assert dish["new_cost"] == pytest.approx(28.0)      # 27.90 -> nearest $0.25
    assert dish["delta"] == pytest.approx(4.0)          # derived from the SAME rounded figures
