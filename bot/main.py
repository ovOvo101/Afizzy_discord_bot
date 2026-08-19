from __future__ import annotations

import logging
import os
from datetime import datetime

import discord
from discord import app_commands

from .config import ConfigError, Settings, load_settings
from .content import VALID_CATEGORIES, ContentError, load_ideas, load_polls, load_prompts
from .database import Database
from .scheduler import DailyScheduler
from .services import ContentService

logging.basicConfig(level=os.getenv("LOG_LEVEL", "INFO"), format="%(asctime)s %(levelname)s %(name)s: %(message)s")
LOGGER = logging.getLogger(__name__)


class CreativeBot(discord.Client):
    def __init__(self, settings: Settings, database: Database, content: ContentService) -> None:
        intents = discord.Intents.default()
        intents.message_content = True
        super().__init__(intents=intents)
        self.settings, self.database, self.content = settings, database, content
        self.tree = app_commands.CommandTree(self)
        self.scheduler: DailyScheduler | None = None
        self._register_commands()

    def _register_commands(self) -> None:
        @self.tree.command(name="idea", description="Get a small creative problem to solve.")
        @app_commands.describe(category="Optional idea category")
        @app_commands.choices(category=[app_commands.Choice(name="random", value="random")] + [app_commands.Choice(name=name, value=name) for name in sorted(VALID_CATEGORIES)])
        async def idea(interaction: discord.Interaction, category: app_commands.Choice[str] | None = None) -> None:
            requested = None if category is None or category.value == "random" else category.value
            await interaction.response.send_message(f"🎲 **Your random idea**\n\n{self.content.idea(requested)}")
            self.content.record_metric(datetime.now(self.settings.schedule.timezone), "idea_uses")

    async def setup_hook(self) -> None:
        if self.settings.discord.guild_id:
            guild = discord.Object(id=self.settings.discord.guild_id)
            self.tree.copy_global_to(guild=guild)
            await self.tree.sync(guild=guild)
        else:
            await self.tree.sync()
        self.scheduler = DailyScheduler(self, self.settings, self.database, self.content)

    async def on_message(self, message: discord.Message) -> None:
        if message.author.bot or not message.reference or not message.reference.message_id:
            return
        prompt_ids = {row["message_id"] for row in self.database.connection.execute("SELECT message_id FROM publications WHERE kind = 'prompt' AND message_id IS NOT NULL")}
        if message.reference.message_id in prompt_ids:
            self.content.record_metric(datetime.now(self.settings.schedule.timezone), "prompt_replies")

    async def close(self) -> None:
        if self.scheduler:
            self.scheduler.stop()
        self.database.close()
        await super().close()


def build_bot(config_path: str) -> CreativeBot:
    settings = load_settings(config_path)
    polls, prompts, ideas = load_polls(settings.polls_path), load_prompts(settings.prompts_path), load_ideas(settings.ideas_path)
    database = Database(settings.database_path)
    database.initialize()
    return CreativeBot(settings, database, ContentService(database, polls, prompts, ideas))


def main() -> None:
    token = os.getenv("DISCORD_TOKEN")
    if not token:
        raise RuntimeError("DISCORD_TOKEN is required; copy .env.example to .env and set it")
    try:
        bot = build_bot(os.getenv("BOT_CONFIG_PATH", "config/config.yaml"))
    except (ConfigError, ContentError) as exc:
        raise RuntimeError(f"Startup validation failed: {exc}") from exc
    bot.run(token, log_handler=None)


if __name__ == "__main__":
    main()
