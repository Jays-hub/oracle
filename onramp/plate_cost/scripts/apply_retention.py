#!/usr/bin/env python
"""CLI: prune ``data/raw/price_observations.parquet`` to the retention window (W7).

Run periodically (e.g. monthly) once a real deploy exists — this script records the *policy*
and does the pruning mechanics; wiring an actual scheduler (cron, a hosting platform's
scheduled-job feature) is a hosting-platform concern, not this script's
(``docs/phase_decisions/W7.md``). Run from ``onramp/plate_cost/``::

    python scripts/apply_retention.py
"""
from __future__ import annotations

import sys
from pathlib import Path

_PLATE_COST_DIR = Path(__file__).resolve().parents[1]
if str(_PLATE_COST_DIR) not in sys.path:
    sys.path.insert(0, str(_PLATE_COST_DIR))

from src import store  # noqa: E402
from src.pricing.retention import DEFAULT_RETENTION_DAYS, prune_price_observations_atomic  # noqa: E402


def main(argv: list[str] | None = None) -> int:
    before, after = prune_price_observations_atomic(store.RAW_DIR)
    if before == 0:
        print("No price_observations.parquet yet — nothing to prune.")
    elif before == after:
        print(
            f"All {before} rows are within the {DEFAULT_RETENTION_DAYS}-day retention "
            "window — nothing pruned."
        )
    else:
        print(
            f"Pruned {before - after} row(s); {after} of {before} kept "
            f"(retention: {DEFAULT_RETENTION_DAYS} days)."
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
