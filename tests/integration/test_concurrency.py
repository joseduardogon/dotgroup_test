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
