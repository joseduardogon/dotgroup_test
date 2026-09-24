"""Shared fixtures: an isolated app and client per test, backed by in-memory SQLite."""

from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient

from library_api.core.config import Settings
from library_api.db.base import Base
from library_api.main import create_app


@pytest.fixture
def settings() -> Settings:
    """Provide settings pointing at a private in-memory database."""
    return Settings(environment="testing", database_url="sqlite://", log_level="WARNING")


@pytest.fixture
def client(settings: Settings) -> Iterator[TestClient]:
    """Yield a client whose app has a freshly created schema.

    The ``with`` block runs the lifespan, so the engine exists before the schema
    is created and is disposed of afterwards.
    """
    app = create_app(settings)
    with TestClient(app, raise_server_exceptions=False) as test_client:
        Base.metadata.create_all(app.state.engine)
        yield test_client


@pytest.fixture
def book_payload() -> dict[str, str]:
    """Return a valid creation payload."""
    return {
        "title": "Dom Casmurro",
        "author": "Machado de Assis",
        "published_date": "1899-12-01",
        "summary": "Bentinho narra a dúvida sobre a fidelidade de Capitu.",
    }
