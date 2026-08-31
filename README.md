# Fizzy Discord Bot

Fizzy is deployed as a continuously running Railway worker. It limits each member to one
message in a configured channel and can run scheduled polls. Polls, prompts, and `/idea`
have independent feature switches.

## Railway deployment

The production deployment uses:

- `Dockerfile` for a reproducible Python image;
- `railway.json` for the Docker builder and restart policy;
- `config/config.railway.yaml` for production settings;
- a Railway Volume mounted at `/data` for persistent SQLite state;
- the Railway secret variable `DISCORD_TOKEN`.

The Bot does not need a public domain because it only opens outbound connections to Discord.
Pushes to the GitHub `main` branch trigger automatic Railway deployments.

## Features

- `features.invite_code_limit`: enables the persistent one-message limit for `invite-code`.
- `discord.invite_code_channel_id`: identifies the channel where that limit applies.
- `features.daily_poll`: enables scheduled polls.
- `scheduling.poll_weekdays`: selects the weekdays when polls are published.
- `features.daily_prompt`: enables scheduled daily prompts.
- `features.idea`: enables the `/idea` command.
- `features.feedback_archive`: translates configured feedback channels and archives them to
  Feishu Bitable.
- `data/polls.yaml`, `data/prompts.yaml`, and `data/ideas.yaml`: inspiration content retained for
  future use.

## Verification

The test suite validates configuration, content, persistent message claims, and the channel
limiter:

```bash
python -m pytest
python -m ruff check bot tests
```

Production status and logs are available in the Railway project dashboard.

## Feedback archive configuration

Enable the feature and add one entry per Discord channel. Each channel may target a different
Feishu Bitable. Columns must be text except `message_time` (date/time) and `message_link` (URL):

```yaml
features:
  feedback_archive: true
feedback:
  deepl_api_url: https://api-free.deepl.com  # use https://api.deepl.com for DeepL Pro
  request_timeout_seconds: 15
  channels:
    - channel_id: 123456789012345678
      app_token: basxxxxxxxxxxxx
      table_id: tblxxxxxxxxxxxx
      fields:
        username: 用户名
        message_time: 消息时间
        original_message: 原始消息
        message_link: 消息链接
        detected_language: 识别语言
        chinese_translation: 中文翻译
        message_id: Discord消息ID
        channel_id: 频道ID
```

Set `DEEPL_API_KEY`, `FEISHU_APP_ID`, and `FEISHU_APP_SECRET` as Railway secrets before
enabling the feature. `DISCORD_TOKEN` remains required. The Feishu custom app must have Bitable
record write access to every configured table. Failed jobs persist in SQLite across restarts,
so keep the Railway Volume mounted at `/data`.

The archive is silent: it never replies to Discord messages. Messages from members with a role
named `staff` (case-insensitive) are ignored.

For the temporary test server, set Railway `BOT_CONFIG_PATH=config/config.test.yaml`. Restore
`BOT_CONFIG_PATH=config/config.railway.yaml` after testing, then remove `config/config.test.yaml`.
