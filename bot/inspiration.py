from __future__ import annotations

from datetime import datetime

import discord
from discord import app_commands

from .config import Settings
from .content import VALID_CATEGORIES, load_ideas, load_polls, load_prompts
from .database import Database
from .scheduler import DailyScheduler
from .services import ContentService


class InspirationFeature:
    """Own all polls, prompts and /idea behavior behind one feature boundary."""

    def __init__(
        self,
        bot: discord.Client,
        tree: app_commands.CommandTree,
        settings: Settings,
        database: Database,
    ) -> None:
        self.bot = bot
        self.tree = tree
        self.settings = settings
        self.database = database
        self.content = ContentService(
            database,
            load_polls(settings.polls_path),
            load_prompts(settings.prompts_path),
            load_ideas(settings.ideas_path),
        )
        self.scheduler: DailyScheduler | None = None
        if settings.features.idea:
            self._register_commands()

    def _register_commands(self) -> None:
        @self.tree.command(name="idea", description="Get a small creative problem to solve.")
        @app_commands.describe(category="Optional idea category")
        @app_commands.choices(
            category=[app_commands.Choice(name="random", value="random")]
            + [
                app_commands.Choice(name=name, value=name)
                for name in sorted(VALID_CATEGORIES)
            ]
        )
        async def idea(
            interaction: discord.Interaction,
            category: app_commands.Choice[str] | None = None,
        ) -> None:
            requested = None if category is None or category.value == "random" else category.value
            await interaction.response.send_message(
                f"🎲 **Your random idea**\n\n{self.content.idea(requested)}"
            )
            self.content.record_metric(
                datetime.now(self.settings.schedule.timezone), "idea_uses"
            )

    def start(self) -> None:
        self.scheduler = DailyScheduler(
            self.bot, self.settings, self.database, self.content
        )

    def stop(self) -> None:
        if self.scheduler:
            self.scheduler.stop()

    async def on_message(self, message: discord.Message) -> None:
        if not self.settings.features.daily_prompt:
            return
        if message.author.bot or not message.reference or not message.reference.message_id:
            return
        prompt_ids = {
            row["message_id"]
            for row in self.database.connection.execute(
                "SELECT message_id FROM publications "
                "WHERE kind = 'prompt' AND message_id IS NOT NULL"
            )
        }
        if message.reference.message_id in prompt_ids:
            self.content.record_metric(
                datetime.now(self.settings.schedule.timezone), "prompt_replies"
            )
