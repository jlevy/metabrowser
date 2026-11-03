"""The Pulls panel session runs production browser code on what a server answers.

``tests/dom/github-pulls-panel-session.js`` drives the GitHub plugin's
``builtin_plugins/github/pulls-panel.js`` -- what the panel shows, its filters, its windows
of rows, Load more, each way a refresh can end, polling only while shown, and walking the
rows with a held key -- through a scripted conversation, and
``tests/golden/cli-ui-github-pulls-panel.tryscript.md`` pins its transcript. So that the
conversation is the real server's and not envelopes a test wrote by hand, its responses come
from ``tests/fixtures/github-pulls-panel-responses.json``: what the in-process application
answered while it served ``tests/github_pull_fixture.py``'s stand-in, with a fake ``gh``
replaying full-size pages built on a scrubbed real item. The first test here replays that
story and fails when the recording no longer matches.

The clock is fixed, so fetch times are literal. Entity tags are the session's own, since the
server's are scoped to the build; which answers share one is kept. Every list answer carries
its window of rows, and the story reads one list many times, so the recording holds each
distinct window once: an answer whose rows an earlier answer carried names that answer,
``{"same_as": "current"}``, and the session reads it back as those rows. A row is one line of
JSON in a string, so a full page is a hundred lines to review. ``make golden-update`` rewrites
the recording and then the transcript.
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

from metabrowser.builtin_plugins.github import gh, pull_list, pull_list_refresh, pulls
from metabrowser.builtin_plugins.github.gh_lists import utc_stamp
from metabrowser.builtin_plugins.github.pull_list import (
    MAX_LIST_PAGES,
    ListPageMark,
    PullList,
    PullListRow,
    write_pull_list,
)
from metabrowser.builtin_plugins.github.served_pull import ServedPulls
from metabrowser.cache.acquire import acquire_source
from metabrowser.cache.repository_store import open_revision
from metabrowser.cache.served_mirror import StoreMirror
from metabrowser.cache.urls import GitSource, RepositorySelection
from metabrowser.git import repo as git_repo
from metabrowser.mirror_refresh import serve_mirror
from metabrowser.server import app
from metabrowser.source import attach_subject, reset_source_session
from tests.github_pull_fixture import (
    ANOTHER_READER,
    CANONICAL,
    DEFAULT_BRANCH,
    FETCHED_AT,
    Origin,
    account,
    install_fake_gh,
    list_page,
    scenario,
)
from tests.golden_harness import JSON_BODY, check_recording, read_recording, run_session
from tests.required_tools import needs_git
from tests.test_cache_acquire import _allow_installed_git

RECORDING = "github-pulls-panel-responses.json"
TRANSCRIPT = "cli-ui-github-pulls-panel.tryscript.md"
_PULLS = "/api/plugin/github/pulls"
_REFRESH = "/api/plugin/github/pulls-refresh"
pytestmark = [
    needs_git,
    pytest.mark.skipif(os.name != "posix", reason="the fake gh is a POSIX script"),
]


def _answer(response: Any) -> dict[str, Any]:
    """One response as the panel sees it: status, entity tag, and body."""

    body = None if response.status_code == 304 else response.json()
    return {"status": response.status_code, "etag": response.headers.get("etag"), "body": body}


def _session_tags(recorded: dict[str, Any]) -> dict[str, Any]:
    """The session's own entity tags for the server's, keeping which answers share one."""

    own: dict[str, str] = {}
    for answer in recorded.values():
        if answer["etag"] is not None:
            answer["etag"] = own.setdefault(answer["etag"], f'"pulls-{len(own) + 1}"')
    return recorded


def _stored_once(recorded: dict[str, Any]) -> dict[str, Any]:
    """*recorded* with each distinct window of rows written once; see the module docstring."""

    whole = recorded["refreshed_whole"]["body"]
    window = recorded["more_done"]["body"]["rows"] + recorded["more_window"]["body"]["rows"]
    assert whole["rows"] == window, "the whole list is not its two windows"
    holder: dict[str, str] = {json.dumps(whole["rows"]): "refreshed_whole"}
    whole["rows"] = {"same_as": ["more_done", "more_window"]}
    for name, answer in recorded.items():
        body = answer["body"]
        if not isinstance(body, dict) or not isinstance(body.get("rows"), list) or not body["rows"]:
            continue
        key = json.dumps(body["rows"])
        if key in holder:
            body["rows"] = {"same_as": holder[key]}
        else:
            holder[key] = name
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
        subject = await open_revision(
            home=published.home,
            store_key=published.store_key,
            commit_oid=origin["topic"],
            store_identity=published.store_id,
            ref=f"refs/remotes/origin/{DEFAULT_BRANCH}",
        )
        await subject.aclose()
        return subject

    attach_subject(asyncio.run(_pin()))
    serve_mirror(
        StoreMirror.from_published(replace(published, source=source)),
        pull_requests=ServedPulls(published),
    )
    git_repo.clear_repo_cache()
    recorded: dict[str, Any] = {}
    gate = threading.Event()
    gate.set()
    original: Callable[..., Awaitable[Any]] = pull_list_refresh.refresh_pull_list

    async def held(*args: Any, **kwargs: Any) -> Any:
        # The test thread sets it; a worker thread waits, so the job runs until then.
        await asyncio.to_thread(gate.wait, 30)
        return await original(*args, **kwargs)

    monkeypatch.setattr(pull_list_refresh, "refresh_pull_list", held)
    try:
        with TestClient(app) as client:

            def read(**params: str) -> dict[str, Any]:
                return _answer(
                    client.get(_PULLS, params={"state": "all", "limit": "100", **params})
                )

            def ask(**body: Any) -> dict[str, Any]:
                return _answer(client.post(_REFRESH, json=body, headers=JSON_BODY))

            def settled(state: str = "all") -> None:
                params = {"state": state, "limit": "0"}
                deadline = time.monotonic() + 50
                while client.get(_PULLS, params=params).json()["refreshing"]:
                    assert time.monotonic() < deadline, "the refresh did not finish"
                    time.sleep(0.01)

            def failing(name: str, answers: dict[str, Any] | None) -> None:
                if answers is not None:
                    answering(answers)
                ask(state="all", retry=True)
                settled()
                recorded[f"failed {name}"] = read()

            # Nothing cached, a refresh that waits, and a read while it does.
            recorded["absent"] = read()
            gate.clear()
            recorded["refresh_started"] = ask(state="all")
            recorded["pending"] = read()
            gate.set()
            settled()
            recorded["current"] = read()
            tag = {"if-none-match": recorded["current"]["etag"]}
            params = {"state": "all", "limit": "100"}
            assert client.get(_PULLS, params=params, headers=tag).status_code == 304

            # The next GitHub page, which a reader's reaching the end asks for.
            gate.clear()
            recorded["more_started"] = ask(state="all", more=True)
            recorded["more_refreshing"] = read()
            gate.set()
            settled()
            recorded["more_done"] = read()
            after = str(recorded["more_done"]["body"]["next_after"])
            recorded["more_window"] = read(after=after)

            # The other two lists, each its own file, and one with no rows at all.
            for name in ("open", "closed"):
                recorded[f"{name}_absent"] = read(state=name)
                recorded[f"{name}_started"] = ask(state=name)
                settled(name)
                recorded[f"{name}_current"] = read(state=name)

            # A minute on, the list is stale. A refresh finds it unchanged. A poll reads the top
            # window, and the whole range held only once the list file is another.
            clock[0] = FETCHED_AT + timedelta(seconds=61)
            recorded["stale"] = read()
            gate.clear()
            recorded["refresh_again"] = ask(state="all")
            recorded["stale_refreshing"] = read()
            gate.set()
            settled()
            recorded["refreshed"] = read()
            recorded["refreshed_whole"] = read(limit="102")
            # Tried a moment ago: an automatic request starts nothing.
            recorded["not_due"] = ask(state="all")

            # Each way a refresh can end, a reader's Retry so the window does not hold it.
            first = list_page("all")
            for name, answers in (
                ("not_logged_in", {**online, "auth": {"stdout": '{"hosts":{}}\n', "exit": 0}}),
                (
                    "gh_too_old",
                    {
                        **online,
                        "auth": {"stderr": "unknown flag: --json\n\nUsage: x\n", "exit": 1},
                    },
                ),
                (
                    "not_found_or_private",
                    {
                        **online,
                        "api": {
                            **online["api"],
                            first: {"status": 404, "body": {"message": "Not Found"}},
                        },
                    },
                ),
                (
                    "network_error",
                    {
                        **online,
                        "api_failure": {
                            "stderr": "error connecting to api.github.com\n",
                            "exit": 1,
                        },
                    },
                ),
                (
                    "gh_failed",
                    {**online, "api": {**online["api"], first: {"status": 200, "raw": "not JSON"}}},
                ),
                (
                    "account_changed",
                    {**online, "auth": [account(), account(ANOTHER_READER)]},
                ),
            ):
                failing(name, answers)
            with monkeypatch.context() as patched:
                patched.setattr(gh, "gh_executable", lambda: None)
                failing("gh_missing", None)
            limit = {
                "status": 403,
                "headers": {"X-Ratelimit-Remaining": "0", "X-Ratelimit-Reset": "1790181960"},
                "body": {"message": "API rate limit exceeded"},
            }
            failing("rate_limited", {**online, "api": {**online["api"], first: limit}})
            recorded["rate_limit_holds"] = ask(state="all", retry=True)
            clock[0] = FETCHED_AT + timedelta(days=7)
            answering(online)
            ask(state="all", retry=True)
            settled()
            slug = published.slug
            directory = home / "sources" / slug / "pulls"
            directory.chmod(0o500)
            try:
                ask(state="all", retry=True)
                settled()
            finally:
                directory.chmod(0o700)
            recorded["failed cache_unwritable"] = read()
            ask(state="all", retry=True)
            settled()

            # A list another account read is shown as it is, labelled with that reader.
            answering({**online, "auth": account(ANOTHER_READER)})
            ask(state="open", retry=True)
            settled("open")
            answering(
                {
                    **online,
                    "api_failure": {"stderr": "error connecting to api.github.com\n", "exit": 1},
                }
            )
            ask(state="open", retry=True)
            settled("open")
            answering(online)
            recorded["another_reader"] = read(state="open")

            # A list with no rows whose refresh failed: the list's address has nothing to
            # select, and says why, as the tab's notice does.
            (directory / "list-open.json").unlink()
            with monkeypatch.context() as patched:
                patched.setattr(gh, "gh_executable", lambda: None)
                ask(state="open", retry=True)
                settled("open")
            recorded["open_gh_missing"] = read(state="open", limit="0")

            # A list at the most pages one may hold, read directly from what it would write:
            # the bound is what is pinned here, and a thousand rows of fetches pin nothing more.
            numbers = range(pull_list.MAX_LIST_ROWS, 0, -1)
            at_cap = PullList(
                schema_version=pull_list.PULL_LIST_SCHEMA,
                source=CANONICAL,
                list="closed",
                fetched_at=utc_stamp(clock[0]),
                reader="gh:octo-reader",
                pages=MAX_LIST_PAGES,
                complete=False,
                truncated=True,
                etags=tuple(
                    ListPageMark(
                        etag=None,
                        numbers=tuple(numbers[start : start + 100]),
                        truncated=start == 0,
                    )
                    for start in range(0, pull_list.MAX_LIST_ROWS, 100)
                ),
                rows=tuple(
                    PullListRow(
                        number=number,
                        title=f"Work item {number}",
                        state="closed",
                        draft=False,
                        merged_at=None,
                        author="contributor",
                        created_at="2026-09-17T08:00:00Z",
                        updated_at="2026-09-17T08:00:00Z",
                        closed_at="2026-09-17T08:00:00Z",
                        base_ref="main",
                        head_ref=f"work-{number}",
                        head_repository="octo/demo",
                        labels=(),
                    )
                    for number in numbers
                ),
            )
            write_pull_list(home, slug, at_cap)
            recorded["at_cap"] = read(state="closed", limit="0")
    finally:
        serve_mirror(None)
        git_repo.clear_repo_cache()
    # A server with no GitHub repository, which has nothing to list.
    reset_source_session()
    with TestClient(app) as client:
        recorded["not_github"] = _answer(client.get(_PULLS, params={"limit": "100"}))
        recorded["not_github_refresh"] = _answer(
            client.post(_REFRESH, json={"state": "all"}, headers=JSON_BODY)
        )
    return _session_tags(recorded)


def test_recording_is_what_a_served_mirror_answers(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, pull_origin: Origin
) -> None:
    recorded = _record(tmp_path, monkeypatch, pull_origin)
    absent = recorded["absent"]["body"]
    assert (absent["state"], absent["reason"]) == ("absent", "not_cached")
    assert recorded["refresh_started"]["status"] == 202
    assert recorded["pending"]["body"]["state"] == "pending"
    current = recorded["current"]["body"]
    # Full-size: a thin fake hides paging and cap bugs.
    assert (len(current["rows"]), current["fetched"], current["complete"]) == (100, 100, False)
    done = recorded["more_done"]["body"]
    assert (done["fetched"], done["complete"], len(done["rows"])) == (102, True, 100)
    assert [row["number"] for row in recorded["more_window"]["body"]["rows"]] == [6, 5]
    assert [row["number"] for row in recorded["open_current"]["body"]["rows"]] == [10, 7]
    assert recorded["stale"]["body"]["state"] == "stale"
    assert recorded["not_due"]["body"]["refresh"] == "not_due"
    for name in (
        "not_logged_in",
        "gh_too_old",
        "not_found_or_private",
        "network_error",
        "gh_failed",
        "account_changed",
        "gh_missing",
        "rate_limited",
        "cache_unwritable",
    ):
        envelope = recorded[f"failed {name}"]["body"]
        assert envelope["last_refresh"]["outcome"] == name
        assert envelope["fetched"] > 0, name
    assert recorded["rate_limit_holds"]["body"]["refresh"] == "not_due"
    assert recorded["another_reader"]["body"]["reader"] == f"gh:{ANOTHER_READER}"
    assert recorded["another_reader"]["body"]["state"] == "stale"
    nothing = recorded["open_gh_missing"]["body"]
    assert (nothing["state"], nothing["fetched"]) == ("absent", 0)
    assert nothing["last_refresh"]["outcome"] == "gh_missing"
    # A poll reads the top window; the whole range only once the list file is another.
    assert len(recorded["refreshed"]["body"]["rows"]) == 100
    assert recorded["refreshed"]["body"]["fetched_at"] != recorded["stale"]["body"]["fetched_at"]
    assert len(recorded["refreshed_whole"]["body"]["rows"]) == 102
    at_cap = recorded["at_cap"]["body"]
    assert (at_cap["at_cap"], at_cap["complete"], at_cap["fetched"]) == (True, False, 1000)
    assert recorded["not_github"]["body"]["reason"] == "not_github"
    assert recorded["not_github_refresh"]["status"] == 409
    check_recording(RECORDING, _stored_once(recorded), transcript=TRANSCRIPT, indent=1)


def test_a_held_key_asks_for_no_row_it_passes() -> None:
    """The cost the golden shows as lists of requests, held as one relation.

    However far a key walks, the walk's requests are the one stop's, and the only rows it
    touches are the two at each step: a held key costs nothing per row but those two marks.
    """

    steps = {step["step"]: step for step in run_session("github-pulls-panel-session.js")["steps"]}
    walking = steps["a key held for 40 rows"]
    assert walking["requests"] == [], "a row walked past read something"
    assert "opened" not in walking, "a row walked past opened"
    assert walking["painted"] == 0, "a step repainted the list"
    assert walking["marks"] == 80, "a step touched more than the two rows that changed"
    # The one read of the row it stopped on, and then the one opening.
    assert len(steps["the key is let go"]["requests"]) == 1
    assert len(steps["the row it stopped on opens"]["opened"]) == 1


def test_the_recording_holds_every_failure_the_plan_names() -> None:
    """Each typed state of the plan's table has a recorded answer the session plays."""

    recording = read_recording(RECORDING)
    for name in (
        "gh_missing",
        "gh_too_old",
        "not_logged_in",
        "rate_limited",
        "network_error",
        "not_found_or_private",
        "account_changed",
        "gh_failed",
        "cache_unwritable",
    ):
        assert f"failed {name}" in recording, name
