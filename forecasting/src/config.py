"""Engine economics config — the validated load path for ``config/items.yaml``.

``config/items.yaml`` carries the per-item newsvendor economics (Co, Cu, prep_type,
lead_time) the engine optimizes against. These are **engine-only** — the on-ramp never
reads them — so they live here, not in the shared ``schemas/`` (which describes the seam
both peers cross).

This module is the **head-chef gate** for the engine's own config: every item is validated
(positive costs, a known ``prep_type``, no stray keys, no duplicate ids/names) before any
downstream phase reads it. A bad value fails loudly here — named by item and field — rather
than silently corrupting the dollar verdict (``q* = Cu/(Co+Cu)`` and the whole objective)
deep inside P1+. Mirrors the seam gate in ``schemas/seam.py``.

Read by ``forecasting/src/evaluate/`` (dollar scoring) and the future
``forecasting/src/decision/`` (prep_type routing). Lives at ``src/`` top level on purpose —
**not** ``src/data/``, whose contract is "reads ONLY data/raw/"; this reads ``config/``.
"""
from __future__ import annotations

from enum import Enum
from pathlib import Path

import yaml
from pydantic import BaseModel, ConfigDict, Field, ValidationError

# src/config.py -> parents: [src, forecasting, repo-root]; the config dir is repo-root-owned.
_DEFAULT_ITEMS_PATH = Path(__file__).resolve().parents[2] / "config" / "items.yaml"


class PrepType(str, Enum):
    """How an item is prepped — sets which decision object it gets (.claude/rules/04).

    ``batch`` → dish-count newsvendor; appears on the prep sheet.
    ``made_to_order`` → ingredient par-level only; never a "make N" line on the sheet.
    Chef-set, never inferred — so an unknown value is a rejection, not a default.
    """

    BATCH = "batch"
    MADE_TO_ORDER = "made_to_order"


class ItemEconomics(BaseModel):
    """One validated entry of ``config/items.yaml``'s ``items:`` list.

    ``extra="forbid"``: a typo'd key (``prep:`` instead of ``prep_type:``) is a rejection,
    not a silently-ignored field — the failure mode this gate exists to stop. Costs must be
    strictly positive; a zero/negative Co or Cu makes the critical ratio and the dollar
    objective meaningless.
    """

    model_config = ConfigDict(extra="forbid")

    id: str = Field(min_length=1)
    name: str = Field(min_length=1)
    prep_type: PrepType
    co: float = Field(gt=0.0)          # overage cost per unsold portion (food cost wasted)
    cu: float = Field(gt=0.0)          # underage cost per stockout (contribution margin lost)
    lead_time_days: int = Field(ge=1)  # the prep decision is made >= 1 day ahead
    notes: str | None = None


def _norm(name: str) -> str:
    """Trim + casefold, for duplicate-name detection. Reimplemented locally (a one-liner)
    rather than imported from the on-ramp — the engine peer must never import ``onramp/``."""
    return name.strip().casefold()


def load_items(path: Path | None = None) -> dict[str, ItemEconomics]:
    """Load and validate ``config/items.yaml``, returning items keyed by ``id``.

    The head-chef gate: nothing downstream sees an item that didn't pass. Raises
    ``FileNotFoundError`` if the file is missing, or ``ValueError`` (named by item and
    field) on a malformed entry, a duplicate id/name, or a structurally wrong file.
    """
    path = path or _DEFAULT_ITEMS_PATH
    if not path.exists():
        raise FileNotFoundError(f"Items config not found: {path}")

    raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict) or "items" not in raw:
        raise ValueError(f"{path.name}: expected a top-level 'items:' key; got {type(raw).__name__}")
    raw_items = raw["items"]
    if not isinstance(raw_items, list) or not raw_items:
        raise ValueError(f"{path.name}: 'items' must be a non-empty list")

    items: dict[str, ItemEconomics] = {}
    seen_names: dict[str, str] = {}  # normalized name -> id, for duplicate detection
    for idx, entry in enumerate(raw_items):
        if not isinstance(entry, dict):
            raise ValueError(f"{path.name}: item #{idx} is not a mapping")
        try:
            item = ItemEconomics(**entry)
        except ValidationError as e:
            label = entry.get("name") or entry.get("id") or f"#{idx}"
            raise ValueError(f"{path.name}: item '{label}' failed validation:\n{e}") from e

        if item.id in items:
            raise ValueError(f"{path.name}: duplicate item id '{item.id}'")
        norm = _norm(item.name)
        if norm in seen_names:
            raise ValueError(
                f"{path.name}: duplicate item name '{item.name}' "
                f"(ids '{seen_names[norm]}' and '{item.id}')"
            )
        seen_names[norm] = item.id
        items[item.id] = item
    return items
