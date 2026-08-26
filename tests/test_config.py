from pathlib import Path

import pytest

from bot.config import ConfigError, load_settings


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
