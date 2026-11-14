"""
Alembic migrations, run on a temporary SQLite file.
"""
from pathlib import Path

import pytest
from alembic import command
from alembic.autogenerate import compare_metadata
from alembic.config import Config
from alembic.migration import MigrationContext
from sqlalchemy import create_engine, inspect

from config import normalize_database_url
from models import Base

BACKEND_DIR = Path(__file__).resolve().parent.parent
TABLES = {"rules", "rule_executions", "correlations"}


@pytest.fixture
def alembic_config(tmp_path: Path) -> Config:
    """Alembic config targeting a temporary SQLite database."""
    cfg = Config(str(BACKEND_DIR / "alembic.ini"))
    cfg.set_main_option("sqlalchemy.url", f"sqlite:///{tmp_path / 'migrated.db'}")
    cfg.attributes["configure_logger"] = False
    return cfg


def _table_names(cfg: Config) -> set[str]:
    engine = create_engine(cfg.get_main_option("sqlalchemy.url"))
    try:
        return set(inspect(engine).get_table_names()) - {"alembic_version"}
    finally:
        engine.dispose()


class TestMigrations:
    def test_should_create_then_drop_all_tables_when_upgrading_and_downgrading(self, alembic_config):
        command.upgrade(alembic_config, "head")
        assert _table_names(alembic_config) == TABLES

        command.downgrade(alembic_config, "base")
        assert _table_names(alembic_config) == set()

    def test_should_match_models_when_upgraded_to_head(self, alembic_config):
        command.upgrade(alembic_config, "head")

        engine = create_engine(alembic_config.get_main_option("sqlalchemy.url"))
        try:
            with engine.connect() as connection:
                differences = compare_metadata(MigrationContext.configure(connection), Base.metadata)
        finally:
            engine.dispose()

        assert differences == []


class TestDatabaseUrl:
    @pytest.mark.parametrize("url, expected", [
        ("postgresql://u:p@host/db?sslmode=require", "postgresql+psycopg://u:p@host/db?sslmode=require"),
        ("postgres://u:p@host/db", "postgresql+psycopg://u:p@host/db"),
        ("postgresql+psycopg://u:p@host/db", "postgresql+psycopg://u:p@host/db"),
        ("sqlite://", "sqlite://"),
    ])
    def test_should_select_psycopg_driver_when_url_is_postgresql(self, url, expected):
        assert normalize_database_url(url) == expected
