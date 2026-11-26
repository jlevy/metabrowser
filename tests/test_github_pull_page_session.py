"""The pull-request page session runs production browser code on what a server answers.

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
both as the hook answers it and, in ``tests/fixtures/github-pull-page-kpress-tree.json``,
as KPress alone renders it. The same server then fetched
pull requests 8 and 9, merged and closed, and read each once, for the header's wording
in those states and a skipped check, then read 8 again once GitHub named no merger. With
GitHub out of reach, a refresh of 8 failed and the page's own request found it not due,
and a press of Fetch for 14 was refused past the bound on jobs. Served an older head of 7,
a refresh then found the newer one. A folder's server answered last. The first test here
replays that story and fails when the recording no longer matches.

The clock is fixed, so fetch times are literal. Entity tags are the session's own, since
the server's are scoped to the build; which answers share one is kept. The Markdown is
cut down to the rendered text: KPress's icon sprite and asset manifest are KPress's
contract, pinned by its own render goldens, and would tie this recording to its version,
and its stylesheets' manifest is left out for the same reason.
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
import subprocess
import threading
import time
from dataclasses import replace
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

import pytest
from starlette.testclient import TestClient

from metabrowser import kpress_adapter
from metabrowser.builtin_plugins.github import pulls
from metabrowser.builtin_plugins.github.served_pull import ServedPull, ServedPulls
from metabrowser.cache.acquire import acquire_source
from metabrowser.cache.repository_store import open_revision
from metabrowser.cache.served_mirror import StoreMirror
from metabrowser.cache.urls import GitSource, RepositorySelection
from metabrowser.git import repo as git_repo
from metabrowser.git.tree_source import GitRevisionSubject
from metabrowser.mirror_refresh import MAX_PULL_JOBS, mirror_session, serve_mirror
from metabrowser.server import app
from metabrowser.source import reset_source_session, serve_subject_opener
from tests.github_pull_fixture import (
    CANONICAL,
    DEFAULT_BRANCH,
    FETCHED_AT,
    HOSTILE_COMMENT,
    Origin,
    allowlist_violations,
    html_tree,
    install_fake_gh,
    ok,
    page,
    scenario,
)
from tests.golden_harness import (
    JSON_BODY,
    check_recording,
    normalize_pull_comparison_scopes,
    run_session,
    settle,
)
from tests.loop_gate import held_until
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


def _api(answers: dict[str, Any], path: str, entry: Any) -> dict[str, Any]:
    return {**answers, "api": {**answers["api"], path: entry}}


def _answer(response: Any) -> dict[str, Any]:
    """One response as the page sees it: status, entity tag, and body."""

    body = None if response.status_code == 304 else response.json()
    if isinstance(body, dict):
        body.pop("assets", None)
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
            "code": body.get("code"),
            "view_href": body.get("view_href"),
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
    return json.loads(normalize_pull_comparison_scopes(json.dumps(recorded)))


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


def _until_refreshed(client: TestClient, number: int) -> None:
    """Poll pull request *number* until its refresh has ended, as ``settle`` polls status.

    Bounded as ``settle`` is, so a refresh that never ends fails this test, with what it
    waited for, inside the recorder's budget, rather than ending the whole run.
    """

    deadline = time.monotonic() + 50
    while client.get(_PULL, params={"number": number}).json()["refreshing"]:
        assert time.monotonic() < deadline, f"the refresh of pull request {number} did not end"
        time.sleep(0.01)


def _fetched(client: TestClient, number: int) -> dict[str, Any]:
    """Pull request *number* after a reader's fetch of it has ended.

    Status follows the mirror and the attended pull request, so this one is watched here.
    """

    client.post(_REFRESH, json={"number": number, "retry": True}, headers=JSON_BODY)
    _until_refreshed(client, number)
    return _answer(client.get(_PULL, params={"number": number}))


def _record(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, origin: Origin) -> dict[str, Any]:
    home = tmp_path / "home"
    monkeypatch.setenv("METABROWSER_CACHE_DIR", str(home))
    _allow_installed_git(monkeypatch)
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
        return subject

    recorded: dict[str, Any] = {}
    # The serving lifespan owns the pin and any subjects a pin switch replaces it with.
    serve_subject_opener(_pin)
    serve_mirror(
        StoreMirror.from_published(replace(published, source=source)),
        pull_request=7,
        pull_requests=ServedPulls(published),
    )
    git_repo.clear_repo_cache()
    try:
        with TestClient(app) as client:
            session = mirror_session(app)
            served = None if session is None else session.companion
            assert isinstance(served, ServedPull)
            read_7 = {"number": 7}
            ask_7 = {"number": 7, "retry": True}
            original = served.refresh
            release = threading.Event()

            async def held() -> None:
                # The test thread sets it; the job is held on the loop until then.
                await held_until(release, 30)
                await original()

            monkeypatch.setattr(served, "refresh", held)
            recorded["absent"] = _answer(client.get(_PULL, params=read_7))
            # Asked again with that answer's tag, an absent pull request is a 304: a page
            # polling one must not repaint on every poll. The session plays its own 304,
            # so this answer is checked here and not recorded.
            tag = {"if-none-match": recorded["absent"]["etag"]}
            assert client.get(_PULL, params=read_7, headers=tag).status_code == 304
            recorded["refresh_started"] = _answer(
                client.post(_REFRESH, json=ask_7, headers=JSON_BODY)
            )
            recorded["pending"] = _answer(client.get(_PULL, params=read_7))
            release.set()
            settle(client)
            recorded["current"] = _answer(client.get(_PULL, params=read_7))
            record = recorded["current"]["body"]["record"]
            for part in (
                "body",
                f"issue_comment/{record['issue_comments'][0]['id']}",
                f"review/{record['reviews'][1]['id']}",
                f"review_comment/{record['review_comments'][0]['id']}",
            ):
                recorded[f"markdown {part.split('/')[0]}"] = _answer(
                    client.get(_MARKDOWN, params={**read_7, "part": part})
                )
            recorded["markdown missing"] = _answer(
                client.get(_MARKDOWN, params={**read_7, "part": "issue_comment/1"})
            )
            # The pin is a branch, so Browse code serves the head first, by its commit and
            # under the pull request's ref; one the mirror lacks is refused, and the page
            # says why.
            head = recorded["current"]["body"]["record"]["pull"]["head"]["sha"]
            browse = {"under": "refs/pull/7/head", "view": "/view/"}
            recorded["switch_refused"] = _switch(
                client.post(_PIN, json={"oid": "e" * 40, **browse}, headers=JSON_BODY)
            )
            recorded["switch_to_head"] = _switch(
                client.post(_PIN, json={"oid": head, **browse}, headers=JSON_BODY)
            )
            recorded["on_head"] = _answer(client.get(_PULL, params=read_7))

            # Five minutes on, the record is stale; a refresh finds nothing changed.
            clock[0] = FETCHED_AT + timedelta(minutes=5)
            recorded["stale"] = _answer(client.get(_PULL, params=read_7))
            release.clear()
            # The page asks by itself, which is not a reader's action: the record is due.
            recorded["refresh_again"] = _answer(
                client.post(_REFRESH, json=read_7, headers=JSON_BODY)
            )
            recorded["stale_refreshing"] = _answer(client.get(_PULL, params=read_7))
            release.set()
            settle(client)
            recorded["refreshed_unchanged"] = _answer(client.get(_PULL, params=read_7))

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
            client.post(_REFRESH, json=ask_7, headers=JSON_BODY)
            settle(client)
            recorded["refreshed"] = _answer(client.get(_PULL, params=read_7))
            recorded["markdown added"] = _answer(
                client.get(_MARKDOWN, params={**read_7, "part": f"issue_comment/{added['id']}"})
            )

            # Ten seconds on, the page's own ask for the current record is a probe: GitHub
            # answers its conditional read 304, so nothing is refreshed, and the record is
            # vouched for by the probe. The ask names the record the page shows, so the
            # answer leaves it out.
            clock[0] = FETCHED_AT + timedelta(minutes=6, seconds=10)
            held_7 = {**read_7, "held": recorded["refreshed"]["body"]["record_revision"]}
            recorded["probed"] = _answer(client.post(_REFRESH, json=held_7, headers=JSON_BODY))
            assert recorded["probed"]["body"]["refresh"] == "not_due"
            probed = recorded["probed"]["body"]["pull"]
            assert probed["record_held"] is True and "record" not in probed
            recorded["probed_current"] = _answer(client.get(_PULL, params=read_7))
            assert recorded["probed_current"]["body"]["verified_by"] == "probe"
            clock[0] = FETCHED_AT + timedelta(minutes=6)

            # The same server, asked for the stand-in's merged and then its closed pull
            # request, each read once: what the header says in a state other than open.
            for number, name in ((8, "merged"), (9, "closed")):
                recorded[name] = _fetched(client, number)

            # GitHub then answers pull request 8 with no merger, and a refresh reads it.
            merged_path = "repos/octo/demo/pulls/8"
            unattributed = {**answers["api"][merged_path]["body"], "merged_by": None}
            answers["api"][merged_path] = ok(merged_path, unattributed)
            for name, value in install_fake_gh(tmp_path, answers).items():
                monkeypatch.setenv(name, value)
            recorded["merged_unattributed"] = _fetched(client, 8)

            # Half an hour on, GitHub is out of reach. A reader's refresh of 8 fails, so the
            # page's own request finds it tried a moment ago; a reader may still ask again.
            clock[0] = FETCHED_AT + timedelta(minutes=30)
            offline = {**answers, "api_failure": {"stderr": "dial tcp: i/o timeout\n", "exit": 1}}
            for name, value in install_fake_gh(tmp_path, offline).items():
                monkeypatch.setenv(name, value)
            recorded["failed"] = _fetched(client, 8)
            recorded["not_due"] = _answer(
                client.post(_REFRESH, json={"number": 8}, headers=JSON_BODY)
            )
            recorded["failed_again"] = _answer(
                client.post(_REFRESH, json={"number": 8, "retry": True}, headers=JSON_BODY)
            )
            _until_refreshed(client, 8)

            # Served an older head of 7, as a page left open is: a refresh finds a newer
            # one, and the server follows the pull request's head to it.
            def _answering_7(head: str) -> None:
                path = "repos/octo/demo/pulls/7"
                body = answers["api"][path]["body"]
                moved = _api(
                    answers, path, ok(path, {**body, "head": {**body["head"], "sha": head}})
                )
                for part, empty in (
                    ("check-runs", {"total_count": 0, "check_runs": []}),
                    ("status", {"state": "pending", "statuses": []}),
                ):
                    listed = page(f"repos/octo/demo/commits/{head}/{part}")
                    moved = _api(moved, listed, ok(listed, empty))
                subprocess.run(
                    ["git", "--git-dir", str(origin.path), "update-ref", "refs/pull/7/head", head],
                    check=True,
                )
                for name, value in install_fake_gh(tmp_path, moved).items():
                    monkeypatch.setenv(name, value)

            clock[0] = FETCHED_AT + timedelta(minutes=40)
            _answering_7(origin["fork_earlier"])
            _fetched(client, 7)
            assert client.post(_PIN, json={"ref": "refs/pull/7/head"}, headers=JSON_BODY).json()
            clock[0] = FETCHED_AT + timedelta(minutes=41)
            _answering_7(origin["fork_head"])
            recorded["followed_head"] = _fetched(client, 7)

            # A number with no record, and a press of Fetch past the bound on jobs.
            recorded["absent_14"] = _answer(client.get(_PULL, params={"number": 14}))
            gate = threading.Event()

            async def waiting(_served: ServedPull) -> None:
                await held_until(gate, 30)

            monkeypatch.setattr(ServedPull, "refresh", waiting)
            for number in range(20, 20 + MAX_PULL_JOBS):
                started = client.post(
                    _REFRESH, json={"number": number, "retry": True}, headers=JSON_BODY
                )
                assert started.status_code == 202
            recorded["too_many"] = _answer(
                client.post(_REFRESH, json={"number": 14, "retry": True}, headers=JSON_BODY)
            )
            gate.set()
    finally:
        serve_mirror(None)
        git_repo.clear_repo_cache()
    # A server with no GitHub repository, which answers for no number. Explicitly
    # choose a plain folder: the test runner itself lives inside a GitHub checkout.
    from metabrowser.server import _set_root_dir

    plain = tmp_path / "plain-folder"
    plain.mkdir()
    _set_root_dir(plain)
    reset_source_session()
    with TestClient(app) as client:
        recorded["not_github"] = _answer(client.get(_PULL, params={"number": 7}))
    return _session_tags(recorded)


# The recorder runs about 226 processes one after another (75 launches of the fake gh, a
# Python interpreter each, and 151 of Git) and spends about 9 s of CPU with them, measured
# 2026-11-23 on a 10-core M1 Pro. CI's call takes about 4 s. Here, alone, it took 33 s at a
# load average near 320 and 42 s near 400; three copies at once near 405 took 43 to 48 s.
# Three more near 396, with an event log recording them, passed the suite's 60 s default,
# which ends the whole run. Each was at a different step, every refresh job had ended (the
# longest in 7.8 s), and no process ran longer than 1.5 s: slow, never stuck. Its polls
# (``settle`` and ``_until_refreshed``) are each bounded at 50 s, so one that never ends
# fails this test instead.
@pytest.mark.timeout(180)
def test_recording_is_what_a_served_pull_request_answers(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, pull_origin: Origin
) -> None:
    recorded = _record(tmp_path, monkeypatch, pull_origin)
    assert (recorded["absent"]["body"]["state"], recorded["absent"]["body"]["reason"]) == (
        "absent",
        "not_cached",
    )
    assert recorded["refresh_started"]["body"]["pull"]["state"] == "pending"
    assert recorded["refresh_again"]["body"]["refresh"] == "started"
    assert recorded["not_due"]["body"]["refresh"] == "not_due"
    assert recorded["failed"]["body"]["last_refresh"]["outcome"] == "network_error"
    assert (recorded["too_many"]["status"], recorded["too_many"]["body"]["code"]) == (
        429,
        "too_many",
    )
    assert recorded["not_github"]["body"]["reason"] == "not_github"
    followed = recorded["followed_head"]["body"]
    assert followed["pin"] == pull_origin["fork_head"] != pull_origin["fork_earlier"]
    assert followed["pin_ref"] == "refs/pull/7/head"
    assert followed["record"]["pull"]["head"]["sha"] == pull_origin["fork_head"]
    assert recorded["switch_refused"]["status"] == 404
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
    # What KPress alone makes of the hostile comment, before the hook hardens it: the
    # input the page's own defense, neutralizeFragment, is played on. It is no answer of
    # the server, and at 245 lines it is a recording of its own, which keeps the server's
    # inside the review budget.
    kpress_tree = html_tree(_prose(_kpress_render(HOSTILE_COMMENT)))
    kept = json.dumps(kpress_tree)
    # KPress (from jlevy/kpress#82) removes a raw `<link>` itself; tests/dom/inert-html-session.js
    # hands one to the page's allowlist directly.
    for hazard in ('"img"', '"svg"', '"data-kpress-video-id"', '"modal-overlay"'):
        assert hazard in kept, f"KPress alone no longer keeps {hazard}"
    assert allowlist_violations(recorded["markdown added"]["body"]["html"], pr_text=True) == []
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
    check_recording(
        "github-pull-page-kpress-tree.json",
        {"tree": kpress_tree},
        transcript="cli-ui-github-pull-page.tryscript.md",
    )


def test_what_the_session_would_insert_is_inside_the_allowlist() -> None:
    """The session's transcript is pinned by its golden; this parses what it would insert.

    The golden shows the hostile comment's HTML as text. Whether that text holds only
    allowlisted tags and attributes is a parse, which a reader of the golden cannot do
    by eye: both what the hook sent and what the page's own defense rebuilt from KPress's
    render alone.

    The script prints its first part unless asked, and its golden is split in two for the
    size of one block, so this asks for both: the second part's typed states are read here
    too, and none of them may claim to know what the pull request changed.
    """

    transcript = run_session("github-pull-page-session.js", "--part", "all")
    steps = {step["step"]: step for step in transcript["steps"]}
    hook = steps["the hook sends the comment inert"]["markdown"][0].split(": ", 1)[1]
    assert allowlist_violations(hook, pr_text=True) == []
    assert allowlist_violations(transcript["pageDefense"]) == []
    # An image written in full over https is an image, with no referrer sent.
    assert (
        '<img loading="lazy" referrerpolicy="no-referrer" src="https://example.com/badge.png"'
        ' alt="build badge">'
    ) in transcript["pageDefense"]
    unavailable = transcript["filesUnavailable"]
    assert set(unavailable) == {
        "fetch_failed",
        "no_merge_base",
        "base_uncertain",
        "commits_unavailable",
        "no_store",
        "comparison_timeout",
        "comparison_too_large",
    }
    for state, said in unavailable.items():
        assert said["files"].startswith("Changes "), state
    # A state another fetch can settle ends with that remedy.
    for state in ("base_uncertain", "commits_unavailable", "comparison_timeout"):
        assert unavailable[state]["files"].split(". ")[-1].startswith("Refresh"), state
    # A checkout's page offers nothing that serves or switches code: it has no pin.
    for when, checkout_page in transcript["checkout"].items():
        if when.startswith("a mirror"):
            continue
        assert (checkout_page["browse"], checkout_page["comparison"]) == (None, None)
    assert transcript["hunks"] and transcript["place"]


# What the navigation's Refresh asks of the page in the mount session (mb-ablv): a refresh
# that recovers the comparison on screen.
_PULLS_REFRESH = (
    'POST /api/plugin/github/pull-refresh {"number":7,"retry":true,"recovery":'
    '{"base":"f92fd713acd521d4ebb62fb9f345ec927b8b6d1b",'
    '"head":"85fcb2fa9e77eb5db485ffef445cbbc645d6db4a"}}'
)


def _text_diagram_steps() -> list[str]:
    """What the mount session's ``textDiagrams`` story says, step by step."""

    # Each binding's Mermaid is the diagram frame's, on a folder's page as on a pinned
    # revision's; the session publishes no Mermaid bundle, so asking only reads its address.
    body = "body as image, 1 figure, Mermaid the diagram frame's"
    comment = "issue_comment/3341937855 as image, 1 figure, Mermaid the diagram frame's"
    gone = ", disposed"
    modules = "kpress-diagrams, kpress-diagram-controls"
    address = "the mermaid bundle's address"
    both = "2 blocks, 2 in a figure"
    one = "1 block, 1 in a figure"
    folder = f"{body}; {comment}"
    first = f"{body}{gone}; {comment}{gone}"
    return [
        "a description and a comment with no Mermaid block: 0 blocks, 0 in a figure; "
        "asked nothing; bindings none",
        f"the same with Mermaid blocks, on a folder's page: {both}; asked markdown plugin, "
        f"markdown plugin, {modules}, {modules}, {address}; bindings {folder}",
        f"a description and a comment each with a Mermaid block: {both}; asked markdown "
        f"plugin, markdown plugin, {modules}, {modules}, {address}; bindings {first}; "
        f"{body}; {comment}",
        f"a poll of the same record: {both}; asked nothing; bindings {first}; {body}; {comment}",
        f"Changes and back to Conversation: {both}; asked nothing; bindings {first}; "
        f"{body}; {comment}",
        f"the description edited, the comment not: {both}; asked markdown plugin, "
        f"{modules}, {address}; bindings {first}; {body}{gone}; {comment}; {body}",
        f"the description's block taken out: {one}; asked nothing; bindings {first}; "
        f"{body}{gone}; {comment}; {body}{gone}",
        f"a block whose text is replaced before the Markdown plugin arrives: {one}; asked "
        f"markdown plugin; bindings {first}; {body}{gone}; {comment}; {body}{gone}",
        f"the page ends: {one}; asked nothing; bindings {first}; {body}{gone}; "
        f"{comment}{gone}; {body}{gone}",
    ]


def test_failed_diff_mount_offers_retry_and_settles_readiness() -> None:
    """Asset and renderer failures recover without a dangling readiness rejection."""

    result = run_session("github-pull-page-mount-behavior.js")
    # What a text's links open (`textLinks`) is the golden's, and the session asserts that a
    # click opens each in-app link's own address. Read here: no link it lists is the missing
    # page github.com resolves a path-relative reference to under the pull request, an in-app
    # link names a file, a pull request's page, a commit's, or the list, and one that leaves
    # for github.com names a file at the head the record's comparison names.
    head = json.loads(
        (Path(__file__).parent / "fixtures/github-pull-page-responses.json").read_text("utf-8")
    )["current"]["body"]["record"]["comparison"]["head"]
    hrefs = re.findall(r"→ ([^;\s]+)", "\n".join(result.pop("textLinks")))
    assert hrefs, "the steps list their links"
    for href in hrefs:
        assert "/pull/docs/" not in href, href
        assert (
            href.startswith(("/view/", "/pull/", "/commit/"))
            or href == "/pulls"
            or href.startswith(f"https://github.com/octo/demo/blob/{head}/")
        ), href
    assert result == {
        "titleStateAndTextBadge": True,
        "failedAssetsRecover": True,
        "failedRenderRecovers": True,
        "staleRetryIsInert": True,
        "checkoutFetchIsAutomatic": True,
        "displayedComparisonRepair": True,
        "bridgeAfterPaint": True,
        "bridgeFramesOwned": True,
        "hiddenReadiness": True,
        "markdownOwnership": True,
        "checkRows": True,
        "headerAges": True,
        "headerShape": True,
        # The freshness note's slot is as wide as its widest age, "59 min ago"; an age wider
        # still sizes its own (mb-ne91).
        "widestNotes": {
            "Fetched just now via GitHub CLI": "Fetched 59 min ago via GitHub CLI",
            "Fetched 3 h ago via GitHub CLI": "Fetched 59 min ago via GitHub CLI",
            "Offline · fetched 12 d ago via GitHub CLI": (
                "Offline · fetched 59 min ago via GitHub CLI"
            ),
            "Description fetched 7 min ago via GitHub CLI": (
                "Description fetched 59 min ago via GitHub CLI"
            ),
            "Fetched at an unknown time via GitHub CLI": (
                "Fetched at an unknown time via GitHub CLI"
            ),
        },
        # A hold's lift time in the short form, en-US in UTC: a time of day when it lifts
        # today, a short date and time when not (B3 of review B on #506).
        "holdLifts": {
            "today": "2:05 PM",
            "tomorrow": "9/18/26, 12:30 AM",
            "next year": "1/2/27, 8:00 AM",
        },
        # The Diff summary is the header's last row on every tab (mb-pb35), and holds the
        # shell's pending placeholder while a comparison is on its way and while it is read,
        # on Changes the mounted diff's, and nothing once a read draws none, until a read of
        # it starts again (mb-onr2), as one does at the page's next paint after a failure;
        # from the first paint of a page whose read will bring a comparison (mb-30dz);
        # a pull request opened again in the document is drawn from the kept comparison as
        # it mounts, one first read on Changes too (mb-neg9).
        "headerSummary": [
            "Conversation, the comparison not yet read: the pending placeholder",
            "the comparison read: the summary",
            "Changes: the summary",
            "Checks, the comparison not yet read: the pending placeholder",
            "Checks, the comparison read: the summary",
            "the same pull request again in this document, before any idle: the summary",
            "opened on Changes, from what its diff read: the summary",
            "opened again on Conversation after Changes, before any idle: the summary",
            "a read that will fail, not yet answered: the pending placeholder",
            "the read fails: nothing",
            "a repaint after it failed, its read asked again: the pending placeholder",
            "that read fails too: nothing",
            "a comparison the summary draws nothing for: nothing",
            "opened on Changes, whose diff reads no comparison: nothing",
            "the record on its way: the pending placeholder",
            "a direct link's page before its first answer: the pending placeholder",
            "its first answer: not cached, its own fetch to be sent: the pending placeholder",
            "its fetch's core preview: the pending placeholder",
            "its record lands, the comparison not yet read: the pending placeholder",
            "the comparison read: the summary",
            "a direct link's first answer: not GitHub's: nothing",
            "a direct link's first answer: a server with no store, its own fetch to be sent: nothing",
            "a direct link's first answer: its refresh failed, nothing running: nothing",
            "a direct link's first answer: a core, its refresh failed, nothing running: nothing",
            "a record that names no comparison: nothing",
            "a core preview whose read prepares its comparison: the pending placeholder",
            "its record lands, the comparison not yet read: the pending placeholder",
            "the comparison read: the summary",
            "a core preview whose read prepares no comparison: nothing",
            "a prepared core, the page's own fetch still to be sent: the pending placeholder",
            "a core whose read ended, the page's own fetch still to be sent: the pending placeholder",
            "a record whose comparison the page asked to prepare: the pending placeholder",
            "the preparation ends with no comparison: nothing",
            "a record whose comparison nothing prepares: nothing",
            "Changes, its diff reads no comparison: nothing",
            # Changes follows a moved head; the way back shows the earlier diff, whose failed
            # read leaves the record's summary drawn, as a repair of an older diff does.
            "a record with a moved head is followed: its diff reads the comparison: the summary",
            "the reader goes back: the earlier diff reads none again: the summary",
            "the reader takes the newer changes, their diff not yet read: the summary",
            "their diff reads the comparison: the summary",
            "Changes, its diff throws: nothing",
            "Retry, the diff not yet read: the pending placeholder",
            "the diff reads the comparison: the summary",
            "Changes, its diff still reading: the pending placeholder",
            "the record then names no comparison: nothing",
        ],
        # The cached changed-files list's brief line holds the Diff summary's row while its
        # comparison is on its way or read, once the page knows the head, for its head and
        # base only, from the Pulls rows' memory when nothing said it changed, else one read
        # at mount; the summary replaces it, a failed read keeps it, and a page that went
        # draws nothing more (mb-z8ea).
        "summaryBrief": [
            "a direct link's page before its first answer, its head unknown: the pending placeholder; 1 reads",
            'its core preview, of the list\'s head and base branch: the brief line "1 A, 2 M \u00b7 +12 \u22124"; 1 reads',
            'its record lands, the comparison not yet read: the brief line "1 A, 2 M \u00b7 +12 \u22124"; 1 reads',
            "the comparison read: the summary; 1 reads",
            "a direct link's page, the list of an older head: the pending placeholder; 1 reads",
            "its core preview, of a newer head: the pending placeholder; 1 reads",
            "a record whose list was read for another base branch: the pending placeholder; 1 reads",
            "a core preview, the local comparison's list, whose base the core cannot say: the pending placeholder; 1 reads",
            'its record lands, naming the same comparison: the brief line "1 A, 2 M \u00b7 +12 \u22124"; 1 reads',
            "a record whose comparison has another base than the local list's: the pending placeholder; 1 reads",
            'a record of the list\'s head, its comparison not yet read: the brief line "1 A, 2 M \u00b7 +12 \u22124"; 1 reads',
            'the comparison\'s read fails: the brief line "1 A, 2 M \u00b7 +12 \u22124"; 1 reads',
            "no list cached: the pending placeholder; 1 reads",
            # A list that deleted nothing says no zero total (mb-ox6a).
            'a record of a list that only adds lines: the brief line "1 A, 2 M \u00b7 +3,893"; 1 reads',
            'opened from a Pulls row that drew its line: the brief line "1 M \u00b7 +12 \u22124"; 0 reads',
            'opened from a Pulls row whose line the lane marked out of date, read again: the brief line "1 A, 2 M \u00b7 +12 \u22124"; 1 reads',
            "a page that went before its read answered, its summary drawn: the summary; 1 reads",
        ],
        # A page mounted with no record in hand holds its cold header and tab column for the
        # quiet period, and the first header with a record lifts it, also while the
        # conversation's first paint still waits for its Markdown (exp-099). Its cold title is
        # the Pulls row's, in the record's shape, when exactly one repository's row for its
        # number is in hand, and the plain "Pull request #N" otherwise.
        "coldHold": [
            "mounted with no record in hand: header github-pull-cold, tab column github-pull-cold",
            "its record lands, the conversation waiting for its Markdown: header shown, tab column shown",
            "the conversation's first paint, at its bound: header shown, tab column shown",
            "on Changes, mounted with no record in hand: header github-pull-cold, tab column github-pull-cold",
            "its record lands: header shown, tab column shown",
            "mounted with its record in hand: header shown, tab column shown",
            'no Pulls row in hand, mounted with no record in hand: title "Pull request #7", plain',
            'its Pulls row in hand, mounted with no record in hand: title "Count to two in the app #7", the record\'s shape',
            "its Pulls row in hand, mounted with no record in hand: header github-pull-cold, tab column github-pull-cold",
            'two repositories\' rows for its number, mounted with no record in hand: title "Pull request #7", plain',
        ],
        # The header's corner, for the View on GitHub button (mb-4wqh): right after the
        # title from the cold header on, one corner for the page's life, and the page asks
        # the SDK for the button of the address it is at after each header paint. An SDK
        # with no button leaves the corner empty.
        "counterpart": [
            'mounted with no record in hand: the corner after the title "Pull request #7"; '
            "asked /pull/7",
            'its record lands: the corner after the title "Count to two in the app", '
            "the same corner; asked /pull/7",
            'a poll brings a new title: the corner after the title "Count to three in the app", '
            "the same corner; asked /pull/7",
            'the route shows Checks: the corner after the title "Count to three in the app", '
            "the same corner; asked /pull/7/checks",
            'an SDK with no button: the corner after the title "Count to two in the app"; '
            "asked for none",
        ],
        # C, G, D, and E run the page's setTab through the shortcut facade, with or without
        # Shift. H is the Commits tab's, so Checks is E. The header keeps the tab column
        # unless its first read fails, so they are live from first paint, as the links
        # are; they wait while the column is out after a failed first read, and while the
        # page is staged inert. The links come back badged at once while Shift is held,
        # which paintHeader's retarget does. The header's links and actions are numbered
        # by their place, through the same facade, and a number runs what its place's
        # control does in the paint on screen: Browse code asks to serve the head, by its
        # commit and under its ref, and, once a refresh serves it, opens the code; Refresh
        # asks for a refresh, and moves up to 1 when Browse code goes. View on GitHub, the
        # corner's button, is not numbered (mb-4wqh).
        "tabKeys": [
            "before the record, the tab column in the page: "
            "Conversation C, Docs D, Changes G, Checks E; live conversation docs files checks",
            "C: showed Conversation",
            "G: opened the files route",
            "the record arrives and paintHeader keeps the column: "
            "Conversation C, Docs D, Changes G, Checks E",
            "live: conversation docs files checks",
            "numbered: 1 Browse code",
            "1: POST /api/source/pin "
            '{"oid":"85fcb2fa9e77eb5db485ffef445cbbc645d6db4a","under":"refs/pull/7/head",'
            '"view":"/view/"}',
            "C: showed Conversation",
            "G: opened the files route",
            "the route arrives: Changes",
            # The page has no Refresh of its own (mb-ablv): Changes numbers Browse code alone,
            # and the navigation's Refresh runs the page's `refresh` as its part
            # (static/refresh-plan.js), which names the comparison on screen. While a refresh
            # runs the page offers none. Code on the pull request's head numbers no switch to
            # it: the server follows that head.
            "numbered on Changes: 1 Browse code",
            f"the navigation's Refresh, the page offering one: {_PULLS_REFRESH}",
            "numbered after a refresh serves the head: 1 Browse code",
            "1: navigation.open /view/",
            f"the navigation's Refresh, the page offering one: {_PULLS_REFRESH}",
            "numbered after a refresh with no pin: none",
            "1: not handled",
            f"the navigation's Refresh, the page offering one: {_PULLS_REFRESH}",
            "numbered with the code on the head: 1 Browse code",
            f"the navigation's Refresh, the page offering one: {_PULLS_REFRESH}",
            "while that refresh runs, the page can refresh: false",
            "the navigation's Refresh, the page not offering one: nothing asked",
            # Once the refresh ends the page offers one again on Changes; on Conversation
            # nothing is left to refresh.
            "once the refresh ends, the page can refresh: true",
            "on Conversation once the refresh ends, the page can refresh: false",
            "numbered on Conversation once the refresh ends: 1 Browse code",
            "2: not handled",
            "Shift+H: not handled",
            "Shift+E: opened the checks route",
            "Shift+C: opened the conversation route",
            "Ctrl+G: not handled",
            "staged inert: G: not handled",
            "committed: G: opened the files route",
            "disposed: Conversation none, Docs none, Changes none, Checks none; keys none; G: not handled",
            "a failed first read takes the column out: live none",
            "G: not handled",
            "on Changes, Shift held while it is out: badges none",
            "the next read answers, and the returning tabs are badged: "
            "Conversation C, Docs D, Changes G, Checks E",
            "the next read answers and paintHeader puts the column back: "
            "Conversation C, Docs D, Changes G, Checks E",
            "live: conversation docs files checks",
            "G: showed Changes",
            # Guided Review's tab and its key R (Docs holds D) exist only where the description
            # opens a `guided-review` fence: the link leads the bar when a record brings one, stays while its tab is shown, and leaves the bar, and the
            # key, otherwise. The page cannot tell a block from an example of one inside
            # another fence, which the server's parse can (mb-y0en), so the example shows
            # the tab too. On the front page, which a block makes the guide, R shows the
            # page on screen and opens no second entry of it (B20 of review B on #677).
            "no block in the description: Conversation C, Docs D, Changes G, Checks E; "
            "live conversation docs files checks",
            "R: not handled",
            "a block in the description: "
            "Guided Review R, Conversation C, Docs D, Changes G, Checks E; "
            "live conversation docs files guided checks",
            "R: showed Guided Review",
            "the route arrives: Guided Review",
            "the block leaves while its tab is shown: "
            "Guided Review R, Conversation C, Docs D, Changes G, Checks E; Guided Review",
            "back on Conversation: Conversation C, Docs D, Changes G, Checks E; R: not handled",
            "the block returns while Shift is held: "
            "badges Guided Review R, Conversation C, Docs D, Changes G, Checks E",
            "R: showed Guided Review",
            "an example of the block inside another fence: "
            "Guided Review R, Conversation C, Docs D, Changes G, Checks E",
            # The guide loads what draws its steps as it mounts, so a step shows whole
            # (mb-7bu6); this page has neither, and the guide says so once for each.
            "the guide, with no diff plugin or allowlist here, said: "
            "metabrowser github: the diff plugin did not load for the guide; "
            "metabrowser github: the guide's notes will show as typed",
            "disposed: keys none",
        ],
        # The guide's first step waits for the description it draws above it (mb-7bu6):
        # a pending Markdown render keeps the step out of sight, and its insertion,
        # which ends the wait, shows the step whole.
        "guideIntroduction": [
            "asked: pull-files-summary, stacks, guided-review, pull-markdown, pull",
            "the guide answered, its description's Markdown not yet: the notice hidden; "
            "the description hidden; a step waits out of sight true",
            "the Markdown is inserted: the notice says This pull request has no guide.; "
            "the description shows Counts to two, rendered.; a step waits out of sight "
            "false",
            "warned: 2",
        ],
        # A description whose Markdown never comes keeps the guide out of sight only until
        # the introduction's bound, `GUIDE_INTRODUCTION_HOLD_MS` (review of #859, M2): then
        # the step shows with the description's placeholder.
        "guideIntroductionBound": [
            "asked: pull-files-summary, stacks, guided-review, pull-markdown, pull",
            "the guide answered, its description's Markdown not yet: the notice hidden; "
            "the description hidden; a step waits out of sight true",
            "its Markdown never comes, and the bound runs out: the notice says This pull "
            "request has no guide.; the description shows its placeholder; a step waits out "
            "of sight false",
            "warned: 2",
        ],
        # A refused text on the mounted page (review A of #527, A6 and A8; review D, D8):
        # one notice right after its plain text, which a rebuilt text element keeps, a
        # later refusal replaces, and a render takes away.
        "textRefusal": [
            "refused past the deadline: plain, 1 notice right after it, a status: "
            "This text took too long to render, so it is shown as written.",
            "rebuilt for another state, its Markdown not yet answered: plain, 1 notice "
            "right after it, a status: This text took too long to render, so it is shown "
            "as written., new element",
            "a newer record, the same text refused again as unavailable: plain, 1 notice "
            "right after it, a status: This text could not be rendered, so it is shown as "
            "written. Reload the page to try again., new element",
            "a newer record whose Markdown renders: rendered rendered A, no notice, same element",
        ],
        # A text's Mermaid blocks, in the description and in a comment, drawn as images
        # through the Markdown plugin's published host, asked for only once a text has one;
        # a binding lasts as long as its text's section and ends with the page (A3 of the
        # review of #597).
        "textDiagrams": _text_diagram_steps(),
        # Browse code's switch is the diff plugin's, in a module it loads on demand: the
        # plugin's assets or that module not loading is said as a failed request, and asks
        # the server nothing (A3 of review A on #511).
        "switchUnavailable": [
            "the diff plugin's assets not loading: The switch request failed.; asked nothing",
            "the switch module not loading: The switch request failed.; asked nothing",
        ],
        # The Diff summary's wait, which the event log hears of only if it runs late: at the
        # late threshold the placeholder says how long it has waited and offers Details, whose
        # panel reads this page's records; leaving ends the wait never_completed, a summary
        # that arrives ends it ok and closes the panel, and a failed refresh's Details read the
        # failures around when it ended (mb-9zp5).
        "eventLogDetails": _event_log_details_steps(),
        # The page has no Refresh of its own (mb-ablv): a status line that says what to retry
        # or fetch ends in its remedy, which waits, muted, until the refresh it asked for runs.
        "statusRemedies": [
            'a current record whose last refresh failed: status "Could not reach '
            'GitHub.DetailsRetry"; remedy Retry; note shown; asked nothing; Refresh may '
            "refresh it",
            'Retry pressed, its refresh not yet started: status "Could not reach '
            'GitHub.DetailsRetry"; remedy Retry (waiting); note shown; asked POST '
            '/api/plugin/github/pull-refresh {"number":8,"retry":true}; Refresh has '
            "nothing to refresh",
            'Retry pressed again while it waits: status "Could not reach GitHub.DetailsRetry"; '
            "remedy Retry (waiting); note shown; asked nothing; Refresh has nothing to "
            "refresh",
            "the refresh runs: status none; remedy none; note shown; asked nothing; Refresh "
            "has nothing to refresh",
            'a direct link to a pull request whose fetch failed: status "This pull request has '
            'not been fetched yet.Could not reach GitHub.DetailsFetch"; remedy Fetch; note '
            "none; asked nothing; Refresh may refresh it",
            'Fetch pressed: status "Fetching the pull request…Could not reach GitHub.Details"; '
            "remedy none; note none; asked POST /api/plugin/github/pull-refresh "
            '{"number":7,"retry":true,"wait_core":true}; Refresh has nothing to refresh',
            'a direct link to a copy saved by another version: status "The saved copy of this '
            'pull request is from another version.Fetch"; remedy Fetch; note none; asked '
            "nothing; Refresh may refresh it",
        ],
    }


def _event_log_details_steps() -> list[str]:
    wait = 'githubPull:diffSummary {"number":7} timed from its start'
    late = 'the late line "The summary of changes has not arrived after 10 s. Details"'
    asked = 'Details asked for {"client":"k3v9q2zx"}, abortable true'
    return [
        f"mounted, the comparison not yet read: the pending placeholder; {wait} running",
        f"still waiting at the late threshold: {late}; {wait} running",
        asked,
        "Details opened: expanded true; the panel says "
        '"Still running: checkout._pull_job for 61.0 s"',
        "Details closed: expanded false; panel in the header false",
        asked,
        f"the page left: panel in the header false; expanded false; {wait} ended never_completed",
        f"another page, late: {late}; {wait} running",
        asked,
        f"its comparison read, its Details open: the summary; {wait} ended ok",
        "the late line's Details: expanded false; panel in the header false",
        f"a page whose comparison is read at once: the summary; {wait} ended ok",
        'a failed refresh, ended 2026-09-17T12:30:00Z: "Could not reach GitHub.Details"',
        'Details asked for {"client":"k3v9q2zx","since":"2026-09-17T11:30:00Z",'
        '"until":"2026-09-17T12:31:00Z"}, abortable true',
        'no reporter: "The event log is not available here."',
    ]


def test_idle_comparison_is_route_owned_and_promotes_on_changes() -> None:
    assert run_session("github-pull-idle-comparison-behavior.js") == {
        "withoutStore": [],
        "changesBeforeIdle": ["foreground"],
        "pollWhilePreparing": {"conversation": 30000, "changes": 1000},
        "hiddenUntilVisible": ["idle", "foreground"],
        "afterLateIdleReply": "Changes ready",
        "afterIdleRefusal": ["idle", "foreground"],
        "disposed": [],
    }


def test_file_history_restores_place_and_fresh_selection_wins() -> None:
    """The real route and page distinguish a history landing from a live file jump."""

    assert run_session("github-pull-file-history-behavior.js") == {
        "sameTabBack": 350,
        "conversationBack": 350,
        "freshSelection": 700,
    }


@pytest.mark.parametrize("scenario", ["history", "poll-order", "docs", "docs-offered"])
def test_explicit_repair_preserves_route_and_response_ownership(scenario: str) -> None:
    assert run_session("github-pull-repair-lifecycle-behavior.js", "--case", scenario) == {
        "case": scenario,
        "passed": True,
    }


def test_changes_follows_a_moved_head_in_the_readers_file_and_entry() -> None:
    """The production page joins a followed diff to the reader's place and history entry.

    A mounted page with a history entry and a diff view that answers ``sectionForPath`` and
    ``pathForSection`` from its own sections (A4 of review A on #745): the place names its
    file, the emptied pane's clamp to its top is not written while the newer comparison is
    read (A3), the newer diff keeps the reader's file, a page mounted again on the entry says
    the same note and lands there, the reader's choice of the earlier diff outlives a reload
    (A5), and a file the newer diff lacks lands on a block's top (A8). While a followed diff
    is read, what replaces it keeps the place already kept: a second push, a push on a page
    loaded again on its entry, and **Show the earlier changes** pressed over the read (B1 of
    review B). A move to Docs draws the record's comparison as read now where nothing was
    chosen (C2 of review C), and Docs's entry remembers what it shows as Changes's does, so
    its note and the reader's choice outlast a reload (C1). Through the production page
    host, a walk of the Pulls tab's files and a click on a file land the page on an entry
    with no state, which the page writes its memory into, so the choice outlasts the next
    reload (A1 of review A on #758); Back to an entry the page left gets what the diff
    shows now, its note and choice included (B1 of review B). Both diff tabs say new
    commits are on their way and
    Conversation does not (A2), and Docs asks for a missing comparison by itself only at
    its own address (A3).
    """

    assert run_session("github-pull-changes-follow-behavior.js") == {
        "placeNamesItsFile": True,
        "clampIsNotWritten": True,
        "followKeepsTheFile": True,
        "reloadSaysAndLands": True,
        "choiceSurvivesReload": True,
        "missingFileLandsOnABlockTop": True,
        "secondFollowDuringReadKeepsTheFile": True,
        "followDuringReloadReadKeepsTheFile": True,
        "wayBackDuringReadKeepsTheFile": True,
        "docsDrawsTheRecordsComparison": True,
        "docsRemembersWhatItShows": True,
        "walkAndClickKeepTheChoice": True,
        "backKeepsTheChoice": True,
        "newCommitsOnBothDiffTabs": True,
        "docsAsksForTheComparison": True,
    }


def test_pending_file_selection_belongs_to_one_files_visit() -> None:
    assert run_session("github-pull-pending-file-behavior.js") == {
        "abandonedJump": False,
        "unavailableRetainsSelection": True,
        "replacementRetainsSelection": True,
        "settledWalkJumpsOnce": True,
        "unsettledWalkShowsProgress": True,
    }


def test_description_is_final_at_first_paint_and_on_a_revisit() -> None:
    """Plain text never paints first where a shown text's Markdown can.

    The first paint of a full record waits, within ``DESCRIPTION_HOLD_MS``, for the Markdown
    it asked for, and is not ready meanwhile, so a page it replaces stays on screen. A
    revisit and a refreshed record with the same text paint the render kept for that text,
    keeping the description's node. Past the bound the text paints plain and its Markdown
    follows. The kept renders are bounded by count and by characters. The state badge's
    first paint is the fresher of the cached record and the repository's list. Changes with
    rendered Markdown shows its first screen only once that screen's Markdown is drawn.
    """

    assert run_session("github-pull-first-paint-behavior.js") == {
        "firstVisit": "held, then final",
        "refreshedSameText": "kept",
        "revisit": "final at first paint",
        "pastTheBound": "a placeholder, then Markdown",
        # The comments and reviews the first screen shows wait with the description, so none is
        # plain at the paint that makes the page ready (review A6).
        "comments": {"texts": 5, "asked": 5, "plainAtReady": 0},
        # Each hold's span says how it ended (review B1).
        "holdSpans": ["hidden met 1", "hidden bound 1"],
        # A direct landing's loading blocks give way to the held conversation (review B5).
        # The header paints the record at once and only the body waits (exp-099), which
        # reverses review D1's change-once for the header.
        "landing": {
            "blocksBefore": True,
            "whileHeld": {
                "holding": True,
                "blocks": False,
                "heading": "Count to two in the app #7",
            },
            "final": True,
            "heading": "Count to two in the app #7",
        },
        # Blocks that had shown stay, the same node, over the held conversation until it shows,
        # so the body never blinks empty between them (review C2).
        "landingAfterBlocksShowed": {
            "whileHeld": {
                "holding": True,
                "sameBlocks": True,
                "cover": True,
                "heading": "Count to two in the app #7",
            },
            "shown": {
                "blocks": False,
                "holding": False,
                "final": True,
                "heading": "Count to two in the app #7",
            },
        },
        # A page replaced during its hold stays out of sight; it never shows plain (review C7).
        "cancelledWhileHeld": {"holding": True},
        # The first screen is the page's own, from its top, whether the page it replaces is at
        # its top or scrolled past the conversation; a text that comes into it as those above
        # render is waited for too (review C1). Before, the second comment, or the first, was
        # plain at ready.
        "firstScreen": {
            **{
                scrolled: {
                    "plainOnFirstScreenAtReady": [],
                    "waitedFor": 3,
                    "outcome": "met",
                    "askedBeforeSecondAnswer": 3,
                }
                for scrolled in ("0", "5000")
            },
            # A text past the screen that fails leaves the hold met (review D4); before, it
            # was unavailable.
            "failsPastTheScreen": {
                "plainOnFirstScreenAtReady": [],
                "waitedFor": 2,
                "outcome": "met",
                "askedBeforeSecondAnswer": 4,
            },
            # Texts asked ahead of the screen take the cascade in 4 round trips, 6 before
            # (review D2).
            "cascade": {
                "plainOnFirstScreenAtReady": [],
                "waitedFor": 6,
                "outcome": "met",
                "rounds": 4,
            },
        },
        # The record that follows a core preview asks for its comments in view as it paints,
        # each a placeholder at that paint and never its source (review A5 on #589); before,
        # the observer asked after the frame, which showed them as source.
        "recordAfterCore": {"commentsInView": 4, "pendingAtPaint": True},
        # Kept cards tell their ages as of the paint, not as of when they were built (review A5).
        "ages": ["186 min", "185 min", "4 min"],
        # A stale record paints the list's state when the list saw a later update.
        "listedState": {"newerList": "Merged", "olderList": "Open"},
        # Changes with rendered Markdown is out of sight, and not ready, until its first
        # screen's Markdown settles or CHANGES_FIRST_SCREEN_MS passes.
        "changes": {
            # The file the address names is landed on while the diff is still held (review B2).
            ending: {
                "asked": 200,
                "held": True,
                "readyWhileHeld": False,
                "shown": True,
                "ready": True,
                "holdingAtJump": True,
            }
            for ending in ("settled", "bound")
        }
        # A page that goes while its diff waits keeps it out of sight and records the wait as
        # cancelled (review E1); before, the diff was shown and the wait recorded as met.
        | {"cancelled": {"held": True, "keptOutOfSight": True, "outcome": "cancelled"}},
        "bounded": True,
        # The header does not wait with the held body (exp-099), so all four tab keys, the
        # stack menu, and the stack keys are live while it waits, as at release (review E2).
        "tabKeysWhileHeld": {
            "whileHeld": {
                "holding": True,
                "tabColumn": "live",
                "live": ["conversation", "docs", "files", "checks"],
                "badges": "Conversation C, Docs D, Changes G, Checks E",
                "g": "opened the files route",
                "stackMenus": 1,
                "stackKeys": "pulls.stack.top, pulls.stack.base",
                "strip": "pulls.stack.top, pulls.stack.base",
                "control-n": "opened #8",
            },
            "released": {
                "holding": False,
                "tabColumn": "live",
                "live": ["conversation", "docs", "files", "checks"],
                "badges": "Conversation C, Docs D, Changes G, Checks E",
                # Nothing went inert, so focus never left the Changes link to be given back.
                "focus": "none",
                "g": "opened the files route",
                "stackMenus": 1,
                "stackKeys": "pulls.stack.top, pulls.stack.base",
                "strip": "pulls.stack.top, pulls.stack.base",
                # Control-N and Control-P walk the stack (mb-lnqj); plain N is free.
                "n": "not handled",
                "control-n": "opened #8",
                "control-p": "opened #6",
            },
        },
    }


def test_selected_core_preview_waits_for_description_and_keeps_parts_pending() -> None:
    """A cold selected page retains prior content until its honest core is ready."""

    assert run_session("github-pull-core-preview-behavior.js") == {
        "description": "rendered preview before full conversation",
        "pendingParts": ["discussion", "checks"],
        "checkResults": {"route": "/pull/7/checks", "links": 2, "empty": True, "pending": True},
        "waitCorePost": {"number": 7, "retry": True, "wait_core": True},
        "previewMarkdownRequests": 1,
        "fullMarkdownRequests": 1,
        "fullRecordWins": True,
        "crossOwnerRetirement": True,
        "stagedReplacement": "A retained through B cancellation until C commits",
    }
