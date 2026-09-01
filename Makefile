## Makefile — canonical entry points for test/lint.
## pytest + ruff live ONLY in the `restaurant-dev` conda env (not `base`), so every
## target below hard-codes `conda run -n restaurant-dev` — the wrong env is
## structurally unavailable. See docs/agentic_workflow/efficiency_backlog.md #1.

CONDA_ENV := restaurant-dev
RUN := conda run -n $(CONDA_ENV)

.PHONY: test lint check import-lint migrate serve serve

test:
	$(RUN) python -m pytest -q

lint:
	$(RUN) ruff check .

import-lint:
	$(RUN) lint-imports

check: lint import-lint test

# Applies the app-DB migrations (W5) to whatever ONRAMP_DATABASE_URL points at (a local
# gitignored SQLite file by default). Runs from the repo root since the layer restructure:
# alembic.ini sits there now, alongside every other entry point, so there is no cd to get wrong.
migrate:
	$(RUN) alembic upgrade head

# The operator-facing web app (L4). The repo root is the import root for every layer package,
# so this is run from the root too — no sys.path bootstrap, no working-directory dependence.
serve:
	$(RUN) python -m surface.web
