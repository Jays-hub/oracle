"""Phase-4 newsvendor policy — turns a fitted quantile distribution into a prep
quantity, plus the expected-waste/expected-stockout integrals of that same
distribution (construction_roadmap.md Phase 4, "the product in miniature").

Deliberately decoupled from forecasting/src/models/quantile.py: every function
here only consumes long-format quantile-forecast rows
([business_date, item_id, service_period, quantile, forecast]) and each item's
(co, cu) — it does not know or care which model produced the quantiles ("model
delivers quantile, policy picks which quantile", Phase 4 Practices (a)).

critical_ratio() is a deliberate, one-line REIMPLEMENTATION of
evaluate/objective.py's function of the same name, not an import. `decision/` is
structurally forbidden from importing `evaluate/` (.importlinter's
engine-truth-firewall contract lists forecasting.src.decision as a source_module
forbidden from importing forecasting.src.evaluate), with exactly one existing,
narrowly-scoped carve-out (models.baselines -> evaluate.objective, see that
contract's own comment). Extending that carve-out to decision/ for a single,
permanently-stable one-line formula (q* = cu/(co+cu)) is a bigger structural
change than duplicating the formula — Anti-Drift favors the smaller, more local
fix, and the duplication risk is near-zero (this is closed-form microeconomics,
not a value that could silently drift out of sync).

Deriving waste/stockout from the distribution (the checkpoint's "five-line
argument", roadmap Phase 4): for a demand distribution with CDF F (F(0) = 0,
demand can't be negative) and prep quantity Q,
    E[(Q - D)^+] = integral_0^Q F(x) dx                       (expected waste)
    E[(D - Q)^+] = integral_Q^inf (1 - F(x)) dx                (expected stockout)
This module only has F at a finite set of fitted quantile levels, so F is
approximated as piecewise-linear between the fitted (value, level) points, with
an explicit (0, 0) floor anchor prepended. The integrals above become exact
trapezoidal-under-a-line sums over that piecewise-linear curve. The top fitted
quantile level (by default 0.99, see models/quantile.py's DEFAULT_QUANTILE_LEVELS)
is treated as the effective right tail of the distribution for expected_stockout
— true probability mass beyond it is assumed negligible, the standard practical
truncation for a demand distribution this concentrated. The approximation is
exact when the true CDF is itself piecewise-linear between the fitted points
(e.g. a uniform demand distribution — see test_newsvendor.py's hand-computed
correctness test) and tightens as the quantile grid is made finer elsewhere.
"""
from __future__ import annotations

import numpy as np
import pandas as pd


def critical_ratio(co: float, cu: float) -> float:
    """q* = Cu / (Co + Cu) — see evaluate/objective.py's function of the same name
    (this is a deliberate local duplicate, not an import; see module docstring)."""
    if co <= 0 or cu <= 0:
        raise ValueError(f"co and cu must both be positive; got co={co}, cu={cu}")
    return cu / (co + cu)


def route_batch_items(items: dict) -> dict:
    """Filter to `prep_type == "batch"` items — rule 04-deployment.md's Prep-Type
    Routing: the dish-count newsvendor (critical_ratio/prep_quantity) applies to
    batch items ONLY. `made_to_order` items route to ingredient par-level logic
    (Phase 7) and must never receive a "make N portions" read-off (P4_review.md
    MINOR-3 — the first build applied prep_quantity to all 11 configured items,
    including the 4 made_to_order ones, which also carry the highest critical
    ratios and so skewed the reported gate number).

    Compares against the plain string "batch" (not `config.PrepType`) so this
    module keeps its existing no-`config.py`-import convention (see module
    docstring) — `config.PrepType` is a `str, Enum` subclass, so `eco.prep_type ==
    "batch"` is true for a real `ItemEconomics.prep_type` without importing the
    enum. `items`: item_id -> object exposing `.prep_type` (e.g.
    `config.ItemEconomics`).
    """
    return {item_id: eco for item_id, eco in items.items() if eco.prep_type == "batch"}


def required_quantile_levels(
    items: dict,
    standard_grid: tuple[float, ...] = (0.05, 0.10, 0.25, 0.50, 0.75, 0.90, 0.95, 0.99),
) -> list[float]:
    """The quantile levels a model must be fit at to serve every item's newsvendor
    read-off EXACTLY (no interpolation needed at q*) — rule 03-model-training.md:
    "a set of quantile forecasts covering [0.10, 0.25, 0.50, 0.75, 0.90, q*]."

    Returns the sorted, de-duplicated union of standard_grid and every item's own
    critical ratio. `items`: item_id -> object exposing `.co`/`.cu` (e.g.
    config.ItemEconomics) — passed in, never loaded from config.py here, matching
    the rest of the engine's convention of receiving `items` as a parameter
    (RollingOriginBacktest.run(), score_predictions(), etc.).
    """
    levels = {round(float(q), 6) for q in standard_grid}
    for eco in items.values():
        levels.add(round(critical_ratio(eco.co, eco.cu), 6))
    return sorted(levels)


def quantile_curve(quantile_forecasts: pd.DataFrame) -> tuple[np.ndarray, np.ndarray]:
    """Build the (x, F(x)) anchor points for ONE item-day's fitted quantile curve.

    `quantile_forecasts` must already be filtered to a single (business_date,
    item_id, service_period) — every row in it is treated as one point on the
    same curve. An explicit (0, 0) floor anchor is prepended (demand cannot be
    negative); skipped if the lowest fitted point is already at 0. Public — reused
    by forecasting/src/evaluate/calibration.py's PIT computation (evaluate/ may
    import decision/; only the reverse is forbidden).

    Raises ValueError if the forecasts are not non-crossing (models/quantile.py's
    predict_quantiles() already guarantees this on its own output; this is a
    second line of defense for any other caller).
    """
    sub = quantile_forecasts.sort_values("quantile")
    qs = sub["quantile"].to_numpy(dtype=float)
    xs = sub["forecast"].to_numpy(dtype=float)
    if len(xs) == 0:
        raise ValueError("quantile_curve: quantile_forecasts is empty")
    if np.any(np.diff(xs) < -1e-9):
        raise ValueError(
            "quantile_curve: forecasts must be non-crossing (non-decreasing in quantile)"
        )
    if xs[0] > 0:
        xs = np.concatenate(([0.0], xs))
        qs = np.concatenate(([0.0], qs))
    return xs, qs


def prep_quantity(quantile_forecasts: pd.DataFrame, r: float) -> float:
    """F^{-1}(r): the newsvendor-optimal prep quantity for one item-day.

    Linearly interpolated between the two fitted quantile levels bracketing r;
    EXACT (not interpolated) when r is itself one of the fitted levels —
    guaranteed for every item's own critical ratio when the model was fit via
    required_quantile_levels(). Clamped to the fitted grid's range at the ends.
    """
    if not 0.0 < r < 1.0:
        raise ValueError(f"r must lie strictly in (0, 1); got {r}")
    xs, qs = quantile_curve(quantile_forecasts)
    return float(np.interp(r, qs, xs))


def _integrate_cdf(xs: np.ndarray, qs: np.ndarray, hi: float) -> float:
    """integral_{xs[0]}^{hi} F(x) dx over the piecewise-linear curve (xs, qs),
    clipping hi into [xs[0], xs[-1]]."""
    hi_c = min(max(hi, xs[0]), xs[-1])
    total = 0.0
    for i in range(len(xs) - 1):
        x0, x1 = xs[i], xs[i + 1]
        if hi_c <= x0:
            break
        q0, q1 = qs[i], qs[i + 1]
        seg_hi = min(hi_c, x1)
        width = seg_hi - x0
        slope = (q1 - q0) / (x1 - x0) if x1 > x0 else 0.0
        # integral of the line q0 + slope*(x - x0) from x0 to seg_hi
        total += q0 * width + slope * width**2 / 2.0
    return total


def expected_waste(quantile_forecasts: pd.DataFrame, prep_qty: float) -> float:
    """E[max(Q - D, 0)] for one item-day's fitted quantile curve — see module
    docstring "Deriving waste/stockout" for the derivation. Non-negative by
    construction; 0 when prep_qty is at or below the distribution's floor.
    """
    xs, qs = quantile_curve(quantile_forecasts)
    if prep_qty <= xs[0]:
        return 0.0
    return _integrate_cdf(xs, qs, prep_qty)


def expected_stockout(quantile_forecasts: pd.DataFrame, prep_qty: float) -> float:
    """E[max(D - Q, 0)] for one item-day's fitted quantile curve — see module
    docstring "Deriving waste/stockout" for the derivation. The top fitted
    quantile level is treated as the effective right tail (F ~= 1 there); 0 when
    prep_qty already reaches or exceeds it.

    KNOWN DOWNWARD BIAS (P4_review.md MINOR-4, builder-acknowledged, not fixed —
    no operator-facing surface reads this yet, see below): truncating F at the top
    fitted level (0.99 by default) drops the true probability mass beyond it, so
    the returned value is systematically an UNDER-estimate of the real expected
    stockout — worst near the truncation boundary itself (measured in
    test_newsvendor.py: ~1% relative error at Q=90 against a grid truncated at 99,
    vs. <0.1% error at interior points), and negligible for an item whose critical
    ratio sits well inside [0.05, 0.95] (true for all 11 real items today — the
    widest is 0.8125). NOT used by the P4 dollar gate (only prep_quantity() feeds
    it) — this only touches the "free waste/stockout byproduct" pitched to the
    chef. Do not surface this number to an operator (Phase 8's prep sheet) without
    either widening/re-anchoring the grid for that item's q* or documenting the
    bias alongside the figure — see docs/phase_decisions/P4.md "Explicitly
    Deferred".
    """
    xs, qs = quantile_curve(quantile_forecasts)
    x_max = xs[-1]
    if prep_qty >= x_max:
        return 0.0
    prep_c = max(prep_qty, xs[0])
    total_tail = (x_max - xs[0]) - _integrate_cdf(xs, qs, x_max)
    waste_to_prep = (prep_c - xs[0]) - _integrate_cdf(xs, qs, prep_c)
    return total_tail - waste_to_prep
