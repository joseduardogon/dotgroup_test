"""Alembic environment: wires migrations to the application metadata and settings."""

from logging.config import fileConfig

from alembic import context
from sqlalchemy import Connection

import library_api.models
from library_api.core.config import get_settings
from library_api.db.base import Base
from library_api.db.session import create_db_engine

config = context.config
if config.config_file_name is not None and config.attributes.get("configure_logger", True):
    fileConfig(config.config_file_name, disable_existing_loggers=False)

target_metadata = Base.metadata


def _database_url() -> str:
    """Resolve the target database URL.

    An explicit ``sqlalchemy.url`` (used by tests and one-off tooling) wins over
    the application settings.

    Returns:
        A SQLAlchemy URL string.
    """
    return config.get_main_option("sqlalchemy.url") or get_settings().database_url


def _configure_and_run(connection: Connection) -> None:
    """Run migrations on ``connection`` with SQLite-friendly options.

    ``render_as_batch`` makes ALTER operations work on SQLite by recreating tables.

    Args:
        connection: Open connection to migrate.
    """
    context.configure(
        connection=connection,
        target_metadata=target_metadata,
        render_as_batch=True,
        compare_type=True,
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_offline() -> None:
    """Emit migration SQL to stdout without connecting to the database."""
    context.configure(
        url=_database_url(),
        target_metadata=target_metadata,
        literal_binds=True,
        render_as_batch=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Apply migrations against a live database."""
    engine = create_db_engine(_database_url())
    try:
        with engine.connect() as connection:
            _configure_and_run(connection)
    finally:
        engine.dispose()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
