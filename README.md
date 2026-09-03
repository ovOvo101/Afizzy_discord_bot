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
- `features.minimum_message_length`: removes messages shorter than 6 non-whitespace
  characters in the configured channels.
- `discord.minimum_message_channel_ids`: lists the channel IDs where the minimum length applies.
- The legacy poll, prompt, and `/idea` features remain disabled; their curated data files have
  been removed.
- `features.feedback_archive`: translates configured feedback channels and archives them to
  Feishu Bitable.
- `features.feedback_analysis`: runs the daily SiliconFlow product-feedback analysis and writes
  review candidates to a separate Feishu Bitable table.

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

To monitor a mixed Discord channel, add it under `feedback.classified_channels`. SiliconFlow
classifies each translated message as `idea`, `bug`, or `invalid`; valid feedback is routed to
the configured table and invalid messages are retained only in SQLite for deduplication:

```yaml
feedback:
  backfill_days: 7
  classified_channels:
    - channel_id: 123456789012345678
      app_token: basxxxxxxxxxxxx
      idea_table_id: tbl_idea
      bug_table_id: tbl_bug
      fields:  # same eight-column mapping used by feedback.channels
        username: 用户名
        message_time: 消息时间
        original_message: 原始消息
        message_link: 消息链接
        detected_language: 识别语言
        chinese_translation: 中文翻译
        message_id: Discord消息ID
        channel_id: 频道ID
```

Classified channels additionally require `SILICONFLOW_API_KEY` and `SILICONFLOW_MODEL`.

## Feedback analysis configuration

Create a new table in the same Feishu Base before enabling this feature. Add `ID`, `Date`,
`Category`, `User Feedback`, `Suggested Solution`, `User`, `Priority`, `审核状态`,
`来源消息ID`, `来源消息链接`, and `来源频道ID`. `Date` is a
date/time field; the others are text fields.

Copy the new table ID from its URL into `feedback_analysis.table_id`, set
`features.feedback_analysis: true`, and add Railway secrets `SILICONFLOW_API_KEY` and
`SILICONFLOW_MODEL`. The production template uses
`https://api.siliconflow.cn/v1/chat/completions` and runs at 10:00 in
`scheduling.timezone`. On its first run it analyzes every successfully archived SQLite feedback
message; later runs only include messages that have not appeared in an earlier analysis run.

Results are always appended with `审核状态=待审核`. SiliconFlow and Feishu stages are persisted
separately, so a Feishu retry does not call SiliconFlow again. Image attachments are
refreshed from Discord at analysis time and used as visual inputs when available.
Select a SiliconFlow model that supports both image input and structured outputs.

For the temporary test server, set Railway `BOT_CONFIG_PATH=config/config.test.yaml`. Restore
`BOT_CONFIG_PATH=config/config.railway.yaml` after testing, then remove `config/config.test.yaml`.
