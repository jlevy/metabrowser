#!/usr/bin/env python3
"""One scripted session of browsing pull requests, against the stand-in or a real server.

The session is what a reader's pages ask of the GitHub plugin, in the order they ask it
(:func:`browse`):

1. **Open the Pulls tab** on its open pull requests: the tab's first ask for the list, its
   first screen of rows once they are listed, the cores of the rows on it, and the tab's next
   ask, which starts the scan of every open pull request's status while the catalog is
   still read.
2. **Open the top row** at once, which nothing has read, so its page's Fetch competes with
   that work for the network; and let its page ask again a probe's interval later.
3. **Switch** to the closed pull requests and open the first, with Fetch too.
4. **Come back** to the open list, which names its top rows for the prefetch, and
   **scroll** a screen down: that screen's rows and their cores, then the walk's cores of
   the rows past it.
5. **Open** the second row's pull request, which the prefetch has read, and **revisit** the
   first.

Before each step but the first two the reader dwells (:data:`DWELLS`). The first pull
request's revisit comes inside its status's window (``FRESHNESS_WINDOW_S``) and its full
read's (``FULL_REFRESH_S``) from its Fetch, which the benchmark checks, so a probe alone
answers it; and each list ask comes a list probe's interval (``LIST_PROBE_S``) or more
after the one before, so each probes.

:func:`browse` takes a :class:`Driver`. ``tests/test_github_browsing_benchmark.py`` runs it
against the in-process stand-in, whose ``gh`` answers with recorded latencies, and holds the
session's request report to its invariants. ``live`` here runs it against a real server
started on a GitHub repository:

    uv --config-file uv.toml run --frozen python explorations/performance-loop/github_browsing.py \\
        live --url http://127.0.0.1:PORT --out .bench/github-browsing.json

It drives the server over HTTP, waits for its jobs by asking the routes that say whether one
runs, dwells in real time, and writes the request report over the session and over each
step (``GET /api/plugin/github/gh-requests``) to ``--out``, with when each step ran. The
server's ``gh`` reads GitHub as the account it is signed in as.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from collections.abc import Callable, Mapping
from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Final, Protocol

PLUGIN: Final = "/api/plugin/github"
REPORT: Final = f"{PLUGIN}/gh-requests"
# The rows one screen of the Pulls tab shows, about a 1280x900 window's worth; the rows the
# tab asks the catalog for (``DISPLAY_ROWS`` in ``pulls-panel.js``); and the rows one cores
# batch prepares (``CORE_BATCH_SIZE`` there, ``MAX_CATALOG_MEMBERS`` on the server). The
# benchmark holds the last two to theirs.
SCREEN_ROWS: Final = 20
DISPLAY_ROWS: Final = 500
CORE_BATCH: Final = 8
# The prefetch a first screen names: its top rows.
PREFETCH_ROWS: Final = 2
# How long the reader dwells before each step, in seconds; a step not named follows the one
# before at once. A visible pull request page asks again every ``ATTENDED_PROBE_S`` (its
# page's ask, ``page asks again``).
DWELLS: Final = {
    "page asks again": 5.0,
    "switch to closed": 12.0,
    "come back": 15.0,
    "open second": 10.0,
    "revisit": 10.0,
}
# How long a session waits for a cores batch it asked for to be ready, as the panel does.
CORE_READY_S: Final = 30.0
# How long a live session waits for the jobs a step started before going on.
LIVE_SETTLE_S: Final = 90.0
LIVE_POLL_S: Final = 0.5


@dataclass(frozen=True, slots=True)
class Answer:
    status: int
    body: Any


class Driver(Protocol):
    """What the session needs of a server: its routes, its jobs, and its clock."""

    def post(self, route: str, body: Mapping[str, Any]) -> Answer: ...

    def get(self, route: str, params: Mapping[str, str]) -> Answer: ...

    def settle(self) -> None:
        """Wait until the jobs the asks so far started have ended."""
        ...

    def dwell(self, seconds: float) -> None:
        """The reader looks at what is on screen for *seconds*."""
        ...

    def pause(self, seconds: float) -> None:
        """Wait *seconds* of real time, as a page's poll does, the clock running."""
        ...

    def now(self) -> float:
        """The event log's time, seconds since the epoch, which the report's window takes."""
        ...

    def begin(self) -> float:
        """When a step begins: now, or the next whole second where a step's window must be
        told from the next one's by the report's whole-second ``since`` and ``until``."""
        ...


@dataclass(frozen=True, slots=True)
class Step:
    name: str
    started: float
    ended: float
    # How long the reader dwelt before it, 0 for a step that follows the one before at once.
    dwelt: float
    # What the step opened or read, for the record: pull request numbers, by what.
    notes: Mapping[str, Any] = field(default_factory=dict[str, Any])


@dataclass
class _Session:
    driver: Driver
    steps: list[Step] = field(default_factory=list[Step])
    opened: list[int] = field(default_factory=list[int])
    windows: int = 0
    dwelt: float = 0.0

    def dwell(self, seconds: float) -> None:
        self.driver.dwell(seconds)
        self.dwelt = seconds

    @contextmanager
    def step(self, name: str, **notes: Any) -> Any:
        started, dwelt, self.dwelt = self.driver.begin(), self.dwelt, 0.0
        yield notes
        self.steps.append(Step(name, started, self.driver.now(), dwelt, notes))

    def list_ask(self, state: str, *, background: bool = False) -> Answer:
        body: dict[str, Any] = {"state": state, "target": DISPLAY_ROWS}
        if background:
            body["background"] = True
        return _ok(self.driver.post(f"{PLUGIN}/pulls-refresh", body))

    def rows(self, state: str, after: int | None = None) -> tuple[list[int], str]:
        params = {"state": state, "limit": str(SCREEN_ROWS)}
        if after is not None:
            params["after"] = str(after)
        window = _ok(self.driver.get(f"{PLUGIN}/pulls", params)).body
        return [row["number"] for row in window["rows"]], window["generation"]

    def listed(self, state: str) -> tuple[list[int], str]:
        """The first screen of *state* once the catalog has rows for it, as the tab waits."""

        deadline = time.monotonic() + LIVE_SETTLE_S
        while True:
            rows, generation = self.rows(state)
            if rows or time.monotonic() > deadline:
                return rows, generation
            self.driver.pause(0.05)

    def cores(self, state: str, generation: str, numbers: list[int], lane: str) -> str:
        """Prepare the cores of *numbers*, asking again as the panel does until the batch has
        ended, and say how it ended."""

        self.windows += 1
        body = {
            "state": state,
            "window": {"id": f"session-{self.windows}", "generation": generation},
            "numbers": numbers[:CORE_BATCH],
            "lane": lane,
        }
        deadline = time.monotonic() + CORE_READY_S
        while True:
            answer = str(
                _ok(self.driver.post(f"{PLUGIN}/pull-cores-prepare", body)).body["preparation"]
            )
            if answer not in ("started", "joined") or time.monotonic() > deadline:
                return answer
            self.driver.pause(0.05)

    def open(self, number: int) -> str:
        """Open pull request *number*'s page: its own ask, and Fetch when nothing is cached."""

        self.opened.append(number)
        asked = _ok(self.driver.post(f"{PLUGIN}/pull-refresh", {"number": number}))
        refresh = str(asked.body.get("refresh"))
        if refresh == "not_cached":
            fetched = self.driver.post(f"{PLUGIN}/pull-refresh", {"number": number, "retry": True})
            refresh = f"not_cached, then {_ok(fetched).body.get('refresh')}"
        return refresh


def _ok(answer: Answer) -> Answer:
    """*answer*, which must have been accepted."""

    if answer.status not in (200, 202):
        raise RuntimeError(f"the server answered {answer.status}: {answer.body}")
    return answer


def browse(driver: Driver) -> list[Step]:
    """Run the session against *driver* (the module docstring has the story)."""

    session = _Session(driver)
    with session.step("open the Pulls tab") as notes:
        session.list_ask("open")
        screen, generation = session.listed("open")
        if not screen:
            raise RuntimeError("the Pulls tab listed no open pull request")
        notes["cores"] = session.cores("open", generation, screen, "visible")
        notes["status_scan"] = session.list_ask("open", background=True).body.get("status_scan")
    first, second = screen[0], screen[min(1, len(screen) - 1)]
    with session.step("open the top row at once", number=first) as notes:
        notes["refresh"] = session.open(first)
    session.dwell(DWELLS["page asks again"])
    with session.step("its page asks again", number=first) as notes:
        notes["refresh"] = session.open(first)
    session.dwell(DWELLS["switch to closed"])
    with session.step("switch to closed and open the first") as notes:
        notes["list"] = session.list_ask("closed").body.get("refresh")
        closed, _ = session.listed("closed")
        if closed:
            notes["number"] = closed[0]
            notes["refresh"] = session.open(closed[0])
    session.dwell(DWELLS["come back"])
    with session.step("come back to the open list and scroll") as notes:
        notes["refresh"] = session.list_ask("open", background=True).body.get("refresh")
        top = screen[:PREFETCH_ROWS]
        prefetch = {"records": top, "files": [], "changed": False}
        notes["prefetch"] = _ok(driver.post(f"{PLUGIN}/pulls-prefetch", prefetch)).body.get(
            "prefetch"
        )
        notes["top"] = top
        below, generation = session.rows("open", after=screen[-1])
        if below:
            notes["cores"] = session.cores("open", generation, below, "visible")
        if below[CORE_BATCH:]:
            notes["walk"] = session.cores("open", generation, below[CORE_BATCH:], "background")
    session.dwell(DWELLS["open second"])
    with session.step("open the second", number=second) as notes:
        notes["refresh"] = session.open(second)
    session.dwell(DWELLS["revisit"])
    with session.step("revisit the first", number=first) as notes:
        notes["refresh"] = session.open(first)
    driver.settle()
    return session.steps


def windows(steps: list[Step], ended: float) -> list[tuple[Step, float, float]]:
    """Each step with the window its calls end in: from its start to the next step's, the
    last to *ended*, since a job a step starts can end during the dwell after it. A step
    that begins on a whole second (:meth:`Driver.begin`) starts its calls after it, so the
    report's whole-second window of the step before, which ends at that second, holds none
    of them."""

    starts = [step.started for step in steps[1:]] + [ended]
    return [(step, step.started, until) for step, until in zip(steps, starts, strict=True)]


# ── The live driver ─────────────────────────────────────────────


def _fields(answer: Answer) -> dict[str, Any]:
    """*answer*'s body as an object, or none."""

    body: object = answer.body
    return dict(body) if isinstance(body, dict) else {}  # pyright: ignore[reportUnknownArgumentType]


def _stamp(moment: float) -> str:
    return datetime.fromtimestamp(moment, UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


@dataclass
class LiveDriver:
    """A real server at *url*, driven over HTTP in real time."""

    url: str
    opened: set[int] = field(default_factory=set[int])
    # The server is local: no proxy the environment names stands between them.
    _opener: urllib.request.OpenerDirector = field(
        default_factory=lambda: urllib.request.build_opener(urllib.request.ProxyHandler({}))
    )

    def _send(self, method: str, route: str, body: Mapping[str, Any] | None = None) -> Answer:
        data = None if body is None else json.dumps(body).encode()
        request = urllib.request.Request(
            self.url + route,
            data=data,
            method=method,
            headers={"content-type": "application/json"} if data is not None else {},
        )
        try:
            with self._opener.open(request, timeout=60) as response:
                return Answer(response.status, json.loads(response.read() or b"null"))
        except urllib.error.HTTPError as exc:
            return Answer(exc.code, json.loads(exc.read() or b"null"))

    def post(self, route: str, body: Mapping[str, Any]) -> Answer:
        number = body.get("number")
        if isinstance(number, int):
            self.opened.add(number)
        return self._send("POST", route, body)

    def get(self, route: str, params: Mapping[str, str]) -> Answer:
        return self._send("GET", f"{route}?{urllib.parse.urlencode(params)}")

    def _busy(self) -> bool:
        listing = [
            _fields(self.get(f"{PLUGIN}/pulls", {"state": state, "limit": "0"}))
            for state in ("open", "closed")
        ]
        statuses = _fields(self.get(f"{PLUGIN}/pull-statuses", {"numbers": "1"}))
        prefetch = _fields(self._send("GET", f"{PLUGIN}/pulls-prefetch"))
        pulls = [_fields(self.get(f"{PLUGIN}/pull", {"number": str(n)})) for n in self.opened]
        return (
            any(bool(body.get("refreshing")) for body in listing + pulls)
            or bool(statuses.get("scanning"))
            or prefetch.get("running") is not None
            or bool(prefetch.get("queued"))
        )

    def settle(self) -> None:
        deadline = time.monotonic() + LIVE_SETTLE_S
        while self._busy() and time.monotonic() < deadline:
            time.sleep(LIVE_POLL_S)

    def dwell(self, seconds: float) -> None:
        time.sleep(seconds)

    def pause(self, seconds: float) -> None:
        time.sleep(seconds)

    def now(self) -> float:
        return time.time()

    def begin(self) -> float:
        # A step begins on a whole second, so the report's windows, which take whole
        # seconds, part one step's calls from the next one's (:func:`windows`).
        now = time.time()
        started = float(int(now) + 1)
        time.sleep(started - now)
        return started

    def report(self, since: float, until: float, *, buckets: int = 1) -> Any:
        params = {"since": _stamp(since), "until": _stamp(until), "buckets": str(buckets)}
        return self.get(REPORT, params).body


def live(url: str, out: Path, *, log: Callable[[str], object] = print) -> None:
    """Run the session against the server at *url* and write what it asked of GitHub."""

    driver = LiveDriver(url.rstrip("/"))
    started = time.time()
    steps = browse(driver)
    ended = time.time()
    # A call is in the report once it has ended; the last step's settle waited for them.
    time.sleep(1)
    result = {
        "url": driver.url,
        "started": _stamp(started),
        "ended": _stamp(ended),
        "steps": [
            {
                "name": step.name,
                "dwelt": step.dwelt,
                "started": _stamp(since),
                "until": _stamp(until),
                "notes": dict(step.notes),
                "report": driver.report(since, until),
            }
            for step, since, until in windows(steps, ended + 1)
        ],
        "report": driver.report(started, ended + 1, buckets=12),
    }
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    log(f"{len(steps)} steps in {ended - started:.0f} s; the report is in {out}")


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description="Run one scripted session of browsing.")
    commands = parser.add_subparsers(dest="command", required=True)
    run = commands.add_parser("live", help="run the session against a running server")
    run.add_argument("--url", required=True, help="the server, e.g. http://127.0.0.1:8123")
    run.add_argument("--out", required=True, type=Path, help="where to write the reports")
    args = parser.parse_args(argv)
    live(args.url, args.out)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
