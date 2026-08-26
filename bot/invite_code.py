from __future__ import annotations

import logging

import discord

from .database import Database

LOGGER = logging.getLogger(__name__)


class InviteCodeLimiter:
    """Enforce a persistent one-message limit in the configured channel."""

    def __init__(self, database: Database, channel_id: int | None) -> None:
        self.database = database
        self.channel_id = channel_id

    async def handle(self, message: discord.Message) -> None:
        if (
            message.author.bot
            or message.guild is None
            or message.channel.id != self.channel_id
        ):
            return

        is_first_message = self.database.claim_invite_code_message(
            message.guild.id, message.channel.id, message.author.id, message.id
        )
        if is_first_message:
            return

        try:
            await message.delete()
        except discord.HTTPException:
            LOGGER.warning(
                "Could not delete extra invite-code message %s in channel %s",
                message.id,
                message.channel.id,
                exc_info=True,
            )
            return

        try:
            await message.author.send(
                "Hi! To keep **#invite-code** organized for everyone, the channel is set "
                "to one message per member. We've removed your latest message so your "
                "original post stays active. Thanks so much for understanding! ✨"
            )
        except discord.HTTPException:
            LOGGER.info(
                "Could not notify user %s about invite-code message limit",
                message.author.id,
            )
