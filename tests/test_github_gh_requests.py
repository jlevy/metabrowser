"""The GitHub request report: what each ``gh`` span records, and what the report adds up.

The report is for measuring browsing before and after a change, so it must say what the
log holds and nothing else. These hold the records to the production code that writes
them (the cost ``gh_budget`` counted, gh's own time, the network slot a job waited for)
and the report to properties of any log: every call is counted once in each grouping,
the time in flight covers the calls' span, and a call added or left out moves exactly
the counts it should.
"""

from __future__ import annotations

import asyncio
import json
import os
import random
import time
from collections.abc import Callable, Generator, Sequence
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import pytest

from metabrowser import event_log, home
from metabrowser.builtin_plugins.github import gh, gh_budget, gh_lanes
from metabrowser.builtin_plugins.github.gh_requests import (
    DUPLICATE_WINDOW_S,
    MAX_BUCKETS,
    REPORTED_BUDGETS,
    REPORTED_LANES,
    Query,
    parse_query,
    report,
)
from metabrowser.event_log_route import QueryError
from metabrowser.mirror_refresh import RefreshCoordinator

NOW = datetime(2026, 11, 26, 10, 0, tzinfo=UTC)
EPOCH = datetime(2000, 1, 1, tzinfo=UTC)
QUERY = "query Fixed($number: Int!) { viewer { login } rateLimit { cost } }"


@pytest.fixture(autouse=True)
def fresh_budget() -> Generator[None]:
    gh_budget.forget()
    yield
    gh_budget.forget()


@pytest.fixture
def sink(tmp_path: Path) -> Generator[event_log.EventLog]:
    state = tmp_path / "state"
    home.ensure_storage_root(state)
    home.ensure_private_directory(state, event_log.EVENTS_DIRECTORY)
    log = event_log.EventLog(state / event_log.EVENTS_DIRECTORY, state)
    with event_log.installed(log):
        yield log
    log.close()


def _records(log: event_log.EventLog) -> list[dict[str, Any]]:
    assert log.path is not None
    return [json.loads(line) for line in log.path.read_text(encoding="utf-8").splitlines()]


def _gh_ends(log: event_log.EventLog) -> list[dict[str, Any]]:
    return [r for r in _records(log) if r["kind"] == "subprocess" and r["event"] == "end"]


def _answer(status: int, body: bytes = b"", *, etag: str = 'W/"a"') -> tuple[int, bytes, bytes]:
    """What gh prints for an answer, and how it exits: ``gh api`` exits 1 past a 2xx."""

    reason = {200: "OK", 304: "Not Modified", 404: "Not Found"}[status]
    out = f"HTTP/2.0 {status} {reason}\r\nEtag: {etag}\r\n\r\n".encode() + body
    if 200 <= status < 300:
        return 0, out, b""
    return 1, out, f"gh: HTTP {status}\n".encode()


def _stand_in_gh(
    monkeypatch: pytest.MonkeyPatch, answer: Callable[[Sequence[str]], tuple[int, bytes, bytes]]
) -> list[Sequence[str]]:
    """Stand in for the gh process alone, so ``gh._run`` spans and reads its answer."""

    calls: list[Sequence[str]] = []

    async def run_in(_exe: str, args: Sequence[str], **_kwargs: object) -> object:
        calls.append(args)
        returncode, stdout, stderr = answer(args)
        return gh._Completed(returncode, stdout, stderr)  # pyright: ignore[reportPrivateUsage]

    monkeypatch.setattr(gh, "_run_in", run_in)
    return calls


def _github(args: Sequence[str]) -> tuple[int, bytes, bytes]:
    """GitHub as these tests need it: a pull's read is ``200`` unless it carries an ETag,
    then ``304``; a missing one is ``404``; a query costs its ``number``."""

    path = args[-1]
    if "graphql" in args[1:2]:
        number = next(a.partition("=")[2] for a in args if a.startswith("number="))
        data = {"data": {"viewer": {"login": "octo"}, "rateLimit": {"cost": int(number)}}}
        return _answer(200, json.dumps(data).encode())
    if path.endswith("/404"):
        return _answer(404, b'{"message": "Not Found"}')
    if any(a.startswith("If-None-Match:") for a in args):
        return _answer(304)
    return _answer(200, b'{"number": 7}')


async def _read_pull(etag: str | None = None) -> None:
    await gh.gh_api("repos/octo/demo/pulls/7", etag=etag, now=NOW)


def test_what_gh_budget_counted_is_what_the_report_says_each_budget_spent(
    sink: event_log.EventLog, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The span's cost is the number ``gh_budget`` counts, and its budget the count it is
    charged to, so the report's spending agrees with the ceiling's and the share's."""

    _stand_in_gh(monkeypatch, _github)

    async def job(name: str, cost: int) -> None:
        with event_log.span("job", name):
            await gh.gh_api("repos/octo/demo/pulls/7", now=NOW)
            await gh.gh_api("repos/octo/demo/pulls/7", etag='W/"a"', now=NOW)
            with pytest.raises(gh.GhError):
                await gh.gh_api("repos/octo/demo/pulls/404", now=NOW)
            await gh.gh_graphql(QUERY, {"number": cost}, now=NOW)

    async def session() -> None:
        await job("test.automatic", 3)
        with gh_budget.speculative():
            await job("test.speculative", 2)
        with gh_budget.speculative(walk=True):
            await job("test.walk", 5)
        with gh_budget.readers_own():
            await job("test.reader", 7)

    asyncio.run(session())
    assert sink.path is not None
    answer = report(Query(since=EPOCH), state=sink.path.parent.parent, directory=sink.path.parent)
    spent = {
        budget: row["core"] + row["graphql_points"] for budget, row in answer["budgets"].items()
    }
    assert spent["automatic"] + spent["speculative"] + spent["walk"] == (
        gh_budget.automatic_spent(NOW)
    )
    assert spent["speculative"] + spent["walk"] == gh_budget.speculative_spent(NOW)
    assert spent["walk"] == gh_budget.walk_spent(NOW)
    # A reader's own action is spent all the same, though no ceiling counts it.
    assert spent["reader"] == 2 + 7
    assert answer["requests"]["requests"] == len(_gh_ends(sink)) == 16
    assert {row["job"] for row in answer["jobs"]} == {
        "test.automatic",
        "test.speculative",
        "test.walk",
        "test.reader",
    }
    for row in answer["budgets"].values():
        if row["requests"]:
            assert (row["statuses"], row["conditional"], row["cache_hits"]) == (
                {"200": 2, "304": 1, "404": 1},
                1,
                1,
            )


def test_a_call_records_the_lane_its_work_was_started_in(
    sink: event_log.EventLog, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The lane is the context's, so a job started inside a lane serves it with nothing
    passed to it, and work nothing marks is visible (``gh_lanes``)."""

    _stand_in_gh(monkeypatch, _github)

    async def session() -> None:
        await _read_pull()
        with gh_lanes.serving("background"):
            job = asyncio.get_running_loop().create_task(_read_pull())
        await _read_pull()
        await job

    asyncio.run(session())
    assert sorted(end["attrs"]["lane"] for end in _gh_ends(sink)) == [
        "background",
        "visible",
        "visible",
    ]


def test_an_unchanged_answer_ends_its_span_answered_and_a_refusal_ends_it_failed(
    sink: event_log.EventLog, monkeypatch: pytest.MonkeyPatch
) -> None:
    """gh exits 1 on a 304 as on a 404, but only the refusal is a failure: the failures
    report counts no conditional read GitHub answered unchanged."""

    _stand_in_gh(monkeypatch, _github)

    async def reads() -> None:
        await _read_pull()
        await _read_pull(etag='W/"a"')
        with pytest.raises(gh.GhError):
            await gh.gh_api("repos/octo/demo/pulls/404", now=NOW)

    asyncio.run(reads())
    ends = {r["attrs"]["http_status"]: r for r in _gh_ends(sink)}
    assert {status: end["attrs"]["exit"] for status, end in ends.items()} == {
        200: 0,
        304: 1,
        404: 1,
    }
    assert {status: end["outcome"] for status, end in ends.items()} == {
        200: "ok",
        304: "ok",
        404: "failed",
    }
    assert "failure" not in ends[304]["attrs"]


def test_a_gh_span_lasts_as_long_as_gh_did_not_as_reading_its_answer(
    sink: event_log.EventLog, monkeypatch: pytest.MonkeyPatch
) -> None:
    _stand_in_gh(monkeypatch, _github)
    read = gh._read_answer  # pyright: ignore[reportPrivateUsage]
    slow_s = 0.3

    def slow_read(stdout: bytes, *, graphql: bool) -> object:
        time.sleep(slow_s)
        return read(stdout, graphql=graphql)

    monkeypatch.setattr(gh, "_read_answer", slow_read)
    started = time.perf_counter()
    asyncio.run(_read_pull())
    assert time.perf_counter() - started >= slow_s
    (record,) = _gh_ends(sink)
    assert record["dur_ms"] < slow_s * 1000
    assert record["attrs"]["http_status"] == 200


def test_a_fingerprint_names_what_is_asked_and_not_the_etag_a_read_carries(
    sink: event_log.EventLog, monkeypatch: pytest.MonkeyPatch
) -> None:
    _stand_in_gh(monkeypatch, _github)

    async def session() -> None:
        await _read_pull()
        await _read_pull('W/"a"')
        await _read_pull('W/"b"')
        await gh.gh_api("repos/octo/demo/pulls/8", now=NOW)
        await gh.gh_graphql(QUERY, {"number": 1}, now=NOW)
        await gh.gh_graphql(QUERY, {"number": 2}, now=NOW)

    asyncio.run(session())
    seven, again, other_tag, eight, one, two = _gh_ends(sink)
    fingerprints = [r["attrs"]["fingerprint"] for r in (seven, again, other_tag, eight, one, two)]
    assert fingerprints[0] == fingerprints[1] == fingerprints[2]
    assert len(set(fingerprints[2:])) == 4
    # The reason it exists: the log drops a query's variables, which tell the reads apart.
    assert one["attrs"]["args"] == two["attrs"]["args"]


def test_a_wait_for_a_network_slot_is_on_the_record_of_the_span_that_waited(
    sink: event_log.EventLog,
) -> None:
    held_s = 0.2

    async def scenario() -> None:
        coordinator = RefreshCoordinator(limit=1)
        holding = asyncio.Event()

        async def holder() -> None:
            holding.set()
            await asyncio.sleep(held_s)

        async def pager() -> None:
            # Two pages, each in a slot it takes itself: the first waits for the holder,
            # the second takes a free slot.
            for _ in range(2):
                async with coordinator.slot():
                    await asyncio.sleep(0)

        coordinator.start("holder", holder, network=True)
        await holding.wait()
        coordinator.start("pager", pager, network=False)
        await asyncio.wait(
            [job for job in (coordinator.job("holder"), coordinator.job("pager")) if job]
        )
        await coordinator.aclose()

    asyncio.run(scenario())
    ends = {
        r["name"].rpartition(".")[2]: r["attrs"]
        for r in _records(sink)
        if r["kind"] == "job" and r["event"] == "end"
    }
    assert ends["holder"]["queued_ms"] < held_s * 1000 / 2
    # Summed over both pages: the second, free slot does not replace the first wait.
    assert ends["pager"]["queued_ms"] >= held_s * 1000 / 2


# ── The report over any log ───────────────────────────────────────────────────────────

_STARTED = "20261126T100000Z"
_STATUSES = (200, 304, 404)


def _end(
    pid: int,
    span: int,
    *,
    start: float,
    dur_ms: float,
    kind: str = "subprocess",
    name: str = "gh api",
    parent: int | None = None,
    outcome: str = "ok",
    attrs: dict[str, Any] | None = None,
) -> dict[str, Any]:
    moment = NOW + timedelta(seconds=start + dur_ms / 1000)
    record: dict[str, Any] = {
        "v": event_log.SCHEMA_VERSION,
        "ts": moment.isoformat(timespec="milliseconds")[:-6] + "Z",
        "event": "end",
        "kind": kind,
        "name": name,
        "span": span,
    }
    if parent is not None:
        record["parent"] = parent
    record.update(dur_ms=dur_ms, outcome=outcome, pid=pid, attrs=attrs or {})
    return record


def _call(
    pid: int,
    span: int,
    *,
    start: float,
    dur_ms: float,
    parent: int | None,
    fingerprint: str,
    budget: str = "automatic",
    lane: str | None = "visible",
    status: int | None = 200,
    graphql: bool = False,
    conditional: bool = False,
) -> dict[str, Any]:
    args = ["api", "graphql"] if graphql else ["api", "--hostname", "github.com"]
    if conditional:
        args += ["-H", "If-None-Match: …"]
    attrs: dict[str, Any] = {"args": args, "budget": budget, "fingerprint": fingerprint}
    if lane is not None:
        attrs["lane"] = lane
    if status is not None:
        attrs |= {"http_status": status, "cost": 1 if graphql or status != 304 else 0}
    # gh exits 1 on a 304 too, and its span still ends answered (gh._run).
    failed = status is None or not (200 <= status < 300 or status == 304)
    return _end(
        pid,
        span,
        start=start,
        dur_ms=dur_ms,
        parent=parent,
        outcome="failed" if failed else "ok",
        attrs=attrs,
    )


def _random_log(
    seed: int, *, pids: Sequence[int] = (4242, 4343)
) -> dict[int, list[dict[str, Any]]]:
    """A log of a few hundred calls in a minute, in jobs of either kind, for each pid."""

    chance = random.Random(seed)
    log: dict[int, list[dict[str, Any]]] = {}
    for pid in pids:
        records: list[dict[str, Any]] = []
        jobs = list(range(1, 9))
        for job in jobs:
            records.append(
                _end(
                    pid,
                    job,
                    start=0,
                    dur_ms=60_000,
                    kind=chance.choice(("job", "request")),
                    name=f"test.job{job % 4}",
                    attrs={"queued_ms": round(chance.uniform(0, 500), 1)}
                    if chance.random() < 0.5
                    else {},
                )
            )
        for span in range(100, 100 + chance.randrange(80, 160)):
            graphql = chance.random() < 0.4
            records.append(
                _call(
                    pid,
                    span,
                    start=round(chance.uniform(0, 55), 3),
                    dur_ms=round(chance.uniform(1, 3000), 1),
                    parent=chance.choice([*jobs, None, 99]),
                    fingerprint=f"f{chance.randrange(12)}",
                    budget=chance.choice(gh_budget.BUDGETS),
                    # A call recorded before calls recorded their lane is unknown.
                    lane=chance.choice([*gh_lanes.LANES, None]),
                    status=chance.choice([*_STATUSES, None]) if not graphql else 200,
                    graphql=graphql,
                    conditional=chance.random() < 0.5,
                )
            )
        log[pid] = sorted(records, key=lambda r: r["ts"])
    return log


def _write(directory: Path, log: dict[int, list[dict[str, Any]]]) -> None:
    for pid, records in log.items():
        segment = directory / f"{event_log.FILE_PREFIX}{_STARTED}-p{pid}-000.jsonl"
        segment.write_text("".join(json.dumps(r) + "\n" for r in records), encoding="utf-8")
        segment.chmod(0o600)
        written = (NOW + timedelta(minutes=5)).timestamp()
        os.utime(segment, (written, written))


def _report(tmp_path: Path, log: dict[int, list[dict[str, Any]]], **query: Any) -> dict[str, Any]:
    state = tmp_path / "report-state"
    home.ensure_storage_root(state)
    home.ensure_private_directory(state, event_log.EVENTS_DIRECTORY)
    directory = state / event_log.EVENTS_DIRECTORY
    for old in directory.iterdir():
        old.unlink()
    _write(directory, log)
    return report(Query(since=EPOCH, **query), state=state, directory=directory)


_ADDITIVE = ("requests", "core", "graphql_points", "conditional", "cache_hits")


@pytest.mark.parametrize("seed", range(4))
def test_every_call_is_counted_once_in_each_grouping(tmp_path: Path, seed: int) -> None:
    log = _random_log(seed)
    answer = _report(tmp_path, log)
    total = answer["requests"]
    assert set(answer["budgets"]) == set(REPORTED_BUDGETS)
    assert list(answer["lanes"]) == list(REPORTED_LANES)
    assert answer["jobs_more"] == 0
    groupings = (list(answer["lanes"].values()), list(answer["budgets"].values()), answer["jobs"])
    for rows in groupings:
        for field in _ADDITIVE:
            assert sum(row[field] for row in rows) == total[field], field
        for status, count in total["statuses"].items():
            assert sum(row["statuses"].get(status, 0) for row in rows) == count
    assert total["requests"] == sum(
        r["kind"] == "subprocess" for records in log.values() for r in records
    )
    by_pid = [_report(tmp_path, log, pid=pid)["requests"] for pid in log]
    for field in _ADDITIVE:
        assert sum(row[field] for row in by_pid) == total[field]


@pytest.mark.parametrize("seed", range(4))
def test_each_row_holds_its_bounds(tmp_path: Path, seed: int) -> None:
    answer = _report(tmp_path, _random_log(seed))
    rows = [answer["requests"], *answer["lanes"].values(), *answer["budgets"].values()]
    for row in [*rows, *answer["jobs"]]:
        answered = sum(row["statuses"].values()) + sum(row["no_status"].values())
        assert answered == row["commands"]["rest"] + row["commands"]["graphql"]
        assert row["cache_hits"] <= row["conditional"] <= row["commands"]["rest"]
        assert row["share_304"] is None or 0 <= row["share_304"] <= 1
        for figures in (row["latency"], row["queued"]):
            if figures["max_ms"] is not None:
                assert figures["p50_ms"] <= figures["p95_ms"] <= figures["max_ms"]
                assert figures["max_ms"] <= figures["total_ms"]
        assert row["peak_in_flight"] <= answer["requests"]["peak_in_flight"]


@pytest.mark.parametrize("buckets", [1, 7, 60])
def test_the_time_in_flight_covers_the_calls_from_first_start_to_last_end(
    tmp_path: Path, buckets: int
) -> None:
    answer = _report(tmp_path, _random_log(buckets), buckets=buckets)
    flight = answer["in_flight"]
    first = datetime.fromisoformat(flight["first"]).timestamp()
    last = datetime.fromisoformat(flight["last"]).timestamp()
    levels = flight["levels_ms"]
    assert sum(levels.values()) == pytest.approx(
        (last - first) * 1000, abs=1.0 + 0.05 * len(levels)
    )
    assert (
        flight["peak"]
        == max(int(level) for level in levels)
        == answer["requests"]["peak_in_flight"]
    )
    assert len(flight["series"]) == buckets
    assert max(part["peak"] for part in flight["series"]) == flight["peak"]
    for part in flight["series"]:
        assert 0 <= part["mean"] <= part["peak"]


def test_a_call_asked_again_is_a_duplicate_only_while_it_runs_or_just_after(
    tmp_path: Path,
) -> None:
    def duplicates(*starts: float) -> dict[str, int]:
        calls = [
            _call(4242, 100 + index, start=start, dur_ms=1000, parent=None, fingerprint="same")
            for index, start in enumerate(starts)
        ]
        other = _call(4242, 99, start=0.5, dur_ms=1000, parent=None, fingerprint="other")
        return _report(tmp_path, {4242: [*calls, other]})["requests"]["duplicates"]

    assert duplicates(0) == {"in_flight": 0, "repeated": 0}
    assert duplicates(0, 0.5) == {"in_flight": 1, "repeated": 0}
    assert duplicates(0, 1 + DUPLICATE_WINDOW_S / 2) == {"in_flight": 0, "repeated": 1}
    assert duplicates(0, 1 + DUPLICATE_WINDOW_S * 2) == {"in_flight": 0, "repeated": 0}
    # Another process asking the same is its own read, not this one's duplicate.
    twin = _call(4343, 100, start=0.5, dur_ms=1000, parent=None, fingerprint="same")
    alone = _call(4242, 100, start=0, dur_ms=1000, parent=None, fingerprint="same")
    answer = _report(tmp_path, {4242: [alone], 4343: [twin]})
    assert answer["requests"]["duplicates"] == {"in_flight": 0, "repeated": 0}


def test_a_call_outside_the_window_or_of_another_process_is_not_counted(
    tmp_path: Path,
) -> None:
    log = _random_log(7, pids=(4242,))
    until = NOW + timedelta(minutes=2)
    before = _report(tmp_path, log, until=until, pid=4242)
    late = _call(4242, 900, start=200, dur_ms=50, parent=None, fingerprint="late")
    elsewhere = _call(4343, 901, start=10, dur_ms=50, parent=None, fingerprint="else")
    after = _report(tmp_path, {4242: [*log[4242], late], 4343: [elsewhere]}, until=until, pid=4242)
    assert after["requests"] == before["requests"]
    assert after["in_flight"] == before["in_flight"]


@pytest.mark.parametrize(
    "params",
    [
        {"limit": "5"},
        {"since": "yesterday"},
        {"since": "2026-11-26T10:01:00Z", "until": "2026-11-26T10:00:00Z"},
        {"pid": "-1"},
        {"pid": "4²"},
        {"buckets": "0"},
        {"buckets": str(MAX_BUCKETS + 1)},
    ],
)
def test_a_parameter_the_report_cannot_take_is_refused(params: dict[str, str]) -> None:
    with pytest.raises(QueryError):
        parse_query(params, now=NOW)


def test_the_window_opens_an_hour_ago_by_default() -> None:
    query = parse_query({}, now=NOW)
    assert NOW - query.since == timedelta(seconds=event_log.RECENT_WINDOW_S)
    assert query.until is None
