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
