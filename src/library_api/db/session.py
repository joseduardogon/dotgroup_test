"""Engine and session factories tuned for SQLite."""

import sqlite3
from collections.abc import Iterator
from pathlib import Path
from typing import Any

from sqlalchemy import Engine, create_engine, event
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

_IN_MEMORY_DATABASES = {None, "", ":memory:"}


def _is_in_memory(database: str | None) -> bool:
    """Tell whether a parsed SQLite ``database`` component is ephemeral.

    Args:
        database: The ``database`` attribute of a SQLAlchemy URL.

    Returns:
        ``True`` for in-memory databases.
    """
    return database in _IN_MEMORY_DATABASES


def _apply_sqlite_pragmas(
    dbapi_connection: sqlite3.Connection, _record: object, *, wal: bool
) -> None:
    """Configure a freshly opened SQLite connection.

    * ``foreign_keys`` is off by default in SQLite and must be enabled per connection.
    * ``busy_timeout`` makes writers wait for the lock instead of failing at once.
    * ``WAL`` lets readers proceed while a writer is active (file databases only).

    Args:
        dbapi_connection: The raw ``sqlite3.Connection``.
        _record: Pool bookkeeping object (unused).
        wal: Whether to switch the journal to write-ahead logging.
    """
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.execute("PRAGMA busy_timeout=5000")
    if wal:
        cursor.execute("PRAGMA journal_mode=WAL")
        cursor.execute("PRAGMA synchronous=NORMAL")
    cursor.close()


def create_db_engine(database_url: str, *, echo: bool = False) -> Engine:
    """Build an :class:`~sqlalchemy.Engine` for ``database_url``.

    In-memory databases get a :class:`~sqlalchemy.pool.StaticPool` so every
    checkout shares the single connection that owns the data. File databases
    have their parent directory created on demand.

    Args:
        database_url: A ``sqlite://`` SQLAlchemy URL.
        echo: Log every SQL statement (debugging aid).

    Returns:
        A configured engine.

    Raises:
        ValueError: If the URL does not point at SQLite.
    """
    url = make_url(database_url)
    if url.get_backend_name() != "sqlite":
        raise ValueError(f"Only SQLite is supported, got '{url.get_backend_name()}'.")

    in_memory = _is_in_memory(url.database)
    kwargs: dict[str, Any] = {"connect_args": {"check_same_thread": False}, "echo": echo}
    if in_memory:
        kwargs["poolclass"] = StaticPool
    elif url.database is not None:
        Path(url.database).expanduser().resolve().parent.mkdir(parents=True, exist_ok=True)

    engine = create_engine(url, **kwargs)
    event.listen(
        engine,
        "connect",
        lambda conn, record: _apply_sqlite_pragmas(conn, record, wal=not in_memory),
    )
    return engine


def create_session_factory(engine: Engine) -> sessionmaker[Session]:
    """Build the session factory bound to ``engine``.

    ``expire_on_commit`` is disabled so ORM objects stay readable after the
    service layer commits, which avoids a redundant ``SELECT`` per response.

    Args:
        engine: The engine sessions will use.

    Returns:
        A configured :class:`~sqlalchemy.orm.sessionmaker`.
    """
    return sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


def session_scope(factory: sessionmaker[Session]) -> Iterator[Session]:
    """Yield a session and guarantee it is closed (rolling back unfinished work).

    Args:
        factory: The session factory to draw from.

    Yields:
        An open session.
    """
    with factory() as session:
        yield session
