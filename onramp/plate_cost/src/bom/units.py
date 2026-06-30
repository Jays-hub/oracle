"""Recipe-unit -> canonical-unit conversion.

Each unit is expressed as a multiple of its family's canonical base (weight -> oz, volume -> fl oz),
so every in-family conversion is *derived* and symmetric (lb<->oz, kg<->g, cup<->tbsp, ...) instead
of hand-listing pairs that drift out of sync. Count units (each, clove, ...) belong to no family:
they convert only to themselves. Cross-family conversion (weight <-> volume) is refused.
"""

# Weight units, expressed in ounces.
_WEIGHT_IN_OZ: dict[str, float] = {
    "oz": 1.0,
    "lb": 16.0,
    "kg": 35.274,
    "g": 0.035274,
}

# Volume units, expressed in fluid ounces.
_VOLUME_IN_FLOZ: dict[str, float] = {
    "fl oz": 1.0,
    "cup": 8.0,
    "pint": 16.0,
    "qt": 32.0,
    "gal": 128.0,
    "tbsp": 0.5,
    "tsp": 1.0 / 6.0,
    "l": 33.814,
    "ml": 0.033814,
}

_FAMILIES: tuple[dict[str, float], ...] = (_WEIGHT_IN_OZ, _VOLUME_IN_FLOZ)


def convert(qty: float, from_unit: str, to_unit: str) -> float:
    from_unit = from_unit.lower().strip()
    to_unit = to_unit.lower().strip()
    if from_unit == to_unit:
        return qty
    for family in _FAMILIES:
        if from_unit in family and to_unit in family:
            return qty * family[from_unit] / family[to_unit]
    raise ValueError(
        f"No conversion from '{from_unit}' to '{to_unit}'. Units must share a measurement family "
        "(weight or volume); count units (each, clove) convert only to themselves. "
        "Add the unit to units.py or align recipe_unit with canonical_unit."
    )
