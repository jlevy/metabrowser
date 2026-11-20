"""The agents catalog and its routes, over the synthetic homes.

Routes are called as the server calls them: a synchronous handler given a request. A
test that needs the catalog fully summarized passes ``sync=1`` and a fixed ``now``, as the
command line does; one that exercises the background worker calls the catalog directly.
"""

from __future__ import annotations

import dataclasses
import json
import os
import stat
import threading
import time
from collections.abc import Callable, Generator, Mapping
from pathlib import Path
from urllib.parse import urlencode

import pytest
from starlette.requests import Request
from starlette.responses import JSONResponse

from metabrowser import server
from metabrowser.builtin_plugins.agents import catalog, claude, codex, routes, store
from metabrowser.builtin_plugins.agents.model import (
    DriftCollector,
    DriftSummary,
    Home,
    SessionSummary,
)
from metabrowser.plugin_api import PluginCacheUnavailableError
from tests import agents_synthetic_home as syn

Handler = Callable[[Request], JSONResponse]
NOW = syn.NOW


def call(handler: Handler, **params: object) -> tuple[int, dict[str, object]]:
    query = urlencode({k: str(v) for k, v in params.items()})
    request = Request(
        {
            "type": "http",
            "method": "GET",
            "path": "/",
            "query_string": query.encode(),
            "headers": [],
        }
    )
    response = handler(request)
    return response.status_code, json.loads(bytes(response.body))


def ok(handler: Handler, **params: object) -> dict[str, object]:
    status, body = call(handler, sync=1, now=NOW, **params)
    assert status == 200, body
    return body


def rows(body: dict[str, object]) -> list[dict[str, object]]:
    value = body["sessions"]
    assert isinstance(value, list)
    return value  # pyright: ignore[reportUnknownVariableType]


def ids(body: dict[str, object]) -> list[str]:
    return [str(row["session_id"]) for row in rows(body)]


@pytest.fixture
def served(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Generator[syn.SyntheticHomes]:
    """Synthetic homes served as the root, with a private cache directory of its own."""

    cache = tmp_path / "cache-home"
    cache.mkdir(mode=0o700)
    monkeypatch.setenv("METABROWSER_CACHE_DIR", str(cache))
    root = tmp_path / "root"
    root.mkdir()
    homes = syn.build(root)
    server._set_root_dir(root)  # pyright: ignore[reportPrivateUsage]
    monkeypatch.setattr(catalog, "PROBE", lambda pid, _start: pid == syn.PID_LIVE)
    monkeypatch.setattr(catalog, "REFRESH_MIN_INTERVAL_SECONDS", 0.0)
    yield homes
    catalog.reset()


# -- the cache key ----------------------------------------------------------------------


def test_the_cache_key_changes_with_everything_a_summary_is_computed_from(
    served: syn.SyntheticHomes, monkeypatch: pytest.MonkeyPatch
) -> None:
    home = served.claude
    session = next(s for s in claude.discover(home) if s.session_id == syn.S1)
    key = store.session_key(session, home.path)
    assert key == store.session_key(session, home.path)
    transcript = Path(session.source_paths[0])

    with transcript.open("a", encoding="utf-8") as handle:
        handle.write('{"type":"system"}\n')
    grown = store.session_key(session, home.path)
    assert grown != key  # size changed

    info = transcript.stat()
    os.utime(transcript, ns=(info.st_atime_ns, info.st_mtime_ns + 1_000_000))
    touched = store.session_key(session, home.path)
    assert touched != grown  # modification time changed

    monkeypatch.setattr(claude, "FAMILY_VERSIONS", {"session": 2, "drift": 1})
    assert store.session_key(session, home.path) != touched  # a family version changed


def test_a_codex_key_follows_the_store_update_time_the_files_do_not_show(
    served: syn.SyntheticHomes,
) -> None:
    session = next(s for s in codex.discover(served.codex) if s.session_id == syn.T1)
    later = dataclasses.replace(session, last_activity=(session.last_activity or 0) + 1)
    assert store.session_key(session, served.codex.path) != store.session_key(
        later, served.codex.path
    )


def test_entries_are_owner_only_and_hold_no_absolute_path(served: syn.SyntheticHomes) -> None:
    ok(routes.catalog_handler)
    cache = Path(os.environ["METABROWSER_CACHE_DIR"]) / "plugins" / "agents"
    files = [p for p in cache.rglob("*") if p.is_file()]
    assert len(files) == 13
    for path in files:
        assert stat.S_IMODE(path.stat().st_mode) == 0o600
        assert str(served.root) not in path.read_text(encoding="utf-8")
    for directory in [p for p in cache.rglob("*") if p.is_dir()]:
        assert stat.S_IMODE(directory.stat().st_mode) == 0o700


def test_a_damaged_entry_is_a_miss_and_is_read_again(served: syn.SyntheticHomes) -> None:
    ok(routes.catalog_handler)
    catalog.reset()
    cache = Path(os.environ["METABROWSER_CACHE_DIR"]) / "plugins" / "agents"
    victim = sorted(p for p in cache.rglob("*.json"))[0]
    victim.write_text("{not json", encoding="utf-8")
    body = ok(routes.catalog_handler)
    progress = body["progress"]
    assert isinstance(progress, dict)
    assert (progress["from_cache"], progress["read"]) == (12, 1)  # pyright: ignore[reportUnknownMemberType]


# -- the worker ---------------------------------------------------------------------------


def test_a_second_process_loads_every_summary_from_the_cache(served: syn.SyntheticHomes) -> None:
    first = ok(routes.catalog_handler)["progress"]
    assert (first["from_cache"], first["read"]) == (0, 13)  # pyright: ignore[reportIndexIssue]
    catalog.reset()  # a new process: no memory, the same cache directory
    second = ok(routes.catalog_handler)["progress"]
    assert (second["from_cache"], second["read"]) == (13, 0)  # pyright: ignore[reportIndexIssue]


def test_an_append_rereads_only_the_session_that_grew(
    served: syn.SyntheticHomes, monkeypatch: pytest.MonkeyPatch
) -> None:
    before = ok(routes.session_handler, agent="claude", id=syn.S1)
    session = before["session"]
    assert isinstance(session, dict)
    records = session["records"]  # pyright: ignore[reportUnknownVariableType]

    read: list[str] = []
    real = claude.summarize

    def counting(home: Home, summary: object) -> object:
        read.append(getattr(summary, "session_id"))  # noqa: B009
        return real(home, summary)  # pyright: ignore[reportArgumentType]

    monkeypatch.setattr(claude, "summarize", counting)
    transcript = next(served.claude.path.glob(f"projects/*/{syn.S1}.jsonl"))
    with transcript.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps({"type": "system", "subtype": "info", "timestamp": syn.iso(NOW)}))
        handle.write("\n")
    after = ok(routes.session_handler, agent="claude", id=syn.S1)
    assert read == [syn.S1]
    appended = after["session"]
    assert isinstance(appended, dict)
    assert appended["records"] == records + 1  # pyright: ignore[reportOperatorIssue]


def test_requests_during_a_pass_share_it(
    served: syn.SyntheticHomes, monkeypatch: pytest.MonkeyPatch
) -> None:
    release = threading.Event()
    calls: list[int] = []
    real = claude.discover

    def slow(home: Home) -> list[object]:
        calls.append(1)
        release.wait(10)
        return real(home)  # pyright: ignore[reportReturnType]

    monkeypatch.setattr(claude, "discover", slow)
    monkeypatch.setattr(catalog, "REFRESH_MIN_INTERVAL_SECONDS", 0.0)
    home = catalog.catalog_for(served.claude)
    threads = [threading.Thread(target=lambda: home.refresh(0.0)) for _ in range(8)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
    snapshot = home.snapshot()
    assert snapshot.state == "scanning"
    assert snapshot.total == 0  # a request does not wait for the pass
    release.set()
    assert home.complete(timeout=30)
    assert len(calls) == 1 + 1  # the shared pass, and the pass `complete` asked for
    assert home.snapshot().total == 5


def test_a_request_never_waits_for_a_pass(
    served: syn.SyntheticHomes, monkeypatch: pytest.MonkeyPatch
) -> None:
    release = threading.Event()
    real = claude.discover
    monkeypatch.setattr(claude, "discover", lambda h: (release.wait(10), real(h))[1])
    monkeypatch.setattr(catalog, "FIRST_PASS_WAIT_SECONDS", 0.05)
    started = time.monotonic()
    status, body = call(routes.catalog_handler, folder=".claude")
    assert status == 200
    assert time.monotonic() - started < 5
    progress = body["progress"]
    assert isinstance(progress, dict)
    assert progress["state"] == "scanning"
    assert progress["total"] == 0
    release.set()
    catalog.catalog_for(served.claude).complete(timeout=30)


def test_a_root_change_drops_every_catalog_and_stops_its_worker(
    served: syn.SyntheticHomes, tmp_path: Path
) -> None:
    ok(routes.catalog_handler)
    old = catalog.catalog_for(served.claude)
    assert old.snapshot().total == 5
    elsewhere = tmp_path / "elsewhere"
    elsewhere.mkdir()
    server._set_root_dir(elsewhere)  # pyright: ignore[reportPrivateUsage]
    assert catalog.catalog_for(served.claude) is not old
    assert not old.complete(timeout=1)  # cancelled: it refuses new passes
    status, body = call(routes.catalog_handler)
    assert (status, body["code"]) == (404, "no_agent_homes")


def test_a_pass_stops_at_its_byte_budget_and_the_next_continues(
    served: syn.SyntheticHomes, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(catalog, "SUMMARY_PASS_BUDGET_BYTES", 1)
    home = catalog.catalog_for(served.claude)
    home.refresh(0.0)
    deadline = time.monotonic() + 30
    while time.monotonic() < deadline and home.snapshot().state != "idle":
        time.sleep(0.01)
    partial = home.snapshot()
    assert partial.pending_budget
    assert 0 < partial.summarized < partial.total
    assert home.complete(timeout=30)  # passes follow until nothing is pending
    assert home.snapshot().summarized == 5


def test_an_unavailable_cache_directory_still_answers_uncached(
    served: syn.SyntheticHomes, monkeypatch: pytest.MonkeyPatch
) -> None:
    def refuse(_name: str) -> Path:
        raise PluginCacheUnavailableError("not private")

    monkeypatch.setattr(store, "plugin_cache_directory", refuse)
    body = ok(routes.catalog_handler)
    assert body["cache"] == {"state": "unavailable", "write_errors": 0}
    totals = body["totals"]
    assert isinstance(totals, dict)
    assert totals["sessions"] == 13  # pyright: ignore[reportUnknownMemberType]
    assert totals["summarized"] == 13  # pyright: ignore[reportUnknownMemberType]
    assert not (Path(os.environ["METABROWSER_CACHE_DIR"]) / "plugins").exists()


def test_a_cache_that_cannot_be_written_degrades_to_uncached(
    served: syn.SyntheticHomes, monkeypatch: pytest.MonkeyPatch
) -> None:
    def refuse(*_args: object) -> int:
        raise PermissionError("read-only")

    monkeypatch.setattr(os, "replace", refuse)
    body = ok(routes.catalog_handler)
    assert body["cache"] == {"state": "ok", "write_errors": 13}
    progress = body["progress"]
    assert isinstance(progress, dict)
    assert progress["summarized"] == 13  # pyright: ignore[reportUnknownMemberType]


# -- catalog ------------------------------------------------------------------------------


def test_catalog_reports_homes_totals_histogram_and_days(served: syn.SyntheticHomes) -> None:
    body = ok(routes.catalog_handler)
    assert list(body) == [
        "folder",
        "now",
        "homes",
        "totals",
        "size_histogram",
        "per_day",
        "progress",
        "freshness",
        "cache",
        "drift",
        "engines",
    ]
    homes = body["homes"]
    assert isinstance(homes, list)
    assert [(h["path"], h["agent"], h["sessions"]) for h in homes] == [  # pyright: ignore[reportUnknownVariableType]
        (".claude", "claude", 5),
        (".codex", "codex", 8),
    ]
    totals = body["totals"]
    assert isinstance(totals, dict)
    assert totals["by_agent"] == {"claude": 5, "codex": 8}  # pyright: ignore[reportUnknownMemberType]
    assert totals["running"] == 3  # pyright: ignore[reportUnknownMemberType]
    histogram = body["size_histogram"]
    assert isinstance(histogram, dict)
    buckets = histogram["buckets"]  # pyright: ignore[reportUnknownVariableType]
    assert sum(b["count"] for b in buckets) == 13  # pyright: ignore[reportUnknownVariableType]
    assert buckets[0] == {"lower": 0, "upper": 1024, "count": 11}  # pyright: ignore[reportUnknownVariableType]
    assert buckets[-1]["upper"] is None  # pyright: ignore[reportUnknownVariableType]
    assert body["engines"] == {"session": "builtin", "drift": "builtin"}
    freshness = body["freshness"]
    assert isinstance(freshness, dict)
    assert freshness["passes"] == 2  # pyright: ignore[reportUnknownMemberType]
    # Passes stamp with the clock, never with the request's `now`.
    assert freshness["fast_pass_at"] != NOW  # pyright: ignore[reportUnknownMemberType]


def test_catalog_of_one_home_folder(served: syn.SyntheticHomes) -> None:
    body = ok(routes.catalog_handler, folder=".codex")
    homes = body["homes"]
    assert isinstance(homes, list)
    assert [h["agent"] for h in homes] == ["codex"]  # pyright: ignore[reportUnknownVariableType]


def test_catalog_refuses_a_folder_without_a_home_or_outside_the_root(
    served: syn.SyntheticHomes,
) -> None:
    (served.root / "plain").mkdir()
    assert call(routes.catalog_handler, folder="plain")[1]["code"] == "no_agent_homes"
    assert call(routes.catalog_handler, folder="plain")[0] == 404
    assert call(routes.catalog_handler, folder="nope")[1]["code"] == "not_found"
    assert call(routes.catalog_handler, folder="../outside")[0] == 404


# -- sessions -----------------------------------------------------------------------------


def test_sessions_default_order_is_newest_first_across_homes(served: syn.SyntheticHomes) -> None:
    body = ok(routes.sessions_handler)
    assert body["total"] == body["available"] == 13
    times = [row["last_activity"] for row in rows(body)]
    assert times == sorted(times, reverse=True)  # pyright: ignore[reportArgumentType]


def test_sessions_filters(served: syn.SyntheticHomes) -> None:
    claude_only = ok(routes.sessions_handler, agent="claude")
    assert {r["agent"] for r in rows(claude_only)} == {"claude"}
    assert claude_only["total"] == 5

    subagents = ok(routes.sessions_handler, origin="subagent")
    assert {r["origin"] for r in rows(subagents)} == {"subagent"}
    both = ok(routes.sessions_handler, origin="review,scheduled")
    assert {r["origin"] for r in rows(both)} == {"review", "scheduled"}

    running = ok(routes.sessions_handler, status="running")
    assert set(ids(running)) == {syn.S1, syn.T5, syn.T6}
    assert {r["status"] for r in rows(running)} == {"running"}
    assert running["total"] == 3  # S1 by pid file; T5 recent, T6 by an active turn

    alpha = ok(routes.sessions_handler, project="/work/alpha")
    assert all(r["project"] == "/work/alpha" for r in rows(alpha))
    assert alpha["total"] >= 1  # pyright: ignore[reportOperatorIssue]

    modelled = ok(routes.sessions_handler, model="claude-test-1")
    assert syn.S1 in ids(modelled)


def test_sessions_time_range_uses_start_then_last_activity(served: syn.SyntheticHomes) -> None:
    everything = ok(routes.sessions_handler)
    starts = sorted(float(str(r["started_at"] or r["last_activity"])) for r in rows(everything))
    middle = starts[len(starts) // 2]
    later = ok(routes.sessions_handler, since=middle)
    earlier = ok(routes.sessions_handler, until=middle)
    assert later["total"] + earlier["total"] == 13  # pyright: ignore[reportOperatorIssue]
    iso = ok(routes.sessions_handler, since="2027-01-01T00:00:00Z")
    assert iso["total"] == 13


def test_sessions_sort_and_order_put_missing_values_last(served: syn.SyntheticHomes) -> None:
    by_size = ok(routes.sessions_handler, sort="size")
    sizes = [r["size_bytes"] for r in rows(by_size)]
    assert sizes == sorted(sizes, reverse=True)  # pyright: ignore[reportArgumentType]
    smallest = ok(routes.sessions_handler, sort="size", order="asc")
    assert [r["size_bytes"] for r in rows(smallest)] == sorted(sizes)  # pyright: ignore[reportArgumentType]
    by_turns = ok(routes.sessions_handler, sort="turns", order="asc")
    turns = [r["turns"] for r in rows(by_turns)]
    known = [t for t in turns if t is not None]
    assert turns[: len(known)] == known  # None sorts last in either direction
    assert known == sorted(known)  # pyright: ignore[reportArgumentType]
    titles = [
        str(r["title"]) for r in rows(ok(routes.sessions_handler, sort="title")) if r["title"]
    ]
    present = titles
    assert present == sorted(present, key=str.casefold)  # text columns ascend by default


def test_sessions_pages_are_bounded_and_complete(served: syn.SyntheticHomes) -> None:
    first = ok(routes.sessions_handler, limit=5)
    second = ok(routes.sessions_handler, limit=5, offset=first["next_offset"])
    third = ok(routes.sessions_handler, limit=5, offset=second["next_offset"])
    assert (len(rows(first)), len(rows(second)), len(rows(third))) == (5, 5, 3)
    assert third["next_offset"] is None
    assert ids(first) + ids(second) + ids(third) == ids(ok(routes.sessions_handler))
    assert first["limit"] == 5


def test_sessions_facets_count_the_whole_folder_not_the_page(served: syn.SyntheticHomes) -> None:
    body = ok(routes.sessions_handler, agent="claude", limit=1)
    facets = body["facets"]
    assert isinstance(facets, dict)
    assert facets["agent"] == {"claude": 5, "codex": 8}  # pyright: ignore[reportUnknownMemberType]
    assert list(body) == [
        "folder",
        "now",
        "filters",
        "sort",
        "order",
        "offset",
        "limit",
        "next_offset",
        "total",
        "available",
        "totals",
        "facets",
        "progress",
        "freshness",
        "cache",
        "sessions",
    ]


@pytest.mark.parametrize(
    ("params", "param"),
    [
        ({"agent": "gemini"}, "agent"),
        ({"origin": "robot"}, "origin"),
        ({"status": "asleep"}, "status"),
        ({"sort": "mood"}, "sort"),
        ({"order": "sideways"}, "order"),
        ({"limit": "0"}, "limit"),
        ({"limit": str(routes.PAGE_MAX + 1)}, "limit"),
        ({"limit": "many"}, "limit"),
        ({"offset": "-1"}, "offset"),
        ({"since": "yesterday"}, "since"),
        ({"project": "x" * (routes.MAX_PARAM_CHARS + 1)}, "project"),
    ],
)
def test_sessions_refuses_a_bad_parameter_with_a_typed_error(
    served: syn.SyntheticHomes, params: Mapping[str, str], param: str
) -> None:
    status, body = call(routes.sessions_handler, sync=1, now=NOW, **params)
    assert status == 400
    assert list(body) == ["error", "code", "param"]
    assert (body["code"], body["param"]) == ("bad_param", param)


# -- session ------------------------------------------------------------------------------


def test_session_by_id_carries_children_parent_and_drift(served: syn.SyntheticHomes) -> None:
    body = ok(routes.session_handler, agent="claude", id=syn.S1)
    session = body["session"]
    assert isinstance(session, dict)
    assert session["session_id"] == syn.S1
    assert session["status"] == "running"
    assert session["summarized"] is True
    assert session["source_paths"] == [f".claude/projects/-work-alpha/{syn.S1}.jsonl"]
    children = body["children"]
    assert isinstance(children, list)
    assert [c["session_id"] for c in children] == [syn.AGENT_A]  # pyright: ignore[reportUnknownVariableType]
    assert body["children_total"] == 1
    assert body["parent"] is None
    drift = body["drift"]
    assert isinstance(drift, dict)
    assert drift["clean"] is False  # pyright: ignore[reportUnknownMemberType]
    assert body["provider_sections"] == []

    child = ok(routes.session_handler, agent="claude", id=syn.AGENT_A)
    parent = child["parent"]
    assert isinstance(parent, dict)
    assert parent["session_id"] == syn.S1  # pyright: ignore[reportUnknownMemberType]


def test_session_by_source_path(served: syn.SyntheticHomes) -> None:
    by_path = ok(routes.session_handler, path=f".claude/projects/-work-alpha/{syn.S1}.jsonl")
    by_id = ok(routes.session_handler, agent="claude", id=syn.S1)
    assert by_path["session"] == by_id["session"]
    rollout = ok(routes.session_handler, path=next(iter(_codex_rollouts(served))))
    session = rollout["session"]
    assert isinstance(session, dict)
    assert session["agent"] == "codex"


def _codex_rollouts(served: syn.SyntheticHomes) -> list[str]:
    return [
        p.relative_to(served.root).as_posix()
        for p in sorted(served.codex.path.glob("sessions/**/*.jsonl"))
    ]


def test_session_refusals(served: syn.SyntheticHomes) -> None:
    assert call(routes.session_handler, agent="claude", id="nope", sync=1, now=NOW)[1]["code"] == (
        "session_not_found"
    )
    assert call(routes.session_handler)[1]["param"] == "id"
    assert call(routes.session_handler, path="missing.jsonl")[1]["code"] == "not_found"
    (served.root / "stray.jsonl").write_text("{}\n", encoding="utf-8")
    assert call(routes.session_handler, path="stray.jsonl")[1]["code"] == "no_agent_homes"
    status, body = call(routes.session_handler, agent="claude", id="nope", sync=1, now=NOW)
    assert status == 404
    assert list(body) == ["error", "code", "param"]


# -- records ------------------------------------------------------------------------------


def _events(body: dict[str, object]) -> list[dict[str, object]]:
    events = body["events"]
    assert isinstance(events, list)
    return events  # pyright: ignore[reportUnknownVariableType]


def test_records_stream_the_whole_session_in_cursor_pages(served: syn.SyntheticHomes) -> None:
    everything = ok(routes.records_handler, agent="claude", id=syn.S1)
    assert everything["next_cursor"] is None
    expected = [e.to_json() for e in claude.stream(served.claude, syn.S1)]
    assert _events(everything) == expected
    assert sum(not e.replay for e in claude.stream(served.claude, syn.S1)) == 21

    collected: list[dict[str, object]] = []
    cursor = 0
    pages = 0
    while True:
        page = ok(routes.records_handler, agent="claude", id=syn.S1, limit=4, cursor=cursor)
        collected.extend(_events(page))
        pages += 1
        next_cursor = page["next_cursor"]
        if next_cursor is None:
            break
        assert isinstance(next_cursor, int)
        cursor = next_cursor
    assert collected == expected
    assert pages > 1


def test_records_filter_by_kind_tool_and_locator(served: syn.SyntheticHomes) -> None:
    prompts = ok(routes.records_handler, agent="claude", id=syn.S1, kind="prompt")
    assert {e["kind"] for e in _events(prompts)} == {"prompt"}
    assert prompts["examined"] == len(list(claude.stream(served.claude, syn.S1)))

    streamed = list(claude.stream(served.claude, syn.S1))
    tool = next(e.tool_name for e in streamed if e.tool_name)
    by_tool = ok(routes.records_handler, agent="claude", id=syn.S1, tool=tool)
    assert _events(by_tool) and all(e["tool_name"] == tool for e in _events(by_tool))

    wanted = streamed[5]
    one = ok(routes.records_handler, agent="claude", id=syn.S1, locator=wanted.locator)
    assert [e["locator"] for e in _events(one)] == [wanted.locator]


def test_records_scan_is_bounded_and_resumable(
    served: syn.SyntheticHomes, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(routes, "RECORDS_SCAN_MAX", 5)
    page = ok(routes.records_handler, agent="claude", id=syn.S1, kind="error")
    assert page["examined"] == 5
    assert page["next_cursor"] == 5


def test_records_of_a_codex_thread_come_from_its_history(served: syn.SyntheticHomes) -> None:
    body = ok(routes.records_handler, agent="codex", id=syn.T1)
    assert [e["locator"] for e in _events(body)] == [
        e.locator for e in codex.stream(served.codex, syn.T1)
    ]


def test_records_bad_parameters(served: syn.SyntheticHomes) -> None:
    for params, param in (
        ({"kind": "colour"}, "kind"),
        ({"limit": routes.RECORDS_MAX + 1}, "limit"),
        ({"cursor": -3}, "cursor"),
    ):
        status, body = call(routes.records_handler, agent="claude", id=syn.S1, **params)
        assert (status, body["param"]) == (400, param)


# -- live ---------------------------------------------------------------------------------


def test_live_lists_what_a_probe_or_a_recent_update_vouches_for(served: syn.SyntheticHomes) -> None:
    body = ok(routes.live_handler)
    assert list(body) == ["folder", "now", "total", "sessions"]
    live = rows(body)
    assert {(r["agent"], r["session_id"]) for r in live} == {
        ("claude", syn.S1),
        ("codex", syn.T5),
        ("codex", syn.T6),
    }
    claude_row = next(r for r in live if r["agent"] == "claude")
    assert claude_row["source"] == "pid-file"
    assert claude_row["title"] == "Synthetic session"  # joined from the catalog
    updated = [r["updated_at"] for r in live]
    assert updated == sorted(updated, reverse=True)  # pyright: ignore[reportArgumentType]


# -- what a response may contain ---------------------------------------------------------


def test_no_response_carries_an_absolute_path_a_secret_or_the_environment(
    served: syn.SyntheticHomes, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("SYNTHETIC_API_TOKEN", "sk-test-0123456789abcdef0123456789abcdef")
    responses = [
        ok(routes.catalog_handler),
        ok(routes.sessions_handler, limit=PAGE),
        ok(routes.live_handler),
        ok(routes.session_handler, agent="claude", id=syn.S1),
        ok(routes.session_handler, agent="codex", id=syn.T1),
        ok(routes.records_handler, agent="claude", id=syn.S1),
        ok(routes.records_handler, agent="codex", id=syn.T8),
        call(routes.sessions_handler, folder="nope")[1],
    ]
    forbidden = [str(served.root), str(served.root.resolve()), os.path.expanduser("~"), "sk-test-"]
    for body in responses:
        text = json.dumps(body)
        for needle in forbidden:
            assert needle not in text, needle


PAGE = routes.PAGE_MAX


def test_a_home_shown_with_the_users_home_collapses_to_a_tilde(
    served: syn.SyntheticHomes, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("HOME", "/work")
    body = ok(routes.sessions_handler, agent="claude")
    assert {r["project"] for r in rows(body)} >= {"~/alpha"}


# -- bounds ------------------------------------------------------------------------------


def test_a_long_title_is_cut_to_one_redacted_line() -> None:
    from metabrowser.builtin_plugins.agents.model import SessionSummary

    secret = "authorization: Bearer abcdefghijklmnop"
    session = SessionSummary(agent="codex", session_id="x", title=f"{secret}\n" + "word " * 100_000)
    title = catalog._bounded(session).title  # pyright: ignore[reportPrivateUsage]
    assert title is not None
    assert "abcdefghijklmnop" not in title
    assert "\n" not in title
    assert len(title) <= catalog.TITLE_MAX_CHARS
    short = SessionSummary(agent="codex", session_id="y", title="short title")
    assert catalog._bounded(short) is short  # pyright: ignore[reportPrivateUsage]


def test_the_codex_title_cut_happens_in_sql(served: syn.SyntheticHomes) -> None:
    assert "substr(title, 1, " in codex._select_list(["id", "title"])  # pyright: ignore[reportPrivateUsage]
    assert "substr(id" not in codex._select_list(["id", "title"])  # pyright: ignore[reportPrivateUsage]


def test_a_request_does_not_start_a_pass_inside_the_duty_interval(
    served: syn.SyntheticHomes, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(catalog, "REFRESH_MIN_INTERVAL_SECONDS", 3600.0)
    home = catalog.catalog_for(served.claude)
    home.refresh(5.0)
    deadline = time.monotonic() + 30
    while home.snapshot().state != "idle" and time.monotonic() < deadline:
        time.sleep(0.01)
    assert home.snapshot().passes == 1
    home.refresh(0.0)  # inside the interval: no second pass
    time.sleep(0.2)
    assert home.snapshot().passes == 1
    assert home.complete(timeout=30)  # a synchronous request always runs one
    assert home.snapshot().passes == 2


# -- review findings -----------------------------------------------------------------------


def test_a_second_sync_request_answers_at_once_while_one_waits(
    served: syn.SyntheticHomes, monkeypatch: pytest.MonkeyPatch
) -> None:
    release = threading.Event()
    real = claude.discover
    monkeypatch.setattr(claude, "discover", lambda h: (release.wait(30), real(h))[1])
    first: list[tuple[int, dict[str, object]]] = []
    waiter = threading.Thread(
        target=lambda: first.append(call(routes.catalog_handler, folder=".claude", sync=1))
    )
    waiter.start()
    deadline = time.monotonic() + 10
    while time.monotonic() < deadline:
        if catalog.SYNC_SLOT.acquire(blocking=False):
            catalog.SYNC_SLOT.release()  # the waiter has not taken the slot yet
            time.sleep(0.01)
        else:
            break
    started = time.monotonic()
    status, body = call(routes.catalog_handler, folder=".claude", sync=1)
    assert status == 200
    assert time.monotonic() - started < 5
    progress = body["progress"]
    assert isinstance(progress, dict)
    assert progress["complete"] is False
    release.set()
    waiter.join(30)
    assert first[0][0] == 200


def test_sync_never_stores_the_requests_now(served: syn.SyntheticHomes) -> None:
    call(routes.catalog_handler, sync=1, now=123)
    for home in (served.claude, served.codex):
        fast_at = catalog.catalog_for(home).snapshot().fast_at
        assert fast_at is not None
        assert fast_at > 1_000_000_000
    assert not hasattr(catalog.HomeCatalog, "_now_override")


def test_sync_waits_share_one_deadline(
    served: syn.SyntheticHomes, monkeypatch: pytest.MonkeyPatch
) -> None:
    waits: list[float] = []
    real = catalog.HomeCatalog.complete

    def recording(self: catalog.HomeCatalog, timeout: float = 0.0) -> bool:
        waits.append(timeout)
        return real(self, timeout)

    monkeypatch.setattr(catalog.HomeCatalog, "complete", recording)
    ok(routes.catalog_handler)
    assert len(waits) == 2
    assert waits[1] <= waits[0] <= catalog.SYNC_TIMEOUT_SECONDS


def test_the_live_cache_is_timed_on_the_monotonic_clock(served: syn.SyntheticHomes) -> None:
    home = catalog.catalog_for(served.codex)
    first = home.live(NOW)
    assert home.live(NOW + 10_000) is first  # a different `now` neither defeats the reuse
    home._live = (time.monotonic() - 10, first)  # pyright: ignore[reportPrivateUsage]
    assert home.live(NOW) is not first  # an old entry is refreshed whatever `now` says


def test_records_never_rescan_the_home(
    served: syn.SyntheticHomes, monkeypatch: pytest.MonkeyPatch
) -> None:
    ok(routes.catalog_handler)

    def fail(_home: Home, _session_id: str) -> list[object]:
        raise AssertionError("records rescanned the home")

    monkeypatch.setattr(claude, "_find", fail)
    body = ok(routes.records_handler, agent="claude", id=syn.S1)
    assert _events(body)
    by_path = ok(routes.records_handler, path=f".claude/projects/-work-alpha/{syn.S1}.jsonl")
    assert _events(by_path) == _events(body)
    assert _events(ok(routes.records_handler, agent="claude", id=syn.AGENT_A))


def test_records_count_skipped_events_toward_one_scan_bound(
    served: syn.SyntheticHomes, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(routes, "RECORDS_SCAN_MAX", 8)
    first = ok(routes.records_handler, agent="claude", id=syn.S1, limit=100)
    assert first["examined"] == 8
    assert first["next_cursor"] == 8
    second = ok(routes.records_handler, agent="claude", id=syn.S1, limit=100, cursor=5)
    assert second["examined"] == 8  # the five skipped count: at most 8 in all
    assert len(_events(second)) == 3
    status, body = call(routes.records_handler, agent="claude", id=syn.S1, cursor=9, sync=1)
    assert (status, body["param"]) == (400, "cursor")


def test_a_path_request_streams_the_file_it_named_when_ids_collide(
    served: syn.SyntheticHomes,
) -> None:
    ok(routes.catalog_handler)
    twin = served.claude.path / "projects" / "-work-beta" / f"{syn.S1}.jsonl"
    twin.parent.mkdir(parents=True, exist_ok=True)
    twin.write_text(
        json.dumps({"type": "system", "subtype": "info", "timestamp": syn.iso(NOW)}) + "\n",
        encoding="utf-8",
    )
    body = ok(routes.records_handler, path=f".claude/projects/-work-beta/{syn.S1}.jsonl")
    assert len(_events(body)) == 1
    original = ok(routes.records_handler, path=f".claude/projects/-work-alpha/{syn.S1}.jsonl")
    assert len(_events(original)) > 1


def test_live_text_from_a_pid_file_is_clipped_and_redacted(served: syn.SyntheticHomes) -> None:
    pid_file = served.claude.path / "sessions" / f"{syn.PID_LIVE}.json"
    data = json.loads(pid_file.read_text(encoding="utf-8"))
    data["name"] = "token=abcdefghijklmnop " + "n" * 5000
    data["cwd"] = "/work/" + "d" * 5000
    pid_file.write_text(json.dumps(data), encoding="utf-8")
    body = ok(routes.live_handler)
    row = next(r for r in rows(body) if r["agent"] == "claude")
    for field in ("name", "project"):
        assert len(str(row[field])) <= routes.LIVE_TEXT_MAX_CHARS
    assert "abcdefghijklmnop" not in str(row["name"])


def test_pid_files_read_are_capped(
    served: syn.SyntheticHomes, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(claude, "MAX_PID_FILES", 1)
    reads: list[int] = []

    def probe(pid: int, _start: str | None) -> bool:
        reads.append(pid)
        return False

    claude.live(served.claude, NOW, probe)
    assert len(reads) <= 1


def test_saves_of_one_key_use_unique_temporary_names(served: syn.SyntheticHomes) -> None:
    session = next(s for s in claude.discover(served.claude) if s.session_id == syn.S1)
    summary, drift = claude.summarize(served.claude, session)
    directory = served.root / "store"
    directory.mkdir()
    first = store.SummaryStore(directory, served.claude.path)
    second = store.SummaryStore(directory, served.claude.path)
    key = "a" * 32
    names: list[str] = []
    real_open = os.open

    def recording(path: str, flags: int, mode: int = 0o777) -> int:
        names.append(str(path))
        return real_open(path, flags, mode)

    with pytest.MonkeyPatch.context() as patch:
        patch.setattr(os, "open", recording)
        assert first.save(key, summary, drift)
        assert second.save(key, summary, drift)
    temporaries = [n for n in names if ".tmp-" in n]
    assert len(set(temporaries)) == 2
    assert first.load(key) is not None
    assert [p.name for p in directory.iterdir()] == [f"{key}.json"]


def test_a_failed_save_removes_only_its_own_temporary_file(served: syn.SyntheticHomes) -> None:
    session = next(s for s in claude.discover(served.claude) if s.session_id == syn.S1)
    summary, drift = claude.summarize(served.claude, session)
    directory = served.root / "store"
    directory.mkdir()
    bystander = directory / f"{'b' * 32}.json.tmp-other"
    bystander.write_text("in progress", encoding="utf-8")
    mine = store.SummaryStore(directory, served.claude.path)

    def refuse(*_args: object) -> None:
        raise PermissionError("no")

    with pytest.MonkeyPatch.context() as patch:
        patch.setattr(os, "replace", refuse)
        assert not mine.save("b" * 32, summary, drift)
    assert bystander.exists()
    assert [p.name for p in directory.iterdir()] == [bystander.name]


def test_an_empty_scan_after_a_full_one_does_not_prune_the_cache(
    served: syn.SyntheticHomes, monkeypatch: pytest.MonkeyPatch
) -> None:
    ok(routes.catalog_handler, folder=".claude")
    cache = Path(os.environ["METABROWSER_CACHE_DIR"]) / "plugins" / "agents"
    before = sorted(p.name for p in cache.rglob("*.json") if p.parent.name.startswith("claude"))
    assert len(before) == 5
    monkeypatch.setattr(claude, "discover", lambda _h: [])
    home = catalog.catalog_for(served.claude)
    assert home.complete(timeout=30)
    assert home.snapshot().total == 0
    after = sorted(p.name for p in cache.rglob("*.json") if p.parent.name.startswith("claude"))
    assert after == before


def test_a_scan_that_reported_read_errors_does_not_prune(
    served: syn.SyntheticHomes, monkeypatch: pytest.MonkeyPatch
) -> None:
    ok(routes.catalog_handler, folder=".codex")
    cache = Path(os.environ["METABROWSER_CACHE_DIR"]) / "plugins" / "agents"
    before = sorted(p.name for p in cache.rglob("*.json") if p.parent.name.startswith("codex"))
    real = codex.discover

    def partial(home: Home, limit: int, drift: DriftCollector) -> list[SessionSummary]:
        found = real(home, limit, drift)
        drift.read_error("state.threads")
        return found[:2]

    monkeypatch.setattr(codex, "discover", partial)
    assert catalog.catalog_for(served.codex).complete(timeout=30)
    after = sorted(p.name for p in cache.rglob("*.json") if p.parent.name.startswith("codex"))
    assert after == before


def test_a_cancelled_worker_does_not_prune(
    served: syn.SyntheticHomes, monkeypatch: pytest.MonkeyPatch
) -> None:
    ok(routes.catalog_handler, folder=".claude")
    pruned: list[int] = []

    def record(self: store.SummaryStore, keep: object) -> int:
        pruned.append(1)
        return 0

    monkeypatch.setattr(store.SummaryStore, "prune", record)
    home = catalog.catalog_for(served.claude)
    home.cancel()
    home._summarize(NOW)  # pyright: ignore[reportPrivateUsage]
    assert pruned == []


def test_a_stale_generation_registers_nothing(served: syn.SyntheticHomes, tmp_path: Path) -> None:
    generation = catalog.generation()
    other = tmp_path / "other"
    other.mkdir()
    server._set_root_dir(other)  # pyright: ignore[reportPrivateUsage]
    assert catalog.generation() == generation + 1
    stale = catalog.catalog_for(served.claude, generation)
    assert not stale.complete(timeout=1)  # cancelled
    assert catalog.catalog_for(served.claude, catalog.generation()) is not stale
    assert catalog._registry[("claude", str(served.claude.path))] is not stale  # pyright: ignore[reportPrivateUsage]


def test_a_failed_read_waits_for_its_key_to_change_or_several_passes(
    served: syn.SyntheticHomes, monkeypatch: pytest.MonkeyPatch
) -> None:
    real = claude.summarize
    attempts: list[str] = []

    def flaky(home: Home, summary: SessionSummary) -> tuple[SessionSummary, DriftSummary]:
        attempts.append(summary.session_id)
        if summary.session_id == syn.S2:
            raise OSError("locked")
        return real(home, summary)

    monkeypatch.setattr(claude, "summarize", flaky)
    home = catalog.catalog_for(served.claude)
    for _ in range(3):
        assert home.complete(timeout=30)
    assert attempts.count(syn.S2) == 1  # not retried while its key held
    assert home.snapshot().failed == 1
