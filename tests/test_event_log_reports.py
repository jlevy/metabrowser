"""What a page reports to the event log, and the client ID that joins it to the server's.

The owner asked, 2026-11-19, that a Diff summary that does not load "after many
seconds" be captured, surfaced, and easy to debug. The server's side is
tests/test_event_log.py; these hold the page's side to the same standard: a report is
checked field by field and bounded before it is written, the route is only the
application's own pages', and the page's ID on each request ties its reports to the
requests and jobs the server ran for it.
"""

from __future__ import annotations

import json
import re
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

from metabrowser import event_log, home, server
from metabrowser.event_log_reports import (
    MAX_BODY_BYTES,
    MAX_REPORTS,
    REPORT_ROUTE,
    SLOW_MS,
    WAIT_LATE_MS,
    RateLimit,
    ReportError,
    accept,
    browser_settings,
    parse_body,
    parse_report,
)
from metabrowser.event_log_route import parse_query, read_log
from metabrowser.mirror_refresh import RefreshCoordinator
from metabrowser.server import _SlowRequestLogMiddleware

PAGE = "k3v9q2zx"

# The largest report of each shape static/event-reports.js sends, with names as long as
# the application's real ones: a slow fetch that failed, with its status and
# Server-Timing; a wait with the pull request it waits for; a freeze with the script the
# browser blamed. MAX_BODY_BYTES's comment cites the size of the largest.
_SLOW_FETCH: dict[str, Any] = {
    "type": "fetch",
    "event": "end",
    "name": "GET /api/github/pull-files-summary",
    "client": f"{PAGE}-1234",
    "dur_ms": 12345.6,
    "outcome": "failed",
    "attrs": {"status": 504, "threshold_ms": 2000, "server_ms": 12301.2, "error": "TypeError"},
}
_LATE_WAIT: dict[str, Any] = {
    "type": "wait",
    "event": "end",
    "name": "githubPull:summary",
    "client": PAGE,
    "dur_ms": 61234.5,
    "outcome": "never_completed",
    "attrs": {"threshold_ms": 10000, "detail": {"number": 12345}},
}
_FREEZE: dict[str, Any] = {
    "type": "render",
    "event": "end",
    "name": "blocked",
    "client": PAGE,
    "dur_ms": 1234.5,
    "outcome": "ok",
    "attrs": {
        "threshold_ms": 500,
        "detail": {
            "at_ms": 123456,
            "blocking_ms": 1184,
            "function": "paintSummaryWait",
            "source": "/static/plugins/github/pull-page.js",
            "invoker": "TimerHandler:setTimeout",
        },
    },
}


def _body(*reports: dict[str, Any], **fields: Any) -> bytes:
    return json.dumps(
        {"page": PAGE, "path": "/pull/7", "reports": list(reports), **fields}
    ).encode()


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


# ── reports become records ────────────────────────────────────


def test_each_report_becomes_a_browser_record_with_its_client_and_the_pages_path(
    sink: event_log.EventLog,
) -> None:
    status, answer = accept(_body(_SLOW_FETCH, _LATE_WAIT, _FREEZE), limit=RateLimit())
    assert status == 200
    assert (answer["accepted"], answer["refused"], answer["rate_limited"]) == (3, [], 0)
    assert answer["logged"] is True
    fetch, wait, freeze = _records(sink)
    assert fetch["kind"] == wait["kind"] == freeze["kind"] == "browser"
    assert fetch["event"] == "end"
    assert fetch["name"] == "fetch GET /api/github/pull-files-summary"
    assert fetch["client"] == f"{PAGE}-1234"
    assert fetch["dur_ms"] == 12345.6
    assert fetch["outcome"] == "failed"
    assert fetch["attrs"] == {
        "status": 504,
        "server_ms": 12301.2,
        "threshold_ms": 2000.0,
        "error": "TypeError",
        "path": "/pull/7",
    }
    assert "span" not in fetch
    assert wait["name"] == "wait githubPull:summary"
    assert wait["client"] == PAGE
    assert wait["outcome"] == "never_completed"
    assert wait["attrs"]["detail"] == {"number": 12345}
    assert freeze["attrs"]["detail"]["function"] == "paintSummaryWait"
    # What the route answers is what it wrote.
    assert [r["name"] for r in answer["records"]] == [fetch["name"], wait["name"], freeze["name"]]


def test_an_open_report_is_a_wait_still_running_and_has_no_outcome(
    sink: event_log.EventLog,
) -> None:
    still = {**_LATE_WAIT, "event": "open", "dur_ms": 10000.0}
    del still["outcome"]
    status, answer = accept(_body(still), limit=RateLimit())
    assert (status, answer["accepted"]) == (200, 1)
    (record,) = _records(sink)
    assert record["event"] == "open"
    assert "outcome" not in record


def test_without_a_log_the_route_answers_what_it_would_have_written() -> None:
    assert not event_log.enabled()
    status, answer = accept(_body(_SLOW_FETCH), limit=RateLimit())
    assert status == 200
    assert answer["logged"] is False
    assert answer["accepted"] == 1
    assert answer["records"][0]["client"] == f"{PAGE}-1234"


def test_text_from_the_page_is_redacted_like_the_servers(sink: event_log.EventLog) -> None:
    leaky = {**_SLOW_FETCH, "attrs": {"status": 401, "error": "denied token=hunter2hunter2"}}
    accept(_body(leaky), limit=RateLimit())
    (record,) = _records(sink)
    assert "hunter2" not in json.dumps(record)
    assert record["attrs"]["error"] == "denied token=[redacted]"


# ── what is refused ───────────────────────────────────────────


@pytest.mark.parametrize(
    ("change", "message"),
    [
        ({"type": "click"}, "type must be one of fetch, render, wait"),
        ({"event": "start"}, "event must be one of open, end"),
        ({"name": ""}, "name must be text"),
        ({"name": "x" * 201}, "name is longer than 200"),
        ({"client": "other123-1"}, "client must be the page's ID"),
        ({"client": f"{PAGE}x-1"}, "client must be the page's ID"),
        ({"client": f"{PAGE}-1 2"}, "client must be the page's ID"),
        ({"dur_ms": -1}, "dur_ms must be from 0"),
        ({"dur_ms": True}, "dur_ms must be a number"),
        ({"dur_ms": "12"}, "dur_ms must be a number"),
        ({"dur_ms": 1e12}, "dur_ms must be from 0"),
        ({"outcome": "timeout"}, "an end's outcome must be one of"),
        ({"event": "open"}, "an open report has no outcome"),
        ({"span": 3}, "span is not a field a report has"),
        ({"attrs": []}, "attrs must be an object"),
        ({"attrs": {"cause": "dns"}}, "attrs.cause is not a field a report has"),
        ({"attrs": {"status": 1000}}, "attrs.status must be an HTTP status"),
        ({"attrs": {"status": "200"}}, "attrs.status must be an HTTP status"),
        ({"attrs": {"server_ms": float("inf")}}, "attrs.server_ms must be from 0"),
        ({"attrs": {"hidden": "yes"}}, "attrs.hidden must be true or false"),
        ({"attrs": {"detail": {"Number": 1}}}, "names must be lowercase words"),
        ({"attrs": {"detail": {"nested": {"a": 1}}}}, "attrs.detail.nested must be text"),
        (
            {"attrs": {"detail": {f"k{i}": i for i in range(9)}}},
            "attrs.detail has more than 8 entries",
        ),
    ],
)
def test_a_report_is_refused_alone_and_says_which_field_and_why(
    change: dict[str, Any], message: str
) -> None:
    bad = {**_SLOW_FETCH, **change}
    with pytest.raises(ReportError, match=message):
        parse_report(bad, page=PAGE)
    status, answer = accept(_body(_LATE_WAIT, bad), limit=RateLimit())
    assert status == 200
    assert answer["accepted"] == 1
    assert [r["index"] for r in answer["refused"]] == [1]
    assert message in answer["refused"][0]["error"]


@pytest.mark.parametrize(
    ("body", "message"),
    [
        (b"not json", "the body must be JSON"),
        (b"\xff\xfe", "the body must be JSON"),
        (b"[]", "the body must be an object"),
        (_body(extra=1), "extra is not a field of a report's body"),
        (json.dumps({"page": f"{PAGE}-1", "reports": []}).encode(), "page must be the page's ID"),
        (json.dumps({"page": "", "reports": []}).encode(), "page must be the page's ID"),
        (json.dumps({"page": PAGE, "path": "pull/7", "reports": []}).encode(), "path must be"),
        (json.dumps({"page": PAGE, "reports": {}}).encode(), "reports must be a list"),
        (_body(*[_LATE_WAIT] * (MAX_REPORTS + 1)), f"at most {MAX_REPORTS} reports"),
        (_body(dropped=-1), "dropped must be a count"),
        (_body(dropped=True), "dropped must be a count"),
    ],
)
def test_a_malformed_body_is_refused_whole_and_writes_nothing(
    sink: event_log.EventLog, body: bytes, message: str
) -> None:
    with pytest.raises(ReportError, match=message):
        parse_body(body)
    status, answer = accept(body, limit=RateLimit())
    assert status == 400
    assert answer["code"] == "invalid_report"
    assert message in answer["error"]
    assert sink.path is None or _records(sink) == []


def test_the_largest_report_the_page_sends_leaves_a_full_batch_well_within_the_body_bound() -> None:
    sizes = {
        name: len(json.dumps(report, separators=(",", ":")).encode())
        for name, report in [("fetch", _SLOW_FETCH), ("wait", _LATE_WAIT), ("render", _FREEZE)]
    }
    largest = max(sizes.values())
    # MAX_BODY_BYTES's comment: the largest is about 300 bytes, so a full batch is about
    # 6 KB, under half the bound.
    assert 250 <= largest <= 350, sizes
    assert MAX_REPORTS * largest < MAX_BODY_BYTES / 2


# ── bounds on volume ──────────────────────────────────────────


def test_the_rate_limit_grants_up_to_its_bound_and_refuses_the_rest_until_the_window_ends() -> None:
    limit = RateLimit(limit=5, window_s=60.0)
    assert limit.take(3, now=0.0) == (3, False)
    assert limit.take(3, now=1.0) == (2, True)
    assert limit.take(2, now=2.0) == (0, False)
    assert limit.take(4, now=60.0) == (4, False)


def test_reports_past_the_rate_limit_are_counted_and_marked_once_a_window(
    sink: event_log.EventLog,
) -> None:
    limit = RateLimit(limit=2, window_s=3600.0)
    _, first = accept(_body(_LATE_WAIT, _LATE_WAIT, _LATE_WAIT), limit=limit)
    _, second = accept(_body(_LATE_WAIT), limit=limit)
    assert (first["accepted"], first["rate_limited"]) == (2, 1)
    assert (second["accepted"], second["rate_limited"]) == (0, 1)
    records = _records(sink)
    marks = [r for r in records if r["name"] == "browser.reports_rate_limited"]
    assert len(marks) == 1
    assert marks[0]["event"] == "mark"
    assert marks[0]["attrs"] == {"limit": 2, "window_s": 3600.0}
    assert len([r for r in records if r["name"] == "wait githubPull:summary"]) == 2


def test_reports_the_page_dropped_itself_are_marked_with_its_id(
    sink: event_log.EventLog,
) -> None:
    status, answer = accept(_body(dropped=7), limit=RateLimit())
    assert (status, answer["dropped_by_page"]) == (200, 7)
    (mark,) = _records(sink)
    assert mark["name"] == "browser.reports_dropped"
    assert mark["attrs"] == {"client": PAGE, "dropped": 7}


# ── the route on the application ──────────────────────────────


@pytest.fixture
def app_client(tmp_path: Path) -> Generator[TestClient]:
    (tmp_path / "doc.md").write_text("# Doc\n", encoding="utf-8")
    server._set_root_dir(tmp_path)
    with TestClient(server.app) as client:
        yield client


def test_the_route_takes_a_json_post_from_the_page_and_answers_what_it_wrote(
    app_client: TestClient, sink: event_log.EventLog
) -> None:
    response = app_client.post(
        REPORT_ROUTE, content=_body(_LATE_WAIT), headers={"content-type": "application/json"}
    )
    assert response.status_code == 200
    assert response.json()["accepted"] == 1
    assert [r["name"] for r in _records(sink) if r["kind"] == "browser"] == [
        "wait githubPull:summary"
    ]


@pytest.mark.parametrize(
    ("headers", "status_code"),
    [
        # A sandboxed document (/raw) has an opaque origin.
        ({"origin": "null"}, 403),
        ({"origin": "https://attacker.example", "sec-fetch-site": "cross-site"}, 403),
        # sendBeacon's text/plain, and a form's types, are never the page's report.
        ({"content-type": "text/plain"}, 415),
        ({"content-type": "application/x-www-form-urlencoded"}, 415),
    ],
)
def test_the_route_is_refused_to_other_origins_and_bodies_that_are_not_json(
    app_client: TestClient,
    sink: event_log.EventLog,
    headers: dict[str, str],
    status_code: int,
) -> None:
    response = app_client.post(
        REPORT_ROUTE,
        content=_body(_LATE_WAIT),
        headers={"content-type": "application/json", **headers},
    )
    assert response.status_code == status_code
    assert [r for r in _records(sink) if r["kind"] == "browser"] == []


def test_the_route_refuses_a_get_and_a_body_past_its_bound(
    app_client: TestClient, sink: event_log.EventLog
) -> None:
    assert app_client.get(REPORT_ROUTE).status_code == 405
    oversized = _body(_LATE_WAIT, path="/" + "x" * MAX_BODY_BYTES)
    declared = app_client.post(
        REPORT_ROUTE, content=oversized, headers={"content-type": "application/json"}
    )
    assert declared.status_code == 413
    assert declared.json()["code"] == "report_too_large"

    def chunks() -> Generator[bytes]:
        # No Content-Length: the bound is the bytes read, not what was declared.
        yield oversized[: MAX_BODY_BYTES // 2]
        yield oversized[MAX_BODY_BYTES // 2 :]

    streamed = app_client.post(
        REPORT_ROUTE, content=chunks(), headers={"content-type": "application/json"}
    )
    assert streamed.status_code == 413
    assert [r for r in _records(sink) if r["kind"] == "browser"] == []


def test_the_page_reads_its_thresholds_and_route_from_its_settings(
    app_client: TestClient,
) -> None:
    settings = browser_settings(long_lived=("/api/events",))
    assert settings["route"] == REPORT_ROUTE
    assert settings["header"] == event_log.CLIENT_HEADER == "x-metabrowser-client"
    assert (settings["slow_ms"], settings["late_ms"]) == (SLOW_MS, WAIT_LATE_MS)
    assert settings["slow_ms"] == event_log.OPEN_AFTER_MS
    assert settings["long_lived"] == ["/api/events"]
    assert settings["log"] is False
    shell = app_client.get("/").text
    match = re.search(r"window\.METABROWSER_SETTINGS=(\{.*?\});</script>", shell)
    assert match is not None
    served = json.loads(match.group(1))["EVENT_REPORTS"]
    assert served == browser_settings(long_lived=server.LONG_LIVED_PATHS)


# ── the client ID joins the page's records to the server's ────


def test_a_requests_client_id_is_on_its_record_and_on_the_job_it_started(
    sink: event_log.EventLog,
) -> None:
    async def started(_request: Request) -> Response:
        coordinator = RefreshCoordinator()

        async def _summary_job() -> None:
            return None

        coordinator.start("octo/demo:pull/7/files", _summary_job, network=False)
        await coordinator.drain(timeout_s=5)
        return JSONResponse({"refresh": "started"}, status_code=202)

    app = Starlette(
        routes=[Route("/api/start", started)],
        middleware=[Middleware(_SlowRequestLogMiddleware, threshold_ms=0, verbose=False)],
    )
    client = TestClient(app)
    assert client.get("/api/start", headers={"x-metabrowser-client": f"{PAGE}-3"}).is_success
    assert client.get("/api/start", headers={"x-metabrowser-client": "not an id"}).is_success
    records = _records(sink)
    tagged, untagged = [r for r in records if r["name"] == "GET /api/start"]
    assert tagged["client"] == f"{PAGE}-3"
    assert "client" not in untagged
    job_starts = [
        r for r in records if r["name"].endswith("_summary_job") and r["event"] == "start"
    ]
    assert [r.get("client") for r in job_starts] == [f"{PAGE}-3", None]


def test_a_pages_id_finds_its_requests_and_reports_and_no_other_pages(
    sink: event_log.EventLog,
) -> None:
    for client in (PAGE, f"{PAGE}-1", f"{PAGE}-22", f"{PAGE}x-1", "other123-1"):
        event_log.begin("request", f"GET /api/{client}", client=client).end()
    accept(_body(_LATE_WAIT), limit=RateLimit())
    state = sink.directory.parent
    status, answer = read_log(parse_query({"client": PAGE}), state=state, directory=sink.directory)
    assert status == 200
    assert sorted(e["name"] for e in answer["events"]) == [
        f"GET /api/{PAGE}",
        f"GET /api/{PAGE}-1",
        f"GET /api/{PAGE}-22",
        "wait githubPull:summary",
    ]
    status, answer = read_log(
        parse_query({"client": f"{PAGE}-1"}), state=state, directory=sink.directory
    )
    assert [e["name"] for e in answer["events"]] == [f"GET /api/{PAGE}-1"]


def test_an_open_span_names_the_client_that_started_it(sink: event_log.EventLog) -> None:
    stuck = event_log.begin("job", "stuck", client=f"{PAGE}-4", announce=True)
    _, answer = read_log(parse_query({}), state=sink.directory.parent, directory=sink.directory)
    (still,) = [s for s in answer["open"] if s["name"] == "stuck"]
    assert still["client"] == f"{PAGE}-4"
    stuck.end()
