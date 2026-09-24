"""ORM models. Importing this package registers every table on ``Base.metadata``."""

from library_api.models.book import Book

__all__ = ["Book"]
