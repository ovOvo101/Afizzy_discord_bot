from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from random import choice
from typing import TypeVar

import yaml

class ContentError(ValueError):
    pass


@dataclass(frozen=True)
class PollItem:
    id: str
    title: str
    question: str
    options: tuple[str, ...]
    description: str | None = None


def _load(path: Path) -> object:
    try:
        return yaml.safe_load(path.read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError) as exc:
        raise ContentError(f"Unable to load {path}") from exc


def load_polls(path: Path) -> list[PollItem]:
    payload = _load(path)
    if not isinstance(payload, list):
        raise ContentError("Poll data must be a list")
    result: list[PollItem] = []
    ids: set[str] = set()
    for index, item in enumerate(payload):
        if not isinstance(item, dict):
            raise ContentError(f"poll {index} must be a mapping")
        identifier, title, question, options = item.get("id"), item.get("title"), item.get("question"), item.get("options")
        if not all(isinstance(value, str) and value.strip() for value in (identifier, title, question)):
            raise ContentError(f"poll {index} needs id, title and question")
        if identifier in ids or not isinstance(options, list) or not 3 <= len(options) <= 5 or not all(isinstance(option, str) and option.strip() for option in options):
            raise ContentError(f"poll {identifier} is invalid")
        ids.add(identifier)
        description = item.get("description")
        if description is not None and not isinstance(description, str):
            raise ContentError(f"poll {identifier} description must be text")
        result.append(PollItem(identifier, title, question, tuple(options), description))
    return result


T = TypeVar("T")


def pick_unseen(items: list[T], used_ids: set[str]) -> T:
    available = [item for item in items if item.id not in used_ids]  # type: ignore[attr-defined]
    return choice(available or items)
