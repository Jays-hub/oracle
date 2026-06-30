"""On-ramp DuckDB access module.

Reads only data/raw/**. Structurally incapable of opening any path outside data/raw/ —
the path is hard-coded, not parameterized. The on-ramp owns this helper; it does not import the
engine's future forecasting/src/data/store.py. The shared artifact is the files + schemas/, never
the helper code. (docs/common_base_reconciliation.md, .claude/rules/05-fullstack-architecture.md)
"""
from pathlib import Path

import duckdb
import pandas as pd

# onramp/plate_cost/src/store.py → parents: [src, plate_cost, onramp, repo-root]
_RAW_DIR = Path(__file__).resolve().parents[3] / "data" / "raw"

# Fail loudly at import time if the path invariant breaks — not a runtime check that can be
# silently skipped, a module-load assertion that fires in every test run and every deploy.
assert _RAW_DIR.parts[-2:] == ("data", "raw"), (
    f"Store helper path invariant violated: expected .../data/raw, got {_RAW_DIR}"
)


def _read_raw_parquet(filename: str) -> pd.DataFrame:
    """Read one seam file from data/raw/ by bare filename.

    - Takes a *filename*, never a path: it can only ever resolve under the hard-coded _RAW_DIR,
      so the helper stays structurally incapable of opening another data layer (the assert is
      defense-in-depth against a future caller passing a traversal string).
    - Parameterized query: the path is bound, never f-string-interpolated into SQL.
    - Fails legibly if the file is missing (rule 07), not with a raw DuckDB IO error.
    - Context-managed connection: closed even if the read raises.
    """
    assert "/" not in filename and "\\" not in filename and ".." not in filename, (
        f"_read_raw_parquet takes a bare filename, not a path: {filename!r}"
    )
    path = _RAW_DIR / filename
    if not path.exists():
        raise FileNotFoundError(
            f"Seam file not found: data/raw/{filename}. "
            "Run the on-ramp export first: `python -m src.run` from onramp/plate_cost/."
        )
    with duckdb.connect() as con:
        return con.execute("SELECT * FROM read_parquet(?)", [str(path)]).df()


def read_bom() -> pd.DataFrame:
    """BOM seam leg from data/raw/bom.parquet."""
    return _read_raw_parquet("bom.parquet")


def read_sales() -> pd.DataFrame:
    """Sales-export seam leg from data/raw/sales_export.parquet."""
    return _read_raw_parquet("sales_export.parquet")
