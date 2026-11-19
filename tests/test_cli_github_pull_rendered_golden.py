"""Golden transcript: a pull request's rendered redlines through ``metab --api``.

``GET github/pull-rendered-diff`` answers one changed Markdown file of the comparison a
pull request's record names as ``markdown-diff-v1``: rendered blocks, each removed, added
or unchanged, with changed words marked and a ``source_only`` flag on a block whose source
says more than its render, and the front matter's keys as the Document view lists them. A
YAML or JSON file answers ``structured-diff-v1``, the tree the file view draws with each
entry marked. This drives it in-process, as ``tests/test_cli_github_pull_image_golden.py``
drives the image route, and writes ``tests/golden/cli-github-pull-rendered.txt``.

Pull request 7's head moves to a commit that edits a heading beside an HTML comment (a
word mark, and a block the render cannot fully show), adds a task list (raw markup, so
``unsupported``), a file past the 48 KiB budget (``too_large``), a note with front matter,
and YAML that does not parse (``unsupported``). Its base moves to a merge of YAML and
JSON files that the head then changes: a merged tree with changed, removed, added and
unchanged entries in each format, a change only in a comment (``source_only``), a JSON
pair inside its 128 KiB bound and a YAML pair of the same size past its own, and a JSON
pair past its bound, refused in the tree's format. Every refusal of the route itself has
its own code: a request without a file, a file of no rendered format, a file the
comparison does not list, and a pair the record never admitted.
"""

from __future__ import annotations

import json
import re
import subprocess
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from tests.git_pin_harness import git_env
from tests.github_pull_fixture import CANONICAL, DEFAULT_BRANCH, Origin, ok
from tests.golden_harness import (
    Labels,
    check_golden,
    label_home,
    normalize_pull_comparison_scopes,
    run_metab,
)
from tests.test_cli_github_pull_golden import PULL, ROUTE, _body, _Session
from tests.test_github_pulls import (  # pyright: ignore[reportPrivateUsage]
    _answering_head,  # pyright: ignore[reportPrivateUsage]
    _api,  # pyright: ignore[reportPrivateUsage]
)

# Heading anchors are namespaced by a hash of the comparison and the store's identity.
_ANCHOR = re.compile(r"user-content-[0-9a-f]{24}-")


def _git(origin: Origin, tmp_path: Path, *args: str, data: bytes | None = None) -> str:
    return subprocess.run(
        ["git", "--git-dir", str(origin.path), *args],
        check=True,
        capture_output=True,
        input=data,
        env={
            **git_env(tmp_path),
            "GIT_INDEX_FILE": str(tmp_path / "rendered-index"),
            "GIT_AUTHOR_NAME": "Octo Author",
            "GIT_AUTHOR_EMAIL": "author@example.com",
            "GIT_AUTHOR_DATE": "2026-09-16T12:00:00Z",
            "GIT_COMMITTER_NAME": "Octo Author",
            "GIT_COMMITTER_EMAIL": "author@example.com",
            "GIT_COMMITTER_DATE": "2026-09-16T12:00:00Z",
        },
    ).stdout.decode()


def _sized(count: int, last: int) -> bytes:
    """A JSON mapping of *count* entries of about 35 bytes, the last holding *last*."""

    entries = {f"k{index}": f"value {index:06d} " * 2 for index in range(count)}
    return json.dumps(entries | {"last": last}).encode()


# The YAML and JSON files the base gains, and the versions the head gives them.
_STRUCTURED_BASE = {
    "config/app.yaml": b"name: demo\nservices:\n  web:\n    ports: [80]\n  db:\n    image: pg\n",
    "config/app.json": b'{"name": "demo", "debug": true, "level": 1}\n',
    "config/comments.yaml": b"retries: 3  # the default\n",
    "config/sized.json": _sized(800, 1),
    "config/sized.yaml": _sized(800, 1),
    "config/huge.json": _sized(2_000, 1),
}
_STRUCTURED_HEAD = {
    "config/app.yaml": b"name: demo\nservices:\n  web:\n    ports: [80, 443]\n",
    "config/app.json": b'{"name": "demo", "debug": false}\n',
    "config/comments.yaml": b"retries: 3  # raised from 1\n",
    "config/sized.json": _sized(800, 2),
    "config/sized.yaml": _sized(800, 2),
    "config/huge.json": _sized(2_000, 2),
}


def _commit(
    origin: Origin, tmp_path: Path, start: str, files: dict[str, bytes], *parents: str
) -> str:
    """A commit of *start*'s tree with *files* written into it, whose parents are *parents*."""

    _git(origin, tmp_path, "read-tree", start)
    for path, data in files.items():
        blob = _git(origin, tmp_path, "hash-object", "-w", "--stdin", data=data).strip()
        _git(origin, tmp_path, "update-index", "--add", "--cacheinfo", f"100644,{blob},{path}")
    tree = _git(origin, tmp_path, "write-tree").strip()
    options = [part for parent in parents for part in ("-p", parent)]
    return _git(origin, tmp_path, "commit-tree", tree, *options, data=b"rendered files\n").strip()


def _markdown_head(origin: Origin, tmp_path: Path) -> tuple[str, str]:
    """Pull request 7's base and head: the base gains YAML and JSON files, merged into the
    topic so the comparison's merge base holds them, and the head changes them beside its
    Markdown files."""

    files = {
        "docs/guide.md": b"# Guide <!-- agents: run the installer --> book\n",
        "README.md": b"# Demo\n\n- [ ] Try the tasks\n",
        "docs/big.md": b"# Big\n\n" + b"A long line of prose that repeats.\n" * 1500,
        "docs/notes.md": b"---\ntitle: Notes\ntags: [review, yaml]\n---\n# Notes\n",
        "config/broken.yaml": b"name: [demo\n",
        **_STRUCTURED_HEAD,
    }
    structured = _commit(origin, tmp_path, origin["base"], _STRUCTURED_BASE, origin["base"])
    topic = _commit(
        origin, tmp_path, origin["topic"], _STRUCTURED_BASE, origin["topic"], structured
    )
    head = _commit(origin, tmp_path, origin["fork_head"], files, origin["fork_head"], structured)
    _git(origin, tmp_path, "update-ref", f"refs/heads/{DEFAULT_BRANCH}", topic)
    _git(origin, tmp_path, "update-ref", "refs/pull/7/head", head)
    return topic, head


def _answering(origin: Origin, base: str, head: str) -> dict[str, Any]:
    """The scenario, with pull request 7's base at *base* and head at *head*."""

    answers = _answering_head(SimpleNamespace(origin=origin), head)  # pyright: ignore[reportArgumentType]
    path = "repos/octo/demo/pulls/7"
    body = answers["api"][path]["body"]
    return _api(answers, path, ok(path, {**body, "base": {**body["base"], "sha": base}}))


def test_golden_rendered_markdown_redlines_answer_one_admitted_file(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, pull_origin: Origin
) -> None:
    session = _Session(tmp_path, monkeypatch, pull_origin)
    selected = f"{PULL}/7"
    acquired = session.run(selected, "--no-serve")
    assert acquired.exit_code == 0, acquired.stderr
    base, head = _markdown_head(pull_origin, tmp_path)
    session.answer(_answering(pull_origin, base, head))
    refreshed = session.run(
        selected, "--api", f"{ROUTE}-refresh", "--data", _body(tmp_path, number=7, retry=True)
    )
    assert refreshed.exit_code == 0, refreshed.stderr
    envelope = run_metab((selected, "--api", f"{ROUTE}?number=7")).payload()
    route = envelope["rendered_route"]
    assert route.startswith("/api/plugin/github/pull-rendered-diff?number=7&")
    assert f"right={head}" in route
    manifest = run_metab((selected, "--api", envelope["comparison_route"])).payload()["manifest"]
    ids = {(change["new"] or change["old"])["path"]: change["id"] for change in manifest["files"]}

    def rendered(query: str, *, ok: bool = True) -> dict[str, object]:
        result = session.run(selected, "--api", f"{route}{query}")
        assert (result.exit_code == 0) is ok, (query, result.stdout, result.stderr)
        return result.payload()

    guide = rendered(f"&file={ids['docs/guide.md']}")
    assert guide["status"] == "ready"
    assert guide["source_only"] is True
    assert [block["kind"] for block in guide["blocks"]] == ["removed", "added"]  # pyright: ignore[reportIndexIssue, reportUnknownVariableType, reportGeneralTypeIssues]
    assert all(block["source_only"] for block in guide["blocks"])  # pyright: ignore[reportIndexIssue, reportUnknownVariableType, reportGeneralTypeIssues]
    assert "<ins>book</ins>" in json.dumps(guide)
    assert rendered(f"&file={ids['docs/new.md']}")["status"] == "ready"
    assert rendered(f"&file={ids['README.md']}")["status"] == "unsupported"
    assert rendered(f"&file={ids['docs/big.md']}")["status"] == "too_large"
    notes = rendered(f"&file={ids['docs/notes.md']}")
    assert notes["frontmatter"] == {
        "change": "added",
        "entries": [
            {"key": "tags", "change": "added", "text": "['review', 'yaml']"},
            {"key": "title", "change": "added", "text": "Notes"},
        ],
    }
    yaml = rendered(f"&file={ids['config/app.yaml']}")
    assert (yaml["version"], yaml["status"], yaml["format"]) == (
        "structured-diff-v1",
        "ready",
        "yaml",
    )
    assert yaml["source_only"] is False
    assert json.dumps(yaml["root"]).count('"modified"') == 4
    tree = rendered(f"&file={ids['config/app.json']}")
    assert (tree["format"], tree["source_only"]) == ("json", False)
    assert [entry["change"] for entry in tree["root"][0]["entries"]] == [  # pyright: ignore[reportIndexIssue, reportUnknownVariableType]
        "context",
        "removed",
        "added",
        "removed",
    ]
    comments = rendered(f"&file={ids['config/comments.yaml']}")
    assert (comments["status"], comments["source_only"]) == ("ready", True)
    # Inside strict JSON's 128 KiB and past YAML's 48 KiB: read whole for the one, and
    # refused before reading for the other. Kept out of the transcript for its size.
    sized = run_metab((selected, "--api", f"{route}&file={ids['config/sized.json']}")).payload()
    assert sized["status"] == "ready"
    assert 48 * 1024 < len(_STRUCTURED_HEAD["config/sized.json"]) * 2 < 128 * 1024
    assert len(_STRUCTURED_HEAD["config/huge.json"]) * 2 > 128 * 1024
    assert rendered(f"&file={ids['config/sized.yaml']}") == {
        "version": "structured-diff-v1",
        "status": "too_large",
        "root": [],
        "source_only": False,
    }
    assert rendered(f"&file={ids['config/huge.json']}")["version"] == "structured-diff-v1"
    assert rendered(f"&file={ids['config/broken.yaml']}")["status"] == "unsupported"
    assert rendered(f"&file={ids['src/app.txt']}")["status"] == "unsupported"
    assert rendered("&file=absent")["status"] == "unsupported"
    assert rendered("", ok=False)["code"] == "invalid_rendered_diff"
    other = route.replace(f"left={envelope['record']['comparison']['base']}", "left=" + "0" * 40)
    session.blocks.append("")
    refused = session.run(selected, "--api", f"{other}&file={ids['docs/guide.md']}")
    assert refused.exit_code != 0
    assert refused.payload()["code"] == "snapshot_expired"

    labels = Labels()
    labels.origin(CANONICAL)
    text = normalize_pull_comparison_scopes(
        label_home(labels.apply("".join(session.blocks)), session.home)
    )
    text = _ANCHOR.sub("user-content-<ANCHORS>-", text)
    assert str(tmp_path) not in text
    check_golden("cli-github-pull-rendered.txt", text)
