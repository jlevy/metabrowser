"""A missing Node or Git fails a test, and the macOS tier cannot pass by skipping."""

from __future__ import annotations

import re
from collections.abc import Callable
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest
from conftest import REQUIRE_MACOS_TIER_ENV, fail_a_required_macos_tier_skip

from tests.required_tools import ALLOW_MISSING_TOOLS_ENV, require_git, require_node

TESTS = Path(__file__).resolve().parent
TOOLS: list[tuple[Callable[[], str], str]] = [(require_node, "node"), (require_git, "git")]


@pytest.fixture
def empty_path(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.setenv("PATH", str(tmp_path))
    monkeypatch.delenv(ALLOW_MISSING_TOOLS_ENV, raising=False)
    return tmp_path


@pytest.mark.parametrize(("require", "tool"), TOOLS)
def test_a_missing_tool_fails_and_names_the_opt_out(
    empty_path: Path, require: Callable[[], str], tool: str
) -> None:
    with pytest.raises(pytest.fail.Exception, match=f"{ALLOW_MISSING_TOOLS_ENV}={tool} to skip"):
        require()


@pytest.mark.parametrize(("require", "tool"), TOOLS)
def test_a_missing_tool_skips_only_when_it_is_the_one_allowed(
    empty_path: Path, monkeypatch: pytest.MonkeyPatch, require: Callable[[], str], tool: str
) -> None:
    other = "git" if tool == "node" else "node"
    monkeypatch.setenv(ALLOW_MISSING_TOOLS_ENV, other)
    with pytest.raises(pytest.fail.Exception):
        require()
    monkeypatch.setenv(ALLOW_MISSING_TOOLS_ENV, f"{other}, {tool}")
    with pytest.raises(pytest.skip.Exception, match=f"{tool} is not on PATH"):
        require()


@pytest.mark.parametrize(("require", "tool"), TOOLS)
def test_a_tool_on_path_is_returned_even_where_missing_is_allowed(
    empty_path: Path, monkeypatch: pytest.MonkeyPatch, require: Callable[[], str], tool: str
) -> None:
    executable = empty_path / tool
    executable.write_text("#!/bin/sh\n", encoding="utf-8")
    executable.chmod(0o755)
    monkeypatch.setenv(ALLOW_MISSING_TOOLS_ENV, tool)
    assert require() == str(executable)


def test_no_test_module_looks_node_or_git_up_itself() -> None:
    """A private lookup is how a skip comes back: every module asks the gate."""

    lookup = re.compile(r"""which\(\s*["'](?:node|git)["']""")
    offenders = sorted(
        path.name
        for path in TESTS.glob("*.py")
        if path.name != "required_tools.py" and lookup.search(path.read_text(encoding="utf-8"))
    )
    assert offenders == []


def _skipped_macos_tier_test(*, marked: bool = True) -> tuple[Any, Any]:
    item = SimpleNamespace(get_closest_marker=lambda name: object() if marked else None)
    report = SimpleNamespace(
        skipped=True, outcome="skipped", longrepr=("tests/test_x.py", 1, "Skipped: needs macOS")
    )
    return item, report


def test_a_required_macos_tier_turns_its_skip_into_a_failure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv(REQUIRE_MACOS_TIER_ENV, "1")
    item, report = _skipped_macos_tier_test()
    fail_a_required_macos_tier_skip(item, report)
    assert report.outcome == "failed"
    assert report.longrepr == (
        f"{REQUIRE_MACOS_TIER_ENV}=1, so a macOS-tier test may not skip. Skipped: needs macOS"
    )


def test_a_skip_stays_a_skip_outside_the_required_macos_tier(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv(REQUIRE_MACOS_TIER_ENV, "1")
    item, report = _skipped_macos_tier_test(marked=False)
    fail_a_required_macos_tier_skip(item, report)
    assert report.outcome == "skipped"

    monkeypatch.delenv(REQUIRE_MACOS_TIER_ENV)
    item, report = _skipped_macos_tier_test()
    fail_a_required_macos_tier_skip(item, report)
    assert report.outcome == "skipped"
