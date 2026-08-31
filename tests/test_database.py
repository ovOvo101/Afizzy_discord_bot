from datetime import UTC, datetime, timedelta
from pathlib import Path

from bot.database import Database
from bot.scheduler import is_due


def test_publications_are_idempotent(tmp_path: Path) -> None:
    database = Database(tmp_path / "bot.sqlite3")
    database.initialize()
    assert database.claim_publication("poll", "2026-08-19", "one")
    assert not database.claim_publication("poll", "2026-08-19", "two")
    database.finish_publication("poll", "2026-08-19", 100, 200)
    assert database.recent_content_ids("poll") == {"one"}
    database.close()


def test_poll_and_metric_tracking(tmp_path: Path) -> None:
    database = Database(tmp_path / "bot.sqlite3")
    database.initialize()
    now = datetime.now(UTC)
    database.save_poll(100, 200, now - timedelta(seconds=1))
    assert database.ended_polls(now)[0]["message_id"] == 100
    database.mark_poll_summarized(100)
    assert database.ended_polls(now) == []
    database.increment_metric("2026-08-19", "idea_uses")
    database.increment_metric("2026-08-19", "idea_uses")
    value = database.connection.execute("SELECT value FROM metrics").fetchone()["value"]
    assert value == 2
    database.close()


def test_due_time() -> None:
    assert is_due(datetime(2026, 8, 19, 18, 0, tzinfo=UTC), "18:00")
    assert not is_due(datetime(2026, 8, 19, 18, 1, tzinfo=UTC), "18:00")
    assert is_due(datetime(2026, 8, 19, 18, 0, tzinfo=UTC), "18:00", (2, 4, 6))
    assert not is_due(datetime(2026, 8, 20, 18, 0, tzinfo=UTC), "18:00", (2, 4, 6))


def test_feedback_claim_is_idempotent_and_retries(tmp_path: Path) -> None:
    database = Database(tmp_path / "bot.sqlite3")
    database.initialize()
    now = datetime.now(UTC)
    args = (1000, 1, 10, "alice", now, "hello", "https://discord.com/channels/1/10/1000")
    assert database.claim_feedback(*args)
    assert not database.claim_feedback(*args)
    assert database.due_feedback(now + timedelta(seconds=1))[0]["message_id"] == 1000

    database.defer_feedback(1000, "temporary", now)
    row = database.connection.execute(
        "SELECT * FROM feedback_tasks WHERE message_id = 1000"
    ).fetchone()
    assert row["attempts"] == 1
    assert datetime.fromisoformat(row["next_attempt_at"]) == now + timedelta(seconds=60)

    database.save_feedback_translation(1000, "EN", "你好")
    database.mark_feedback_delivered(1000, "rec123")
    database.mark_feedback_acknowledged(1000)
    row = database.connection.execute(
        "SELECT * FROM feedback_tasks WHERE message_id = 1000"
    ).fetchone()
    assert row["chinese_translation"] == "你好"
    assert row["feishu_record_id"] == "rec123"
    assert row["acknowledged"] == 1
    database.close()


def test_invite_code_channel_allows_one_message_per_user(tmp_path: Path) -> None:
    database = Database(tmp_path / "bot.sqlite3")
    database.initialize()
    assert database.claim_invite_code_message(1, 10, 100, 1000)
    assert not database.claim_invite_code_message(1, 10, 100, 1001)
    assert database.claim_invite_code_message(1, 10, 101, 1002)
    assert database.claim_invite_code_message(1, 11, 100, 1003)
    database.close()
