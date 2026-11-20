"""Which agent homes a folder holds, from a few ``stat`` calls."""

from __future__ import annotations

from pathlib import Path

from metabrowser.builtin_plugins.agents.homes import (
    MAX_HOME_ENTRIES,
    holds_homes,
    home_of,
    homes_in,
    is_claude_home,
    is_codex_home,
)
from tests import agents_synthetic_home as syn


def _agents(folder: Path) -> list[tuple[str, str]]:
    return [(h.agent, h.path.relative_to(folder).as_posix()) for h in homes_in(folder)]


def test_a_claude_home_is_projects_plus_a_marker(tmp_path: Path) -> None:
    homes = syn.build(tmp_path)
    assert is_claude_home(homes.claude.path)
    assert not is_codex_home(homes.claude.path)  # its sessions/ holds pid files, not rollouts
    (tmp_path / "bare" / "projects").mkdir(parents=True)
    assert not is_claude_home(tmp_path / "bare")  # a projects/ folder alone is nobody's home


def test_a_codex_home_is_a_state_store_or_sessions_with_a_marker(tmp_path: Path) -> None:
    homes = syn.build(tmp_path)
    assert is_codex_home(homes.codex.path)
    assert not is_claude_home(homes.codex.path)
    store_only = tmp_path / "store-only"
    store_only.mkdir()
    (store_only / "state_7.sqlite").write_bytes(b"")
    assert is_codex_home(store_only)
    sessions_only = tmp_path / "sessions-only"
    (sessions_only / "sessions").mkdir(parents=True)
    assert not is_codex_home(sessions_only)  # `sessions/` is a common folder name
    (sessions_only / "config.toml").write_text("", encoding="utf-8")
    assert is_codex_home(sessions_only)


def test_a_folder_holds_the_homes_it_contains_directly(tmp_path: Path) -> None:
    syn.build(tmp_path)
    assert _agents(tmp_path) == [("claude", ".claude"), ("codex", ".codex")]
    assert _agents(tmp_path / ".claude") == [("claude", ".")]
    assert holds_homes(tmp_path)
    assert holds_homes(tmp_path / ".codex")


def test_a_projects_own_dot_claude_is_not_a_home(tmp_path: Path) -> None:
    (tmp_path / ".claude" / "commands").mkdir(parents=True)
    (tmp_path / ".claude" / "settings.json").write_text("{}", encoding="utf-8")
    assert homes_in(tmp_path) == ()
    assert not holds_homes(tmp_path)


def test_an_absent_or_unreadable_folder_holds_nothing(tmp_path: Path) -> None:
    assert homes_in(tmp_path / "missing") == ()
    assert not holds_homes(tmp_path)


def test_a_huge_folder_is_not_scanned_past_its_bound(tmp_path: Path) -> None:
    assert MAX_HOME_ENTRIES >= 1000
    crowded = tmp_path / "crowded"
    crowded.mkdir()
    for number in range(30):
        (crowded / f"f{number}").write_text("", encoding="utf-8")
    assert not is_codex_home(crowded)


def test_home_of_finds_the_home_above_a_transcript(tmp_path: Path) -> None:
    homes = syn.build(tmp_path)
    transcript = homes.claude.path / "projects" / "-work-alpha" / f"{syn.S1}.jsonl"
    found = home_of(transcript, tmp_path)
    assert found is not None
    assert (found.agent, found.path) == ("claude", homes.claude.path)
    assert home_of(tmp_path / "elsewhere" / "x.jsonl", tmp_path) is None
