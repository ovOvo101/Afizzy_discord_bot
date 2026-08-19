from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from random import choice
from typing import TypeVar

import yaml

VALID_CATEGORIES = frozenset({"oc", "fanart", "fanfiction", "writing", "relationship", "worldbuilding", "au", "funny", "challenge"})


class ContentError(ValueError):
    pass


@dataclass(frozen=True)
class PollItem:
    id: str
    title: str
    question: str
    options: tuple[str, ...]
    description: str | None = None


@dataclass(frozen=True)
class PromptItem:
    id: str
    category: str
    text: str


@dataclass(frozen=True)
class IdeaItem:
    id: str
    text: str


@dataclass(frozen=True)
class IdeaParts:
    base: dict[str, tuple[IdeaItem, ...]]
    constraints: tuple[IdeaItem, ...]
    bonuses: tuple[IdeaItem, ...]


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


def load_prompts(path: Path) -> list[PromptItem]:
    payload = _load(path)
    if not isinstance(payload, list):
        raise ContentError("Prompt data must be a list")
    result: list[PromptItem] = []
    ids: set[str] = set()
    for index, item in enumerate(payload):
        if not isinstance(item, dict):
            raise ContentError(f"prompt {index} must be a mapping")
        identifier, category, text = item.get("id"), item.get("category"), item.get("text")
        if not isinstance(identifier, str) or identifier in ids or category not in VALID_CATEGORIES or not isinstance(text, str) or not text.strip():
            raise ContentError(f"prompt {index} is invalid")
        ids.add(identifier)
        result.append(PromptItem(identifier, category, text))
    return result


def load_ideas(path: Path) -> IdeaParts:
    payload = _load(path)
    if not isinstance(payload, dict) or not isinstance(payload.get("base"), dict):
        raise ContentError("Idea data must have a base mapping")
    base: dict[str, tuple[IdeaItem, ...]] = {}
    identifiers: set[str] = set()

    def parse_entries(value: object, prefix: str) -> tuple[IdeaItem, ...]:
        if not isinstance(value, list) or not value:
            raise ContentError(f"{prefix} must be a non-empty list")
        result: list[IdeaItem] = []
        for index, item in enumerate(value, start=1):
            if isinstance(item, str):  # Legacy input remains readable during migration.
                identifier, text = f"{prefix}-{index:02d}", item
            elif isinstance(item, dict):
                identifier, text = item.get("id"), item.get("text")
            else:
                raise ContentError(f"invalid {prefix} entry")
            if not isinstance(identifier, str) or not identifier.strip() or identifier in identifiers or not isinstance(text, str) or not text.strip():
                raise ContentError(f"invalid {prefix} entry")
            identifiers.add(identifier)
            result.append(IdeaItem(identifier, text))
        return tuple(result)

    for category, raw_entries in payload["base"].items():
        if category not in VALID_CATEGORIES:
            raise ContentError(f"invalid idea category: {category}")
        base[category] = parse_entries(raw_entries, f"base-{category}")
    constraints, bonuses = payload.get("constraints", []), payload.get("bonuses", [])
    return IdeaParts(base, parse_entries(constraints, "constraint"), parse_entries(bonuses, "bonus"))


T = TypeVar("T")


def pick_unseen(items: list[T], used_ids: set[str]) -> T:
    available = [item for item in items if item.id not in used_ids]  # type: ignore[attr-defined]
    return choice(available or items)


def make_idea(parts: IdeaParts, category: str | None = None) -> str:
    available = category if category in parts.base else choice(list(parts.base))
    lines = [choice(parts.base[available]).text]
    if parts.constraints:
        lines.append(choice(parts.constraints).text)
    if parts.bonuses:
        lines.extend(["", f"Bonus: {choice(parts.bonuses).text}"])
    return "\n".join(lines)
