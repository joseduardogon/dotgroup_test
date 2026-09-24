"""Integration tests that run the real Alembic migrations."""

from pathlib import Path

import pytest
from alembic import command
from alembic.autogenerate import compare_metadata
from alembic.config import Config
from alembic.migration import MigrationContext
from sqlalchemy import inspect

from library_api.db.base import Base
from library_api.db.session import create_db_engine

pytestmark = pytest.mark.integration

ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture
def database_url(tmp_path: Path) -> str:
    """Return the URL of a throwaway SQLite file."""
    return f"sqlite:///{tmp_path / 'm.db'}"


@pytest.fixture
def alembic_config(database_url: str) -> Config:
    """Return an Alembic config targeting the throwaway database."""
    config = Config(str(ROOT / "alembic.ini"))
    config.set_main_option("script_location", str(ROOT / "migrations"))
    config.set_main_option("sqlalchemy.url", database_url)
    config.attributes["configure_logger"] = False
    return config


def test_upgrade_matches_models_and_downgrade_is_clean(
    alembic_config: Config, database_url: str
) -> None:
    """Migrations and ORM metadata must not drift, and downgrade removes everything."""
    command.upgrade(alembic_config, "head")
    engine = create_db_engine(database_url)

    with engine.connect() as connection:
        diff = compare_metadata(MigrationContext.configure(connection), Base.metadata)
        assert diff == []

    command.downgrade(alembic_config, "base")
    assert "books" not in inspect(engine).get_table_names()
    engine.dispose()


def test_offline_mode_renders_sql(
    alembic_config: Config, capsys: pytest.CaptureFixture[str]
) -> None:
    """``--sql`` mode emits DDL without touching the database."""
    command.upgrade(alembic_config, "head", sql=True)

    assert "CREATE TABLE books" in capsys.readouterr().out
