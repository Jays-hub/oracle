"""The on-ramp's application database (W5) — on-ramp-private, never the seam.

See ``docs/website_production_overview.md`` §3: this is the "designated database" that holds
users, restaurants, credentials, sessions, and staged uploads. ``forecasting/`` never reads it
and never knows it exists; the only coupling between the two peers stays ``data/raw/**``.
"""
