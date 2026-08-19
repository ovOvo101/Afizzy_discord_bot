---
name: discord-bot-manager
description: Manage this repository's local Discord creativity bot through natural language. Use for starting, stopping, restarting, checking, or reading logs; reading or changing safe Bot configuration; and listing, adding, updating, previewing, or deleting daily polls, creative prompts, and /idea Base, Constraint, or Bonus entries.
---

# Discord Bot Manager

Run all commands from the repository root with `.venv/bin/python -m bot.admin`. Never read, print, edit, or request the Discord token; it belongs only in `.env`.

## Lifecycle

- For “start”, run `start`; report the structured status.
- For “stop”, run `stop`.
- For “restart”, run `restart`.
- For status or logs, run `status` or `logs --lines N`.
- Explain that this local process stops when the computer sleeps or shuts down.

## Configuration

- For a complete safe configuration view, run `config list`.
- For one value, run `config get <dotted-path>`.
- For a requested value change, run `config set <dotted-path> <JSON-value-or-text>`.
- For disabling a configured Discord channel or guild ID, run `config unset <dotted-path>`.
- Do not edit YAML directly. The CLI validates the candidate, creates a backup, applies it atomically, and restarts the Bot only if it was already running.

## Content

Use these content kinds: `poll`, `prompt`, `idea-base`, `constraint`, `bonus`.

- List: `content <kind> list`; require `--category <category>` for `idea-base`.
- Find one: `content <kind> get <id>`.
- Add: translate the request into a stable ID and JSON object, then run `content <kind> add <id> --data '<JSON>'`. Include `--category` for `idea-base`.
- Update: run `content <kind> update <id> --data '<JSON partial>'`.
- Delete: first run `content <kind> preview-delete <id>`, show the exact item, then wait for an explicit user confirmation. Only after confirmation run `content <kind> delete <id> --confirm <id>`.

Use a valid category for prompts and idea bases: `oc`, `fanart`, `fanfiction`, `writing`, `relationship`, `worldbuilding`, `au`, `funny`, or `challenge`. Polls need `title`, `question`, and 3–5 `options`; prompts need `category` and `text`; idea entries need `text` and idea bases also need `category`.

## Reporting

Summarize the CLI JSON result. For writes, state the backup path and whether the Bot restarted. If the CLI returns an error, do not retry by editing YAML directly; explain the validation error and ask for corrected content.
