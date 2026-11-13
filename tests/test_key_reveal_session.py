"""The key reveal session runs the production keymap on what the server says a page shows.

``tests/dom/key-reveal-session.js`` drives the shortcut registry, the Shift reveal, the
shell keymap, Help, the main tabs, and the Pulls tab's keys through a scripted page, and
``tests/golden/cli-ui-key-reveal.tryscript.md`` pins its transcript. Which keys are live
depends on the server's answers: the views and their keys in a file's ``/api/file``
envelope, whether ``/api/git/repo`` finds a repository, and whether
``/api/source/status`` names a pin. So the session plays those answers from
``tests/fixtures/key-reveal-responses.json``, which the first test here records from the
in-process application and fails when the recording drifts. A recording keeps of each
answer what the keymap reads, the status and the envelope's kind, path, and views (or
the repository and pin fields), because the rest names the sandbox and the clock.

The transcript prints the shell keys the session's registry registered, and
``tests/test_keymap.py`` holds them to the reserved table in ``src/metabrowser/keymap.py``.
``make golden-update`` rewrites the recording and then the transcript.
"""

from __future__ import annotations

import asyncio
import os
import subprocess
from pathlib import Path
from typing import Any

import pytest
from starlette.testclient import TestClient

from metabrowser import server
from metabrowser.cache.acquire import acquire_source
from metabrowser.cache.records import StoreOperation
from metabrowser.capabilities import Capabilities, set_capabilities
from metabrowser.mirror_refresh import serve_mirror
from metabrowser.source import reset_source_session
from tests.golden_harness import (
    check_recording,
    pinned_git_env,
    read_recording,
    run_session,
    serve_published,
    stand_in_sandbox,
)
from tests.required_tools import needs_git
from tests.source_mirror_fixture import FETCHED_AT, build_origin
from tests.test_cache_acquire import _allow_installed_git, _file_source
from tests.test_source_freshness_session import _write_state

RECORDING = "key-reveal-responses.json"
TRANSCRIPT = "cli-ui-key-reveal.tryscript.md"

posix_only = pytest.mark.skipif(os.name != "posix", reason="owner-only cache is POSIX-only")
pytestmark = [posix_only, needs_git]

# A folder of every multi-view kind the session opens, as `cli-show.tryscript.md` builds.
FILES = {
    "README.md": "# Sample\n\nHello.\n",
    "data.json": '{"name": "sample", "version": 1}\n',
    "session.jsonl": '{"type":"system","subtype":"init","session_id":"s1","model":"m1"}\n',
    "page.html": "<!doctype html>\n<title>Page</title>\n<p>Hello</p>\n",
    "docs/guide.md": "# Guide\n",
}
STATUS_FIELDS = ("pin", "ref", "ref_name")


def _file(client: TestClient, path: str) -> dict[str, Any]:
    response = client.get("/api/file", params={"path": path})
    body = response.json()
    return {
        "status": response.status_code,
        "body": {"kind": body["kind"], "path": body["path"], "views": body.get("views", [])},
    }


def _repo(client: TestClient) -> dict[str, Any]:
    response = client.get("/api/git/repo")
    body = response.json()
    return {"status": response.status_code, "body": {"is_repo": body["is_repo"]}}


def _status(client: TestClient) -> dict[str, Any]:
    response = client.get("/api/source/status")
    body = response.json()
    return {
        "status": response.status_code,
        "body": {field: body.get(field) for field in STATUS_FIELDS},
    }


def _folder(tmp_path: Path, name: str, *, repository: bool) -> Path:
    root = tmp_path / name
    for relative, text in FILES.items():
        (root / relative).parent.mkdir(parents=True, exist_ok=True)
        (root / relative).write_text(text)
    if repository:
        env = pinned_git_env()
        subprocess.run(["git", "init", "-q", "-b", "main", str(root)], check=True, env=env)
        subprocess.run(["git", "-C", str(root), "add", "-A"], check=True, env=env)
        subprocess.run(
            ["git", "-C", str(root), "commit", "-q", "-m", "Sample"], check=True, env=env
        )
    return root


def _record(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> dict[str, Any]:
    recorded: dict[str, Any] = {}

    # A plain folder: every multi-view kind, and HTML with its active content on and off.
    reset_source_session()
    server._set_root_dir(_folder(tmp_path, "plain", repository=False))  # pyright: ignore[reportPrivateUsage]
    with TestClient(server.app) as client:
        recorded["folder"] = {
            "status": _status(client),
            "repo": _repo(client),
            "files": {
                path: _file(client, path)
                for path in ("", "docs", "README.md", "data.json", "session.jsonl", "page.html")
            },
        }
        set_capabilities(Capabilities(active_content=False, mutations=False))
        recorded["folder"]["inactive_html"] = _file(client, "page.html")

    # The same folder as a Git repository, where the Commits tab appears.
    reset_source_session()
    set_capabilities(Capabilities(active_content=True, mutations=False))
    server._set_root_dir(  # pyright: ignore[reportPrivateUsage]
        _folder(tmp_path, "repository", repository=True)
    )
    with TestClient(server.app) as client:
        recorded["repository"] = {"status": _status(client), "repo": _repo(client)}

    # A served mirror's pin, which has a branch switcher and no modified-within filter.
    reset_source_session()
    monkeypatch.setenv("METABROWSER_CACHE_DIR", str(tmp_path / "home"))
    _allow_installed_git(monkeypatch)
    origin = build_origin(tmp_path)
    published = asyncio.run(acquire_source(_file_source(origin), home=tmp_path / "home"))
    _write_state(
        published, operation=StoreOperation(kind="acquire", outcome="succeeded", at=FETCHED_AT)
    )
    serve_published(published)
    try:
        with TestClient(server.app) as client:
            recorded["pin"] = {
                "status": _status(client),
                "repo": _repo(client),
                "files": {"": _file(client, "")},
            }
    finally:
        serve_mirror(None)
    return stand_in_sandbox(recorded, tmp_path, published.store_key, home=published.home)


def test_recording_is_what_the_application_answers(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    recorded = _record(tmp_path, monkeypatch)
    files = recorded["folder"]["files"]
    keys = {
        path: [view.get("key") for view in answer["body"]["views"]]
        for path, answer in files.items()
    }
    assert keys == {
        "": ["o", "m"],
        "docs": ["o", "m"],
        "README.md": ["v", "s"],
        "data.json": ["v", "s"],
        "session.jsonl": ["v", "c", "s"],
        "page.html": ["v", "s"],
    }
    assert [view["id"] for view in recorded["folder"]["inactive_html"]["body"]["views"]] == [
        "source"
    ]
    assert recorded["folder"]["repo"]["body"]["is_repo"] is False
    assert recorded["folder"]["status"]["body"]["pin"] is None
    assert recorded["repository"]["repo"]["body"]["is_repo"] is True
    assert recorded["pin"]["status"]["body"]["pin"]
    check_recording(RECORDING, recorded, transcript=TRANSCRIPT)


def test_the_session_runs_on_the_recording() -> None:
    parts = [run_session("key-reveal-session.js", *part) for part in ((), ("gestures",), ("tabs",))]
    recording = read_recording(RECORDING)
    assert recording["pin"]["status"]["body"]["pin"]

    # What each part printed is what its golden pins, which tests/test_keymap.py holds to
    # the reserved shell keys.
    assert {key for part in parts for key in part["shellKeys"]} == set("123456789fhjknprtuw")

    by_name = {step["step"]: step for part in parts for step in part["steps"]}
    root = by_name["the root folder has no Up"]
    assert "header.parent" not in [command for _key, command, _target in root["keys"]]
    assert root["pressed"] == {"key": "u", "handled": False}
    # Copying is ancillary: its controls are on screen, and none has a key.
    for copying in (
        "copying is ancillary: the Copy path button has no key, and Y does nothing",
        "a commit view's Copy revision is ancillary and has no key",
    ):
        assert by_name[copying]["pressed"] == {"key": "y", "handled": False}, copying
        assert by_name[copying]["ancillary"], copying
    preview = by_name["the Preview tab is V, and P outside a stack does nothing"]
    assert ["V", "view-tabs.v", "Preview tab"] in preview["keys"]
    assert preview["p"] is False
    # The main tabs in their order, each with its letter.
    hosted = by_name["a repository with a hosted origin shows Files, Pulls, and Commits"]
    assert hosted["tabs"] == ["Files", "Pulls", "Commits"]
    assert [key for key, command, _target in hosted["keys"] if command.startswith("main-")] == [
        "F",
        "R",
        "H",
    ]
    # The numbers are positional and Help never gives a digit a fixed meaning.
    positional = by_name["Help lists the numbers once, as positional"]
    assert positional["helpDigits"] == [
        {"keys": "1–9", "range": True, "action": "Numbered links and actions"}
    ]
    assert positional["numbers"] == ["File type"]
    assert ["1", "File type"] in positional["badges"]
    assert by_name["Shift held past the threshold reveals"]["rootMarked"] is True
    for chord in (
        "a capital typed within the threshold never reveals",
        "? within the threshold opens Help and never reveals",
        "Shift+wheel never reveals",
        "Shift with the pointer travelling to a click never reveals",
        "Shift during a press that moved focus never reveals",
        "Shift in Quick Search's field never reveals",
    ):
        assert by_name[chord]["reveal"] == "idle", chord
    # A handled key that moves focus keeps the reveal: only the window's own blur ends it.
    for moved in (
        "↑ on a tree row moves one row and keeps the reveal",
        "a held J moves rows and does no reveal work on its repeats",
        "H with Shift still held opens Commits, focuses its row, and keeps the reveal",
        "F during the reveal shows the filter bar, and its filters gain 1 and 2",
    ):
        assert by_name[moved]["reveal"] == "revealed", moved
    assert by_name["the window losing focus ends the reveal"]["reveal"] == "idle"
    files = by_name["F during the reveal shows the filter bar, and its filters gain 1 and 2"]
    assert ["1", "Modified within"] in files["badges"]
    assert ["2", "File type"] in files["badges"]
    assert files["numbers"] == ["Modified within", "File type"]
    opened = by_name["2 opens the file type filter and focuses its checked row"]
    assert opened["focus"] == {
        "menu": "filter-type-menu",
        "row": "Any type",
        "checked": "true",
        "open": "true",
    }

    # What a navigation and a key cost: one publication, and while revealed one pass.
    same_kind = by_name["a move between two files of one kind registers nothing"]["cost"]
    assert same_kind == {"publications": ["batch(target)"], "targetReads": 0, "keycapsCreated": 0}
    moved_revealed = by_name["a navigation while revealed moves the badges in one pass"]["cost"]
    assert len(moved_revealed["publications"]) == 1
    assert by_name["a held J moves rows and does no reveal work on its repeats"]["repeats"] == {
        "publications": [],
        "targetReads": 0,
        "keycapsCreated": 0,
    }

    late = by_name["Commits registered while the registry is down gets its tab, then its key"]
    assert late["whileDown"] == {"threw": None, "tab": True, "container": True, "key": None}
    assert late["key"] == "H"
    assert late["pressed"] == {"key": "h", "handled": True}
    cancelled = by_name["V follows the committed bar, and a cancelled stage changes nothing"]
    assert cancelled["v"] == {
        "structured": "Tree",
        "agentLog": "Log",
        "back": "Tree",
        "whileStaged": "Tree",
        "afterCancel": "Tree",
    }
    assert by_name["the keymap after a pageshow rebuild"]["sameAsBefore"] is True
