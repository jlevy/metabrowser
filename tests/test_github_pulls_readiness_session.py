"""Each Pulls row's and stack member's readiness runs production browser code on what a server answers.

``tests/dom/github-pulls-readiness-session.js`` drives the readiness lane
(``builtin_plugins/github/row-readiness.js``), the Pulls tab's readiness column
(``pulls-panel.js``), and a stack's member rows in the stack menu (``createStackMenu`` in
``pull-page.js``) and on the stack's page (``stack-page.js``), all drawn by
``stack-member-row.js``, and ``tests/golden/cli-ui-github-pulls-readiness.tryscript.md`` pins
its transcript (mb-3n21). So that what it draws is the server's verdict and not one a test
wrote, its answers are recorded here, in ``tests/fixtures/github-pulls-readiness-responses.json``:
what the in-process application answered while it served ``tests/github_pull_fixture.py``'s
stand-in, the list of pull requests and ``GET pull-statuses`` for its rows, before the scan of
every open pull request's status, while the scan runs, once it has ended, after a push the
scan has not read, after a scan another tab's Refresh started, which the story's lane does not
hear start, and after an open pull request is marked a draft; and what ``POST pulls-refresh``
said of the scan each time, and when the last one ended (``status_scan_at``). The scan is held
on the loop while the story reads it running, as the panel session's list job is. The first
test records it and fails when the recording no longer matches. A row is one line of JSON in a
string, so a hundred rows are a hundred lines to review, as the panel's recording keeps them.

The stand-in's open pull requests are each judged as GitHub's answers for them say:
``STATUS_SHAPES`` gives pull request 7 a pending docs build and a review required, and the
draft 10 conflicts; every generated one is clean with no checks; 8 is merged and 9 closed. So
the rows hold an open pull request of each tone, a closed and a merged one, and, once 105 is
pushed, one the server has no status of for its head.
"""

from __future__ import annotations

import asyncio
import json
import os
import threading
import time
from collections.abc import Awaitable, Callable
from dataclasses import replace
from datetime import timedelta
from pathlib import Path
from typing import Any

import pytest
from starlette.testclient import TestClient

from metabrowser import server
from metabrowser.builtin_plugins.github import pull_list, pull_status_scan, pulls
from metabrowser.builtin_plugins.github.served_pull import ServedPulls
from metabrowser.cache.acquire import acquire_source
from metabrowser.cache.repository_store import open_revision
from metabrowser.cache.served_mirror import StoreMirror
from metabrowser.cache.urls import GitSource, RepositorySelection
from metabrowser.git import repo as git_repo
from metabrowser.mirror_refresh import serve_mirror
from metabrowser.server import app
from metabrowser.source import reset_source_session, serve_subject_opener
from tests.github_pull_fixture import (
    CANONICAL,
    DEFAULT_BRANCH,
    FETCHED_AT,
    Origin,
    catalog_entries,
    install_fake_gh,
    list_page,
    scenario,
)
from tests.golden_harness import JSON_BODY, check_recording, read_recording, run_session
from tests.loop_gate import held_until
from tests.required_tools import needs_git
from tests.test_cache_acquire import _allow_installed_git

RECORDING = "github-pulls-readiness-responses.json"
TRANSCRIPT = "cli-ui-github-pulls-readiness.tryscript.md"
SESSION = "github-pulls-readiness-session.js"
_PULLS = "/api/plugin/github/pulls"
_REFRESH = "/api/plugin/github/pulls-refresh"
_STATUSES = "/api/plugin/github/pull-statuses"
# The pull request the story pushes after the scan.
PUSHED = 105
PUSHED_HEAD = "f" * 40
# The pull request the story marks a draft, ready to merge while open.
DRAFTED = 106
# The open rows the lane story draws, which a scan this story's lane does not hear read again.
REREAD = [106, 105, 10, 7]
pytestmark = [
    needs_git,
    pytest.mark.skipif(os.name != "posix", reason="the fake gh is a POSIX script"),
]


def _answer(response: Any) -> dict[str, Any]:
    """One response as a surface sees it: its status and its body, with no entity tag, which
    no readiness read sends back."""

    return {"status": response.status_code, "body": response.json()}


def _one_row_a_line(recorded: dict[str, Any]) -> dict[str, Any]:
    """*recorded* with each answer's rows written one to a line, as JSON in a string, and each
    list's catalog generation, which is the run's own, named by the order it first appears in,
    so which answers share one is kept."""

    generations: dict[str, str] = {}
    for answer in recorded.values():
        body = answer["body"]
        for envelope in (body, body.get("pulls") if isinstance(body, dict) else None):
            if isinstance(envelope, dict) and isinstance(envelope.get("generation"), str):
                envelope["generation"] = generations.setdefault(
                    envelope["generation"], f"catalog-{len(generations) + 1}"
                )
    for answer in recorded.values():
        body = answer["body"]
        if isinstance(body, dict) and isinstance(body.get("rows"), list):
            body["rows"] = [json.dumps(row, ensure_ascii=False) for row in body["rows"]]
    return recorded


def _record(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, origin: Origin) -> dict[str, Any]:
    home = tmp_path / "home"
    monkeypatch.setenv("METABROWSER_CACHE_DIR", str(home))
    _allow_installed_git(monkeypatch)
    monkeypatch.setattr(
        "metabrowser.cache.acquire.remote_url_for",
        lambda source: origin.url if source.normalized == CANONICAL else source.normalized,  # pyright: ignore[reportUnknownLambdaType, reportUnknownMemberType]
    )
    clock = [FETCHED_AT]
    monkeypatch.setattr(pull_list, "utc_now", lambda: clock[0])
    monkeypatch.setattr(pulls, "utc_now", lambda: clock[0])
    online = scenario(origin)

    def answering(answers: dict[str, Any]) -> None:
        for name, value in install_fake_gh(tmp_path, answers).items():
            monkeypatch.setenv(name, value)

    answering(online)
    source = GitSource(
        transport="https",
        form="url",
        normalized=CANONICAL,
        selection=RepositorySelection(kind="repository"),
    )
    published = asyncio.run(acquire_source(source, home=home))

    async def _pin() -> Any:
        return await open_revision(
            home=published.home,
            store_key=published.store_key,
            commit_oid=origin["topic"],
            store_identity=published.store_id,
            ref=f"refs/remotes/origin/{DEFAULT_BRANCH}",
        )

    serve_subject_opener(_pin)
    serve_mirror(
        StoreMirror.from_published(replace(published, source=source)),
        pull_requests=ServedPulls(published),
    )
    git_repo.clear_repo_cache()
    # The scan is held on the loop while the story reads it running, then let go.
    gate = threading.Event()
    gate.set()
    original: Callable[..., Awaitable[Any]] = pull_status_scan._scan_job  # pyright: ignore[reportPrivateUsage]

    async def held(*args: Any, **kwargs: Any) -> Any:
        await held_until(gate, 30)
        return await original(*args, **kwargs)

    monkeypatch.setattr(pull_status_scan, "_scan_job", held)
    recorded: dict[str, Any] = {}
    try:
        with TestClient(app) as client:

            def read(**params: str) -> dict[str, Any]:
                return _answer(
                    client.get(_PULLS, params={"state": "all", "limit": "100", **params})
                )

            def ask(**body: Any) -> dict[str, Any]:
                return _answer(client.post(_REFRESH, json=body, headers=JSON_BODY))

            def statuses(numbers: list[int]) -> dict[str, Any]:
                query = ",".join(str(number) for number in numbers)
                return _answer(client.get(_STATUSES, params={"numbers": query}))

            def listed() -> None:
                deadline = time.monotonic() + 50
                while client.get(_PULLS, params={"limit": "0"}).json()["refreshing"]:
                    assert time.monotonic() < deadline, "the catalog job did not finish"
                    time.sleep(0.01)

            def scanned() -> None:
                deadline = time.monotonic() + 50
                while client.get(_STATUSES, params={"numbers": "1"}).json()["scanning"]:
                    assert time.monotonic() < deadline, "the status scan did not finish"
                    time.sleep(0.01)

            # The list's first ask reads the catalog; the scan waits for a catalog to follow.
            recorded["catalog_started"] = ask(state="all", target=500)
            listed()
            scanned()
            recorded["list"] = read()
            numbers = [row["number"] for row in recorded["list"]["body"]["rows"]]
            recorded["more"] = read(after=str(recorded["list"]["body"]["next_after"]))
            more = [row["number"] for row in recorded["more"]["body"]["rows"]]
            recorded["unscanned"] = statuses(numbers)
            recorded["unscanned_more"] = statuses(more)
            # The next ask starts the scan, which is held while it is read running.
            gate.clear()
            clock[0] += timedelta(seconds=20)
            recorded["scan_started"] = ask(state="all", target=500, background=True)
            recorded["scanning"] = statuses(numbers)
            recorded["scanning_more"] = statuses(more)
            recorded["scan_joined"] = ask(state="all", target=500, background=True)
            gate.set()
            scanned()
            recorded["scanned"] = statuses(numbers)
            recorded["scanned_more"] = statuses(more)
            clock[0] += timedelta(seconds=10)
            recorded["scan_not_due"] = ask(state="all", target=500, background=True)
            scanned()

            # A push to one pull request, which the list's probe finds: its row names the new
            # head, and the status kept describes the old one, as GitHub's answer the scan
            # reads still does.
            items = [
                *online["api"][list_page("all")]["body"],
                *online["api"][list_page("all", 2)]["body"],
            ]
            clock[0] += timedelta(seconds=20)
            pushed = [
                {
                    **item,
                    "head": {**item["head"], "sha": PUSHED_HEAD},
                    "updated_at": f"{clock[0]:%Y-%m-%dT%H:%M:%SZ}",
                }
                if item["number"] == PUSHED
                else item
                for item in items
            ]
            catalog = {
                key: entry
                for key, entry in catalog_entries(pushed).items()
                if not key.startswith("graphql:statuses:")
            }
            answering({**online, "api": {**online["api"], **catalog}})
            recorded["push_found"] = ask(state="all", target=500, background=True)
            listed()
            scanned()
            recorded["pushed_list"] = read()
            recorded["pushed_more"] = read(after=str(recorded["pushed_list"]["body"]["next_after"]))
            recorded["pushed"] = statuses([PUSHED])

            # Another tab's Refresh starts a scan this story's lane does not hear, as a look at
            # the mirror's base branches starts one after an ask has answered: the next ask,
            # with nothing due, says when it ended (`status_scan_at`).
            clock[0] += timedelta(seconds=20)
            recorded["scan_elsewhere"] = ask(state="all", target=500, retry=True)
            listed()
            scanned()
            recorded["scan_ended_elsewhere"] = ask(state="all", target=500, background=True)
            recorded["rescanned"] = statuses(REREAD)

            # The author marks an open pull request a draft, which the list's probe finds: the
            # verdict judges the catalog's lifecycle, so the same status is judged anew.
            clock[0] += timedelta(seconds=20)
            drafted = [
                {**item, "draft": True, "updated_at": f"{clock[0]:%Y-%m-%dT%H:%M:%SZ}"}
                if item["number"] == DRAFTED
                else item
                for item in pushed
            ]
            catalog = {
                key: entry
                for key, entry in catalog_entries(drafted).items()
                if not key.startswith("graphql:statuses:")
            }
            answering({**online, "api": {**online["api"], **catalog}})
            ask(state="all", target=500, background=True)
            listed()
            scanned()
            recorded["drafted"] = statuses([DRAFTED])
    finally:
        gate.set()
        serve_mirror(None)
        git_repo.clear_repo_cache()
    reset_source_session()
    plain = tmp_path / "no-repository"
    plain.mkdir()
    server._set_root_dir(plain)  # pyright: ignore[reportPrivateUsage]
    with TestClient(app) as client:
        recorded["not_github"] = _answer(client.get(_STATUSES, params={"numbers": "106"}))
    return recorded


def test_recording_is_what_a_served_mirror_answers(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, pull_origin: Origin
) -> None:
    recorded = _record(tmp_path, monkeypatch, pull_origin)
    assert recorded["catalog_started"]["body"]["status_scan"] == "not_due"
    list_rows = {row["number"]: row for row in recorded["list"]["body"]["rows"]}
    assert len(list_rows) == 100
    assert all(row["state"] == "absent" for row in recorded["unscanned"]["body"]["rows"])
    assert recorded["unscanned"]["body"]["scanning"] is False
    assert recorded["scan_started"]["body"]["status_scan"] == "started"
    assert recorded["scanning"]["body"]["scanning"] is True
    assert all(row["state"] == "absent" for row in recorded["scanning"]["body"]["rows"])
    assert recorded["scan_joined"]["body"]["status_scan"] == "joined"
    assert recorded["scanned"]["body"]["scanning"] is False
    assert recorded["scan_not_due"]["body"]["status_scan"] == "not_due"
    # The list's two pages, by activity: 8 and 7 were updated before the first page's rows.
    by_number = {
        row["number"]: row
        for answer in ("scanned", "scanned_more")
        for row in recorded[answer]["body"]["rows"]
    }
    tones = {
        number: row["readiness"]["tone"] if row["readiness"] else None
        for number, row in by_number.items()
    }
    # An open pull request of each tone, and none for the closed and the merged one.
    assert {tones[106], tones[7], tones[10]} == {"success", "attention", "danger"}
    assert tones[8] is None and tones[9] is None
    assert {by_number[8]["lifecycle"], by_number[9]["lifecycle"]} == {"merged", "closed"}
    assert all(
        tones[number] is not None for number, row in list_rows.items() if row["state"] == "open"
    ), "the scan judged every open row the list holds"
    (pushed,) = recorded["pushed"]["body"]["rows"]
    assert (pushed["state"], pushed["reason"], pushed["head"]) == (
        "absent",
        "other_head",
        PUSHED_HEAD,
    )
    # A scan the story's lane did not hear start ends before the next ask, which says so.
    assert recorded["scan_elsewhere"]["body"]["status_scan"] == "started"
    ended = recorded["scan_ended_elsewhere"]["body"]
    assert ended["status_scan"] == "not_due"
    assert ended["status_scan_at"] > recorded["scan_not_due"]["body"]["status_scan_at"]
    assert recorded["rescanned"]["body"]["scan"]["at"] == ended["status_scan_at"]
    # A draft judged anew: the same status, another lifecycle, another verdict.
    (draft,) = recorded["drafted"]["body"]["rows"]
    assert (draft["lifecycle"], by_number[DRAFTED]["lifecycle"]) == ("draft", "open")
    assert draft["head"] == by_number[DRAFTED]["head"]
    assert draft["readiness"]["verdict"] != by_number[DRAFTED]["readiness"]["verdict"]
    moved = {row["number"]: row for row in recorded["pushed_list"]["body"]["rows"]}
    assert moved[PUSHED]["head_oid"] == PUSHED_HEAD != list_rows[PUSHED]["head_oid"]
    assert recorded["pushed_list"]["body"]["generation"] != recorded["list"]["body"]["generation"]
    assert recorded["not_github"]["body"] == {
        "source": None,
        "scanning": False,
        "scan": None,
        "rows": [],
    }
    check_recording(RECORDING, _one_row_a_line(recorded), transcript=TRANSCRIPT, indent=1)


def test_every_row_draws_the_verdict_its_answer_gives() -> None:
    """What the session drew, held to the recording: each row's glyph and words are its
    answer's verdict, tone, and label, and a row with none draws none."""

    recording = read_recording(RECORDING)
    rows = {
        json.loads(row)["number"]: json.loads(row)
        for answer in ("scanned", "scanned_more")
        for row in recording[answer]["body"]["rows"]
    }
    drawn = run_session(SESSION, "--part", "all")["invariants"]
    for number, shown in drawn["panel"].items():
        readiness = rows[int(number)]["readiness"]
        expected = (
            None
            if readiness is None
            else {
                "verdict": readiness["verdict"],
                "tone": readiness["tone"],
                "label": readiness["label"],
            }
        )
        assert shown == expected, number
