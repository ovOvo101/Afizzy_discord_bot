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
