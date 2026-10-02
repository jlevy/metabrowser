"""Golden transcript: refreshing a ``file://`` mirror and switching its pin, in-process.

A refresh runs ``git fetch``, which the acquisition floor refuses on a Git below it, so
this runs the production CLI in-process with only the floor and the clock replaced -- the
boundary ``tests/test_cli_git_pin_golden.py`` uses -- and stays a ``.txt`` transcript.
Every command is its own ``metab`` invocation, so what one command changes reaches the
next only through the store, exactly as for a user running them one after another.
Nothing binds a port.

The origin is ``tests/source_mirror_fixture.py``'s, written with ``git fast-import`` so
every commit ID is the same on every machine. Between the first status and the refresh,
the origin moves the way a busy upstream does:

- ``topic`` is force-pushed: ``second`` is dropped and ``rewritten`` replaces it;
- ``feature`` is deleted;
- ``v2`` tags ``rewritten``.

The transcript then shows the refresh starting and, once it has ended, the status after
it; the next command pinning the new default revision; a page's own request for a
missing commit's fetch starting nothing on the mirror just fetched, and a retry fetching
all the same; the force-pushed-away commit and
the deleted branch's commit still readable by ID; the deleted branch gone by name; and a
refresh against a removed origin recorded as ``origin_unavailable``, which exits 1 while
the mirror keeps serving. The clock is fixed and the session moves it before each fetch,
so the transcript shows which command set ``last_fetch_at`` and which left it alone.
"""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
from pathlib import Path
from typing import Any

import pytest

from tests.golden_harness import (
    Invocation,
    Labels,
    check_golden,
    file_url,
    isolate_cli,
    label_home,
    ok,
    pinned_git_env,
    refused,
)
from tests.required_tools import needs_git
from tests.source_mirror_fixture import build_origin

posix_only = pytest.mark.skipif(os.name != "posix", reason="owner-only cache is POSIX-only")

pytestmark = needs_git

FIRST = "fcb9d63c3c8533d1b929861f451a066e6d4f2d9e"
SECOND = "42382ea2303b733e1e21b4bd6ddb974ca4e775eb"
FEATURE = "c7ae2a331f546e6a2431ed7093e9e430a9d1269b"


def _move_origin(origin: Path) -> str:
    """Force-push ``topic``, delete ``feature``, and tag the rewrite; return its commit."""

    stream = (
        b"reset refs/heads/topic\n"
        b"commit refs/heads/topic\nmark :1\n"
        b"committer Mirror <mirror@example.invalid> 1767240000 +0000\n"
        b"data 10\nrewritten\n\n"
        b"from " + FIRST.encode() + b"\n"
        b"M 100644 inline REWRITTEN.md\ndata 22\nReplaces the second.\n\n"
        b"reset refs/tags/v2\nfrom :1\n\n"
        b"done\n"
    )
    env = pinned_git_env()
    subprocess.run(
        ["git", "--git-dir", str(origin), "fast-import", "--quiet", "--done", "--force"],
        check=True,
        capture_output=True,
        input=stream,
        env=env,
    )
    subprocess.run(
        ["git", "--git-dir", str(origin), "update-ref", "-d", "refs/heads/feature"],
        check=True,
        env=env,
    )
    return subprocess.run(
        ["git", "--git-dir", str(origin), "rev-parse", "--verify", "refs/heads/topic"],
        check=True,
        capture_output=True,
        text=True,
        env=env,
    ).stdout.strip()


def _body(directory: Path, name: str, body: dict[str, Any]) -> str:
    path = directory / name
    path.write_text(json.dumps(body) + "\n", encoding="utf-8")
    return str(path)


def _sections(stdout: str) -> list[tuple[str, Any]]:
    """Each ``api:`` or ``after:`` header with the envelope that follows it."""

    sections: list[tuple[str, Any]] = []
    for chunk in re.split(r"(?m)^(?=(?:api|after): )", stdout):
        if not chunk.strip():
            continue
        start = chunk.index("{")
        sections.append((chunk[:start], json.loads(chunk[start:])))
    return sections


def _payload(result: Invocation) -> Any:
    return _sections(result.stdout)[0][1]


def _after(result: Invocation) -> Any:
    return _sections(result.stdout)[1][1]


@posix_only
def test_golden_refresh_and_pin_switching(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    sandbox = isolate_cli(tmp_path, monkeypatch)
    clock = sandbox.clock
    origin = build_origin(tmp_path)
    url = file_url(origin)
    bodies = tmp_path / "bodies"
    bodies.mkdir()
    refresh = _body(bodies, "refresh.json", {})

    blocks: list[str] = []

    def api(route: str, *, data: str | None = None, refuse: bool = False) -> Invocation:
        args = [url, "--api", route] + (["--data", data] if data else [])
        result = refused(args) if refuse else ok(args)
        shown = f"file://<ORIGIN> --api {route}" + (f" --data {Path(data).name}" if data else "")
        blocks.append(result.block(shown))
        return result

    before = _payload(api("/api/source/status"))
    assert before["pin"] == SECOND
    assert before["last_outcome"]["operation"] == "acquire"
    assert before["stale"] is False

    rewritten = _move_origin(origin)

    clock.advance(10)
    refreshed = api("/api/source/refresh", data=refresh)
    started = _payload(refreshed)
    assert started["refresh"] == "started"
    assert started["status"]["refreshing"] is True
    # The command waits for the refresh it asked for, then reports how it ended.
    ended = _after(refreshed)
    assert ended["refreshing"] is False
    assert ended["last_outcome"]["outcome"] == "succeeded"
    assert ended["latest"] == rewritten and ended["pin"] == SECOND

    after = _payload(api("/api/source/status"))
    assert after["pin"] == rewritten
    assert after["latest"] == rewritten
    assert after["last_outcome"]["operation"] == "refresh"
    assert after["last_outcome"]["outcome"] == "succeeded"

    # The fetch a page asks for when it opens a commit the mirror lacks. The mirror was
    # just fetched, so the page's own request starts nothing and is answered at once;
    # a reader's retry fetches all the same.
    own = api("/api/source/refresh", data=_body(bodies, "commit-fetch.json", {"for": "commit"}))
    assert _payload(own)["refresh"] == "fresh"
    assert _payload(own)["status"]["refreshing"] is False
    assert len(_sections(own.stdout)) == 1, "nothing was started, so there is nothing to follow"
    clock.advance(10)
    retried = api(
        "/api/source/refresh",
        data=_body(bodies, "commit-retry.json", {"for": "commit", "retry": True}),
    )
    assert _payload(retried)["refresh"] == "started"
    assert _after(retried)["last_outcome"]["outcome"] == "succeeded"

    old = _payload(api("/api/source/pin", data=_body(bodies, "pin-second.json", {"oid": SECOND})))
    assert old["changed"] is True and old["status"]["pin"] == SECOND
    tag = _payload(api("/api/source/pin", data=_body(bodies, "pin-v2.json", {"ref": "v2"})))
    assert tag["status"]["pin"] == rewritten
    gone = api(
        "/api/source/pin", data=_body(bodies, "pin-feature.json", {"ref": "feature"}), refuse=True
    )
    assert _payload(gone)["code"] == "selection_not_found"
    kept = _payload(
        api("/api/source/pin", data=_body(bodies, "pin-feature-oid.json", {"oid": FEATURE}))
    )
    assert kept["status"]["pin"] == FEATURE

    shutil.rmtree(origin)
    clock.advance(10)
    unreachable = api("/api/source/refresh", data=refresh, refuse=True)
    assert "the refresh ended with origin_unavailable" in unreachable.stderr
    assert _after(unreachable)["last_outcome"]["outcome"] == "origin_unavailable"
    # The record keeps the outcome by name, so the next command reports it too.
    failed = _payload(api("/api/source/status"))
    assert failed["pin"] == rewritten
    assert failed["last_outcome"]["operation"] == "refresh"
    assert failed["last_outcome"]["outcome"] == "origin_unavailable"
    # The last successful fetch, the retry's, is kept; only the outcome records the failure.
    assert failed["last_fetch_at"] == _after(retried)["last_fetch_at"]

    labels = Labels()
    labels.origin(url)
    rendered = label_home(labels.apply("".join(blocks)), sandbox.home)
    assert str(tmp_path) not in rendered
    check_golden("cli-git-refresh.txt", rendered)
