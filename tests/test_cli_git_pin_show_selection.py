"""``--show`` on a Git pin reads its selection as a display name.

A pinned tree may hold a file literally named ``g1-notes.md`` or a directory
named ``g1-data``, because ``g1-`` is Metabrowser's wire prefix and nothing
reserves it in Git. A selection a human typed at the shell is a display name,
so it must resolve to that tracked path rather than being base64-decoded into
an unrelated one. ``/view/`` addresses stay wire identities, which is what
keeps a tracked file from capturing a route.

The CLI runs in process with ``require_acquisition_git`` patched, the same
boundary ``tests/test_cli_git_pin_golden.py`` uses, because the CI runner's Git
is below the acquisition floor.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
from pathlib import Path
from typing import Any

import pytest
from typer.testing import CliRunner

from metabrowser.cli.main import _app
from metabrowser.git.process import _REPO_PINNING_GIT_VARS
from metabrowser.git.tree_source import GitPath
from tests.test_cli_cache_acquire_golden import _allow_installed_git, _file_url

posix_only = pytest.mark.skipif(os.name != "posix", reason="owner-only cache is POSIX-only")

pytestmark = pytest.mark.skipif(shutil.which("git") is None, reason="git executable is required")

runner = CliRunner()


def _git(root: Path, *args: str) -> None:
    env = {key: value for key, value in os.environ.items() if key not in _REPO_PINNING_GIT_VARS}
    env.update(
        {
            "GIT_AUTHOR_NAME": "Fixture Author",
            "GIT_AUTHOR_EMAIL": "author@example.invalid",
            "GIT_COMMITTER_NAME": "Fixture Author",
            "GIT_COMMITTER_EMAIL": "author@example.invalid",
            "GIT_CONFIG_GLOBAL": os.devnull,
            "GIT_CONFIG_NOSYSTEM": "1",
        }
    )
    subprocess.run(["git", "-C", str(root), *args], check=True, capture_output=True, env=env)


@pytest.fixture
def wire_shaped_origin(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> str:
    """A ``file://`` origin whose tracked names collide with the wire prefix."""

    monkeypatch.setenv("METABROWSER_HOME", str(tmp_path / "home"))
    monkeypatch.setenv("METABROWSER_LOG_LEVEL", "ERROR")
    monkeypatch.setenv("METABROWSER_PLUGINS_DIRS", "")
    monkeypatch.setenv("TERM", "dumb")
    _allow_installed_git(monkeypatch)

    work = tmp_path / "work"
    work.mkdir()
    _git(work, "init", "-q", "-b", "main")
    (work / "g1-notes.md").write_text("notes\n", encoding="utf-8")
    (work / "plain.md").write_text("plain\n", encoding="utf-8")
    (work / "g1-tools").mkdir()
    (work / "g1-tools" / "x.md").write_text("tool\n", encoding="utf-8")
    # Four base64url characters decode cleanly, so this one silently became a
    # different path rather than failing loudly.
    (work / "g1-data").mkdir()
    (work / "g1-data" / "x.md").write_text("data\n", encoding="utf-8")
    _git(work, "add", "-A")
    _git(work, "commit", "-qm", "first")
    return _file_url(work)


def _show(url: str, selection: str) -> dict[str, Any]:
    result = runner.invoke(_app, [url, "--show", selection, "--format", "json"])
    assert result.exit_code == 0, result.output
    return json.loads(result.stdout)


@posix_only
@pytest.mark.parametrize(
    "selection",
    ["plain.md", "g1-notes.md", "g1-tools/x.md", "g1-data/x.md", "g1-data"],
)
def test_show_resolves_a_tracked_display_name(wire_shaped_origin: str, selection: str) -> None:
    """Every tracked name resolves to itself, wire-shaped or not."""

    shown = _show(wire_shaped_origin, selection)
    assert shown["show"] == selection
    expected = GitPath.from_segments(
        *(part.encode("utf-8") for part in selection.split("/"))
    ).to_wire()
    assert shown["route"] == f"/view/{expected}"


@posix_only
def test_show_accepts_the_wire_identity_a_route_carries(wire_shaped_origin: str) -> None:
    """A ``/view/`` address stays a wire identity; a lookalike file cannot capture it."""

    wire = GitPath.from_segments(b"g1-notes.md").to_wire()
    shown = _show(wire_shaped_origin, f"/view/{wire}")
    assert shown["route"] == f"/view/{wire}"
    assert shown["kind"] == "markdown"


@posix_only
def test_show_falls_back_to_the_wire_reading_for_an_untracked_name(
    wire_shaped_origin: str,
) -> None:
    """A bare wire token with no matching display name still resolves."""

    wire = GitPath.from_segments(b"plain.md").to_wire()
    shown = _show(wire_shaped_origin, wire)
    assert shown["route"] == f"/view/{wire}"
    assert shown["kind"] == "markdown"


@posix_only
def test_show_reports_a_selection_the_pin_does_not_hold(wire_shaped_origin: str) -> None:
    """A name that is neither tracked nor a resolvable identity fails, not 200s."""

    result = runner.invoke(_app, [wire_shaped_origin, "--show", "g1-absent.md"])
    assert result.exit_code != 0
    assert "g1-absent.md is not a selection the browser can open" in str(result.exception)
