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

import asyncio
import os
import threading
import time
from pathlib import Path
from typing import Any

import pytest
from starlette.testclient import TestClient

from metabrowser import checkout_store, server
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
from tests.required_tools import needs_git

RECORDING = "source-ref-selector-origin-responses.json"
TRANSCRIPT = "cli-ui-source-ref-selector-origin.tryscript.md"
ORIGIN_TRUNK = "refs/remotes/origin/trunk"
VIEW = "/view/m"

pytestmark = [
    pytest.mark.skipif(os.name != "posix", reason="owner-only cache is POSIX-only"),
    needs_git,
]


def _push(work: Path, origin: Path, text: str, *refs: str) -> str:
    pinned_git(work, "checkout", "-q", "trunk")
    (work / "m").write_text(text, encoding="utf-8")
    pinned_git(work, "commit", "-q", "-a", "-m", text.strip())
    pinned_git(work, "push", "-q", str(origin), "trunk", *refs)
    return pinned_git(work, "rev-parse", "HEAD")


def _until(client: TestClient, wanted: str) -> dict[str, Any]:
    """The remote-tracking list once the store is in state *wanted* and nothing fetches."""

    deadline = time.monotonic() + 240
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
        await asyncio.to_thread(gate.wait)
        return await acquire(*args, **kwargs)

    fetch_gate = threading.Event()
    fetch_gate.set()
    from metabrowser.cache import served_mirror

    update = served_mirror.update_store

    async def held_fetch(*args: Any, **kwargs: Any) -> Any:
        await asyncio.to_thread(fetch_gate.wait)
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
            recorded["branches"] = listing(client, "branch")
            recorded["tags"] = listing(client, "tag")
            # Just fetched: a visible page's own ask finds nothing due.
            recorded["ask_fresh"] = post(client, "/api/source/refresh", {"for": "page"})
            # An hour on, the origin has moved: the ask starts a fetch, held while the
            # list is asked for again.
            recorded["moved"] = _push(work, replica.origin, "m7\n")
            isolated.clock.advance(3600)
            fetch_gate.clear()
            recorded["ask_started"] = post(client, "/api/source/refresh", {"for": "page"})
            recorded["remotes_fetching"] = listing(client, "remote")
            fetch_gate.set()
            recorded["remotes_fetched"] = _until(client, "ready")
            recorded["switch_origin_branch"] = post(
                client, "/api/source/pin", {"ref": ORIGIN_TRUNK, "view": VIEW}
            )
            recorded["remotes_on_origin_branch"] = listing(client, "remote")
    finally:
        gate.set()
        fetch_gate.set()
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
    # The replica's commits share one pinned date, so the rows read by name. The origin's
    # trunk is where the origin has it, not where the checkout's last fetch left it.
    assert [row["name"] for row in ready["refs"]] == ["origin/feature", "origin/trunk"]
    assert ready["refs"][1]["commit"] != absent["refs"][0]["commit"]
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
    assert fetched["refs"][1]["commit"] == recorded["moved"]
    assert fetched["origin"]["last_fetch_at"] != ready["origin"]["last_fetch_at"]
    switched = recorded["switch_origin_branch"]["body"]
    assert switched["status"]["pin"] == recorded["moved"]
    assert switched["status"]["refreshable"] is True
    assert switched["status"]["location"] == "/sandbox/checkout"
    on_branch = recorded["remotes_on_origin_branch"]["body"]
    assert [row["name"] for row in on_branch["refs"] if row["current"]] == ["origin/trunk"]
    check_recording(RECORDING, recorded, transcript=TRANSCRIPT)


def test_the_session_reads_the_origin_from_the_store_and_asks_as_a_visible_page() -> None:
    session = run_session("source-ref-selector-origin-session.js")
    recording = read_recording(RECORDING)
    by_name = {step["step"]: step for step in session["steps"]}
    opened = by_name["an open list of a checkout makes a visible page's own ask, once"]
    assert opened["requests"] == [
        "GET /api/source/refs?kind=branch",
        'POST /api/source/refresh {"for":"page"}',
    ]
    # The checkout's own branches read no store, so that list says nothing of one.
    assert "origin" not in opened["paint"]
    remotes = by_name[
        "the origin's branches are the store's, and the list says when it was fetched"
    ]
    fetched_at = recording["remotes"]["body"]["origin"]["last_fetch_at"]
    assert remotes["paint"]["origin"] == (
        f"The origin's branches are as Metabrowser last fetched them (fetched {fetched_at}) [quiet]"
    )
    assert [row.split(" ")[0] for row in remotes["paint"]["rows"]] == [
        "origin/feature",
        "origin/trunk",
    ]
    asked = by_name["a fetch the ask started is followed: the list is asked for again"]
    assert asked["requests"] == ["GET /api/source/refs?kind=remote"]
    waiting = by_name["while the store is fetched, the open list asks again after a wait"]
    assert waiting["pullsPending"] is True
    moved = by_name["the fetch ended: the origin's branch moved, and nothing more is asked"]
    assert recording["moved"].startswith(moved["paint"]["rows"][1].split(" ")[1])
    assert "pullsPending" not in moved
    chosen = by_name["an origin branch is asked for by its ref"]
    assert chosen["requests"] == [
        'POST /api/source/pin {"ref":"refs/remotes/origin/trunk","view":"/view/m"}'
    ]
    refused = by_name["an origin that needs credentials is not fetched, and the list says why"]
    assert refused["paint"]["origin"].startswith("Origin not fetched. The origin was not found")
    assert refused["paint"]["origin"].endswith("These are the checkout's own. [warning]")
    # The mirror's session and a checkout with no store paint no such line.
    assert session["quietWithoutAStore"] == {"asked": [], "origin": None}
