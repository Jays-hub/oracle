"""On-ramp DuckDB access module.

Reads only data/raw/**. Structurally incapable of opening any path outside data/raw/ —
the base path is hard-coded, not parameterized; only a validated tenant segment beneath it varies.
The on-ramp owns this helper; it does not import the engine's future
forecasting/src/data/store.py. The shared artifact is the files + schemas/, never the helper code.
(docs/common_base_reconciliation.md, .claude/rules/05-fullstack-architecture.md)

RAW_DIR is the ONE canonical definition of the seam directory — src/capture/seam_upload.py
re-exports it (``from ..store import RAW_DIR``) rather than computing its own copy, and
web/app.py's write routes call ``store.tenant_raw_dir(identity.restaurant_id)`` (never ``RAW_DIR``
bare, since W9). Previously the read side (this module's own ``_RAW_DIR``) and the write side
(seam_upload's independently-computed ``RAW_DIR``) were two separate module-level constants that
happened to agree in production but had to be monkeypatched independently in tests
(W3_review.md LOW-1) — a single source collapses that to one patch point and one path-derivation
formula to keep in sync.

Tenant partitioning (W9, speculative — data/CONTRACT.md): ``data/raw/`` is a container of one
subdirectory per ``restaurant_id`` (the app-DB's ``Restaurant.id``), not itself a set of files
anymore. Every read function below now requires ``restaurant_id`` and resolves it through
``tenant_raw_dir()`` before touching the filesystem.
"""
import re
from pathlib import Path

import duckdb
import pandas as pd

# onramp/plate_cost/src/store.py → parents: [src, plate_cost, onramp, repo-root]
RAW_DIR = Path(__file__).resolve().parents[3] / "data" / "raw"

# Fail loudly at import time if the path invariant breaks — an explicit check (not `assert`, which
# `python -O` strips) so it fires in every test run and every deploy, optimized or not.
if RAW_DIR.parts[-2:] != ("data", "raw"):
    raise RuntimeError(f"Store helper path invariant violated: expected .../data/raw, got {RAW_DIR}")

# A real restaurant_id is always a Restaurant.id (uuid.uuid4().hex, src/db/models.py) or the
# fixed demo/simulation sentinel (data/CONTRACT.md) — both are alphanumeric. This pattern is
# deliberately a permissive path-safe slug, not a strict UUID parse: it exists to keep an
# arbitrary caller-supplied string from ever becoming a traversal (`..`, `/`, `\`, a null byte),
# not to enforce that every id looks like a UUID.
_RESTAURANT_ID_PATTERN = re.compile(r"[A-Za-z0-9_-]{1,64}\Z")


def tenant_raw_dir(restaurant_id: str) -> Path:
    """Resolve one tenant's seam subdirectory under RAW_DIR, validating restaurant_id first.

    This is the ONE place a caller-supplied string becomes a filesystem path in this module —
    every read/write below either takes this function's return value directly or (for the write
    side, src/capture/*.py) is handed it by web/app.py. Raises ValueError, never silently
    coerces, on anything that isn't a bare path-safe segment (rule 07: hostile until validated).
    """
    if not _RESTAURANT_ID_PATTERN.match(restaurant_id):
        raise ValueError(f"invalid restaurant_id for a seam path: {restaurant_id!r}")
    path = RAW_DIR / restaurant_id
    if path.parent != RAW_DIR:
        raise RuntimeError(f"tenant_raw_dir escaped RAW_DIR: {path}")
    return path


def _read_raw_parquet(base_dir: Path, filename: str) -> pd.DataFrame:
    """Read one seam file from a tenant's subdirectory by bare filename.

    - Takes a *filename*, never a path: combined with ``base_dir`` always being a
      ``tenant_raw_dir()`` result, the helper stays structurally incapable of opening another
      data layer (the check below is defense-in-depth against a future caller passing a
      traversal string as the filename).
    - Parameterized query: the path is bound, never f-string-interpolated into SQL.
    - Fails legibly if the file is missing (rule 07), not with a raw DuckDB IO error.
    - Context-managed connection: closed even if the read raises.
    """
    if "/" in filename or "\\" in filename or ".." in filename:
        raise RuntimeError(f"_read_raw_parquet takes a bare filename, not a path: {filename!r}")
    path = base_dir / filename
    if not path.exists():
        raise FileNotFoundError(
            f"Seam file not found: data/raw/{base_dir.name}/{filename}. "
            "Run the on-ramp export first: `python -m src.run` from onramp/plate_cost/."
        )
    with duckdb.connect() as con:
        return con.execute("SELECT * FROM read_parquet(?)", [str(path)]).df()


def read_bom(restaurant_id: str) -> pd.DataFrame:
    """BOM seam leg from data/raw/<restaurant_id>/bom.parquet."""
    return _read_raw_parquet(tenant_raw_dir(restaurant_id), "bom.parquet")


def read_sales(restaurant_id: str) -> pd.DataFrame:
    """Sales-export seam leg from data/raw/<restaurant_id>/sales_export.parquet."""
    return _read_raw_parquet(tenant_raw_dir(restaurant_id), "sales_export.parquet")


def read_price_observations(restaurant_id: str) -> pd.DataFrame:
    """Invoice/price-history seam leg from data/raw/<restaurant_id>/price_observations.parquet (W3)."""
    return _read_raw_parquet(tenant_raw_dir(restaurant_id), "price_observations.parquet")


def read_food_cost(restaurant_id: str) -> pd.DataFrame:
    """Derived per-dish food-cost seam leg from data/raw/<restaurant_id>/food_cost.parquet (W6) --
    read back so /your-data can disclose the leg it now sends the engine (W6_review.md MAJOR-1)."""
    return _read_raw_parquet(tenant_raw_dir(restaurant_id), "food_cost.parquet")
