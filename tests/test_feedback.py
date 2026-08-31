from datetime import UTC, datetime
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock

import discord

from bot.config import load_settings
from bot.database import Database
from bot.feedback import FeedbackArchive


FIELDS = {
    "username": "用户名",
    "message_time": "消息时间",
    "original_message": "原始消息",
    "message_link": "消息链接",
    "detected_language": "识别语言",
    "chinese_translation": "中文翻译",
    "message_id": "Discord消息ID",
    "channel_id": "频道ID",
}


def settings(tmp_path: Path, monkeypatch: object) -> object:
    for name in ("DEEPL_API_KEY", "FEISHU_APP_ID", "FEISHU_APP_SECRET"):
        monkeypatch.setenv(name, "test")  # type: ignore[attr-defined]
    path = tmp_path / "config" / "config.yaml"
    path.parent.mkdir()
    path.write_text(
        f"""
discord: {{guild_id: 1}}
features: {{invite_code_limit: false, feedback_archive: true}}
scheduling: {{}}
storage: {{database_path: data/test.sqlite3}}
content: {{polls_path: data/polls.yaml, prompts_path: data/prompts.yaml, ideas_path: data/ideas.yaml}}
feedback:
  channels:
    - channel_id: 10
      app_token: bas1
      table_id: tbl1
      fields: {FIELDS!r}
""",
        encoding="utf-8",
    )
    return load_settings(path)


def discord_message(message_id: int = 1000, content: str = "hello") -> SimpleNamespace:
    return SimpleNamespace(
        id=message_id,
        content=content,
        guild=SimpleNamespace(id=1),
        channel=SimpleNamespace(id=10),
        author=SimpleNamespace(name="alice", bot=False, roles=[]),
        webhook_id=None,
        type=discord.MessageType.default,
        attachments=[SimpleNamespace(url="https://cdn.example/file.png")],
        created_at=datetime(2026, 8, 31, 1, 2, tzinfo=UTC),
        jump_url="https://discord.com/channels/1/10/1000",
    )


async def test_message_is_queued_once_with_attachment(tmp_path: Path, monkeypatch: object) -> None:
    configured = settings(tmp_path, monkeypatch)
    database = Database(tmp_path / "feedback.sqlite3")
    database.initialize()
    archive = FeedbackArchive(SimpleNamespace(), configured, database)  # type: ignore[arg-type]
    message = discord_message()

    await archive.on_message(message)  # type: ignore[arg-type]
    await archive.on_message(message)  # type: ignore[arg-type]

    rows = database.connection.execute("SELECT * FROM feedback_tasks").fetchall()
    assert len(rows) == 1
    assert rows[0]["username"] == "alice"
    assert rows[0]["original_message"] == (
        "hello\n\nAttachments:\nhttps://cdn.example/file.png"
    )
    database.close()


async def test_process_archives_without_discord_reply(tmp_path: Path, monkeypatch: object) -> None:
    configured = settings(tmp_path, monkeypatch)
    database = Database(tmp_path / "feedback.sqlite3")
    database.initialize()
    message = discord_message()
    database.claim_feedback(
        message.id,
        message.guild.id,
        message.channel.id,
        message.author.name,
        message.created_at,
        message.content,
        message.jump_url,
    )
    bot = SimpleNamespace(get_channel=AsyncMock())
    archive = FeedbackArchive(bot, configured, database)  # type: ignore[arg-type]
    archive.api.translate = AsyncMock(return_value=("EN", "你好"))  # type: ignore[method-assign]
    archive.api.create_feishu_record = AsyncMock(return_value="rec123")  # type: ignore[method-assign]
    row = database.connection.execute("SELECT * FROM feedback_tasks").fetchone()

    await archive._process(row)

    stored = database.connection.execute("SELECT * FROM feedback_tasks").fetchone()
    assert stored["feishu_record_id"] == "rec123"
    assert stored["acknowledged"] == 1
    archive.api.create_feishu_record.assert_awaited_once()  # type: ignore[union-attr]
    bot.get_channel.assert_not_called()
    database.close()


async def test_staff_messages_are_ignored(tmp_path: Path, monkeypatch: object) -> None:
    configured = settings(tmp_path, monkeypatch)
    database = Database(tmp_path / "feedback.sqlite3")
    database.initialize()
    archive = FeedbackArchive(SimpleNamespace(), configured, database)  # type: ignore[arg-type]
    message = discord_message()
    message.author.roles = [SimpleNamespace(name="Staff")]

    await archive.on_message(message)  # type: ignore[arg-type]

    count = database.connection.execute("SELECT COUNT(*) FROM feedback_tasks").fetchone()[0]
    assert count == 0
    database.close()
