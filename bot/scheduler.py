from __future__ import annotations

import logging
from datetime import datetime, timedelta

import discord
from discord.ext import tasks

from .config import Settings
from .database import Database
from .content import PollItem, pick_unseen

LOGGER = logging.getLogger(__name__)


def is_due(
    now: datetime, time_string: str, weekdays: tuple[int, ...] | None = None
) -> bool:
    return now.strftime("%H:%M") == time_string and (
        weekdays is None or now.weekday() in weekdays
    )


class DailyScheduler:
    def __init__(self, bot: discord.Client, settings: Settings, database: Database, polls: list[PollItem]) -> None:
        self.bot, self.settings, self.database, self.polls = bot, settings, database, polls
        self.tick.start()

    def stop(self) -> None:
        self.tick.cancel()

    @tasks.loop(seconds=30)
    async def tick(self) -> None:
        try:
            now = datetime.now(self.settings.schedule.timezone)
            if self.settings.features.daily_poll and is_due(
                now,
                self.settings.schedule.poll_time,
                self.settings.schedule.poll_weekdays,
            ):
                await self.publish_poll(now)
            if self.settings.features.daily_poll:
                await self.summarize_ended_polls(now)
        except Exception:
            LOGGER.exception("Scheduler tick failed")

    @tick.before_loop
    async def before_tick(self) -> None:
        await self.bot.wait_until_ready()

    async def _channel(self, channel_id: int | None) -> discord.abc.Messageable | None:
        if not channel_id:
            return None
        channel = self.bot.get_channel(channel_id) or await self.bot.fetch_channel(channel_id)
        return channel if hasattr(channel, "send") else None

    async def publish_poll(self, now: datetime) -> None:
        channel = await self._channel(self.settings.discord.poll_channel_id)
        if channel is None:
            return
        item = pick_unseen(self.polls, self.database.recent_content_ids("poll"))
        day = now.date().isoformat()
        if not self.database.claim_publication("poll", day, item.id):
            return
        try:
            poll = discord.Poll(question=item.question, duration=timedelta(hours=self.settings.schedule.poll_duration_hours), multiple=False)
            for option in item.options:
                poll.add_answer(text=option)
            message = await channel.send(content=f"🗳️ **{item.title}**\n{item.description or 'A tiny question for today. Pick what feels right.'}", poll=poll)
            self.database.finish_publication("poll", day, message.id, channel.id)  # type: ignore[attr-defined]
            self.database.save_poll(message.id, channel.id, now + timedelta(hours=self.settings.schedule.poll_duration_hours))  # type: ignore[attr-defined]
            LOGGER.info(
                "Published scheduled poll %s as message %s in channel %s",
                item.id,
                message.id,
                channel.id,
            )
        except Exception:
            self.database.abandon_publication("poll", day)
            LOGGER.exception("Unable to publish daily poll")

    async def summarize_ended_polls(self, now: datetime) -> None:
        for row in self.database.ended_polls(now):
            try:
                channel = await self._channel(row["channel_id"])
                if channel is None or not hasattr(channel, "fetch_message"):
                    continue
                message = await channel.fetch_message(row["message_id"])
                poll = message.poll
                answers = getattr(poll, "answers", []) if poll else []
                results = [f"{answer.text}: {getattr(answer, 'vote_count', 0)}" for answer in answers]
                text = "📊 **Daily poll results**\n" + ("\n".join(results) if results else "The poll has ended — thanks for voting!")
                await channel.send(text)
                self.database.mark_poll_summarized(row["message_id"])
            except Exception:
                LOGGER.exception("Unable to summarize poll %s", row["message_id"])
