"""File watches on the event stream: a page's own paths, registered on its connection.

``metabrowser.file_watches`` keeps each ``/api/events`` connection's watched paths and the
generation each was last seen at, and its poll sends ``file.changed`` to the connection
that saw another; ``POST /api/events/watch`` (``events_route.py``) registers and
unregisters them. ``tests/golden/cli-api-events-watch.tryscript.md`` pins what
``metab --api`` reaches: the generation a watch compares, and each refusal.
"""

from __future__ import annotations

import asyncio
import json
import os
from collections.abc import Iterator
from pathlib import Path
from typing import Any, cast

import pytest
from starlette.requests import Request

from metabrowser import server
from metabrowser.builtin_plugins.delimited import source as delimited
from metabrowser.events import FileChanged, FsResyncRequired, Heartbeat
from metabrowser.events_route import _EventBus, api_events_watch
from metabrowser.file_watches import (
    HEAD_WATCH_PATH,
    FileWatches,
    TooManyWatchesError,
    UnknownConnectionError,
    _touches,  # pyright: ignore[reportPrivateUsage]
    watch_generation,
)
from metabrowser.table_source import open_table_source
from tests.inventory_harness import inventory_harness
from tests.required_tools import needs_git
from tests.source_checkout_fixture import git


@pytest.fixture
def root(tmp_path: Path) -> Iterator[Path]:
    server._set_root_dir(tmp_path)  # pyright: ignore[reportPrivateUsage]
    delimited.PARSE_CACHE.clear()
    (tmp_path / "people.csv").write_text("name,age\nAda,36\nBob,41\n", encoding="utf-8")
    (tmp_path / "notes.txt").write_text("plain\n", encoding="utf-8")
    yield tmp_path
    delimited.PARSE_CACHE.clear()


def _touch(path: Path, text: str) -> None:
    """Rewrite *path* so its generation moves even within one mtime tick."""

    path.write_text(text, encoding="utf-8")
    stat = path.stat()
    os.utime(path, ns=(stat.st_atime_ns, stat.st_mtime_ns + 1_000_000_000))


def _request(app: object, body: dict[str, Any] | bytes) -> Request:
    raw = body if isinstance(body, bytes) else json.dumps(body).encode()

    async def receive() -> dict[str, Any]:
        return {"type": "http.request", "body": raw, "more_body": False}

    scope = {"type": "http", "method": "POST", "path": "/api/events/watch", "headers": []}
    request = Request(scope, receive)
    request.scope["app"] = app
    return request


async def _post(app: object, body: dict[str, Any] | bytes) -> tuple[int, dict[str, Any]]:
    response = await api_events_watch(_request(app, body))
    return response.status_code, json.loads(bytes(response.body))


async def _attached(bus: _EventBus) -> tuple[str, asyncio.Queue[Any]]:
    snapshot, queue = await bus.snapshot_and_attach("root-depth-2")
    assert snapshot.connection is not None
    return snapshot.connection, queue


def _events(queue: asyncio.Queue[Any]) -> list[Any]:
    out: list[Any] = []
    while not queue.empty():
        out.append(queue.get_nowait().event)
    return out


def test_each_snapshot_names_its_own_connection_first_on_the_wire(root: Path) -> None:
    async def run() -> tuple[str, str, str]:
        async with inventory_harness(root) as harness:
            first, _ = await _attached(harness.bus)
            second, _ = await _attached(harness.bus)
            snapshot, _queue = await harness.bus.snapshot_and_attach("root-depth-2")
            from metabrowser.events import EventEnvelope, encode_sse

            frame = encode_sse(EventEnvelope(id=0, event=snapshot)).decode()
            return first, second, frame

    first, second, frame = asyncio.run(run())
    assert first != second
    # The browser compares two snapshots without their connection, so it leads the data.
    assert frame.split("data: ", 1)[1].startswith('{"connection":"')


def test_registering_answers_the_generation_a_table_read_samples(root: Path) -> None:
    async def run() -> tuple[int, dict[str, Any], str]:
        async with inventory_harness(root) as harness:
            connection, _queue = await _attached(harness.bus)
            opened = await open_table_source("people.csv")
            rows_generation = await asyncio.to_thread(opened.source.generation)
            status, body = await _post(
                harness.app,
                {"connection": connection, "path": "people.csv", "generation": rows_generation},
            )
            return status, body, rows_generation

    status, body, rows_generation = asyncio.run(run())
    assert status == 200
    assert body["watching"] is True
    assert body["generation"] == rows_generation
    assert body["changed"] is False


def test_a_change_before_registering_is_answered_not_lost(root: Path) -> None:
    async def run() -> dict[str, Any]:
        async with inventory_harness(root) as harness:
            connection, _queue = await _attached(harness.bus)
            held = await watch_generation("people.csv")
            _touch(root / "people.csv", "name,age\nAda,36\nBob,41\nCy,7\n")
            _status, body = await _post(
                harness.app, {"connection": connection, "path": "people.csv", "generation": held}
            )
            return body

    assert asyncio.run(run())["changed"] is True


def test_a_poll_sends_one_change_for_a_burst_to_the_watching_connection_only(
    root: Path,
) -> None:
    async def run() -> tuple[list[Any], list[Any], list[Any]]:
        async with inventory_harness(root) as harness:
            watcher, watching = await _attached(harness.bus)
            _other, other = await _attached(harness.bus)
            await harness.bus.watches.register(watcher, "people.csv")
            await harness.bus.watches.register(watcher, "notes.txt")
            _events(watching)
            _events(other)
            for n in range(3):
                _touch(root / "people.csv", f"name,age\nAda,{n}\n")
            await harness.bus.watches.poll()
            burst = _events(watching)
            await harness.bus.watches.poll()
            quiet = _events(watching)
            return burst, quiet, _events(other)

    burst, quiet, other = asyncio.run(run())
    changes = [event for event in burst if isinstance(event, FileChanged)]
    assert [event.path for event in changes] == ["people.csv"]
    assert not [event for event in quiet if isinstance(event, FileChanged)]
    assert not [event for event in other if isinstance(event, FileChanged)]


def test_a_removed_file_is_a_change_to_no_generation(root: Path) -> None:
    async def run() -> list[Any]:
        async with inventory_harness(root) as harness:
            connection, queue = await _attached(harness.bus)
            await harness.bus.watches.register(connection, "notes.txt")
            _events(queue)
            (root / "notes.txt").unlink()
            await harness.bus.watches.poll()
            return [event for event in _events(queue) if isinstance(event, FileChanged)]

    assert asyncio.run(run()) == [FileChanged(path="notes.txt", generation=None)]


def test_an_unknown_connection_is_refused_both_ways(root: Path) -> None:
    async def run() -> list[tuple[int, str]]:
        async with inventory_harness(root) as harness:
            answers = []
            for body in (
                {"connection": "gone", "path": "people.csv", "generation": None},
                {"connection": "gone", "path": "people.csv", "watch": False},
            ):
                status, answer = await _post(harness.app, body)
                answers.append((status, answer["code"]))
            return answers

    assert asyncio.run(run()) == [(409, "unknown_connection"), (409, "unknown_connection")]


def test_a_connection_that_ended_or_was_resynced_holds_no_watches(root: Path) -> None:
    async def run() -> tuple[int, str, int, str]:
        async with inventory_harness(root) as harness:
            ended, queue = await _attached(harness.bus)
            await harness.bus.watches.register(ended, "people.csv")
            harness.bus.detach_connection(queue)
            status, body = await _post(harness.app, {"connection": ended, "path": "notes.txt"})
            resynced, _queue = await _attached(harness.bus)
            await harness.bus.watches.register(resynced, "people.csv")
            harness.bus.publish(FsResyncRequired(reason="test"))
            again, answer = await _post(harness.app, {"connection": resynced, "path": "notes.txt"})
            return status, body["code"], again, answer["code"]

    assert asyncio.run(run()) == (409, "unknown_connection", 409, "unknown_connection")


def test_unregistering_stops_the_changes(root: Path) -> None:
    async def run() -> tuple[int, dict[str, Any], list[Any]]:
        async with inventory_harness(root) as harness:
            connection, queue = await _attached(harness.bus)
            await harness.bus.watches.register(connection, "people.csv")
            status, body = await _post(
                harness.app, {"connection": connection, "path": "people.csv", "watch": False}
            )
            _events(queue)
            _touch(root / "people.csv", "name\nZed\n")
            await harness.bus.watches.poll()
            return status, body, _events(queue)

    status, body, later = asyncio.run(run())
    assert (status, body["watching"]) == (200, False)
    assert not [event for event in later if isinstance(event, FileChanged)]


def test_a_connection_watches_at_most_its_bound(root: Path) -> None:
    async def generation(_path: str) -> str | None:
        return "g"

    async def run() -> None:
        watches = FileWatches(send=lambda _c, _e: None, generation_of=generation, max_paths=2)
        watches.open("c")
        await watches.register("c", "a")
        await watches.register("c", "b")
        await watches.register("c", "a")  # A path already watched is not another.
        with pytest.raises(TooManyWatchesError):
            await watches.register("c", "c")
        with pytest.raises(UnknownConnectionError):
            await watches.register("d", "a")

    asyncio.run(run())


def test_the_route_refuses_past_the_bound(root: Path) -> None:
    async def run() -> tuple[int, dict[str, Any]]:
        async with inventory_harness(root) as harness:
            connection, _queue = await _attached(harness.bus)
            for n in range(harness.bus.watches.max_paths):
                await harness.bus.watches.register(connection, f"p{n}")
            return await _post(harness.app, {"connection": connection, "path": "people.csv"})

    status, body = asyncio.run(run())
    assert status == 409
    assert body["code"] == "too_many_watches"
    assert body["max_paths"] > 0


@pytest.mark.parametrize(
    ("body", "code"),
    [
        (b"not json", "bad_request"),
        (b"[]", "bad_request"),
        ({"connection": "c"}, "bad_request"),
        ({"path": "x", "watch": "no"}, "bad_request"),
        ({"path": "x", "watch": False}, "bad_request"),
        (b"{" + b" " * 9000 + b"}", "body_too_large"),
    ],
)
def test_a_malformed_registration_is_refused(
    root: Path, body: dict[str, Any] | bytes, code: str
) -> None:
    async def run() -> tuple[int, str]:
        async with inventory_harness(root) as harness:
            status, answer = await _post(harness.app, body)
            return status, answer["code"]

    status, answered = asyncio.run(run())
    assert answered == code
    assert status in (400, 413)


def test_an_inventory_change_at_a_watched_path_or_its_sidecar_polls_soon() -> None:
    assert _touches("people.csv", "people.csv")
    assert _touches("data", "data/people.csv")
    assert _touches("app.db-wal", "app.db")
    assert _touches("app.db-journal", "app.db/users")
    assert not _touches("other.csv", "people.csv")
    assert not _touches("", "people.csv")
    assert not _touches("data/other.csv", "data/people.csv")


def _woken(watches: FileWatches) -> bool:
    woken = watches._wake.is_set()  # pyright: ignore[reportPrivateUsage]
    watches._wake.clear()  # pyright: ignore[reportPrivateUsage]
    return woken


def test_a_nudge_wakes_for_what_touches_says_and_forgets_released_watches() -> None:
    """The nudge's index answers as _touches does, and holds only what is watched."""

    async def none(_path: str) -> str | None:
        return None

    async def run() -> None:
        watches = FileWatches(send=lambda _c, _e: None, generation_of=none)
        watches.open("a")
        watches.open("b")
        await watches.register("a", "data/people.csv")
        await watches.register("b", "data/people.csv")
        await watches.register("b", "app.db/users")
        for dirty, expected in [
            (["data/people.csv"], True),
            (["data"], True),
            (["app.db-wal"], True),
            (["app.db-journal"], True),
            (["data/other.csv"], False),
            ([""], False),
            (["-wal"], False),
            ([f"elsewhere/f{n}.txt" for n in range(1024)], False),
        ]:
            watches.nudge(dirty)
            assert _woken(watches) is expected, dirty
        watches.unregister("a", "data/people.csv")
        watches.nudge(["data"])
        assert _woken(watches), "b still watches data/people.csv"
        watches.close("b")
        assert watches._reached == {}  # pyright: ignore[reportPrivateUsage]
        watches.nudge(["data", "app.db"])
        assert not _woken(watches)

    asyncio.run(run())


def test_a_poll_never_sends_a_generation_older_than_a_registration_answered() -> None:
    """A path sampled, then written and registered by another connection, is not sent
    the older sample; the next poll compares it as usual."""

    generation = {"p": "g0"}
    sampling = asyncio.Event()
    release = asyncio.Event()

    async def sample(path: str) -> str | None:
        seen = generation[path]
        if not release.is_set():
            sampling.set()
            await release.wait()
        return seen

    async def run() -> list[tuple[str, str | None]]:
        sent: list[tuple[str, str | None]] = []
        watches = FileWatches(
            send=lambda connection, event: sent.append((connection, event.generation)),
            generation_of=sample,
        )
        watches.open("early")
        watches.open("late")
        release.set()
        await watches.register("early", "p")
        release.clear()
        poll = asyncio.create_task(watches.poll())
        await sampling.wait()
        generation["p"] = "g1"
        release.set()
        assert await watches.register("late", "p") == "g1"
        await poll
        assert watches.watched("late") == {"p": "g1"}
        await watches.poll()
        return sent

    # The late connection is never sent g0; the early one hears g1, from the second poll.
    assert asyncio.run(run()) == [("early", "g1")]


def test_the_poll_loop_runs_on_a_nudge_and_spaces_its_polls() -> None:
    polls: list[float] = []

    async def generation(_path: str) -> str | None:
        polls.append(asyncio.get_running_loop().time())
        return str(len(polls))

    async def run() -> list[FileChanged]:
        sent: list[FileChanged] = []
        arrived: asyncio.Queue[FileChanged] = asyncio.Queue()

        def send(_connection: str, event: FileChanged) -> None:
            sent.append(event)
            arrived.put_nowait(event)

        watches = FileWatches(send=send, generation_of=generation, interval_s=60.0, spacing_s=0.05)
        watches.open("c")
        await watches.register("c", "a.csv")
        task = asyncio.create_task(watches.run())
        try:
            async with asyncio.timeout(10):
                watches.nudge(["a.csv"])
                await arrived.get()
                watches.nudge(["a.csv-wal"])
                await arrived.get()
        finally:
            task.cancel()
            await asyncio.gather(task, return_exceptions=True)
        return sent

    sent = asyncio.run(run())
    assert [event.generation for event in sent] == ["2", "3"]
    assert polls[2] - polls[1] >= 0.04


def test_a_full_queue_restarts_the_watching_connection(root: Path) -> None:
    from metabrowser import events_route

    async def run() -> tuple[object, bool]:
        original = events_route.PER_CONNECTION_QUEUE_SIZE
        events_route.PER_CONNECTION_QUEUE_SIZE = 1
        try:
            async with inventory_harness(root) as harness:
                connection, queue = await _attached(harness.bus)
                harness.bus.publish(Heartbeat(ts_ns=1))
                cast(Any, harness.bus)._send_to_connection(
                    connection, FileChanged(path="people.csv", generation="g")
                )
                return queue.get_nowait().event, harness.bus.connection_is_open(connection)
        finally:
            events_route.PER_CONNECTION_QUEUE_SIZE = original

    event, still_open = asyncio.run(run())
    assert isinstance(event, FsResyncRequired)
    assert not still_open


def test_a_pinned_revision_answers_as_the_event_stream_does(tmp_path: Path) -> None:
    from tests.git_pin_harness import fast_import_store, pinned_client

    store, commit = fast_import_store(tmp_path, {b"people.csv": b"name\nada\n"})

    async def run() -> tuple[int, dict[str, Any]]:
        async with pinned_client(store, commit) as (client, _subject):
            response = await client.post("/api/events/watch", json={"path": "people.csv"})
            return response.status_code, response.json()

    status, body = asyncio.run(run())
    assert status == 409
    assert body == {
        "error": "This is not available here.",
        "detail": "source does not support watcher",
        "code": "unsupported_for_subject",
        "capability": "watcher",
    }


@needs_git
@pytest.mark.parametrize("linked", [False, True], ids=["main worktree", "linked worktree"])
def test_a_checkouts_head_is_watched_by_what_it_names(tmp_path: Path, linked: bool) -> None:
    """``HEAD_WATCH_PATH`` moves when the served checkout's ``HEAD`` names another branch
    or another commit, and at nothing else: the page's row names that branch.

    A linked worktree's ``.git`` is a file and its ``HEAD`` is under the repository's own
    directory, outside the served root, so no file under the root changes when it checks
    out a branch; and a commit moves the branch's ref and leaves the ``HEAD`` file as it
    was. The generation is what ``HEAD`` names, so it follows both.
    """

    main = tmp_path / "main"
    main.mkdir()
    git(main, "init", "-q", "-b", "trunk")
    (main / "a.txt").write_text("a\n", encoding="utf-8")
    git(main, "add", "-A")
    git(main, "commit", "-q", "-m", "first")
    git(main, "branch", "feature")
    root = main
    if linked:
        root = tmp_path / "linked"
        git(main, "worktree", "add", "-q", "-b", "topic", str(root))
        assert (root / ".git").is_file()
    server._set_root_dir(root)  # pyright: ignore[reportPrivateUsage]

    async def run() -> tuple[list[str | None], list[Any], dict[str, Any]]:
        async with inventory_harness(root) as harness:
            connection, queue = await _attached(harness.bus)
            seen = [await harness.bus.watches.register(connection, HEAD_WATCH_PATH)]

            async def after(*command: str) -> None:
                git(root, *command)
                seen.append(await watch_generation(HEAD_WATCH_PATH))

            # A file written and staged: HEAD names what it named.
            (root / "b.txt").write_text("b\n", encoding="utf-8")
            await after("add", "-A")
            await after("commit", "-q", "-m", "second")
            await after("checkout", "-q", "feature")
            await after("checkout", "-q", "--detach", "feature")
            await harness.bus.watches.poll()
            # What `metab --api` reaches: the generation, with nothing registered.
            _status, asked = await _post(harness.app, {"path": HEAD_WATCH_PATH})
            return seen, _events(queue), asked

    seen, events, asked = asyncio.run(run())
    registered, staged, committed, switched, detached = seen
    assert registered is not None and staged == registered
    # A commit, another branch, and a detached HEAD at that branch's commit each name
    # something else, and nothing repeats.
    assert len({registered, committed, switched, detached}) == 4
    changes = [event for event in events if isinstance(event, FileChanged)]
    assert [(event.path, event.generation) for event in changes] == [(HEAD_WATCH_PATH, detached)]
    assert asked["generation"] == detached and asked["watching"] is False


def test_a_folder_that_is_no_checkout_watches_that_path_as_any_other(root: Path) -> None:
    async def run() -> tuple[str | None, str | None]:
        async with inventory_harness(root):
            missing = await watch_generation(HEAD_WATCH_PATH)
            (root / ".git").mkdir()
            (root / ".git" / "HEAD").write_text("not a head\n", encoding="utf-8")
            return missing, await watch_generation(HEAD_WATCH_PATH)

    missing, present = asyncio.run(run())
    assert missing is None and present is not None
