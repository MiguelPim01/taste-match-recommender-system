"""Small SQLite state store for sequential training and recoverable announcements."""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path


class State:
    def __init__(self, path: Path):
        path.parent.mkdir(parents=True, exist_ok=True)
        self.connection = sqlite3.connect(path, timeout=30)
        self.connection.execute("PRAGMA journal_mode=WAL")
        self.connection.execute("PRAGMA busy_timeout=30000")
        self.connection.execute("CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY, value TEXT NOT NULL)")
        self.connection.execute("""CREATE TABLE IF NOT EXISTS ready_events
                              (event_id TEXT PRIMARY KEY, payload TEXT NOT NULL, sent INTEGER NOT NULL DEFAULT 0)""")
        self.connection.commit()

    def close(self):
        self.connection.close()

    def get(self, key: str, default=None):
        row = self.connection.execute("SELECT value FROM settings WHERE key=?", (key,)).fetchone()
        return json.loads(row[0]) if row else default

    def set(self, key: str, value):
        self.connection.execute("INSERT INTO settings(key,value) VALUES(?,?) "
                                "ON CONFLICT(key) DO UPDATE SET value=excluded.value",
                                (key, json.dumps(value)))
        self.connection.commit()

    def complete(self, watermarks: dict, *, champion: dict | None = None, ready_event: dict | None = None):
        with self.connection:
            self._put("last_counts", watermarks)
            self._put("pending_request", None)
            if champion is not None:
                self._put("champion", champion)
            if ready_event is not None:
                self.connection.execute("INSERT OR IGNORE INTO ready_events(event_id,payload) VALUES(?,?)",
                                        (ready_event["event_id"], json.dumps(ready_event)))

    def _put(self, key: str, value):
        self.connection.execute("INSERT INTO settings(key,value) VALUES(?,?) "
                                "ON CONFLICT(key) DO UPDATE SET value=excluded.value",
                                (key, json.dumps(value)))

    def pending_ready(self):
        return self.connection.execute("SELECT event_id,payload FROM ready_events WHERE sent=0 ORDER BY rowid").fetchall()

    def mark_ready_sent(self, event_id: str):
        self.connection.execute("UPDATE ready_events SET sent=1 WHERE event_id=?", (event_id,))
        self.connection.commit()
