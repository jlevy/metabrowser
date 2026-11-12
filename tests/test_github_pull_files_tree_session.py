"""The changed-files tree session runs production browser code on what a server answers.

``tests/dom/github-pull-files-tree-session.js`` drives ``builtin_plugins/github/pull-files-tree.js``
-- a tree from a list, folder chains drawn as one row, expansion, renames, a deleted file, a
name the display rule changes, the current file, a cut list, each ``gh`` state, and a list
that fills page by page -- and ``tests/golden/cli-ui-github-pull-files-tree.tryscript.md``
pins its transcript. Its input is ``tests/fixtures/github-pull-files-responses.json``: what
the production CLI and route answered while a fake ``gh`` replayed full-size pages of changed
files, with the clock fixed, each row as one line of JSON. A list filling is caught between its pages: the job runs here
with a network slot that, each time it is taken, reads the route's envelope from the rows
held on, as a tree polling while it fills would. The first test replays that story and fails
when the recording no longer matches; ``make golden-update`` rewrites it.
"""

from __future__ import annotations

import asyncio
import contextlib
import json
import os
from collections.abc import AsyncGenerator, Callable
from pathlib import Path
from typing import Any

import pytest

from metabrowser.builtin_plugins.github.pull_files_refresh import refresh_pull_files
from metabrowser.builtin_plugins.github.pull_files_route import (
    FilesView,
    FilesWindow,
    pull_files_envelope,
)
from metabrowser.builtin_plugins.github.pull_list import ListedRepository
from tests.github_pull_fixture import (
    ANOTHER_READER,
    CANONICAL,
    CAPPED_PULL,
    TREE_PULL,
    Origin,
    account,
    file_item,
    file_pages,
    files_page,
    files_scenario,
    tree_files,
)
from tests.golden_harness import check_recording, origin_identity, read_recording, run_session
from tests.required_tools import needs_git
from tests.test_cli_github_pull_files_golden import _after, _api, _first, _Session, _with

RECORDING = "github-pull-files-responses.json"
TRANSCRIPT = "cli-ui-github-pull-files-tree.tryscript.md"
pytestmark = [
    needs_git,
    pytest.mark.skipif(os.name != "posix", reason="the fake gh is a POSIX script"),
]

_FAILURES = (
    "not_logged_in",
    "gh_too_old",
    "not_found_or_private",
    "network_error",
    "gh_failed",
    "account_changed",
    "gh_missing",
    "rate_limited",
    "cache_unwritable",
)


def _filling(
    repository: ListedRepository, number: int, captured: list[dict[str, Any]]
) -> Callable[[], contextlib.AbstractAsyncContextManager[object]]:
    """A network slot that reads the route each time it is taken, from the rows held on."""

    @contextlib.asynccontextmanager
    async def slot() -> AsyncGenerator[object]:
        held = sum(len(envelope["rows"]) for envelope in captured)
        view = FilesView(number, repository, None, True, None)
        envelope = pull_files_envelope(view, FilesWindow(number, offset=held))
        if envelope["fetched"] > held or not captured:
            captured.append(dict(envelope))
        yield None

    return slot


def _record(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, origin: Origin) -> dict[str, Any]:
    session = _Session(tmp_path, monkeypatch, origin)
    online = files_scenario(origin)
    recorded: dict[str, Any] = {}
    recorded["absent"] = session.get(f"?number={TREE_PULL}&limit=0").payload()
    repository = ListedRepository(session.home, origin_identity(CANONICAL).slug, "octo", "demo")

    # A first fill, caught between its pages, and the read after the job.
    captured: list[dict[str, Any]] = []
    asyncio.run(
        refresh_pull_files(
            repository, TREE_PULL, local=None, slot=_filling(repository, TREE_PULL, captured)
        )
    )
    for index, envelope in enumerate(captured):
        recorded[f"filling {index}"] = envelope
    held = sum(len(envelope["rows"]) for envelope in captured)
    recorded["filled"] = session.get(f"?number={TREE_PULL}&offset={held}").payload()

    started = session.post({"number": CAPPED_PULL})
    recorded["pending"] = _first(started)["files"]
    recorded["capped"] = _after(started)
    cached = session.run(f"{CANONICAL}/pull/7", "--api", "/api/plugin/github/pull?number=7")
    assert cached.exit_code == 0, cached.stderr
    assert session.post({"number": 7}).exit_code == 0
    recorded["comparison"] = session.get("?number=7").payload()

    # A list stopped by GitHub's limit at its third page, as the route then answers it.
    halted = CAPPED_PULL - 1
    limited = {
        "status": 403,
        "headers": {"X-Ratelimit-Remaining": "0", "X-Ratelimit-Reset": "1790181960"},
        "body": {"message": "API rate limit exceeded"},
    }
    session.answer(
        {
            **online,
            "api": {
                **online["api"],
                **file_pages(halted, tree_files()),
                files_page(halted, 3): limited,
            },
        }
    )
    session.post({"number": halted, "retry": True})
    recorded["stopped"] = session.get(f"?number={halted}").payload()

    # Each typed failure, after the list is held.
    failing: dict[str, dict[str, Any]] = {
        "not_logged_in": _with(online, auth={"stdout": '{"hosts":{}}\n', "exit": 0}),
        "gh_too_old": _with(
            online, auth={"stderr": "unknown flag: --json\n\nUsage: gh auth status\n", "exit": 1}
        ),
        "not_found_or_private": _api(
            online, files_page(TREE_PULL, 1), {"status": 404, "body": {"message": "Not Found"}}
        ),
        "network_error": _with(
            online, api_failure={"stderr": "error connecting to api.github.com\n", "exit": 1}
        ),
        "gh_failed": _api(online, files_page(TREE_PULL, 1), {"status": 200, "raw": "not JSON"}),
        "account_changed": _with(online, auth=[account(), account(ANOTHER_READER)]),
        "rate_limited": _api(
            online,
            files_page(TREE_PULL, 1),
            {"status": 429, "headers": {"Retry-After": "120"}, "body": {"message": "slow down"}},
        ),
    }
    for state, answers in failing.items():
        session.answer(answers)
        recorded[f"failed {state}"] = _after(session.post({"number": TREE_PULL, "retry": True}))
        session.advance(121)
    session.answer(online)
    with monkeypatch.context() as patched:
        from metabrowser.builtin_plugins.github import gh

        patched.setattr(gh, "gh_executable", lambda: None)
        recorded["failed gh_missing"] = _after(session.post({"number": TREE_PULL, "retry": True}))
    pulls_directory = session.home / "sources" / repository.slug / "pulls"
    pulls_directory.chmod(0o500)
    try:
        refused = session.post({"number": TREE_PULL, "retry": True})
    finally:
        pulls_directory.chmod(0o700)
    recorded["failed cache_unwritable"] = _after(refused)
    recorded["stale"] = session.get(f"?number={TREE_PULL}&limit=0").payload()
    # Two successful, equally sized refreshes in one clock second must be distinct.
    # Polling at the old end first sees no rows; its identity must force a read from zero.
    for name in ("before", "after"):
        session.answer(
            {
                **online,
                "api": {**online["api"], **file_pages(TREE_PULL, [file_item(f"{name}.js")])},
            }
        )
        assert session.post({"number": TREE_PULL, "retry": True}).exit_code == 0
        recorded[f"same second {name}"] = session.get(f"?number={TREE_PULL}").payload()
    recorded["same second continuation"] = session.get(f"?number={TREE_PULL}&offset=1").payload()
    root = tmp_path / "root"
    root.mkdir(exist_ok=True)
    recorded["not_github"] = session.run(
        str(root), "--api", f"/api/plugin/github/pull-files?number={TREE_PULL}&limit=0"
    ).payload()
    return recorded


def test_recording_is_what_the_routes_answer(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, pull_origin: Origin
) -> None:
    recorded = _record(tmp_path, monkeypatch, pull_origin)
    assert (recorded["absent"]["state"], recorded["absent"]["reason"]) == ("absent", "not_cached")
    # Full-size pages: each published as it arrived, the count honest at each.
    fills = [recorded[name] for name in sorted(recorded) if name.startswith("filling ")]
    assert [(f["fetched"], f["pages"], f["last_page"], f["complete"]) for f in fills[1:]] == [
        (100, 1, 3, False),
        (200, 2, 3, False),
    ]
    assert [len(f["rows"]) for f in fills[1:]] == [100, 100]
    assert {f["generation"] for f in fills[1:]} == {recorded["filled"]["generation"]}
    filled = recorded["filled"]
    assert (filled["fetched"], filled["complete"], len(filled["rows"])) == (249, True, 49)
    assert recorded["pending"]["state"] == "pending"
    capped = recorded["capped"]
    assert (capped["fetched"], capped["capped"], capped["complete"]) == (3000, True, True)
    assert recorded["comparison"]["listed_from"] == "comparison"
    stopped = recorded["stopped"]
    assert (stopped["fetched"], stopped["complete"], stopped["refreshing"]) == (200, False, False)
    for name in _FAILURES:
        envelope = recorded[f"failed {name}"]
        assert envelope["last_refresh"]["outcome"] == name, name
        assert envelope["fetched"] == 249, name
    assert recorded["stale"]["state"] == "stale"
    assert recorded["not_github"]["reason"] == "not_github"
    before, after = recorded["same second before"], recorded["same second after"]
    assert before["generation"] != after["generation"]
    assert after["generation"] == recorded["same second continuation"]["generation"]
    assert before["fetched_at"] == after["fetched_at"]
    assert before["fetched"] == after["fetched"] == 1
    assert before["rows"][0]["path"] == "before.js"
    assert after["rows"][0]["path"] == "after.js"
    assert recorded["same second continuation"]["rows"] == []
    check_recording(RECORDING, _rows_as_lines(recorded), transcript=TRANSCRIPT, indent=1)


def _rows_as_lines(recorded: dict[str, Any]) -> dict[str, Any]:
    """Each row as one line of JSON, so a page of rows is a hundred lines to review."""

    return {
        name: {**envelope, "rows": [json.dumps(row) for row in envelope["rows"]]}
        for name, envelope in recorded.items()
    }


def test_the_tree_holds_its_invariants() -> None:
    """What the golden shows, held as relations a reviewer can break the model against.

    Each is independent of the transcript's wording: the rows a list fills to are its rows,
    in one order; no folder whose only child is a folder is a row of its own; a file is
    counted once in each folder above it; and a name is only ever the server's display.
    """

    out = run_session("github-pull-files-tree-session.js")
    checks = out["invariants"]
    assert checks["filled rows are the list's rows"] is True
    assert checks["no single-child folder is its own row"] is True
    assert checks["each folder counts the files under it"] is True
    assert checks["every name is the server's display"] is True
    assert checks["a list for another read starts again at 0"] is True


def test_a_tree_opens_once_and_never_grows_without_input() -> None:
    """A row's tree opens at its height, and late rows wait for the reader.

    Opening waits ``FILES_OPEN_HOLD_MS`` for the cached list it reads at once, so a list the
    cache holds goes from closed to its rows in one step, where it went through its loading
    line first. Rows a GitHub job brings ``LATE_ROWS_MS`` past the reader's last press or key
    are offered on the line, at its height, and drawn when the reader asks; before, they
    pushed the rows below without input. Rows inside the input's window are drawn as before.
    """

    assert run_session("github-pull-files-opening-behavior.js") == {
        "cached": ["closed", "4 rows"],
        "lateRows": ["closed", "loading line", "offer: Show 2 files", "4 rows"],
        "promptRows": ["closed", "loading line", "4 rows"],
        "slowRead": ["closed", "loading line"],
    }


def test_the_recording_holds_every_failure_the_plan_names() -> None:
    """Each typed state of the plan's table has a recorded answer the session plays."""

    recording = read_recording(RECORDING)
    for name in _FAILURES:
        assert recording[f"failed {name}"]["last_refresh"]["outcome"] == name
    assert json.dumps(recording).count('"capped": true') >= 1


def test_removed_focused_file_transfers_focus_after_replacement_paint() -> None:
    """A refreshed list retains keyboard ownership and never steals unrelated focus."""

    assert run_session("github-pull-files-focus-behavior.js") == [
        {"scenario": "survivor", "focus": "a.py"},
        {"scenario": "empty", "focus": "owner"},
        {"scenario": "other focus", "focus": "elsewhere"},
        {"scenario": "windowed survivor", "focus": "a000.py"},
        {"scenario": "windowed other focus", "focus": "elsewhere"},
        # A stale list's rows are never covered by progress: while its refresh is asked for
        # and runs, the names breathe in one group, nothing spins, and no line says the list
        # is stale ("Refreshing Content" in docs/design-system.md). The rows stay usable, so
        # the group is never marked busy.
        {
            "scenario": "refreshing",
            "paints": {
                phase: {
                    "breathing": phase != "settled",
                    "busy": None,
                    "spinner": False,
                    "line": None,
                    "names": ["src", "a.py", "b.py"],
                    "namesBreathe": True,
                }
                for phase in ("asked", "running", "settled")
            },
        },
    ]


def test_closed_file_tree_replies_cannot_own_a_reopened_visit() -> None:
    assert run_session("github-pull-files-lifecycle-behavior.js") == {
        "ownedReads": 9,
        "ownedRefreshReplies": 6,
    }
