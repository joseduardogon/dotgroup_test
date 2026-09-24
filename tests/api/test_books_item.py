"""Tests for ``GET/PATCH/DELETE /api/v1/books/{id}``."""

import uuid

import pytest
from fastapi.testclient import TestClient

URL = "/api/v1/books"


@pytest.fixture
def book(client: TestClient, book_payload: dict[str, str]) -> dict[str, str]:
    """Create and return a stored book."""
    created: dict[str, str] = client.post(URL, json=book_payload).json()
    return created


def test_get_unknown_returns_404_problem(client: TestClient) -> None:
    """Unknown ids yield a problem+json 404 carrying the request id."""
    missing = uuid.uuid4()
    response = client.get(f"{URL}/{missing}", headers={"X-Request-ID": "req-123"})

    assert response.status_code == 404
    body = response.json()
    assert body["code"] == "book-not-found"
    assert body["instance"] == f"{URL}/{missing}"
    assert body["request_id"] == "req-123"
    assert response.headers["x-request-id"] == "req-123"


def test_get_malformed_id_returns_422(client: TestClient) -> None:
    """A non-UUID id is a validation error, not a 500."""
    assert client.get(f"{URL}/not-a-uuid").status_code == 422


def test_patch_updates_only_sent_fields_and_search_follows(
    client: TestClient, book: dict[str, str]
) -> None:
    """A partial update changes the field and keeps search in sync."""
    response = client.patch(f"{URL}/{book['id']}", json={"author": "Joaquim Maria"})

    assert response.status_code == 200
    body = response.json()
    assert body["author"] == "Joaquim Maria"
    assert body["title"] == book["title"]
    assert body["updated_at"] >= book["updated_at"]
    assert client.get(URL, params={"author": "joaquim"}).json()["total"] == 1
    assert client.get(URL, params={"author": "machado"}).json()["total"] == 0


@pytest.mark.parametrize("body", [{}, {"title": None}, {"unknown": 1}])
def test_patch_invalid_bodies_return_422(
    client: TestClient, book: dict[str, str], body: dict[str, object]
) -> None:
    """Empty, null and unknown-field bodies are refused."""
    assert client.patch(f"{URL}/{book['id']}", json=body).status_code == 422


def test_patch_unknown_returns_404(client: TestClient) -> None:
    """Updating a missing book is a 404."""
    assert client.patch(f"{URL}/{uuid.uuid4()}", json={"title": "x"}).status_code == 404


def test_patch_into_duplicate_returns_409_and_rolls_back(
    client: TestClient, book: dict[str, str], book_payload: dict[str, str]
) -> None:
    """Colliding with another book is a 409 and leaves the record untouched."""
    other = client.post(URL, json=book_payload | {"title": "Outro"}).json()

    response = client.patch(f"{URL}/{other['id']}", json={"title": book["title"]})

    assert response.status_code == 409
    assert client.get(f"{URL}/{other['id']}").json()["title"] == "Outro"


def test_delete_then_get_is_404(client: TestClient, book: dict[str, str]) -> None:
    """Deletion is effective and returns 204 without a body."""
    response = client.delete(f"{URL}/{book['id']}")

    assert response.status_code == 204
    assert response.content == b""
    assert client.get(f"{URL}/{book['id']}").status_code == 404
    assert client.delete(f"{URL}/{book['id']}").status_code == 404
