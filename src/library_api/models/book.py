"""The ``Book`` aggregate root."""

import uuid
from datetime import UTC, date, datetime
from enum import StrEnum

from sqlalchemy import Date, Index, String, Text, UniqueConstraint, Uuid
from sqlalchemy.orm import Mapped, mapped_column, validates

from library_api.core.text import normalize_for_search
from library_api.db.base import Base
from library_api.db.types import UTCDateTime

TITLE_MAX_LENGTH = 255
AUTHOR_MAX_LENGTH = 255
SUMMARY_MAX_LENGTH = 5000


def _utcnow() -> datetime:
    """Return the current time as a timezone-aware UTC datetime.

    Returns:
        ``datetime.now(UTC)``; isolated so it is trivial to patch in tests.
    """
    return datetime.now(UTC)


class BookSortField(StrEnum):
    """Columns a book listing can be ordered by."""

    TITLE = "title"
    AUTHOR = "author"
    PUBLISHED_DATE = "published_date"
    CREATED_AT = "created_at"


class SortOrder(StrEnum):
    """Sort direction."""

    ASC = "asc"
    DESC = "desc"


class Book(Base):
    """A book registered in the virtual library.

    ``title_search`` and ``author_search`` are derived shadow columns holding the
    accent- and case-folded text (see :func:`~library_api.core.text.normalize_for_search`).
    They are maintained automatically by validators, back the search filters and
    participate in the natural-key uniqueness constraint so that ``"Dom Casmurro"``
    and ``"dom  casmurro"`` cannot be registered twice.

    Attributes:
        id: Surrogate primary key (UUID4), safe to expose publicly.
        title: Book title as entered by the user.
        author: Author name as entered by the user.
        published_date: Date the book was first published.
        summary: Free text synopsis.
        title_search: Normalized ``title`` used for lookups.
        author_search: Normalized ``author`` used for lookups.
        created_at: Insertion timestamp (UTC).
        updated_at: Last modification timestamp (UTC).
    """

    __tablename__ = "books"
    __table_args__ = (
        UniqueConstraint(
            "title_search", "author_search", "published_date", name="uq_books_identity"
        ),
        Index("ix_books_title_search", "title_search"),
        Index("ix_books_author_search", "author_search"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    title: Mapped[str] = mapped_column(String(TITLE_MAX_LENGTH))
    author: Mapped[str] = mapped_column(String(AUTHOR_MAX_LENGTH))
    published_date: Mapped[date] = mapped_column(Date)
    summary: Mapped[str] = mapped_column(Text)
    title_search: Mapped[str] = mapped_column(String(TITLE_MAX_LENGTH))
    author_search: Mapped[str] = mapped_column(String(AUTHOR_MAX_LENGTH))
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, default=_utcnow)
    updated_at: Mapped[datetime] = mapped_column(UTCDateTime, default=_utcnow, onupdate=_utcnow)

    @validates("title")
    def _sync_title_search(self, _key: str, value: str) -> str:
        """Keep ``title_search`` consistent whenever ``title`` is assigned.

        Args:
            _key: Attribute name (unused).
            value: The new title.

        Returns:
            ``value`` unchanged.
        """
        self.title_search = normalize_for_search(value)
        return value

    @validates("author")
    def _sync_author_search(self, _key: str, value: str) -> str:
        """Keep ``author_search`` consistent whenever ``author`` is assigned.

        Args:
            _key: Attribute name (unused).
            value: The new author.

        Returns:
            ``value`` unchanged.
        """
        self.author_search = normalize_for_search(value)
        return value

    def __repr__(self) -> str:
        """Return a debugging representation that never dumps the summary.

        Returns:
            A short ``Book(...)`` string.
        """
        return f"Book(id={self.id}, title={self.title!r}, author={self.author!r})"
