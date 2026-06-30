"""Smoke tests for the web layer (web/app.py).

Covers: GET / returns 200, renders the grid with quadrant sections and
dollar figures, the sample-data banner is present, and the margin
derives from the rounded cost (the reconciliation discipline, rule 06).
"""
from fastapi.testclient import TestClient

from web.app import app

_client = TestClient(app)


def test_grid_returns_200():
    resp = _client.get("/")
    assert resp.status_code == 200


def test_grid_contains_quadrant_section():
    resp = _client.get("/")
    text = resp.text
    assert any(label in text for label in ("Stars", "Plowhorses", "Puzzles", "Dogs"))


def test_grid_contains_dollar_figure():
    resp = _client.get("/")
    assert "$" in resp.text


def test_sample_banner_present():
    """Sample-data label must be visible — no bare numbers dressed as validated results."""
    resp = _client.get("/")
    assert "sample" in resp.text.lower()


def test_margin_reconciles_with_rounded_cost():
    """For every dish rendered, Menu − ~Cost = Margin (reconciles by eye).

    Verifies the precision discipline from rule 06: the displayed margin must
    derive from the rounded cost, not the raw precise cost.
    """
    from web.compute import build_grid_data, round_to_quarter

    data = build_grid_data()
    for dish in data["rows"]:
        expected_margin = round(dish["menu_price"] - round_to_quarter(dish["menu_price"] - dish["margin_display"]), 10)
        assert abs(dish["margin_display"] - expected_margin) < 1e-9, (
            f"{dish['name']}: margin {dish['margin_display']:.4f} doesn't reconcile "
            f"with rounded cost {dish['cost_display']:.2f}"
        )


def test_static_file_reachable():
    resp = _client.get("/static/style.css")
    assert resp.status_code == 200
    assert "margin-amount" in resp.text


def test_clean_sample_data_has_no_skipped():
    """The clean sample data costs every dish — the skipped list is present and empty."""
    from web.compute import build_grid_data

    data = build_grid_data()
    assert data["skipped"] == []


def test_dish_rows_match_typed_contract():
    """Every rendered row carries exactly the DishRow keys — the compute→template contract holds."""
    from web.compute import DishRow, build_grid_data

    data = build_grid_data()
    expected = set(DishRow.__annotations__)
    assert data["rows"], "expected at least one costed dish in the sample data"
    for row in data["rows"]:
        assert set(row) == expected


def test_grid_failure_returns_legible_error(monkeypatch):
    """A compute failure yields a calm 503 with a correlation id — never a stack trace (rules 06/07).

    Internals (exception message, traceback, file paths) must stay server-side in the log.
    """
    import web.app as appmod

    def boom():
        raise RuntimeError("simulated: a sample file is missing at /secret/internal/path")

    monkeypatch.setattr(appmod, "build_grid_data", boom)
    resp = _client.get("/")

    assert resp.status_code == 503
    assert "Reference:" in resp.text
    # Internals must not leak to the client.
    assert "simulated" not in resp.text
    assert "/secret/internal/path" not in resp.text
    assert "Traceback" not in resp.text


def test_uncostable_dish_is_surfaced_not_dropped(monkeypatch):
    """A dish that fails to cost must be named in `skipped` and never vanish from the grid.

    Guards the silent-drop regression (rule 01 missingness report, rule 07 name-the-failure):
    the old `except ValueError: pass` dropped such dishes with no trace.
    """
    import web.compute as compute

    real_plate_cost = compute.plate_cost
    forced = {"name": None}

    def fake_plate_cost(dish, *args, **kwargs):
        if forced["name"] is None:
            forced["name"] = dish.name
            raise ValueError("forced: dangling ingredient reference")
        return real_plate_cost(dish, *args, **kwargs)

    monkeypatch.setattr(compute, "plate_cost", fake_plate_cost)
    data = compute.build_grid_data()

    skipped_names = [s["name"] for s in data["skipped"]]
    row_names = [r["name"] for r in data["rows"]]
    assert forced["name"] in skipped_names
    assert forced["name"] not in row_names
