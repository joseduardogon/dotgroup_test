"""Edge cases of ``PATCH`` and ``DELETE`` on ``/api/v1/books/{id}``."""

import uuid

import pytest
from fastapi.testclient import TestClient

URL = "/api/v1/books"


@pytest.fixture
def book(client: TestClient, book_payload: dict[str, str]) -> dict[str, str]:
    """Create and return a stored book."""
    created: dict[str, str] = client.post(URL, json=book_payload).json()
    return created


def test_patch_rejects_future_publication_date(client: TestClient, book: dict[str, str]) -> None:
    """The not-in-the-future rule also applies to updates."""
    response = client.patch(f"{URL}/{book['id']}", json={"published_date": "2999-01-01"})

    assert response.status_code == 422
    assert response.json()["errors"][0]["location"] == ["body", "published_date"]


def test_patch_title_is_reflected_by_search(client: TestClient, book: dict[str, str]) -> None:
    """Renaming a book moves it from the old title to the new one in search results."""
    client.patch(f"{URL}/{book['id']}", json={"title": "Quincas Borba"})

    assert client.get(URL, params={"title": "quincas"}).json()["total"] == 1
    assert client.get(URL, params={"title": "casmurro"}).json()["total"] == 0


def test_patch_changes_publication_date_and_keeps_other_fields(
    client: TestClient, book: dict[str, str]
) -> None:
    """Only the sent field changes."""
    response = client.patch(f"{URL}/{book['id']}", json={"published_date": "1900-01-01"})

    body = response.json()
    assert body["published_date"] == "1900-01-01"
    assert body["author"] == book["author"]
    assert body["summary"] == book["summary"]


def test_patch_strictly_advances_updated_at_and_keeps_created_at(
    client: TestClient, book: dict[str, str]
) -> None:
    """``updated_at`` moves forward; ``created_at`` never changes."""
    body = client.patch(f"{URL}/{book['id']}", json={"summary": "Novo resumo."}).json()

    assert body["updated_at"] > book["updated_at"]
    assert body["created_at"] == book["created_at"]


def test_delete_with_malformed_id_returns_422(client: TestClient) -> None:
    """A non-UUID id is rejected before touching the database."""
    assert client.delete(f"{URL}/not-a-uuid").status_code == 422


def test_delete_removes_book_from_search(client: TestClient, book: dict[str, str]) -> None:
    """A deleted book no longer appears in listings."""
    client.delete(f"{URL}/{book['id']}")

    assert client.get(URL).json()["total"] == 0


def test_delete_unknown_returns_problem_document(client: TestClient) -> None:
    """Deleting a missing book yields a 404 problem with the request path."""
    missing = uuid.uuid4()

    response = client.delete(f"{URL}/{missing}")

    assert response.status_code == 404
    assert response.json()["instance"] == f"{URL}/{missing}"
