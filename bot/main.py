from __future__ import annotations

import logging
import os

import discord
from discord import app_commands

from .config import ConfigError, Settings, load_settings
from .content import ContentError
from .database import Database
from .inspiration import InspirationFeature
from .invite_code import InviteCodeLimiter

logging.basicConfig(level=os.getenv("LOG_LEVEL", "INFO"), format="%(asctime)s %(levelname)s %(name)s: %(message)s")
LOGGER = logging.getLogger(__name__)


class CreativeBot(discord.Client):
    def __init__(self, settings: Settings, database: Database) -> None:
        intents = discord.Intents.default()
        intents.message_content = True
        super().__init__(intents=intents)
        self.settings, self.database = settings, database
        self.tree = app_commands.CommandTree(self)
        self.invite_code = (
            InviteCodeLimiter(database, settings.discord.invite_code_channel_id)
            if settings.features.invite_code_limit
            else None
        )
        self.inspiration = (
            InspirationFeature(self, self.tree, settings, database)
            if any(
                (
                    settings.features.daily_poll,
                    settings.features.daily_prompt,
                    settings.features.idea,
                )
            )
            else None
        )

    async def setup_hook(self) -> None:
        if self.settings.discord.guild_id:
            guild = discord.Object(id=self.settings.discord.guild_id)
            self.tree.copy_global_to(guild=guild)
            await self.tree.sync(guild=guild)
        else:
            await self.tree.sync()
        if self.inspiration:
            self.inspiration.start()

    async def on_message(self, message: discord.Message) -> None:
        if self.invite_code:
            await self.invite_code.handle(message)
        if self.inspiration:
            await self.inspiration.on_message(message)

    async def close(self) -> None:
        if self.inspiration:
            self.inspiration.stop()
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
