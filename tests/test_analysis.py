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
            alert_after_attempts=3,
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
        {"total_items": 0, "priority_counts": {}, "top_category_counts": {}},
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
    request_payload = json.loads(body["messages"][1]["content"][-1]["text"])
    assert "historical_analysis_summary" in request_payload
    assert "historical_analysis" not in request_payload
    assert body["response_format"]["type"] == "json_schema"
    assert "input" not in body
    assert "text" not in body
    database.close()


def test_history_is_reduced_to_bounded_summary(tmp_path: Path) -> None:
    database = Database(tmp_path / "bot.sqlite3")
    database.initialize()
    now = datetime.now(UTC).isoformat()
    database.connection.executemany(
        """
        INSERT INTO feedback_analysis_items(
          run_id, item_index, payload, feishu_record_id, created_at
        ) VALUES (1, ?, ?, ?, ?)
        """,
        [
            (0, json.dumps({"category": "搜索", "priority": "🔴 P1"}), "rec1", now),
            (1, json.dumps({"category": "搜索", "priority": "🟡 P2"}), "rec2", now),
            (2, json.dumps({"category": "聊天", "priority": "🟡 P2"}), None, now),
        ],
    )
    database.connection.commit()

    summary = database.analysis_history_summary()

    assert summary == {
        "total_items": 2,
        "priority_counts": {"🟡 P2": 1, "🔴 P1": 1},
        "top_category_counts": {"搜索": 2},
    }
    database.close()


async def test_failure_alert_is_sent_once_after_threshold(
    tmp_path: Path, monkeypatch: object
) -> None:
    database = Database(tmp_path / "bot.sqlite3")
    database.initialize()
    run = database.claim_analysis_run("2026-09-04")
    assert run is not None
    now = datetime.now(UTC)
    for _ in range(3):
        database.defer_analysis_run(run["id"], "upstream unavailable", now)
    monkeypatch.setenv("FEISHU_ALERT_WEBHOOK_URL", "https://example.com/webhook")  # type: ignore[attr-defined]
    configured = _settings()
    analyzer = FeedbackAnalyzer(SimpleNamespace(), configured, database)  # type: ignore[arg-type]
    analyzer._send_failure_webhook = AsyncMock()  # type: ignore[method-assign]

    await analyzer._alert_failure(run["id"], RuntimeError("upstream unavailable"))
    await analyzer._alert_failure(run["id"], RuntimeError("upstream unavailable"))

    analyzer._send_failure_webhook.assert_awaited_once()  # type: ignore[union-attr]
    assert database.analysis_run(run["id"])["failure_alerted"] == 1
    database.close()


async def test_missing_alert_webhook_does_not_interrupt_retry(
    tmp_path: Path, monkeypatch: object
) -> None:
    monkeypatch.delenv("FEISHU_ALERT_WEBHOOK_URL", raising=False)  # type: ignore[attr-defined]
    database = Database(tmp_path / "bot.sqlite3")
    database.initialize()
    run = database.claim_analysis_run("2026-09-05")
    assert run is not None
    for _ in range(3):
        database.defer_analysis_run(run["id"], "upstream unavailable", datetime.now(UTC))
    analyzer = FeedbackAnalyzer(SimpleNamespace(), _settings(), database)  # type: ignore[arg-type]
    analyzer._send_failure_webhook = AsyncMock()  # type: ignore[method-assign]

    await analyzer._alert_failure(run["id"], RuntimeError("upstream unavailable"))

    analyzer._send_failure_webhook.assert_not_awaited()  # type: ignore[union-attr]
    assert database.analysis_run(run["id"])["failure_alerted"] == 0
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
