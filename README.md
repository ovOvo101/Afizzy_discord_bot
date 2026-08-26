# Fizzy Discord Bot

A Discord bot that currently limits each member to one message in channels named `invite-code`. Daily polls, daily prompts, and `/idea` are isolated in an optional inspiration feature and are silent by default.

中文、零基础部署说明见：[使用指南.md](使用指南.md)。

将项目交给可信协作者、且不需要日常推送 GitHub 时，请使用：[分享指南.md](分享指南.md)。

## Run locally

1. Create a Discord application and Bot in the [Discord Developer Portal](https://discord.com/developers/applications). Enable **Message Content Intent** so the Bot can receive message events.
2. Invite it with the `bot` and `applications.commands` scopes. Grant View Channel, Send Messages, Manage Messages, Embed Links, Create Polls, and Use Application Commands in its target channels.
3. Copy `.env.example` to `.env`, then set `DISCORD_TOKEN`.
4. Copy `config/config.example.yaml` to `config/config.yaml`, then set the server ID. Keep `features.inspiration: false` so polls, prompts, and `/idea` remain silent.
5. Install and start:

   ```bash
   python3 -m venv .venv
   .venv/bin/pip install -e '.[dev]'
   .venv/bin/python -m bot.main
   ```

For development command sync, set `discord.guild_id` to your test server ID. Global slash commands can take up to an hour to appear.

## Manage through Codex

Install the shareable Skill into Codex, then use natural language such as “start the bot”, “show the current config”, or “add an OC prompt”.

```bash
cp -R skills/discord-bot-manager ~/.codex/skills/
```

The Skill uses the local management CLI. It keeps the Bot process, logs, SQLite database and content backups in `runtime/`, which is not committed.

```bash
.venv/bin/python -m bot.admin status
.venv/bin/python -m bot.admin start
.venv/bin/python -m bot.admin logs --lines 50
.venv/bin/python -m bot.admin stop
```

## Content and configuration

- `features.invite_code_limit`: enables the independent one-message limit for `invite-code` channels.
- `features.inspiration`: enables the isolated poll, prompt, and `/idea` feature as a group. It is `false` by default.

- `data/polls.yaml`: at least three, and at most five, answer options per poll.
- `data/prompts.yaml`: daily prompts by category.
- `data/ideas.yaml`: composable base prompts, constraints and bonuses for `/idea`.
- `config/config.yaml`: your local configuration, not committed. Start from `config/config.example.yaml`.

When inspiration is enabled, the app validates its content before connecting to Discord. The management CLI validates and backs up changes before applying them, then restarts an already-running Bot. Message-limit state is stored in SQLite, so restarting the Bot does not reset a member's allowance.

## Tests

```bash
python -m pytest
python -m ruff check bot tests
```

## Deploy on Railway

The repository includes `railway.json` and `config/config.railway.yaml` for a continuously
running worker. Connect this GitHub repository to Railway, set the secret variable
`DISCORD_TOKEN`, and attach a volume at `/data` so the SQLite message-limit history survives
redeployments. Do not generate a public domain; the Discord Bot only needs outbound access.
