"""create books table

Revision ID: 0001
Revises:
Create Date: 2026-09-23
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

from library_api.db.types import UTCDateTime

revision: str = "0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Create the ``books`` table and its indexes."""
    op.create_table(
        "books",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("author", sa.String(length=255), nullable=False),
        sa.Column("published_date", sa.Date(), nullable=False),
        sa.Column("summary", sa.Text(), nullable=False),
        sa.Column("title_search", sa.String(length=255), nullable=False),
        sa.Column("author_search", sa.String(length=255), nullable=False),
        sa.Column("created_at", UTCDateTime(), nullable=False),
        sa.Column("updated_at", UTCDateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id", name="pk_books"),
        sa.UniqueConstraint(
            "title_search", "author_search", "published_date", name="uq_books_identity"
        ),
    )
    op.create_index("ix_books_title_search", "books", ["title_search"])
    op.create_index("ix_books_author_search", "books", ["author_search"])


def downgrade() -> None:
    """Drop the ``books`` table."""
    op.drop_index("ix_books_author_search", table_name="books")
    op.drop_index("ix_books_title_search", table_name="books")
    op.drop_table("books")
