"""A click must not wait behind work nobody asked for.

Metabrowser serves over HTTP/1.1, where a browser opens at most six connections
per origin. The page holds two of them open forever as ``EventSource`` streams,
so four remain for every fetch it makes -- and the folder-warming sweep issues
many at once. A reader clicks a row, the request finds no free connection, and
waits for speculative work it did not ask for.

That is not a theory. On a 241,063-file tree it was measured in a real browser:

    /api/tree?path=scripts&depth=2     client 6,610 ms    server 12.4 ms
    selectFile                         8,896 ms, its own fetch 8,482 ms, threw

The server answered in twelve milliseconds and the reader waited six seconds.

**Why this check exists rather than a note in a document.** Finding it took a
person driving a browser and pasting a console table. Nothing in the repository
could see it: the server is fast by every server-side measure, and it is fast
*here* too -- the defect lives entirely in how many requests the client has in
flight when the reader acts. So this reproduces the browser's connection budget
without a browser, and fails.

**Why a tiny tree is enough.** Starvation is a function of the connection budget,
not of the corpus: six slots, two held open, a sweep that wants more than four.
A large tree makes it worse and is not needed to show it, which is what lets
this run in ``make verify`` instead of in a benchmark nobody runs.

What it measures is the gap between what the server spent and what the client
waited. ``Server-Timing`` reports the first; the wall clock reports the second.
Those two moving together is a slow server. The second far above the first is
this bug, and the distinction is the whole diagnosis.
"""

from __future__ import annotations

import http.client
import os
import queue
import socket
import subprocess
import sys
import tempfile
import threading
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

# What a browser allows per origin on HTTP/1.1. Chrome, Firefox and Safari all
# use six; it is not configurable by the page.
BROWSER_CONNECTION_LIMIT = 6
# What the app holds open and never releases: app.js opens an inventory stream
# and a per-view stream, both EventSource.
EVENT_STREAM_CONNECTIONS = 2
# A click should feel immediate. The project's own line is that nothing under
# ~50 ms should flash a spinner; a request that the server answers in single
# digits has no business taking longer than this once queueing is removed.
INTERACTION_BUDGET_MS = 250.0
# How many speculative requests the sweep is allowed to have outstanding. This
# is the number the fix has to bound; today nothing does.
SPECULATIVE_REQUESTS = 8


def _free_port() -> int:
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        return int(probe.getsockname()[1])


# How much the sweep has queued when the reader clicks. The browser had 51
# outstanding subtree fetches in the run that motivated this check.
QUEUED_SPECULATIVE_REQUESTS = 48
# Folders, and files in each. Sized so one subtree request costs tens of
# milliseconds rather than one: the delay a click sees is
# (queued / free slots) x per-request cost, so a corpus where every request is
# instant cannot show the defect however many requests are queued. This is a
# few seconds to build and is the smallest tree that reproduces.
CORPUS_FOLDERS = 24
CORPUS_FILES_PER_FOLDER = 400


def _build_tree(root: Path) -> None:
    """A tree where a subtree request costs enough for a queue to form behind it."""
    for index in range(CORPUS_FOLDERS):
        directory = root / f"folder{index:02d}" / "nested"
        directory.mkdir(parents=True, exist_ok=True)
        for leaf in range(CORPUS_FILES_PER_FOLDER):
            (directory / f"file{leaf:04d}.txt").write_text("x\n")


def _hold_event_stream(port: int, stop: threading.Event) -> None:
    """Occupy one connection the way EventSource does: open, and never finish."""
    connection = http.client.HTTPConnection("127.0.0.1", port, timeout=30)
    try:
        connection.request("GET", "/api/events?scope=root-depth-2")
        response = connection.getresponse()
        while not stop.is_set():
            # Reading a little at a time keeps the socket in use without
            # buffering an unbounded stream.
            if not response.read(1):
                break
    except (OSError, http.client.HTTPException):
        pass
    finally:
        connection.close()


class ConnectionBudget:
    """The browser's per-origin connection cap, modelled explicitly.

    This is the part that makes the check faithful. A browser does not open a
    socket per request: it keeps at most six to an origin and QUEUES the rest,
    which is where the waiting happens. An earlier version of this file opened a
    fresh connection per request and measured no delay at all -- correctly, since
    without the cap there is nothing to queue behind.
    """

    def __init__(self, port: int, slots: int) -> None:
        self._pool: queue.Queue[http.client.HTTPConnection] = queue.Queue()
        for _ in range(slots):
            self._pool.put(http.client.HTTPConnection("127.0.0.1", port, timeout=120))
        self._port = port

    def get(self, path: str) -> tuple[float, float | None, int]:
        """Wall time INCLUDING the wait for a free connection, as a reader sees it."""
        started = time.perf_counter()
        connection = self._pool.get()
        try:
            connection.request("GET", path)
            response = connection.getresponse()
            response.read()
            wall_ms = (time.perf_counter() - started) * 1000
            server_ms: float | None = None
            for part in (response.getheader("Server-Timing") or "").split(","):
                if "srv;dur=" in part:
                    try:
                        server_ms = float(part.split("srv;dur=")[1].split(";")[0])
                    except (IndexError, ValueError):
                        server_ms = None
            return wall_ms, server_ms, response.status
        except (OSError, http.client.HTTPException):
            connection.close()
            connection = http.client.HTTPConnection("127.0.0.1", self._port, timeout=120)
            return (time.perf_counter() - started) * 1000, None, 0
        finally:
            self._pool.put(connection)


def _timed_get(port: int, path: str) -> tuple[float, float | None, int]:
    """One request on its own connection, for readiness checks only."""
    connection = http.client.HTTPConnection("127.0.0.1", port, timeout=60)
    started = time.perf_counter()
    try:
        connection.request("GET", path)
        response = connection.getresponse()
        response.read()
        return (time.perf_counter() - started) * 1000, None, response.status
    finally:
        connection.close()


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="mb-interaction-") as workspace:
        tree = Path(workspace) / "tree"
        tree.mkdir()
        _build_tree(tree)
        port = _free_port()
        server = subprocess.Popen(
            [
                sys.executable,
                "-c",
                "from metabrowser.cli.entrypoint import main; main()",
                str(tree),
                "--port",
                str(port),
                "--no-open",
            ],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            cwd=str(ROOT),
            env={**os.environ, "PYTHONPATH": str(ROOT / "src")},
        )
        stop = threading.Event()
        streams: list[threading.Thread] = []
        try:
            deadline = time.monotonic() + 60
            while time.monotonic() < deadline:
                try:
                    _timed_get(port, "/api/tree?depth=0")
                    break
                except OSError:
                    continue
            else:
                print("interaction latency: server never answered", file=sys.stderr)
                return 1

            # Hold the connections EventSource holds.
            for _ in range(EVENT_STREAM_CONNECTIONS):
                thread = threading.Thread(target=_hold_event_stream, args=(port, stop), daemon=True)
                thread.start()
                streams.append(thread)
            time.sleep(0.5)

            # The reader's browser now has four connections left. The sweep
            # queues far more requests than that, and a click joins the back of
            # the same queue -- there is no priority between speculative work
            # and work somebody asked for.
            free_slots = BROWSER_CONNECTION_LIMIT - EVENT_STREAM_CONNECTIONS
            budget = ConnectionBudget(port, free_slots)

            sweep_done = threading.Event()

            def sweep() -> None:
                workers: list[threading.Thread] = []
                for index in range(QUEUED_SPECULATIVE_REQUESTS):
                    thread = threading.Thread(
                        target=budget.get,
                        args=(f"/api/tree?path=folder{index % CORPUS_FOLDERS:02d}&depth=2",),
                        daemon=True,
                    )
                    thread.start()
                    workers.append(thread)
                for thread in workers:
                    thread.join(timeout=120)
                sweep_done.set()

            threading.Thread(target=sweep, daemon=True).start()
            # Let the queue build, the way it has by the time a reader reacts to
            # the first rows appearing.
            time.sleep(0.3)

            samples = [budget.get("/api/file?path=folder00") for _ in range(3)]
            sweep_done.wait(timeout=180)

            # The same click with nothing else in flight, so the comparison is
            # against this machine rather than against a remembered number.
            idle_budget = ConnectionBudget(port, free_slots)
            idle = [idle_budget.get("/api/file?path=folder00") for _ in range(3)]
        finally:
            stop.set()
            server.terminate()
            try:
                server.wait(timeout=20)
            except subprocess.TimeoutExpired:
                server.kill()

    busy_wall = sorted(s[0] for s in samples)[len(samples) // 2]
    idle_wall = sorted(s[0] for s in idle)[len(idle) // 2]
    server_side = [s[1] for s in samples if s[1] is not None]
    busy_server = sorted(server_side)[len(server_side) // 2] if server_side else None

    print(
        f"interaction latency under a saturated connection budget\n"
        f"  connections: {BROWSER_CONNECTION_LIMIT} browser cap, "
        f"{EVENT_STREAM_CONNECTIONS} held by event streams, "
        f"{BROWSER_CONNECTION_LIMIT - EVENT_STREAM_CONNECTIONS} left for fetches\n"
        f"  click while the sweep runs : {busy_wall:8.1f} ms wall"
        + (f", {busy_server:.1f} ms server" if busy_server is not None else "")
        + f"\n  click with nothing running : {idle_wall:8.1f} ms wall\n"
        f"  budget                     : {INTERACTION_BUDGET_MS:8.1f} ms"
    )

    if busy_wall > INTERACTION_BUDGET_MS:
        queued = busy_wall - (busy_server or 0.0)
        print(
            f"\nA user-initiated request waited {busy_wall:.0f} ms while the server spent "
            f"{busy_server:.1f} ms on it.\n"
            f"About {queued:.0f} ms of that is queueing behind speculative requests the\n"
            "reader did not ask for. Bound the sweep's concurrency so a slot stays free,\n"
            "abort speculative fetches when an interaction needs one, or serve HTTP/2 and\n"
            "stop rationing connections at all. See mb-y2ft.",
            file=sys.stderr,
        )
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
