"""Tests for the engine economics config gate (forecasting/src/config.py).

The head-chef gate for config/items.yaml: good config loads; every category of malformed
config is rejected loudly, named by item. Mirrors tests/test_seam_schemas.py for the seam.
"""
import textwrap
from pathlib import Path

import pytest
from pydantic import ValidationError

from forecasting.src.config import ItemEconomics, PrepType, load_items


# --- ItemEconomics model: accept / reject ---

def _item(**over):
    base = dict(
        id="braised_short_rib", name="Braised Short Rib", prep_type="batch",
        co=14.0, cu=28.0, lead_time_days=1,
    )
    base.update(over)
    return base


def test_item_accepts_valid():
    item = ItemEconomics(**_item())
    assert item.prep_type is PrepType.BATCH
    assert item.co == 14.0


def test_item_accepts_made_to_order():
    item = ItemEconomics(**_item(id="classic_caesar_salad", name="Caesar", prep_type="made_to_order"))
    assert item.prep_type is PrepType.MADE_TO_ORDER


@pytest.mark.parametrize("bad", [
    {"prep_type": "Batch"},        # wrong case — not an enum member
    {"prep_type": "braise"},       # unknown prep_type (never inferred — rule 04)
    {"co": 0.0},                   # cost must be > 0
    {"co": -14.0},                 # negative cost is meaningless
    {"cu": 0.0},                   # cost must be > 0
    {"lead_time_days": 0},         # must decide >= 1 day ahead
    {"name": ""},                  # required, non-empty
    {"id": ""},                    # required, non-empty
    {"prp_type": "batch"},         # typo'd key -> extra="forbid" rejects
])
def test_item_rejects_bad(bad):
    with pytest.raises(ValidationError):
        ItemEconomics(**_item(**bad))


# --- load_items on the shipped config ---

def test_shipped_config_loads_all_11():
    items = load_items()
    assert len(items) == 11
    assert items["braised_short_rib"].prep_type is PrepType.BATCH
    assert items["classic_caesar_salad"].prep_type is PrepType.MADE_TO_ORDER


def test_shipped_config_costs_all_positive():
    for item in load_items().values():
        assert item.co > 0
        assert item.cu > 0
        assert item.lead_time_days >= 1


# --- load_items: structural and duplicate rejection ---

def _write(tmp_path: Path, body: str) -> Path:
    p = tmp_path / "items.yaml"
    p.write_text(textwrap.dedent(body), encoding="utf-8")
    return p


def test_load_rejects_duplicate_id(tmp_path):
    p = _write(tmp_path, """
        items:
          - {id: a, name: Alpha, prep_type: batch, co: 1.0, cu: 2.0, lead_time_days: 1}
          - {id: a, name: Beta,  prep_type: batch, co: 1.0, cu: 2.0, lead_time_days: 1}
    """)
    with pytest.raises(ValueError, match="duplicate item id"):
        load_items(p)


def test_load_rejects_duplicate_name_normalized(tmp_path):
    # "Short Rib" vs "short rib " (case + trailing space) collide under normalization.
    p = _write(tmp_path, """
        items:
          - {id: a, name: Short Rib,   prep_type: batch, co: 1.0, cu: 2.0, lead_time_days: 1}
          - {id: b, name: 'short rib ', prep_type: batch, co: 1.0, cu: 2.0, lead_time_days: 1}
    """)
    with pytest.raises(ValueError, match="duplicate item name"):
        load_items(p)


def test_load_names_the_failing_item(tmp_path):
    p = _write(tmp_path, """
        items:
          - {id: a, name: Alpha, prep_type: batch, co: -1.0, cu: 2.0, lead_time_days: 1}
    """)
    with pytest.raises(ValueError, match="Alpha"):
        load_items(p)


def test_load_rejects_missing_items_key(tmp_path):
    p = _write(tmp_path, "foo: bar\n")
    with pytest.raises(ValueError, match="items"):
        load_items(p)


def test_load_rejects_empty_items_list(tmp_path):
    p = _write(tmp_path, "items: []\n")
    with pytest.raises(ValueError, match="non-empty"):
        load_items(p)


def test_load_missing_file_raises(tmp_path):
    with pytest.raises(FileNotFoundError):
        load_items(tmp_path / "nope.yaml")
