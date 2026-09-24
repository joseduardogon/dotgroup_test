"""Structured logging with request correlation.

A :class:`contextvars.ContextVar` carries the current request id so every log
record emitted while serving a request can be correlated without threading the
id through function signatures.
"""

import json
import logging
import sys
from contextvars import ContextVar
from datetime import UTC, datetime
from typing import Any, override

request_id_ctx: ContextVar[str | None] = ContextVar("request_id", default=None)

_RESERVED = frozenset(logging.LogRecord("", 0, "", 0, "", None, None).__dict__) | {
    "message",
    "asctime",
    "taskName",
}


class JsonFormatter(logging.Formatter):
    """Render each record as a single-line JSON document.

    Extra fields passed via ``logger.info("msg", extra={...})`` are merged at the
    top level, which keeps the output friendly to log aggregators.
    """

    @override
    def format(self, record: logging.LogRecord) -> str:
        """Serialize ``record``.

        Args:
            record: The log record to render.

        Returns:
            A compact JSON string without trailing newline.
        """
        payload: dict[str, Any] = {
            "timestamp": datetime.fromtimestamp(record.created, tz=UTC).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        if (request_id := request_id_ctx.get()) is not None:
            payload["request_id"] = request_id
        payload.update({k: v for k, v in record.__dict__.items() if k not in _RESERVED})
        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)
        return json.dumps(payload, default=str, ensure_ascii=False)


class _RequestIdFilter(logging.Filter):
    """Inject the current request id into plain-text records."""

    @override
    def filter(self, record: logging.LogRecord) -> bool:
        """Attach ``request_id`` to ``record``.

        Args:
            record: The record being processed.

        Returns:
            Always ``True``; the filter only enriches records.
        """
        record.request_id = request_id_ctx.get() or "-"
        return True


def configure_logging(level: str = "INFO", *, json_output: bool = False) -> None:
    """Configure the root logger idempotently.

    Args:
        level: Minimum severity, as a ``logging`` level name.
        json_output: Use :class:`JsonFormatter` instead of the human friendly format.
    """
    handler = logging.StreamHandler(sys.stdout)
    if json_output:
        handler.setFormatter(JsonFormatter())
    else:
        handler.addFilter(_RequestIdFilter())
        handler.setFormatter(
            logging.Formatter("%(asctime)s %(levelname)-8s [%(request_id)s] %(name)s: %(message)s")
        )
    root = logging.getLogger()
    root.handlers[:] = [handler]
    root.setLevel(level)
    logging.getLogger("uvicorn.access").disabled = True
