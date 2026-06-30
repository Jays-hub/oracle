"""Dollar objective for the prep-demand newsvendor.

Realized cost = Σ over items: Co·max(0, prep−demand) + Cu·max(0, demand−prep)

This is the ONLY metric that determines whether a model ships. MAPE/RMSE are
diagnostics; dollar_loss is the verdict. (.claude/rules/03-model-training.md)

The critical ratio q* = Cu / (Co + Cu) is the service level that minimizes
expected dollar_loss. The optimal prep quantity is F^{-1}(q*), where F is the
item's demand CDF. This derivation is in forecasting/docs/conceptual_spine.md.
Config values (Co, Cu per item) live in config/items.yaml.
"""
from __future__ import annotations

import numpy as np


def _require_positive_costs(co: float, cu: float) -> None:
    """Co and Cu parameterize both the loss function and the critical ratio; a zero or
    negative cost makes both meaningless (and would let a wrong dollar verdict pass silently).
    Reject loudly at every public entry point — the same gate, applied consistently."""
    if co <= 0 or cu <= 0:
        raise ValueError(f"Co and Cu must both be positive; got Co={co}, Cu={cu}")


def dollar_loss(
    prep: float | np.ndarray,
    demand: float | np.ndarray,
    co: float,
    cu: float,
) -> float | np.ndarray:
    """Realized newsvendor cost for one item-day, or a vectorized array.

    Parameters
    ----------
    prep:   quantity prepped (scalar or array)
    demand: quantity demanded (scalar or array)
    co:     overage cost per unsold unit (food cost of one wasted portion)
    cu:     underage cost per stockout (contribution margin lost on one missed sale)

    Returns
    -------
    A plain ``float`` for scalar inputs, an ``ndarray`` for array inputs. Always >= 0.
    """
    _require_positive_costs(co, cu)
    prep_arr = np.asarray(prep, dtype=float)
    demand_arr = np.asarray(demand, dtype=float)
    overage = np.maximum(0.0, prep_arr - demand_arr)
    underage = np.maximum(0.0, demand_arr - prep_arr)
    loss = co * overage + cu * underage
    # Scalar in -> scalar out: a 0-d result is np.float64, which leaks into callers and
    # mismatches the annotated return type. Hand back a plain float for the scalar case.
    return float(loss) if np.ndim(loss) == 0 else loss


def critical_ratio(co: float, cu: float) -> float:
    """Optimal service level: q* = Cu / (Co + Cu).

    Prep at F^{-1}(q*) to minimise expected dollar_loss.
    A higher q* means prep above the median — correct when running out (Cu)
    costs more than over-prepping (Co). Config values live in config/items.yaml.
    """
    _require_positive_costs(co, cu)
    return cu / (co + cu)


def total_realized_cost(
    preps: np.ndarray,
    demands: np.ndarray,
    co: float,
    cu: float,
) -> float:
    """Sum of dollar_loss across a vector of item-days. The backtest's bottom line."""
    return float(np.sum(dollar_loss(preps, demands, co, cu)))
