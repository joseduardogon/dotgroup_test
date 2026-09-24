"""Unit tests for request schemas."""

from datetime import UTC, datetime, timedelta

import pytest
from pydantic import ValidationError

from library_api.models.book import AUTHOR_MAX_LENGTH, SUMMARY_MAX_LENGTH, TITLE_MAX_LENGTH
from library_api.schemas.book import BookCreate, BookUpdate


def _valid(**overrides: object) -> dict[str, object]:
    """Build a valid payload with optional overrides."""
    return {
        "title": "T",
        "author": "A",
        "published_date": "2000-01-01",
        "summary": "S",
    } | overrides


def test_create_strips_whitespace() -> None:
    """Surrounding whitespace is removed from text fields."""
    book = BookCreate.model_validate(_valid(title="  Hi  "))
    assert book.title == "Hi"


@pytest.mark.parametrize("field", ["title", "author", "summary"])
def test_create_rejects_blank_text(field: str) -> None:
    """Whitespace-only strings are invalid."""
    with pytest.raises(ValidationError):
        BookCreate.model_validate(_valid(**{field: "   "}))


def test_create_rejects_future_date() -> None:
    """A publication date in the future is invalid."""
    tomorrow = (datetime.now(UTC) + timedelta(days=2)).date().isoformat()
    with pytest.raises(ValidationError, match="future"):
        BookCreate.model_validate(_valid(published_date=tomorrow))


def test_create_rejects_unknown_fields() -> None:
    """Unknown fields are rejected rather than silently dropped."""
    with pytest.raises(ValidationError):
        BookCreate.model_validate(_valid(isbn="123"))


def test_update_requires_a_field() -> None:
    """An empty PATCH body is invalid."""
    with pytest.raises(ValidationError, match="at least one field"):
        BookUpdate.model_validate({})


def test_update_rejects_explicit_null() -> None:
    """Explicit nulls are invalid instead of ignored."""
    with pytest.raises(ValidationError, match="cannot be null: title"):
        BookUpdate.model_validate({"title": None})


def test_update_accepts_partial() -> None:
    """A single field is enough."""
    assert BookUpdate.model_validate({"summary": "x"}).model_fields_set == {"summary"}


@pytest.mark.parametrize(
    ("field", "limit"),
    [("title", TITLE_MAX_LENGTH), ("author", AUTHOR_MAX_LENGTH), ("summary", SUMMARY_MAX_LENGTH)],
)
def test_create_accepts_text_exactly_at_the_length_limit(field: str, limit: int) -> None:
    """A field at its documented maximum length is valid."""
    book = BookCreate.model_validate(_valid(**{field: "x" * limit}))
    assert len(getattr(book, field)) == limit


@pytest.mark.parametrize(
    ("field", "limit"),
    [("title", TITLE_MAX_LENGTH), ("author", AUTHOR_MAX_LENGTH), ("summary", SUMMARY_MAX_LENGTH)],
)
def test_create_rejects_text_one_over_the_length_limit(field: str, limit: int) -> None:
    """A field one character past its documented maximum is invalid."""
    with pytest.raises(ValidationError, match="at most"):
        BookCreate.model_validate(_valid(**{field: "x" * (limit + 1)}))
