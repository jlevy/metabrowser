"""KPress is MetaBrowser's required, released rendering dependency."""

from __future__ import annotations

import tomllib
from pathlib import Path

PROJECT_FILE = Path(__file__).resolve().parent.parent / "pyproject.toml"
SOURCE_DIR = PROJECT_FILE.parent / "src" / "metabrowser"


def test_kpress_is_an_exact_required_runtime_dependency() -> None:
    project = tomllib.loads(PROJECT_FILE.read_text(encoding="utf-8"))

    assert "kpress==0.1.0" in project["project"]["dependencies"]
    assert "kpress" not in project["project"].get("optional-dependencies", {})
    assert "kpress" not in project.get("dependency-groups", {}).get("dev", [])


def test_kpress_does_not_resolve_from_the_monorepo_workspace() -> None:
    project = tomllib.loads(PROJECT_FILE.read_text(encoding="utf-8"))

    assert "kpress" not in project.get("tool", {}).get("uv", {}).get("sources", {})


def test_runtime_has_no_optional_kpress_branch() -> None:
    adapter = (SOURCE_DIR / "kpress_adapter.py").read_text(encoding="utf-8")
    server = (SOURCE_DIR / "server.py").read_text(encoding="utf-8")

    assert "KPressUnavailableError" not in adapter
    assert "KPressUnavailableError" not in server
    assert "kpress_unavailable" not in server
