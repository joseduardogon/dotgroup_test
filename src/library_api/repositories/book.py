"""Repository for :class:`~library_api.models.book.Book`."""

import uuid
from dataclasses import dataclass

from sqlalchemy import ColumnElement, Select, func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import InstrumentedAttribute, Session

from library_api.core.exceptions import DuplicateBookError
from library_api.core.text import normalize_for_search
from library_api.models.book import Book, BookSortField, SortOrder

_SQLITE_UNIQUE_VIOLATION = "SQLITE_CONSTRAINT_UNIQUE"

_SORT_COLUMNS: dict[BookSortField, InstrumentedAttribute[object]] = {
    BookSortField.TITLE: Book.title_search,
    BookSortField.AUTHOR: Book.author_search,
    BookSortField.PUBLISHED_DATE: Book.published_date,
    BookSortField.CREATED_AT: Book.created_at,
}


@dataclass(frozen=True, slots=True)
class BookSearchCriteria:
    """Transport-agnostic description of a book search.

    Attributes:
        q: Text matched against title OR author.
        title: Text the title must contain.
        author: Text the author must contain.
        sort: Column to order by.
        order: Sort direction.
        limit: Maximum number of rows to return.
        offset: Rows to skip.
    """

    q: str | None = None
    title: str | None = None
    author: str | None = None
    sort: BookSortField = BookSortField.TITLE
    order: SortOrder = SortOrder.ASC
    limit: int = 20
    offset: int = 0


class BookRepository:
    """Collection-like access to persisted books.

    The repository flushes but never commits: transaction boundaries belong to
    the service layer (unit-of-work), which keeps multi-step use cases atomic.
    """

    def __init__(self, session: Session) -> None:
        """Bind the repository to a session.

        Args:
            session: The unit-of-work session.
        """
        self._session = session

    def add(self, book: Book) -> Book:
        """Persist a new book.

        Args:
            book: Transient instance to insert.

        Returns:
            The same instance, now flushed (identifiers and timestamps populated).

        Raises:
            DuplicateBookError: If the natural key (title, author, date) exists.
        """
        self._session.add(book)
        self.flush()
        return book

    def get(self, book_id: uuid.UUID) -> Book | None:
        """Fetch a book by primary key.

        Args:
            book_id: Identifier to look up.

        Returns:
            The book, or ``None`` when absent.
        """
        return self._session.get(Book, book_id)

    def search(self, criteria: BookSearchCriteria) -> tuple[list[Book], int]:
        """Run a filtered, sorted and paginated query.

        Two statements are issued: the page and the total count for the same
        filters. Ordering always ends with the primary key so pagination is
        stable even when the sort column has ties.

        Args:
            criteria: Filters, ordering and pagination.

        Returns:
            A ``(items, total)`` tuple.
        """
        conditions = self._conditions(criteria)
        total = self._session.scalar(select(func.count()).select_from(Book).where(*conditions))

        column = _SORT_COLUMNS[criteria.sort]
        direction = column.asc() if criteria.order is SortOrder.ASC else column.desc()
        statement: Select[tuple[Book]] = (
            select(Book)
            .where(*conditions)
            .order_by(direction, Book.id)
            .limit(criteria.limit)
            .offset(criteria.offset)
        )
        return list(self._session.scalars(statement)), total or 0

    def delete(self, book: Book) -> None:
        """Remove a book.

        Args:
            book: Persistent instance to delete.
        """
        self._session.delete(book)
        self._session.flush()

    def flush(self) -> None:
        """Flush pending changes, translating constraint violations.

        Raises:
            DuplicateBookError: If the pending changes violate the natural key.
            IntegrityError: For any other constraint violation, which indicates a
                programming error rather than a client conflict.
        """
        try:
            self._session.flush()
        except IntegrityError as exc:
            if getattr(exc.orig, "sqlite_errorname", None) != _SQLITE_UNIQUE_VIOLATION:
                raise
            raise DuplicateBookError from exc

    @staticmethod
    def _conditions(criteria: BookSearchCriteria) -> list[ColumnElement[bool]]:
        """Translate criteria into SQL predicates.

        User text is normalized like the stored shadow columns, and ``LIKE``
        wildcards inside it are escaped, so ``"100%"`` matches literally.

        Args:
            criteria: The search description.

        Returns:
            Predicates to be combined with AND.
        """
        conditions: list[ColumnElement[bool]] = []
        if criteria.title:
            conditions.append(_contains(Book.title_search, criteria.title))
        if criteria.author:
            conditions.append(_contains(Book.author_search, criteria.author))
        if criteria.q:
            conditions.append(
                or_(
                    _contains(Book.title_search, criteria.q),
                    _contains(Book.author_search, criteria.q),
                )
            )
        return conditions


def _contains(column: InstrumentedAttribute[str], text: str) -> ColumnElement[bool]:
    """Build an escaped, normalized "contains" predicate.

    Args:
        column: Normalized shadow column to compare against.
        text: Raw user text.

    Returns:
        A ``LIKE`` expression with an explicit escape character.
    """
    return column.contains(normalize_for_search(text), autoescape=True)
