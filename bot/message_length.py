from __future__ import annotations

import logging

import discord

LOGGER = logging.getLogger(__name__)


class MinimumMessageLength:
    """Remove text messages that are too short in configured channels."""

    def __init__(self, channel_ids: tuple[int, ...], minimum: int = 6) -> None:
        self.channel_ids = frozenset(channel_ids)
        self.minimum = minimum

    async def handle(self, message: discord.Message) -> bool:
        if (
            message.author.bot
            or message.guild is None
            or message.channel.id not in self.channel_ids
        ):
            return False

        # Whitespace does not count, so messages such as "hi    " cannot bypass the rule.
        character_count = sum(not character.isspace() for character in message.content)
        if character_count >= self.minimum:
            return False

        try:
            await message.delete()
        except discord.HTTPException:
            LOGGER.warning(
                "Could not delete short message %s in channel %s",
                message.id,
                message.channel.id,
                exc_info=True,
            )
            return False

        try:
            await message.author.send(
                f"Hi! Your message in **#{message.channel.name}** was automatically removed "
                "because it didn’t meet this channel’s posting guidelines.\n\n"
                "If you’d like to say hello, please head over to **#self-introduce**. "
                "If you’d like to share an invite code, please use **#invite-code** or "
                "send it directly to your friend.\n\n"
                "Thanks for your understanding and helping us keep the channel organized! ✨"
            )
        except discord.HTTPException:
            LOGGER.info(
                "Could not notify user %s about minimum message length",
                message.author.id,
            )
        return True
