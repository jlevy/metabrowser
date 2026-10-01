"""The pull-request page session runs production browser code on what a served PR answers.

``tests/dom/github-pull-page-session.js`` drives the GitHub plugin's
``builtin_plugins/github/pull-page.js`` -- what the page shows, its polling, the refresh a
stale page offers, its tabs, and the Markdown it asks for part by part -- through a
scripted conversation, and ``tests/golden/cli-ui-github-pull-page.tryscript.md`` pins its
transcript. So that the conversation is the real server's and not envelopes a test
wrote by hand, its responses come from ``tests/fixtures/github-pull-page-responses.json``:
what the in-process application answered while it served pull request 7 of
``tests/github_pull_fixture.py``'s stand-in, with a fake ``gh`` replaying scrubbed real
responses. Serving began on the default branch, as it does when the pull request cannot
be opened at startup. The page opened with nothing cached, fetched the record, read its
Markdown, switched the pin to the head the record names, went stale, refreshed to a
record with the same text, and refreshed again to one with a hostile comment, recorded
both as the hook answers it and as KPress alone renders it. The same server then served
pull requests 8 and 9, merged and closed, and read each once, for the header's wording
in those states and a skipped check, then read 8 again once GitHub named no merger. The first test here replays that story and fails
when the recording no longer matches.

The clock is fixed, so fetch times are literal. Entity tags are the session's own, since
the server's are scoped to the build; which answers share one is kept. The Markdown is
cut down to the rendered text: KPress's icon sprite and asset manifest are KPress's
contract, pinned by its own render goldens, and would tie this recording to its version.
Every pull envelope carries the whole record, and the story reads one record many
times, so the recording holds each distinct record once: an answer whose record an
earlier answer carried names that answer, ``{"same_as": "current"}``, and the session
reads it back as that record. ``make golden-update`` rewrites the recording and then
the transcript.
"""

from __future__ import annotations

import asyncio
import copy
import json
import os
import re
import threading
from dataclasses import replace
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

import pytest
from starlette.testclient import TestClient

from metabrowser import kpress_adapter
from metabrowser.builtin_plugins.github import pulls
from metabrowser.builtin_plugins.github.served_pull import ServedPull, served_pull
from metabrowser.cache.acquire import acquire_source
from metabrowser.cache.repository_store import open_revision
from metabrowser.cache.served_mirror import StoreMirror
from metabrowser.cache.urls import GitSource, RepositorySelection
from metabrowser.git import repo as git_repo
from metabrowser.git.tree_source import GitRevisionSubject
from metabrowser.mirror_refresh import mirror_session, serve_mirror
from metabrowser.server import app
from metabrowser.source import attach_subject
from tests.github_pull_fixture import (
    CANONICAL,
    DEFAULT_BRANCH,
    FETCHED_AT,
    HOSTILE_COMMENT,
    Origin,
    allowlist_violations,
    copy_origin,
    html_tree,
    install_fake_gh,
    ok,
    page,
    scenario,
)
from tests.golden_harness import JSON_BODY, check_recording, run_session, settle
from tests.required_tools import needs_git
from tests.test_cache_acquire import _allow_installed_git

_PULL = "/api/plugin/github/pull"
_REFRESH = "/api/plugin/github/pull-refresh"
_MARKDOWN = "/api/plugin/github/pull-markdown"
_PIN = "/api/source/pin"
_PROSE = re.compile(r'<div class="kpress-prose[^"]*">(.*)</div></div></article>', re.S)
pytestmark = [
    needs_git,
    pytest.mark.skipif(os.name != "posix", reason="the fake gh is a POSIX script"),
]


def _answer(response: Any) -> dict[str, Any]:
    """One response as the page sees it: status, entity tag, and body."""

    body = None if response.status_code == 304 else response.json()
    return {"status": response.status_code, "etag": response.headers.get("etag"), "body": body}


def _switch(response: Any) -> dict[str, Any]:
    """A pin switch as the page reads it: the status and the pin now served.

    The rest of its status envelope carries wall-clock fetch times.
    """

    body = response.json()
    status = body.get("status") or {}
    return {
        "status": response.status_code,
        "etag": None,
        "body": {
            "changed": body.get("changed"),
            "pin": status.get("pin"),
            "ref": status.get("ref"),
        },
    }


def _prose(html: str) -> str:
    match = _PROSE.search(html)
    assert match is not None, "KPress no longer wraps rendered text in kpress-prose"
    return match.group(1)


def _kpress_render(text: str) -> str:
    """KPress's own sanitized HTML of *text*, rendered as the hook renders it."""

    return str(
        kpress_adapter.render_kpress_view(
            source_text=text,
            source_path="pull-7-hostile.md",
            kind="markdown",
            view="document",
            ext=".md",
            mtime_hash="hostile",
            size=len(text.encode()),
            include_toc="off",
        )["html"]
    )


def _session_tags(recorded: dict[str, Any]) -> dict[str, Any]:
    """Replace the server's entity tags with the session's own, keeping which are equal.

    The server's tags are scoped to the build, which changes with every version, so the
    recording would drift on each release; what the page relies on is only which answers
    carry the same tag.
    """

    own: dict[str, str] = {}
    for answer in recorded.values():
        if answer["etag"] is not None:
            answer["etag"] = own.setdefault(answer["etag"], f'"pull-{len(own) + 1}"')
    return recorded


def _stored_once(recorded: dict[str, Any]) -> dict[str, Any]:
    """*recorded* with each distinct record written once; see the module docstring.

    A record is held in full by the first pull-route answer that carried it. So a
    one-field change to a pull request's record is one changed line of the recording.
    """

    holder: dict[str, str] = {}
    for name, answer in recorded.items():
        body = answer["body"]
        if not isinstance(body, dict):
            continue
        # A pull-route answer is the envelope; a refresh answers one under ``pull``.
        for envelope in (body, body.get("pull")):
            if not isinstance(envelope, dict) or not isinstance(envelope.get("record"), dict):
                continue
            # As text, in the order the server wrote it: reordered keys are a change.
            key = json.dumps(envelope["record"])
            if key in holder:
                envelope["record"] = {"same_as": holder[key]}
            elif envelope is body:
                holder[key] = name
    return recorded


def _record(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, built: Origin) -> dict[str, Any]:
    home = tmp_path / "home"
    monkeypatch.setenv("METABROWSER_HOME", str(home))
    _allow_installed_git(monkeypatch)
    origin = copy_origin(built, tmp_path)
    monkeypatch.setattr(
        "metabrowser.cache.acquire.remote_url_for",
        lambda source: origin.url if source.normalized == CANONICAL else source.normalized,  # pyright: ignore[reportUnknownLambdaType, reportUnknownMemberType]
    )
    clock = [FETCHED_AT]
    monkeypatch.setattr(pulls, "utc_now", lambda: clock[0])
    answers = scenario(origin)
    for name, value in install_fake_gh(tmp_path, answers).items():
        monkeypatch.setenv(name, value)
    source = GitSource(
        transport="https",
        form="url",
        normalized=CANONICAL,
        selection=RepositorySelection(kind="pull_request", pull_request=7),
    )
    published = asyncio.run(acquire_source(source, home=home))
    # The pull request could not be opened when serving began, as when gh is missing,
    # so the pin fell back to the default branch; its head arrives with the first record.

    async def _pin() -> GitRevisionSubject:
        subject = await open_revision(
            home=published.home,
            store_key=published.store_key,
            commit_oid=origin["topic"],
            store_identity=published.store_id,
            ref=f"refs/remotes/origin/{DEFAULT_BRANCH}",
        )
        await subject.aclose()
        return subject

    recorded: dict[str, Any] = {}
    attach_subject(asyncio.run(_pin()))
    serve_mirror(
        StoreMirror.from_published(replace(published, source=source)),
        pull_request=7,
        companion=served_pull(published, 7),
    )
    git_repo.clear_repo_cache()
    try:
        with TestClient(app) as client:
            session = mirror_session(app)
            served = None if session is None else session.companion
            assert isinstance(served, ServedPull)
            original = served.refresh
            release = threading.Event()

            async def held() -> None:
                # The test thread sets it; a worker thread waits, so the job runs until then.
                await asyncio.to_thread(release.wait, 30)
                await original()

            monkeypatch.setattr(served, "refresh", held)
            recorded["absent"] = _answer(client.get(_PULL))
            # Asked again with that answer's tag, an absent pull request is a 304: a page
            # polling one must not repaint on every poll. The session plays its own 304,
            # so this answer is checked here and not recorded.
            tag = {"if-none-match": recorded["absent"]["etag"]}
            assert client.get(_PULL, headers=tag).status_code == 304
            recorded["refresh_started"] = _answer(client.post(_REFRESH, json={}, headers=JSON_BODY))
            recorded["pending"] = _answer(client.get(_PULL))
            release.set()
            settle(client)
            recorded["current"] = _answer(client.get(_PULL))
            record = recorded["current"]["body"]["record"]
            for part in (
                "body",
                f"issue_comment/{record['issue_comments'][0]['id']}",
                f"review/{record['reviews'][1]['id']}",
                f"review_comment/{record['review_comments'][0]['id']}",
            ):
                recorded[f"markdown {part.split('/')[0]}"] = _answer(
                    client.get(_MARKDOWN, params={"part": part})
                )
            recorded["markdown missing"] = _answer(
                client.get(_MARKDOWN, params={"part": "issue_comment/1"})
            )
            # The record names a head the fallback pin is not; the page offers it.
            recorded["switch_to_head"] = _switch(
                client.post(_PIN, json={"ref": "refs/pull/7/head"}, headers=JSON_BODY)
            )
            recorded["on_head"] = _answer(client.get(_PULL))

            # Five minutes on, the record is stale; a refresh finds nothing changed.
            clock[0] = FETCHED_AT + timedelta(minutes=5)
            recorded["stale"] = _answer(client.get(_PULL))
            release.clear()
            recorded["refresh_again"] = _answer(client.post(_REFRESH, json={}, headers=JSON_BODY))
            recorded["stale_refreshing"] = _answer(client.get(_PULL))
            release.set()
            settle(client)
            recorded["refreshed_unchanged"] = _answer(client.get(_PULL))

            # A minute later a refresh reads one more comment, which carries markup
            # KPress's sanitized mode keeps and the page must not load.
            clock[0] = FETCHED_AT + timedelta(minutes=6)
            comments_path = page("repos/octo/demo/issues/7/comments")
            comments = copy.deepcopy(answers["api"][comments_path]["body"])
            added = {
                **comments[0],
                "id": comments[0]["id"] + 1,
                "user": {"login": "forker"},
                "body": HOSTILE_COMMENT,
                "created_at": "2026-09-17T12:03:00Z",
                "updated_at": "2026-09-17T12:03:00Z",
            }
            answers["api"][comments_path] = ok(comments_path, [*comments, added])
            for name, value in install_fake_gh(tmp_path, answers).items():
                monkeypatch.setenv(name, value)
            client.post(_REFRESH, json={}, headers=JSON_BODY)
            settle(client)
            recorded["refreshed"] = _answer(client.get(_PULL))
            recorded["markdown added"] = _answer(
                client.get(_MARKDOWN, params={"part": f"issue_comment/{added['id']}"})
            )
            # What KPress alone makes of the same text, before the hook hardens it: the
            # input the page's own defense, neutralizeFragment, is played on.
            recorded["kpress added"] = {
                "status": 200,
                "etag": None,
                "body": {"tree": html_tree(_prose(_kpress_render(HOSTILE_COMMENT)))},
            }

            # The same server, handed the stand-in's merged and then its closed pull
            # request as the one it serves, as the CLI hands it one for a /pull/<n> URL,
            # and each read once: what the header says in a state other than open. The
            # server's batch readers belong to this session's event loop, so the answers
            # are recorded here rather than from a second server.
            assert session is not None
            for number, name in ((8, "merged"), (9, "closed")):
                session.companion = served_pull(published, number)
                client.post(_REFRESH, json={}, headers=JSON_BODY)
                settle(client)
                recorded[name] = _answer(client.get(_PULL))

            # GitHub then answers pull request 8 with no merger, and a refresh reads it.
            merged_path = "repos/octo/demo/pulls/8"
            unattributed = {**answers["api"][merged_path]["body"], "merged_by": None}
            answers["api"][merged_path] = ok(merged_path, unattributed)
            for name, value in install_fake_gh(tmp_path, answers).items():
                monkeypatch.setenv(name, value)
            session.companion = served_pull(published, 8)
            client.post(_REFRESH, json={}, headers=JSON_BODY)
            settle(client)
            recorded["merged_unattributed"] = _answer(client.get(_PULL))
    finally:
        serve_mirror(None)
        git_repo.clear_repo_cache()
    return _session_tags(recorded)


def test_recording_is_what_a_served_pull_request_answers(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, pull_origin: Origin
) -> None:
    recorded = _record(tmp_path, monkeypatch, pull_origin)
    assert (recorded["absent"]["body"]["state"], recorded["absent"]["body"]["reason"]) == (
        "absent",
        "not_cached",
    )
    assert recorded["refresh_started"]["body"]["pull"]["state"] == "pending"
    assert recorded["pending"]["body"]["refreshing"] is True
    assert recorded["current"]["body"]["state"] == "current"
    assert "<strong>two</strong>" in recorded["markdown body"]["body"]["html"]
    assert recorded["markdown missing"]["status"] == 404
    current = recorded["current"]["body"]
    assert current["pin"] != current["record"]["pull"]["head"]["sha"], "the pin fell back"
    switched = recorded["switch_to_head"]
    assert (switched["status"], switched["body"]["ref"]) == (200, "refs/pull/7/head")
    assert recorded["on_head"]["body"]["pin"] == current["record"]["pull"]["head"]["sha"]
    assert recorded["stale"]["body"]["state"] == "stale"
    assert recorded["stale_refreshing"]["body"]["refreshing"] is True
    refreshed = recorded["refreshed"]["body"]
    assert refreshed["state"] == "current"
    assert len(refreshed["record"]["issue_comments"]) == 2
    assert datetime.fromisoformat(refreshed["fetched_at"]) > FETCHED_AT
    unchanged = recorded["refreshed_unchanged"]["body"]
    assert unchanged["fetched_at"] != recorded["stale"]["body"]["fetched_at"]
    assert (
        unchanged["record"]["issue_comments"]
        == recorded["stale"]["body"]["record"]["issue_comments"]
    )
    kept = json.dumps(recorded["kpress added"]["body"]["tree"])
    for hazard in ('"link"', '"img"', '"svg"', '"data-kpress-video-id"', '"modal-overlay"'):
        assert hazard in kept, f"KPress alone no longer keeps {hazard}"
    assert allowlist_violations(recorded["markdown added"]["body"]["html"]) == []
    merged = recorded["merged"]["body"]["record"]["pull"]
    assert (merged["merged"], merged["merged_by"], merged["commits"]) == (True, "octo", 1)
    conclusions = [run["conclusion"] for run in recorded["merged"]["body"]["record"]["check_runs"]]
    assert conclusions == ["success", "skipped"]
    closed = recorded["closed"]["body"]["record"]["pull"]
    assert (closed["state"], closed["merged"], closed["commits"]) == ("closed", False, 1)
    unattributed = recorded["merged_unattributed"]["body"]["record"]["pull"]
    assert (unattributed["merged"], unattributed["merged_by"]) == (True, None)
    check_recording(
        "github-pull-page-responses.json",
        _stored_once(recorded),
        transcript="cli-ui-github-pull-page.tryscript.md",
    )


def test_what_the_session_would_insert_is_inside_the_allowlist() -> None:
    """The session's transcript is pinned by its golden; this parses what it would insert.

    The golden shows the hostile comment's HTML as text. Whether that text holds only
    allowlisted tags and attributes is a parse, which a reader of the golden cannot do
    by eye: both what the hook sent and what the page's own defense rebuilt from KPress's
    render alone.
    """

    transcript = run_session("github-pull-page-session.js")
    steps = {step["step"]: step for step in transcript["steps"]}
    hook = steps["the hook sends the comment inert"]["markdown"][0].split(": ", 1)[1]
    assert allowlist_violations(hook) == []
    assert allowlist_violations(transcript["pageDefense"]) == []
    assert "build badge</a>" in transcript["pageDefense"]
