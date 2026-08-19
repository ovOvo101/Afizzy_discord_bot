from __future__ import annotations

import argparse
import shutil
from pathlib import Path

import yaml

from bot import admin

ROOT = Path(__file__).parent.parent


def prepare_project(tmp_path: Path, monkeypatch) -> Path:
    root = tmp_path / "project"
    (root / "config").mkdir(parents=True)
    shutil.copytree(ROOT / "data", root / "data", ignore=shutil.ignore_patterns("*.sqlite3"))
    shutil.copy(ROOT / "config/config.example.yaml", root / "config/config.yaml")
    monkeypatch.setattr(admin, "ROOT", root)
    monkeypatch.setattr(admin, "CONFIG_PATH", root / "config/config.yaml")
    monkeypatch.setattr(admin, "RUNTIME", root / "runtime")
    monkeypatch.setattr(admin, "PID_PATH", root / "runtime/bot.pid")
    monkeypatch.setattr(admin, "LOG_PATH", root / "runtime/bot.log")
    monkeypatch.setattr(admin, "BACKUPS", root / "runtime/backups")
    return root


def test_config_set_creates_backup_and_keeps_secrets_out(tmp_path: Path, monkeypatch) -> None:
    root = prepare_project(tmp_path, monkeypatch)
    result = admin.config_action(argparse.Namespace(action="set", path="scheduling.poll_time", value='"19:30"'))
    assert result["scheduling.poll_time"] == "19:30"
    assert result["restarted"] is False
    assert list((root / "runtime/backups").glob("config-*.yaml"))
    visible = admin.config_action(argparse.Namespace(action="list"))
    assert all("TOKEN" not in key for key in visible)


def test_config_rejects_required_unset(tmp_path: Path, monkeypatch) -> None:
    prepare_project(tmp_path, monkeypatch)
    try:
        admin.config_action(argparse.Namespace(action="unset", path="scheduling.poll_time"))
    except admin.AdminError as exc:
        assert "Required" in str(exc)
    else:
        raise AssertionError("required field was deleted")


def test_idea_content_crud_requires_delete_confirmation(tmp_path: Path, monkeypatch) -> None:
    root = prepare_project(tmp_path, monkeypatch)
    added = admin.content_action(argparse.Namespace(kind="idea-base", category="oc", action="add", id="base-oc-test", data='{"text":"Test idea."}'))
    assert added["action"] == "add"
    fetched = admin.content_action(argparse.Namespace(kind="idea-base", category="oc", action="get", id="base-oc-test"))
    assert fetched["text"] == "Test idea."
    preview = admin.content_action(argparse.Namespace(kind="idea-base", category="oc", action="preview-delete", id="base-oc-test"))
    assert preview["delete"]["id"] == "base-oc-test"
    try:
        admin.content_action(argparse.Namespace(kind="idea-base", category="oc", action="delete", id="base-oc-test", confirm=None))
    except admin.AdminError as exc:
        assert "requires" in str(exc)
    else:
        raise AssertionError("delete was not confirmed")
    deleted = admin.content_action(argparse.Namespace(kind="idea-base", category="oc", action="delete", id="base-oc-test", confirm="base-oc-test"))
    assert deleted["action"] == "delete"
    payload = yaml.safe_load((root / "data/ideas.yaml").read_text(encoding="utf-8"))
    assert all(item["id"] != "base-oc-test" for item in payload["base"]["oc"])


def test_status_cleans_stale_pid(tmp_path: Path, monkeypatch) -> None:
    prepare_project(tmp_path, monkeypatch)
    admin.RUNTIME.mkdir()
    admin.PID_PATH.write_text("999999", encoding="utf-8")
    assert admin.status()["running"] is False
    assert not admin.PID_PATH.exists()
