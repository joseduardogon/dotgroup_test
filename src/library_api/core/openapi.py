"""OpenAPI post-processing so the published contract matches the real responses.

FastAPI documents every validation failure as ``application/json`` with its stock
``HTTPValidationError`` schema, while this service answers with RFC 9457
``application/problem+json`` documents. Without this step generated clients would
be built against the wrong error contract.
"""

from typing import Any, override

from fastapi import FastAPI

from library_api.core.errors import PROBLEM_MEDIA_TYPE

_PROBLEM_REF = {"$ref": "#/components/schemas/ProblemDetail"}
_STOCK_VALIDATION_SCHEMAS = ("HTTPValidationError", "ValidationError")

_PROBLEM_EXAMPLES: dict[str, tuple[str, dict[str, Any]]] = {
    "404": (
        "Unknown book",
        {
            "type": "urn:library-api:problem:book-not-found",
            "title": "Book not found",
            "status": 404,
            "detail": "No book exists with id '0b1f3a52-6f0e-4a3e-9c53-0f6a3c1f9a11'.",
            "instance": "/api/v1/books/0b1f3a52-6f0e-4a3e-9c53-0f6a3c1f9a11",
            "code": "book-not-found",
            "request_id": "3f0c5d0e7a5d4a1f9b0d2d8f6a1c2b3e",
        },
    ),
    "409": (
        "Duplicate book",
        {
            "type": "urn:library-api:problem:duplicate-book",
            "title": "Book already registered",
            "status": 409,
            "detail": (
                "A book with the same title, author and publication date is already registered."
            ),
            "instance": "/api/v1/books",
            "code": "duplicate-book",
            "request_id": "3f0c5d0e7a5d4a1f9b0d2d8f6a1c2b3e",
        },
    ),
    "422": (
        "Invalid payload",
        {
            "type": "urn:library-api:problem:validation-error",
            "title": "Request validation failed",
            "status": 422,
            "detail": "1 validation error(s) in the request.",
            "instance": "/api/v1/books",
            "code": "validation-error",
            "request_id": "3f0c5d0e7a5d4a1f9b0d2d8f6a1c2b3e",
            "errors": [
                {
                    "location": ["body", "published_date"],
                    "message": "Value error, published_date cannot be in the future",
                    "type": "value_error",
                }
            ],
        },
    ),
}


def _uses_problem_schema(status: str, content: dict[str, Any]) -> bool:
    """Tell whether a response declares a problem-like JSON body.

    Args:
        status: HTTP status code as it appears in the OpenAPI document.
        content: The response ``content`` mapping.

    Returns:
        ``True`` for ``ProblemDetail`` bodies and for FastAPI's stock 422 schema.
    """
    schema = content.get("application/json", {}).get("schema", {})
    if schema == _PROBLEM_REF:
        return True
    return status == "422" and str(schema.get("$ref", "")).endswith(_STOCK_VALIDATION_SCHEMAS[0])


def normalize_problem_responses(schema: dict[str, Any]) -> dict[str, Any]:
    """Rewrite error responses to advertise ``application/problem+json``.

    Every response that references ``ProblemDetail`` (or the stock 422 schema) is
    moved to the problem media type and gets a realistic example. The now unused
    stock validation schemas are removed from the components.

    Args:
        schema: The OpenAPI document produced by FastAPI; modified in place.

    Returns:
        The same document, for convenience.
    """
    for operations in schema.get("paths", {}).values():
        for operation in operations.values():
            for status, response in operation.get("responses", {}).items():
                if not _uses_problem_schema(status, response.get("content", {})):
                    continue
                media: dict[str, Any] = {"schema": _PROBLEM_REF}
                if status in _PROBLEM_EXAMPLES:
                    name, value = _PROBLEM_EXAMPLES[status]
                    media["examples"] = {name: {"value": value}}
                response["content"] = {PROBLEM_MEDIA_TYPE: media}
                if status == "422":
                    response["description"] = "Request validation failed."
    components = schema.get("components", {}).get("schemas", {})
    for name in _STOCK_VALIDATION_SCHEMAS:
        components.pop(name, None)
    return schema


class LibraryAPI(FastAPI):
    """FastAPI application whose OpenAPI document reflects the problem+json contract."""

    @override
    def openapi(self) -> dict[str, Any]:
        """Build (once) and return the normalized OpenAPI document.

        Returns:
            The cached OpenAPI schema.
        """
        if self.openapi_schema is None:
            self.openapi_schema = normalize_problem_responses(super().openapi())
        return self.openapi_schema
