"""Declarative base with deterministic constraint names.

Explicit naming conventions are what make Alembic autogenerate and batch
migrations on SQLite reliable: anonymous constraints cannot be dropped or
altered later on.
"""

from sqlalchemy import MetaData
from sqlalchemy.orm import DeclarativeBase

NAMING_CONVENTION = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}


class Base(DeclarativeBase):
    """Root of every ORM model in the application."""

    metadata = MetaData(naming_convention=NAMING_CONVENTION)
