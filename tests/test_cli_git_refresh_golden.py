"""Golden transcript: refreshing a ``file://`` mirror and switching its pin, in-process.

A refresh runs ``git fetch``, which the acquisition floor refuses on CI's Git, so this
runs the production CLI in-process with only the floor patched -- the boundary
``tests/test_cli_git_pin_golden.py`` uses -- and stays a ``.txt`` transcript. Every
command is its own ``metab`` invocation, so what one command changes reaches the next
only through the store, exactly as for a user running them one after another. Nothing
binds a port.

The origin is ``tests/source_mirror_fixture.py``'s, written with ``git fast-import`` so
every commit ID is the same on every machine. Between the first status and the refresh,
the origin moves the way a busy upstream does:

- ``topic`` is force-pushed: ``second`` is dropped and ``rewritten`` replaces it;
- ``feature`` is deleted;
- ``v2`` tags ``rewritten``.

The transcript then shows the refresh starting and, once it has ended, the status after
it; the next command pinning the new default revision; the force-pushed-away commit and
the deleted branch's commit still readable by ID; the deleted branch gone by name; and a
refresh against a removed origin recorded as ``origin_unavailable``, which exits 1 while
the mirror keeps serving. Fetch times are wall-clock values no fixture can pin, so they
read ``<TIME>``.

Regenerate after an intended change with:

    GOLDEN_UPDATE=1 uv --config-file uv.toml run --frozen pytest tests/test_cli_git_refresh_golden.py
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

from tests.source_mirror_fixture import build_origin
from tests.test_cli_cache_acquire_golden import _elide_payload, _file_url, _isolate, _strip_logs
from tests.test_cli_git_pin_golden import _Invocation, _ok, _refused
from tests.test_cli_golden import check_golden

posix_only = pytest.mark.skipif(os.name != "posix", reason="owner-only cache is POSIX-only")

pytestmark = pytest.mark.skipif(shutil.which("git") is None, reason="git executable is required")

FIRST = "fcb9d63c3c8533d1b929861f451a066e6d4f2d9e"
SECOND = "42382ea2303b733e1e21b4bd6ddb974ca4e775eb"
FEATURE = "c7ae2a331f546e6a2431ed7093e9e430a9d1269b"


def _git_env(directory: Path) -> dict[str, str]:
    env = {name: value for name, value in os.environ.items() if not name.startswith("GIT_")}
    env["GIT_CONFIG_GLOBAL"] = os.devnull
    env["GIT_CONFIG_NOSYSTEM"] = "1"
    return env


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
    env = _git_env(origin.parent)
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


def _body(directory: Path, name: str, body: dict[str, str]) -> str:
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


def _payload(result: _Invocation) -> Any:
    return _sections(result.stdout)[0][1]


def _after(result: _Invocation) -> Any:
    return _sections(result.stdout)[1][1]


def _record(command: str, result: _Invocation) -> str:
    stdout = "".join(
        header + json.dumps(_elide_payload(payload), indent=2, ensure_ascii=False) + "\n"
        for header, payload in _sections(_strip_logs(result.stdout))
    )
    return (
        f"# metab {command}\n"
        f"exit: {result.exit_code}\n"
        f"--- stdout ---\n{stdout}"
        f"--- stderr ---\n{_strip_logs(result.stderr)}"
    )


@posix_only
def test_golden_refresh_and_pin_switching(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _isolate(tmp_path, monkeypatch)
    origin = build_origin(tmp_path)
    url = _file_url(origin)
    bodies = tmp_path / "bodies"
    bodies.mkdir()
    refresh = _body(bodies, "refresh.json", {})

    blocks: list[str] = []

    def api(route: str, *, data: str | None = None, refused: bool = False) -> _Invocation:
        args = [url, "--api", route] + (["--data", data] if data else [])
        result = _refused(args) if refused else _ok(args)
        shown = f"file://<ORIGIN> --api {route}" + (f" --data {Path(data).name}" if data else "")
        blocks.append(_record(shown, result))
        return result

    before = _payload(api("/api/source/status"))
    assert before["pin"] == SECOND
    assert before["last_outcome"]["operation"] == "acquire"
    assert before["stale"] is False

    rewritten = _move_origin(origin)

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

    old = _payload(api("/api/source/pin", data=_body(bodies, "pin-second.json", {"oid": SECOND})))
    assert old["changed"] is True and old["status"]["pin"] == SECOND
    tag = _payload(api("/api/source/pin", data=_body(bodies, "pin-v2.json", {"ref": "v2"})))
    assert tag["status"]["pin"] == rewritten
    gone = api(
        "/api/source/pin", data=_body(bodies, "pin-feature.json", {"ref": "feature"}), refused=True
    )
    assert _payload(gone)["code"] == "selection_not_found"
    kept = _payload(
        api("/api/source/pin", data=_body(bodies, "pin-feature-oid.json", {"oid": FEATURE}))
    )
    assert kept["status"]["pin"] == FEATURE

    shutil.rmtree(origin)
    unreachable = api("/api/source/refresh", data=refresh, refused=True)
    assert "the refresh ended with origin_unavailable" in unreachable.stderr
    assert _after(unreachable)["last_outcome"]["outcome"] == "origin_unavailable"
    # The record keeps the outcome by name, so the next command reports it too.
    failed = _payload(api("/api/source/status"))
    assert failed["pin"] == rewritten
    assert failed["last_outcome"]["operation"] == "refresh"
    assert failed["last_outcome"]["outcome"] == "origin_unavailable"
    # The last successful fetch is kept; only the outcome records the failure.
    assert failed["last_fetch_at"] == after["last_fetch_at"]

    rendered = "".join(blocks)
    assert str(tmp_path) not in rendered
    check_golden("cli-git-refresh.txt", rendered)
