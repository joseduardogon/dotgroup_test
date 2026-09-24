"""Application settings following the twelve-factor "config in the environment" rule."""

from functools import lru_cache
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict

from library_api import __version__

Environment = Literal["development", "testing", "production"]
LogLevel = Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]


class Settings(BaseSettings):
    """Typed, validated runtime configuration.

    Values are read from environment variables prefixed with ``LIBRARY_`` and,
    for local development convenience, from a ``.env`` file. Unknown variables
    are ignored so the process can share an environment with other tooling.

    Attributes:
        app_name: Human readable service name shown in the OpenAPI document.
        app_version: Semantic version of the running build.
        environment: Deployment stage; influences defaults such as logging.
        database_url: SQLAlchemy URL. Only SQLite is officially supported.
        log_level: Minimum severity emitted by the application loggers.
        log_json: Emit one JSON object per log line (recommended in production).
        docs_enabled: Expose Swagger UI, ReDoc and the OpenAPI schema.
    """

    model_config = SettingsConfigDict(
        env_prefix="LIBRARY_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_name: str = "Virtual Library API"
    app_version: str = __version__
    environment: Environment = "development"
    database_url: str = "sqlite:///./data/library.db"
    log_level: LogLevel = "INFO"
    log_json: bool = False
    docs_enabled: bool = True


@lru_cache
def get_settings() -> Settings:
    """Return the process-wide settings instance.

    The result is cached so the environment is parsed exactly once. Tests that
    need different values should build their own :class:`Settings` and hand it
    to :func:`library_api.main.create_app` instead of mutating the cache.

    Returns:
        The lazily created, immutable-by-convention settings object.
    """
    return Settings()
