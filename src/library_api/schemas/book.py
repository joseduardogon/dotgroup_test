"""Book request and response contracts."""

import re
import uuid
from datetime import UTC, date, datetime
from typing import Annotated, Self

from pydantic import (
    AfterValidator,
    BaseModel,
    ConfigDict,
    Field,
    StringConstraints,
    model_validator,
)

from library_api.models.book import (
    AUTHOR_MAX_LENGTH,
    SUMMARY_MAX_LENGTH,
    TITLE_MAX_LENGTH,
    BookSortField,
    SortOrder,
)


def _not_in_the_future(value: date) -> date:
    """Reject publication dates later than today (UTC).

    Args:
        value: The candidate date.

    Returns:
        ``value`` when valid.

    Raises:
        ValueError: If ``value`` lies in the future.
    """
    if value > datetime.now(UTC).date():
        raise ValueError("published_date cannot be in the future")
    return value


_CONTROL_CHARACTERS = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")


def _without_control_characters(value: str) -> str:
    """Reject NUL and other non-printable control characters.

    Newlines and tabs remain valid so summaries can span several lines.

    Args:
        value: The candidate text.

    Returns:
        ``value`` when valid.

    Raises:
        ValueError: If a forbidden control character is present.
    """
    if _CONTROL_CHARACTERS.search(value):
        raise ValueError("control characters are not allowed")
    return value


Title = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=1, max_length=TITLE_MAX_LENGTH),
    AfterValidator(_without_control_characters),
    Field(description="Book title.", examples=["Dom Casmurro"]),
]
Author = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=1, max_length=AUTHOR_MAX_LENGTH),
    AfterValidator(_without_control_characters),
    Field(description="Author full name.", examples=["Machado de Assis"]),
]
PublishedDate = Annotated[
    date,
    AfterValidator(_not_in_the_future),
    Field(description="Publication date (ISO 8601, not in the future).", examples=["1899-12-01"]),
]
Summary = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=1, max_length=SUMMARY_MAX_LENGTH),
    AfterValidator(_without_control_characters),
    Field(description="Synopsis of the book.", examples=["Bentinho narra a dúvida sobre Capitu."]),
]


class BookCreate(BaseModel):
    """Payload to register a new book."""

    model_config = ConfigDict(extra="forbid")

    title: Title
    author: Author
    published_date: PublishedDate
    summary: Summary


class BookUpdate(BaseModel):
    """Partial update (``PATCH``) payload.

    Only the fields present in the request body are changed. Explicitly sending
    ``null`` for a required column is rejected instead of being silently ignored.
    """

    model_config = ConfigDict(extra="forbid")

    title: Title | None = None
    author: Author | None = None
    published_date: PublishedDate | None = None
    summary: Summary | None = None

    @model_validator(mode="after")
    def _require_meaningful_change(self) -> Self:
        """Ensure at least one field is provided and none is explicitly ``null``.

        Returns:
            The validated instance.

        Raises:
            ValueError: If the body is empty or contains ``null`` values.
        """
        if not self.model_fields_set:
            raise ValueError("at least one field must be provided")
        nulls = sorted(name for name in self.model_fields_set if getattr(self, name) is None)
        if nulls:
            raise ValueError(f"fields cannot be null: {', '.join(nulls)}")
        return self


class BookRead(BaseModel):
    """Representation of a stored book."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    title: str
    author: str
    published_date: date
    summary: str
    created_at: datetime
    updated_at: datetime


class BookSearchParams(BaseModel):
    """Query string contract of ``GET /books``.

    Filters are combined with logical AND. ``q`` is a convenience free-text
    filter matching the title **or** the author.
    """

    model_config = ConfigDict(extra="forbid")

    q: Annotated[
        str | None,
        Field(
            min_length=1,
            max_length=255,
            description="Free text matched against title OR author.",
            examples=["assis"],
        ),
    ] = None
    title: Annotated[
        str | None,
        Field(min_length=1, max_length=255, description="Title contains this text."),
    ] = None
    author: Annotated[
        str | None,
        Field(min_length=1, max_length=255, description="Author contains this text."),
    ] = None
    sort: Annotated[BookSortField, Field(description="Field to order by.")] = BookSortField.TITLE
    order: Annotated[SortOrder, Field(description="Sort direction.")] = SortOrder.ASC
    limit: Annotated[int, Field(ge=1, le=100, description="Page size.")] = 20
    offset: Annotated[int, Field(ge=0, description="Items to skip.")] = 0
