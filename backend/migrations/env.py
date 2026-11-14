"""
Alembic environment.

The database URL comes from DATABASE_URL (config.get_database_url), unless a
caller sets `sqlalchemy.url` on the Alembic Config (tests do, to target a
temporary database).
"""
from logging.config import fileConfig

from alembic import context
from sqlalchemy import create_engine

from config import get_database_url, normalize_database_url
from models import Base

config = context.config

# Callers that manage logging themselves (tests) set configure_logger to False
if config.config_file_name is not None and config.attributes.get("configure_logger", True):
    fileConfig(config.config_file_name, disable_existing_loggers=False)

target_metadata = Base.metadata


def _database_url() -> str:
    """URL of the database to migrate."""
    return normalize_database_url(config.get_main_option("sqlalchemy.url") or get_database_url())


def run_migrations_offline() -> None:
    """Emit the migration SQL to the script output without a database connection."""
    context.configure(
        url=_database_url(),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run the migrations against the database."""
    connectable = create_engine(_database_url())
    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)
        with context.begin_transaction():
            context.run_migrations()
    connectable.dispose()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
