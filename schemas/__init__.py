"""schemas/ — the single definition of every shape that crosses the seam (``data/CONTRACT.md``).

Platform-owned: imported by both peers, owned by neither. See ``seam.py`` for the row models
and the Gate-4 capture behind this module.
"""
from .seam import BomRow, SalesExportRow

__all__ = ["BomRow", "SalesExportRow"]
