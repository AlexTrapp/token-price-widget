"""SQLite storage backend (default)."""

import json
import re
import sqlite3
from datetime import datetime, timezone

from .base import BaseStorage


class SQLiteStorage(BaseStorage):
    def __init__(self, url: str):
        # url: "sqlite:///path/to/file.db" or "sqlite:///:memory:"
        path = re.sub(r"^sqlite:///", "", url)
        self._conn = sqlite3.connect(path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._migrate()

    def _migrate(self):
        self._conn.execute("""
            CREATE TABLE IF NOT EXISTS price_snapshots (
                id        INTEGER PRIMARY KEY AUTOINCREMENT,
                token     TEXT NOT NULL,
                ts        TEXT NOT NULL,
                price_hive REAL,
                price_usd  REAL,
                raw_steps  TEXT
            )
        """)
        self._conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_token_ts ON price_snapshots (token, ts)"
        )
        self._conn.commit()

    def save_snapshot(self, token, prices, raw_steps, ts=None):
        ts = ts or datetime.now(timezone.utc)
        self._conn.execute(
            """INSERT INTO price_snapshots (token, ts, price_hive, price_usd, raw_steps)
               VALUES (?, ?, ?, ?, ?)""",
            (
                token,
                ts.isoformat(),
                prices.get("hive"),
                prices.get("usd"),
                json.dumps(raw_steps),
            ),
        )
        self._conn.commit()

    def get_history(self, token, since=None, limit=500):
        if since:
            rows = self._conn.execute(
                """SELECT * FROM price_snapshots
                   WHERE token=? AND ts>=? ORDER BY ts DESC LIMIT ?""",
                (token, since.isoformat(), limit),
            ).fetchall()
        else:
            rows = self._conn.execute(
                """SELECT * FROM price_snapshots
                   WHERE token=? ORDER BY ts DESC LIMIT ?""",
                (token, limit),
            ).fetchall()
        return [dict(r) for r in rows]

    def get_latest(self, token):
        row = self._conn.execute(
            "SELECT * FROM price_snapshots WHERE token=? ORDER BY ts DESC LIMIT 1",
            (token,),
        ).fetchone()
        return dict(row) if row else None

    def prune(self, token, before):
        self._conn.execute(
            "DELETE FROM price_snapshots WHERE token=? AND ts<?",
            (token, before.isoformat()),
        )
        self._conn.commit()

    def close(self):
        self._conn.close()
