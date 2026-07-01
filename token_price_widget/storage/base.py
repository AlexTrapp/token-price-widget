"""Abstract storage interface."""

from abc import ABC, abstractmethod
from datetime import datetime


class BaseStorage(ABC):
    @abstractmethod
    def save_snapshot(self, token: str, prices: dict, raw_steps: list, ts: datetime):
        """Persist one price snapshot."""

    @abstractmethod
    def get_history(self, token: str, since: datetime = None, limit: int = 500) -> list:
        """Return snapshots newest-first as list of dicts."""

    @abstractmethod
    def get_latest(self, token: str) -> dict | None:
        """Return the single most recent snapshot for a token."""

    @abstractmethod
    def prune(self, token: str, before: datetime):
        """Delete snapshots older than before."""

    @abstractmethod
    def close(self):
        """Release any connections."""
