"""The ref selector session runs production browser code on what a served mirror answers.

``tests/dom/source-ref-selector-session.js`` drives ``static/source-ref-selector.js`` --
opening, the filter's pause, aborted requests, the branch and tag lists, switching,
and where arrow keys move focus --
through a scripted conversation, and
``tests/golden/cli-ui-source-ref-selector.tryscript.md`` pins its transcript, and
``tests/dom/source-ref-selector-pulls-session.js`` (``cli-ui-source-ref-selector-pulls.tryscript.md``)
the pull requests a branch heads, on the same recording. So that the
conversation is the real server's and not envelopes a test wrote by hand, its responses
come from ``tests/fixtures/source-ref-selector-responses.json``: what the in-process
application answered for the listings and the switches the session plays. The first
test here replays them against a real store and fails when the recording no longer
matches.

The origin is ``tests/source_mirror_fixture.py``'s, written by ``git fast-import``, so
every commit ID is the same on every machine, and its last fetch is recorded at the
fixture's fixed time, so every status envelope is literal. ``make golden-update``
rewrites the recording and then the transcript.

The same module is a served checkout's selector
(``tests/dom/source-ref-selector-checkout-session.js``). Its conversation is recorded the same
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
from metabrowser.builtin_plugins.github.pull_list import ListedRepository
from metabrowser.builtin_plugins.github.ref_pulls import GithubRefPulls, ref_pulls_of
from metabrowser.cache.acquire import acquire_source
from metabrowser.cache.records import StoreOperation
from metabrowser.commit_ids import short_commit
from metabrowser.git.process import UnsupportedGitVersionError
from metabrowser.git.tree_source import GitPath
from metabrowser.mirror_refresh import serve_mirror
from tests.github_pull_fixture import head_item, seed_catalog
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
from tests.source_checkout_fixture import admit_installed_git, build_checkout, git
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


def _record_pull_requests(
    client: TestClient, repository: ListedRepository, monkeypatch: pytest.MonkeyPatch
) -> dict[str, Any]:
    """The listings of a mirror whose repository's pull requests the provider has cached.

    The mirror's origin is a ``file://`` one, which no provider owns, so the route is given
    what the GitHub provider answers for a catalog (``ref_pulls_of``) seeded with real
    publications: the pull requests are the production code's, and so is the envelope. The
    catalog is empty and a job is filling it, then half full and still being filled, then
    whole.
    """

    held: dict[str, Any] = {"refreshing": True}

    async def provided(app: object) -> GithubRefPulls:
        return await asyncio.to_thread(ref_pulls_of, repository, refreshing=held["refreshing"])

    monkeypatch.setattr("metabrowser.cache.providers.ref_pulls_for", provided)

    def listing(**params: str) -> dict[str, Any]:
        return answer(client.get("/api/source/refs", params=params))

    recorded: dict[str, Any] = {"pending": listing(kind="branch")}
    # `topic`, the default, is the head of a merged pull request; `feature` of an open one
    # and an earlier closed one, and of one from a fork, which is another branch of the
    # same name and is not listed.
    items = [
        head_item(12, "topic", "Start the topic", state="closed", merged=True),
        head_item(18, "feature", "Try the first design", state="closed"),
        head_item(21, "feature", "feat(ref): choose among branches"),
        head_item(30, "feature", "From a fork", head_repository="forker/demo"),
    ]
    seed_catalog(repository, items[:2], complete=False, fetched_at="2026-10-01T12:00:00Z")
    recorded["filling"] = listing(kind="branch")
    # A filter while the catalog is half full finds only what is cached, and says so.
    recorded["filling_by_title"] = listing(kind="branch", q="try")
    recorded["filling_nothing"] = listing(kind="branch", q="zzz")
    held["refreshing"] = False
    seed_catalog(repository, items, fetched_at="2026-10-01T12:00:00Z")
    recorded["annotated"] = listing(kind="branch")
    recorded["by_number"] = listing(kind="branch", q="#1")
    recorded["by_title"] = listing(kind="branch", q="start the")
    recorded["tags_with_pulls"] = listing(kind="tag")
    return recorded


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
            page = client.get("/view/").text
            assert 'data-source-mode="local-mirror"' in page
            assert f'data-source-synced-at="{FETCHED_AT}"' in page
            assert "data-source-path=" not in page

            def listing(**params: str) -> dict[str, Any]:
                return answer(client.get("/api/source/refs", params=params))

            def switch(body: dict[str, str]) -> dict[str, Any]:
                return answer(client.post("/api/source/pin", json=body, headers=JSON_BODY))

            recorded["branches"] = listing(kind="branch")
            recorded["tags"] = listing(kind="tag")
            recorded["filtered"] = listing(kind="branch", q="feat")
            recorded["nothing"] = listing(kind="branch", q="zzz")
            recorded["refused"] = listing(kind="commit")
            recorded |= _record_pull_requests(
                client,
                ListedRepository(published.home, published.slug, "octo", "demo"),
                monkeypatch,
            )
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

        recorded["working_tree"] = listing(kind="working_tree")
        recorded["branches"] = listing(kind="branch")
        recorded["tags"] = listing(kind="tag")
        recorded["remotes"] = listing(kind="remote")
        recorded["switch_missing"] = switch({"ref": "refs/heads/gone"})
        recorded["switch_working_tree_same"] = switch(
            {"working_tree": True, "view": "/view/README.md"}
        )
        recorded["switch_branch"] = switch({"ref": "refs/heads/feature", "view": "/view/README.md"})
        recorded["branches_on_revision"] = listing(kind="branch")
        recorded["working_tree_on_revision"] = listing(kind="working_tree")
        recorded["switch_checked_out"] = switch({"ref": "refs/heads/topic", "view": readme})
        recorded["branches_on_checked_out"] = listing(kind="branch")
        recorded["switch_working_tree"] = switch({"working_tree": True, "view": readme})
        # HEAD moved in a terminal after the page was drawn, and then was detached. Each
        # listing reads it from the checkout's files as it answers, well inside the
        # repository's lookup TTL (`GIT_REPO_INFO_TTL_S`): nothing here drops what the
        # server keeps, so a listing that named the branch left would fail below.
        git(checkout, "checkout", "-q", "feature")
        recorded["working_tree_moved"] = listing(kind="working_tree")
        recorded["branches_moved"] = listing(kind="branch")
        git(checkout, "checkout", "-q", "--detach", "topic")
        recorded["working_tree_detached"] = listing(kind="working_tree")
        recorded["branches_detached"] = listing(kind="branch")
        # A switch made on the Commits tab names no address: the page lands on that tab
        # (static/source-ref-selector.js, `switchTo`).
        recorded["switch_from_commits"] = switch({"ref": "refs/heads/feature"})
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
    # The lists in the order of the chooser's tabs, the working tree's first.
    assert branches["kinds"] == ["working_tree", "branch", "remote", "tag"]
    assert branches["working_tree"] == {
        "current": True,
        "head": "refs/heads/topic",
        "head_name": "topic",
        "head_commit": branches["refs"][0]["commit"],
        "name": "checkout",
        # The checkout's path is the sandbox's, and stands in as the recording's.
        "location": "/sandbox/checkout",
    }
    # The working tree's own list has no refs, and says of the working tree what every
    # listing does.
    tree = recorded["working_tree"]["body"]
    assert (tree["kind"], tree["refs"], tree["pull_requests"], tree["origin"]) == (
        "working_tree",
        [],
        None,
        None,
    )
    assert tree["working_tree"] == branches["working_tree"]
    assert recorded["working_tree_on_revision"]["body"]["working_tree"] == {
        **tree["working_tree"],
        "current": False,
    }
    # The origin's default, topic, is first. The rest are newest first: local-work
    # was committed in February, after feature's commit.
    assert [row["name"] for row in branches["refs"]] == ["topic", "local-work", "feature"]
    assert branches["refs"][0]["checked_out"] and not branches["refs"][0]["current"]
    # origin/HEAD names origin/topic. Its older commit still lists above origin/feature.
    assert [row["name"] for row in recorded["remotes"]["body"]["refs"]] == [
        "origin/topic",
        "origin/feature",
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
    # A branch checked out in a terminal is named by the next listing, of either kind,
    # though the server's kept identity of the repository is seconds old: the working
    # tree's own list names it, and Branches moves the checked-out badge to it.
    feature = next(row for row in branches["refs"] if row["name"] == "feature")
    moved = recorded["working_tree_moved"]["body"]["working_tree"]
    assert (moved["head_name"], moved["head_commit"]) == ("feature", feature["commit"])
    listed_moved = recorded["branches_moved"]["body"]
    assert listed_moved["working_tree"] == moved
    assert [row["name"] for row in listed_moved["refs"] if row["checked_out"]] == ["feature"]
    assert [row["name"] for row in listed_moved["refs"]] == ["topic", "local-work", "feature"]
    # A detached HEAD names its commit, and no branch is checked out.
    for name in ("working_tree_detached", "branches_detached"):
        detached = recorded[name]["body"]["working_tree"]
        assert (detached["current"], detached["head"], detached["head_name"]) == (True, None, None)
        assert detached["head_commit"] == branches["refs"][0]["commit"]
    assert not any(row["checked_out"] for row in recorded["branches_detached"]["body"]["refs"])
    # Asked with no address, the answer names none: where the page goes is the page's.
    from_commits = recorded["switch_from_commits"]["body"]
    assert from_commits["status"]["ref"] == "refs/heads/feature"
    assert "view_href" not in from_commits
    check_recording(CHECKOUT_RECORDING, recorded, transcript=TRANSCRIPT)


def test_the_session_runs_a_checkout_on_its_recording() -> None:
    checkout = run_session("source-ref-selector-checkout-session.js")["checkout"]
    by_name = {step["step"]: step for step in checkout["steps"]}
    recording = read_recording(CHECKOUT_RECORDING)
    # The row says it shows the working tree, and which branch the files on disk are on.
    opened = by_name["the button names the working tree and the branch it is on"]["paint"]
    assert opened["button"] == "Working tree · Branch: topic"
    # The list opens on the working tree's tab, which asks for no refs and has one entry.
    asks = by_name["opening asks where the working tree is, and for no refs"]
    assert asks["requests"] == ["GET /api/source/refs?kind=working_tree"]
    listed = by_name["the list opens on the working tree's tab, its one entry current"]["paint"]
    assert (listed["kind"], listed["rows"]) == ("working_tree", [])
    assert listed["workingTree"] == (
        "Working tree on topic: /sandbox/checkout (kept whole: checkout) [current]"
    )
    assert listed["lists"] == ["working_tree", "branch", "remote", "tag"]
    listed = by_name["the checkout's branches, with the checked-out branch marked"]
    assert listed["requests"] == ["GET /api/source/refs?kind=branch"]
    assert listed["paint"]["rows"][0].startswith("topic ")
    assert "[checked out]" in listed["paint"]["rows"][0]
    assert "[current]" not in listed["paint"]["rows"][0]
    # A press on the tab of what the page already shows switches nothing.
    pressed = by_name["a press on Working tree while it is shown only shows its tab"]
    assert pressed["requests"] == ["GET /api/source/refs?kind=working_tree"]
    assert "navigated" not in pressed and pressed["paint"]["kind"] == "working_tree"
    asked = by_name["a branch is asked for by its ref, with the folder's address"]
    body = {"ref": "refs/heads/feature", "view": recording["views"]["readme"]}
    assert asked["requests"] == [f"POST /api/source/pin {json.dumps(body, separators=(',', ':'))}"]
    assert by_name["the page goes to the same file in the revision"]["navigated"] == [
        recording["views"]["readme_revision"]
    ]
    # A page that shows a ref names it alone, and its list opens on that ref's tab.
    named = by_name["the button names the branch shown, and nothing else"]["paint"]
    assert named == {"button": "Branch: feature", "open": False}
    shown = by_name["the list opens on Branches, where the branch shown is current"]
    assert shown["requests"] == ["GET /api/source/refs?kind=branch"]
    shown = shown["paint"]
    assert shown["kind"] == "branch"
    assert shown["workingTree"] == "Working tree on topic: /sandbox/checkout (kept whole: checkout)"
    # An arrow key onto the Working tree tab shows where the files on disk are, and asks
    # the server to switch nothing: the page stays on the branch it shows.
    arrowed = by_name["an arrow key onto Working tree shows its entry and switches nothing"]
    assert arrowed["requests"] == ["GET /api/source/refs?kind=working_tree"]
    assert "navigated" not in arrowed
    assert (arrowed["paint"]["button"], arrowed["paint"]["kind"]) == (
        "Branch: feature",
        "working_tree",
    )
    # The checked-out branch's own revision does not read as its working tree (mb-cxpq).
    checked_out = by_name["the checked-out branch's revision is not its working tree"]["paint"]
    assert checked_out == {"button": "Branch: topic", "open": False}
    assert checked_out["button"] != opened["button"]
    current = by_name["the checked-out branch is current in Branches once it is shown"]["paint"]
    assert [row.split()[0] for row in current["rows"] if "[current]" in row] == ["topic"]
    # The folder's own name is kept whole at the end of its path, whichever separator
    # joined it, and the home directory, `~`, is not cut at all.
    assert checkout["folders"] == {
        "under the home directory": "~/src/[checkout]",
        "with the platform's other separator": "~\\src\\[checkout]",
        "the home directory itself": "[~]",
        "outside the home directory": "/srv/[checkout]",
    }
    assert [row.split()[0] for row in shown["rows"] if "[current]" in row] == ["feature"]
    # The checked-out branch navigates as any ref does; it is not the way back.
    assert by_name["the checked-out branch opens its commit, not the working tree"][
        "navigated"
    ] == [recording["views"]["readme_revision"]]
    # A press on the Working tree tab from a page that shows a ref switches at once.
    pressed = by_name["a press on Working tree asks for the files on disk, not for a ref"]
    body = {"working_tree": True, "view": recording["views"]["readme_revision"]}
    assert pressed["requests"] == [
        f"POST /api/source/pin {json.dumps(body, separators=(',', ':'))}"
    ]
    assert by_name["the page goes to the same file in the folder"]["navigated"] == [
        recording["views"]["readme"]
    ]
    # The chooser heads the Commits tab too. A switch made there names no address, and the
    # page reloads on Commits, at the tab's own landing, which selects the newest commit of
    # the history now served; the row there names the revision chosen.
    assert by_name["a switch on the Commits tab names no address"]["requests"] == [
        'POST /api/source/pin {"ref":"refs/heads/feature"}'
    ]
    assert by_name["the page reloads on the Commits tab's own landing"]["navigated"] == [
        '/view/ {"gitLanding":true}'
    ]
    reloaded = by_name["the reloaded Commits tab's row names the revision chosen there"]
    assert reloaded["paint"]["button"] == "Branch: feature"
    # A switch that failed says why in the list, which every switch is now asked from.
    failed = by_name["a switch that failed says so in the list, which stays open"]["paint"]
    assert (failed["open"], failed["error"]) == (True, "The switch request failed.")
    assert by_name["closing the list clears it"]["paint"] == {
        "button": "Branch: topic",
        "open": False,
    }
    # A checkout in a terminal: the row and its tooltip follow HEAD, in place.
    short = short_commit(recording["working_tree_detached"]["body"]["working_tree"]["head_commit"])
    drawn = by_name["a page drawn before a checkout in a terminal names the branch it was on"]
    asked = by_name["a HEAD that moved asks where it is, and for no refs, with the list closed"]
    fresh = by_name["the row names the branch HEAD is on now, in place"]
    entry = by_name["the open tab's entry names it too"]
    same = by_name["an answer that says the same draws nothing"]
    gone = by_name["a HEAD detached since names its commit, in the row and the entry"]
    assert asked["requests"] == ["GET /api/source/refs?kind=working_tree"]
    assert [(step["paint"]["button"], step["tip"]) for step in (drawn, fresh, gone)] == [
        ("Working tree · Branch: topic", "The files on disk, live. The checkout is on topic."),
        ("Working tree · Branch: feature", "The files on disk, live. The checkout is on feature."),
        (f"Working tree · {short}", f"The files on disk, live. HEAD is detached at {short}."),
    ]
    # The list stayed as it was each time, closed and then open, and the page went nowhere.
    assert (fresh["paint"]["open"], gone["paint"]["open"]) == (False, True)
    assert entry["paint"]["workingTree"].startswith("Working tree on feature: ")
    assert gone["paint"]["workingTree"].startswith(f"Working tree at {short}: ")
    assert same["renders"] == entry["renders"] and gone["renders"] > same["renders"]
    # An open Branches list follows as well: its "checked out" mark is HEAD's.
    before = by_name["Branches as they were listed while HEAD was on feature"]["paint"]
    after = by_name["the open Branches list follows: no branch is checked out"]["paint"]
    assert [row.split()[0] for row in before["rows"] if "[checked out]" in row] == ["feature"]
    assert not any("[checked out]" in row for row in after["rows"])
    # A change heard during a load the reader waits on asks after it, never in its place.
    waiting = by_name["a change heard during a load the reader waits on asks nothing yet"]
    assert waiting["requests"] == ["GET /api/source/refs?kind=tag"]
    assert by_name["and asks again once that load has answered"]["requests"] == [
        "GET /api/source/refs?kind=tag"
    ]
    kept = by_name["a refused ask leaves the row as it was"]
    assert (kept["paint"], kept["renders"]) == (drawn["paint"], drawn["renders"])
    moves = (drawn, asked, fresh, entry, same, gone, before, after, waiting, kept)
    assert not any("navigated" in step for step in moves)
    assert (
        "navigated"
        not in by_name["choosing the working tree's entry while it is shown only closes"]
    )
    assert by_name["a ref gone from the checkout says so, and nothing is fetched"]["paint"][
        "error"
    ] == ("That branch or tag is no longer in the checkout.")
    assert by_name["a working-tree page left behind offers a reload"]["paint"]["stale"] == (
        "The server now shows another revision [Reload page]"
    )
    assert by_name["a revision's page left behind offers one too"]["paint"]["stale"] == (
        "The server now shows the working tree [Reload page]"
    )
    assert by_name["a folder Git does not take for a repository loses its row"]["paint"] == {
        "removed": True
    }
    # Which Git is needed is the answer's `error`, for an agent.
    assert recording["unsupported_git"]["body"]["code"] == "unsupported_git"
    assert by_name["an older Git is refused, and the page says so"]["paint"]["error"] == (
        "Git on this machine is too old to list these. Update Git to see them."
    )
    mirror = by_name["a mirror's selector asks for no working tree and offers no reload"]
    assert mirror["requests"] == [] and "stale" not in mirror["paint"]
    short = short_commit(recording["switch_branch"]["body"]["status"]["pin"])
    # The words are there exactly when the page shows the files on disk; a ref is named
    # alone, as a mirror names one.
    assert checkout["labels"] == [
        "Working tree · Branch: topic (local chip)"
        " | The files on disk, live. The checkout is on topic.",
        f"Working tree · {short} (commit-ID face)"
        f" | The files on disk, live. HEAD is detached at {short}.",
        "Working tree | The files on disk, live.",
        "Branch: feature (local chip) | null",
        "Remote branch: origin/feature (remote chip) | null",
        "Tag: v1 (tag chip) | null",
        f"Commit: {short} (commit-ID face) | null",
    ]
    # The tab a list opens on is the one that holds what the page shows.
    assert checkout["opens"] == {
        "a checkout's working tree": "working_tree",
        "a checkout's branch": "branch",
        "a checkout's remote-tracking branch": "remote",
        "a checkout's tag": "tag",
        "a checkout's commit with no ref": "branch",
        "a mirror's branch": "branch",
        "a mirror's tag": "tag",
        "a mirror's pull request": "branch",
    }
    # The row is one shape whatever the page shows: closed, every step's paint is the
    # label and whether the list is open, and at most the offer to reload a page the
    # server has left. Nothing else is ever in the row to move it.
    closed = [step["paint"] for step in checkout["steps"] if step["paint"].get("open") is False]
    assert len(closed) > 10
    assert all(set(paint) <= {"button", "open", "stale"} for paint in closed)
    pin = recording["switch_branch"]["body"]["status"]["pin"]
    refused = "refused when another is served: true; while its own is: false"
    assert checkout["guard"] == {
        "a checkout's working tree": f"working-tree; {refused}",
        "a checkout's revision": f"{pin}; {refused}",
        "a mirror's pin": f"{pin}; {refused}",
        "a plain folder": "nothing",
    }
    # The page's own data requests wait out its switch, and go with the page (mb-bio7):
    # at once when the page stays, never early because of an earlier switch's bound, and
    # a request given up while held settles at once without being sent.
    tallies = "/api/tree?depth=0 working-tree"
    hold = {step["step"]: step for step in checkout["hold"]}
    assert [step["sent"] for step in checkout["hold"]] == [
        [],
        [],
        [tallies, tallies],
        [tallies],
        [tallies],
        [tallies],
        [],
        [],
        [tallies],
        [],
        [tallies],
        ["/api/source/pin null"],
        ["/api/source/pin null"],
    ]
    assert hold["a second source control cannot post while a ref switch is in flight"][
        "refusal"
    ] == ("selection_busy")
    assert hold["a request made while the switch is asked waits for the answer"]["bounds"] == [5000]
    assert hold["a request given up while it is held settles at once"]["settled"] == "AbortError"


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
        "That branch or tag is no longer in the mirror."
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


def test_the_session_lists_a_branchs_pull_requests_and_asks_while_the_server_fills_them() -> None:
    by_name = {
        step["step"]: step for step in run_session("source-ref-selector-pulls-session.js")["steps"]
    }
    branches = "GET /api/source/refs?kind=branch"
    pending = by_name[
        "pull requests not cached yet: the rows show none, and the list will ask again"
    ]
    # Nothing is cached, and a job fills it: no row has a pull request, the filter says
    # only what it always did, and the list waits to ask again.
    assert pending["requests"] == [branches] and pending["pullsPending"] is True
    assert pending["paint"]["pullRequests"] == "none cached, filling"
    assert "filter" not in pending["paint"]
    assert not any("|" in row for row in pending["paint"]["rows"])
    # Asking again is quiet: nothing is loading, and the rows stay as they were.
    quiet = by_name["asking again shows nothing while it waits"]
    assert quiet["requests"] == [branches] and quiet["paint"]["loading"] is False
    assert "pullsPending" not in quiet
    filling = by_name[
        "a branch shows the pull requests the server has, and it asks again until it has all"
    ]
    assert filling["paint"]["filter"] == "Filter branches or pull requests"
    assert filling["paint"]["pullRequests"] == "partly cached, filling"
    assert filling["paint"]["rows"][1].endswith("| #18 closed Try the first design")
    assert filling["pullsPending"] is True
    # A refusal leaves the rows and stops the asking.
    refused = by_name["an ask that is refused leaves the rows as they are and asks no more"]
    assert refused["paint"]["rows"] == filling["paint"]["rows"] and "pullsPending" not in refused
    # The whole cache: the open pull request first, the other counted, and no more asking.
    full = by_name["a full cache lists each branch's pull requests, open first, and asks no more"]
    assert full["paint"]["pullRequests"] == "cached" and "pullsPending" not in full
    assert full["paint"]["rows"][1].endswith("| #21 open feat(ref): choose among branches +1")
    # The server finds a branch by its pull request, and the list shows what it answers.
    number = by_name["the filter finds a branch by its pull request's number"]
    assert number["requests"] == [f"{branches}&q=%231"]
    assert number["paint"]["rows"][1].endswith("| #18 closed Try the first design +1")
    title = by_name["and by the words of its title, whatever its name says"]
    assert [row.split()[0] for row in title["paint"]["rows"]] == ["topic"]
    tags = by_name["a list of tags has no pull requests, and the filter finds tags"]
    assert "pullRequests" not in tags["paint"] and "filter" not in tags["paint"]
    # Closing the list cancels the wait.
    assert "pullsPending" not in by_name["closing stops asking for pull requests"]


def test_the_session_draws_only_what_an_ask_for_pull_requests_moved() -> None:
    session = run_session("source-ref-selector-pulls-session.js")
    by_name = {step["step"]: step for step in session["steps"]}
    # An ask that finds the same listing draws nothing, so the rows keep their focus, their
    # tooltips, and a press in progress, and it asks again while the server fills (mb-tjbm
    # review A2).
    unchanged = by_name["an ask that finds the listing unchanged draws nothing"]
    assert unchanged["rendered"] == 0 and unchanged["pullsPending"] is True
    # An ask that comes due while a filter is typed asks nothing, and is made again: the
    # filter is asked for with what was typed, as it was, not lost to it (review A9).
    waiting = by_name["an ask that comes due while a filter is typed waits for it"]
    assert waiting["requests"] == [] and waiting["filterPending"] and waiting["pullsPending"]
    found = by_name["the filter finds what is cached, and the list says it may find more"]
    assert found["requests"] == ["GET /api/source/refs?kind=branch&q=try"]
    assert found["paint"]["note"].startswith("Some pull requests are still loading")
    # What a filter finds in a catalog still filling is said not to be all of it (review A8).
    nothing = by_name["a filter that finds nothing says so, and that it may find more later"]
    assert nothing["paint"]["note"].startswith(
        "No branches match. Some pull requests are still loading"
    )
    # Where the list scrolls to when its rows move: the top row stays where it was, the foot
    # stays the foot, and a focused row stays in view (review A1).
    anchors = {line.split(":")[0]: line for line in session["anchors"]}
    top = anchors["the top row stays where it was while rows above it grow"]
    assert "570 -> 660 px" in top and "(its top 560 -> 650)" in top
    assert "2688 -> 2778 px" in anchors["the foot stays the foot, as End left it"]
    assert "560 -> 946 px" in anchors["a focused row in view stays in view"]
    assert "1680 -> 2130 px" in anchors["a focused row out of view is left where it is"]
    assert session["same"] == [
        "the same answer: same",
        "a pull request's title changed: different",
        "the server began filling its pull requests: different",
        "no answer and an answer: different",
        "a row fewer: different",
        # The rows a drawn list keeps and patches: the same refs, whatever pull requests.
        "the same refs with other pull requests: same",
        "a ref's commit moved: different",
        "a row fewer: different",
    ]
