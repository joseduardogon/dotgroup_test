"""Schemas shared across resources: pagination envelope and problem details."""

from pydantic import BaseModel, ConfigDict, Field


class Page[T](BaseModel):
    """Offset-paginated collection envelope.

    ``total`` counts every match, so clients can compute the number of pages as
    ``ceil(total / limit)``. An ``offset`` past the end yields an empty ``items``.
    """

    items: list[T] = Field(description="Elements of the requested window.")
    total: int = Field(ge=0, description="Total number of matches, ignoring pagination.")
    limit: int = Field(ge=1, description="Maximum number of items returned per page.")
    offset: int = Field(ge=0, description="Number of matches skipped before this page.")


class FieldError(BaseModel):
    """A single request validation failure."""

    location: list[str | int] = Field(
        description="Path to the offending input.", examples=[["body", "title"]]
    )
    message: str = Field(description="Human readable explanation.")
    type: str = Field(description="Pydantic error type identifier.", examples=["string_too_short"])


class ProblemDetail(BaseModel):
    """RFC 9457 ``application/problem+json`` document returned for every error."""

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

    type: str = Field(description="URI reference identifying the problem type.")
    title: str = Field(description="Short, stable summary of the problem type.")
    status: int = Field(description="HTTP status code.")
    detail: str = Field(description="Explanation specific to this occurrence.")
    instance: str = Field(description="Path of the request that failed.")
    code: str = Field(description="Stable machine readable error code (extension member).")
    request_id: str | None = Field(
        default=None, description="Correlation id; matches the ``X-Request-ID`` response header."
    )
    errors: list[FieldError] | None = Field(
        default=None, description="Field level validation errors (422 only)."
    )
