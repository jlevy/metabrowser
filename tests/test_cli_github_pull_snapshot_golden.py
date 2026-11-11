"""Golden transcript: a pull request's revision files through ``metab --api``.

``GET github/pull-snapshot`` opens a file at the base or the head of the comparison a
pull request's record names, without changing the served pin, and admits nothing else.
This drives it in-process, as ``tests/test_cli_github_pull_golden.py`` drives the rest of
the pull routes, and writes ``tests/golden/cli-github-pull-snapshot.txt``: the pair the
envelope's ``snapshot_route`` names opens on both sides, every refusal has its own code,
``<n>.snapshots.json`` keeps the pair a refresh replaced, and that earlier pair still
opens after the head moved. The page's two preference scripts are the shell's own and
are pinned by its goldens, so each is shown here by name.
"""

from __future__ import annotations

import json
import re
import subprocess
from pathlib import Path
from types import SimpleNamespace

import pytest

from metabrowser.git.tree_source import GitPath
from tests.git_pin_harness import git_env
from tests.github_pull_fixture import CANONICAL, Origin
from tests.golden_harness import (
    Labels,
    check_golden,
    label_home,
    normalize_pull_comparison_scopes,
    run_metab,
)
from tests.test_cli_github_pull_golden import PULL, ROUTE, _body, _Session
from tests.test_github_pulls import _answering_head  # pyright: ignore[reportPrivateUsage]

_SCRIPT = re.compile(r"<script>(.*?)</script>", re.DOTALL)


def _script_name(found: re.Match[str]) -> str:
    body = found.group(1)
    if "metabrowser.themeMode" in body:
        name = "the shell's theme script"
    elif "function normalize" in body:
        name = "the shell's document width script"
    else:
        name = "the document width default"
    return f"<script>[{name}]</script>"


def _wire(path: str) -> str:
    return GitPath.from_display(path).to_wire()


def test_golden_revision_files_open_only_from_an_admitted_pair(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, pull_origin: Origin
) -> None:
    session = _Session(tmp_path, monkeypatch, pull_origin)
    selected = f"{PULL}/7"
    acquired = session.run(selected, "--no-serve")
    assert acquired.exit_code == 0, acquired.stderr
    envelope = run_metab((selected, "--api", f"{ROUTE}?number=7")).payload()
    first = envelope["snapshot_route"]
    assert first.startswith("/api/plugin/github/pull-snapshot?number=7&")

    def snapshot(route: str, query: str, *, ok: bool = True) -> str:
        result = session.run(selected, "--api", f"{route}&{query}")
        assert (result.exit_code == 0) is ok, (query, result.stdout, result.stderr)
        return result.stdout

    app = _wire("src/app.txt")
    # Both sides of the record's own comparison open, as files and as a Source window.
    assert snapshot(first, f"side=head&path={app}&mode=download").endswith("one\ntwo\n\n")
    assert snapshot(first, f"side=base&path={app}&mode=download").endswith("one\n\n")
    assert "<pre><code>one\ntwo\n</code></pre>" in snapshot(
        first, f"side=head&path={app}&mode=source"
    )
    # Each refusal says what it is, as JSON for an image request.
    other = first.replace(f"left={envelope['record']['comparison']['base']}", "left=" + "0" * 40)
    snapshot(other, f"side=head&path={app}&mode=image", ok=False)
    snapshot(first, f"side=middle&path={app}&mode=image", ok=False)
    snapshot(first, f"side=head&path={_wire('src/absent.txt')}&mode=image", ok=False)
    snapshot(first, f"side=head&path={_wire('src')}&mode=image", ok=False)
    snapshot(first, f"side=head&path={_wire('README.md')}&mode=image", ok=False)
    snapshot(first, f"side=head&path={app}&mode=source&offset=99", ok=False)
    history = sorted((session.home / "sources").glob("*/pulls/7.snapshots.json"))
    assert len(history) == 1, history
    snapshots = history[0]
    session.blocks.append(f"# sources/<SLUG>/pulls/7.snapshots.json\n{snapshots.read_text()}\n\n")

    # The pull request's head moves on GitHub; a reader's refresh reads it.
    earlier = pull_origin["fork_earlier"]
    subprocess.run(
        ["git", "--git-dir", str(pull_origin.path), "update-ref", "refs/pull/7/head", earlier],
        check=True,
        capture_output=True,
        env=git_env(tmp_path),
    )
    session.answer(_answering_head(SimpleNamespace(origin=pull_origin), earlier))  # pyright: ignore[reportArgumentType]
    refreshed = session.run(
        selected, "--api", f"{ROUTE}-refresh", "--data", _body(tmp_path, number=7, retry=True)
    )
    assert refreshed.exit_code == 0, refreshed.stderr
    later = run_metab((selected, "--api", f"{ROUTE}?number=7")).payload()["snapshot_route"]
    assert later != first
    session.blocks.append(f"# sources/<SLUG>/pulls/7.snapshots.json\n{snapshots.read_text()}\n\n")
    # The earlier pair still opens, and so does the new one.
    assert snapshot(first, f"side=head&path={app}&mode=download").endswith("one\ntwo\n\n")
    assert snapshot(later, f"side=head&path={app}&mode=download").endswith("one\nextra\n\n")

    labels = Labels()
    labels.origin(CANONICAL)
    rendered = normalize_pull_comparison_scopes(
        label_home(labels.apply("".join(session.blocks)), session.home)
    )
    rendered = _SCRIPT.sub(_script_name, rendered)
    assert str(tmp_path) not in rendered
    assert json.loads(snapshots.read_text())[0]["reader"] == "gh:octo-reader"
    check_golden("cli-github-pull-snapshot.txt", rendered)
