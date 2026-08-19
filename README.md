# Creative Discord Bot

A low-pressure Discord bot for creator communities. It posts one daily poll, one daily creative prompt, and provides `/idea` for on-demand inspiration. Translation, AI chat, rankings, moderation and economy features are intentionally out of scope.

## Run locally

1. Create a Discord application and Bot in the [Discord Developer Portal](https://discord.com/developers/applications). Enable **Message Content Intent** under Bot settings; it is only used to count replies to the daily prompt.
2. Invite it with the `bot` and `applications.commands` scopes. Grant View Channel, Send Messages, Embed Links, Create Polls, and Use Application Commands in its target channels.
3. Copy `.env.example` to `.env`, then set `DISCORD_TOKEN`.
4. Copy `config/config.example.yaml` to `config/config.yaml`, then set the target channel IDs. Keep them as `0` to disable that scheduled post safely.
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

- `data/polls.yaml`: at least three, and at most five, answer options per poll.
- `data/prompts.yaml`: daily prompts by category.
- `data/ideas.yaml`: composable base prompts, constraints and bonuses for `/idea`.
- `config/config.yaml`: your local configuration, not committed. Start from `config/config.example.yaml`.

The app validates all config and content before it connects to Discord. The management CLI validates and backs up changes before applying them, then restarts an already-running Bot. It records date-level publication state in SQLite, so a restart cannot double-post a scheduled item. It restores pending poll-result summaries after restart but never sends missed daily posts retroactively.

## Tests

```bash
python -m pytest
python -m ruff check bot tests
```
