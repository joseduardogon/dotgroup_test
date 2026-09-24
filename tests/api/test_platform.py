"""Tests for health probes, error handling, middleware and OpenAPI."""

import logging

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine

from library_api.core.config import Settings
from library_api.main import create_app


def _app(client: TestClient) -> FastAPI:
    """Return the FastAPI instance behind ``client`` with proper typing."""
    app = client.app
    assert isinstance(app, FastAPI)
    return app


def test_liveness(client: TestClient) -> None:
    """The liveness probe always answers ok."""
    assert client.get("/health/live").json() == {"status": "ok"}


def test_readiness_ok(client: TestClient) -> None:
    """Readiness is ok when the database answers."""
    assert client.get("/health/ready").json() == {"status": "ok"}


def test_readiness_unavailable_when_database_is_down(client: TestClient) -> None:
    """A broken database yields 503 instead of an exception."""
    factory = _app(client).state.session_factory
    factory.configure(bind=create_engine("sqlite:////nonexistent-dir/x.db"))

    response = client.get("/health/ready")

    assert response.status_code == 503
    assert response.json() == {"status": "unavailable"}


def test_request_id_is_generated_and_unsafe_ids_are_replaced(client: TestClient) -> None:
    """Missing or malicious request ids are replaced with a UUID."""
    generated = client.get("/health/live").headers["x-request-id"]
    assert len(generated) == 32

    replaced = client.get("/health/live", headers={"X-Request-ID": "bad id with spaces"})
    assert replaced.headers["x-request-id"] != "bad id with spaces"


def test_access_log_is_emitted(client: TestClient, caplog: pytest.LogCaptureFixture) -> None:
    """Each request produces one access log record with timing."""
    with caplog.at_level(logging.INFO, logger="library_api.access"):
        client.get("/health/live")

    record = next(r for r in caplog.records if r.name == "library_api.access")
    assert record.__dict__["status_code"] == 200
    assert record.__dict__["duration_ms"] >= 0


def test_unknown_route_and_wrong_method_are_problem_json(client: TestClient) -> None:
    """Framework errors use the same problem format and keep the Allow header."""
    missing = client.get("/nope")
    assert missing.status_code == 404
    assert missing.headers["content-type"] == "application/problem+json"
    assert missing.json()["code"] == "not-found"

    wrong = client.put("/api/v1/books")
    assert wrong.status_code == 405
    assert wrong.headers["allow"]


def test_unexpected_errors_are_hidden_from_clients(client: TestClient) -> None:
    """Unhandled exceptions produce a generic 500 without leaking internals."""

    def boom() -> None:
        """Fail with an internal message that must never reach the client."""
        raise RuntimeError("secret internals")

    _app(client).add_api_route("/boom", boom)
    response = client.get("/boom")

    assert response.status_code == 500
    assert response.json()["code"] == "internal-error"
    assert "secret" not in response.text


def test_root_redirects_to_docs(client: TestClient) -> None:
    """The bare host redirects to the interactive docs."""
    response = client.get("/", follow_redirects=False)

    assert response.status_code == 307
    assert response.headers["location"] == "/docs"


def test_openapi_documents_every_endpoint(client: TestClient) -> None:
    """The schema exposes the books and health operations."""
    paths = client.get("/openapi.json").json()["paths"]

    assert set(paths["/api/v1/books"]) == {"get", "post"}
    assert set(paths["/api/v1/books/{book_id}"]) == {"get", "patch", "delete"}
    assert "/health/ready" in paths


def test_docs_can_be_disabled() -> None:
    """Production can hide the documentation endpoints."""
    app = create_app(Settings(database_url="sqlite://", docs_enabled=False))
    with TestClient(app) as client:
        assert client.get("/openapi.json").status_code == 404
