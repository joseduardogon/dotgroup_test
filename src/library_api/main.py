"""Application factory and ASGI entrypoint."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.responses import RedirectResponse

from library_api.api import health
from library_api.api.v1 import books
from library_api.core.config import Settings, get_settings
from library_api.core.errors import register_exception_handlers
from library_api.core.logging import configure_logging
from library_api.core.middleware import RequestContextMiddleware
from library_api.db.session import create_db_engine, create_session_factory

API_V1_PREFIX = "/api/v1"

DESCRIPTION = """
Register and search books in a virtual library.

* **Search** by title, by author, or free text (`q`); accent and case insensitive.
* **Errors** follow [RFC 9457](https://www.rfc-editor.org/rfc/rfc9457) (`application/problem+json`).
* **Tracing**: send `X-Request-ID`; it is echoed back and present in every log line.
"""

TAGS_METADATA = [
    {"name": "Books", "description": "Register, search, update and remove books."},
    {"name": "Health", "description": "Liveness and readiness probes for orchestrators."},
]


def create_app(settings: Settings | None = None) -> FastAPI:
    """Build a fully wired application.

    Taking ``settings`` as a parameter (instead of reading globals) keeps the
    factory pure and lets tests run isolated apps against in-memory databases.

    Args:
        settings: Configuration to use. Defaults to the environment based settings.

    Returns:
        The configured :class:`~fastapi.FastAPI` instance.
    """
    settings = settings or get_settings()
    configure_logging(settings.log_level, json_output=settings.log_json)

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        """Create the engine on startup and dispose of it on shutdown.

        Args:
            app: The application being started.

        Yields:
            Control to the running application.
        """
        engine = create_db_engine(settings.database_url)
        app.state.engine = engine
        app.state.session_factory = create_session_factory(engine)
        try:
            yield
        finally:
            engine.dispose()

    app = FastAPI(
        title=settings.app_name,
        version=settings.app_version,
        description=DESCRIPTION,
        openapi_tags=TAGS_METADATA,
        contact={"name": "José Eduardo Gontijo de Carvalho"},
        license_info={"name": "MIT"},
        docs_url="/docs" if settings.docs_enabled else None,
        redoc_url="/redoc" if settings.docs_enabled else None,
        openapi_url="/openapi.json" if settings.docs_enabled else None,
        lifespan=lifespan,
    )
    app.add_middleware(RequestContextMiddleware)
    register_exception_handlers(app)
    app.include_router(health.router)
    app.include_router(books.router, prefix=API_V1_PREFIX)

    @app.get("/", include_in_schema=False)
    def root() -> RedirectResponse:
        """Send visitors of the bare host to the interactive documentation.

        Returns:
            A redirect to ``/docs``.
        """
        return RedirectResponse("/docs")

    return app
