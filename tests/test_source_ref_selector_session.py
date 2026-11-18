"""The ref selector session runs production browser code on what a served mirror answers.

``tests/dom/source-ref-selector-session.js`` drives ``static/source-ref-selector.js`` --
opening, the filter's pause, aborted requests, the branch and tag lists, switching,
and where arrow keys move focus --
through a scripted conversation, and
``tests/golden/cli-ui-source-ref-selector.tryscript.md`` pins its transcript. So that the
conversation is the real server's and not envelopes a test wrote by hand, its responses
come from ``tests/fixtures/source-ref-selector-responses.json``: what the in-process
application answered for the listings and the switches the session plays. The first
test here replays them against a real store and fails when the recording no longer
matches.

The origin is ``tests/source_mirror_fixture.py``'s, written by ``git fast-import``, so
every commit ID is the same on every machine, and its last fetch is recorded at the
fixture's fixed time, so every status envelope is literal. ``make golden-update``
rewrites the recording and then the transcript.

The same module is a served checkout's selector. Its conversation is recorded the same
way, from ``tests/source_checkout_fixture.py``'s checkout served as a folder, in
``tests/fixtures/source-ref-selector-checkout-responses.json``: the listings on the working
tree and on a revision, a branch, the checked-out branch, and the working tree again.
"""

from __future__ import annotations

import asyncio
import json
import os
from pathlib import Path
from typing import Any

import pytest
from starlette.testclient import TestClient

from metabrowser import server
from metabrowser.cache.acquire import acquire_source
from metabrowser.cache.records import StoreOperation
from metabrowser.git.process import UnsupportedGitVersionError
from metabrowser.git.tree_source import GitPath
from metabrowser.mirror_refresh import serve_mirror
from tests.golden_harness import (
    JSON_BODY,
    answer,
    check_recording,
    read_recording,
    run_session,
    serve_published,
    stand_in_sandbox,
)
from tests.required_tools import needs_git
from tests.source_checkout_fixture import admit_installed_git, build_checkout
from tests.source_checkout_fixture import view as revision_view
from tests.source_mirror_fixture import FETCHED_AT, build_origin
from tests.test_cache_acquire import _allow_installed_git, _file_source
from tests.test_source_freshness_session import _write_state

RECORDING = "source-ref-selector-responses.json"
CHECKOUT_RECORDING = "source-ref-selector-checkout-responses.json"
TRANSCRIPT = "cli-ui-source-ref-selector.tryscript.md"

TOPIC = "refs/remotes/origin/topic"
FEATURE = "refs/remotes/origin/feature"

posix_only = pytest.mark.skipif(os.name != "posix", reason="owner-only cache is POSIX-only")
pytestmark = [
    posix_only,
    needs_git,
]


def _view(display: str) -> str:
    return "/view/" + GitPath.from_display(display).to_wire()


def _record(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> dict[str, Any]:
    monkeypatch.setenv("METABROWSER_CACHE_DIR", str(tmp_path / "home"))
    _allow_installed_git(monkeypatch)
    origin = build_origin(tmp_path)
    published = asyncio.run(acquire_source(_file_source(origin), home=tmp_path / "home"))
    _write_state(
        published, operation=StoreOperation(kind="acquire", outcome="succeeded", at=FETCHED_AT)
    )
    serve_published(published)
    recorded: dict[str, Any] = {"views": {"readme": _view("README.md"), "notes": _view("NOTES.md")}}
    try:
        with TestClient(server.app) as client:

            def listing(**params: str) -> dict[str, Any]:
                return answer(client.get("/api/source/refs", params=params))

            def switch(body: dict[str, str]) -> dict[str, Any]:
                return answer(client.post("/api/source/pin", json=body, headers=JSON_BODY))

            recorded["branches"] = listing(kind="branch")
            recorded["tags"] = listing(kind="tag")
            recorded["filtered"] = listing(kind="branch", q="feat")
            recorded["nothing"] = listing(kind="branch", q="zzz")
            # The selector sends no limit; this is the page a longer list would answer.
            recorded["page"] = listing(kind="branch", limit="1")
            recorded["refused"] = listing(kind="commit")
            # NOTES.md is only on topic, so a page on it goes to the root on feature.
            recorded["switch_away"] = switch({"ref": FEATURE, "view": _view("NOTES.md")})
            recorded["switch_keep"] = switch({"ref": TOPIC, "view": _view("README.md")})
            recorded["switch_same"] = switch({"ref": TOPIC, "view": _view("README.md")})
            recorded["switch_no_view"] = switch({"ref": FEATURE})
            recorded["switch_missing"] = switch({"ref": "refs/remotes/origin/gone"})
    finally:
        serve_mirror(None)
    return stand_in_sandbox(recorded, tmp_path, published.store_key, home=published.home)


def test_recording_is_what_a_served_mirror_answers(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    recorded = _record(tmp_path, monkeypatch)
    branches = recorded["branches"]["body"]
    assert [row["name"] for row in branches["refs"]] == ["topic", "feature"]
    assert branches["refs"][0]["default"] and branches["refs"][0]["current"]
    assert recorded["page"]["body"]["truncated"] is True
    assert recorded["refused"]["status"] == 400
    assert recorded["switch_away"]["body"]["view_href"] == "/view/"
    keep = recorded["switch_keep"]["body"]
    assert (keep["changed"], keep["view_href"]) == (True, recorded["views"]["readme"])
    assert recorded["switch_same"]["body"]["changed"] is False
    assert "view_href" not in recorded["switch_no_view"]["body"]
    assert recorded["switch_missing"]["status"] == 404
    check_recording(RECORDING, recorded, transcript=TRANSCRIPT)


def _record_checkout(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> dict[str, Any]:
    sandbox = tmp_path.resolve()
    admit_installed_git(monkeypatch)
    checkout = build_checkout(sandbox)
    server._set_root_dir(checkout)
    readme = revision_view("README.md")
    recorded: dict[str, Any] = {"views": {"readme": "/view/README.md", "readme_revision": readme}}
    with TestClient(server.app) as client:

        def listing(**params: str) -> dict[str, Any]:
            return answer(client.get("/api/source/refs", params=params))

        def switch(body: dict[str, object]) -> dict[str, Any]:
            return answer(client.post("/api/source/pin", json=body, headers=JSON_BODY))

        recorded["branches"] = listing(kind="branch")
        recorded["tags"] = listing(kind="tag")
        recorded["remotes"] = listing(kind="remote")
        recorded["switch_missing"] = switch({"ref": "refs/heads/gone"})
        recorded["switch_working_tree_same"] = switch(
            {"working_tree": True, "view": "/view/README.md"}
        )
        recorded["switch_branch"] = switch({"ref": "refs/heads/feature", "view": "/view/README.md"})
        recorded["branches_on_revision"] = listing(kind="branch")
        recorded["switch_checked_out"] = switch({"ref": "refs/heads/topic", "view": readme})
        recorded["switch_working_tree"] = switch({"working_tree": True, "view": readme})
    # A folder holding a `.git` that is no repository, whose row the page removes.
    hollow = sandbox / "hollow"
    (hollow / ".git").mkdir(parents=True)
    server._set_root_dir(hollow)
    with TestClient(server.app) as client:
        recorded["not_a_repository"] = answer(client.get("/api/source/refs"))

    # The checkout again, on a Git below the floor.
    def below_the_floor() -> tuple[int, int, int]:
        raise UnsupportedGitVersionError("git version 2.39.2", "2.43.7 or newer")

    monkeypatch.setattr("metabrowser.checkout_revisions.require_acquisition_git", below_the_floor)
    server._set_root_dir(checkout)
    with TestClient(server.app) as client:
        recorded["unsupported_git"] = answer(client.get("/api/source/refs"))
    return stand_in_sandbox(recorded, sandbox)


def test_recording_is_what_a_served_checkout_answers(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    recorded = _record_checkout(tmp_path, monkeypatch)
    assert recorded["not_a_repository"]["body"]["code"] == "unsupported_for_subject"
    assert recorded["unsupported_git"]["body"]["code"] == "unsupported_git"
    branches = recorded["branches"]["body"]
    assert branches["kinds"] == ["branch", "tag", "remote"]
    assert branches["working_tree"] == {
        "current": True,
        "head": "refs/heads/topic",
        "head_name": "topic",
    }
    assert [row["name"] for row in branches["refs"]] == ["topic", "feature", "local-work"]
    assert branches["refs"][0]["checked_out"] and not branches["refs"][0]["current"]
    assert [row["name"] for row in recorded["remotes"]["body"]["refs"]] == [
        "origin/feature",
        "origin/topic",
    ]
    switched = recorded["switch_branch"]["body"]
    assert (switched["changed"], switched["view_href"]) == (
        True,
        recorded["views"]["readme_revision"],
    )
    # The checkout's path is the sandbox's, and stands in as the recording's.
    assert switched["status"]["location"] == "/sandbox/checkout"
    on_revision = recorded["branches_on_revision"]["body"]
    assert on_revision["working_tree"]["current"] is False
    assert [row["name"] for row in on_revision["refs"] if row["current"]] == ["feature"]
    # The checked-out branch is a revision too: a pin, not the working tree.
    assert recorded["switch_checked_out"]["body"]["status"]["subject"] == "git_revision"
    back = recorded["switch_working_tree"]["body"]
    assert (back["status"]["subject"], back["status"]["pin"], back["view_href"]) == (
        "attached_filesystem",
        None,
        recorded["views"]["readme"],
    )
    assert recorded["switch_working_tree_same"]["body"]["changed"] is False
    assert recorded["switch_missing"]["status"] == 404
    check_recording(CHECKOUT_RECORDING, recorded, transcript=TRANSCRIPT)


def test_the_session_runs_a_checkout_on_its_recording() -> None:
    checkout = run_session("source-ref-selector-session.js")["checkout"]
    by_name = {step["step"]: step for step in checkout["steps"]}
    recording = read_recording(CHECKOUT_RECORDING)
    assert by_name["the button names the working tree"]["paint"]["button"] == "Working tree"
    listed = by_name["the working tree is listed above the branches, and is what is served"]
    assert listed["paint"]["workingTree"] == ("Working tree: Live local files, on topic [current]")
    assert listed["paint"]["lists"] == ["branch", "tag", "remote"]
    assert listed["paint"]["rows"][0].startswith("topic ")
    assert "[checked out]" in listed["paint"]["rows"][0]
    assert "[current]" not in listed["paint"]["rows"][0]
    asked = by_name["a branch is asked for by its ref, with the folder's address"]
    body = {"ref": "refs/heads/feature", "view": recording["views"]["readme"]}
    assert asked["requests"] == [f"POST /api/source/pin {json.dumps(body, separators=(',', ':'))}"]
    assert by_name["the page goes to the same file in the revision"]["navigated"] == [
        recording["views"]["readme_revision"]
    ]
    shown = by_name["the branch shown is current, and the working tree no longer is"]["paint"]
    assert shown["workingTree"] == "Working tree: Live local files, on topic"
    assert [row.split()[0] for row in shown["rows"] if "[current]" in row] == ["feature"]
    # The checked-out branch navigates as any ref does; it is not the way back.
    assert by_name["the checked-out branch opens its commit, not the working tree"][
        "navigated"
    ] == [recording["views"]["readme_revision"]]
    way_back = by_name["the working tree is asked for by name, not by a ref"]
    body = {"working_tree": True, "view": recording["views"]["readme_revision"]}
    assert way_back["requests"] == [
        f"POST /api/source/pin {json.dumps(body, separators=(',', ':'))}"
    ]
    assert by_name["the page goes to the same file in the folder"]["navigated"] == [
        recording["views"]["readme"]
    ]
    assert "navigated" not in by_name["choosing the working tree while it is shown only closes"]
    assert by_name["a ref gone from the checkout says so, and nothing is fetched"]["paint"][
        "error"
    ] == ("That ref is no longer in the checkout.")
    assert by_name["a working-tree page left behind offers a reload"]["paint"]["stale"] == (
        "The server now shows another revision [Reload]"
    )
    assert by_name["a revision's page left behind offers one too"]["paint"]["stale"] == (
        "The server now shows the working tree [Reload]"
    )
    assert by_name["a folder Git does not take for a repository loses its row"]["paint"] == {
        "removed": True
    }
    assert (
        by_name["an older Git is refused in the server's words"]["paint"]["error"]
        == (recording["unsupported_git"]["body"]["error"])
    )
    mirror = by_name["a mirror's selector asks for no working tree and offers no reload"]
    assert mirror["requests"] == [] and "stale" not in mirror["paint"]
    assert checkout["labels"] == [
        "Working tree",
        "Branch: feature (local chip)",
        "Remote branch: origin/feature (remote chip)",
        "Tag: v1 (tag chip)",
        f"Commit: {recording['switch_branch']['body']['status']['pin'][:12]}",
    ]
    pin = recording["switch_branch"]["body"]["status"]["pin"]
    refused = "refused when another is served: true; while its own is: false"
    assert checkout["guard"] == {
        "a checkout's working tree": f"working-tree; {refused}",
        "a checkout's revision": f"{pin}; {refused}",
        "a mirror's pin": f"{pin}; {refused}",
        "a plain folder": "nothing",
    }
    # The page's own data requests wait out its switch, and go with the page (mb-bio7).
    tallies = "/api/tree?depth=0 working-tree"
    assert [(step["sent"], step["timers"]) for step in checkout["hold"]] == [
        ([], []),
        ([], [5000]),
        ([tallies, tallies], []),
        ([tallies], []),
        ([tallies], [5000]),
        ([], []),
    ]


def test_the_session_runs_on_the_recording() -> None:
    by_name = {
        step["step"]: step for step in run_session("source-ref-selector-session.js")["steps"]
    }
    recording = read_recording(RECORDING)
    assert by_name["the button names the served branch"]["requests"] == []
    assert by_name["opening asks for the branches"]["requests"] == [
        "GET /api/source/refs?kind=branch"
    ]
    typed = by_name["typing waits for a pause"]
    assert typed["requests"] == [] and typed["filterPending"] is True
    assert by_name["the pause asks once"]["requests"] == ["GET /api/source/refs?kind=branch&q=feat"]
    body = {"ref": FEATURE, "view": recording["views"]["notes"]}
    assert by_name["a switch is under way"]["requests"] == [
        f"POST /api/source/pin {json.dumps(body, separators=(',', ':'))}"
    ]
    away = by_name["a branch without the page's file opens at the root"]
    assert away["navigated"] == ["/view/"]
    kept = by_name["a branch with the page's file keeps it"]
    assert kept["navigated"] == [recording["views"]["readme"]]
    assert "navigated" not in by_name["choosing what the page shows only closes"]
    assert by_name["a page off /view/ names no address and opens at the root"]["navigated"] == [
        "/view/"
    ]
    assert by_name["a ref gone from the mirror says so"]["paint"]["error"] == (
        "That ref is no longer in the mirror."
    )
    aborted = by_name["a newer filter aborts the older request"]
    assert aborted["requests"] == [
        "GET /api/source/refs?kind=branch&q=zzz",
        "aborted GET /api/source/refs?kind=branch&q=zzz",
        "GET /api/source/refs?kind=branch&q=feat",
    ]
    assert aborted["paint"]["query"] == "feat" and aborted["paint"]["error"] is None
    closed = by_name["closing aborts the request on its way"]
    assert closed["requests"][-1].startswith("aborted GET") and closed["paint"]["open"] is False
