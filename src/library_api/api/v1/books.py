"""``/books`` endpoints."""

import uuid
from http import HTTPStatus
from typing import Annotated

from fastapi import APIRouter, Query, Request, Response

from library_api.api.deps import BookServiceDep
from library_api.repositories.book import BookSearchCriteria
from library_api.schemas.book import BookCreate, BookRead, BookSearchParams, BookUpdate
from library_api.schemas.common import Page, ProblemDetail

router = APIRouter(prefix="/books", tags=["Books"])

_PROBLEM_RESPONSES: dict[int | str, dict[str, object]] = {
    HTTPStatus.NOT_FOUND: {"model": ProblemDetail, "description": "Book not found."},
}


@router.post(
    "",
    response_model=BookRead,
    status_code=HTTPStatus.CREATED,
    summary="Register a book",
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
    The ``Location`` header points to the new resource.
    """
    book = service.register(payload)
    response.headers["Location"] = str(request.url_for("get_book", book_id=book.id))
    return BookRead.model_validate(book)


@router.get(
    "",
    response_model=Page[BookRead],
    summary="Search books",
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
    responses=_PROBLEM_RESPONSES,
)
def get_book(book_id: uuid.UUID, service: BookServiceDep) -> BookRead:
    """Return a single book by its identifier."""
    return BookRead.model_validate(service.get(book_id))


@router.patch(
    "/{book_id}",
    response_model=BookRead,
    summary="Update a book",
    responses={
        **_PROBLEM_RESPONSES,
        HTTPStatus.CONFLICT: {"model": ProblemDetail, "description": "Would duplicate a book."},
    },
)
def update_book(book_id: uuid.UUID, payload: BookUpdate, service: BookServiceDep) -> BookRead:
    """Partially update a book; only the fields sent are modified."""
    return BookRead.model_validate(service.update(book_id, payload))


@router.delete(
    "/{book_id}",
    status_code=HTTPStatus.NO_CONTENT,
    summary="Delete a book",
    responses=_PROBLEM_RESPONSES,
)
def delete_book(book_id: uuid.UUID, service: BookServiceDep) -> Response:
    """Permanently remove a book."""
    service.remove(book_id)
    return Response(status_code=HTTPStatus.NO_CONTENT)
