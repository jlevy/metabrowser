"""The pull-request page session runs production browser code on what a served PR answers.

``tests/dom/github-pull-page-session.js`` drives the GitHub plugin's
``builtin_plugins/github/pull-page.js`` -- what the page shows, its polling, the refresh a
stale page offers, its tabs, and the Markdown it asks for part by part -- through a
scripted conversation, and ``tests/golden/cli-ui-github-pull-page.tryscript.md`` pins its
transcript. So that the conversation is the real server's and not envelopes a test
wrote by hand, its responses come from ``tests/fixtures/github-pull-page-responses.json``:
what the in-process application answered while it served pull request 7 of
``tests/github_pull_fixture.py``'s stand-in, with a fake ``gh`` replaying scrubbed real
responses. The page opened with nothing cached, fetched the record, read its Markdown,
went stale, and refreshed to a record with one more comment. The first test here replays
that story and fails when the recording no longer matches.

The clock is fixed, so fetch times are literal. Only the Markdown is cut down to the
rendered text: KPress's icon sprite and asset manifest are KPress's contract, pinned by
its own render goldens, and would tie this recording to its version.

Regenerate the recording after an intended change, then the transcript:

    GOLDEN_UPDATE=1 uv --config-file uv.toml run --frozen pytest tests/test_github_pull_page_session.py
    npx --no-install tryscript run --update tests/golden/cli-ui-github-pull-page.tryscript.md
"""

from __future__ import annotations

import asyncio
import copy
import json
import os
import re
import shutil
import subprocess
import threading
import time
from dataclasses import replace
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

import pytest
from starlette.testclient import TestClient

from metabrowser.builtin_plugins.github import pulls
from metabrowser.builtin_plugins.github.served_pull import ServedPull, served_pull
from metabrowser.cache.acquire import acquire_source
from metabrowser.cache.pull_refs import fetch_pull_head
from metabrowser.cache.repository_store import open_revision
from metabrowser.cache.served_mirror import StoreMirror
from metabrowser.cache.urls import GitSource, RepositorySelection
from metabrowser.git import repo as git_repo
from metabrowser.git.tree_source import GitRevisionSubject
from metabrowser.mirror_refresh import mirror_session, serve_mirror
from metabrowser.server import app
from metabrowser.source import attach_subject, reset_source_session
from tests.github_pull_fixture import (
    CANONICAL,
    FETCHED_AT,
    build_origin,
    install_fake_gh,
    ok,
    page,
    scenario,
)
from tests.test_cache_acquire import _allow_installed_git

REPO_ROOT = Path(__file__).resolve().parent.parent
SESSION_JS = REPO_ROOT / "tests" / "dom" / "github-pull-page-session.js"
FIXTURE = REPO_ROOT / "tests" / "fixtures" / "github-pull-page-responses.json"

_JSON = {"content-type": "application/json"}
_PULL = "/api/plugin/github/pull"
_REFRESH = "/api/plugin/github/pull-refresh"
_MARKDOWN = "/api/plugin/github/pull-markdown"
_PROSE = re.compile(r'<div class="kpress-prose[^"]*">(.*)</div></div></article>', re.S)

pytestmark = [
    pytest.mark.skipif(shutil.which("git") is None, reason="git executable is required"),
    pytest.mark.skipif(os.name != "posix", reason="the fake gh is a POSIX script"),
]


def _answer(response: Any) -> dict[str, Any]:
    """One response as the page sees it: status, entity tag, and body."""

    body = None if response.status_code == 304 else response.json()
    return {"status": response.status_code, "etag": response.headers.get("etag"), "body": body}


def _markdown(response: Any) -> dict[str, Any]:
    answer = _answer(response)
    body = answer["body"]
    match = _PROSE.search(body["html"])
    assert match is not None, "KPress no longer wraps rendered text in kpress-prose"
    answer["body"] = {
        "number": body["number"],
        "fetched_at": body["fetched_at"],
        "part": body["part"],
        "html": match.group(1),
    }
    return answer


def _settle(client: TestClient) -> None:
    deadline = time.monotonic() + 60
    while client.get("/api/source/status").json()["refreshing"]:
        assert time.monotonic() < deadline, "the refresh did not finish"
        time.sleep(0.02)


def _record(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> dict[str, Any]:
    home = tmp_path / "home"
    monkeypatch.setenv("METABROWSER_HOME", str(home))
    _allow_installed_git(monkeypatch)
    origin = build_origin(tmp_path)
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
    # The head arrives as the CLI brings it, through GitHub's own ref; no record yet.
    assert asyncio.run(fetch_pull_head(published, 7)) == origin["fork_head"]

    async def _pin() -> GitRevisionSubject:
        subject = await open_revision(
            home=published.home,
            store_key=published.store_key,
            commit_oid=origin["fork_head"],
            store_identity=published.store_id,
            ref="refs/pull/7/head",
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
            recorded["absent_unchanged"] = _answer(
                client.get(_PULL, headers={"if-none-match": recorded["absent"]["etag"]})
            )
            recorded["refresh_started"] = _answer(client.post(_REFRESH, json={}, headers=_JSON))
            recorded["pending"] = _answer(client.get(_PULL))
            release.set()
            _settle(client)
            recorded["current"] = _answer(client.get(_PULL))
            record = recorded["current"]["body"]["record"]
            for part in (
                "body",
                f"issue_comment/{record['issue_comments'][0]['id']}",
                f"review/{record['reviews'][1]['id']}",
                f"review_comment/{record['review_comments'][0]['id']}",
            ):
                recorded[f"markdown {part.split('/')[0]}"] = _markdown(
                    client.get(_MARKDOWN, params={"part": part})
                )
            recorded["markdown missing"] = _answer(
                client.get(_MARKDOWN, params={"part": "issue_comment/1"})
            )

            # Five minutes on, the record is stale; a refresh reads one more comment.
            clock[0] = FETCHED_AT + timedelta(minutes=5)
            recorded["stale"] = _answer(client.get(_PULL))
            comments_path = page("repos/octo/demo/issues/7/comments")
            comments = copy.deepcopy(answers["api"][comments_path]["body"])
            added = {
                **comments[0],
                "id": comments[0]["id"] + 1,
                "user": {"login": "forker"},
                "body": "Rebased on `topic`; see [the docs](docs/new.md).",
                "created_at": "2026-09-17T12:03:00Z",
                "updated_at": "2026-09-17T12:03:00Z",
            }
            answers["api"][comments_path] = ok(comments_path, [*comments, added])
            for name, value in install_fake_gh(tmp_path, answers).items():
                monkeypatch.setenv(name, value)
            release.clear()
            recorded["refresh_again"] = _answer(client.post(_REFRESH, json={}, headers=_JSON))
            recorded["stale_refreshing"] = _answer(client.get(_PULL))
            release.set()
            _settle(client)
            recorded["refreshed"] = _answer(client.get(_PULL))
            recorded["markdown added"] = _markdown(
                client.get(_MARKDOWN, params={"part": f"issue_comment/{added['id']}"})
            )
    finally:
        serve_mirror(None)
        reset_source_session()
        git_repo.clear_repo_cache()
    return recorded


def test_recording_is_what_a_served_pull_request_answers(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    recorded = _record(tmp_path, monkeypatch)
    assert (recorded["absent"]["body"]["state"], recorded["absent"]["body"]["reason"]) == (
        "absent",
        "not_cached",
    )
    assert recorded["absent_unchanged"]["status"] == 304
    assert recorded["refresh_started"]["body"]["pull"]["state"] == "pending"
    assert recorded["pending"]["body"]["refreshing"] is True
    assert recorded["current"]["body"]["state"] == "current"
    assert "<strong>two</strong>" in recorded["markdown body"]["body"]["html"]
    assert recorded["markdown missing"]["status"] == 404
    assert recorded["stale"]["body"]["state"] == "stale"
    assert recorded["stale_refreshing"]["body"]["refreshing"] is True
    refreshed = recorded["refreshed"]["body"]
    assert refreshed["state"] == "current"
    assert len(refreshed["record"]["issue_comments"]) == 2
    assert datetime.fromisoformat(refreshed["fetched_at"]) > FETCHED_AT
    rendered = json.dumps(recorded, indent=2, ensure_ascii=False) + "\n"
    if os.environ.get("GOLDEN_UPDATE") == "1":
        FIXTURE.write_text(rendered, encoding="utf-8")
        return
    assert FIXTURE.read_text(encoding="utf-8") == rendered, (
        "a served pull request answers differently now; regenerate with GOLDEN_UPDATE=1 "
        "and update tests/golden/cli-ui-github-pull-page.tryscript.md"
    )


def test_the_session_runs_on_the_recording() -> None:
    if shutil.which("node") is None:
        pytest.skip("node not available")
    result = subprocess.run(
        ["node", str(SESSION_JS)], capture_output=True, text=True, timeout=60, check=False
    )
    assert result.returncode == 0, f"stdout: {result.stdout!r}\nstderr: {result.stderr!r}"
    steps = {step["step"]: step for step in json.loads(result.stdout)["steps"]}
    assert steps["open with nothing cached"]["paint"]["canRefresh"] is True
    assert steps["the record arrives"]["paint"]["status"] == "current"
    assert steps["an unchanged answer is a 304"]["paints"] == 0
    refreshed = steps["the refresh brought another comment"]["paint"]
    assert [item.split(" ")[0] for item in refreshed["timeline"]][-1] == "comment"
    assert steps["a render of the older record is dropped"]["markdown"] == []
