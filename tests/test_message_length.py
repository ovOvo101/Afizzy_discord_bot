from types import SimpleNamespace
from unittest.mock import AsyncMock

from bot.message_length import MinimumMessageLength


def message(content: str, channel_id: int = 10) -> SimpleNamespace:
    author = SimpleNamespace(id=100, bot=False, send=AsyncMock())
    channel = SimpleNamespace(id=channel_id, name="introductions")
    return SimpleNamespace(
        id=1000,
        content=content,
        author=author,
        channel=channel,
        guild=SimpleNamespace(id=1),
        delete=AsyncMock(),
    )


async def test_removes_message_shorter_than_six_characters() -> None:
    limiter = MinimumMessageLength((10,))
    short = message("hi   ")

    assert await limiter.handle(short)  # type: ignore[arg-type]

    short.delete.assert_awaited_once()
    short.author.send.assert_awaited_once()


async def test_keeps_six_character_message() -> None:
    limiter = MinimumMessageLength((10,))
    valid = message("你好世界!!")

    assert not await limiter.handle(valid)  # type: ignore[arg-type]

    valid.delete.assert_not_awaited()
    valid.author.send.assert_not_awaited()


async def test_ignores_unconfigured_channel() -> None:
    limiter = MinimumMessageLength((10,))
    other = message("hi", channel_id=11)

    assert not await limiter.handle(other)  # type: ignore[arg-type]

    other.delete.assert_not_awaited()
