from __future__ import annotations

from datetime import datetime

from .content import IdeaParts, PollItem, PromptItem, make_idea, pick_unseen
from .database import Database


class ContentService:
    def __init__(self, database: Database, polls: list[PollItem], prompts: list[PromptItem], ideas: IdeaParts) -> None:
        self.database, self.polls, self.prompts, self.ideas = database, polls, prompts, ideas

    def next_poll(self) -> PollItem:
        return pick_unseen(self.polls, self.database.recent_content_ids("poll"))

    def next_prompt(self) -> PromptItem:
        return pick_unseen(self.prompts, self.database.recent_content_ids("prompt"))

    def idea(self, category: str | None) -> str:
        return make_idea(self.ideas, category)

    def record_metric(self, now: datetime, metric: str) -> None:
        self.database.increment_metric(now.date().isoformat(), metric)

