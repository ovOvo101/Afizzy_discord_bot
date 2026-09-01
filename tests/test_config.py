from pathlib import Path

import pytest

from bot.config import ConfigError, load_settings


ANALYSIS_FIELDS = {
    "number": "ID",
    "dates": "Date",
    "category": "Category",
    "user_feedback": "Feedback",
    "suggested_solution": "Solution",
    "users": "User",
    "priority": "Priority",
    "review_status": "Review",
    "source_message_ids": "Message IDs",
    "source_message_links": "Links",
    "source_channel_ids": "Channels",
}


def test_load_settings_resolves_paths(tmp_path: Path) -> None:
    config_dir = tmp_path / "config"
    config_dir.mkdir()
    (config_dir / "config.yaml").write_text("""
discord: {guild_id: 0, poll_channel_id: 1, prompt_channel_id: 2, invite_code_channel_id: 3}
features: {invite_code_limit: true, daily_poll: true, daily_prompt: false, idea: false}
scheduling: {timezone: Asia/Shanghai, poll_time: '18:00', poll_weekdays: [wednesday, friday, sunday], prompt_time: '20:00', poll_duration_hours: 24}
storage: {database_path: data/test.sqlite3}
content: {polls_path: data/polls.yaml, prompts_path: data/prompts.yaml, ideas_path: data/ideas.yaml}
""", encoding="utf-8")
    settings = load_settings(config_dir / "config.yaml")
    assert settings.discord.poll_channel_id == 1
    assert settings.discord.invite_code_channel_id == 3
    assert settings.features.invite_code_limit
    assert settings.features.daily_poll
    assert settings.schedule.poll_weekdays == (2, 4, 6)
    assert not settings.features.daily_prompt
    assert not settings.features.idea
    assert settings.database_path == tmp_path / "data/test.sqlite3"


def test_invalid_time_is_rejected(tmp_path: Path) -> None:
    path = tmp_path / "config.yaml"
    path.write_text("scheduling: {poll_time: never}\n", encoding="utf-8")
    with pytest.raises(ConfigError):
        load_settings(path)


def test_analysis_requires_siliconflow_environment(
    tmp_path: Path, monkeypatch: object
) -> None:
    monkeypatch.delenv("SILICONFLOW_API_KEY", raising=False)  # type: ignore[attr-defined]
    monkeypatch.delenv("SILICONFLOW_MODEL", raising=False)  # type: ignore[attr-defined]
    for name in ("DEEPL_API_KEY", "FEISHU_APP_ID", "FEISHU_APP_SECRET"):
        monkeypatch.setenv(name, "test")  # type: ignore[attr-defined]
    path = tmp_path / "config.yaml"
    path.write_text(
        f"""
features: {{feedback_archive: true, feedback_analysis: true}}
storage: {{database_path: data/test.sqlite3}}
content: {{polls_path: data/polls.yaml, prompts_path: data/prompts.yaml, ideas_path: data/ideas.yaml}}
feedback:
  channels:
    - channel_id: 10
      app_token: bas1
      table_id: tbl1
      fields:
        username: username
        message_time: time
        original_message: original
        message_link: link
        detected_language: language
        chinese_translation: translation
        message_id: message_id
        channel_id: channel_id
feedback_analysis:
  app_token: bas1
  table_id: tbl2
  fields: {ANALYSIS_FIELDS!r}
""",
        encoding="utf-8",
    )

    with pytest.raises(ConfigError, match="SILICONFLOW_API_KEY"):
        load_settings(path)

    monkeypatch.setenv("SILICONFLOW_API_KEY", "test")  # type: ignore[attr-defined]
    monkeypatch.setenv("SILICONFLOW_MODEL", "test-model")  # type: ignore[attr-defined]
    settings = load_settings(path)
    assert settings.features.feedback_analysis
    assert settings.feedback_analysis.schedule_time == "10:00"
    assert settings.feedback_analysis.api_url == (
        "https://api.siliconflow.cn/v1/chat/completions"
    )


def test_classified_feedback_channel_configuration(
    tmp_path: Path, monkeypatch: object
) -> None:
    for name in (
        "DEEPL_API_KEY",
        "FEISHU_APP_ID",
        "FEISHU_APP_SECRET",
        "SILICONFLOW_API_KEY",
        "SILICONFLOW_MODEL",
    ):
        monkeypatch.setenv(name, "test")  # type: ignore[attr-defined]
    path = tmp_path / "config.yaml"
    path.write_text(
        """
features: {feedback_archive: true}
storage: {database_path: data/test.sqlite3}
content: {polls_path: data/polls.yaml, prompts_path: data/prompts.yaml, ideas_path: data/ideas.yaml}
feedback:
  backfill_days: 7
  classified_channels:
    - channel_id: 20
      app_token: bas1
      idea_table_id: idea-table
      bug_table_id: bug-table
      fields:
        username: username
        message_time: time
        original_message: original
        message_link: link
        detected_language: language
        chinese_translation: translation
        message_id: message_id
        channel_id: channel_id
""",
        encoding="utf-8",
    )

    settings = load_settings(path)

    channel = settings.feedback.classified_channels[0]
    assert channel.channel_id == 20
    assert channel.idea_table_id == "idea-table"
    assert channel.bug_table_id == "bug-table"
    assert settings.feedback.backfill_days == 7
