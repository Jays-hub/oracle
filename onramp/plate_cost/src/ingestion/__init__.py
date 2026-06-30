"""
ingestion — Invoice Capture, OCR, and Entity Resolution
=========================================================
Phase 2 module. Turns raw invoices into PriceObservation rows via:
  1. Capture: photo upload or digital vendor feed
  2. Extraction: OCR line items → (raw_string, pack_size, pack_unit, price)
  3. Entity resolution: raw_string → ingredient_id with learned mappings +
     a human-confirmation queue for unresolved strings
  4. Write: new PriceObservation rows; history is always retained, never overwritten

This is the engineering wall. Budget for entity resolution edge cases.
The confirmation queue (human-in-the-loop, shrinks over time) is the tolerance mechanism —
never silently discard an unresolved string; always surface it for confirmation.

GATE: do not build this module until the Phase 2 competitive check is complete.
See plate_cost/CLAUDE.md § "GATE — before building the invoice layer".
"""
