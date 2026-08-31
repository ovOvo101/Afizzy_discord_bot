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
        CREATE TABLE IF NOT EXISTS invite_code_messages (
          guild_id INTEGER NOT NULL, channel_id INTEGER NOT NULL, user_id INTEGER NOT NULL,
          message_id INTEGER NOT NULL, created_at TEXT NOT NULL,
          PRIMARY KEY(guild_id, channel_id, user_id)
        );
        CREATE TABLE IF NOT EXISTS feedback_tasks (
          message_id INTEGER PRIMARY KEY,
          guild_id INTEGER NOT NULL,
          channel_id INTEGER NOT NULL,
          username TEXT NOT NULL,
          message_time TEXT NOT NULL,
          original_message TEXT NOT NULL,
          message_link TEXT NOT NULL,
          detected_language TEXT,
          chinese_translation TEXT,
          feishu_record_id TEXT,
          acknowledged INTEGER NOT NULL DEFAULT 0,
          attempts INTEGER NOT NULL DEFAULT 0,
          next_attempt_at TEXT NOT NULL,
          last_error TEXT,
          created_at TEXT NOT NULL
        );
        CREATE INDEX IF NOT EXISTS feedback_tasks_due
          ON feedback_tasks(next_attempt_at)
          WHERE acknowledged = 0;
        """)
        self.connection.commit()

    def close(self) -> None:
        self.connection.close()

    def claim_publication(self, kind: str, local_date: str, content_id: str) -> bool:
        cursor = self.connection.execute("INSERT OR IGNORE INTO publications(kind, local_date, content_id, created_at) VALUES (?, ?, ?, ?)", (kind, local_date, content_id, datetime.now(UTC).isoformat()))
        self.connection.commit()
        return cursor.rowcount == 1

    def claim_feedback(
        self,
        message_id: int,
        guild_id: int,
        channel_id: int,
        username: str,
        message_time: datetime,
        original_message: str,
        message_link: str,
    ) -> bool:
        now = datetime.now(UTC).isoformat()
        cursor = self.connection.execute(
            """
            INSERT OR IGNORE INTO feedback_tasks(
              message_id, guild_id, channel_id, username, message_time,
              original_message, message_link, next_attempt_at, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                message_id,
                guild_id,
                channel_id,
                username,
                message_time.astimezone(UTC).isoformat(),
                original_message,
                message_link,
                now,
                now,
            ),
        )
        self.connection.commit()
        return cursor.rowcount == 1

    def due_feedback(self, now: datetime, limit: int = 20) -> list[sqlite3.Row]:
        return self.connection.execute(
            """
            SELECT * FROM feedback_tasks
            WHERE acknowledged = 0 AND next_attempt_at <= ?
            ORDER BY next_attempt_at, created_at LIMIT ?
            """,
            (now.astimezone(UTC).isoformat(), limit),
        ).fetchall()

    def save_feedback_translation(
        self, message_id: int, detected_language: str, translation: str
    ) -> None:
        self.connection.execute(
            """
            UPDATE feedback_tasks
            SET detected_language = ?, chinese_translation = ?, last_error = NULL
            WHERE message_id = ?
            """,
            (detected_language, translation, message_id),
        )
        self.connection.commit()

    def mark_feedback_delivered(self, message_id: int, record_id: str) -> None:
        self.connection.execute(
            """
            UPDATE feedback_tasks
            SET feishu_record_id = ?, last_error = NULL, next_attempt_at = ?
            WHERE message_id = ?
            """,
            (record_id, datetime.now(UTC).isoformat(), message_id),
        )
        self.connection.commit()

    def mark_feedback_acknowledged(self, message_id: int) -> None:
        self.connection.execute(
            "UPDATE feedback_tasks SET acknowledged = 1, last_error = NULL WHERE message_id = ?",
            (message_id,),
        )
        self.connection.commit()

    def defer_feedback(self, message_id: int, error: str, now: datetime) -> None:
        row = self.connection.execute(
            "SELECT attempts FROM feedback_tasks WHERE message_id = ?", (message_id,)
        ).fetchone()
        attempts = int(row["attempts"]) + 1
        delays = (60, 120, 240, 480, 960)
        delay = delays[attempts - 1] if attempts <= len(delays) else 3600
        next_attempt = now.astimezone(UTC).timestamp() + delay
        self.connection.execute(
            """
            UPDATE feedback_tasks
            SET attempts = ?, next_attempt_at = ?, last_error = ? WHERE message_id = ?
            """,
            (
                attempts,
                datetime.fromtimestamp(next_attempt, UTC).isoformat(),
                error[:1000],
                message_id,
            ),
        )
        self.connection.commit()

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

    def claim_invite_code_message(
        self, guild_id: int, channel_id: int, user_id: int, message_id: int
    ) -> bool:
        cursor = self.connection.execute(
            """
            INSERT OR IGNORE INTO invite_code_messages(
              guild_id, channel_id, user_id, message_id, created_at
            ) VALUES (?, ?, ?, ?, ?)
            """,
            (guild_id, channel_id, user_id, message_id, datetime.now(UTC).isoformat()),
        )
        self.connection.commit()
        return cursor.rowcount == 1
