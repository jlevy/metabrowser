"""The event log read as spans: nested, timed, and counted (``event_log_views``).

The fixture segment tells the stuck-page story of 2026-11-19 (a refresh that could not
connect, GitHub's 503, a comparison whose job and process never ended before the server was
killed mid-line); the rest build a log line by line to hold each rule: where a span starts,
what a filter keeps, how the distribution is cut, and what a hand-edited file may not do.
"""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

import pytest

from metabrowser import event_log, event_log_views
from metabrowser.event_log_views import ViewError

FIXTURE = (
    Path(__file__).parent
    / "fixtures"
    / "event-log-views"
    / "events-20261119T220000Z-p7007-000.jsonl"
)


def _stamp(second: float) -> str:
    whole = int(second)
    milli = round((second - whole) * 1000)
    return f"2026-11-19T22:{whole // 60:02d}:{whole % 60:02d}.{milli:03d}Z"


def _line(second: float, event: str, kind: str, name: str, **fields: Any) -> str:
    attrs = fields.pop("attrs", None)
    record: dict[str, Any] = {
        "v": 1,
        "ts": _stamp(second),
        "event": event,
        "kind": kind,
        "name": name,
    }
    record.update(fields)
    record.setdefault("pid", 1)
    if attrs is not None:
        record["attrs"] = attrs
    return json.dumps(record)


def _table(*lines: str) -> event_log_views.Table:
    return event_log_views.build_table(("\n".join(lines) + "\n").encode())


def _roots(table: event_log_views.Table, **params: str) -> dict[str, Any]:
    return event_log_views.timeline(
        table, event_log_views.parse_filter(params), parent=None, offset=0, limit=1000
    )


@pytest.fixture(scope="module")
def story() -> event_log_views.Table:
    return event_log_views.build_table(FIXTURE.read_bytes())


# ── Reading a segment ───────────────────────────────────────────────────────────────


def test_a_segment_is_read_as_spans_marks_and_reports(story: event_log_views.Table) -> None:
    log = event_log_views.log_summary(story)
    assert (log["records"], log["spans"], log["unfinished"]) == (58, 46, 2)
    # The torn last line, and the line of a later schema version, are counted and skipped.
    assert log["skipped"] == 2
    assert log["pids"] == [7007]
    assert story.offset_ms(story.items[-1]) > 199_000
    kinds = {item.type for item in story.items}
    assert kinds == {"span", "mark", "report"}


def test_a_span_starts_where_its_best_record_says(story: event_log_views.Table) -> None:
    # A job's start record is exact; the process under it has only open records, which
    # carry its age so far; a request has only its end record, and its duration.
    job = story.spans["7007:45"]
    assert job.start == pytest.approx(story.first + 199.91, abs=1e-3)
    process = story.spans["7007:46"]
    assert process.start == pytest.approx(story.first + 199.93, abs=1e-3)
    request = story.spans["7007:1"]
    assert (request.start - story.first) * 1000 == pytest.approx(899.2, abs=0.5)


def test_a_span_with_no_end_is_unfinished_and_aged_to_the_logs_last_record(
    story: event_log_views.Table,
) -> None:
    job = story.spans["7007:45"]
    assert job.unfinished and not job.ended
    assert job.opens == 3
    assert story.elapsed_ms(job) == pytest.approx((story.last - job.start) * 1000)
    assert story.elapsed_ms(story.spans["7007:44"]) == 30003.1


def test_a_report_made_while_a_wait_still_ran_is_not_a_time_to_rank(
    story: event_log_views.Table,
) -> None:
    waits = [i for i in story.items if i.name == "wait githubPull:diffSummary"]
    assert [(i.event, story.elapsed_ms(i)) for i in waits] == [("open", None), ("end", 32100.0)]


def test_lines_that_are_not_records_of_this_version_are_counted_not_read() -> None:
    table = event_log_views.build_table(
        b'{"v":2,"ts":"2026-11-19T22:00:00.000Z"}\nnot json\n\n'
        + _line(1, "mark", "lifecycle", "server.start").encode()
        + b'\n{"v":1,"ts":"2026-11'
    )
    assert (table.records, table.skipped) == (1, 3)


@pytest.mark.parametrize(
    ("claimed", "kept"),
    [
        (5.0, 5.0),
        (-3.0, 0.0),
        (1e18, event_log_views.MAX_DURATION_MS),
        (1e300, event_log_views.MAX_DURATION_MS),
        (float("inf"), None),
        (True, None),
        ("5", None),
    ],
)
def test_a_duration_a_file_claims_is_kept_within_what_a_calendar_can_hold(
    claimed: object, kept: float | None
) -> None:
    table = _table(_line(1, "end", "job", "x", span=1, dur_ms=claimed, outcome="ok"))
    assert table.spans["1:1"].dur_ms == kept
    log = event_log_views.log_summary(table)
    assert log["started"] and log["ended"], "a start the calendar can show"


@pytest.mark.parametrize(
    "stamp", ["0001-01-01T00:00:00Z", "1969-12-31T23:59:59Z", "9999-12-31T23:59:59Z", "nonsense"]
)
def test_a_time_outside_the_years_the_writer_could_have_stamped_is_no_time(stamp: str) -> None:
    table = event_log_views.build_table(
        json.dumps(
            {"v": 1, "ts": stamp, "event": "end", "kind": "job", "name": "x", "span": 1, "pid": 1}
        ).encode()
    )
    assert (table.records, table.skipped, table.items) == (0, 1, [])


def test_an_attribute_a_file_nests_past_the_bound_or_makes_not_finite_is_cut() -> None:
    nested: dict[str, Any] = {"deep": 1}
    for _ in range(event_log_views.MAX_ATTR_DEPTH + 3):
        nested = {"in": nested}
    table = _table(
        _line(
            1,
            "end",
            "job",
            "x",
            span=1,
            dur_ms=1.0,
            attrs={"nested": nested, "kept": [1, {"a": 2}]},
        )
    )
    attrs = table.spans["1:1"].attrs
    assert attrs["kept"] == [1, {"a": 2}]
    json.dumps(attrs, allow_nan=False)
    cut = attrs["nested"]
    for _ in range(event_log_views.MAX_ATTR_DEPTH - 2):
        cut = cut["in"]
    assert cut == {"in": None}


def test_a_record_with_no_usable_time_is_left_out() -> None:
    table = _table(
        '{"v":1,"event":"mark","kind":"lifecycle","name":"no time"}',
        '{"v":1,"ts":"yesterday","event":"mark","kind":"lifecycle","name":"bad time"}',
        _line(2, "mark", "lifecycle", "server.start"),
    )
    assert [i.name for i in table.items] == ["server.start"]


def test_an_empty_file_is_an_empty_table() -> None:
    table = event_log_views.build_table(b"")
    assert (table.records, table.items) == (0, [])
    assert event_log_views.log_summary(table)["started"] is None
    assert _roots(table)["rows"] == []


# ── Nesting ─────────────────────────────────────────────────────────────────────────


def test_a_job_nests_under_its_request_and_a_process_under_its_job(
    story: event_log_views.Table,
) -> None:
    answer = _roots(story)
    refresh = next(r for r in answer["rows"] if r["key"] == "7007:22")
    assert (refresh["children"], refresh["below"]) == (1, 3)
    job = event_log_views.timeline(
        story, event_log_views.parse_filter({}), parent="7007:22", offset=0, limit=10
    )["rows"]
    assert [(r["key"], r["children"]) for r in job] == [("7007:23", 2)]
    inner = event_log_views.timeline(
        story, event_log_views.parse_filter({}), parent="7007:23", offset=0, limit=10
    )["rows"]
    assert [(r["kind"], r["name"]) for r in inner] == [
        ("subprocess", "gh api"),
        ("probe", "probe api.github.com:443"),
    ]
    assert all(r["parent"] == "7007:23" for r in inner)


def test_roots_are_in_time_order_with_marks_and_reports_among_them(
    story: event_log_views.Table,
) -> None:
    rows = _roots(story)["rows"]
    starts = [r["start_ms"] for r in rows]
    assert starts == sorted(starts)
    assert rows[0]["type"] == "mark" and rows[0]["name"] == "server.start"
    assert {r["type"] for r in rows} == {"span", "mark", "report"}


def test_a_page_of_roots_says_whether_more_follow() -> None:
    table = _table(
        *[
            _line(i, "end", "request", f"GET /{i}", span=i, dur_ms=1.0, outcome="ok")
            for i in range(1, 8)
        ]
    )
    first = event_log_views.timeline(
        table, event_log_views.parse_filter({}), parent=None, offset=0, limit=3
    )
    assert (first["total"], len(first["rows"]), first["has_more"]) == (7, 3, True)
    last = event_log_views.timeline(
        table, event_log_views.parse_filter({}), parent=None, offset=6, limit=3
    )
    assert (len(last["rows"]), last["has_more"]) == (1, False)


def test_a_span_whose_parent_is_in_an_earlier_segment_is_a_root_marked_orphan() -> None:
    table = _table(
        _line(5, "end", "subprocess", "git fetch", span=9, parent=3, dur_ms=2.0, outcome="ok")
    )
    (row,) = _roots(table)["rows"]
    assert row["orphan"] is True and row["parent"] is None


def test_spans_nested_in_a_circle_are_all_shown() -> None:
    table = _table(
        _line(5, "end", "job", "a", span=1, parent=2, dur_ms=1.0, outcome="ok"),
        _line(6, "end", "job", "b", span=2, parent=1, dur_ms=1.0, outcome="ok"),
        _line(7, "end", "job", "self", span=3, parent=3, dur_ms=1.0, outcome="ok"),
    )
    reachable = {r["name"] for r in _roots(table)["rows"]}
    assert "self" in reachable
    below = [
        r["name"]
        for root in _roots(table)["rows"]
        for r in event_log_views.timeline(
            table, event_log_views.parse_filter({}), parent=root["key"], offset=0, limit=9
        )["rows"]
    ]
    assert sorted(reachable | set(below)) == ["a", "b", "self"]


def test_a_deep_chain_is_put_together_in_time_linear_in_its_length() -> None:
    """A segment holds at most about 8,000 spans, and one chain of them cost 14 s to read
    when each span's depth was walked to the root and each link checked for a circle by
    walking all the way up (review A of #633). Now each is settled once."""

    count = 8_000
    lines = [
        _line(1, "end", "job", f"s{n}", span=n, parent=n - 1 if n > 1 else None, dur_ms=1.0)
        for n in range(1, count + 1)
    ]
    started = time.perf_counter()
    table = _table(*lines)
    answer = _roots(table)
    took = time.perf_counter() - started
    assert took < 3.0, f"{count} spans nested in a chain took {took:.1f} s"
    assert table.depth["1:1"] == 0 and table.depth[f"1:{count}"] == count - 1
    (root,) = answer["rows"]
    assert (root["children"], root["below"]) == (1, count - 1)


def test_a_long_circle_is_cut_once_and_every_span_is_still_shown() -> None:
    count = 4_000
    lines = [
        _line(1, "end", "job", f"s{n}", span=n, parent=n % count + 1, dur_ms=1.0)
        for n in range(1, count + 1)
    ]
    table = _table(*lines)
    roots = [span for span in table.spans.values() if span.parent_key is None]
    assert len(roots) == 1, "one link closes the circle, and only one is cut"
    assert sorted(table.depth.values()) == list(range(count))


def test_two_processes_in_one_file_keep_their_span_numbers_apart() -> None:
    table = _table(
        _line(5, "end", "request", "one", span=1, pid=10, dur_ms=1.0, outcome="ok"),
        _line(6, "end", "job", "child of one", span=2, parent=1, pid=10, dur_ms=1.0, outcome="ok"),
        _line(7, "end", "request", "other", span=1, pid=20, dur_ms=1.0, outcome="ok"),
    )
    assert sorted(table.spans) == ["10:1", "10:2", "20:1"]
    assert table.spans["10:2"].parent_key == "10:1"
    assert table.spans["20:1"].parent_key is None


def test_a_span_that_is_not_in_the_log_is_not_found() -> None:
    table = _table(_line(1, "mark", "lifecycle", "server.start"))
    with pytest.raises(ViewError) as raised:
        event_log_views.timeline(
            table, event_log_views.parse_filter({}), parent="1:99", offset=0, limit=5
        )
    assert (raised.value.code, raised.value.status) == ("span_missing", 404)


# ── Filters ─────────────────────────────────────────────────────────────────────────


def test_a_filter_keeps_the_spans_that_match_and_those_above_them(
    story: event_log_views.Table,
) -> None:
    answer = _roots(story, outcome="timeout,failed")
    assert [(r["key"], r["matched"], r["children"]) for r in answer["rows"]] == [
        ("7007:22", False, 1),
        ("7007:38", False, 1),
    ]
    below = event_log_views.timeline(
        story,
        event_log_views.parse_filter({"outcome": "failed"}),
        parent="7007:23",
        offset=0,
        limit=9,
    )
    # The probe and the gh process both failed; nothing under the job is hidden here, but
    # under the second refresh the process that succeeded is.
    assert {r["name"] for r in below["rows"]} == {"gh api", "probe api.github.com:443"}
    second = event_log_views.timeline(
        story,
        event_log_views.parse_filter({"outcome": "failed"}),
        parent="7007:39",
        offset=0,
        limit=9,
    )
    assert [r["name"] for r in second["rows"]] == ["gh api"]


def test_a_minimum_time_counts_an_unfinished_spans_age(story: event_log_views.Table) -> None:
    answer = _roots(story, min_ms="29000", kind="job,subprocess")
    keys = {r["key"] for r in answer["rows"]}
    assert "7007:44" in keys  # the request that waited for the job that never ended
    inner = event_log_views.timeline(
        story,
        event_log_views.parse_filter({"min_ms": "29000"}),
        parent="7007:44",
        offset=0,
        limit=9,
    )
    assert [(r["key"], r["matched"]) for r in inner["rows"]] == [("7007:45", True)]


def test_a_filter_the_log_has_no_vocabulary_for_is_refused() -> None:
    for params in ({"kind": "bogus"}, {"outcome": "meh"}, {"min_ms": "-1"}, {"cause": "x"}):
        with pytest.raises(ViewError) as raised:
            event_log_views.parse_filter(params)
        assert raised.value.code == "invalid_query"


def test_a_limit_must_be_a_whole_number_in_bounds() -> None:
    assert event_log_views.parse_page({}, default_limit=7) == (0, 7)
    assert event_log_views.parse_page({"offset": "4", "limit": "9"}, default_limit=7) == (4, 9)
    for params in (
        {"limit": "0"},
        {"limit": "x"},
        {"limit": "²"},
        {"offset": "-1"},
        {"limit": str(event_log_views.MAX_LIMIT + 1)},
    ):
        with pytest.raises(ViewError):
            event_log_views.parse_page(params, default_limit=7)


# ── Slowest and the distribution ────────────────────────────────────────────────────


def test_the_slowest_come_first_with_the_spans_above_each(story: event_log_views.Table) -> None:
    answer = event_log_views.slowest(
        story, event_log_views.parse_filter({"kind": "subprocess"}), limit=3
    )
    assert [(r["key"], r["elapsed_ms"]) for r in answer["items"]] == [
        ("7007:24", 30006.4),
        ("7007:46", pytest.approx(29973.0, abs=0.5)),
        ("7007:42", 1810.2),
    ]
    assert answer["items"][1]["state"] == "unfinished"
    assert [s["name"] for s in answer["items"][1]["path"]] == [
        "GET /api/plugin/github/pull-comparison",
        "comparison_cache.manifest",
    ]


def test_every_timed_thing_falls_in_one_bucket_of_the_distribution(
    story: event_log_views.Table,
) -> None:
    answer = event_log_views.slowest(story, event_log_views.parse_filter({}), limit=1)
    assert sum(answer["histogram"]) == answer["timed"]
    assert len(answer["histogram"]) == len(answer["edges_ms"]) + 1
    assert event_log.OPEN_AFTER_MS in answer["edges_ms"]


@pytest.mark.parametrize(
    ("elapsed", "bucket"),
    [
        (0.5, 0),
        (1.0, 1),
        (9.99, 1),
        (10.0, 2),
        (499.0, 3),
        (500.0, 4),
        (1999.0, 4),
        (2000.0, 5),
        (9999.0, 5),
        (10000.0, 6),
    ],
)
def test_a_time_falls_in_the_bucket_between_its_edges(elapsed: float, bucket: int) -> None:
    assert event_log_views._bucket(elapsed) == bucket  # pyright: ignore[reportPrivateUsage]


# ── By kind ─────────────────────────────────────────────────────────────────────────


def test_percentiles_are_nearest_rank() -> None:
    ordered = [float(n) for n in range(1, 21)]
    percentile = event_log_views._percentile  # pyright: ignore[reportPrivateUsage]
    assert (percentile(ordered, 50), percentile(ordered, 95), percentile(ordered, 100)) == (
        10.0,
        19.0,
        20.0,
    )
    assert percentile([4.2], 95) == 4.2
    assert percentile([], 50) is None


def test_each_kind_is_counted_by_outcome_and_timed(story: event_log_views.Table) -> None:
    answer = event_log_views.by_kind(story, event_log_views.parse_filter({}))
    kinds = {k["kind"]: k for k in answer["kinds"]}
    assert [k["kind"] for k in answer["kinds"]] == [
        "request",
        "job",
        "subprocess",
        "browser",
        "lifecycle",
        "loop",
        "probe",
    ]
    assert kinds["request"]["outcomes"] == {"ok": 35, "cancelled": 1}
    assert kinds["job"]["outcomes"] == {"failed": 2, "unfinished": 1}
    assert kinds["request"]["max_ms"] == 30003.1
    names = {n["name"]: n for n in kinds["request"]["names"]}
    assert names["GET /api/file"]["count"] == 10
    assert names["GET /api/file"]["p50_ms"] == 5.2
    # An unfinished job counts as failed work, with the age it reached.
    assert {n["name"]: n["failed"] for n in kinds["job"]["names"]}["comparison_cache.manifest"] == 1
    assert sum(kinds["request"]["histogram"]) == kinds["request"]["timed"]


def test_a_kind_lists_its_names_by_time_and_says_how_many_it_left_out() -> None:
    lines = [
        _line(i, "end", "request", f"GET /r{i}", span=i, dur_ms=float(i), outcome="ok")
        for i in range(1, event_log_views.NAMES_SHOWN + 4)
    ]
    answer = event_log_views.by_kind(_table(*lines), event_log_views.parse_filter({}))
    (group,) = answer["kinds"]
    assert len(group["names"]) == event_log_views.NAMES_SHOWN
    assert group["names_more"] == 3
    assert group["names"][0]["name"] == f"GET /r{event_log_views.NAMES_SHOWN + 3}"


# ── Errors ──────────────────────────────────────────────────────────────────────────


def test_failures_are_grouped_by_cause_with_the_page_apart(story: event_log_views.Table) -> None:
    answer = event_log_views.errors(story, ())
    assert [(c["cause"], c["count"]) for c in answer["causes"]] == [
        ("connect_timeout", 3),
        ("server_error", 2),
    ]
    assert answer["failures"] == 5
    first = answer["causes"][0]
    assert first["addresses"] == ["20.172.24.160"]
    assert first["message"].startswith("GitHub could not be reached because the connection")
    assert {e["key"] for e in first["examples"]} == {"7007:23", "7007:24", "7007:25"}
    assert answer["probe"]["verdict"] == "connect_timeout"
    # A page's never_completed fetch is not counted among the causes.
    assert answer["page_reports"]["count"] == 1
    assert answer["page_reports"]["outcomes"] == {"never_completed": 1}


def test_an_example_is_opened_where_it_happened_when_two_processes_share_a_span_number() -> None:
    """Both processes failed a ``refresh`` numbered 2 under a request numbered 1; the
    examples open the span of their own process, not the first with that number."""

    table = _table(
        _line(1, "end", "request", "GET /a", span=1, pid=1, dur_ms=5.0, outcome="ok"),
        _line(
            2,
            "end",
            "job",
            "refresh",
            span=2,
            parent=1,
            pid=1,
            dur_ms=5.0,
            outcome="failed",
            attrs={"cause": "connect_timeout"},
        ),
        _line(61, "end", "request", "GET /b", span=1, pid=2, dur_ms=5.0, outcome="ok"),
        _line(
            62,
            "end",
            "job",
            "refresh",
            span=2,
            parent=1,
            pid=2,
            dur_ms=5.0,
            outcome="failed",
            attrs={"cause": "connect_timeout"},
        ),
    )
    (group,) = event_log_views.errors(table, ())["causes"]
    assert [(e["pid"], e["span"], e["key"]) for e in group["examples"]] == [
        (2, 2, "2:2"),
        (1, 2, "1:2"),
    ]
    assert [[step["name"] for step in e["path"]] for e in group["examples"]] == [
        ["GET /b"],
        ["GET /a"],
    ]


def test_a_failure_the_page_reported_is_opened_where_it_sits_among_the_roots() -> None:
    table = _table(
        _line(
            1,
            "end",
            "browser",
            "fetch /api/x",
            client="abcd1234-1",
            pid=3,
            dur_ms=4000.0,
            outcome="never_completed",
            attrs={"status": None, "path": "/api/x"},
        ),
    )
    (example,) = event_log_views.errors(table, ())["page_reports"]["examples"]
    assert example["client"] == "abcd1234-1" and example["pid"] == 3 and example["ts"]
    assert table.points[example["key"]].kind == "browser"
    answer = event_log_views.timeline(
        table,
        event_log_views.parse_filter({}),
        parent=None,
        offset=0,
        limit=9,
        focus=example["key"],
    )
    assert answer["focus"]["found"] is True
    assert answer["focus"]["steps"] == [{"parent": None, "key": example["key"], "index": 0}]


def test_work_with_no_end_is_listed_apart_longest_first(story: event_log_views.Table) -> None:
    answer = event_log_views.errors(story, ())
    assert answer["unfinished"]["total"] == 2
    assert [r["key"] for r in answer["unfinished"]["rows"]] == ["7007:45", "7007:46"]
    assert answer["not_failures"] == {"cancelled": 1}


def test_errors_take_the_kinds_the_failures_route_takes(story: event_log_views.Table) -> None:
    kinds = event_log_views.parse_kinds("job")
    answer = event_log_views.errors(story, kinds)
    assert answer["failures"] == 2
    assert [r["key"] for r in answer["unfinished"]["rows"]] == ["7007:45"]


def test_a_log_with_no_failure_says_so() -> None:
    answer = event_log_views.errors(
        _table(_line(1, "end", "request", "GET /", span=1, dur_ms=2.0, outcome="ok")), ()
    )
    assert (answer["failures"], answer["causes"], answer["unfinished"]["total"]) == (0, [], 0)


# ── Bounds ──────────────────────────────────────────────────────────────────────────


def test_a_view_reads_a_segment_as_the_log_writes_one() -> None:
    assert event_log_views.MAX_VIEW_BYTES == event_log.MAX_FILE_BYTES + event_log.MAX_LINE_BYTES


def test_the_table_cache_is_keyed_on_what_the_content_is() -> None:
    table = _table(_line(1, "mark", "lifecycle", "server.start"))
    event_log_views.remember("events.jsonl", "fingerprint-1", table)
    assert event_log_views.remembered("events.jsonl", "fingerprint-1") is table
    assert event_log_views.remembered("events.jsonl", "fingerprint-2") is None
    assert event_log_views.remembered("other.jsonl", "fingerprint-1") is None


def test_the_views_vocabulary_is_the_writers(story: event_log_views.Table) -> None:
    log = event_log_views.log_summary(story)
    assert log["kinds"] == list(event_log.KINDS)
    assert log["outcomes"] == list(event_log.OUTCOMES)
