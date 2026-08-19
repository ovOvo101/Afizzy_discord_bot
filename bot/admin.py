"""Safe local lifecycle and content administration for the Discord bot."""
from __future__ import annotations

import argparse
import json
import os
import signal
import subprocess
import sys
import time
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import yaml
from dotenv import load_dotenv

from .config import ConfigError, load_settings
from .content import VALID_CATEGORIES, ContentError, load_ideas, load_polls, load_prompts

ROOT = Path(__file__).resolve().parents[1]
CONFIG_PATH = ROOT / "config/config.yaml"
RUNTIME = ROOT / "runtime"
PID_PATH = RUNTIME / "bot.pid"
LOG_PATH = RUNTIME / "bot.log"
BACKUPS = RUNTIME / "backups"
MAX_BACKUPS = 20
MUTABLE_CONFIG = {
    "discord.guild_id", "discord.poll_channel_id", "discord.prompt_channel_id",
    "scheduling.timezone", "scheduling.poll_time", "scheduling.prompt_time",
    "scheduling.poll_duration_hours", "storage.database_path", "content.polls_path",
    "content.prompts_path", "content.ideas_path",
}
OPTIONAL_CONFIG = {"discord.guild_id", "discord.poll_channel_id", "discord.prompt_channel_id"}


class AdminError(RuntimeError):
    pass


def output(value: object) -> None:
    print(json.dumps(value, ensure_ascii=False, indent=2, default=str))


def read_yaml(path: Path) -> Any:
    try:
        return yaml.safe_load(path.read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError) as exc:
        raise AdminError(f"Cannot read {path.relative_to(ROOT)}") from exc


def validate_project() -> None:
    load_settings(CONFIG_PATH)
    settings = load_settings(CONFIG_PATH)
    load_polls(settings.polls_path)
    load_prompts(settings.prompts_path)
    load_ideas(settings.ideas_path)


def process_id() -> int | None:
    try:
        pid = int(PID_PATH.read_text(encoding="utf-8").strip())
        os.kill(pid, 0)
        return pid
    except (OSError, ValueError):
        PID_PATH.unlink(missing_ok=True)
        return None


def status() -> dict[str, object]:
    pid = process_id()
    return {"running": pid is not None, "pid": pid, "log_path": str(LOG_PATH.relative_to(ROOT))}


def start() -> dict[str, object]:
    load_dotenv(ROOT / ".env")
    if not os.getenv("DISCORD_TOKEN"):
        raise AdminError("DISCORD_TOKEN is missing from .env")
    validate_project()
    active = process_id()
    if active:
        return {**status(), "message": "Bot is already running"}
    RUNTIME.mkdir(parents=True, exist_ok=True)
    with LOG_PATH.open("a", encoding="utf-8") as log:
        process = subprocess.Popen(
            [sys.executable, "-m", "bot.main"], cwd=ROOT, stdout=log,
            stderr=subprocess.STDOUT, start_new_session=True, env=os.environ.copy(),
        )
    PID_PATH.write_text(str(process.pid), encoding="utf-8")
    time.sleep(0.25)
    if process.poll() is not None:
        PID_PATH.unlink(missing_ok=True)
        raise AdminError("Bot exited during startup; inspect runtime/bot.log")
    return {**status(), "message": "Bot started"}


def stop() -> dict[str, object]:
    pid = process_id()
    if not pid:
        return {**status(), "message": "Bot is not running"}
    os.kill(pid, signal.SIGTERM)
    deadline = time.monotonic() + 8
    while time.monotonic() < deadline:
        if process_id() is None:
            return {**status(), "message": "Bot stopped"}
        time.sleep(0.1)
    os.kill(pid, signal.SIGKILL)
    PID_PATH.unlink(missing_ok=True)
    return {**status(), "message": "Bot force-stopped"}


def restart_if_running(was_running: bool) -> dict[str, object]:
    if not was_running:
        return {"restarted": False}
    stop()
    return {"restarted": True, "status": start()}


def tail(lines: int) -> dict[str, object]:
    if not LOG_PATH.exists():
        return {"lines": []}
    return {"lines": LOG_PATH.read_text(encoding="utf-8", errors="replace").splitlines()[-lines:]}


def backup(path: Path) -> Path:
    BACKUPS.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%S%fZ")
    target = BACKUPS / f"{path.stem}-{stamp}{path.suffix}"
    target.write_text(path.read_text(encoding="utf-8"), encoding="utf-8")
    candidates = sorted(BACKUPS.glob(f"{path.stem}-*{path.suffix}"))
    for stale in candidates[:-MAX_BACKUPS]:
        stale.unlink()
    return target


def validate_candidate(path: Path, payload: object, loader: Callable[[Path], object]) -> None:
    candidate = path.with_name(f".{path.name}.candidate")
    candidate.write_text(yaml.safe_dump(payload, allow_unicode=True, sort_keys=False), encoding="utf-8")
    try:
        loader(candidate)
    except (ConfigError, ContentError) as exc:
        raise AdminError(str(exc)) from exc
    finally:
        candidate.unlink(missing_ok=True)


def write_yaml(path: Path, payload: object, loader: Callable[[Path], object]) -> str:
    was_running = process_id() is not None
    validate_candidate(path, payload, loader)
    saved = backup(path)
    temporary = path.with_name(f".{path.name}.new")
    temporary.write_text(yaml.safe_dump(payload, allow_unicode=True, sort_keys=False), encoding="utf-8")
    temporary.replace(path)
    result = restart_if_running(was_running)
    return json.dumps({"backup": str(saved.relative_to(ROOT)), **result}, ensure_ascii=False)


def config_value(payload: dict[str, Any], dotted: str) -> tuple[dict[str, Any], str]:
    if dotted not in MUTABLE_CONFIG:
        raise AdminError("Config path is not editable")
    section, key = dotted.split(".", 1)
    return payload.setdefault(section, {}), key


def config_action(args: argparse.Namespace) -> dict[str, object]:
    payload = read_yaml(CONFIG_PATH)
    if not isinstance(payload, dict):
        raise AdminError("Config root must be a mapping")
    if args.action == "list":
        return {path: payload.get(path.split(".")[0], {}).get(path.split(".")[1]) for path in sorted(MUTABLE_CONFIG)}
    parent, key = config_value(payload, args.path)
    if args.action == "get":
        return {args.path: parent.get(key)}
    if args.action == "unset":
        if args.path not in OPTIONAL_CONFIG:
            raise AdminError("Required config paths cannot be deleted")
        parent[key] = 0
    else:
        try:
            parent[key] = json.loads(args.value)
        except json.JSONDecodeError:
            parent[key] = args.value
    meta = json.loads(write_yaml(CONFIG_PATH, payload, load_settings))
    return {args.path: parent[key], **meta}


def content_path(kind: str) -> tuple[Path, Callable[[Path], object]]:
    settings = load_settings(CONFIG_PATH)
    return {
        "poll": (settings.polls_path, load_polls), "prompt": (settings.prompts_path, load_prompts),
        "idea-base": (settings.ideas_path, load_ideas), "constraint": (settings.ideas_path, load_ideas),
        "bonus": (settings.ideas_path, load_ideas),
    }[kind]


def content_entries(payload: Any, kind: str, category: str | None = None) -> list[dict[str, Any]]:
    if kind in {"poll", "prompt"}:
        return payload
    if kind == "idea-base":
        if not category:
            raise AdminError("idea-base requires --category")
        return payload["base"].setdefault(category, [])
    key = "constraints" if kind == "constraint" else "bonuses"
    return payload.setdefault(key, [])


def content_action(args: argparse.Namespace) -> dict[str, object]:
    path, loader = content_path(args.kind)
    payload = read_yaml(path)
    entries = content_entries(payload, args.kind, getattr(args, "category", None))
    if args.action == "list":
        return {"items": entries}
    item = next((entry for entry in entries if entry.get("id") == args.id), None)
    if args.action == "get":
        if not item:
            raise AdminError("Item not found")
        return item
    if args.action == "preview-delete":
        if not item:
            raise AdminError("Item not found")
        return {"delete": item, "confirmation": f"Run delete with --confirm {args.id}"}
    if args.action == "delete":
        if args.confirm != args.id:
            raise AdminError("Deletion requires --confirm with the item ID")
        if not item:
            raise AdminError("Item not found")
        entries.remove(item)
        if not entries:
            raise AdminError("A content group cannot be empty")
    else:
        try:
            values = json.loads(args.data)
        except (TypeError, json.JSONDecodeError) as exc:
            raise AdminError("--data must be a JSON object") from exc
        if not isinstance(values, dict):
            raise AdminError("--data must be a JSON object")
        if args.action == "add":
            if item:
                raise AdminError("ID already exists")
            values["id"] = args.id
            if args.kind == "idea-base" and args.category not in VALID_CATEGORIES:
                raise AdminError("Unknown idea category")
            entries.append(values)
        elif args.action == "update":
            if not item:
                raise AdminError("Item not found")
            if "id" in values and values["id"] != args.id:
                raise AdminError("IDs cannot be changed")
            item.update(values)
    meta = json.loads(write_yaml(path, payload, loader))
    return {"kind": args.kind, "action": args.action, **meta}


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    for name in ("start", "stop", "restart", "status"):
        sub.add_parser(name)
    logs = sub.add_parser("logs")
    logs.add_argument("--lines", type=int, default=50)
    config = sub.add_parser("config")
    config_sub = config.add_subparsers(dest="action", required=True)
    config_sub.add_parser("list")
    for name in ("get", "unset"):
        item = config_sub.add_parser(name); item.add_argument("path")
    item = config_sub.add_parser("set"); item.add_argument("path"); item.add_argument("value")
    content = sub.add_parser("content")
    content.add_argument("kind", choices=["poll", "prompt", "idea-base", "constraint", "bonus"])
    content.add_argument("--category", choices=sorted(VALID_CATEGORIES))
    content_sub = content.add_subparsers(dest="action", required=True)
    content_sub.add_parser("list")
    for name in ("get", "preview-delete"):
        item = content_sub.add_parser(name); item.add_argument("id")
    item = content_sub.add_parser("delete"); item.add_argument("id"); item.add_argument("--confirm")
    for name in ("add", "update"):
        item = content_sub.add_parser(name); item.add_argument("id"); item.add_argument("--data", required=True)
    return parser


def main() -> None:
    args = build_parser().parse_args()
    try:
        if args.command == "start": result = start()
        elif args.command == "stop": result = stop()
        elif args.command == "restart": stop(); result = start()
        elif args.command == "status": result = status()
        elif args.command == "logs": result = tail(args.lines)
        elif args.command == "config": result = config_action(args)
        else: result = content_action(args)
        output(result)
    except AdminError as exc:
        output({"error": str(exc)})
        raise SystemExit(2)


if __name__ == "__main__":
    main()
