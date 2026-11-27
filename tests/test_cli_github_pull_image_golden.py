"""Golden transcript: the images a pull request's rendered Markdown shows, through ``metab --api``.

``GET github/pull-image`` serves an image at the head of the comparison a pull request's
record names, without changing the served pin, and admits nothing else. This drives it
in-process, as ``tests/test_cli_github_pull_golden.py`` drives the rest of the pull
routes, and writes ``tests/golden/cli-github-pull-image.txt``: the pair the envelope's
``image_route`` names is admitted, which a text file at its head shows by being no image,
every refusal has its own code, ``<n>.snapshots.json`` keeps the pair a refresh replaced,
and that earlier pair is still admitted after the head moved. The fixture's commits hold
no image; ``tests/test_github_pull_snapshot.py`` serves one.
"""

from __future__ import annotations

import json
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
    operational_once,
    run_metab,
)
from tests.test_cli_github_pull_golden import PULL, ROUTE, _body, _Session
from tests.test_github_pulls import _answering_head  # pyright: ignore[reportPrivateUsage]

_LOGO = b"logo bytes\n"


def _wire(path: str) -> str:
    return GitPath.from_display(path).to_wire()


def _commit_with_logo(origin: Origin, tmp_path: Path) -> str:
    """A commit on pull request 7's head that adds ``logo.png``, now its head on the origin.

    Its identity and dates are fixed, so its ID is the same on every run.
    """

    env = {
        **git_env(tmp_path),
        "GIT_AUTHOR_NAME": "Forker",
        "GIT_AUTHOR_EMAIL": "forker@example.invalid",
        "GIT_AUTHOR_DATE": "1789000000 +0000",
        "GIT_COMMITTER_NAME": "Forker",
        "GIT_COMMITTER_EMAIL": "forker@example.invalid",
        "GIT_COMMITTER_DATE": "1789000000 +0000",
    }

    def git(*args: str, data: bytes = b"") -> str:
        result = subprocess.run(
            ["git", "--git-dir", str(origin.path), *args],
            input=data,
            capture_output=True,
            check=True,
            env=env,
        )
        return result.stdout.decode().strip()

    parent = origin["fork_head"]
    logo = git("hash-object", "-w", "--stdin", data=_LOGO)
    listing = git("ls-tree", parent) + f"\n100644 blob {logo}\tlogo.png\n"
    tree = git("mktree", data=listing.encode())
    head = git("commit-tree", tree, "-p", parent, data=b"add a logo\n")
    git("update-ref", "refs/pull/7/head", head)
    return head


def test_golden_images_open_only_from_an_admitted_pair(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, pull_origin: Origin
) -> None:
    session = _Session(tmp_path, monkeypatch, pull_origin)
    selected = f"{PULL}/7"
    acquired = session.run(selected, "--no-serve")
    assert acquired.exit_code == 0, acquired.stderr
    envelope = run_metab((selected, "--api", f"{ROUTE}?number=7")).payload()
    first = envelope["image_route"]
    assert first.startswith("/api/plugin/github/pull-image?number=7&")

    def image(route: str, query: str) -> str:
        result = session.run(selected, "--api", f"{route}&{query}")
        assert result.exit_code != 0, (query, result.stdout)
        return result.stdout

    app = f"path={_wire('src/app.txt')}"
    # The record's own pair is admitted: its head has the file, which is no image.
    assert '"code": "unsupported_image"' in image(first, app)
    # Each refusal says what it is.
    other = first.replace(f"left={envelope['record']['comparison']['base']}", "left=" + "0" * 40)
    assert '"code": "snapshot_expired"' in image(other, app)
    assert '"code": "invalid_image"' in image(first, "path=")
    assert '"code": "file_not_found"' in image(first, f"path={_wire('src/absent.png')}")
    assert '"code": "not_a_file"' in image(first, f"path={_wire('src')}")
    history = sorted((session.home / "sources").glob("*/pulls/7.snapshots.json"))
    assert len(history) == 1, history
    snapshots = history[0]
    session.blocks.append(f"# sources/<SLUG>/pulls/7.snapshots.json\n{snapshots.read_text()}\n\n")

    # The pull request gains a commit that adds an image, and a reader's refresh reads it.
    # Its bytes are a few of text, which the route serves by its name's type.
    head = _commit_with_logo(pull_origin, tmp_path)
    session.answer(_answering_head(SimpleNamespace(origin=pull_origin), head))  # pyright: ignore[reportArgumentType]
    refreshed = session.run(
        selected, "--api", f"{ROUTE}-refresh", "--data", _body(tmp_path, number=7, retry=True)
    )
    assert refreshed.exit_code == 0, refreshed.stderr
    later = run_metab((selected, "--api", f"{ROUTE}?number=7")).payload()["image_route"]
    assert later != first and f"right={head}" in later
    session.blocks.append(f"# sources/<SLUG>/pulls/7.snapshots.json\n{snapshots.read_text()}\n\n")
    served = session.run(selected, "--api", f"{later}&path={_wire('logo.png')}")
    assert served.exit_code == 0, served.stdout
    assert served.stdout.endswith(f"status: 200\n{_LOGO.decode()}\n"), served.stdout
    # The earlier pair is still admitted, and its head has no such image.
    assert '"code": "unsupported_image"' in image(first, app)
    assert '"code": "file_not_found"' in image(first, f"path={_wire('logo.png')}")

    labels = Labels()
    labels.origin(CANONICAL)
    rendered = normalize_pull_comparison_scopes(
        label_home(labels.apply("".join(session.blocks)), session.home)
    )
    assert str(tmp_path) not in rendered
    assert json.loads(snapshots.read_text())[0]["reader"] == "gh:octo-reader"
    check_golden("cli-github-pull-image.txt", operational_once(rendered))
