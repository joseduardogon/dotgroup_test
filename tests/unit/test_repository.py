"""Unit tests for repository error translation."""

from collections.abc import Iterator
from datetime import date

import pytest
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from library_api.db.base import Base
from library_api.db.session import create_db_engine, create_session_factory
from library_api.models.book import Book
from library_api.repositories.book import BookRepository


@pytest.fixture
def session() -> Iterator[Session]:
    """Yield a session on a fresh in-memory database."""
    engine = create_db_engine("sqlite://")
    Base.metadata.create_all(engine)
    with create_session_factory(engine)() as db_session:
        yield db_session
    engine.dispose()


def test_non_unique_integrity_errors_are_not_reported_as_duplicates(session: Session) -> None:
    """A NOT NULL violation surfaces as ``IntegrityError`` instead of a fake conflict."""
    incomplete = Book(title="T", author="A", published_date=date(2000, 1, 1))

    with pytest.raises(IntegrityError):
        BookRepository(session).add(incomplete)
