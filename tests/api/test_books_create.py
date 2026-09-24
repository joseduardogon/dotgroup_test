"""Tests for ``POST /api/v1/books``."""

import pytest
from fastapi.testclient import TestClient

URL = "/api/v1/books"


def test_create_returns_201_location_and_body(
    client: TestClient, book_payload: dict[str, str]
) -> None:
    """A valid payload is persisted and echoed with server generated fields."""
    response = client.post(URL, json=book_payload)

    assert response.status_code == 201
    body = response.json()
    assert response.headers["location"].endswith(f"{URL}/{body['id']}")
    assert body["title"] == "Dom Casmurro"
    assert body["created_at"]
    assert body["updated_at"]
    assert client.get(response.headers["location"]).json() == body


def test_location_is_relative_and_ignores_the_host_header(
    client: TestClient, book_payload: dict[str, str]
) -> None:
    """``Location`` never reflects a client-supplied ``Host``."""
    response = client.post(URL, json=book_payload, headers={"Host": "evil.example"})

    assert response.headers["location"] == f"{URL}/{response.json()['id']}"


@pytest.mark.parametrize("field", ["title", "author", "summary"])
def test_control_characters_are_rejected(
    client: TestClient, book_payload: dict[str, str], field: str
) -> None:
    """NUL bytes in text fields are a validation error."""
    response = client.post(URL, json=book_payload | {field: "bad\x00value"})

    assert response.status_code == 422


def test_multiline_summary_is_accepted(client: TestClient, book_payload: dict[str, str]) -> None:
    """Newlines remain valid in summaries."""
    assert client.post(URL, json=book_payload | {"summary": "a\nb"}).status_code == 201


def test_create_duplicate_returns_409_ignoring_case_and_accents(
    client: TestClient, book_payload: dict[str, str]
) -> None:
    """The natural key is compared in normalized form."""
    client.post(URL, json=book_payload)
    twin = book_payload | {"title": "  DOM   CASMURRÓ ", "author": "machado de ássis"}

    response = client.post(URL, json=twin)

    assert response.status_code == 409
    assert response.headers["content-type"] == "application/problem+json"
    assert response.json()["code"] == "duplicate-book"


def test_same_title_different_date_is_a_distinct_book(
    client: TestClient, book_payload: dict[str, str]
) -> None:
    """A new edition (different date) is allowed."""
    client.post(URL, json=book_payload)
    assert client.post(URL, json=book_payload | {"published_date": "1900-01-01"}).status_code == 201


def test_create_validation_errors_are_problem_details(client: TestClient) -> None:
    """Invalid input yields 422 with a per-field error list."""
    response = client.post(URL, json={"title": "", "published_date": "2999-01-01"})

    assert response.status_code == 422
    body = response.json()
    assert body["code"] == "validation-error"
    assert body["status"] == 422
    locations = {tuple(error["location"]) for error in body["errors"]}
    assert ("body", "title") in locations
    assert ("body", "author") in locations
    assert ("body", "published_date") in locations
    assert ("body", "summary") in locations


def test_create_rejects_unknown_field(client: TestClient, book_payload: dict[str, str]) -> None:
    """Unknown properties are refused."""
    assert client.post(URL, json=book_payload | {"isbn": "1"}).status_code == 422
