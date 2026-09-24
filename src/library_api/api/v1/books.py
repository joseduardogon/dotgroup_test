"""``/books`` endpoints."""

import uuid
from http import HTTPStatus
from typing import Annotated

from fastapi import APIRouter, Path, Query, Request, Response

from library_api.api.deps import BookServiceDep
from library_api.repositories.book import BookSearchCriteria
from library_api.schemas.book import BookCreate, BookRead, BookSearchParams, BookUpdate
from library_api.schemas.common import Page, ProblemDetail

router = APIRouter(prefix="/books", tags=["Books"])

BookId = Annotated[
    uuid.UUID,
    Path(
        description="Identifier of the book (UUID v4).",
        examples=["0b1f3a52-6f0e-4a3e-9c53-0f6a3c1f9a11"],
    ),
]

_PROBLEM_RESPONSES: dict[int | str, dict[str, object]] = {
    HTTPStatus.NOT_FOUND: {"model": ProblemDetail, "description": "Book not found."},
}


@router.post(
    "",
    response_model=BookRead,
    status_code=HTTPStatus.CREATED,
    summary="Register a book",
    response_description="The stored book, including its generated id and timestamps.",
    responses={
        HTTPStatus.CONFLICT: {"model": ProblemDetail, "description": "Book already registered."},
        HTTPStatus.UNPROCESSABLE_ENTITY: {
            "model": ProblemDetail,
            "description": "Invalid payload.",
        },
    },
)
def create_book(
    payload: BookCreate, service: BookServiceDep, request: Request, response: Response
) -> BookRead:
    """Register a new book in the library.

    A book is identified by the (accent and case insensitive) combination of
    title, author and publication date; registering it twice yields ``409``.
    The ``Location`` header holds the new resource's path (a relative reference,
    so it never reflects the client-supplied ``Host`` header).
    """
    book = service.register(payload)
    response.headers["Location"] = request.app.url_path_for("get_book", book_id=book.id)
    return BookRead.model_validate(book)


@router.get(
    "",
    response_model=Page[BookRead],
    summary="Search books",
    response_description="A page of matching books plus the total number of matches.",
    responses={
        HTTPStatus.UNPROCESSABLE_ENTITY: {"model": ProblemDetail, "description": "Invalid query."},
    },
)
def list_books(
    params: Annotated[BookSearchParams, Query()], service: BookServiceDep
) -> Page[BookRead]:
    """Search and list books with pagination.

    Matching is case and accent insensitive and uses substring semantics:

    * ``title`` - the title contains the text.
    * ``author`` - the author contains the text.
    * ``q`` - the title **or** the author contains the text.

    Combined filters are ANDed. Results are ordered by ``sort``/``order`` with the
    id as tiebreaker, so paging is stable.
    """
    items, total = service.search(BookSearchCriteria(**params.model_dump()))
    return Page[BookRead](
        items=[BookRead.model_validate(book) for book in items],
        total=total,
        limit=params.limit,
        offset=params.offset,
    )


@router.get(
    "/{book_id}",
    response_model=BookRead,
    summary="Get a book",
    response_description="The requested book.",
    responses=_PROBLEM_RESPONSES,
)
def get_book(book_id: BookId, service: BookServiceDep) -> BookRead:
    """Return a single book by its identifier."""
    return BookRead.model_validate(service.get(book_id))


@router.patch(
    "/{book_id}",
    response_model=BookRead,
    summary="Update a book",
    response_description="The book after the update.",
    responses={
        **_PROBLEM_RESPONSES,
        HTTPStatus.CONFLICT: {"model": ProblemDetail, "description": "Would duplicate a book."},
    },
)
def update_book(book_id: BookId, payload: BookUpdate, service: BookServiceDep) -> BookRead:
    """Partially update a book; only the fields sent are modified."""
    return BookRead.model_validate(service.update(book_id, payload))


@router.delete(
    "/{book_id}",
    status_code=HTTPStatus.NO_CONTENT,
    summary="Delete a book",
    response_description="The book was deleted; the response has no body.",
    responses=_PROBLEM_RESPONSES,
)
def delete_book(book_id: BookId, service: BookServiceDep) -> Response:
    """Permanently remove a book."""
    service.remove(book_id)
    return Response(status_code=HTTPStatus.NO_CONTENT)
