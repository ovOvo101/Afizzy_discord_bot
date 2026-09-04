from __future__ import annotations

import logging
import os

import discord

from .analysis import FeedbackAnalyzer
from .config import ConfigError, Settings, load_settings
from .content import ContentError
from .database import Database
from .feedback import FeedbackArchive
from .polls import PollFeature
from .invite_code import InviteCodeLimiter
from .message_length import MinimumMessageLength

logging.basicConfig(level=os.getenv("LOG_LEVEL", "INFO"), format="%(asctime)s %(levelname)s %(name)s: %(message)s")
LOGGER = logging.getLogger(__name__)


class CreativeBot(discord.Client):
    def __init__(self, settings: Settings, database: Database) -> None:
        intents = discord.Intents.default()
        intents.message_content = True
        super().__init__(intents=intents)
        self.settings, self.database = settings, database
        self.minimum_message_length = (
            MinimumMessageLength(settings.discord.minimum_message_channel_ids)
            if settings.features.minimum_message_length
            else None
        )
        self.invite_code = (
            InviteCodeLimiter(database, settings.discord.invite_code_channel_id)
            if settings.features.invite_code_limit
            else None
        )
        self.polls = (
            PollFeature(self, settings, database)
            if settings.features.daily_poll
            else None
        )
        self.feedback = (
            FeedbackArchive(self, settings, database)
            if settings.features.feedback_archive
            else None
        )
        self.feedback_analysis = (
            FeedbackAnalyzer(self, settings, database)
            if settings.features.feedback_analysis
            else None
        )

    async def setup_hook(self) -> None:
        if self.polls:
            self.polls.start()
        if self.feedback:
            await self.feedback.start()
        if self.feedback_analysis:
            await self.feedback_analysis.start()

    async def on_message(self, message: discord.Message) -> None:
        if self.minimum_message_length and await self.minimum_message_length.handle(message):
            return
        if self.invite_code:
            await self.invite_code.handle(message)
        if self.feedback:
            await self.feedback.on_message(message)

    async def close(self) -> None:
        if self.polls:
            self.polls.stop()
        if self.feedback:
            await self.feedback.stop()
        if self.feedback_analysis:
            await self.feedback_analysis.stop()
        self.database.close()
        await super().close()


def build_bot(config_path: str) -> CreativeBot:
    settings = load_settings(config_path)
    database = Database(settings.database_path)
    database.initialize()
    return CreativeBot(settings, database)


def main() -> None:
    token = os.getenv("DISCORD_TOKEN")
    if not token:
        raise RuntimeError("DISCORD_TOKEN is required")
    try:
        bot = build_bot(os.getenv("BOT_CONFIG_PATH", "config/config.railway.yaml"))
    except (ConfigError, ContentError) as exc:
        raise RuntimeError(f"Startup validation failed: {exc}") from exc
    bot.run(token, log_handler=None)


if __name__ == "__main__":
    main()
