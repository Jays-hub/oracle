"""Alembic environment — resolves the app-DB URL through src.db.engine (W5), never a second
hardcoded copy in alembic.ini, and points target_metadata at src.db.models.Base so
`alembic revision --autogenerate` compares against the real ORM models."""
import sys
from pathlib import Path
from logging.config import fileConfig

from alembic import context
from sqlalchemy import engine_from_config, pool

# migrations/env.py -> parents: [migrations, plate_cost]
_PLATE_COST_DIR = Path(__file__).resolve().parents[1]
if str(_PLATE_COST_DIR) not in sys.path:
    sys.path.insert(0, str(_PLATE_COST_DIR))

from src.db.engine import resolve_database_url  # noqa: E402 (after sys.path bootstrap)
from src.db.models import Base  # noqa: E402

config = context.config
if config.config_file_name is not None:
    # disable_existing_loggers=False: fileConfig()'s default (True) disables every logger in
    # the process that isn't explicitly named in alembic.ini's [loggers] section — harmless for
    # the standalone `alembic` CLI (a fresh process every time), but this env.py also runs
    # in-process whenever a test invokes alembic.command.upgrade() directly (test_db_engine.py),
    # where it would otherwise silently kill logging for the rest of the test session (e.g.
    # web.app's logger going permanently .disabled, breaking any later caplog-based assertion).
    fileConfig(config.config_file_name, disable_existing_loggers=False)

config.set_main_option("sqlalchemy.url", resolve_database_url())
target_metadata = Base.metadata


def run_migrations_offline() -> None:
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url, target_metadata=target_metadata, literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
