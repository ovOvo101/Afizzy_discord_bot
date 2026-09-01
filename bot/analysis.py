from __future__ import annotations

import asyncio
from datetime import UTC, datetime
import json
import logging
import os
from typing import Any

import aiohttp
import discord
from discord.ext import tasks

from .config import Settings
from .database import Database
from .feedback import ApiError, FeedbackApiClient

LOGGER = logging.getLogger(__name__)
PRIORITIES = ("🔴 P0", "🔴 P1", "🟡 P2", "⚪ Idea", "🟢 Community")

ANALYSIS_INSTRUCTIONS = """你是 Afizzy 的产品反馈分析员。把 Discord 用户消息整理成产品团队可审核的需求：
1. 提炼真实问题，不照抄原文；过滤闲聊、致谢和 Staff 回复。
2. 合并本批次中本质相同的反馈，并列出全部日期和用户。
3. 与提供的全部历史分析比较；如果相似，仍生成待审核的新条目，并填写 possible_duplicate 和 duplicate_reason，不要修改历史条目。
4. Category 使用简洁的产品领域名称。Suggested Solution 必须具体可执行。
5. Priority 只能是 🔴 P0、🔴 P1、🟡 P2、⚪ Idea、🟢 Community。
6. source_message_ids 必须只使用输入中出现的 Discord 消息 ID。没有有效产品反馈时返回空 items。
只返回符合 JSON Schema 的结果。"""


def _response_schema() -> dict[str, Any]:
    item = {
        "type": "object",
        "properties": {
            "dates": {"type": "string"},
            "category": {"type": "string"},
            "user_feedback": {"type": "string"},
            "suggested_solution": {"type": "string"},
            "users": {"type": "string"},
            "priority": {"type": "string", "enum": list(PRIORITIES)},
            "possible_duplicate": {"type": "string"},
            "duplicate_reason": {"type": "string"},
            "source_message_ids": {
                "type": "array",
                "items": {"type": "string"},
                "minItems": 1,
            },
        },
        "required": [
            "dates",
            "category",
            "user_feedback",
            "suggested_solution",
            "users",
            "priority",
            "possible_duplicate",
            "duplicate_reason",
            "source_message_ids",
        ],
        "additionalProperties": False,
    }
    return {
        "type": "object",
        "properties": {"items": {"type": "array", "items": item}},
        "required": ["items"],
        "additionalProperties": False,
    }


class FeedbackAnalyzer:
    def __init__(self, bot: discord.Client, settings: Settings, database: Database) -> None:
        self.bot = bot
        self.settings = settings
        self.database = database
        self.api = FeedbackApiClient(settings)
        self._analysis_session: aiohttp.ClientSession | None = None

    def _model(self) -> str:
        return os.environ["SILICONFLOW_MODEL"]

    def _api_key(self) -> str:
        return os.environ["SILICONFLOW_API_KEY"]

    async def start(self) -> None:
        await self.api.start()
        timeout = aiohttp.ClientTimeout(
            total=self.settings.feedback_analysis.request_timeout_seconds
        )
        self._analysis_session = aiohttp.ClientSession(timeout=timeout)
        self.run_daily.start()
        self.process_pending.start()

    async def stop(self) -> None:
        self.run_daily.cancel()
        self.process_pending.cancel()
        if self._analysis_session is not None:
            await self._analysis_session.close()
            self._analysis_session = None
        await self.api.close()

    @tasks.loop(seconds=30)
    async def run_daily(self) -> None:
        local_now = datetime.now(UTC).astimezone(self.settings.schedule.timezone)
        scheduled = self.settings.feedback_analysis.schedule_time
        if local_now.strftime("%H:%M") < scheduled:
            return
        run = self.database.claim_analysis_run(local_now.date().isoformat())
        if run is not None:
            LOGGER.info("Created feedback analysis run %s", run["id"])

    @run_daily.before_loop
    async def before_run_daily(self) -> None:
        await self.bot.wait_until_ready()

    @tasks.loop(seconds=10)
    async def process_pending(self) -> None:
        for run in self.database.due_analysis_runs(datetime.now(UTC)):
            try:
                await self._process_run(run)
            except Exception as exc:
                self.database.defer_analysis_run(run["id"], str(exc), datetime.now(UTC))
                LOGGER.warning("Feedback analysis run %s deferred: %s", run["id"], exc)

    @process_pending.before_loop
    async def before_process_pending(self) -> None:
        await self.bot.wait_until_ready()

    async def _process_run(self, run: Any) -> None:
        rows = self.database.analysis_messages(run["id"])
        if not rows:
            self.database.complete_analysis_run(run["id"])
            return
        if not run["openai_response"]:
            result, raw = await self._analyze(rows)
            allowed_ids = {str(row["message_id"]) for row in rows}
            serialized: list[str] = []
            for item in result["items"]:
                source_ids = item["source_message_ids"]
                if not source_ids or any(value not in allowed_ids for value in source_ids):
                    raise ApiError("SiliconFlow returned an unknown source_message_id")
                serialized.append(json.dumps(item, ensure_ascii=False))
            self.database.save_analysis_response(run["id"], raw, serialized)
        messages = {str(row["message_id"]): row for row in rows}
        for item_row in self.database.pending_analysis_items(run["id"]):
            item = json.loads(item_row["payload"])
            fields = self._feishu_fields(run, item_row, item, messages)
            config = self.settings.feedback_analysis
            record_id = await self.api.create_bitable_record(
                config.app_token, config.table_id, fields
            )
            self.database.mark_analysis_item_delivered(item_row["id"], record_id)
        self.database.complete_analysis_run(run["id"])
        LOGGER.info("Completed feedback analysis run %s", run["id"])

    async def _analyze(self, rows: list[Any]) -> tuple[dict[str, Any], str]:
        if self._analysis_session is None:
            raise RuntimeError("SiliconFlow client has not been started")
        history = [json.loads(row["payload"]) for row in self.database.analysis_history()]
        messages = [
            {
                "message_id": str(row["message_id"]),
                "channel_id": str(row["channel_id"]),
                "date_utc": row["message_time"],
                "username": row["username"],
                "original": row["original_message"],
                "chinese_translation": row["chinese_translation"],
                "message_link": row["message_link"],
            }
            for row in rows
        ]
        body = self._request_body(history, messages, await self._image_inputs(rows))
        try:
            async with self._analysis_session.post(
                self.settings.feedback_analysis.api_url,
                headers={
                    "Authorization": f"Bearer {self._api_key()}",
                    "Content-Type": "application/json",
                },
                json=body,
            ) as response:
                payload = await response.json(content_type=None)
                if response.status != 200:
                    raise ApiError(f"SiliconFlow request failed with HTTP {response.status}")
        except (aiohttp.ClientError, asyncio.TimeoutError) as exc:
            raise ApiError(f"SiliconFlow request failed: {type(exc).__name__}") from exc
        raw = self._output_text(payload)
        try:
            result = json.loads(raw)
            if not isinstance(result.get("items"), list):
                raise ValueError
        except (json.JSONDecodeError, AttributeError, ValueError) as exc:
            raise ApiError("SiliconFlow returned an invalid structured response") from exc
        return result, raw

    def _request_body(
        self,
        history: list[dict[str, Any]],
        messages: list[dict[str, Any]],
        images: list[dict[str, Any]],
    ) -> dict[str, Any]:
        content = list(images)
        content.append(
            {
                "type": "text",
                "text": json.dumps(
                    {"historical_analysis": history, "new_messages": messages},
                    ensure_ascii=False,
                ),
            }
        )
        return {
            "model": self._model(),
            "messages": [
                {"role": "system", "content": ANALYSIS_INSTRUCTIONS},
                {"role": "user", "content": content},
            ],
            "stream": False,
            "response_format": {
                "type": "json_schema",
                "json_schema": {
                    "name": "feedback_analysis",
                    "strict": True,
                    "schema": _response_schema(),
                },
            },
        }

    @staticmethod
    def _output_text(payload: dict[str, Any]) -> str:
        try:
            content = payload["choices"][0]["message"]["content"]
            if not isinstance(content, str):
                raise TypeError
            return content
        except (KeyError, IndexError, TypeError) as exc:
            raise ApiError("SiliconFlow response contains no output text") from exc

    async def _image_inputs(self, rows: list[Any]) -> list[dict[str, Any]]:
        remaining = self.settings.feedback_analysis.max_images_per_batch
        result: list[dict[str, Any]] = []
        if remaining == 0:
            return result
        for row in rows:
            try:
                channel = self.bot.get_channel(row["channel_id"]) or await self.bot.fetch_channel(
                    row["channel_id"]
                )
                message = await channel.fetch_message(row["message_id"])
                for attachment in message.attachments:
                    if remaining == 0:
                        return result
                    content_type = attachment.content_type or ""
                    if content_type.startswith("image/"):
                        result.append(
                            {
                                "type": "image_url",
                                "image_url": {"url": attachment.url, "detail": "auto"},
                            }
                        )
                        remaining -= 1
            except (discord.DiscordException, AttributeError):
                LOGGER.info("Could not refresh attachments for message %s", row["message_id"])
        return result

    def _feishu_fields(
        self, run: Any, item_row: Any, item: dict[str, Any], messages: dict[str, Any]
    ) -> dict[str, Any]:
        names = self.settings.feedback_analysis.fields
        source_ids = item["source_message_ids"]
        source_rows = [messages[value] for value in source_ids]
        source_times = [datetime.fromisoformat(row["message_time"]) for row in source_rows]
        first_message_time_ms = int(min(source_times).timestamp() * 1000)
        return {
            names["number"]: str(item_row["id"]),
            names["dates"]: first_message_time_ms,
            names["category"]: item["category"],
            names["user_feedback"]: item["user_feedback"],
            names["suggested_solution"]: item["suggested_solution"],
            names["users"]: item["users"],
            names["priority"]: item["priority"],
            names["review_status"]: "待审核",
            names["possible_duplicate"]: item["possible_duplicate"],
            names["duplicate_reason"]: item["duplicate_reason"],
            names["source_message_ids"]: ", ".join(source_ids),
            names["source_message_links"]: "\n".join(row["message_link"] for row in source_rows),
            names["source_channel_ids"]: ", ".join(
                sorted({str(row["channel_id"]) for row in source_rows})
            ),
            names["analysis_batch"]: f"{run['local_date']}#{run['id']}",
            names["model"]: self._model(),
        }
