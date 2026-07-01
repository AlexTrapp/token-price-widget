"""Flat JSON file storage backend — zero deps, useful for dev/testing."""

import json
import re
from datetime import datetime, timezone
from pathlib import Path

from .base import BaseStorage


class JSONFileStorage(BaseStorage):
    def __init__(self, url: str):
        # url: "json:///path/to/prices.json"
        path = re.sub(r"^json:///", "", url)
        self._path = Path(path)
        if self._path.exists():
            self._data = json.loads(self._path.read_text())
        else:
            self._data = {}

    def _save(self):
        self._path.write_text(json.dumps(self._data, indent=2))

    def save_snapshot(self, token, prices, raw_steps, ts=None):
        ts = ts or datetime.now(timezone.utc)
        self._data.setdefault(token, []).append(
            {
                "ts": ts.isoformat(),
                "price_hive": prices.get("hive"),
                "price_usd": prices.get("usd"),
                "raw_steps": raw_steps,
            }
        )
        self._save()

    def get_history(self, token, since=None, limit=500):
        rows = self._data.get(token, [])
        if since:
            rows = [r for r in rows if r["ts"] >= since.isoformat()]
        return list(reversed(rows))[:limit]

    def get_latest(self, token):
        rows = self._data.get(token, [])
        return rows[-1] if rows else None

    def prune(self, token, before):
        rows = self._data.get(token, [])
        self._data[token] = [r for r in rows if r["ts"] >= before.isoformat()]
        self._save()

    def close(self):
        pass
