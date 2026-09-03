from types import SimpleNamespace
from unittest.mock import AsyncMock

from bot.message_length import MinimumMessageLength


def message(
    content: str,
    channel_id: int = 10,
    attachments: list[SimpleNamespace] | None = None,
    embeds: list[SimpleNamespace] | None = None,
    stickers: list[SimpleNamespace] | None = None,
    poll: SimpleNamespace | None = None,
    message_snapshots: list[SimpleNamespace] | None = None,
) -> SimpleNamespace:
    author = SimpleNamespace(id=100, bot=False, send=AsyncMock())
    channel = SimpleNamespace(id=channel_id, name="introductions")
    return SimpleNamespace(
        id=1000,
        content=content,
        attachments=attachments or [],
        embeds=embeds or [],
        stickers=stickers or [],
        poll=poll,
        message_snapshots=message_snapshots or [],
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


async def test_any_attachment_bypasses_length_limit() -> None:
    limiter = MinimumMessageLength((10,))
    document = SimpleNamespace(content_type="application/pdf", filename="notes.pdf")
    with_attachment = message("", attachments=[document])

    assert not await limiter.handle(with_attachment)  # type: ignore[arg-type]

    with_attachment.delete.assert_not_awaited()


async def test_embed_bypasses_length_limit() -> None:
    limiter = MinimumMessageLength((10,))
    with_embed = message("hi", embeds=[SimpleNamespace()])

    assert not await limiter.handle(with_embed)  # type: ignore[arg-type]

    with_embed.delete.assert_not_awaited()


async def test_sticker_and_poll_bypass_length_limit() -> None:
    limiter = MinimumMessageLength((10,))
    with_sticker = message("", stickers=[SimpleNamespace()])
    with_poll = message("", poll=SimpleNamespace())

    assert not await limiter.handle(with_sticker)  # type: ignore[arg-type]
    assert not await limiter.handle(with_poll)  # type: ignore[arg-type]

    with_sticker.delete.assert_not_awaited()
    with_poll.delete.assert_not_awaited()


async def test_forwarded_message_snapshot_bypasses_length_limit() -> None:
    forwarded = message("", message_snapshots=[SimpleNamespace(content="forwarded text")])

    assert not await MinimumMessageLength((10,)).handle(forwarded)  # type: ignore[arg-type]

    forwarded.delete.assert_not_awaited()
    forwarded.author.send.assert_not_awaited()
