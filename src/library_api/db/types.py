"""Custom SQLAlchemy column types."""

from datetime import UTC, datetime
from typing import override

from sqlalchemy import DateTime, Dialect
from sqlalchemy.types import TypeDecorator


class UTCDateTime(TypeDecorator[datetime]):
    """Timezone-aware ``datetime`` that is always stored as naive UTC.

    SQLite has no native timezone support and silently drops offsets. This
    decorator normalizes on the way in and re-attaches ``UTC`` on the way out,
    so application code never sees naive datetimes.
    """

    impl = DateTime
    cache_ok = True

    @override
    def process_bind_param(self, value: datetime | None, dialect: Dialect) -> datetime | None:
        """Convert an aware datetime to naive UTC before persisting.

        Args:
            value: The Python value being bound.
            dialect: The active dialect (unused).

        Returns:
            Naive UTC datetime, or ``None``.

        Raises:
            ValueError: If ``value`` is a naive datetime, which would be ambiguous.
        """
        if value is None:
            return None
        if value.tzinfo is None:
            raise ValueError("Naive datetimes are not accepted; use timezone-aware values.")
        return value.astimezone(UTC).replace(tzinfo=None)

    @override
    def process_result_value(self, value: datetime | None, dialect: Dialect) -> datetime | None:
        """Re-attach UTC to a value loaded from the database.

        Args:
            value: The naive datetime read from the database.
            dialect: The active dialect (unused).

        Returns:
            Timezone-aware UTC datetime, or ``None``.
        """
        return None if value is None else value.replace(tzinfo=UTC)
