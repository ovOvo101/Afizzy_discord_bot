from datetime import UTC, datetime
import json
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock

from bot.analysis import FeedbackAnalyzer
from bot.database import Database


FIELDS = {
    "number": "ID",
    "dates": "Date",
    "category": "Category",
    "user_feedback": "User Feedback",
    "suggested_solution": "Suggested Solution",
    "users": "User",
    "priority": "Priority",
    "review_status": "审核状态",
    "possible_duplicate": "疑似重复目标",
    "duplicate_reason": "重复判断说明",
    "source_message_ids": "来源消息ID",
    "source_message_links": "来源消息链接",
    "source_channel_ids": "来源频道ID",
}


def _settings() -> SimpleNamespace:
    return SimpleNamespace(
        feedback=SimpleNamespace(request_timeout_seconds=15),
        feedback_analysis=SimpleNamespace(
            api_url="https://api.siliconflow.cn/v1/chat/completions",
            request_timeout_seconds=120,
            max_images_per_batch=0,
            schedule_time="10:00",
            app_token="bas1",
            table_id="tbl1",
            fields=FIELDS,
        ),
        schedule=SimpleNamespace(timezone=UTC),
    )


def _archived_feedback(database: Database, message_id: int = 100) -> None:
    database.claim_feedback(
        message_id,
        1,
        10,
        "alice",
        datetime(2026, 8, 31, tzinfo=UTC),
        "search is missing",
        f"https://discord.com/channels/1/10/{message_id}",
    )
    database.save_feedback_translation(message_id, "EN", "缺少搜索")
    database.mark_feedback_delivered(message_id, "raw-record")
    database.mark_feedback_acknowledged(message_id)


def test_analysis_run_claims_each_message_once(tmp_path: Path) -> None:
    database = Database(tmp_path / "bot.sqlite3")
    database.initialize()
    _archived_feedback(database)

    first = database.claim_analysis_run("2026-09-01")
    second = database.claim_analysis_run("2026-09-01")

    assert first is not None
    assert second is None
    assert [row["message_id"] for row in database.analysis_messages(first["id"])] == [100]
    database.close()


def test_siliconflow_chat_completions_request_format(
    tmp_path: Path, monkeypatch: object
) -> None:
    monkeypatch.setenv("SILICONFLOW_MODEL", "Qwen/test-vl")  # type: ignore[attr-defined]
    database = Database(tmp_path / "bot.sqlite3")
    database.initialize()
    analyzer = FeedbackAnalyzer(SimpleNamespace(), _settings(), database)  # type: ignore[arg-type]
    body = analyzer._request_body(
        [],
        [{"message_id": "100", "original": "hello"}],
        [{"type": "image_url", "image_url": {"url": "https://example.com/a.png"}}],
    )

    assert body["model"] == "Qwen/test-vl"
    assert body["messages"][0]["role"] == "system"
    system_prompt = body["messages"][0]["content"]
    assert "默认使用简体中文" in system_prompt
    assert "例如 fizz" in system_prompt
    assert body["messages"][1]["content"][0]["type"] == "image_url"
    assert body["messages"][1]["content"][-1]["type"] == "text"
    assert body["response_format"]["type"] == "json_schema"
    assert "input" not in body
    assert "text" not in body
    database.close()


async def test_analysis_is_saved_before_feishu_write(
    tmp_path: Path, monkeypatch: object
) -> None:
    monkeypatch.setenv("SILICONFLOW_MODEL", "test-model")  # type: ignore[attr-defined]
    database = Database(tmp_path / "bot.sqlite3")
    database.initialize()
    _archived_feedback(database)
    run = database.claim_analysis_run("2026-09-01")
    assert run is not None
    analyzer = FeedbackAnalyzer(SimpleNamespace(), _settings(), database)  # type: ignore[arg-type]
    item = {
        "dates": "2026/8/31",
        "category": "Search",
        "user_feedback": "用户无法搜索角色。",
        "suggested_solution": "增加角色搜索入口。",
        "users": "alice",
        "priority": "🔴 P0",
        "possible_duplicate": "",
        "duplicate_reason": "",
        "source_message_ids": ["100"],
    }
    analyzer._analyze = AsyncMock(  # type: ignore[method-assign]
        return_value=({"items": [item]}, json.dumps({"items": [item]}))
    )
    analyzer.api.create_bitable_record = AsyncMock(return_value="analysis-record")  # type: ignore[method-assign]

    await analyzer._process_run(run)

    stored_run = database.connection.execute(
        "SELECT * FROM feedback_analysis_runs WHERE id = ?", (run["id"],)
    ).fetchone()
    stored_item = database.connection.execute(
        "SELECT * FROM feedback_analysis_items WHERE run_id = ?", (run["id"],)
    ).fetchone()
    assert stored_run["status"] == "completed"
    assert stored_run["openai_response"]
    assert stored_item["feishu_record_id"] == "analysis-record"
    fields = analyzer.api.create_bitable_record.await_args.args[2]  # type: ignore[union-attr]
    assert fields["审核状态"] == "待审核"
    assert fields["来源消息ID"] == "100"
    database.close()
