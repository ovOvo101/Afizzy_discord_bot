from pathlib import Path

import pytest

from bot.content import (
    ContentError,
    PollItem,
    load_polls,
    pick_unseen,
)

def test_pick_unseen_prefers_unused() -> None:
    polls = [
        PollItem("used", "Used", "Question?", ("a", "b", "c")),
        PollItem("unused", "Unused", "Question?", ("a", "b", "c")),
    ]
    picked = pick_unseen(polls, {"used"})
    assert picked.id == "unused"


def test_invalid_poll_option_count_is_rejected(tmp_path: Path) -> None:
    path = tmp_path / "polls.yaml"
    path.write_text("- id: x\n  title: title\n  question: question\n  options: [one, two]\n", encoding="utf-8")
    with pytest.raises(ContentError):
        load_polls(path)
