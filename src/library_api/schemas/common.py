"""Schemas shared across resources: pagination envelope and problem details."""

from pydantic import BaseModel, ConfigDict, Field


class Page[T](BaseModel):
    """Offset-paginated collection envelope.

    Attributes:
        items: Elements of the requested window.
        total: Number of elements matching the query across all pages.
        limit: Page size that was applied.
        offset: Number of elements skipped.
    """

    items: list[T]
    total: int = Field(ge=0, description="Total number of matches, ignoring pagination.")
    limit: int = Field(ge=1, description="Maximum number of items returned per page.")
    offset: int = Field(ge=0, description="Number of matches skipped before this page.")


class FieldError(BaseModel):
    """A single request validation failure.

    Attributes:
        location: Path to the offending input, e.g. ``["body", "title"]``.
        message: Human readable explanation.
        type: Pydantic error type identifier.
    """

    location: list[str | int]
    message: str
    type: str


class ProblemDetail(BaseModel):
    """RFC 9457 ``application/problem+json`` document.

    Attributes:
        type: URI reference identifying the problem type.
        title: Short, stable summary of the problem type.
        status: HTTP status code.
        detail: Explanation specific to this occurrence.
        instance: Path of the request that failed.
        code: Stable machine readable error code (extension member).
        request_id: Correlation id, matching the ``X-Request-ID`` response header.
        errors: Field level validation errors, present for 422 responses.
    """

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "type": "urn:library-api:problem:book-not-found",
                "title": "Book not found",
                "status": 404,
                "detail": "No book exists with id '0b1f...'.",
                "instance": "/api/v1/books/0b1f...",
                "code": "book-not-found",
                "request_id": "3f0c5d0e7a5d4a1f9b0d2d8f6a1c2b3e",
            }
        }
    )

    type: str
    title: str
    status: int
    detail: str
    instance: str
    code: str
    request_id: str | None = None
    errors: list[FieldError] | None = None
