"""The page's reporter (static/event-reports.js) against the server that takes its reports.

tests/dom/event-reports-session.js runs the production reporter without a browser. These
tests hold it to the server: its settings are the ones the shell serves, every body it
sends is one ``POST /api/event-log/client`` accepts whole, and its Details, read from the
answers the routes give for a refresh job that never ends while the page waits on it,
say that the job is still running and that the page's wait never completed. The owner
asked for exactly that to be captured and surfaced, 2026-11-19 (mb-9zp5).
"""

from __future__ import annotations

import json
import subprocess
from collections.abc import Generator
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import pytest

from metabrowser import event_log, home, server
from metabrowser.event_log_reports import RateLimit, accept, browser_settings
from metabrowser.event_log_route import parse_query, read_log, summarize_failures
from tests.required_tools import require_node

ROOT = Path(__file__).resolve().parents[1]
SESSION = ROOT / "tests" / "dom" / "event-reports-session.js"
PAGE = "k3v9q2zx"


def _node(*args: str) -> Any:
    require_node()
    result = subprocess.run(
        ["node", str(SESSION), *args],
        capture_output=True,
        text=True,
        timeout=60,
        check=False,
        cwd=ROOT,
    )
    assert result.returncode == 0, result.stderr
    return json.loads(result.stdout)


@pytest.fixture
def sink(tmp_path: Path) -> Generator[event_log.EventLog]:
    state = tmp_path / "state"
    home.ensure_storage_root(state)
    home.ensure_private_directory(state, event_log.EVENTS_DIRECTORY)
    log = event_log.EventLog(state / event_log.EVENTS_DIRECTORY, state)
    with event_log.installed(log):
        yield log
    log.close()


def test_the_sessions_settings_are_the_ones_the_shell_serves(sink: event_log.EventLog) -> None:
    told = _node()
    assert told["settings"] == browser_settings(long_lived=server.LONG_LIVED_PATHS)


def test_every_body_the_page_sends_is_accepted_whole(
    tmp_path: Path, sink: event_log.EventLog
) -> None:
    bodies_file = tmp_path / "bodies.json"
    _node("--bodies", str(bodies_file))
    bodies = json.loads(bodies_file.read_text(encoding="utf-8"))
    assert len(bodies) >= 10
    limit = RateLimit(limit=10**6)
    for body in bodies:
        status, answer = accept(json.dumps(body).encode(), limit=limit)
        assert status == 200, answer
        assert answer["refused"] == [], body
        assert answer["accepted"] == len(body["reports"])
    names = {record["name"] for record in _browser_records(sink)}
    # Each kind of report the page makes reached the log.
    assert {
        "fetch GET /api/plugin/github/pull-files-summary",
        "fetch /api/plugin/github/pull",
        "wait githubPull:diffSummary",
        "render blocked",
    } <= names


def _browser_records(log: event_log.EventLog) -> list[dict[str, Any]]:
    assert log.path is not None
    records = [json.loads(line) for line in log.path.read_text(encoding="utf-8").splitlines()]
    return [record for record in records if record["kind"] == "browser"]


def test_a_refresh_job_that_never_ends_is_in_the_details_with_the_wait_it_left_unfinished(
    tmp_path: Path, sink: event_log.EventLog
) -> None:
    # The page's third request starts the pull request's refresh, which never ends, and a
    # gh call under it that times out connecting.
    request = event_log.begin("request", "POST /api/plugin/github/pull-refresh", client=f"{PAGE}-3")
    with event_log.within(request):
        stuck = event_log.begin("job", "checkout._pull_job", announce=True)
        gh = event_log.begin(
            "subprocess",
            "gh api",
            attrs={"cause": "connect_timeout", "address": "20.172.24.160"},
        )
        gh.end("timeout")
    request.end()
    # The page reports its Diff summary's wait at the late threshold, and then that it never
    # completed: the reader left after a minute.
    for event, duration, outcome in (("open", 10000.0, None), ("end", 61234.5, "never_completed")):
        report: dict[str, Any] = {
            "type": "wait",
            "event": event,
            "name": "githubPull:diffSummary",
            "client": PAGE,
            "dur_ms": duration,
            "attrs": {"threshold_ms": 10000, "detail": {"number": 7}},
        }
        if outcome is not None:
            report["outcome"] = outcome
        body = {"page": PAGE, "path": "/pull/7", "reports": [report]}
        status, answer = accept(json.dumps(body).encode(), limit=RateLimit())
        assert (status, answer["accepted"]) == (200, 1)
    state, directory = sink.directory.parent, sink.directory
    status, page = read_log(
        parse_query({"client": PAGE, "limit": "200"}), state=state, directory=directory
    )
    assert status == 200
    failures = summarize_failures(
        state=state,
        directory=directory,
        since=datetime.now(UTC) - timedelta(hours=1),
        until=None,
        kinds=(),
    )
    answers = tmp_path / "answers.json"
    answers.write_text(json.dumps({"failures": failures, "page": page, "client": PAGE}))
    lines = {part["heading"]: part["items"] for part in _node("--describe", str(answers))}
    stuck.end()
    # The job is still running, and is this page's: it is listed first.
    assert lines["Still running"][0].startswith("checkout._pull_job · for ")
    assert lines["connect timeout: 1 in the window"][:1] == ["Addresses: 20.172.24.160"]
    assert any(
        item.startswith("gh api · timeout") for item in lines["connect timeout: 1 in the window"]
    )
    # The page's wait is a failure in the window, and the page's own unfinished work.
    assert "never completed: 1 in the window" in lines
    mine = lines["This page’s slow or unfinished work"]
    assert mine[0].startswith("wait githubPull:diffSummary · never_completed · 61.2 s")
    assert any(item.startswith("gh api · timeout · connect timeout") for item in mine)
