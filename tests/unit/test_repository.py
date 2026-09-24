"""Unit tests for repository error translation."""

from datetime import date

import pytest
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from library_api.models.book import Book
from library_api.repositories.book import BookRepository


def test_non_unique_integrity_errors_are_not_reported_as_duplicates(session: Session) -> None:
    """A NOT NULL violation surfaces as ``IntegrityError`` instead of a fake conflict."""
    incomplete = Book(title="T", author="A", published_date=date(2000, 1, 1))

    with pytest.raises(IntegrityError):
        BookRepository(session).add(incomplete)
