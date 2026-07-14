## Makefile — canonical entry points for test/lint.
## pytest + ruff live ONLY in the `restaurant-dev` conda env (not `base`), so every
## target below hard-codes `conda run -n restaurant-dev` — the wrong env is
## structurally unavailable. See docs/agentic_workflow/efficiency_backlog.md #1.

CONDA_ENV := restaurant-dev
RUN := conda run -n $(CONDA_ENV)

.PHONY: test lint check import-lint migrate

test:
	$(RUN) python -m pytest -q

lint:
	$(RUN) ruff check .

import-lint:
	$(RUN) lint-imports

check: lint import-lint test

# Applies the on-ramp app-DB migrations (W5) to whatever ONRAMP_DATABASE_URL points at (a
# local gitignored SQLite file by default). cd'd into onramp/plate_cost/ because alembic.ini's
# script_location is relative to that directory (matches how `python -m web` is also run from
# there).
migrate:
	cd onramp/plate_cost && $(RUN) alembic upgrade head
