"""A repository folder's own store of its origin (``metabrowser/checkout_store.py``).

A folder served from a checkout lists its origin's branches and tags from a store
Metabrowser keeps beside the checkout, as it last fetched them, and serves one from that
store. The checkout is never written: every test that makes, fetches, probes, or reads
the store compares every entry under the checkout's ``.git``, and its working tree,
before and after.

The origin is a replica from ``tests/checkout_replica.py``: a bare ``file://`` repository
standing in for ``https://github.com/octo/demo``, which the checkout's ``origin`` names
as a real one does, while ``remote_url_for`` fetches from the local one.
"""

from __future__ import annotations

import asyncio
import hashlib
import itertools
import time
from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from unittest.mock import patch

import pytest
from starlette.testclient import TestClient

from metabrowser import checkout_store, server
from metabrowser.checkout_revisions import CHECKOUT_REFS_POLL_S
from metabrowser.checkout_store import (
    ABSENCE_DETAIL,
    CheckoutStoreError,
    serve_checkout_store,
    store_turn,
)
from metabrowser.mirror_refresh import STORE_PROBE_S
from tests.checkout_replica import Replica, build_linear, clone_checkout, fingerprint
from tests.golden_harness import FixedClock, isolate_cli, pinned_git
from tests.loop_gate import held_until
from tests.required_tools import needs_git
from tests.source_checkout_fixture import read_refs_at_every_ask
from tests.test_serve_pin import posix_only

# Every test here keeps a store, which the suite's environment keeps from any application
# (``tests/conftest.py``); those of the environment itself set it as they need.
pytestmark = [posix_only, needs_git, pytest.mark.usefixtures("keeps_origin_store")]

_JSON = {"content-type": "application/json"}
_ORIGIN_TRUNK = "refs/remotes/origin/trunk"


@dataclass(frozen=True, slots=True)
class _Folder:
    """A checkout that is behind its origin, the origin, and the application home."""

    checkout: Path
    replica: Replica
    home: Path
    clock: FixedClock
    # What the checkout has of the origin's trunk, and where the origin is now.
    behind: str
    ahead: str
    feature: str

    @property
    def source(self) -> Path:
        return self.replica.origin.parent / "source"


def _push(replica: Replica, name: str, *refs: str) -> str:
    """Commit *name* on the origin's trunk from its source repository, and push *refs*."""

    work = replica.origin.parent / "source"
    pinned_git(work, "checkout", "-q", "trunk")
    (work / name).write_text(f"{name}\n", encoding="utf-8")
    pinned_git(work, "add", name)
    pinned_git(work, "commit", "-q", "-m", name)
    pinned_git(work, "push", "-q", str(replica.origin), "trunk", *refs)
    return pinned_git(work, "rev-parse", "HEAD")


def _working_tree(checkout: Path) -> dict[str, str]:
    """Every file of the working tree outside ``.git``, by its bytes."""

    return {
        path.relative_to(checkout).as_posix(): hashlib.sha256(path.read_bytes()).hexdigest()
        for path in sorted(checkout.rglob("*"))
        if path.is_file() and ".git" not in path.relative_to(checkout).parts
    }


@pytest.fixture
def folder(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> _Folder:
    """A checkout of the replica, then an origin that moved on: a commit, a branch, a tag."""

    sandbox = isolate_cli(tmp_path, monkeypatch)
    directory = tmp_path.resolve() / "replica"
    directory.mkdir()
    replica = build_linear(directory)
    checkout = clone_checkout(replica, tmp_path.resolve() / "checkout")
    pinned_git(checkout, "tag", "local-only")
    behind = replica["M5"]
    work = directory / "source"
    pinned_git(work, "checkout", "-q", "-b", "feature", replica["M3"])
    (work / "feature.txt").write_text("feature\n", encoding="utf-8")
    pinned_git(work, "add", "feature.txt")
    pinned_git(work, "commit", "-q", "-m", "F1")
    feature = pinned_git(work, "rev-parse", "HEAD")
    pinned_git(work, "checkout", "-q", "trunk")
    pinned_git(work, "tag", "v2", replica["M4"])
    ahead = _push(replica, "m6", "feature", "v2")
    monkeypatch.setattr("metabrowser.cache.acquire.remote_url_for", lambda _source: replica.url)
    return _Folder(checkout, replica, sandbox.home, sandbox.clock, behind, ahead, feature)


def _refs(client: TestClient, kind: str) -> dict[str, Any]:
    response = client.get(f"/api/source/refs?kind={kind}")
    assert response.status_code == 200, response.text
    return response.json()


def _ready(client: TestClient, *, timeout_s: float = 30.0) -> dict[str, Any]:
    """The listing of remote-tracking branches once the store exists and nothing fetches."""

    deadline = time.monotonic() + timeout_s
    while True:
        listing = _refs(client, "remote")
        origin = listing["origin"]
        if origin is not None and origin["state"] == "ready" and not origin["refreshing"]:
            return listing
        assert origin is None or origin["state"] != "absent", origin
        assert time.monotonic() < deadline, f"the store was never made: {origin}"
        time.sleep(0.05)


def _by_name(listing: dict[str, Any]) -> dict[str, str]:
    return {row["name"]: row["commit"] for row in listing["refs"]}


def _post(client: TestClient, route: str, body: dict[str, Any] | None = None) -> Any:
    return client.post(route, json={} if body is None else body, headers=_JSON)


@pytest.fixture
def served(folder: _Folder) -> Iterator[TestClient]:
    """A server on the checkout, which keeps the store as ``metab PATH`` does."""

    server._set_root_dir(folder.checkout)  # pyright: ignore[reportPrivateUsage]
    serve_checkout_store()
    with TestClient(server.app) as client:
        yield client


# ── The list ─────────────────────────────────────────────────────────


def test_a_served_checkout_lists_its_origins_refs_from_metabrowsers_own_store(
    folder: _Folder, served: TestClient
) -> None:
    """The origin's branches and tags are the origin's as Metabrowser fetched them, not
    where the reader's own last fetch left ``origin/*``; the checkout's own are its own."""

    before = fingerprint(folder.checkout)
    tree = _working_tree(folder.checkout)
    listing = _ready(served)
    assert listing["origin"]["address"] == "https://github.com/octo/demo"
    assert listing["origin"]["reason"] is None
    assert listing["origin"]["last_fetch_at"] is not None
    remote = _by_name(listing)
    # The checkout never fetched these: its own origin/trunk is still at M5.
    assert pinned_git(folder.checkout, "rev-parse", _ORIGIN_TRUNK) == folder.behind
    assert remote == {"origin/trunk": folder.ahead, "origin/feature": folder.feature}
    assert all(row["ref"].startswith("refs/remotes/origin/") for row in listing["refs"])
    assert not any(row["checked_out"] for row in listing["refs"])
    tags = _by_name(_refs(served, "tag"))
    assert tags == {"v2": folder.replica["M4"], "local-only": folder.behind}
    # The checkout's own branches are read from the checkout, as before.
    branches = _refs(served, "branch")
    assert _by_name(branches) == {"trunk": folder.behind}
    assert branches["refs"][0]["checked_out"] is True
    assert branches["origin"]["state"] == "ready"
    assert fingerprint(folder.checkout) == before
    assert _working_tree(folder.checkout) == tree


def test_an_origin_branch_says_where_the_readers_own_ref_is_when_it_differs(
    folder: _Folder, served: TestClient
) -> None:
    """The row is the origin's branch as Metabrowser fetched it. Where the checkout's own
    `origin/<branch>` is another commit, or the checkout has none, the row says so, and
    stops saying so once the reader's own fetch has brought it."""

    rows = {row["name"]: row for row in _ready(served)["refs"]}
    trunk = rows["origin/trunk"]
    # The origin's trunk is at M6; the reader's last fetch left theirs at M5. Both commits'
    # dates are in the row, for the page to say which is the later; the replica pins
    # every commit to one date.
    assert trunk["commit"] == folder.ahead
    assert trunk["checkout"] == {"commit": folder.behind, "committed_at": trunk["committed_at"]}
    assert isinstance(trunk["committed_at"], float)
    # A branch the reader never fetched: the checkout has no such ref.
    assert rows["origin/feature"]["checkout"] == {"commit": None, "committed_at": None}
    # A filter keeps the mark, and no other list has one.
    assert _refs(served, "remote&q=trunk")["refs"][0]["checkout"] == trunk["checkout"]
    for kind in ("branch", "tag"):
        assert all("checkout" not in row for row in _refs(served, kind)["refs"])

    # The reader fetches: their refs are the origin's, and the rows say nothing.
    pinned_git(
        folder.checkout,
        *("fetch", "-q", folder.replica.url, "+refs/heads/*:refs/remotes/origin/*"),
    )
    assert all("checkout" not in row for row in _refs(served, "remote")["refs"])
    # The reader pushes a commit Metabrowser has not fetched: theirs is the later one.
    pinned_git(folder.checkout, "commit", "-q", "--allow-empty", "-m", "pushed")
    pushed = pinned_git(folder.checkout, "rev-parse", "HEAD")
    pinned_git(folder.checkout, "update-ref", _ORIGIN_TRUNK, pushed)
    again = {row["name"]: row for row in _refs(served, "remote")["refs"]}
    assert again["origin/trunk"]["commit"] == folder.ahead
    assert again["origin/trunk"]["checkout"]["commit"] == pushed
    assert "checkout" not in again["origin/feature"]


def test_another_remotes_branches_stay_listed_from_the_checkout(
    folder: _Folder, tmp_path: Path
) -> None:
    """Only the origin's are taken from the store; a second remote's are the checkout's."""

    other = tmp_path.resolve() / "other.git"
    pinned_git(tmp_path, "clone", "-q", "--bare", str(folder.replica.origin), str(other))
    pinned_git(folder.checkout, "remote", "add", "fork", f"file://{other}")
    pinned_git(folder.checkout, "fetch", "-q", "fork")
    server._set_root_dir(folder.checkout)  # pyright: ignore[reportPrivateUsage]
    serve_checkout_store()
    with TestClient(server.app) as client:
        remote = _by_name(_ready(client))
    assert remote["origin/trunk"] == folder.ahead
    assert remote["fork/trunk"] == folder.ahead
    assert remote["fork/feature"] == folder.feature
    assert set(remote) == {"origin/trunk", "origin/feature", "fork/trunk", "fork/feature"}


# ── Never written ────────────────────────────────────────────────────


def test_the_checkout_is_byte_identical_after_the_store_is_made_fetched_probed_and_read(
    folder: _Folder, served: TestClient
) -> None:
    """Refs, objects, configuration, index, and working tree: nothing under the checkout
    changes across an acquisition, a served origin branch and its files, a probe, a
    reader's fetch, and the way back to the working tree."""

    before = fingerprint(folder.checkout)
    tree = _working_tree(folder.checkout)
    _ready(served)
    assert fingerprint(folder.checkout) == before, "the acquisition wrote the checkout"

    switched = _post(served, "/api/source/pin", {"ref": _ORIGIN_TRUNK})
    assert switched.status_code == 200, switched.text
    assert switched.json()["status"]["pin"] == folder.ahead
    pin = {"x-metabrowser-pin": folder.ahead}
    assert served.get("/api/tree", headers=pin).status_code == 200
    assert fingerprint(folder.checkout) == before, "serving an origin branch wrote the checkout"

    probed = _post(served, "/api/source/refresh", {"for": "page"})
    assert probed.status_code == 200, probed.text
    assert probed.json()["refresh"] == "probed"
    assert fingerprint(folder.checkout) == before, "the probe wrote the checkout"

    newer = _push(folder.replica, "m7")
    assert _post(served, "/api/source/refresh").status_code == 202
    assert _settled(served)["pin"] == newer
    assert fingerprint(folder.checkout) == before, "the fetch wrote the checkout"

    back = _post(served, "/api/source/pin", {"working_tree": True})
    assert back.status_code == 200, back.text
    assert back.json()["status"]["subject"] == "attached_filesystem"
    assert fingerprint(folder.checkout) == before
    assert _working_tree(folder.checkout) == tree
    # The checkout's own remote-tracking branch is where the reader's last fetch left it.
    assert pinned_git(folder.checkout, "rev-parse", _ORIGIN_TRUNK) == folder.behind


def test_a_small_fetch_leaves_objects_the_checkout_already_holds_as_they_were(
    folder: _Folder,
) -> None:
    """The origin sends a few objects the checkout holds but offered no tip for, here
    ones it fetched by address, which only ``FETCH_HEAD`` names. A fetch that unpacked
    them would mark each one written again, in the checkout, by its modification time;
    the store keeps the pack instead, at the acquisition and at a refresh."""

    pinned_git(folder.checkout, "fetch", "-q", str(folder.replica.origin), "trunk")
    _push(folder.replica, "m7")
    before = fingerprint(folder.checkout)
    server._set_root_dir(folder.checkout)  # pyright: ignore[reportPrivateUsage]
    serve_checkout_store()
    with TestClient(server.app) as client:
        _ready(client)
        assert fingerprint(folder.checkout) == before, "the acquisition touched the checkout"
        _push(folder.replica, "m8")
        pinned_git(folder.checkout, "fetch", "-q", str(folder.replica.origin), "trunk")
        newest = _push(folder.replica, "m9")
        before = fingerprint(folder.checkout)
        assert _post(client, "/api/source/refresh").status_code == 202
        _settled(client)
        assert _by_name(_refs(client, "remote"))["origin/trunk"] == newest
    assert fingerprint(folder.checkout) == before, "the fetch touched the checkout"


def test_a_folder_no_page_is_looking_at_fetches_its_store_by_itself_and_writes_no_checkout(
    folder: _Folder, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The idle timer a server runs for its folder's store: with no request asking, a
    store grown old is fetched, the list moves, and the checkout is as it was."""

    monkeypatch.setattr("metabrowser.mirror_refresh.STORE_IDLE_REFRESH_S", 0.2)
    monkeypatch.setattr("metabrowser.mirror_refresh.IDLE_CHECK_FLOOR_S", 0.05)
    before = fingerprint(folder.checkout)
    server._set_root_dir(folder.checkout)  # pyright: ignore[reportPrivateUsage]
    serve_checkout_store()
    with TestClient(server.app) as client:
        assert _by_name(_ready(client))["origin/trunk"] == folder.ahead
        newer = _push(folder.replica, "m7")
        # The fixture's clock stands still, so the store is old only once it is moved.
        folder.clock.advance(3600)
        deadline = time.monotonic() + 30
        # A GET starts no work, so only the server's own timer can have fetched.
        while _by_name(_refs(client, "remote"))["origin/trunk"] != newer:
            assert time.monotonic() < deadline, "the idle refresh never fetched"
            time.sleep(0.05)
    assert fingerprint(folder.checkout) == before, "the idle fetch wrote the checkout"


def _settled(client: TestClient, *, timeout_s: float = 30.0) -> dict[str, Any]:
    deadline = time.monotonic() + timeout_s
    while True:
        status = client.get("/api/source/status").json()
        if not status["refreshing"]:
            return status
        assert time.monotonic() < deadline, "the refresh did not finish"
        time.sleep(0.05)


# ── Serving an origin branch ─────────────────────────────────────────


def test_an_origin_branch_is_served_from_the_store_inert_and_follows_a_fetch(
    folder: _Folder, served: TestClient
) -> None:
    """A commit the checkout lacks is read from the store, the page is a folder's still,
    the pin is fetched and followed as a mirror's is, and a local branch is not."""

    _ready(served)
    switched = _post(served, "/api/source/pin", {"ref": _ORIGIN_TRUNK}).json()
    status = switched["status"]
    assert switched["changed"] is True
    assert status["pin"] == folder.ahead != folder.behind
    assert (status["ref"], status["ref_name"]) == (_ORIGIN_TRUNK, "origin/trunk")
    assert status["subject"] == "git_revision"
    assert status["refreshable"] is True and status["follows"] is True
    assert status["probe_every_s"] == STORE_PROBE_S
    assert status["last_fetch_at"] is not None
    # A folder's page, named and placed as the folder is, with no mirror's address.
    assert status["name"] == "checkout" and status["origin"] is None
    # The kind is how the root was opened: a checkout, whichever revision it shows.
    identity = served.get("/api/identity").json()
    assert (identity["kind"], identity["short_name"]) == ("git", "checkout")
    assert identity["full_name"].endswith("/checkout@origin/trunk")
    listing = _refs(served, "remote")
    assert listing["pin"] == folder.ahead and listing["working_tree"]["current"] is False
    assert [row["name"] for row in listing["refs"] if row["current"]] == ["origin/trunk"]

    newer = _push(folder.replica, "m7")
    refreshed = _post(served, "/api/source/refresh")
    assert refreshed.status_code == 202, refreshed.text
    assert refreshed.json()["refresh"] == "started"
    assert _settled(served)["pin"] == newer

    # The checkout's own branch is read from the checkout, and nothing fetches into it.
    local = _post(served, "/api/source/pin", {"ref": "refs/heads/trunk"}).json()["status"]
    assert local["pin"] == folder.behind
    # It follows the checkout's own ref, read every few seconds and never fetched.
    assert local["follows"] is True and local["probe_every_s"] == CHECKOUT_REFS_POLL_S
    # A tag only the checkout has is the checkout's; one the origin has is the store's.
    own = _post(served, "/api/source/pin", {"ref": "refs/tags/local-only"}).json()["status"]
    assert own["pin"] == folder.behind and own["probe_every_s"] == CHECKOUT_REFS_POLL_S
    theirs = _post(served, "/api/source/pin", {"ref": "refs/tags/v2"}).json()["status"]
    assert theirs["pin"] == folder.replica["M4"] and theirs["follows"] is True
    back = _post(served, "/api/source/pin", {"working_tree": True}).json()
    assert back["changed"] is True and back["status"]["subject"] == "attached_filesystem"


def test_a_refresh_of_the_working_tree_fetches_the_store_and_the_list_moves(
    folder: _Folder, served: TestClient
) -> None:
    """Refresh on a folder fetches Metabrowser's store, whatever the folder shows."""

    assert _by_name(_ready(served))["origin/trunk"] == folder.ahead
    newer = _push(folder.replica, "m7")
    refreshed = _post(served, "/api/source/refresh")
    assert refreshed.status_code == 202, refreshed.text
    answer = refreshed.json()
    assert answer["refresh"] == "started"
    assert answer["status"]["subject"] == "attached_filesystem"
    assert answer["origin"]["state"] == "ready" and answer["origin"]["refreshing"] is True
    assert _by_name(_ready(served))["origin/trunk"] == newer


# ── Without a store ──────────────────────────────────────────────────


def test_a_one_shot_command_reads_the_store_the_cache_has_and_makes_none(
    folder: _Folder, monkeypatch: pytest.MonkeyPatch
) -> None:
    """``metab PATH --api`` lists the checkout's refs and says the origin is not fetched;
    it starts no acquisition and no timer. After a server made the store, it lists from it."""

    started: list[str] = []
    acquire = checkout_store.acquire_checkout_store

    async def counted(*args: Any, **kwargs: Any) -> Any:
        started.append("acquire")
        return await acquire(*args, **kwargs)

    monkeypatch.setattr(checkout_store, "acquire_checkout_store", counted)
    server._set_root_dir(folder.checkout)  # pyright: ignore[reportPrivateUsage]
    with TestClient(server.app) as client:
        listing = _refs(client, "remote")
        assert listing["origin"] == {
            "state": "absent",
            "reason": "not_fetched",
            "detail": ABSENCE_DETAIL["not_fetched"],
            "address": "https://github.com/octo/demo",
            "last_fetch_at": None,
            "last_outcome": None,
            "refreshing": False,
        }
        # As before the store: the checkout's own remote-tracking branch, where it is.
        assert _by_name(listing) == {"origin/trunk": folder.behind}
        assert _by_name(_refs(client, "tag")) == {"local-only": folder.behind}
    assert started == []
    assert not folder.home.exists()

    server._set_root_dir(folder.checkout)  # pyright: ignore[reportPrivateUsage]
    serve_checkout_store()
    with TestClient(server.app) as client:
        _ready(client)
    assert started == ["acquire"]

    server._set_root_dir(folder.checkout)  # pyright: ignore[reportPrivateUsage]
    with TestClient(server.app) as client:
        listing = _refs(client, "remote")
        assert listing["origin"]["state"] == "ready"
        assert _by_name(listing)["origin/trunk"] == folder.ahead
    assert started == ["acquire"]


def test_an_origin_that_needs_credentials_is_shown_as_not_fetched_with_the_reason(
    folder: _Folder, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The acquisition's refusal is the reason; the list is the checkout's own; and a
    page's own ask does not try the origin again before the timer's own next try."""

    attempts: list[str] = []

    async def refused(*_args: Any, **_kwargs: Any) -> Any:
        attempts.append("acquire")
        raise CheckoutStoreError("not_found_or_private", "the repository could not be read")

    monkeypatch.setattr(checkout_store, "acquire_checkout_store", refused)
    server._set_root_dir(folder.checkout)  # pyright: ignore[reportPrivateUsage]
    serve_checkout_store()
    with TestClient(server.app) as client:
        deadline = time.monotonic() + 30
        while (listing := _refs(client, "remote"))["origin"]["state"] != "absent":
            assert time.monotonic() < deadline, listing["origin"]
            time.sleep(0.05)
        assert listing["origin"]["reason"] == "not_found_or_private"
        assert "never asks for a password" in listing["origin"]["detail"]
        assert _by_name(listing) == {"origin/trunk": folder.behind}
        asked = _post(client, "/api/source/refresh", {"for": "page"})
        assert (asked.status_code, asked.json()["refresh"]) == (200, "not_due")
        assert attempts == ["acquire"]
        # A reader's own refresh tries again.
        assert _post(client, "/api/source/refresh").json()["refresh"] == "started"
        deadline = time.monotonic() + 30
        while len(attempts) < 2:
            assert time.monotonic() < deadline
            time.sleep(0.05)


def test_an_origin_that_refuses_says_what_its_provider_says_to_do(
    folder: _Folder, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The chooser's line is the only place a reader learns why the origin is not
    fetched, so it carries the provider's hint, as the command line's refusal does."""

    from metabrowser.cache import acquire, providers

    async def unreadable(source: Any, **_kwargs: Any) -> Any:
        raise acquire.RemoteAccessError("not_found_or_private", source.normalized)

    monkeypatch.setattr(acquire, "acquire_source", unreadable)
    monkeypatch.setattr(
        providers,
        "provider_credential_hint",
        lambda url: f"if it is private, sign in with gh auth login ({url})",
    )
    server._set_root_dir(folder.checkout)  # pyright: ignore[reportPrivateUsage]
    serve_checkout_store()
    with TestClient(server.app) as client:
        deadline = time.monotonic() + 30
        while (origin := _refs(client, "remote")["origin"])["state"] != "absent":
            assert time.monotonic() < deadline, origin
            time.sleep(0.05)
    assert origin["reason"] == "not_found_or_private"
    assert origin["detail"] == (
        ABSENCE_DETAIL["not_found_or_private"]
        + " If it is private, sign in with gh auth login (https://github.com/octo/demo)."
    )


def test_a_failing_acquisition_is_tried_again_less_often_each_time(
    folder: _Folder, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Each failure in a row doubles the wait before the next unasked try, from when the
    attempt ended, up to the cap. The waits are lower bounds, so load only lengthens them."""

    attempts: list[float] = []

    async def unreachable(*_args: Any, **_kwargs: Any) -> Any:
        attempts.append(time.monotonic())
        raise CheckoutStoreError("network_error", "the repository could not be read")

    monkeypatch.setattr(checkout_store, "acquire_checkout_store", unreachable)
    monkeypatch.setattr(checkout_store, "STORE_IDLE_REFRESH_S", 0.2)
    monkeypatch.setattr(checkout_store, "ACQUISITION_RETRY_CAP_S", 0.8)
    server._set_root_dir(folder.checkout)  # pyright: ignore[reportPrivateUsage]
    serve_checkout_store()
    with TestClient(server.app) as client:
        deadline = time.monotonic() + 30
        while len(attempts) < 5:
            assert time.monotonic() < deadline, attempts
            # A visible page's own ask is held to the same waits: it starts a try only
            # once one is due, so asking all the while shortens none of them.
            assert _post(client, "/api/source/refresh", {"for": "page"}).status_code < 300
            time.sleep(0.02)
        # The timer keeps trying until the client shuts down, which under load can take
        # past the next wait, so judge only the first five tries.
        tried = attempts[:5]
    waits = [later - earlier for earlier, later in itertools.pairwise(tried)]
    assert all(wait >= least for wait, least in zip(waits, (0.2, 0.4, 0.8, 0.8), strict=True)), (
        waits
    )


def _hold_the_loop_until(when: float) -> None:
    """Keep the running loop from turning until *when* on its clock, as load can: what fell
    due meanwhile runs in the turns after the caller's next ``await``, together."""

    while time.monotonic() < when:
        time.sleep(0.01)


def test_a_try_a_page_starts_as_the_timer_falls_due_is_the_only_one(
    folder: _Folder, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The timer's wait and a visible page's ask fall due in one turn of the loop. The ask
    starts the try, which fails before the timer looks again, and the timer then waits
    from that try's end rather than starting a second at once (mb-0tw5)."""

    from metabrowser.checkout_store import CheckoutStore
    from metabrowser.mirror_refresh import RefreshCoordinator

    idle = 0.5
    attempts: list[float] = []

    async def unreachable(*_args: Any, **_kwargs: Any) -> Any:
        attempts.append(time.monotonic())
        raise CheckoutStoreError("network_error", "the repository could not be read")

    monkeypatch.setattr(checkout_store, "acquire_checkout_store", unreachable)
    monkeypatch.setattr(checkout_store, "STORE_IDLE_REFRESH_S", idle)

    async def scenario() -> str:
        coordinator = RefreshCoordinator()
        store = CheckoutStore(folder.checkout, coordinator, serving=True)
        try:
            await store.open()
            deadline = time.monotonic() + 30
            while (due := store.retry_at()) is None:
                assert time.monotonic() < deadline, attempts
                await asyncio.sleep(0.01)
            # The timer has looked at the first failure and waits for the try it makes due.
            for _ in range(5):
                await asyncio.sleep(0)
            _hold_the_loop_until(due + 0.05)
            asked, _ = await store.refresh("page")
            # The try the ask started, the end of the timer's wait, and what the timer does
            # then each take a turn or two of the loop.
            for _ in range(10):
                await asyncio.sleep(0)
            return asked
        finally:
            await store.aclose()
            await coordinator.aclose()

    assert asyncio.run(scenario()) == "started"
    waits = [later - earlier for earlier, later in itertools.pairwise(attempts)]
    # Lower bounds: the page's try came an idle interval after the first, and any the timer
    # made before it stopped, which only load lets it reach, twice the wait before.
    least = (idle * 2**at for at in itertools.count())
    assert waits and all(wait >= bound for wait, bound in zip(waits, least, strict=False)), waits


def test_an_acquisition_that_ran_out_its_deadline_waits_for_a_reader_to_ask(
    folder: _Folder, monkeypatch: pytest.MonkeyPatch
) -> None:
    """It downloaded for the whole deadline and kept nothing, and would again, so neither
    the timer nor a visible page's own ask starts it over; a reader's refresh does."""

    from metabrowser.cache import acquire
    from metabrowser.git.process import GitTimeoutError

    attempts: list[str] = []

    async def too_long(*_args: Any, **_kwargs: Any) -> Any:
        attempts.append("acquire")
        raise GitTimeoutError

    monkeypatch.setattr(acquire, "acquire_source", too_long)
    monkeypatch.setattr(checkout_store, "STORE_IDLE_REFRESH_S", 0.05)
    server._set_root_dir(folder.checkout)  # pyright: ignore[reportPrivateUsage]
    serve_checkout_store()
    with TestClient(server.app) as client:
        deadline = time.monotonic() + 30
        while (origin := _refs(client, "remote")["origin"])["state"] != "absent":
            assert time.monotonic() < deadline, origin
            time.sleep(0.05)
        assert (origin["reason"], origin["detail"]) == ("timed_out", ABSENCE_DETAIL["timed_out"])
        # Twenty idle intervals, each of which the timer once spent on another try.
        time.sleep(1.0)
        asked = _post(client, "/api/source/refresh", {"for": "page"})
        assert (asked.status_code, asked.json()["refresh"]) == (200, "not_due")
        assert attempts == ["acquire"]
        assert _post(client, "/api/source/refresh").json()["refresh"] == "started"
        deadline = time.monotonic() + 30
        while len(attempts) < 2:
            assert time.monotonic() < deadline
            time.sleep(0.05)


def test_the_acquisition_never_prompts() -> None:
    """Every Git the store runs has no terminal to ask on and no askpass program."""

    from metabrowser.git.process import ACQUISITION_POLICY, git_environment

    environment = git_environment(ACQUISITION_POLICY)
    assert environment["GIT_TERMINAL_PROMPT"] == "0"
    assert environment["GIT_ASKPASS"] == "" and environment["SSH_ASKPASS"] == ""


def test_a_checkout_with_a_local_origin_or_none_keeps_no_store_and_is_served_as_before(
    folder: _Folder,
) -> None:
    """An origin on this machine, and a checkout with no origin, list as they did, the
    refresh route still refuses a folder, and nothing is written to the cache."""

    for change in (
        ("remote", "set-url", "origin", folder.replica.url),
        ("remote", "remove", "origin"),
    ):
        pinned_git(folder.checkout, *change)
        server._set_root_dir(folder.checkout)  # pyright: ignore[reportPrivateUsage]
        serve_checkout_store()
        with TestClient(server.app) as client:
            deadline = time.monotonic() + 30
            while (listing := _refs(client, "remote"))["origin"] is not None:
                assert listing["origin"]["state"] == "acquiring", listing["origin"]
                assert time.monotonic() < deadline
                time.sleep(0.05)
            refused = _post(client, "/api/source/refresh")
            assert refused.status_code == 409, refused.text
            assert refused.json()["code"] == "unsupported_for_subject"
            assert _by_name(_refs(client, "tag")) == {"local-only": folder.behind}
        assert not folder.home.exists()


@pytest.mark.parametrize("environment", ["unset", "0"])
def test_the_serve_command_keeps_no_store_where_the_environment_says_to_keep_none(
    folder: _Folder, monkeypatch: pytest.MonkeyPatch, environment: str
) -> None:
    """Bead mb-i4x0: a server a test starts as a process of its own cannot be pointed at a
    local origin, so it fetched the fixture's GitHub address from the network. With
    ``METABROWSER_ORIGIN_STORE=0``, which the suite sets, the serve command keeps no store
    and the folder is served as before; unset, it keeps one, as ``metab PATH`` does."""

    from typer.testing import CliRunner

    from metabrowser.checkout_store import ORIGIN_STORE_ENV
    from metabrowser.cli.main import _app
    from tests.held_port import listener_on

    attempts: list[str] = []

    async def acquired(*_args: Any, **_kwargs: Any) -> Any:
        attempts.append("acquire")
        raise CheckoutStoreError("network_error", "never reached")

    monkeypatch.setattr(checkout_store, "acquire_checkout_store", acquired)
    if environment == "unset":
        monkeypatch.delenv(ORIGIN_STORE_ENV, raising=False)
    else:
        monkeypatch.setenv(ORIGIN_STORE_ENV, environment)
        # Short enough that a store kept after all would be tried again below.
        monkeypatch.setattr(checkout_store, "STORE_IDLE_REFRESH_S", 0.05)
    with (
        patch("metabrowser.cli.serve._QuietForceExitServer"),
        patch(
            "metabrowser.cli.serve.listen_on_available_local_port", return_value=listener_on(8411)
        ),
    ):
        result = CliRunner().invoke(_app, [str(folder.checkout), "--no-open"])
    assert result.exit_code == 0, result.output
    with TestClient(server.app) as client:
        if environment == "unset":
            deadline = time.monotonic() + 30
            while (origin := _refs(client, "remote")["origin"])["state"] != "absent":
                assert time.monotonic() < deadline, origin
                time.sleep(0.05)
            assert origin["reason"] == "network_error"
        else:
            assert _refs(client, "remote")["origin"] is None
            # On the working tree, a page's ask and a reader's refresh are both refused, as
            # on a checkout whose origin is on this machine.
            for body in ({"for": "page"}, None):
                refused = _post(client, "/api/source/refresh", body)
                assert refused.status_code == 409, refused.text
                assert refused.json()["code"] == "unsupported_for_subject"
            time.sleep(0.3)
    assert attempts == ([] if environment == "0" else ["acquire"])


def test_a_one_shot_command_keeps_no_store_where_a_serve_keeps_none(
    folder: _Folder, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Review A3 of #762: ``METABROWSER_ORIGIN_STORE=0`` reached the serve command only, so
    ``metab FOLDER --api`` still read a store, and a one-shot ``POST /api/source/refresh``
    made one, where the served page had none. Every open mode now reads it as the
    application starts, so a transcript answers what a browser sees."""

    import json

    from typer.testing import CliRunner

    from metabrowser.checkout_store import ORIGIN_STORE_ENV
    from metabrowser.cli.main import _app

    attempts: list[str] = []

    async def acquired(*_args: Any, **_kwargs: Any) -> Any:
        attempts.append("acquire")
        raise CheckoutStoreError("network_error", "never reached")

    monkeypatch.setattr(checkout_store, "acquire_checkout_store", acquired)

    def one_shot_refs() -> Any:
        result = CliRunner().invoke(
            _app,
            [str(folder.checkout), "--api", "/api/source/refs?kind=remote", "--format", "json"],
        )
        assert result.exit_code == 0, result.output
        return json.loads(result.output)["origin"]

    def answers(serving: bool) -> dict[str, Any]:
        server._set_root_dir(folder.checkout)  # pyright: ignore[reportPrivateUsage]
        if serving:
            serve_checkout_store()
        with TestClient(server.app) as client:
            refused = _post(client, "/api/source/refresh")
            return {
                "origin": _refs(client, "remote")["origin"],
                "refresh": (refused.status_code, refused.json().get("code")),
            }

    # Unset, as outside the suite, a one-shot command reads the store the cache has.
    monkeypatch.delenv(ORIGIN_STORE_ENV, raising=False)
    assert one_shot_refs()["reason"] == "not_fetched"
    monkeypatch.setenv(ORIGIN_STORE_ENV, "0")
    assert one_shot_refs() is None
    one_shot = answers(serving=False)
    assert one_shot == answers(serving=True)
    assert one_shot == {"origin": None, "refresh": (409, "unsupported_for_subject")}
    assert attempts == []


@pytest.mark.parametrize(
    ("spelled", "shown"),
    [
        ("git@example.com:octo/demo.git", "git@example.com:octo/demo.git"),
        ("http://example.com/octo/demo.git", "http://example.com/octo/demo.git"),
        ("http://token@example.com/octo/demo.git", "http://example.com/octo/demo.git"),
        ("git://example.com/octo/demo.git", "git://example.com/octo/demo.git"),
        # A query string or a fragment can carry a credential: neither is shown.
        ("http://host/a/b.git?token=secret", "http://host/a/b.git"),
        ("http://host/a/b.git#fragment", "http://host/a/b.git"),
        ("git://tok@host/a/b.git#x?token=secret", "git://host/a/b.git"),
        # Review C1 on #740: a userinfo holding a raw ``?``, ``#``, or ``@`` is no prefix.
        ("http://user:pa?ss@host.example/octo/demo.git", "http://host.example/octo/demo.git"),
        ("http://user:pa#ss@host.example/octo/demo.git", "http://host.example/octo/demo.git"),
        ("http://tok?en@host.example/octo/demo.git", "http://host.example/octo/demo.git"),
        ("git://user:s3cr#t@host.example/octo/demo.git", "git://host.example/octo/demo.git"),
        ("http://a@b@host/x.git", "http://host/x.git"),
    ],
)
def test_an_origin_reached_another_way_is_one_metabrowser_cannot_fetch(
    folder: _Folder, monkeypatch: pytest.MonkeyPatch, spelled: str, shown: str
) -> None:
    """SSH on a host no provider reduces, ``http``, and ``git``: each names another
    machine by a transport Metabrowser does not fetch over, so the chooser says so, with
    the address and no userinfo, and a server never tries it."""

    attempts: list[str] = []

    async def acquired(*_args: Any, **_kwargs: Any) -> Any:
        attempts.append("acquire")
        raise CheckoutStoreError("fetch_failed", "never reached")

    monkeypatch.setattr(checkout_store, "acquire_checkout_store", acquired)
    monkeypatch.setattr(checkout_store, "STORE_IDLE_REFRESH_S", 0.05)
    pinned_git(folder.checkout, "remote", "set-url", "origin", spelled)
    server._set_root_dir(folder.checkout)  # pyright: ignore[reportPrivateUsage]
    serve_checkout_store()
    with TestClient(server.app) as client:
        deadline = time.monotonic() + 30
        while (origin := _refs(client, "remote")["origin"])["state"] != "absent":
            assert time.monotonic() < deadline, origin
            time.sleep(0.05)
        assert origin["reason"] == "transport_unsupported"
        assert origin["detail"] == ABSENCE_DETAIL["transport_unsupported"]
        assert origin["address"] == shown
        assert _post(client, "/api/source/refresh").status_code == 409
        # Several idle intervals: a transport that cannot be fetched is never retried.
        time.sleep(0.3)
    assert attempts == []
    assert not folder.home.exists()


# ── One store, one turn ──────────────────────────────────────────────


def test_the_github_plugin_takes_cores_turn_and_names_cores_store(folder: _Folder) -> None:
    """The plugin's pull jobs and the folder's fetch queue at one turn, for one store:
    the address core reads from the checkout is the plugin's, and so is the turn."""

    from metabrowser.builtin_plugins.github import checkout as plugin
    from metabrowser.cache.lender import checkout_origin

    repository = plugin._resolve(folder.checkout, folder.home)  # pyright: ignore[reportPrivateUsage]
    assert repository is not None
    named = checkout_origin(folder.checkout)
    assert named is not None
    assert (named.transport, named.normalized) == (
        repository.git_source.transport,
        repository.git_source.normalized,
    )
    state = plugin._checkout_state(repository)  # pyright: ignore[reportPrivateUsage]
    assert state.turn is store_turn(folder.home, named)


def test_a_turn_something_holds_is_the_stores_however_many_stores_follow(folder: _Folder) -> None:
    """Two turns for one store would let two jobs fetch into it at once, so a turn in use
    is never dropped for the turns of stores served since."""

    from dataclasses import replace

    from metabrowser.cache.lender import checkout_origin

    named = checkout_origin(folder.checkout)
    assert named is not None
    held = store_turn(folder.home, named)
    for number in range(32):
        store_turn(folder.home, replace(named, normalized=f"{named.normalized}-{number}"))
    assert store_turn(folder.home, named) is held


def test_the_plugins_acquisition_is_cores_and_a_server_then_adopts_that_store(
    folder: _Folder,
) -> None:
    """A store the plugin's comparison made is the one the folder lists from."""

    from metabrowser.builtin_plugins.github import checkout as plugin

    repository = plugin._resolve(folder.checkout, folder.home)  # pyright: ignore[reportPrivateUsage]
    assert repository is not None
    published = asyncio.run(plugin._acquire_comparison(repository))  # pyright: ignore[reportPrivateUsage]
    assert published.lender is not None
    server._set_root_dir(folder.checkout)  # pyright: ignore[reportPrivateUsage]
    with TestClient(server.app) as client:
        listing = _refs(client, "remote")
    assert listing["origin"]["state"] == "ready"
    assert _by_name(listing)["origin/trunk"] == folder.ahead


def test_a_follow_in_flight_does_not_take_back_the_working_tree_the_reader_chose(
    folder: _Folder, served: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A fetch moved the served origin branch, and while the server was opening its new
    tip the reader chose the working tree. The working tree stays served: the follow and
    the checkout's own switch are one at a time."""

    import threading

    from metabrowser.cache.served_mirror import StoreMirror

    _ready(served)
    assert _post(served, "/api/source/pin", {"ref": _ORIGIN_TRUNK}).status_code == 200
    opening = threading.Event()
    release = threading.Event()
    open_selection = StoreMirror.open_selection

    async def held(self: StoreMirror, **kwargs: Any) -> Any:
        opening.set()
        await held_until(release, 30)
        return await open_selection(self, **kwargs)

    monkeypatch.setattr(StoreMirror, "open_selection", held)
    _push(folder.replica, "m7")
    assert _post(served, "/api/source/refresh").status_code == 202
    assert opening.wait(30), "the fetch never came to follow the branch"
    answers: list[Any] = []
    chooser = threading.Thread(
        target=lambda: answers.append(_post(served, "/api/source/pin", {"working_tree": True}))
    )
    chooser.start()
    # Long enough for an unguarded switch to have ended before the follow attaches.
    chooser.join(1.0)
    release.set()
    chooser.join(30)
    assert not chooser.is_alive() and answers[0].status_code == 200
    _ready(served)
    assert served.get("/api/source/status").json()["subject"] == "attached_filesystem"


def test_an_acquisition_that_ends_as_the_application_stops_leaves_no_session_behind(
    folder: _Folder,
) -> None:
    """A store adopted after its application closed would name a session of a stopped
    loop for the root, which the next application in the process would then list from."""

    from metabrowser.cache.lender import checkout_origin
    from metabrowser.checkout_revisions import CheckoutRevisions
    from metabrowser.checkout_store import CheckoutStore, acquire_checkout_store
    from metabrowser.mirror_refresh import RefreshCoordinator

    async def scenario() -> tuple[bool, bool]:
        source = checkout_origin(folder.checkout)
        assert source is not None
        published = await acquire_checkout_store(source, home=folder.home, checkout=folder.checkout)
        coordinator = RefreshCoordinator()
        store = CheckoutStore(folder.checkout, coordinator, serving=False)
        # The origin is read, and the acquisition is still to end, as the application stops.
        store._origin = await asyncio.to_thread(  # pyright: ignore[reportPrivateUsage]
            checkout_store._read_origin,  # pyright: ignore[reportPrivateUsage]
            folder.checkout,
        )
        await store.aclose()
        await store._adopt(published)  # pyright: ignore[reportPrivateUsage]
        await coordinator.aclose()
        return store.session is None, CheckoutRevisions(folder.checkout).origin is None

    assert asyncio.run(scenario()) == (True, True)


# ── Follow-ups: the default branch, short names, the row, and the retry ──


def test_the_origins_default_branch_lists_first_and_is_marked(
    folder: _Folder, served: TestClient
) -> None:
    """The Remotes list marks the origin's default branch, as a mirror's list does; the
    checkout's own branches still mark the one checked out."""

    listing = _ready(served)
    assert [(row["name"], row["default"], row["checked_out"]) for row in listing["refs"]] == [
        ("origin/trunk", True, False),
        ("origin/feature", False, False),
    ]
    branch = _refs(served, "branch")["refs"][0]
    assert (branch["default"], branch["checked_out"]) == (False, True)


def test_a_short_name_is_read_from_the_store_and_the_answer_names_its_source(
    folder: _Folder, served: TestClient
) -> None:
    """``origin/trunk`` and a tag the origin has are the store's; the checkout's own
    branch of a name, and a tag only it has, are the checkout's."""

    _ready(served)
    for name, commit, where in (
        ("origin/trunk", folder.ahead, "origin"),
        ("origin/feature", folder.feature, "origin"),
        ("v2", folder.replica["M4"], "origin"),
        ("trunk", folder.behind, "checkout"),
        ("local-only", folder.behind, "checkout"),
        (folder.behind[:12], folder.behind, "checkout"),
    ):
        answer = _post(served, "/api/source/pin", {"ref": name})
        assert answer.status_code == 200, (name, answer.text)
        assert (answer.json()["status"]["pin"], answer.json()["read_from"]) == (commit, where), name
    back = _post(served, "/api/source/pin", {"working_tree": True}).json()
    assert back["read_from"] is None
    missing = _post(served, "/api/source/pin", {"ref": "origin/gone"})
    assert missing.status_code == 404


def test_ref_opens_an_origin_branch_from_the_store_once_the_cache_has_one(
    folder: _Folder,
) -> None:
    """``metab PATH --ref origin/trunk`` reads the checkout while there is no store, and
    the store once there is one, and says which on standard error."""

    from tests.golden_harness import run_metab

    command = [str(folder.checkout), "--ref", "origin/trunk", "--api", "/api/source/status"]
    before = run_metab(command)
    assert before.exit_code == 0, before.stderr
    assert f'"pin": "{folder.behind}"' in before.stdout
    assert "is read from the checkout" in before.stderr
    server._set_root_dir(folder.checkout)  # pyright: ignore[reportPrivateUsage]
    serve_checkout_store()
    with TestClient(server.app) as client:
        _ready(client)
    after = run_metab(command)
    assert after.exit_code == 0, after.stderr
    assert f'"pin": "{folder.ahead}"' in after.stdout
    assert '"refreshable": true' in after.stdout
    assert "is read from Metabrowser's store of the origin" in after.stderr
    # The checkout's own branch says nothing: it was never the origin's to read.
    local = run_metab([str(folder.checkout), "--ref", "trunk", "--api", "/api/source/status"])
    assert f'"pin": "{folder.behind}"' in local.stdout and "ref:" not in local.stderr


def test_every_page_of_a_folder_with_a_store_has_its_status_and_a_revisions_the_row(
    folder: _Folder, served: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The working tree's status and a local branch's say when the origin's store was
    fetched and that it can be refreshed. The working tree follows nothing and its page
    has no freshness row, since it shows the disk: the navigation's Refresh fetches the
    store from there. The local branch follows the checkout's own ref, its page has the
    row, and its page's ask reads that ref beside the store's own answer."""

    read_refs_at_every_ask(monkeypatch)
    _ready(served)
    assert 'id="source-freshness"' not in served.get("/view/").text
    status = served.get("/api/source/status").json()
    assert status["subject"] == "attached_filesystem"
    assert status["refreshable"] is True and status["last_fetch_at"] is not None
    assert (status["follows"], status["probe_every_s"], status["pin"]) == (False, None, None)
    assert status["stale"] is False
    folder.clock.advance(3600)
    assert served.get("/api/source/status").json()["stale"] is True
    local = _post(served, "/api/source/pin", {"ref": "refs/heads/trunk"}).json()["status"]
    assert 'id="source-freshness"' in served.get("/view/").text
    assert local["refreshable"] is True and local["follows"] is True
    assert local["probe_every_s"] == CHECKOUT_REFS_POLL_S
    # The reader commits on trunk: the page's ask finds it, and the store, an hour old
    # by the clock above, is fetched for the same ask, quietly.
    pinned_git(folder.checkout, "commit", "-q", "--allow-empty", "-m", "local")
    committed = pinned_git(folder.checkout, "rev-parse", "HEAD")
    asked = _post(served, "/api/source/refresh", {"for": "page"})
    assert asked.status_code == 202, asked.text
    assert asked.json()["status"]["pin"] == committed
    assert _settled(served)["pin"] == committed
    again = _post(served, "/api/source/refresh", {"for": "page"})
    assert (again.status_code, again.json()["refresh"]) == (200, "probed")


def test_a_checkout_that_keeps_no_store_has_no_freshness_row(folder: _Folder) -> None:
    pinned_git(folder.checkout, "remote", "set-url", "origin", folder.replica.url)
    server._set_root_dir(folder.checkout)  # pyright: ignore[reportPrivateUsage]
    with TestClient(server.app) as client:
        assert _refs(client, "remote")["origin"] is None
        assert 'id="source-freshness"' not in client.get("/view/").text
        assert client.get("/api/source/status").json()["refreshable"] is False


def test_a_checkout_that_could_not_lend_is_tried_again_on_the_idle_timer(
    folder: _Folder, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A partial clone made whole later gets its store with no request asking, and until
    then the chooser keeps saying why there is none, the retry included."""

    import threading

    attempts: list[str] = []
    retrying = threading.Event()
    release = threading.Event()
    acquire = checkout_store.acquire_checkout_store

    async def refused_once(*args: Any, **kwargs: Any) -> Any:
        attempts.append("acquire")
        if len(attempts) == 1:
            raise CheckoutStoreError("lender_missing", "the checkout cannot lend its objects")
        retrying.set()
        await held_until(release, 30)
        return await acquire(*args, **kwargs)

    monkeypatch.setattr(checkout_store, "acquire_checkout_store", refused_once)
    monkeypatch.setattr(checkout_store, "STORE_IDLE_REFRESH_S", 0.3)
    server._set_root_dir(folder.checkout)  # pyright: ignore[reportPrivateUsage]
    serve_checkout_store()
    try:
        with TestClient(server.app) as client:
            assert retrying.wait(30), "the acquisition was never tried again"
            during = _refs(client, "remote")["origin"]
            assert (during["state"], during["reason"]) == ("absent", "lender_missing")
            assert during["refreshing"] is True
            release.set()
            deadline = time.monotonic() + 30
            while (listing := _refs(client, "remote"))["origin"]["state"] != "ready":
                assert time.monotonic() < deadline, listing["origin"]
                time.sleep(0.05)
            assert _by_name(listing)["origin/trunk"] == folder.ahead
    finally:
        release.set()
    assert attempts == ["acquire", "acquire"]
