from __future__ import annotations

from dataclasses import dataclass
import os
from pathlib import Path
from zoneinfo import ZoneInfo

import yaml


class ConfigError(ValueError):
    pass


@dataclass(frozen=True)
class DiscordConfig:
    guild_id: int | None
    poll_channel_id: int | None
    prompt_channel_id: int | None
    invite_code_channel_id: int | None


@dataclass(frozen=True)
class ScheduleConfig:
    timezone: ZoneInfo
    poll_time: str
    poll_weekdays: tuple[int, ...]
    prompt_time: str
    poll_duration_hours: int


@dataclass(frozen=True)
class FeatureConfig:
    invite_code_limit: bool
    daily_poll: bool
    daily_prompt: bool
    idea: bool
    feedback_archive: bool


FEEDBACK_FIELD_KEYS = (
    "username",
    "message_time",
    "original_message",
    "message_link",
    "detected_language",
    "chinese_translation",
    "message_id",
    "channel_id",
)


@dataclass(frozen=True)
class FeedbackChannelConfig:
    channel_id: int
    app_token: str
    table_id: str
    fields: dict[str, str]


@dataclass(frozen=True)
class FeedbackConfig:
    deepl_api_url: str
    request_timeout_seconds: int
    backfill_days: int
    excluded_usernames: tuple[str, ...]
    channels: tuple[FeedbackChannelConfig, ...]


@dataclass(frozen=True)
class Settings:
    discord: DiscordConfig
    schedule: ScheduleConfig
    features: FeatureConfig
    feedback: FeedbackConfig
    database_path: Path
    polls_path: Path
    prompts_path: Path
    ideas_path: Path


def _optional_positive_int(value: object, name: str) -> int | None:
    if value in (None, 0, "", "0"):
        return None
    try:
        result = int(value)  # type: ignore[arg-type]
    except (TypeError, ValueError) as exc:
        raise ConfigError(f"{name} must be a positive integer") from exc
    if result < 1:
        raise ConfigError(f"{name} must be a positive integer")
    return result


def _time(value: object, name: str) -> str:
    if not isinstance(value, str) or len(value) != 5 or value[2] != ":":
        raise ConfigError(f"{name} must be HH:MM")
    try:
        hour, minute = (int(part) for part in value.split(":"))
    except ValueError as exc:
        raise ConfigError(f"{name} must be HH:MM") from exc
    if not 0 <= hour <= 23 or not 0 <= minute <= 59:
        raise ConfigError(f"{name} must be a valid time")
    return value


def _boolean(value: object, name: str, default: bool) -> bool:
    if value is None:
        return default
    if not isinstance(value, bool):
        raise ConfigError(f"{name} must be true or false")
    return value


def _weekdays(value: object) -> tuple[int, ...]:
    names = {
        "monday": 0,
        "tuesday": 1,
        "wednesday": 2,
        "thursday": 3,
        "friday": 4,
        "saturday": 5,
        "sunday": 6,
    }
    if value is None:
        return tuple(range(7))
    if not isinstance(value, list) or not value:
        raise ConfigError("scheduling.poll_weekdays must be a non-empty list")
    try:
        weekdays = tuple(names[str(day).lower()] for day in value)
    except KeyError as exc:
        raise ConfigError("scheduling.poll_weekdays contains an invalid weekday") from exc
    if len(set(weekdays)) != len(weekdays):
        raise ConfigError("scheduling.poll_weekdays must not contain duplicates")
    return weekdays


def load_settings(path: str | Path) -> Settings:
    config_path = Path(path)
    try:
        payload = yaml.safe_load(config_path.read_text(encoding="utf-8")) or {}
    except OSError as exc:
        raise ConfigError(f"Unable to read config: {config_path}") from exc
    if not isinstance(payload, dict):
        raise ConfigError("Config root must be a mapping")
    discord = payload.get("discord", {})
    scheduling = payload.get("scheduling", {})
    storage = payload.get("storage", {})
    content = payload.get("content", {})
    features = payload.get("features", {})
    feedback = payload.get("feedback", {})
    if not all(
        isinstance(section, dict)
        for section in (discord, scheduling, storage, content, features, feedback)
    ):
        raise ConfigError("Config sections must be mappings")
    try:
        timezone = ZoneInfo(str(scheduling.get("timezone", "Asia/Shanghai")))
    except Exception as exc:
        raise ConfigError("scheduling.timezone is invalid") from exc
    duration = scheduling.get("poll_duration_hours", 24)
    if not isinstance(duration, int) or not 1 <= duration <= 168:
        raise ConfigError("poll_duration_hours must be between 1 and 168")
    root = config_path.parent.parent
    def resolve(value: object, name: str) -> Path:
        if not isinstance(value, str) or not value:
            raise ConfigError(f"{name} is required")
        return root / value
    feedback_enabled = _boolean(
        features.get("feedback_archive"), "features.feedback_archive", False
    )
    raw_channels = feedback.get("channels", [])
    if not isinstance(raw_channels, list):
        raise ConfigError("feedback.channels must be a list")
    feedback_channels: list[FeedbackChannelConfig] = []
    seen_channel_ids: set[int] = set()
    for index, item in enumerate(raw_channels):
        prefix = f"feedback.channels[{index}]"
        if not isinstance(item, dict):
            raise ConfigError(f"{prefix} must be a mapping")
        channel_id = _optional_positive_int(item.get("channel_id"), f"{prefix}.channel_id")
        if channel_id is None:
            raise ConfigError(f"{prefix}.channel_id is required")
        if channel_id in seen_channel_ids:
            raise ConfigError(f"Duplicate feedback channel_id: {channel_id}")
        seen_channel_ids.add(channel_id)
        app_token, table_id, fields = item.get("app_token"), item.get("table_id"), item.get("fields")
        if not isinstance(app_token, str) or not app_token:
            raise ConfigError(f"{prefix}.app_token is required")
        if not isinstance(table_id, str) or not table_id:
            raise ConfigError(f"{prefix}.table_id is required")
        if not isinstance(fields, dict):
            raise ConfigError(f"{prefix}.fields must be a mapping")
        if set(fields) != set(FEEDBACK_FIELD_KEYS) or not all(
            isinstance(value, str) and value for value in fields.values()
        ):
            raise ConfigError(
                f"{prefix}.fields must contain exactly: {', '.join(FEEDBACK_FIELD_KEYS)}"
            )
        if len(set(fields.values())) != len(FEEDBACK_FIELD_KEYS):
            raise ConfigError(f"{prefix}.fields must map to distinct Feishu columns")
        feedback_channels.append(
            FeedbackChannelConfig(channel_id, app_token, table_id, dict(fields))
        )
    if feedback_enabled and not feedback_channels:
        raise ConfigError("feedback.channels is required when feedback_archive is enabled")
    timeout = feedback.get("request_timeout_seconds", 15)
    if not isinstance(timeout, int) or not 1 <= timeout <= 120:
        raise ConfigError("feedback.request_timeout_seconds must be between 1 and 120")
    api_url = feedback.get("deepl_api_url", "https://api-free.deepl.com")
    if not isinstance(api_url, str) or not api_url.startswith("https://"):
        raise ConfigError("feedback.deepl_api_url must be an HTTPS URL")
    backfill_days = feedback.get("backfill_days", 0)
    if not isinstance(backfill_days, int) or not 0 <= backfill_days <= 30:
        raise ConfigError("feedback.backfill_days must be between 0 and 30")
    raw_excluded = feedback.get("excluded_usernames", [])
    if not isinstance(raw_excluded, list) or not all(
        isinstance(name, str) and name.strip() for name in raw_excluded
    ):
        raise ConfigError("feedback.excluded_usernames must be a list of usernames")
    excluded_usernames = tuple(name.strip().casefold() for name in raw_excluded)
    if len(set(excluded_usernames)) != len(excluded_usernames):
        raise ConfigError("feedback.excluded_usernames must not contain duplicates")
    if feedback_enabled:
        missing = [
            name
            for name in ("DEEPL_API_KEY", "FEISHU_APP_ID", "FEISHU_APP_SECRET")
            if not os.getenv(name)
        ]
        if missing:
            raise ConfigError(f"Missing required environment variables: {', '.join(missing)}")
    return Settings(
        discord=DiscordConfig(
            _optional_positive_int(discord.get("guild_id"), "guild_id"),
            _optional_positive_int(discord.get("poll_channel_id"), "poll_channel_id"),
            _optional_positive_int(discord.get("prompt_channel_id"), "prompt_channel_id"),
            _optional_positive_int(
                discord.get("invite_code_channel_id"), "invite_code_channel_id"
            ),
        ),
        schedule=ScheduleConfig(
            timezone,
            _time(scheduling.get("poll_time", "18:00"), "poll_time"),
            _weekdays(scheduling.get("poll_weekdays")),
            _time(scheduling.get("prompt_time", "20:00"), "prompt_time"),
            duration,
        ),
        features=FeatureConfig(
            invite_code_limit=_boolean(
                features.get("invite_code_limit"), "features.invite_code_limit", True
            ),
            daily_poll=_boolean(features.get("daily_poll"), "features.daily_poll", False),
            daily_prompt=_boolean(
                features.get("daily_prompt"), "features.daily_prompt", False
            ),
            idea=_boolean(features.get("idea"), "features.idea", False),
            feedback_archive=feedback_enabled,
        ),
        feedback=FeedbackConfig(
            api_url.rstrip("/"),
            timeout,
            backfill_days,
            excluded_usernames,
            tuple(feedback_channels),
        ),
        database_path=resolve(storage.get("database_path"), "storage.database_path"),
        polls_path=resolve(content.get("polls_path"), "content.polls_path"),
        prompts_path=resolve(content.get("prompts_path"), "content.prompts_path"),
        ideas_path=resolve(content.get("ideas_path"), "content.ideas_path"),
    )
