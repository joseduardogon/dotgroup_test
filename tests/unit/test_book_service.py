"""Unit tests for :class:`~library_api.services.book.BookService` (no HTTP involved)."""

import uuid
from datetime import date

import pytest
from sqlalchemy.orm import Session

from library_api.core.exceptions import BookNotFoundError, DuplicateBookError
from library_api.repositories.book import BookRepository, BookSearchCriteria
from library_api.schemas.book import BookCreate, BookUpdate
from library_api.services.book import BookService


@pytest.fixture
def service(session: Session) -> BookService:
    """Build a service wired to the in-memory session."""
    return BookService(session, BookRepository(session))


def _data(**overrides: object) -> BookCreate:
    """Build a valid creation payload with optional overrides."""
    payload = {
        "title": "Dom Casmurro",
        "author": "Machado de Assis",
        "published_date": date(1899, 12, 1),
        "summary": "Resumo.",
    } | overrides
    return BookCreate.model_validate(payload)


def test_register_persists_and_populates_generated_fields(service: BookService) -> None:
    """A registered book has an id and timestamps and can be read back."""
    book = service.register(_data())

    assert isinstance(book.id, uuid.UUID)
    assert book.created_at.tzinfo is not None
    assert service.get(book.id) is book


def test_register_duplicate_raises_and_leaves_the_session_usable(service: BookService) -> None:
    """After a conflict the transaction is rolled back and new work still succeeds."""
    service.register(_data())

    with pytest.raises(DuplicateBookError):
        service.register(_data(title="  dom CASMURRO "))

    assert service.register(_data(title="Esaú e Jacó")).title == "Esaú e Jacó"
    assert service.search(BookSearchCriteria())[1] == 2


def test_get_unknown_raises_not_found(service: BookService) -> None:
    """A missing id raises the domain error carrying that id."""
    missing = uuid.uuid4()

    with pytest.raises(BookNotFoundError, match=str(missing)):
        service.get(missing)


def test_update_applies_only_provided_fields(service: BookService) -> None:
    """Fields left out of the update keep their value."""
    book = service.register(_data())

    updated = service.update(book.id, BookUpdate(summary="Outro resumo."))

    assert updated.summary == "Outro resumo."
    assert updated.title == "Dom Casmurro"


def test_update_collision_rolls_back_and_keeps_original_values(service: BookService) -> None:
    """A colliding update raises and the record is not left half-modified."""
    first = service.register(_data())
    second = service.register(_data(title="Outro"))

    with pytest.raises(DuplicateBookError):
        service.update(second.id, BookUpdate(title=first.title))

    assert service.get(second.id).title == "Outro"


def test_update_unknown_raises_not_found(service: BookService) -> None:
    """Updating a missing book fails before touching the database."""
    with pytest.raises(BookNotFoundError):
        service.update(uuid.uuid4(), BookUpdate(title="x"))


def test_remove_deletes_and_second_remove_fails(service: BookService) -> None:
    """A book can be removed exactly once."""
    book = service.register(_data())

    service.remove(book.id)

    with pytest.raises(BookNotFoundError):
        service.remove(book.id)


def test_remove_failure_rolls_back_and_keeps_the_book(
    service: BookService, session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    """If commit fails during removal, the session rolls back instead of half-applying it."""
    book = service.register(_data())

    def _failing_commit() -> None:
        raise RuntimeError("boom")

    monkeypatch.setattr(session, "commit", _failing_commit)

    with pytest.raises(RuntimeError):
        service.remove(book.id)

    monkeypatch.undo()
    assert service.get(book.id).id == book.id


def test_search_returns_items_and_total(service: BookService) -> None:
    """Search delegates to the repository and reports the unpaginated total."""
    for title in ("Alfa", "Beta", "Gama"):
        service.register(_data(title=title))

    items, total = service.search(BookSearchCriteria(limit=2))

    assert [book.title for book in items] == ["Alfa", "Beta"]
    assert total == 3
