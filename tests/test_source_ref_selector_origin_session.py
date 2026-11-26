"""The ref selector on a checkout that keeps a store of its origin, on recorded answers.

``tests/dom/source-ref-selector-origin-session.js`` drives the production
``static/source-ref-selector.js`` through a folder's conversation with the store
Metabrowser keeps beside its checkout (``metabrowser/checkout_store.py``): the line that
says where the origin's branches and tags are read from and when they were fetched, the
visible page's own ask an open list makes, the list asked for again while that fetch
runs, an origin branch chosen, and an origin that is not fetched, with the reason.

Every answer the session replays is one the in-process application gave for a real
checkout, recorded here in ``tests/fixtures/source-ref-selector-origin-responses.json``:
a replica from ``tests/checkout_replica.py`` whose origin moved on after the clone, so
the checkout's own ``origin/trunk`` is behind the origin's. This module fails when the
recording drifts from what the server answers, so the session never runs on an envelope
a test wrote by hand; ``tests/golden/cli-ui-source-ref-selector-origin.tryscript.md``
pins what the session prints.
"""

from __future__ import annotations

import os
import threading
import time
from pathlib import Path
from typing import Any

import pytest
from starlette.testclient import TestClient

from metabrowser import checkout_store, server
from metabrowser.checkout_revisions import CHECKOUT_REFS_POLL_S
from metabrowser.checkout_store import CheckoutStoreError, serve_checkout_store
from tests.checkout_replica import build_linear, clone_checkout
from tests.golden_harness import (
    JSON_BODY,
    answer,
    check_recording,
    isolate_cli,
    pinned_git,
    read_recording,
    run_session,
    stand_in_sandbox,
)
from tests.loop_gate import held_until
from tests.required_tools import needs_git
from tests.source_checkout_fixture import read_refs_at_every_ask

RECORDING = "source-ref-selector-origin-responses.json"
TRANSCRIPT = "cli-ui-source-ref-selector-origin.tryscript.md"
ORIGIN_TRUNK = "refs/remotes/origin/trunk"
LOCAL_TRUNK = "refs/heads/trunk"
LOCAL_TOPIC = "refs/heads/topic"
VIEW = "/view/m"

pytestmark = [
    pytest.mark.skipif(os.name != "posix", reason="owner-only cache is POSIX-only"),
    needs_git,
    # The recording is a served checkout's with a store, which the suite's environment
    # keeps from every application (``tests/conftest.py``).
    pytest.mark.usefixtures("keeps_origin_store"),
]


def _push(work: Path, origin: Path, text: str, *refs: str) -> str:
    pinned_git(work, "checkout", "-q", "trunk")
    (work / "m").write_text(text, encoding="utf-8")
    pinned_git(work, "commit", "-q", "-a", "-m", text.strip())
    pinned_git(work, "push", "-q", str(origin), "trunk", *refs)
    return pinned_git(work, "rev-parse", "HEAD")


def _until(client: TestClient, wanted: str) -> dict[str, Any]:
    """The remote-tracking list once the store is in state *wanted* and nothing fetches."""

    deadline = time.monotonic() + 30
    while True:
        listed = client.get("/api/source/refs", params={"kind": "remote"})
        origin = listed.json()["origin"]
        if origin["state"] == wanted and (wanted == "acquiring" or not origin["refreshing"]):
            return answer(listed)
        assert time.monotonic() < deadline, origin
        time.sleep(0.05)


def _record(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> dict[str, Any]:
    sandbox = tmp_path.resolve()
    isolated = isolate_cli(sandbox, monkeypatch)
    # Each page ask below comes right after the commit it is about.
    read_refs_at_every_ask(monkeypatch)
    replica = build_linear(sandbox)
    checkout = clone_checkout(replica, sandbox / "checkout")
    pinned_git(checkout, "tag", "local-only")
    work = sandbox / "source"
    pinned_git(work, "checkout", "-q", "-b", "feature", replica["M3"])
    (work / "feature.txt").write_text("feature\n", encoding="utf-8")
    pinned_git(work, "add", "feature.txt")
    pinned_git(work, "commit", "-q", "-m", "F1")
    pinned_git(work, "tag", "v2", replica["M4"])
    _push(work, replica.origin, "m6\n", "feature", "v2")
    monkeypatch.setattr("metabrowser.cache.acquire.remote_url_for", lambda _source: replica.url)
    recorded: dict[str, Any] = {"views": {"m": VIEW}}

    def listing(client: TestClient, kind: str) -> dict[str, Any]:
        return answer(client.get("/api/source/refs", params={"kind": kind}))

    def post(client: TestClient, route: str, body: dict[str, Any]) -> dict[str, Any]:
        return answer(client.post(route, json=body, headers=JSON_BODY))

    # A command that only reads: no store yet, and none made.
    server._set_root_dir(checkout)  # pyright: ignore[reportPrivateUsage]
    with TestClient(server.app) as client:
        recorded["not_fetched_remotes"] = listing(client, "remote")

    # A server whose origin refuses: private, and no credentials for it.
    acquire = checkout_store.acquire_checkout_store

    async def refused(*_args: Any, **_kwargs: Any) -> Any:
        raise CheckoutStoreError("not_found_or_private", "the repository could not be read")

    with monkeypatch.context() as scoped:
        scoped.setattr(checkout_store, "acquire_checkout_store", refused)
        server._set_root_dir(checkout)  # pyright: ignore[reportPrivateUsage]
        serve_checkout_store()
        with TestClient(server.app) as client:
            recorded["refused_remotes"] = _until(client, "absent")
            recorded["ask_refused"] = post(client, "/api/source/refresh", {"for": "page"})

    # A server that makes the store, held at its first fetch and then let go.
    gate = threading.Event()

    async def held(*args: Any, **kwargs: Any) -> Any:
        await held_until(gate, 30)
        return await acquire(*args, **kwargs)

    fetch_gate = threading.Event()
    fetch_gate.set()
    from metabrowser.cache import served_mirror

    update = served_mirror.update_store

    failing: list[bool] = []

    async def held_fetch(*args: Any, **kwargs: Any) -> Any:
        await held_until(fetch_gate, 30)
        if failing:
            raise OSError("the fetch could not run")
        return await update(*args, **kwargs)

    monkeypatch.setattr(checkout_store, "acquire_checkout_store", held)
    monkeypatch.setattr(served_mirror, "update_store", held_fetch)
    server._set_root_dir(checkout)  # pyright: ignore[reportPrivateUsage]
    serve_checkout_store()
    try:
        with TestClient(server.app) as client:
            recorded["acquiring_remotes"] = _until(client, "acquiring")
            gate.set()
            recorded["remotes"] = _until(client, "ready")
            recorded["working_tree"] = listing(client, "working_tree")
            recorded["branches"] = listing(client, "branch")
            recorded["tags"] = listing(client, "tag")
            # Just fetched: a visible page's own ask finds nothing due.
            recorded["ask_fresh"] = post(client, "/api/source/refresh", {"for": "page"})
            # What the freshness row of the folder's pages reads: the working tree's
            # status, which says how fresh the store of the origin is.
            recorded["status_working_tree"] = client.get("/api/source/status").json()
            # An hour on, the origin has moved: the ask starts a fetch, held while the
            # list is asked for again.
            recorded["moved"] = _push(work, replica.origin, "m7\n")
            isolated.clock.advance(3600)
            recorded["status_stale"] = client.get("/api/source/status").json()
            fetch_gate.clear()
            recorded["ask_started"] = post(client, "/api/source/refresh", {"for": "page"})
            recorded["remotes_fetching"] = listing(client, "remote")
            fetch_gate.set()
            recorded["remotes_fetched"] = _until(client, "ready")
            # A reader's own Refresh on the working tree's page, held and then let end.
            fetch_gate.clear()
            recorded["refresh_started"] = post(client, "/api/source/refresh", {})
            fetch_gate.set()
            _until(client, "ready")
            recorded["status_refreshed"] = client.get("/api/source/status").json()
            recorded["switch_origin_branch"] = post(
                client, "/api/source/pin", {"ref": ORIGIN_TRUNK, "view": VIEW}
            )
            recorded["remotes_on_origin_branch"] = listing(client, "remote")
            # An hour on, the origin branch's page finds the store grown old. It shows the
            # store, so its ask is the loud one, held while the status is read.
            isolated.clock.advance(3600)
            recorded["status_origin_branch_stale"] = client.get("/api/source/status").json()
            fetch_gate.clear()
            recorded["origin_branch_refresh_started"] = post(client, "/api/source/refresh", {})
            fetch_gate.set()
            _until(client, "ready")
            # The checkout's own branch follows the checkout: the reader commits on it,
            # a visible page's own ask reads the refs and finds the commit, and the page
            # asks the pin route where it is on that commit.
            on_origin = recorded["switch_origin_branch"]["body"]["view_href"]
            local = post(client, "/api/source/pin", {"ref": LOCAL_TRUNK, "view": on_origin})
            recorded["switch_local_branch"] = local
            pinned_git(checkout, "commit", "-q", "--allow-empty", "-m", "local")
            recorded["committed"] = pinned_git(checkout, "rev-parse", "HEAD")
            recorded["ask_local_moved"] = post(client, "/api/source/refresh", {"for": "page"})
            recorded["follow_local_branch"] = post(
                client, "/api/source/pin", {"ref": LOCAL_TRUNK, "view": local["body"]["view_href"]}
            )
            # Back on the working tree, a Refresh that fails.
            post(client, "/api/source/pin", {"working_tree": True})
            failing.append(True)
            post(client, "/api/source/refresh", {})
            _until(client, "ready")
            recorded["status_refresh_failed"] = client.get("/api/source/status").json()
            failing.clear()
    finally:
        gate.set()
        fetch_gate.set()

    # A checkout whose origin is on this machine keeps no store, so nothing of it is
    # refreshable; a page on its own branch follows that branch all the same.
    plain = sandbox / "plain"
    pinned_git(sandbox, "clone", "-q", replica.url, str(plain))
    server._set_root_dir(plain)  # pyright: ignore[reportPrivateUsage]
    with TestClient(server.app) as client:
        local = post(client, "/api/source/pin", {"ref": LOCAL_TRUNK, "view": VIEW})
        recorded["plain_switch"] = local
        recorded["plain_ask"] = post(client, "/api/source/refresh", {"for": "page"})
        pinned_git(plain, "commit", "-q", "--allow-empty", "-m", "plain")
        recorded["plain_ask_moved"] = post(client, "/api/source/refresh", {"for": "page"})
        recorded["plain_follow"] = post(
            client, "/api/source/pin", {"ref": LOCAL_TRUNK, "view": local["body"]["view_href"]}
        )
        recorded["plain_follow_refused"] = post(
            client, "/api/source/pin", {"ref": "refs/heads/gone", "view": VIEW}
        )
        # A branch the reader deletes while its page is shown: its last commit stays.
        pinned_git(plain, "branch", "topic")
        recorded["plain_topic"] = post(client, "/api/source/pin", {"ref": LOCAL_TOPIC})
        pinned_git(plain, "branch", "-D", "topic")
        recorded["plain_ask_gone"] = post(client, "/api/source/refresh", {"for": "page"})
    return stand_in_sandbox(recorded, sandbox, home=isolated.home)


def test_recording_is_what_a_served_checkout_with_a_store_answers(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    recorded = _record(tmp_path, monkeypatch)
    absent = recorded["not_fetched_remotes"]["body"]
    assert (absent["origin"]["state"], absent["origin"]["reason"]) == ("absent", "not_fetched")
    assert [row["name"] for row in absent["refs"]] == ["origin/trunk"]
    refused = recorded["refused_remotes"]["body"]["origin"]
    assert (refused["state"], refused["reason"]) == ("absent", "not_found_or_private")
    assert recorded["ask_refused"]["body"]["refresh"] == "not_due"
    assert recorded["acquiring_remotes"]["body"]["origin"]["refreshing"] is True
    ready = recorded["remotes"]["body"]
    assert ready["origin"]["state"] == "ready"
    # The origin's default branch first, and marked. Its trunk is where the origin has it,
    # not where the checkout's last fetch left it.
    assert [(row["name"], row["default"]) for row in ready["refs"]] == [
        ("origin/trunk", True),
        ("origin/feature", False),
    ]
    assert ready["refs"][0]["commit"] != absent["refs"][0]["commit"]
    # Each says where the reader's own ref is: behind on trunk, and none for feature.
    assert ready["refs"][0]["checkout"]["commit"] == absent["refs"][0]["commit"]
    assert ready["refs"][1]["checkout"] == {"commit": None, "committed_at": None}
    assert all("checkout" not in row for row in recorded["branches"]["body"]["refs"])
    # The working tree's status says how fresh the store is, and can refresh it.
    assert recorded["ask_fresh"]["body"]["status"]["refreshable"] is True
    assert recorded["ask_fresh"]["body"]["status"]["subject"] == "attached_filesystem"
    assert [row["name"] for row in recorded["tags"]["body"]["refs"]] == ["local-only", "v2"]
    assert (recorded["ask_fresh"]["status"], recorded["ask_fresh"]["body"]["refresh"]) == (
        200,
        "not_due",
    )
    assert (recorded["ask_started"]["status"], recorded["ask_started"]["body"]["refresh"]) == (
        202,
        "started",
    )
    assert recorded["remotes_fetching"]["body"]["origin"]["refreshing"] is True
    fetched = recorded["remotes_fetched"]["body"]
    assert fetched["refs"][0]["commit"] == recorded["moved"]
    assert fetched["origin"]["last_fetch_at"] != ready["origin"]["last_fetch_at"]
    assert recorded["status_stale"]["stale"] is True
    started = recorded["refresh_started"]["body"]
    assert (started["refresh"], started["status"]["refreshing"]) == ("started", True)
    assert started["status"]["refresh_quiet"] is False
    assert recorded["status_refresh_failed"]["last_outcome"]["outcome"] == "failed"
    switched = recorded["switch_origin_branch"]["body"]
    assert switched["status"]["pin"] == recorded["moved"]
    assert switched["status"]["refreshable"] is True and switched["read_from"] == "origin"
    assert switched["status"]["location"] == "/sandbox/checkout"
    on_branch_stale = recorded["status_origin_branch_stale"]
    assert (on_branch_stale["stale"], on_branch_stale["follows"]) == (True, True)
    assert on_branch_stale["ref"] == switched["status"]["ref"]
    loud = recorded["origin_branch_refresh_started"]
    assert (loud["status"], loud["body"]["refresh"]) == (202, "started")
    assert (loud["body"]["status"]["refreshing"], loud["body"]["status"]["follows"]) == (True, True)
    on_branch = recorded["remotes_on_origin_branch"]["body"]
    assert [row["name"] for row in on_branch["refs"] if row["current"]] == ["origin/trunk"]
    # The checkout's own branch follows the checkout, with a store and without one.
    local = recorded["switch_local_branch"]["body"]["status"]
    assert (local["ref"], local["follows"], local["refreshable"]) == (LOCAL_TRUNK, True, True)
    assert local["probe_every_s"] == CHECKOUT_REFS_POLL_S
    moved = recorded["ask_local_moved"]
    assert (moved["status"], moved["body"]["refresh"]) == (200, "probed")
    assert moved["body"]["status"]["pin"] == recorded["committed"] != local["pin"]
    followed = recorded["follow_local_branch"]["body"]
    assert followed["changed"] is False
    assert followed["view_href"] == recorded["switch_local_branch"]["body"]["view_href"]
    plain = recorded["plain_switch"]["body"]["status"]
    assert (plain["follows"], plain["refreshable"]) == (True, False)
    assert plain["probe_every_s"] == CHECKOUT_REFS_POLL_S
    assert recorded["plain_ask"]["body"]["status"]["pin"] == plain["pin"]
    assert recorded["plain_ask_moved"]["body"]["status"]["pin"] != plain["pin"]
    assert recorded["plain_follow_refused"]["status"] == 404
    topic = recorded["plain_topic"]["body"]["status"]
    gone = recorded["plain_ask_gone"]["body"]["status"]
    assert (gone["pin"], gone["ref"], gone["follows"]) == (topic["pin"], LOCAL_TOPIC, True)
    assert (gone["latest"], gone["ref_on_origin"]) == (None, None)
    check_recording(RECORDING, recorded, transcript=TRANSCRIPT)


def test_the_session_reads_the_origin_from_the_store_and_asks_as_a_visible_page() -> None:
    session = run_session("source-ref-selector-origin-session.js")
    recording = read_recording(RECORDING)
    by_name = {step["step"]: step for step in session["steps"]}
    opened = by_name["the checkout's own branches read no store, so their list asks nothing"]
    assert opened["requests"] == ["GET /api/source/refs?kind=branch"]
    assert "origin" not in opened["paint"]
    remotes = by_name[
        "the origin's branches are the store's, and the list says when it was fetched"
    ]
    fetched_at = recording["remotes"]["body"]["origin"]["last_fetch_at"]
    assert remotes["paint"]["origin"] == (
        f"The origin's branches are as Metabrowser last fetched them (fetched {fetched_at}) [quiet]"
    )
    # The list that reads the store makes the visible page's own ask, once for the opening.
    assert remotes["requests"] == [
        "GET /api/source/refs?kind=remote",
        'POST /api/source/refresh {"for":"page"}',
    ]
    tags = by_name["the origin's tags are the store's, beside the tag only the checkout has"]
    assert tags["requests"] == ["GET /api/source/refs?kind=tag"]
    assert [row.split(" ")[0] for row in remotes["paint"]["rows"]] == [
        "origin/trunk",
        "origin/feature",
    ]
    assert "[default]" in remotes["paint"]["rows"][0]
    asked = by_name["a fetch the ask started is followed: the list is asked for again"]
    assert asked["requests"] == ["GET /api/source/refs?kind=remote"]
    waiting = by_name["while the store is fetched, the open list asks again after a wait"]
    assert waiting["pullsPending"] is True
    moved = by_name["the fetch ended: the origin's branch moved, and nothing more is asked"]
    assert recording["moved"].startswith(moved["paint"]["rows"][0].split(" ")[1])
    assert "pullsPending" not in moved
    # The navigation's Refresh. An open list is read again, and one that says the same is
    # not drawn; on this working tree's page the origin's fetch is asked for as the
    # reader's own, which names no purpose, and the open list follows it to its end.
    reread = by_name["Refresh reads the open list again, and one that says the same is not drawn"]
    assert (reread["requests"], reread["drawnAgain"]) == (["GET /api/source/refs?kind=remote"], 0)
    fetch = by_name["Refresh asks for the origin's fetch, as the reader's own"]
    assert fetch["requests"] == ["POST /api/source/refresh {}"]
    followed = by_name["the fetch started, so the open list is asked for again"]
    assert followed["requests"] == ["GET /api/source/refs?kind=remote"]
    assert by_name["the list says the fetch runs, and waits to ask again"]["pullsPending"] is True
    ended = by_name["the fetch ended, and the list is the origin's as just fetched"]
    assert ended["requests"] == ["GET /api/source/refs?kind=remote"]
    assert "pullsPending" not in ended and ended["paint"]["rows"] == moved["paint"]["rows"]
    # A closed list is fetched for and lists nothing.
    behind = by_name["with the list closed, Refresh fetches and lists nothing"]
    assert behind["requests"] == ["POST /api/source/refresh {}"]
    chosen = by_name["an origin branch is asked for by its ref"]
    assert chosen["requests"] == [
        'POST /api/source/pin {"ref":"refs/remotes/origin/trunk","view":"/view/m"}'
    ]
    refused = by_name["an origin that needs credentials is not fetched, and the list says so"]
    # Why is the answer's `detail`, for an agent; the line says only that it is not fetched.
    assert refused["paint"]["origin"].startswith("Origin not fetched.")
    assert refused["paint"]["origin"].endswith("These are the checkout's own. [warning]")
    # The mirror's session and a checkout with no store paint no such line.
    assert session["quietWithoutAStore"] == {"asked": [], "origin": None}
    # A row whose branch the reader's checkout has elsewhere, or not at all, says so.
    assert "[yours differs]" in remotes["paint"]["rows"][0]
    assert "[not in checkout]" in remotes["paint"]["rows"][1]
    # The tip names no commit: the row says which (docs/design-system-messages.md).
    assert remotes["paint"]["own"][0].startswith(
        "origin/trunk: Your checkout's origin/trunk is at another commit."
    )
    own = session["ownDifference"]
    assert own["asRecorded"][0].startswith("yours differs: ")
    assert own["asRecorded"][1].startswith("not in checkout: Your checkout has no origin/feature")
    assert " is at an earlier commit by date." in own["yoursEarlier"]
    assert " is at a later commit by date." in own["yoursLater"]
    assert own["ownBranches"] == [None] * len(recording["branches"]["body"]["refs"])
