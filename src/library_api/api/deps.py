"""FastAPI dependency providers (composition root for request scoped objects)."""

from collections.abc import Iterator
from typing import Annotated

from fastapi import Depends, Request
from sqlalchemy.orm import Session

from library_api.db.session import session_scope
from library_api.repositories.book import BookRepository
from library_api.services.book import BookService


def get_session(request: Request) -> Iterator[Session]:
    """Provide a request scoped database session.

    Args:
        request: Current request; gives access to the app level session factory.

    Yields:
        An open session that is closed when the request finishes.
    """
    yield from session_scope(request.app.state.session_factory)


SessionDep = Annotated[Session, Depends(get_session)]


def get_book_service(session: SessionDep) -> BookService:
    """Assemble a :class:`BookService` for the current request.

    Args:
        session: The request scoped session.

    Returns:
        A service wired to a repository on the same session.
    """
    return BookService(session, BookRepository(session))


BookServiceDep = Annotated[BookService, Depends(get_book_service)]
