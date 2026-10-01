"""The View file session runs production browser code on what a served mirror answers.

``tests/dom/diff-view-file-session.js`` loads the diff plugin whole, as the shell loads
it, mounts the diff of a commit and of a pull request's comparison, reads the View file
controls of each file bar, and follows them; ``tests/golden/cli-ui-diff-view-file.tryscript.md``
pins its transcript. So that the conversation is the real server's and not envelopes a
test wrote by hand, its documents, the block the shell writes into a page, and every
answer of ``POST /api/source/pin`` come from
``tests/fixtures/diff-view-file-responses.json``: what the in-process application
answered while it served ``tests/diff_view_file_fixture.py``'s mirror, then while a
server on another repository, and one on a folder, answered a page left open from it.
The first test here replays that story against real stores and fails when the recording
no longer matches.

Commit IDs are real: both origins are written by ``git fast-import``. Fetch times are
wall-clock values, so each is replaced by one fixed stand-in. ``make golden-update``
rewrites the recording and then the transcript.
"""

from __future__ import annotations

import asyncio
import json
import os
import re
import shutil
import subprocess
from pathlib import Path
from typing import Any

import pytest
from starlette.testclient import TestClient

from metabrowser import server
from metabrowser.cache.acquire import PublishedSource, acquire_source
from metabrowser.cache.records import StoreOperation
from metabrowser.git.tree_source import GitPath
from metabrowser.mirror_refresh import serve_mirror
from metabrowser.source import reset_source_session
from tests import source_mirror_fixture
from tests.diff_view_file_fixture import (
    LATIN1_NAME,
    NEW_NAME,
    OLD_NAME,
    build_origin,
    commits,
    view,
)
from tests.golden_harness import (
    JSON_BODY,
    answer,
    check_recording,
    run_session,
    serve_published,
)
from tests.required_tools import needs_git
from tests.source_mirror_fixture import FETCHED_AT
from tests.test_cache_acquire import _allow_installed_git, _file_source
from tests.test_source_freshness_session import _settle, _stand_in_times, _write_state

SESSION = "diff-view-file-session.js"
# What the shell writes into a page on a pin: the commit and ref it was rendered for.
_PAGE_PIN = re.compile(r"window\.METABROWSER_SOURCE_PIN=(\{.*?\});</script>")

posix_only = pytest.mark.skipif(os.name != "posix", reason="owner-only cache is POSIX-only")
pytestmark = [
    posix_only,
    needs_git,
]


def _page(client: TestClient) -> dict[str, Any] | None:
    """The page block of the shell as served now; ``None`` when it writes none."""

    shell = client.get("/view/")
    assert shell.status_code == 200
    found = _PAGE_PIN.search(shell.text)
    return None if found is None else json.loads(found.group(1))


def _switch(client: TestClient, body: dict[str, str]) -> dict[str, Any]:
    response = client.post("/api/source/pin", json=body, headers=JSON_BODY)
    return {"request": body, **answer(response)}


def _acquire(origin: Path, home: Path) -> PublishedSource:
    published = asyncio.run(acquire_source(_file_source(origin), home=home))
    _write_state(
        published, operation=StoreOperation(kind="acquire", outcome="succeeded", at=FETCHED_AT)
    )
    return published


def _record(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> dict[str, Any]:
    home = tmp_path / "home"
    monkeypatch.setenv("METABROWSER_HOME", str(home))
    _allow_installed_git(monkeypatch)
    origin = build_origin(tmp_path)
    ids = commits(origin)
    readme = view("README.md")
    recorded: dict[str, Any] = {
        "commits": ids,
        "views": {
            "readme": readme,
            "old_name": view(OLD_NAME),
            "new_name": view(NEW_NAME),
            "latin1": view(LATIN1_NAME),
        },
    }
    try:
        serve_published(_acquire(origin, home))
        with TestClient(server.app) as client:

            def comparison(**params: str) -> dict[str, Any]:
                return answer(client.get("/api/plugin/diff/comparison", params=params))

            recorded["page"] = _page(client)
            recorded["commit"] = comparison(revision=ids["second"])
            recorded["root"] = comparison(revision=ids["first"])
            # A pull request's Files changed: its base branch against its head, from
            # their merge base.
            recorded["pull"] = comparison(
                left=ids["base"], right=ids["second"], base_policy="merge_base"
            )
            patch = view("changes.patch").removeprefix("/view/")
            recorded["patch"] = answer(
                client.get("/api/plugin/diff/document", params={"path": patch})
            )
            recorded["switch_parent"] = _switch(
                client, {"oid": ids["first"], "view": recorded["views"]["old_name"]}
            )
            recorded["page_at_parent"] = _page(client)
            # Asked of a page brought back by Back, for the deleted file's old side.
            recorded["switch_gone"] = _switch(
                client, {"oid": ids["first"], "view": view("gone.txt")}
            )
            recorded["switch_head"] = _switch(
                client, {"oid": ids["second"], "view": recorded["views"]["new_name"]}
            )
        # A page left open while its server was restarted on another repository: that
        # mirror has neither commit. A server fetches once for a commit its mirror
        # lacks, then says the origin does not have it.
        other = tmp_path / "other"
        other.mkdir()
        other_origin = source_mirror_fixture.build_origin(other)
        serve_published(_acquire(other_origin, home), serving=True)
        with TestClient(server.app) as client:
            _settle(client)
            lacking = {"oid": ids["first"], "view": readme}
            recorded["other_pending"] = _switch(client, lacking)
            _settle(client)
            recorded["other_not_found"] = _switch(client, lacking)
            # Asked once more with its origin gone, the fetch cannot run.
            shutil.move(other_origin, other / "away.git")
            assert _switch(client, lacking)["status"] == 202
            _settle(client)
            recorded["other_fetch_failed"] = _switch(client, lacking)
        # The same page after its server was restarted on a folder, which has no pin.
        folder = tmp_path / "folder"
        folder.mkdir()
        serve_mirror(None)
        reset_source_session()
        server._set_root_dir(folder)
        with TestClient(server.app) as client:
            recorded["folder_page"] = _page(client)
            recorded["folder_refused"] = _switch(client, lacking)
    finally:
        serve_mirror(None)
    return _stand_in_times(recorded)


def test_recording_is_what_the_servers_answer(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    recorded = _record(tmp_path, monkeypatch)
    ids = recorded["commits"]
    assert recorded["page"] == {"pin": ids["second"], "ref": "refs/remotes/origin/trunk"}
    resolved = recorded["commit"]["body"]["resolved"]
    assert (resolved["base_policy"], resolved["left"]["id"], resolved["right"]["id"]) == (
        "first_parent",
        ids["first"],
        ids["second"],
    )
    files = recorded["commit"]["body"]["manifest"]["files"]
    assert {change["kind"] for change in files} == {"modified", "added", "deleted", "renamed"}
    assert {(change.get("new") or change["old"])["entry_type"] for change in files} == {
        "file",
        "symlink",
        "submodule",
    }
    assert recorded["root"]["body"]["resolved"]["left"] == {
        "kind": "empty",
        "symbolic": ids["first"],
    }
    pull = recorded["pull"]["body"]["resolved"]
    # The merge base, not the tip of the base branch the comparison named.
    assert (pull["base_policy"], pull["left"]["id"]) == ("merge_base", ids["first"])
    assert pull["left"]["id"] != ids["base"]
    assert recorded["patch"]["body"]["resolved"]["left"]["kind"] == "patch"
    parent = recorded["switch_parent"]
    assert (parent["status"], parent["body"]["view_href"]) == (200, recorded["views"]["old_name"])
    assert recorded["page_at_parent"] == {"pin": ids["first"], "ref": None}
    head = recorded["switch_head"]
    assert (head["status"], head["body"]["view_href"]) == (200, recorded["views"]["new_name"])
    # Back on the branch's tip by its ID, the server serves the branch again.
    assert head["body"]["status"]["ref"] == "refs/remotes/origin/trunk"
    assert recorded["other_pending"]["status"] == 202
    assert recorded["other_pending"]["body"]["code"] == "selection_pending"
    assert recorded["other_not_found"]["status"] == 404
    assert recorded["other_fetch_failed"]["status"] == 502
    assert recorded["other_fetch_failed"]["body"]["code"] == "selection_fetch_failed"
    assert recorded["folder_page"] is None
    assert recorded["folder_refused"]["status"] == 409
    check_recording(
        "diff-view-file-responses.json", recorded, transcript="cli-ui-diff-view-file.tryscript.md"
    )


_LINK = re.compile(r"link (/view/\S+) · Open .* at ([0-9a-f]{12}), ")
_SWITCH = re.compile(r"POST /api/source/pin \[content-type: application/json\] (\{.*\})$")


def test_every_side_the_session_offers_is_a_file_at_its_commit(tmp_path: Path) -> None:
    """Git itself confirms what the transcript cannot: each address names a real file.

    ``tests/golden/cli-ui-diff-view-file.tryscript.md`` pins what the session prints. This
    asks the fixture's repository whether every link's address, and every address a
    switch posts, is a blob at the commit it is offered at: so a deleted file is offered
    only where it exists, a renamed one at its old path on the old side, and a name that
    is not UTF-8 by its bytes.
    """

    offered: set[tuple[str, str]] = set()
    for step in run_session(SESSION)["steps"]:
        for controls in step.get("bars", {}).values():
            for control in controls:
                link = _LINK.search(control)
                if link is not None:
                    offered.add((link.group(2), link.group(1)))
        for request in step["requests"]:
            switch = _SWITCH.match(request)
            if switch is not None:
                body = json.loads(switch.group(1))
                offered.add((body["oid"], body["view"]))
    # Both commits, by link and by switch, and every kind of change among them.
    assert len(offered) >= 12, offered
    origin = build_origin(tmp_path)
    for commit, address in sorted(offered):
        segments = GitPath.from_wire(address.removeprefix("/view/")).segments
        kind = subprocess.run(
            [
                b"git",
                b"--git-dir",
                os.fsencode(origin),
                b"cat-file",
                b"-t",
                commit.encode() + b":" + b"/".join(segments),
            ],
            capture_output=True,
            check=False,
        )
        assert kind.stdout.strip() == b"blob", (commit, address, kind.stderr)
