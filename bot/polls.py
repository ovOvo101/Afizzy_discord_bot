from __future__ import annotations

import discord

from .config import Settings
from .content import load_polls
from .database import Database
from .scheduler import DailyScheduler


class PollFeature:
    """Own scheduled poll publication and result summaries."""

    def __init__(self, bot: discord.Client, settings: Settings, database: Database) -> None:
        self.bot = bot
        self.settings = settings
        self.database = database
        self.poll_items = load_polls(settings.polls_path)
        self.scheduler: DailyScheduler | None = None

    def start(self) -> None:
        self.scheduler = DailyScheduler(
            self.bot, self.settings, self.database, self.poll_items
        )

    def stop(self) -> None:
        if self.scheduler:
            self.scheduler.stop()
