from __future__ import annotations

import sqlite3
from datetime import UTC, datetime
from pathlib import Path


class Database:
    def __init__(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        self.connection = sqlite3.connect(path)
        self.connection.row_factory = sqlite3.Row

    def initialize(self) -> None:
        self.connection.executescript("""
        CREATE TABLE IF NOT EXISTS publications (
          kind TEXT NOT NULL, local_date TEXT NOT NULL, content_id TEXT NOT NULL,
          message_id INTEGER, channel_id INTEGER, created_at TEXT NOT NULL,
          PRIMARY KEY(kind, local_date)
        );
        CREATE TABLE IF NOT EXISTS polls (
          message_id INTEGER PRIMARY KEY, channel_id INTEGER NOT NULL, ends_at TEXT NOT NULL,
          summary_posted INTEGER NOT NULL DEFAULT 0
        );
        CREATE TABLE IF NOT EXISTS metrics (
          day TEXT NOT NULL, metric TEXT NOT NULL, value INTEGER NOT NULL DEFAULT 0,
          PRIMARY KEY(day, metric)
        );
        """)
        self.connection.commit()

    def close(self) -> None:
        self.connection.close()

    def claim_publication(self, kind: str, local_date: str, content_id: str) -> bool:
        cursor = self.connection.execute("INSERT OR IGNORE INTO publications(kind, local_date, content_id, created_at) VALUES (?, ?, ?, ?)", (kind, local_date, content_id, datetime.now(UTC).isoformat()))
        self.connection.commit()
        return cursor.rowcount == 1

    def abandon_publication(self, kind: str, local_date: str) -> None:
        self.connection.execute("DELETE FROM publications WHERE kind = ? AND local_date = ? AND message_id IS NULL", (kind, local_date))
        self.connection.commit()

    def finish_publication(self, kind: str, local_date: str, message_id: int, channel_id: int) -> None:
        self.connection.execute("UPDATE publications SET message_id = ?, channel_id = ? WHERE kind = ? AND local_date = ?", (message_id, channel_id, kind, local_date))
        self.connection.commit()

    def recent_content_ids(self, kind: str, limit: int = 14) -> set[str]:
        rows = self.connection.execute("SELECT content_id FROM publications WHERE kind = ? AND message_id IS NOT NULL ORDER BY local_date DESC LIMIT ?", (kind, limit)).fetchall()
        return {row["content_id"] for row in rows}

    def save_poll(self, message_id: int, channel_id: int, ends_at: datetime) -> None:
        self.connection.execute("INSERT OR REPLACE INTO polls(message_id, channel_id, ends_at) VALUES (?, ?, ?)", (message_id, channel_id, ends_at.isoformat()))
        self.connection.commit()

    def ended_polls(self, now: datetime) -> list[sqlite3.Row]:
        return self.connection.execute("SELECT * FROM polls WHERE summary_posted = 0 AND ends_at <= ?", (now.isoformat(),)).fetchall()

    def mark_poll_summarized(self, message_id: int) -> None:
        self.connection.execute("UPDATE polls SET summary_posted = 1 WHERE message_id = ?", (message_id,))
        self.connection.commit()

    def increment_metric(self, day: str, metric: str) -> None:
        self.connection.execute("INSERT INTO metrics(day, metric, value) VALUES (?, ?, 1) ON CONFLICT(day, metric) DO UPDATE SET value = value + 1", (day, metric))
        self.connection.commit()
