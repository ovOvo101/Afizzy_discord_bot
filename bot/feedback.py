from __future__ import annotations

import asyncio
from datetime import UTC, datetime
import logging
import os
import time
from typing import Any

import aiohttp
import discord
from discord.ext import tasks

from .config import FeedbackChannelConfig, Settings
from .database import Database

LOGGER = logging.getLogger(__name__)
FEISHU_TOKEN_URL = "https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal"


class ApiError(RuntimeError):
    pass


class FeedbackApiClient:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.session: aiohttp.ClientSession | None = None
        self._feishu_token: str | None = None
        self._feishu_token_expires_at = 0.0
        self._token_lock = asyncio.Lock()

    async def start(self) -> None:
        if self.session is None:
            timeout = aiohttp.ClientTimeout(
                total=self.settings.feedback.request_timeout_seconds
            )
            self.session = aiohttp.ClientSession(timeout=timeout)

    async def close(self) -> None:
        if self.session is not None:
            await self.session.close()
            self.session = None

    def _session(self) -> aiohttp.ClientSession:
        if self.session is None:
            raise RuntimeError("Feedback API client has not been started")
        return self.session

    async def translate(self, text: str) -> tuple[str, str]:
        headers = {
            "Authorization": f"DeepL-Auth-Key {os.environ['DEEPL_API_KEY']}",
            "Content-Type": "application/json",
        }
        try:
            async with self._session().post(
                f"{self.settings.feedback.deepl_api_url}/v2/translate",
                headers=headers,
                json={"text": [text], "target_lang": "ZH-HANS"},
            ) as response:
                payload = await response.json(content_type=None)
                if response.status != 200:
                    raise ApiError(f"DeepL request failed with HTTP {response.status}")
        except (aiohttp.ClientError, asyncio.TimeoutError) as exc:
            raise ApiError(f"DeepL request failed: {type(exc).__name__}") from exc
        try:
            result = payload["translations"][0]
            return str(result["detected_source_language"]), str(result["text"])
        except (KeyError, IndexError, TypeError) as exc:
            raise ApiError("DeepL returned an invalid response") from exc

    async def _get_feishu_token(self, force: bool = False) -> str:
        async with self._token_lock:
            if (
                not force
                and self._feishu_token
                and time.monotonic() < self._feishu_token_expires_at
            ):
                return self._feishu_token
            try:
                async with self._session().post(
                    FEISHU_TOKEN_URL,
                    json={
                        "app_id": os.environ["FEISHU_APP_ID"],
                        "app_secret": os.environ["FEISHU_APP_SECRET"],
                    },
                ) as response:
                    payload = await response.json(content_type=None)
                    if response.status != 200 or payload.get("code", 0) != 0:
                        raise ApiError(
                            f"Feishu token request failed with HTTP {response.status}, "
                            f"code {payload.get('code', 'unknown')}"
                        )
            except (aiohttp.ClientError, asyncio.TimeoutError) as exc:
                raise ApiError(f"Feishu token request failed: {type(exc).__name__}") from exc
            try:
                self._feishu_token = str(payload["tenant_access_token"])
                expires_in = int(payload.get("expire", 7200))
            except (KeyError, TypeError, ValueError) as exc:
                raise ApiError("Feishu token response is invalid") from exc
            self._feishu_token_expires_at = time.monotonic() + max(60, expires_in - 300)
            return self._feishu_token

    async def create_feishu_record(
        self, channel: FeedbackChannelConfig, fields: dict[str, Any]
    ) -> str:
        url = (
            "https://open.feishu.cn/open-apis/bitable/v1/apps/"
            f"{channel.app_token}/tables/{channel.table_id}/records"
        )
        for attempt in range(2):
            token = await self._get_feishu_token(force=attempt == 1)
            try:
                async with self._session().post(
                    url,
                    headers={"Authorization": f"Bearer {token}"},
                    json={"fields": fields},
                ) as response:
                    payload = await response.json(content_type=None)
            except (aiohttp.ClientError, asyncio.TimeoutError) as exc:
                raise ApiError(f"Feishu record request failed: {type(exc).__name__}") from exc
            code = payload.get("code", 0)
            if attempt == 0 and (response.status == 401 or code in {99991663, 99991664, 99991668}):
                continue
            if response.status != 200 or code != 0:
                raise ApiError(
                    f"Feishu record request failed with HTTP {response.status}, "
                    f"code {code}"
                )
            try:
                return str(payload["data"]["record"]["record_id"])
            except (KeyError, TypeError) as exc:
                raise ApiError("Feishu record response is invalid") from exc
        raise ApiError("Feishu authentication failed after token refresh")


class FeedbackArchive:
    def __init__(self, bot: discord.Client, settings: Settings, database: Database) -> None:
        self.bot = bot
        self.settings = settings
        self.database = database
        self.channels = {item.channel_id: item for item in settings.feedback.channels}
        self.api = FeedbackApiClient(settings)

    async def start(self) -> None:
        await self.api.start()
        self.process_pending.start()

    async def stop(self) -> None:
        self.process_pending.cancel()
        await self.api.close()

    async def on_message(self, message: discord.Message) -> None:
        if message.channel.id not in self.channels:
            return
        if (
            message.guild is None
            or message.author.bot
            or message.webhook_id is not None
            or message.type not in {discord.MessageType.default, discord.MessageType.reply}
            or not message.content.strip()
            or any(
                role.name.casefold() == "staff"
                for role in getattr(message.author, "roles", ())
            )
        ):
            return
        attachment_urls = [attachment.url for attachment in message.attachments]
        original = message.content
        if attachment_urls:
            original += "\n\nAttachments:\n" + "\n".join(attachment_urls)
        claimed = self.database.claim_feedback(
            message.id,
            message.guild.id,
            message.channel.id,
            message.author.name,
            message.created_at,
            original,
            message.jump_url,
        )
        if claimed:
            LOGGER.info("Queued Discord feedback message %s", message.id)

    @tasks.loop(seconds=5)
    async def process_pending(self) -> None:
        now = datetime.now(UTC)
        for row in self.database.due_feedback(now):
            try:
                await self._process(row)
            except Exception as exc:
                self.database.defer_feedback(row["message_id"], str(exc), datetime.now(UTC))
                LOGGER.warning(
                    "Feedback message %s deferred: %s", row["message_id"], str(exc)
                )

    @process_pending.before_loop
    async def before_process_pending(self) -> None:
        await self.bot.wait_until_ready()

    async def _process(self, row: Any) -> None:
        channel_config = self.channels.get(row["channel_id"])
        if channel_config is None:
            raise ApiError(f"No feedback configuration for channel {row['channel_id']}")
        detected_language = row["detected_language"]
        translation = row["chinese_translation"]
        if not translation:
            detected_language, translation = await self.api.translate(row["original_message"])
            self.database.save_feedback_translation(
                row["message_id"], detected_language, translation
            )
        if not row["feishu_record_id"]:
            names = channel_config.fields
            timestamp_ms = int(datetime.fromisoformat(row["message_time"]).timestamp() * 1000)
            fields: dict[str, Any] = {
                names["username"]: row["username"],
                names["message_time"]: timestamp_ms,
                names["original_message"]: row["original_message"],
                names["message_link"]: {
                    "link": row["message_link"],
                    "text": "Open Discord message",
                },
                names["detected_language"]: detected_language,
                names["chinese_translation"]: translation,
                names["message_id"]: str(row["message_id"]),
                names["channel_id"]: str(row["channel_id"]),
            }
            record_id = await self.api.create_feishu_record(channel_config, fields)
            self.database.mark_feedback_delivered(row["message_id"], record_id)
        self.database.mark_feedback_acknowledged(row["message_id"])
        LOGGER.info("Archived feedback message %s", row["message_id"])
