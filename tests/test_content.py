from pathlib import Path

import pytest

from bot.content import (
    ContentError,
    load_ideas,
    load_polls,
    load_prompts,
    make_idea,
    pick_unseen,
)

ROOT = Path(__file__).parent.parent


def test_curated_content_is_valid() -> None:
    polls = load_polls(ROOT / "data/polls.yaml")
    prompts = load_prompts(ROOT / "data/prompts.yaml")
    ideas = load_ideas(ROOT / "data/ideas.yaml")
    assert len(polls) >= 30
    assert len(prompts) >= 60
    assert "Bonus:" in make_idea(ideas, "oc")


def test_pick_unseen_prefers_unused() -> None:
    polls = load_polls(ROOT / "data/polls.yaml")
    picked = pick_unseen(polls[:2], {polls[0].id})
    assert picked.id == polls[1].id


def test_invalid_poll_option_count_is_rejected(tmp_path: Path) -> None:
    path = tmp_path / "polls.yaml"
    path.write_text("- id: x\n  title: title\n  question: question\n  options: [one, two]\n", encoding="utf-8")
    with pytest.raises(ContentError):
        load_polls(path)
