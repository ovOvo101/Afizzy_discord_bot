from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock

from bot.database import Database
from bot.invite_code import InviteCodeLimiter


def message(message_id: int) -> SimpleNamespace:
    author = SimpleNamespace(id=100, bot=False, send=AsyncMock())
    channel = SimpleNamespace(id=10, name="invite-code")
    return SimpleNamespace(
        id=message_id,
        author=author,
        channel=channel,
        guild=SimpleNamespace(id=1),
        delete=AsyncMock(),
    )


async def test_invite_code_limiter_keeps_first_and_removes_second(tmp_path: Path) -> None:
    database = Database(tmp_path / "bot.sqlite3")
    database.initialize()
    limiter = InviteCodeLimiter(database)
    first = message(1000)
    second = message(1001)

    await limiter.handle(first)  # type: ignore[arg-type]
    await limiter.handle(second)  # type: ignore[arg-type]

    first.delete.assert_not_awaited()
    second.delete.assert_awaited_once()
    second.author.send.assert_awaited_once_with(
        "Hi! To keep **#invite-code** organized for everyone, the channel is set "
        "to one message per member. We've removed your latest message so your "
        "original post stays active. Thanks so much for understanding! ✨"
    )
    database.close()


async def test_invite_code_limiter_ignores_other_channels(tmp_path: Path) -> None:
    database = Database(tmp_path / "bot.sqlite3")
    database.initialize()
    limiter = InviteCodeLimiter(database)
    other = message(1000)
    other.channel.name = "general"

    await limiter.handle(other)  # type: ignore[arg-type]

    other.delete.assert_not_awaited()
    database.close()
