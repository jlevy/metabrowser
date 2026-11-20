"""The event log views' session runs production browser code on what the routes answer.

``tests/dom/event-log-view-session.js`` drives the plugin's views (``event-log-views.js``)
and their state (``event-log-model.js``) through a scripted page: the timeline's first
page and the next, a row opening to the spans it started, a filter rebuilding the
timeline, the three other views, a refusal, and a view replaced or disposed while an
answer was on its way. ``tests/golden/cli-ui-event-log-view.tryscript.md`` pins its
transcript. So that the conversation is the server's and not envelopes a test wrote by
hand, the session plays the answers in the four
``tests/fixtures/event-log-view-*-responses.json`` recordings: what the in-process
application answered for each request the page makes, and for a file it does not have,
over the segment ``cli-api-event-log-views.tryscript.md`` pins. The first test here
records them again and fails when a recording drifts; ``make golden-update`` rewrites the
recordings and then the transcript.

The session asks for a page of 20 roots where the server's own is 200, so that the log has
a second page to read: the first page is the server's answer to ``limit=20``, and the
test below holds each page of it to the server's answer for the same window.
"""

from __future__ import annotations

import shutil
from pathlib import Path
from typing import Any
from urllib.parse import urlencode

import pytest
from starlette.testclient import TestClient

from metabrowser import server
from metabrowser.source import reset_source_session
from tests.golden_harness import check_recording, read_recording, run_session

RECORDINGS = {
    "timeline": "event-log-view-timeline-responses.json",
    "latency": "event-log-view-latency-responses.json",
    "summary": "event-log-view-summary-responses.json",
    "reveal": "event-log-view-reveal-responses.json",
}
TRANSCRIPT = "cli-ui-event-log-view.tryscript.md"
LOG = "events-20261119T220000Z-p7007-000.jsonl"
FIXTURE = Path(__file__).parent / "fixtures" / "event-log-views" / LOG
HOOK = "/api/plugin/event-log"

# Every request the session makes, as the page spells it: a route and its parameters,
# in the recording that holds its answer. The page asks for a first page with no limit;
# the session answers it with the server's page of 20 (``FIRST_PAGE``), so the second,
# which the page asks for with the limit the first answered with, is a page the server has.
# Four recordings, because the answers are long and each stays within the fixtures'
# review budget (``devtools/check_goldens.py``). ``reveal`` holds what Show in timeline asks:
# where a row is (``focus``, a page of one), the roots through a row's place (the page of 23
# that reaches the 43rd after the first 20), and the roots newest first.
REQUESTS: dict[str, list[tuple[str, dict[str, str]]]] = {
    "timeline": [
        ("timeline", {"limit": "20"}),
        ("timeline", {"offset": "20", "limit": "20"}),
        ("timeline", {"offset": "40", "limit": "20"}),
        ("timeline", {"parent": "7007:22"}),
        ("timeline", {"parent": "7007:23"}),
        ("timeline", {"kind": "job"}),
        ("timeline", {"kind": "job", "parent": "7007:22"}),
        ("timeline", {"kind": "job", "outcome": "failed"}),
    ],
    "latency": [("slowest", {}), ("slowest", {"kind": "subprocess"})],
    "reveal": [
        ("timeline", {"focus": "7007:46", "limit": "1"}),
        ("timeline", {"offset": "20", "limit": "23"}),
        ("timeline", {"parent": "7007:44"}),
        ("timeline", {"parent": "7007:45"}),
        ("timeline", {"focus": "7007:25", "limit": "1"}),
        ("timeline", {"order": "newest", "limit": "20"}),
    ],
    "summary": [
        ("kinds", {}),
        ("kinds", {"outcome": "failed"}),
        ("errors", {}),
        ("errors", {"path": "absent.jsonl"}),
    ],
}
FIRST_PAGE = {"limit": "20"}


def _key(route: str, params: dict[str, str]) -> str:
    return f"{route}?{urlencode(sorted({'path': LOG, **params}.items()))}"


def _serve(tmp_path: Path) -> TestClient:
    root = tmp_path / "root"
    root.mkdir()
    shutil.copy(FIXTURE, root / LOG)
    reset_source_session()
    server._set_root_dir(root)  # pyright: ignore[reportPrivateUsage]
    return TestClient(server.app)


def _ask(client: TestClient, route: str, params: dict[str, str]) -> dict[str, Any]:
    response = client.get(f"{HOOK}/{route}", params={"path": LOG, **params})
    return {"status": response.status_code, "body": response.json()}


def _record(tmp_path: Path) -> dict[str, dict[str, Any]]:
    recorded: dict[str, dict[str, Any]] = {}
    with _serve(tmp_path) as client:
        for name, requests in REQUESTS.items():
            recorded[name] = {
                "answers": {
                    _key(route, params): _ask(client, route, params) for route, params in requests
                }
            }
    recorded["timeline"]["first_page"] = _key("timeline", FIRST_PAGE)
    return recorded


@pytest.mark.parametrize("name", list(RECORDINGS))
def test_the_recorded_answers_are_what_the_routes_answer(tmp_path: Path, name: str) -> None:
    check_recording(RECORDINGS[name], _record(tmp_path)[name], transcript=TRANSCRIPT)


def test_the_first_page_of_twenty_is_the_start_of_the_servers_timeline(tmp_path: Path) -> None:
    with _serve(tmp_path) as client:
        whole = _ask(client, "timeline", {})["body"]
        first = _ask(client, "timeline", FIRST_PAGE)["body"]
        second = _ask(client, "timeline", {"offset": "20", "limit": "20"})["body"]
        third = _ask(client, "timeline", {"offset": "40", "limit": "20"})["body"]
    assert first["rows"] == whole["rows"][:20]
    assert second["rows"] == whole["rows"][20:40]
    assert third["rows"] == whole["rows"][40:]
    assert (first["total"], first["has_more"]) == (whole["total"], True)
    assert (second["has_more"], third["has_more"]) == (True, False)


def test_the_session_plays_the_recordings_and_asks_for_nothing_else() -> None:
    # The session fails on a request the recordings do not hold, and on an invariant of
    # the views it checks; what it prints is the golden's.
    transcript = run_session("event-log-view-session.js")
    assert transcript["requests asked of the server"]["unrecorded"] == []


def test_the_first_page_is_named_in_the_timeline_recording() -> None:
    recording = read_recording(RECORDINGS["timeline"])
    assert recording["first_page"] in recording["answers"]


def test_every_recorded_answer_is_ok_but_the_refusal() -> None:
    for name in RECORDINGS:
        for key, answer in read_recording(RECORDINGS[name])["answers"].items():
            if key == _key("errors", {"path": "absent.jsonl"}):
                assert answer["status"] == 404
            else:
                assert answer["status"] == 200, key
