"""Tests for ``GET /api/v1/books`` (search, sorting and pagination)."""

import pytest
from fastapi.testclient import TestClient

URL = "/api/v1/books"

CATALOG = [
    ("Dom Casmurro", "Machado de Assis", "1899-12-01"),
    ("Memórias Póstumas de Brás Cubas", "Machado de Assis", "1881-01-01"),
    ("Ensaio sobre a Cegueira", "José Saramago", "1995-01-01"),
    ("O Alquimista", "Paulo Coelho", "1988-01-01"),
    ("100% Puro", "Autor Teste", "2001-01-01"),
]


@pytest.fixture(autouse=True)
def _seed(client: TestClient) -> None:
    """Load the catalog used by every test in this module."""
    for title, author, published in CATALOG:
        response = client.post(
            URL,
            json={
                "title": title,
                "author": author,
                "published_date": published,
                "summary": f"Summary of {title}",
            },
        )
        assert response.status_code == 201


def _titles(client: TestClient, **params: str) -> list[str]:
    """Return the titles produced by a search."""
    response = client.get(URL, params=params)
    assert response.status_code == 200
    return [item["title"] for item in response.json()["items"]]


def test_list_all_defaults_to_title_ascending(client: TestClient) -> None:
    """Without filters every book is returned, ordered by normalized title."""
    body = client.get(URL).json()

    assert body["total"] == 5
    assert body["limit"] == 20
    assert body["offset"] == 0
    assert [item["title"] for item in body["items"]] == [
        "100% Puro",
        "Dom Casmurro",
        "Ensaio sobre a Cegueira",
        "Memórias Póstumas de Brás Cubas",
        "O Alquimista",
    ]


def test_filter_by_author_is_accent_and_case_insensitive(client: TestClient) -> None:
    """``author=SARAMAGO`` and ``author=jose`` both match ``José Saramago``."""
    assert _titles(client, author="SARAMAGO") == ["Ensaio sobre a Cegueira"]
    assert _titles(client, author="jose") == ["Ensaio sobre a Cegueira"]


def test_filter_by_title_substring(client: TestClient) -> None:
    """Title filtering is a substring match ignoring accents."""
    assert _titles(client, title="memorias postumas") == ["Memórias Póstumas de Brás Cubas"]


def test_filters_combine_with_and(client: TestClient) -> None:
    """Title AND author must both match."""
    assert _titles(client, title="dom", author="machado") == ["Dom Casmurro"]
    assert _titles(client, title="dom", author="saramago") == []


def test_q_matches_title_or_author(client: TestClient) -> None:
    """``q`` searches both columns."""
    assert _titles(client, q="machado") == ["Dom Casmurro", "Memórias Póstumas de Brás Cubas"]
    assert _titles(client, q="alquimista") == ["O Alquimista"]


def test_like_wildcards_are_escaped(client: TestClient) -> None:
    """``%`` and ``_`` are literals, not wildcards."""
    assert _titles(client, title="100%") == ["100% Puro"]
    assert _titles(client, title="%") == ["100% Puro"]
    assert _titles(client, title="_") == []


def test_sort_and_order(client: TestClient) -> None:
    """Sorting by publication date descending puts the newest first."""
    titles = _titles(client, sort="published_date", order="desc")

    assert titles[0] == "100% Puro"
    assert titles[-1] == "Memórias Póstumas de Brás Cubas"


def test_pagination_windows_and_total(client: TestClient) -> None:
    """``limit``/``offset`` window the results while ``total`` stays constant."""
    first = client.get(URL, params={"limit": 2, "offset": 0}).json()
    last = client.get(URL, params={"limit": 2, "offset": 4}).json()

    assert first["total"] == last["total"] == 5
    assert len(first["items"]) == 2
    assert len(last["items"]) == 1
    first_ids = {item["id"] for item in first["items"]}
    assert first_ids.isdisjoint(item["id"] for item in last["items"])


@pytest.mark.parametrize(
    "params",
    [{"limit": 0}, {"limit": 101}, {"offset": -1}, {"sort": "nope"}, {"order": "up"}, {"x": "1"}],
)
def test_invalid_query_parameters_return_422(
    client: TestClient, params: dict[str, str | int]
) -> None:
    """Out-of-range or unknown query parameters are rejected."""
    assert client.get(URL, params=params).status_code == 422
