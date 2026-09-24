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
from pydantic.config import JsonDict

from library_api.models.book import (
    AUTHOR_MAX_LENGTH,
    SUMMARY_MAX_LENGTH,
    TITLE_MAX_LENGTH,
    BookSortField,
    SortOrder,
)

_CONTROL_CHARACTERS = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")

_EXAMPLE_BOOK: JsonDict = {
    "title": "Dom Casmurro",
    "author": "Machado de Assis",
    "published_date": "1899-12-01",
    "summary": "Bentinho narra a dúvida sobre a fidelidade de Capitu.",
}


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
SearchText = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=1, max_length=255),
    AfterValidator(_without_control_characters),
]


class BookCreate(BaseModel):
    """Payload to register a new book. All four fields are required."""

    model_config = ConfigDict(extra="forbid", json_schema_extra={"example": _EXAMPLE_BOOK})

    title: Title
    author: Author
    published_date: PublishedDate
    summary: Summary


class BookUpdate(BaseModel):
    """Partial update (``PATCH``) payload.

    Only the fields present in the request body are changed. Explicitly sending
    ``null`` for a required column is rejected instead of being silently ignored.
    """

    model_config = ConfigDict(
        extra="forbid", json_schema_extra={"example": {"summary": "Novo resumo."}}
    )

    title: Title | None = Field(default=None, description="New title.")
    author: Author | None = Field(default=None, description="New author name.")
    published_date: PublishedDate | None = Field(default=None, description="New publication date.")
    summary: Summary | None = Field(default=None, description="New synopsis.")

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

    model_config = ConfigDict(
        from_attributes=True,
        json_schema_extra={
            "example": {
                "id": "0b1f3a52-6f0e-4a3e-9c53-0f6a3c1f9a11",
                **_EXAMPLE_BOOK,
                "created_at": "2026-09-23T12:00:00Z",
                "updated_at": "2026-09-23T12:00:00Z",
            }
        },
    )

    id: uuid.UUID = Field(description="Unique, opaque identifier (UUID v4).")
    title: str = Field(description="Book title.")
    author: str = Field(description="Author full name.")
    published_date: date = Field(description="Publication date (ISO 8601).")
    summary: str = Field(description="Synopsis of the book.")
    created_at: datetime = Field(description="When the book was registered (UTC).")
    updated_at: datetime = Field(description="When the book was last modified (UTC).")


class BookSearchParams(BaseModel):
    """Query string contract of ``GET /books``.

    Filters are combined with logical AND. ``q`` is a convenience free-text
    filter matching the title **or** the author. Text filters are trimmed and
    must not be blank.
    """

    model_config = ConfigDict(extra="forbid")

    q: SearchText | None = Field(
        default=None,
        description="Free text matched against title OR author.",
        examples=["assis"],
    )
    title: SearchText | None = Field(
        default=None, description="Title contains this text.", examples=["casmurro"]
    )
    author: SearchText | None = Field(
        default=None, description="Author contains this text.", examples=["machado"]
    )
    sort: BookSortField = Field(
        default=BookSortField.TITLE, description="Field to order by.", examples=["published_date"]
    )
    order: SortOrder = Field(
        default=SortOrder.ASC, description="Sort direction.", examples=["desc"]
    )
    limit: int = Field(default=20, ge=1, le=100, description="Page size (1-100).", examples=[20])
    offset: int = Field(default=0, ge=0, description="Number of matches to skip.", examples=[0])
