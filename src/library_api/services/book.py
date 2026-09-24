"""Book use cases."""

import uuid

from sqlalchemy.orm import Session

from library_api.core.exceptions import BookNotFoundError
from library_api.models.book import Book
from library_api.repositories.book import BookRepository, BookSearchCriteria
from library_api.schemas.book import BookCreate, BookUpdate


class BookService:
    """Orchestrates book use cases and owns the transaction (unit of work).

    Every public mutating method either commits fully or rolls back, so callers
    never observe a half-applied change.
    """

    def __init__(self, session: Session, repository: BookRepository) -> None:
        """Wire the service.

        Args:
            session: Session whose transaction this service controls.
            repository: Persistence gateway bound to the same session.
        """
        self._session = session
        self._repository = repository

    def register(self, data: BookCreate) -> Book:
        """Register a new book.

        Args:
            data: Validated creation payload.

        Returns:
            The persisted book.

        Raises:
            DuplicateBookError: If the same title, author and date already exist.
        """
        book = Book(**data.model_dump())
        try:
            self._repository.add(book)
            self._session.commit()
        except Exception:
            self._session.rollback()
            raise
        return book

    def get(self, book_id: uuid.UUID) -> Book:
        """Fetch a book or fail.

        Args:
            book_id: Identifier to look up.

        Returns:
            The book.

        Raises:
            BookNotFoundError: If it does not exist.
        """
        book = self._repository.get(book_id)
        if book is None:
            raise BookNotFoundError(book_id)
        return book

    def search(self, criteria: BookSearchCriteria) -> tuple[list[Book], int]:
        """Search books.

        Args:
            criteria: Filters, ordering and pagination.

        Returns:
            A ``(items, total)`` tuple.
        """
        return self._repository.search(criteria)

    def update(self, book_id: uuid.UUID, data: BookUpdate) -> Book:
        """Apply a partial update.

        Args:
            book_id: Identifier of the book to change.
            data: Payload; only explicitly provided fields are applied.

        Returns:
            The updated book.

        Raises:
            BookNotFoundError: If the book does not exist.
            DuplicateBookError: If the change collides with another book.
        """
        book = self.get(book_id)
        try:
            for field, value in data.model_dump(exclude_unset=True).items():
                setattr(book, field, value)
            self._repository.flush()
            self._session.commit()
        except Exception:
            self._session.rollback()
            raise
        return book

    def remove(self, book_id: uuid.UUID) -> None:
        """Delete a book.

        Args:
            book_id: Identifier of the book to delete.

        Raises:
            BookNotFoundError: If the book does not exist.
        """
        book = self.get(book_id)
        self._repository.delete(book)
        self._session.commit()
