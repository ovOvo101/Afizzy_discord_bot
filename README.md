# Creative Discord Bot

A low-pressure Discord bot for creator communities. It posts one daily poll, one daily creative prompt, and provides `/idea` for on-demand inspiration. Translation, AI chat, rankings, moderation and economy features are intentionally out of scope.

## Run locally

1. Create a Discord application and Bot in the [Discord Developer Portal](https://discord.com/developers/applications). Enable **Message Content Intent** under Bot settings; it is only used to count replies to the daily prompt.
2. Invite it with the `bot` and `applications.commands` scopes. Grant View Channel, Send Messages, Embed Links, Create Polls, and Use Application Commands in its target channels.
3. Copy `.env.example` to `.env`, then set `DISCORD_TOKEN`.
4. Set the target channel IDs in `config/config.yaml`. Keep them as `0` to disable that scheduled post safely.
5. Install and start:

   ```bash
   python3 -m venv .venv
   .venv/bin/pip install -e '.[dev]'
   .venv/bin/python -m bot.main
   ```

For development command sync, set `discord.guild_id` to your test server ID. Global slash commands can take up to an hour to appear.

## Docker deployment

```bash
cp .env.example .env
# edit .env and config/config.yaml
docker compose up -d --build
```

SQLite lives in the named `bot-data` volume. Back it up periodically, for example: `docker cp "$(docker compose ps -q bot)":/app/data/bot.sqlite3 ./bot-backup.sqlite3`. Store that copied file in your normal backup destination.

## Content and configuration

- `data/polls.yaml`: at least three, and at most five, answer options per poll.
- `data/prompts.yaml`: daily prompts by category.
- `data/ideas.yaml`: composable base prompts, constraints and bonuses for `/idea`.
- `config/config.yaml`: schedule defaults to Asia/Shanghai, poll at 18:00 and prompt at 20:00.

The app validates all config and content before it connects to Discord. It records date-level publication state in SQLite, so a restart cannot double-post a scheduled item. It restores pending poll-result summaries after restart but never sends missed daily posts retroactively.

## Tests

```bash
python -m pytest
python -m ruff check bot tests
```
