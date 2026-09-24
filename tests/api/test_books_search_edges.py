"""Edge cases of ``GET /api/v1/books``: pagination limits, ordering and blank filters."""

from typing import Any

import pytest
from fastapi.testclient import TestClient

URL = "/api/v1/books"

BOOKS = [
    ("Dom Casmurro", "Machado de Assis", "1899-12-01"),
    ("Dom Casmurro", "Machado de Assis", "1900-06-01"),
    ("Ensaio sobre a Cegueira", "José Saramago", "1995-01-01"),
    ("O Alquimista", "Paulo Coelho", "1988-01-01"),
]


@pytest.fixture(autouse=True)
def _seed(client: TestClient) -> None:
    """Load four books; two share title and author to force sort ties."""
    for title, author, published in BOOKS:
        response = client.post(
            URL,
            json={
                "title": title,
                "author": author,
                "published_date": published,
                "summary": "s",
            },
        )
        assert response.status_code == 201


def _search(client: TestClient, **params: str | int) -> dict[str, Any]:
    """Run a successful search and return the decoded page."""
    response = client.get(URL, params=params)
    assert response.status_code == 200
    page: dict[str, Any] = response.json()
    return page


def test_offset_beyond_total_returns_empty_page_with_real_total(client: TestClient) -> None:
    """Paging past the end is not an error: ``items`` is empty, ``total`` is intact."""
    page = _search(client, offset=1000)

    assert page["items"] == []
    assert page["total"] == len(BOOKS)
    assert page["offset"] == 1000


def test_maximum_page_size_is_accepted(client: TestClient) -> None:
    """``limit=100`` is the inclusive upper bound."""
    page = _search(client, limit=100)

    assert page["limit"] == 100
    assert len(page["items"]) == len(BOOKS)


@pytest.mark.parametrize(
    ("sort", "order", "expected_first_author"),
    [
        ("author", "asc", "José Saramago"),
        ("author", "desc", "Paulo Coelho"),
    ],
)
def test_sort_by_author(
    client: TestClient, sort: str, order: str, expected_first_author: str
) -> None:
    """Authors are ordered on their accent-folded form (``José`` sorts before ``Machado``)."""
    items = _search(client, sort=sort, order=order)["items"]

    assert items[0]["author"] == expected_first_author


def test_sort_by_created_at_follows_insertion_order(client: TestClient) -> None:
    """Descending ``created_at`` returns the most recently registered book first."""
    items = _search(client, sort="created_at", order="desc")["items"]

    assert items[0]["title"] == "O Alquimista"
    assert items[-1]["published_date"] == "1899-12-01"


def test_paging_through_sort_ties_is_stable(client: TestClient) -> None:
    """Rows tied on the sort key are never repeated or skipped across pages."""
    seen: list[str] = []
    for offset in range(len(BOOKS)):
        items = _search(client, sort="title", limit=1, offset=offset)["items"]
        seen.extend(item["id"] for item in items)

    assert len(seen) == len(BOOKS)
    assert len(set(seen)) == len(BOOKS)


def test_q_combined_with_specific_filters_is_anded(client: TestClient) -> None:
    """``q`` narrows the result further when ``title``/``author`` are also present."""
    assert _search(client, q="machado", title="dom")["total"] == 2
    assert _search(client, q="machado", author="saramago")["total"] == 0


def test_no_match_returns_empty_page(client: TestClient) -> None:
    """A search without matches yields ``total == 0`` and no items."""
    page = _search(client, q="nonexistent")

    assert page["items"] == []
    assert page["total"] == 0


@pytest.mark.parametrize("name", ["q", "title", "author"])
@pytest.mark.parametrize("value", ["", "   "])
def test_blank_text_filters_are_rejected(client: TestClient, name: str, value: str) -> None:
    """Empty or whitespace-only filters would match everything and are refused."""
    response = client.get(URL, params={name: value})

    assert response.status_code == 422
    assert response.json()["errors"][0]["location"] == ["query", name]


def test_text_filters_are_trimmed(client: TestClient) -> None:
    """Surrounding whitespace in a filter does not change the result."""
    assert _search(client, title="  alquimista  ")["total"] == 1
