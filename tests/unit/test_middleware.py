"""Unit tests for :class:`~library_api.core.middleware.RequestContextMiddleware` at ASGI level."""

import asyncio
import logging
from typing import Any

import pytest
from starlette.types import Message, Receive, Scope, Send

from library_api.core.logging import request_id_ctx
from library_api.core.middleware import REQUEST_ID_HEADER, RequestContextMiddleware


def _scope(request_id: str | None = None, scope_type: str = "http") -> Scope:
    """Build a minimal ASGI scope, optionally carrying an ``X-Request-ID`` header."""
    headers = [] if request_id is None else [(b"x-request-id", request_id.encode())]
    return {"type": scope_type, "method": "GET", "path": "/probe", "headers": headers}


class _Recorder:
    """Downstream app that records what the middleware exposed to it."""

    def __init__(self, status: int = 200, *, fail: bool = False) -> None:
        """Configure the fake application."""
        self.status = status
        self.fail = fail
        self.seen_context: str | None = None
        self.seen_state: str | None = None
        self.called_with: Scope | None = None

    async def __call__(self, scope: Scope, _receive: Receive, send: Send) -> None:
        """Record the ambient request id and answer (or fail)."""
        self.called_with = scope
        self.seen_context = request_id_ctx.get()
        self.seen_state = scope.get("state", {}).get("request_id")
        if self.fail:
            raise RuntimeError("downstream failure")
        await send({"type": "http.response.start", "status": self.status, "headers": []})
        await send({"type": "http.response.body", "body": b""})


def _run(app: RequestContextMiddleware, scope: Scope) -> list[Message]:
    """Drive ``app`` with ``scope`` and return every message it sent."""
    sent: list[Message] = []

    async def receive() -> Message:
        """Provide an empty request body."""
        return {"type": "http.request", "body": b"", "more_body": False}

    async def send(message: Message) -> None:
        """Collect outgoing messages."""
        sent.append(message)

    asyncio.run(app(scope, receive, send))
    return sent


def _header(messages: list[Message], name: str) -> str | None:
    """Return a response header value from the ``http.response.start`` message."""
    start = next(m for m in messages if m["type"] == "http.response.start")
    values: list[tuple[bytes, bytes]] = start["headers"]
    return next((v.decode() for k, v in values if k.decode().lower() == name.lower()), None)


def test_safe_incoming_request_id_is_propagated_everywhere() -> None:
    """A well-formed id reaches the context var, the request state and the response."""
    downstream = _Recorder()

    messages = _run(RequestContextMiddleware(downstream), _scope("client-id-42"))

    assert downstream.seen_context == "client-id-42"
    assert downstream.seen_state == "client-id-42"
    assert _header(messages, REQUEST_ID_HEADER) == "client-id-42"


@pytest.mark.parametrize("unsafe", ["has space", "semi;colon", "x" * 129, "new\tline"])
def test_unsafe_incoming_request_id_is_replaced_by_a_uuid(unsafe: str) -> None:
    """Values outside ``[A-Za-z0-9._-]{1,128}`` are never echoed."""
    downstream = _Recorder()

    messages = _run(RequestContextMiddleware(downstream), _scope(unsafe))

    generated = _header(messages, REQUEST_ID_HEADER)
    assert generated is not None
    assert generated != unsafe
    assert len(generated) == 32


def test_missing_request_id_is_generated_per_request() -> None:
    """Every request without an id gets its own fresh value."""
    middleware = RequestContextMiddleware(_Recorder())

    first = _header(_run(middleware, _scope()), REQUEST_ID_HEADER)
    second = _header(_run(middleware, _scope()), REQUEST_ID_HEADER)

    assert first != second


def test_context_var_is_reset_after_the_request() -> None:
    """The request id does not leak into unrelated code after the response."""
    _run(RequestContextMiddleware(_Recorder()), _scope("abc"))

    assert request_id_ctx.get() is None


def test_context_var_is_reset_even_when_the_app_raises() -> None:
    """Failures still clean up and still produce an access log record."""
    with pytest.raises(RuntimeError):
        _run(RequestContextMiddleware(_Recorder(fail=True)), _scope("abc"))

    assert request_id_ctx.get() is None


@pytest.mark.parametrize("scope_type", ["lifespan", "websocket"])
def test_non_http_scopes_pass_through_untouched(scope_type: str) -> None:
    """Lifespan and websocket connections are forwarded without modification."""
    downstream = _Recorder()
    scope = _scope(scope_type=scope_type)

    async def receive() -> Message:
        """Provide no messages."""
        return {}

    async def send(_: Message) -> None:
        """Discard outgoing messages."""

    asyncio.run(RequestContextMiddleware(downstream)(scope, receive, send))

    assert downstream.called_with is scope
    assert "state" not in scope
    assert request_id_ctx.get() is None


def test_access_log_records_method_path_status_and_duration(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """One structured access record is emitted per request."""
    with caplog.at_level(logging.INFO, logger="library_api.access"):
        _run(RequestContextMiddleware(_Recorder(status=418)), _scope("abc"))

    fields: dict[str, Any] = next(
        r for r in caplog.records if r.name == "library_api.access"
    ).__dict__
    assert fields["method"] == "GET"
    assert fields["path"] == "/probe"
    assert fields["status_code"] == 418
    assert fields["duration_ms"] >= 0
