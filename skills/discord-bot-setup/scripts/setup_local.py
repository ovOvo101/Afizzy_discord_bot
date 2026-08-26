#!/usr/bin/env python3
"""Prepare a local checkout without reading or emitting Discord secrets."""
from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
from pathlib import Path


def token_configured(path: Path) -> bool:
    """Return only whether a non-placeholder token exists; never return its value."""
    if not path.exists():
        return False
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        if line.strip().startswith("DISCORD_TOKEN="):
            value = line.split("=", 1)[1].strip().strip('"').strip("'")
            return bool(value and value != "replace-me")
    return False


def run(command: list[str], root: Path) -> tuple[bool, str]:
    result = subprocess.run(command, cwd=root, capture_output=True, text=True, check=False)
    message = (result.stderr or result.stdout).strip()
    return result.returncode == 0, message[-1000:]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project-root", default=".", help="Path to the Bot project root.")
    parser.add_argument("--skip-install", action="store_true", help="Do not create a venv or install packages.")
    args = parser.parse_args()

    root = Path(args.project_root).expanduser().resolve()
    required = (root / "pyproject.toml", root / "bot", root / "config/config.example.yaml", root / ".env.example")
    if not all(path.exists() for path in required):
        print(json.dumps({"ready": False, "error": "This is not a Discord Bot project root."}, ensure_ascii=False))
        return 2

    env_path, config_path = root / ".env", root / "config/config.yaml"
    venv_python = root / ".venv/bin/python"
    changes: list[str] = []
    install_error = ""

    if not env_path.exists():
        shutil.copy2(root / ".env.example", env_path)
        changes.append("created .env from .env.example")
    if not config_path.exists():
        shutil.copy2(root / "config/config.example.yaml", config_path)
        changes.append("created config/config.yaml from config example")

    if not args.skip_install:
        if not venv_python.exists():
            ok, error = run([sys.executable, "-m", "venv", ".venv"], root)
            if ok:
                changes.append("created .venv")
            else:
                install_error = error or "Could not create .venv"
        if not install_error:
            ok, error = run([str(venv_python), "-m", "pip", "install", "-e", ".[dev]"], root)
            if ok:
                changes.append("installed project dependencies")
            else:
                install_error = error or "Could not install dependencies"

    validation_error = ""
    if venv_python.exists() and not install_error:
        ok, error = run([str(venv_python), "-c", "from bot.admin import validate_project; validate_project()"], root)
        if not ok:
            validation_error = error or "Configuration or content validation failed"

    result = {
        "project_root": str(root),
        "venv_ready": venv_python.exists(),
        "token_configured": token_configured(env_path),
        "config_exists": config_path.exists(),
        "configuration_valid": bool(venv_python.exists() and not install_error and not validation_error),
        "changes": changes,
        "install_error": install_error or None,
        "validation_error": validation_error or None,
    }
    result["ready_to_start"] = bool(
        result["venv_ready"] and result["token_configured"] and result["configuration_valid"]
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if not install_error and not validation_error else 1


if __name__ == "__main__":
    raise SystemExit(main())
