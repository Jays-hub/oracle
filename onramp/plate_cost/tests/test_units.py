"""Regression tests for the units refactor (task #7): in-family conversions are symmetric and
complete; cross-family and count conversions are refused."""
import pytest

from src.bom.units import convert


def test_identity():
    assert convert(5.0, "oz", "oz") == 5.0


def test_weight_symmetry_roundtrip():
    oz = convert(2.0, "lb", "oz")
    assert oz == pytest.approx(32.0)
    assert convert(oz, "oz", "lb") == pytest.approx(2.0)


def test_cross_unit_within_family_now_works():
    # lb<->kg was impossible in the old hand-listed table; derived base factors make it work.
    assert convert(1.0, "kg", "g") == pytest.approx(1000.0, rel=1e-3)


def test_volume_conversion():
    assert convert(1.0, "cup", "tbsp") == pytest.approx(16.0)


def test_cross_family_refused():
    with pytest.raises(ValueError):
        convert(1.0, "oz", "fl oz")  # weight -> volume


def test_count_unit_refused():
    with pytest.raises(ValueError):
        convert(1.0, "each", "oz")
