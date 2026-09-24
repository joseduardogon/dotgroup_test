"""Fixtures for unit tests that need a real (in-memory) database."""

from collections.abc import Iterator

import pytest
from sqlalchemy.orm import Session

from library_api.db.base import Base
from library_api.db.session import create_db_engine, create_session_factory


@pytest.fixture
def session() -> Iterator[Session]:
    """Yield a session on a fresh in-memory database with the schema created."""
    engine = create_db_engine("sqlite://")
    Base.metadata.create_all(engine)
    with create_session_factory(engine)() as db_session:
        yield db_session
    engine.dispose()
