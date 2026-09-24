"""Unit tests for DB helpers and logging."""

import json
import logging
import sys
from datetime import UTC, datetime, timedelta, timezone
from pathlib import Path

import pytest
from sqlalchemy import text
from sqlalchemy.dialects import sqlite

from library_api.core.config import Settings, get_settings
from library_api.core.logging import JsonFormatter, configure_logging, request_id_ctx
from library_api.db.session import create_db_engine
from library_api.db.types import UTCDateTime
from library_api.models.book import Book

DIALECT = sqlite.dialect()


def test_utc_datetime_rejects_naive() -> None:
    """Naive datetimes are ambiguous and refused."""
    with pytest.raises(ValueError, match="Naive"):
        UTCDateTime().process_bind_param(datetime.fromisoformat("2020-01-01"), DIALECT)


def test_utc_datetime_round_trip() -> None:
    """Offsets are normalized to UTC and restored on load."""
    plus3 = timezone(timedelta(hours=3))
    value = datetime(2020, 1, 1, 12, tzinfo=plus3)
    kind = UTCDateTime()
    stored = kind.process_bind_param(value, DIALECT)
    assert stored == datetime(2020, 1, 1, 9, tzinfo=UTC).replace(tzinfo=None)
    assert kind.process_result_value(stored, DIALECT) == value
    assert kind.process_bind_param(None, DIALECT) is None
    assert kind.process_result_value(None, DIALECT) is None


def test_engine_rejects_non_sqlite() -> None:
    """Only SQLite is supported."""
    with pytest.raises(ValueError, match="Only SQLite"):
        create_db_engine("postgresql://u:p@h/db")


def test_engine_creates_parent_dir_and_enables_pragmas(tmp_path: Path) -> None:
    """File databases get their folder created, WAL and foreign keys."""
    engine = create_db_engine(f"sqlite:///{tmp_path / 'nested' / 'x.db'}")
    with engine.connect() as conn:
        assert conn.execute(text("PRAGMA foreign_keys")).scalar() == 1
        assert conn.execute(text("PRAGMA journal_mode")).scalar() == "wal"
    engine.dispose()


def test_json_formatter_includes_request_id_and_extras() -> None:
    """JSON logs carry the request id, extras and exceptions."""
    token = request_id_ctx.set("abc")
    try:
        try:
            raise RuntimeError("boom")
        except RuntimeError:
            record = logging.getLogger("t").makeRecord(
                "t",
                logging.ERROR,
                __file__,
                1,
                "hello %s",
                ("w",),
                sys.exc_info(),
                extra={"status_code": 201},
            )
        payload = json.loads(JsonFormatter().format(record))
    finally:
        request_id_ctx.reset(token)
    assert payload["message"] == "hello w"
    assert payload["request_id"] == "abc"
    assert payload["status_code"] == 201
    assert "RuntimeError" in payload["exception"]
    assert datetime.fromisoformat(payload["timestamp"]).tzinfo == UTC


def test_configure_logging_both_modes() -> None:
    """Both output modes install exactly one handler."""
    root = logging.getLogger()
    saved = root.handlers[:], root.level
    try:
        configure_logging("INFO", json_output=True)
        assert isinstance(root.handlers[0].formatter, JsonFormatter)
        configure_logging("INFO", json_output=False)
        assert len(root.handlers) == 1
        assert not isinstance(root.handlers[0].formatter, JsonFormatter)
    finally:
        root.handlers[:], root.level = saved


def test_settings_are_read_from_the_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    """``LIBRARY_`` variables override defaults and the accessor is cached."""
    monkeypatch.setenv("LIBRARY_DATABASE_URL", "sqlite:///./other.db")
    assert Settings().database_url == "sqlite:///./other.db"
    get_settings.cache_clear()
    assert get_settings() is get_settings()
    get_settings.cache_clear()


def test_book_repr_omits_the_summary() -> None:
    """``repr`` is short and never dumps the synopsis."""
    book = Book(title="T", author="A", summary="secret synopsis")
    assert "secret" not in repr(book)
    assert book.title_search == "t"
