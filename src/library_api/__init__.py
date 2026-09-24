"""Virtual Library API.

A small but production-grade HTTP service that lets clients register books and
search them by title or author. The package follows a layered architecture:

* ``api`` - HTTP transport (routers, dependencies, serialization).
* ``services`` - application/use-case logic and transaction boundaries.
* ``repositories`` - persistence gateway, the only layer that builds SQL.
* ``models`` / ``db`` - ORM mapping and database plumbing.
* ``schemas`` - Pydantic contracts exposed on the wire.
* ``core`` - cross-cutting concerns (settings, logging, errors, middleware).
"""

from importlib.metadata import version

__version__ = version("dotgroup-test")

__all__ = ["__version__"]
