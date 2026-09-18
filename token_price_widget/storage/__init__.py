"""Storage backend factory."""

from .base import BaseStorage
from .json_file import JSONFileStorage
from .sqlite import SQLiteStorage


def get_storage(database_url: str) -> BaseStorage:
    if database_url.startswith("sqlite://"):
        return SQLiteStorage(database_url)
    if database_url.startswith("json://"):
        return JSONFileStorage(database_url)
    raise ValueError(
        f"Unsupported database_url scheme: {database_url!r}. "
        "Built-in backends: sqlite://, json://. "
        "To add another (e.g. Postgres, Mongo), implement BaseStorage "
        "and register it here — see CONTRIBUTING.md."
    )
