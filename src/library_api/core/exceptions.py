"""Domain-level exception hierarchy.

Exceptions carry the semantics of the failure (not found, conflict, ...) and are
translated to RFC 9457 problem documents at the HTTP boundary. Inner layers
therefore never need to know about status codes beyond the class defaults.
"""

from http import HTTPStatus


class AppError(Exception):
    """Base class for every error deliberately raised by the application.

    Attributes:
        status: HTTP status the error maps to.
        code: Stable, machine readable identifier (kebab-case) exposed to clients.
        title: Short, human readable summary that does not vary between occurrences.
        detail: Occurrence specific explanation.
    """

    status: HTTPStatus = HTTPStatus.INTERNAL_SERVER_ERROR
    code: str = "internal-error"
    title: str = "Internal server error"

    def __init__(self, detail: str | None = None) -> None:
        """Create the error.

        Args:
            detail: Explanation of this specific occurrence. Defaults to the title.
        """
        self.detail = detail or self.title
        super().__init__(self.detail)


class NotFoundError(AppError):
    """Raised when a requested resource does not exist."""

    status = HTTPStatus.NOT_FOUND
    code = "resource-not-found"
    title = "Resource not found"


class ConflictError(AppError):
    """Raised when the request conflicts with the current state of a resource."""

    status = HTTPStatus.CONFLICT
    code = "resource-conflict"
    title = "Resource conflict"


class BookNotFoundError(NotFoundError):
    """Raised when no book exists for the given identifier."""

    code = "book-not-found"
    title = "Book not found"

    def __init__(self, book_id: object) -> None:
        """Create the error.

        Args:
            book_id: Identifier that was looked up.
        """
        super().__init__(f"No book exists with id '{book_id}'.")


class DuplicateBookError(ConflictError):
    """Raised when a book with the same title, author and publication date exists."""

    code = "duplicate-book"
    title = "Book already registered"

    def __init__(self) -> None:
        """Create the error with a fixed, explanatory message."""
        super().__init__(
            "A book with the same title, author and publication date is already registered."
        )
