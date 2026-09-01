"""costing — the W6 costed reveal over the operator's own captured data.

``menu_prices.py`` is the DB-aware menu-price catalog (no FastAPI import — ``web/menu_prices.py``
is the only caller that knows about HTTP). ``tenant_grid.py`` is pure compute: the real-tenant
popularity x margin grid, the dish-detail line items, and the derived ``food_cost`` seam leg that
closes ``data/CONTRACT.md``'s "Co provenance" forward note.
"""
