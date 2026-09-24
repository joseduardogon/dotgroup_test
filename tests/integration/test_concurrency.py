"""Integration test: the duplicate guarantee holds under concurrent writers."""

from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from library_api.core.config import Settings
from library_api.db.base import Base
from library_api.main import create_app

pytestmark = pytest.mark.integration

WRITERS = 8


def test_concurrent_identical_posts_create_exactly_one_book(
    tmp_path: Path, book_payload: dict[str, str]
) -> None:
    """Racing writers are serialized by the database constraint, not by luck."""
    app = create_app(Settings(database_url=f"sqlite:///{tmp_path / 'race.db'}", log_level="ERROR"))

    with TestClient(app) as owner:
        Base.metadata.create_all(app.state.engine)

        def post(_: int) -> int:
            """Send the same payload from an independent client."""
            return TestClient(app).post("/api/v1/books", json=book_payload).status_code

        with ThreadPoolExecutor(max_workers=WRITERS) as pool:
            statuses = list(pool.map(post, range(WRITERS)))

        assert sorted(statuses) == [201] + [409] * (WRITERS - 1)
        assert owner.get("/api/v1/books").json()["total"] == 1


def test_concurrent_deletes_of_the_same_book_succeed_exactly_once(
    tmp_path: Path, book_payload: dict[str, str]
) -> None:
    """Racing deletes on one id yield exactly one 204 and 404 for every other writer."""
    app = create_app(
        Settings(database_url=f"sqlite:///{tmp_path / 'race-delete.db'}", log_level="ERROR")
    )

    with TestClient(app) as owner:
        Base.metadata.create_all(app.state.engine)
        book_id = owner.post("/api/v1/books", json=book_payload).json()["id"]

        def delete(_: int) -> int:
            """Send a delete for the same id from an independent client."""
            return TestClient(app).delete(f"/api/v1/books/{book_id}").status_code

        with ThreadPoolExecutor(max_workers=WRITERS) as pool:
            statuses = list(pool.map(delete, range(WRITERS)))

        assert sorted(statuses) == [204] + [404] * (WRITERS - 1)
        assert owner.get(f"/api/v1/books/{book_id}").status_code == 404
