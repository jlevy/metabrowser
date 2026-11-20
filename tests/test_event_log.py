"""The structured event log: spans, their records, bounds, and the work a page waits on.

The owner asked, 2026-11-19, whether a pull request's Diff summary that does not load
"after many seconds" is captured in the logs. It was not: the refresh and comparison
jobs the page waits on are not requests, and a ``gh`` that timed out left nothing even
at debug level. These tests hold the log to recording that work: a job that starts and
never ends, and a ``gh`` that never answers, each leave a record within seconds.
"""

from __future__ import annotations

import asyncio
import json
import os
import stat
import sys
import time
from collections.abc import Generator
from pathlib import Path
from typing import Any

import pytest
from starlette.applications import Starlette
from starlette.middleware import Middleware
from starlette.requests import Request
from starlette.responses import JSONResponse, Response
from starlette.routing import Route
from starlette.testclient import TestClient

from metabrowser import event_log, home
from metabrowser.builtin_plugins.diff.comparison_cache import ComparisonCache
from metabrowser.builtin_plugins.github import gh as gh_module
from metabrowser.builtin_plugins.github import pull_list
from metabrowser.builtin_plugins.github.pull_record import PullRefreshStamp
from metabrowser.event_log_route import QueryError, parse_query, read_log
from metabrowser.git.process import GitCommandError, run_git
from metabrowser.mirror_refresh import RefreshCoordinator
from metabrowser.server import _end_request_span, _SlowRequestLogMiddleware
from metabrowser.server_timing import Record
from tests.required_tools import require_git


def _state(tmp_path: Path) -> tuple[Path, Path]:
    state = tmp_path / "state"
    home.ensure_storage_root(state)
    home.ensure_private_directory(state, event_log.EVENTS_DIRECTORY)
    return state, state / event_log.EVENTS_DIRECTORY


@pytest.fixture
def sink(tmp_path: Path) -> Generator[event_log.EventLog]:
    state, directory = _state(tmp_path)
    log = event_log.EventLog(directory, state)
    with event_log.installed(log):
        yield log
    log.close()


def _records(log: event_log.EventLog) -> list[dict[str, Any]]:
    assert log.path is not None
    return [json.loads(line) for line in log.path.read_text(encoding="utf-8").splitlines()]


def _named(log: event_log.EventLog, name: str) -> list[dict[str, Any]]:
    return [record for record in _records(log) if record["name"] == name]


# ── spans and records ─────────────────────────────────────────


def test_no_log_costs_a_shared_span_and_passes_a_job_through() -> None:
    assert not event_log.enabled()
    assert event_log.begin("request", "GET /") is event_log.NULL_SPAN

    async def work() -> int:
        return 7

    coroutine = work()
    assert event_log.job(coroutine, "work") is coroutine
    assert asyncio.run(coroutine) == 7


def test_an_end_record_carries_the_schema_duration_outcome_and_parent(
    sink: event_log.EventLog,
) -> None:
    with event_log.span("request", "GET /api/tree") as outer:
        with event_log.span("subprocess", "git rev-parse", attrs={"args": ["rev-parse"]}):
            pass
        outer.set(status=200)
    inner, request = _records(sink)
    assert inner["v"] == event_log.SCHEMA_VERSION == 1
    assert inner["event"] == "end"
    assert inner["kind"] == "subprocess"
    assert inner["parent"] == request["span"]
    assert inner["outcome"] == "ok"
    assert inner["pid"] == os.getpid()
    assert inner["ts"].endswith("Z")
    assert inner["attrs"] == {"args": ["rev-parse"]}
    assert "parent" not in request
    assert request["attrs"] == {"status": 200}
    assert isinstance(request["dur_ms"], float)


@pytest.mark.parametrize(
    ("raised", "outcome"),
    [
        (asyncio.CancelledError(), "cancelled"),
        (TimeoutError("late"), "timeout"),
        (RuntimeError("broke"), "failed"),
    ],
)
def test_an_exception_ends_the_span_by_its_kind_and_still_propagates(
    sink: event_log.EventLog, raised: BaseException, outcome: str
) -> None:
    with pytest.raises(type(raised)), event_log.span("job", "work"):
        raise raised
    (record,) = _records(sink)
    assert record["outcome"] == outcome
    if outcome != "cancelled":
        assert record["attrs"]["error"].startswith(type(raised).__name__)


def test_a_job_writes_its_start_names_its_parent_and_fails_by_what_it_noted(
    sink: event_log.EventLog,
) -> None:
    async def refresh() -> None:
        event_log.current().note_failure("network_error", "gh did not answer within 15 s")

    async def scenario() -> None:
        with event_log.span("request", "POST /api/plugin/github/pull-refresh"):
            task = asyncio.create_task(event_log.job(refresh(), "pulls.refresh"))
        await task

    asyncio.run(scenario())
    # The start is written when the job first runs, here after its request has ended.
    request, start, end = _records(sink)
    assert (start["event"], start["name"]) == ("start", "pulls.refresh")
    assert start["parent"] == request["span"] == end["parent"]
    assert end["outcome"] == "failed"
    assert end["attrs"] == {
        "failure": "network_error",
        "failure_message": "gh did not answer within 15 s",
    }


# ── work that never finishes ──────────────────────────────────


def test_open_records_mark_a_late_span_at_the_threshold_and_each_doubling(
    sink: event_log.EventLog,
) -> None:
    late = event_log.begin("job", "stuck", announce=True)
    threshold_s = event_log.OPEN_AFTER_MS / 1000
    for after in (0.5, threshold_s + 0.1, threshold_s + 0.2, 2 * threshold_s + 0.1):
        sink.check_open(now=late.started + after)
    opens = [r for r in _named(sink, "stuck") if r["event"] == "open"]
    assert [round(r["dur_ms"] / 1000, 1) for r in opens] == [
        round(threshold_s + 0.1, 1),
        round(2 * threshold_s + 0.1, 1),
    ]
    sink.close()
    assert _named(sink, "stuck")[-1]["outcome"] == "abandoned"
    assert _records(sink)[-1]["name"] == "server.stop"


def test_a_refresh_job_that_never_ends_is_on_record_from_its_start(
    sink: event_log.EventLog,
) -> None:
    """The refresh a pull request page polls for: started, late, then abandoned."""

    async def scenario() -> None:
        coordinator = RefreshCoordinator()
        never = asyncio.Event()

        async def _pull_job() -> None:
            await never.wait()

        with event_log.span("request", "POST /api/plugin/github/pull-refresh"):
            assert coordinator.start("octo/demo:pull/7", _pull_job, network=True) == "started"
        await asyncio.sleep(0)
        (job,) = [s for s in event_log.open_spans() if s.kind == "job"]
        assert job.name == "test_event_log._pull_job"
        sink.check_open(now=sink._open[job.span].started + 3.0)
        await coordinator.aclose()

    asyncio.run(scenario())
    records = _named(sink, "test_event_log._pull_job")
    assert [r["event"] for r in records] == ["start", "open", "end"]
    assert records[0]["attrs"] == {"key": "octo/demo:pull/7", "network": True}
    assert records[1]["dur_ms"] >= event_log.OPEN_AFTER_MS
    assert records[2]["outcome"] == "cancelled"
    assert "queued_ms" in records[2]["attrs"]


def test_the_comparison_a_diff_summary_waits_for_is_a_job_its_request_started(
    sink: event_log.EventLog,
) -> None:
    async def scenario() -> None:
        cache = ComparisonCache()
        never = asyncio.Event()

        async def compute() -> Any:
            await never.wait()

        with event_log.span("request", "GET /api/plugin/github/pull-comparison"):
            waiting = asyncio.create_task(cache.manifest(("store", "left", "right"), compute))
            await asyncio.sleep(0.01)
        (job,) = [s for s in event_log.open_spans() if s.kind == "job"]
        assert job.name == "comparison_cache.manifest"
        waiting.cancel()
        await asyncio.sleep(0)
        # The reader left; the listing it started is still running, and still open.
        assert [s.name for s in event_log.open_spans()] == ["comparison_cache.manifest"]
        for task in asyncio.all_tasks() - {asyncio.current_task()}:
            task.cancel()
        await asyncio.sleep(0.01)

    asyncio.run(scenario())
    start, request, end = (
        _named(sink, "comparison_cache.manifest")[0],
        *(r for r in _records(sink) if r["kind"] == "request"),
        _named(sink, "comparison_cache.manifest")[-1],
    )
    assert start["event"] == "start"
    assert start["parent"] == request["span"]
    assert start["attrs"] == {"key": "store left right"}
    assert request["outcome"] == "ok"
    assert end["outcome"] == "cancelled"


@pytest.mark.skipif(os.name != "posix", reason="the stand-in gh is a POSIX shell script")
def test_a_gh_that_never_answers_ends_timeout_with_where_it_stalled(
    sink: event_log.EventLog, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The Step 1 failure: ``gh auth status`` hangs and the refresh says it timed out."""

    directory = tmp_path / "bin"
    directory.mkdir()
    gh = directory / "gh"
    gh.write_text("#!/bin/sh\necho 'connecting to api.github.com' >&2\nexec sleep 30\n")
    gh.chmod(gh.stat().st_mode | stat.S_IXUSR)
    monkeypatch.setenv("PATH", f"{directory}{os.pathsep}{os.environ.get('PATH', '')}")

    async def scenario() -> None:
        async def refresh() -> None:
            with pytest.raises(gh_module.GhError, match="did not answer within 0.5 s"):
                await gh_module.gh_active_account(timeout_s=0.5)

        await event_log.job(refresh(), "pulls.refresh")

    asyncio.run(scenario())
    (gh_end,) = _named(sink, "gh auth")
    job_start = _named(sink, "pulls.refresh")[0]
    assert gh_end["outcome"] == "timeout"
    assert gh_end["parent"] == job_start["span"]
    assert gh_end["attrs"]["args"] == [
        "auth",
        "status",
        "--active",
        "--hostname",
        "github.com",
        "--json",
        "hosts",
    ]
    assert gh_end["attrs"]["stalled"] == "before any answer"
    assert gh_end["attrs"]["stderr_tail"] == "connecting to api.github.com"
    assert gh_end["attrs"]["timeout_s"] == 0.5


def test_git_processes_are_spans_with_their_command_and_failure(
    sink: event_log.EventLog, tmp_path: Path
) -> None:
    require_git()
    repository = tmp_path / "repo"
    repository.mkdir()

    async def scenario() -> None:
        with pytest.raises(GitCommandError):
            await run_git(["rev-parse", "--verify", "no-such-ref"], cwd=repository)

    asyncio.run(scenario())
    (record,) = _named(sink, "git rev-parse")
    assert record["outcome"] == "failed"
    assert record["attrs"]["args"] == ["rev-parse", "--verify", "no-such-ref"]
    assert record["attrs"]["exit"] != 0
    assert "not a git repository" in record["attrs"]["stderr_tail"]


# ── requests ──────────────────────────────────────────────────


def test_every_request_is_a_span_and_a_job_it_starts_names_it(
    sink: event_log.EventLog,
) -> None:
    async def started(_request: Request) -> Response:
        coordinator = RefreshCoordinator()

        async def _files_job() -> None:
            return None

        coordinator.start("octo/demo:pull/7/files", _files_job, network=False)
        await coordinator.drain(timeout_s=5)
        return JSONResponse({"refresh": "started"}, status_code=202)

    async def broken(_request: Request) -> Response:
        return Response("no", status_code=503)

    app = Starlette(
        routes=[Route("/start", started), Route("/broken", broken)],
        middleware=[Middleware(_SlowRequestLogMiddleware, threshold_ms=0, verbose=False)],
    )
    client = TestClient(app)
    assert client.get("/start?number=7").status_code == 202
    assert client.get("/broken").status_code == 503
    (request,) = _named(sink, "GET /start")
    assert request["outcome"] == "ok"
    assert request["attrs"]["status"] == 202
    assert request["attrs"]["query"] == "number=7"
    job_start, job_end = _named(sink, "test_event_log._files_job")
    assert job_start["parent"] == request["span"]
    assert job_end["outcome"] == "ok"
    (failed,) = _named(sink, "GET /broken")
    assert failed["outcome"] == "failed"
    assert failed["attrs"]["status"] == 503


# ── privacy and bounds ────────────────────────────────────────


def test_redaction_drops_tokens_credentials_and_escape_codes() -> None:
    text = (
        "\x1b[31mfatal\x1b[0m: https://x-access-token:secret@github.com/o/r "
        "token ghp_" + "a" * 36 + " Authorization: Bearer abc\x07"
    )
    cleaned = event_log.redact(text)
    assert "secret" not in cleaned
    assert "ghp_" not in cleaned
    assert "abc" not in cleaned
    assert "\x1b" not in cleaned and "\x07" not in cleaned
    assert cleaned.startswith("fatal: https://[credentials]@github.com/o/r")
    assert len(event_log.redact("x" * 5000)) == event_log.MAX_TEXT_CHARS


@pytest.mark.parametrize(
    "text",
    [
        "access_token=s3cr3tvalue",
        "client_secret=s3cr3tvalue",
        "GITHUB_TOKEN=s3cr3tvalue",
        "x_api_key: s3cr3tvalue",
        "x-api-key: s3cr3tvalue",
        "password=s3cr3tvalue",
    ],
)
def test_redaction_drops_the_values_of_compound_secret_names(text: str) -> None:
    cleaned = event_log.redact(f"curl failed with {text} set")
    assert "s3cr3tvalue" not in cleaned
    assert cleaned.endswith("[redacted] set")


def test_gh_command_lines_keep_names_and_drop_values() -> None:
    args = [
        "api",
        "graphql",
        "-f",
        "query=query { viewer { login } }",
        "-F",
        "number=7",
        "-H",
        'If-None-Match: W/"abc"',
        "--jq",
        ".data",
        "repos/o/r/pulls/7/files?per_page=100",
    ]
    assert gh_module.loggable_args(args) == [
        "api",
        "graphql",
        "-f",
        "query=…",
        "-F",
        "number=…",
        "-H",
        "If-None-Match: …",
        "--jq",
        "…",
        "repos/o/r/pulls/7/files?per_page=100",
    ]


def test_segments_roll_and_the_directory_stays_within_its_total(tmp_path: Path) -> None:
    state, directory = _state(tmp_path)
    log = event_log.EventLog(directory, state, max_file_bytes=4096, max_total_bytes=12_000)
    with event_log.installed(log):
        for index in range(200):
            with event_log.span("request", f"GET /{index}"):
                pass
    log.close()
    files = event_log.list_files(directory)
    assert len(files) >= 2
    assert sum(f.bytes for f in files) <= 12_000 + 4096
    assert all(f.bytes <= 4096 for f in files)
    assert log.path is not None and log.path.name in {f.name for f in files}
    assert [f.segment for f in files] == sorted((f.segment for f in files), reverse=True)


def test_an_oversized_record_keeps_its_core_fields(sink: event_log.EventLog) -> None:
    with event_log.span("job", "huge", attrs={"blob": "x" * (2 * event_log.MAX_LINE_BYTES)}):
        pass
    (record,) = _records(sink)
    assert record["name"] == "huge"
    assert record["outcome"] == "ok"
    assert set(record["attrs"]) == {"dropped_bytes"}


def test_an_oversized_name_is_cut_so_the_line_stays_within_its_bound(
    sink: event_log.EventLog,
) -> None:
    with event_log.span("request", "GET /" + "n" * (12 * 1024)):
        pass
    assert sink.path is not None
    (line,) = sink.path.read_bytes().splitlines()
    assert len(line) + 1 <= event_log.MAX_LINE_BYTES
    record = json.loads(line)
    assert record["name"].startswith("GET /nnn")
    assert set(record["attrs"]) == {"dropped_bytes"}


# ── failures of the log itself ────────────────────────────────


def test_text_that_cannot_be_encoded_is_escaped_and_never_fails_the_work(
    sink: event_log.EventLog,
) -> None:
    """Git output decoded with surrogateescape holds lone surrogates, which UTF-8 refuses."""

    odd = b"na\xefve".decode("utf-8", errors="surrogateescape")
    with (
        pytest.raises(RuntimeError, match="broken"),
        event_log.span("job", f"read {odd}", attrs={"path": odd}),
    ):
        raise RuntimeError(f"broken {odd}")
    (record,) = _records(sink)
    assert record["outcome"] == "failed"
    assert record["name"] == f"read {odd}"
    assert record["attrs"]["path"] == odd
    assert record["attrs"]["error"] == f"RuntimeError: broken {odd}"


def test_a_record_that_cannot_be_encoded_is_dropped_without_raising(
    sink: event_log.EventLog,
) -> None:
    cycle: list[object] = []
    cycle.append(cycle)
    event_log.mark("lifecycle", "cycle", value=cycle)
    event_log.mark("lifecycle", "after")
    assert [r["name"] for r in _records(sink)] == ["after"]


def test_a_failed_or_short_write_pauses_the_log_and_a_fresh_segment_resumes_it(
    sink: event_log.EventLog, monkeypatch: pytest.MonkeyPatch
) -> None:
    event_log.mark("lifecycle", "before")
    first = sink.path
    assert first is not None
    target = sink._fd
    real_write = os.write

    def short(fd: int, data: bytes) -> int:
        return real_write(fd, data[:5]) if fd == target else real_write(fd, data)

    monkeypatch.setattr(event_log.os, "write", short)
    event_log.mark("lifecycle", "torn")
    monkeypatch.setattr(event_log.os, "write", real_write)
    # Paused: the route names no file, and records wait for the backoff.
    assert sink.path is None
    event_log.mark("lifecycle", "during backoff")
    assert sink.path is None
    sink._retry_at = 0.0  # the backoff has passed
    event_log.mark("lifecycle", "after")
    assert sink.path is not None and sink.path != first
    assert [r["name"] for r in _records(sink)] == ["after"]
    # A write that raises pauses it the same way.
    assert sink._fd is not None
    os.close(sink._fd)
    event_log.mark("lifecycle", "into a closed descriptor")
    assert sink.path is None
    assert sink._retry_s == 2 * event_log.RETRY_FIRST_S


def test_one_servers_prune_keeps_another_live_servers_segment(tmp_path: Path) -> None:
    """An idle server's segment has the oldest time; a busy one's prune must keep it."""

    state, directory = _state(tmp_path)
    idle = event_log.EventLog(directory, state, clock=lambda: 1_700_000_000.0)
    idle.write(idle.record("mark", "lifecycle", "server.start"))
    assert idle.path is not None
    long_ago = time.time() - 3600
    os.utime(idle.path, (long_ago, long_ago))
    # A segment of a server that has stopped, older still: no process has this pid.
    stopped = directory / "events-20231114T000000Z-p99999999-000.jsonl"
    stopped.write_bytes(b"{}\n" * 4000)
    os.utime(stopped, (long_ago - 60, long_ago - 60))
    busy = event_log.EventLog(
        directory,
        state,
        max_file_bytes=4096,
        max_total_bytes=12_000,
        clock=lambda: 1_700_000_100.0,
    )
    with event_log.installed(busy):
        for index in range(200):
            with event_log.span("request", f"GET /{index}"):
                pass
    busy.close()
    names = {f.name for f in event_log.list_files(directory)}
    assert idle.path.name in names
    assert stopped.name not in names
    with event_log.installed(idle):
        status, answer = read_log(parse_query({}), state=state, directory=directory)
    assert status == 200
    assert answer["writing"] == answer["file"] == idle.path.name
    assert [e["name"] for e in answer["events"]] == ["server.start"]
    idle.close()


def test_a_segment_deleted_while_open_is_replaced_and_the_route_reads_the_newest(
    sink: event_log.EventLog,
) -> None:
    other = event_log.EventLog(sink.directory, sink.directory.parent, clock=lambda: 1.0e9)
    other.write(other.record("mark", "lifecycle", "other.start"))
    assert other.path is not None
    first = sink.path
    assert first is not None
    first.unlink()
    status, answer = read_log(
        parse_query({}), state=sink.directory.parent, directory=sink.directory
    )
    assert status == 200
    assert answer["writing"] == first.name
    assert answer["file"] == other.path.name
    sink.check_file()
    assert sink.path is not None and sink.path != first and sink.path.exists()
    event_log.mark("lifecycle", "after")
    assert [r["name"] for r in _records(sink)] == ["after"]
    other.close()


def test_a_job_cancelled_before_its_first_step_leaves_no_span_open(
    sink: event_log.EventLog,
) -> None:
    async def scenario() -> None:
        async def refresh() -> None:
            return None

        work = refresh()
        task = asyncio.create_task(event_log.job(work, "refresh"))
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task
        work.close()

    asyncio.run(scenario())
    assert event_log.open_spans() == []
    assert _named(sink, "refresh") == []


def test_closing_a_log_ends_its_spans_in_it_when_it_is_not_the_processs(
    tmp_path: Path,
) -> None:
    state, directory = _state(tmp_path)
    log = event_log.EventLog(directory, state)
    with event_log.installed(log):
        event_log.begin("job", "refresh", announce=True)
    log.close()
    assert [(r["event"], r.get("outcome")) for r in _named(log, "refresh")] == [
        ("start", None),
        ("end", "abandoned"),
    ]


def test_a_refresh_failure_is_the_jobs_even_when_its_stamp_is_not_written(
    sink: event_log.EventLog, tmp_path: Path
) -> None:
    stamp = PullRefreshStamp(
        outcome="network_error", message="gh did not answer within 15 s", at="2026-11-19T21:00:00Z"
    )
    with event_log.span("job", "files"):
        pull_list.write_files_refresh(
            tmp_path / "home", "github-com--octo--demo--46386669dc01", 7, stamp, persist=False
        )
    (record,) = _named(sink, "files")
    assert record["outcome"] == "failed"
    assert record["attrs"]["failure"] == "network_error"


@pytest.mark.parametrize("status", [None, 200])
def test_a_cancelled_request_is_cancelled_before_or_after_its_answer_began(
    sink: event_log.EventLog, status: int | None
) -> None:
    span = event_log.begin("request", "GET /slow")
    _end_request_span(
        span,
        status=status,
        body_bytes=0,
        start_ms=None,
        query="",
        record=Record(),
        failure=asyncio.CancelledError(),
    )
    (record,) = _named(sink, "GET /slow")
    assert record["outcome"] == "cancelled"
    assert "error" not in record["attrs"]


def test_open_log_is_owner_only_and_off_when_the_environment_says_so(tmp_path: Path) -> None:
    environ = {"METABROWSER_STATE_DIR": str(tmp_path / "state"), "METABROWSER_EVENT_LOG": "0"}
    assert event_log.open_log(served="/x", version="0", environ=environ) is None
    environ["METABROWSER_EVENT_LOG"] = "1"
    opened = event_log.open_log(served="/x", version="0", environ=environ)
    try:
        assert opened is not None and opened.path is not None
        assert stat.S_IMODE(opened.path.stat().st_mode) == 0o600
        assert stat.S_IMODE(opened.path.parent.stat().st_mode) == 0o700
        assert event_log.parse_file_name(opened.path.name) is not None
        first = json.loads(opened.path.read_text().splitlines()[0])
        assert (first["event"], first["name"]) == ("mark", "server.start")
        assert first["attrs"] == {"served": "/x", "version": "0"}
    finally:
        event_log.close_log()
    assert not event_log.enabled()


def test_a_stop_from_the_signal_handler_abandons_what_was_running(
    sink: event_log.EventLog,
) -> None:
    event_log.begin("job", "refresh", announce=True)
    sink.close_from_signal_handler()
    *_, abandoned, stop = _records(sink)
    assert (abandoned["name"], abandoned["outcome"]) == ("refresh", "abandoned")
    assert stop["name"] == "server.stop"


def test_a_blocked_event_loop_is_an_open_loop_span(sink: event_log.EventLog) -> None:
    async def scenario() -> None:
        sink.watch_loop(asyncio.get_running_loop())
        sink._ping_loop()
        ping = sink._ping
        assert ping is not None
        # The loop has not run the ping yet: as far as the watcher knows, it is blocked.
        sink.check_open(now=ping.started + 2.5)
        await asyncio.sleep(0.01)
        assert sink._ping is None

    asyncio.run(scenario())
    records = _named(sink, "event_loop.turn")
    # Its open record, and no end: a turn quicker than the threshold writes none.
    assert [r["event"] for r in records] == ["open"]
    assert records[0]["kind"] == "loop"


# ── the route ─────────────────────────────────────────────────


def test_the_query_refuses_what_it_cannot_apply() -> None:
    for params, message in [
        ({"kind": "job,nope"}, "kind must be among"),
        ({"limit": "0"}, "limit must be from 1"),
        ({"min_ms": "-1"}, "min_ms must be"),
        ({"file": "../x"}, "file must name"),
        ({"sort": "name"}, "sort must be"),
        ({"bogus": "1"}, "unknown parameter bogus"),
        # str.isdigit takes a superscript two, which int() refuses.
        ({"limit": "\u00b2"}, "limit must be a whole number"),
        ({"span": "9" * 5000}, "span must be a whole number"),
    ]:
        with pytest.raises(QueryError, match=message):
            parse_query(params)


def test_the_route_reads_the_writing_segment_with_filters_and_open_spans(
    sink: event_log.EventLog,
) -> None:
    with event_log.span("subprocess", "gh auth") as quick:
        quick.end("timeout")
    with event_log.span("request", "GET /quick"):
        pass
    stuck = event_log.begin("job", "stuck", announce=True)
    assert sink.path is not None
    status, answer = read_log(
        parse_query({"outcome": "timeout"}), state=sink.directory.parent, directory=sink.directory
    )
    assert status == 200
    assert answer["writing"] == answer["file"] == sink.path.name
    assert [e["name"] for e in answer["events"]] == ["gh auth"]
    assert (answer["scanned"], answer["matched"]) == (3, 1)
    assert [s["name"] for s in answer["open"]] == ["stuck"]
    status, answer = read_log(
        parse_query({"span": str(stuck.id)}), state=sink.directory.parent, directory=sink.directory
    )
    assert [e["event"] for e in answer["events"]] == ["start"]
    stuck.end()


def test_the_route_says_a_missing_log_is_absent(tmp_path: Path) -> None:
    status, answer = read_log(
        parse_query({}), state=tmp_path / "state", directory=tmp_path / "state" / "events"
    )
    assert status == 200
    assert (answer["state"], answer["files"], answer["file"], answer["events"]) == (
        "absent",
        [],
        None,
        [],
    )
    assert answer["writing"] is None


if sys.platform == "win32":  # pragma: no cover
    pytestmark = pytest.mark.skip(reason="owner-only storage is POSIX")
