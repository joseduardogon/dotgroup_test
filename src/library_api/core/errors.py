"""Translation of exceptions into RFC 9457 problem responses."""

import logging
from http import HTTPStatus
from typing import cast

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from library_api.core.exceptions import AppError
from library_api.core.logging import request_id_ctx
from library_api.schemas.common import FieldError, ProblemDetail

PROBLEM_MEDIA_TYPE = "application/problem+json"
_PROBLEM_URN = "urn:library-api:problem:{code}"
_logger = logging.getLogger(__name__)


def _problem(
    request: Request,
    *,
    status: int,
    title: str,
    detail: str,
    code: str,
    errors: list[FieldError] | None = None,
    headers: dict[str, str] | None = None,
) -> JSONResponse:
    """Build a problem+json response.

    Args:
        request: The failing request; supplies the ``instance`` member.
        status: HTTP status code.
        title: Stable summary of the problem type.
        detail: Occurrence specific explanation.
        code: Machine readable identifier, also used to mint the ``type`` URN.
        errors: Optional field level errors.
        headers: Extra response headers (e.g. ``Allow``).

    Returns:
        A ready to send response with the problem media type.
    """
    body = ProblemDetail(
        type=_PROBLEM_URN.format(code=code),
        title=title,
        status=status,
        detail=detail,
        instance=request.url.path,
        code=code,
        request_id=request_id_ctx.get(),
        errors=errors,
    )
    return JSONResponse(
        body.model_dump(mode="json", exclude_none=True),
        status_code=status,
        media_type=PROBLEM_MEDIA_TYPE,
        headers=headers,
    )


async def _handle_app_error(request: Request, exc: Exception) -> JSONResponse:
    """Render a domain :class:`AppError`.

    Args:
        request: The failing request.
        exc: The raised error; guaranteed to be an ``AppError`` by registration.

    Returns:
        The problem response.
    """
    error = cast("AppError", exc)
    return _problem(
        request, status=error.status, title=error.title, detail=error.detail, code=error.code
    )


async def _handle_validation_error(request: Request, exc: Exception) -> JSONResponse:
    """Render request validation failures as 422 problems.

    Args:
        request: The failing request.
        exc: The validation error raised by FastAPI.

    Returns:
        A 422 problem listing every offending field.
    """
    validation_error = cast("RequestValidationError", exc)
    errors = [
        FieldError(location=list(err["loc"]), message=err["msg"], type=err["type"])
        for err in validation_error.errors()
    ]
    return _problem(
        request,
        status=HTTPStatus.UNPROCESSABLE_ENTITY,
        title="Request validation failed",
        detail=f"{len(errors)} validation error(s) in the request.",
        code="validation-error",
        errors=errors,
    )


async def _handle_http_exception(request: Request, exc: Exception) -> JSONResponse:
    """Render framework level HTTP errors (404 routes, 405, ...) as problems.

    Args:
        request: The failing request.
        exc: The Starlette HTTP exception.

    Returns:
        The problem response, preserving headers such as ``Allow``.
    """
    http_error = cast("StarletteHTTPException", exc)
    phrase = HTTPStatus(http_error.status_code).phrase
    return _problem(
        request,
        status=http_error.status_code,
        title=phrase,
        detail=str(http_error.detail),
        code=phrase.lower().replace(" ", "-"),
        headers=dict(http_error.headers) if http_error.headers else None,
    )


async def _handle_unexpected_error(request: Request, exc: Exception) -> JSONResponse:
    """Last-resort handler: log the traceback, hide internals from the client.

    Args:
        request: The failing request.
        exc: Any unhandled exception.

    Returns:
        A generic 500 problem carrying only the request id for support lookups.
    """
    _logger.error("Unhandled exception", exc_info=exc)
    return _problem(
        request,
        status=HTTPStatus.INTERNAL_SERVER_ERROR,
        title=AppError.title,
        detail="An unexpected error occurred. Quote the request id when reporting it.",
        code=AppError.code,
    )


def register_exception_handlers(app: FastAPI) -> None:
    """Install all problem+json handlers on ``app``.

    Args:
        app: The application to configure.
    """
    app.add_exception_handler(AppError, _handle_app_error)
    app.add_exception_handler(RequestValidationError, _handle_validation_error)
    app.add_exception_handler(StarletteHTTPException, _handle_http_exception)
    app.add_exception_handler(Exception, _handle_unexpected_error)
