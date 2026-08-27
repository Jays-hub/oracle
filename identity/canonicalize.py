"""L1 canonicalization — the identity layer's current, deliberately minimal implementation.

`normalize_name` is the whole of entity resolution in this repo today. It lived in the on-ramp's
report module until the layer restructure; it is identity code, and `identity/__init__.py`'s spec
already named it as such ("Identity across both peers is currently ``name.strip().casefold()``").
Homing it here makes that statement structural rather than a docstring, and gives R2–R6 an obvious
place to replace it — every caller already imports canonicalization from the identity layer.

The known failure is recorded in `identity/__init__.py`: this is correct for a chef's hand-typed
recipe sheet and wrong on the first real invoice, where ``TOMATO ROMA 25# CS`` and
``Tomatoes, Roma, 25 lb`` casefold to two distinct ids.
"""


def normalize_name(name: str) -> str:
    """Canonical key for joining a menu item to its sales rows: trim surrounding whitespace and
    casefold, so 'Braised Short Rib ' and 'braised short rib' match instead of silently scoring 0
    covers — which would drop a popular dish into the 'Dog' quadrant by mislabel alone."""
    return name.strip().casefold()
