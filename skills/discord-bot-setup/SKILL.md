---
name: discord-bot-setup
description: Set up a shared copy of this repository's Discord bot on a new local Mac. Use when someone needs to install dependencies, create safe local configuration files, verify readiness, install the management skill, or make a first local Bot start without exposing a Discord token.
---

# Discord Bot Setup

Prepare a local copy of this project for a trusted operator. The Bot token is a secret: never request it in chat, read it, print it, put it in a command, commit it, or copy it between machines. The operator writes it directly into their own local `.env`.

## Setup workflow

1. Confirm the current directory is the project root (it contains `pyproject.toml`, `bot/`, and `config/config.example.yaml`). If the project has not been cloned yet, ask the operator to clone or download it first.
2. Run the bootstrap script from the project root:

   ```bash
   python ~/.codex/skills/discord-bot-setup/scripts/setup_local.py --project-root .
   ```

   It creates `.venv` and installs dependencies, creates local `.env` and `config/config.yaml` only when absent, and validates the configuration and content. It reports only readiness booleans, never a token.
3. If `token_configured` is false, tell the operator to open `.env` locally in a text editor and replace `replace-me` with their own Discord Bot Token. Do not ask them to paste or reveal it. After they say it is saved, rerun the bootstrap script with `--skip-install`.
4. Ask for the non-secret Discord server ID. If needed, explain: Discord Settings → Advanced → enable Developer Mode; then right-click the server → Copy ID.
5. Set the server ID and current feature mode through the manager CLI (never by directly editing YAML):

   ```bash
   .venv/bin/python -m bot.admin config set discord.guild_id <server-id>
   .venv/bin/python -m bot.admin config set features.invite_code_limit true
   .venv/bin/python -m bot.admin config set features.inspiration false
   ```

   The Bot limits each member to one message in channels named `invite-code`. Polls, prompts, and `/idea` remain silent while inspiration is false. Read only safe settings with `config list`.
6. Install the accompanying management skill so later requests such as “start Bot” or “add an OC prompt” work naturally:

   ```bash
   mkdir -p ~/.codex/skills
   cp -R skills/discord-bot-manager ~/.codex/skills/discord-bot-manager
   ```

   Do not overwrite an existing manager skill without first telling the operator and obtaining confirmation.
7. Start with `.venv/bin/python -m bot.admin start`, then inspect `status` and `logs --lines 50`. Report the result without exposing secrets.

## Important limits

- The Bot runs on this Mac and goes offline if the Mac sleeps, shuts down, or loses network access.
- One Bot Token should have one intended running instance. Multiple copies using the same token can duplicate messages and split local SQLite history.
- Discord app creation, bot invitation, and Token generation happen in Discord's Developer Portal; guide the operator there if they have not completed those steps.
- This Skill is a convenience workflow, not an access-control boundary. Anyone with the local project and Token can operate the Bot identity.

## Troubleshooting

- If setup reports an invalid config or content file, show the reported path/error and do not overwrite the existing local files.
- If the Bot does not start, run `logs --lines 50`; common causes are an invalid Token, incorrect channel permissions, or a missing channel ID.
- If slash commands do not appear promptly, confirm `discord.guild_id` is the test server ID and that the app was invited with the `applications.commands` scope.
