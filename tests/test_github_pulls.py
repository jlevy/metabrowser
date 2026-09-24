"""Pull-request records: the gh runner, the account check, refresh, bounds, and reads.

Everything runs against ``tests/github_pull_fixture.py``: a ``file://`` origin with
GitHub's ``refs/pull/<n>/head`` standing in for ``https://github.com/octo/demo``, and a
fake ``gh`` replaying scrubbed real responses. Nothing reaches the network or the
``gh`` a developer has signed in.
"""

from __future__ import annotations

import asyncio
import json
import os
import shutil
import subprocess
import threading
import time
from collections.abc import Iterator
from dataclasses import dataclass, replace
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any
from unittest.mock import patch

import pytest
from starlette.testclient import TestClient
from typer.testing import CliRunner

from metabrowser.builtin_plugins.github import pulls
from metabrowser.builtin_plugins.github.gh import (
    GhError,
    GhResponse,
    gh_account,
    gh_api,
    parse_account,
    parse_included_response,
    rate_limit_reset,
)
from metabrowser.builtin_plugins.github.pull_record import (
    MAX_BODY_BYTES,
    MAX_DIFF_HUNK_BYTES,
    PullRecord,
    apply_text_budget,
    cut_text,
    escaped_size,
    read_pull_record,
    serialize_pull_record,
    write_pull_record,
)
from metabrowser.builtin_plugins.github.pull_route import pull_state
from metabrowser.builtin_plugins.github.pulls import PullDataError, open_pull_request
from metabrowser.builtin_plugins.github.served_pull import ServedPull, served_pull
from metabrowser.cache import pull_refs
from metabrowser.cache.acquire import PublishedSource, acquire_source
from metabrowser.cache.layout import open_cache
from metabrowser.cache.locks import LockBusyError, store_fetch_lock
from metabrowser.cache.paths import source_pull_record
from metabrowser.cache.pull_refs import ref_commit
from metabrowser.cache.repository_store import open_revision
from metabrowser.cache.resolve import resolve_pin
from metabrowser.cache.served_mirror import StoreMirror
from metabrowser.cache.urls import GitSource, RepositorySelection
from metabrowser.cli.main import _app
from metabrowser.git import repo as git_repo
from metabrowser.git.process import repository_store_target
from metabrowser.git.tree_source import GitRevisionSubject
from metabrowser.mirror_refresh import (
    FRESHNESS_WINDOW_S,
    InvalidSelectionError,
    mirror_session,
    serve_mirror,
)
from metabrowser.server import app
from metabrowser.source import attach_subject, reset_source_session
from metabrowser.source_routes import PIN_HEADER
from tests.git_pin_harness import git_env
from tests.github_pull_fixture import (
    CANONICAL,
    FETCHED_AT,
    READER,
    Origin,
    account,
    build_origin,
    install_fake_gh,
    ok,
    page,
    scenario,
)
from tests.test_cache_acquire import _allow_installed_git

pytestmark = [
    pytest.mark.skipif(shutil.which("git") is None, reason="git executable is required"),
    pytest.mark.skipif(os.name != "posix", reason="the fake gh is a POSIX script"),
]

SOURCE = GitSource(transport="https", form="url", normalized=CANONICAL)


@dataclass
class _Stand:
    origin: Origin
    published: PublishedSource
    tmp_path: Path
    monkeypatch: pytest.MonkeyPatch

    def answer(self, answers: dict[str, Any]) -> None:
        for name, value in install_fake_gh(self.tmp_path, answers).items():
            self.monkeypatch.setenv(name, value)

    def calls(self) -> list[dict[str, Any]]:
        log = self.tmp_path / "fake-gh-log.jsonl"
        if not log.exists():
            return []
        entries = [json.loads(line) for line in log.read_text(encoding="utf-8").splitlines()]
        log.unlink()
        return entries

    def refresh(self, number: int) -> PullRecord:
        return asyncio.run(pulls.refresh_pull_request(self.published, number))

    def record(self, number: int) -> PullRecord | str:
        return read_pull_record(self.published.home, self.published.slug, number)


@pytest.fixture
def stand(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> _Stand:
    home = tmp_path / "home"
    monkeypatch.setenv("METABROWSER_HOME", str(home))
    _allow_installed_git(monkeypatch)
    origin = build_origin(tmp_path)
    local = origin.url
    monkeypatch.setattr(
        "metabrowser.cache.acquire.remote_url_for",
        lambda source: local if source.normalized == CANONICAL else source.normalized,  # pyright: ignore[reportUnknownLambdaType, reportUnknownMemberType]
    )
    monkeypatch.setattr(pulls, "utc_now", lambda: FETCHED_AT)
    stand = _Stand(origin, None, tmp_path, monkeypatch)  # pyright: ignore[reportArgumentType]
    stand.answer(scenario(origin))
    stand.published = asyncio.run(acquire_source(SOURCE, home=home))
    stand.calls()
    return stand


def _api(answers: dict[str, Any], path: str, entry: Any) -> dict[str, Any]:
    return {**answers, "api": {**answers["api"], path: entry}}


# ── gh runner ──────────────────────────────────────────────────


def test_included_response_is_split_as_gh_prints_it() -> None:
    # gh 2.98.0 ends the status line with LF and each header with CRLF.
    raw = b'HTTP/2.0 200 OK\nEtag: W/"abc"\r\nLink: <x>; rel="next"\r\n\r\n{"a": 1}'
    response = parse_included_response(raw)
    assert response is not None
    assert (response.status, response.etag, response.has_next_page) == (200, 'W/"abc"', True)
    assert response.json() == {"a": 1}
    not_modified = parse_included_response(b'HTTP/2.0 304 Not Modified\nEtag: "abc"\r\n\r\n')
    assert not_modified is not None and (not_modified.status, not_modified.body) == (304, b"")
    assert parse_included_response(b"error connecting to api.github.com\n") is None


def test_rate_limit_reset_reads_retry_after_then_the_primary_reset() -> None:
    now = datetime(2026, 9, 17, 12, 0, tzinfo=UTC)
    exhausted = GhResponse(
        403, {"x-ratelimit-remaining": "0", "x-ratelimit-reset": "1790181960"}, b"{}"
    )
    assert rate_limit_reset(exhausted, now=now) == "2026-09-23T16:46:00Z"
    secondary = GhResponse(403, {"retry-after": "60", "x-ratelimit-remaining": "0"}, b"{}")
    assert rate_limit_reset(secondary, now=now) == "2026-09-17T12:01:00Z"
    assert (
        rate_limit_reset(GhResponse(403, {"x-ratelimit-remaining": "12"}, b"{}"), now=now) is None
    )
    assert rate_limit_reset(GhResponse(429, {}, b"{}"), now=now) == "unknown"


def test_gh_api_runs_isolated_with_fixed_arguments(
    stand: _Stand, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("GH_DEBUG", "api")
    monkeypatch.setenv("GH_HOST", "enterprise.example.com")
    monkeypatch.setenv("GH_REPO", "other/repo")
    # Common in dotfiles: either makes gh colorize --include headers and JSON.
    monkeypatch.setenv("CLICOLOR_FORCE", "1")
    monkeypatch.setenv("GH_FORCE_TTY", "1")
    response = asyncio.run(gh_api("repos/octo/demo/pulls/7", etag='W/"x"'))
    assert response.status == 200
    (call,) = stand.calls()
    assert call["args"] == [
        "api",
        "--hostname",
        "github.com",
        "--method",
        "GET",
        "--include",
        "-H",
        "X-GitHub-Api-Version: 2022-11-28",
        "-H",
        'If-None-Match: W/"x"',
        "repos/octo/demo/pulls/7",
    ]
    assert call["stdin_null"] is True
    assert call["env"] == {
        "GH_PROMPT_DISABLED": "1",
        "GH_NO_UPDATE_NOTIFIER": "1",
        "NO_COLOR": "1",
        "GH_DEBUG": None,
        "GH_HOST": None,
        "GH_REPO": None,
        "GH_FORCE_TTY": None,
        "CLICOLOR_FORCE": None,
    }


@pytest.mark.parametrize(
    "path", ["../repos/x", "repos/octo/../demo", "repos/octo/demo --paginate", "-X"]
)
def test_gh_api_refuses_a_path_it_did_not_build(path: str) -> None:
    with pytest.raises(ValueError, match="not a repository API path"):
        asyncio.run(gh_api(path))


def test_gh_api_returns_304_and_types_refusals(stand: _Stand) -> None:
    entry = scenario(stand.origin)["api"]["repos/octo/demo/pulls/7"]
    unchanged = asyncio.run(gh_api("repos/octo/demo/pulls/7", etag=entry["headers"]["Etag"]))
    assert (unchanged.status, unchanged.body) == (304, b"")
    with pytest.raises(GhError) as missing:
        asyncio.run(gh_api("repos/octo/demo/pulls/404"))
    assert missing.value.state == "not_found_or_private"
    stand.answer(
        {
            **scenario(stand.origin),
            "api_failure": {
                "stderr": "To get started with GitHub CLI, please run:  gh auth login\n",
                "exit": 4,
            },
        }
    )
    with pytest.raises(GhError) as logged_out:
        asyncio.run(gh_api("repos/octo/demo/pulls/7"))
    assert logged_out.value.state == "not_logged_in"


def test_account_is_the_active_login_even_in_an_error_state() -> None:
    assert parse_account(account("octo", state="error")["stdout"].encode()) == "octo"
    assert parse_account(b'{"hosts":{}}') is None
    inactive = {"hosts": {"github.com": [{"active": False, "login": "other", "state": "success"}]}}
    assert parse_account(json.dumps(inactive).encode()) is None
    with pytest.raises(GhError):
        parse_account(b'{"hosts":{"github.com":[{"active":true,"login":"bad login"}]}}')


def test_account_states(stand: _Stand, monkeypatch: pytest.MonkeyPatch) -> None:
    assert asyncio.run(gh_account()) == READER
    stand.answer({**scenario(stand.origin), "auth": {"stdout": '{"hosts":{}}\n'}})
    with pytest.raises(GhError) as logged_out:
        asyncio.run(gh_account())
    assert logged_out.value.state == "not_logged_in"
    stand.answer(
        {**scenario(stand.origin), "auth": {"stderr": "unknown flag: --json\n", "exit": 1}}
    )
    with pytest.raises(GhError) as old:
        asyncio.run(gh_account())
    assert old.value.state == "gh_too_old"
    monkeypatch.setattr("metabrowser.builtin_plugins.github.gh.gh_executable", lambda: None)
    with pytest.raises(GhError) as missing:
        asyncio.run(gh_account())
    assert missing.value.state == "gh_missing"


# ── refresh ────────────────────────────────────────────────────


def test_a_fork_pull_request_brings_its_commits_and_the_mirror_base(stand: _Stand) -> None:
    record = stand.refresh(7)
    origin = stand.origin
    assert record.reader == f"gh:{READER}"
    assert record.pull.head.repository == "forker/demo"
    assert asyncio.run(ref_commit(stand.published, "refs/pull/7/head")) == origin["fork_head"]
    assert record.comparison is not None
    assert (record.comparison.base, record.comparison.base_from) == (origin["base"], "base_branch")
    assert record.comparison.base_commit == origin["topic"]
    assert stand.record(7) == record


def test_merged_and_closed_pull_requests_compare_from_base_sha(stand: _Stand) -> None:
    origin = stand.origin
    merged = stand.refresh(8)
    assert merged.pull.merged and merged.pull.mergeable == "unknown"
    assert merged.comparison is not None
    assert (merged.comparison.base_commit, merged.comparison.base_from) == (
        origin["topic_before_merge"],
        "base_sha",
    )
    # 9's base.sha is on no mirrored ref, so it is fetched by ID first.
    closed = stand.refresh(9)
    assert closed.pull.head.repository is None and closed.pull.author is None
    assert closed.comparison is not None
    assert closed.comparison.base_commit == origin["rewritten_base"]
    assert closed.comparison.base == origin["base"]
    draft = stand.refresh(10)
    assert draft.pull.draft and draft.pull.mergeable == "conflicting"
    assert draft.comparison is not None and draft.comparison.base == origin["topic"]


def test_a_second_refresh_is_conditional_and_reuses_unchanged_parts(stand: _Stand) -> None:
    first = stand.refresh(7)
    stand.calls()
    again = stand.refresh(7)
    api_calls = [call["args"] for call in stand.calls() if call["args"][0] == "api"]
    assert len(api_calls) == 6
    assert all(any(arg.startswith("If-None-Match: ") for arg in args) for args in api_calls)
    assert again.model_dump(exclude={"fetched_at"}) == first.model_dump(exclude={"fetched_at"})


def test_etags_are_not_sent_for_another_reader(stand: _Stand) -> None:
    stand.refresh(7)
    stand.answer({**scenario(stand.origin), "auth": account("someone-else")})
    stand.calls()
    record = stand.refresh(7)
    assert record.reader == "gh:someone-else"
    sent = [call["args"] for call in stand.calls() if call["args"][0] == "api"]
    assert not any(arg.startswith("If-None-Match: ") for args in sent for arg in args)


def test_a_record_read_while_the_account_changed_is_discarded(stand: _Stand) -> None:
    stand.answer({**scenario(stand.origin), "auth": [account(READER), account("someone-else")]})
    with pytest.raises(PullDataError) as changed:
        stand.refresh(7)
    assert changed.value.state == "account_changed"
    assert stand.record(7) == "not_cached"


def test_a_head_that_moved_once_is_read_again(stand: _Stand) -> None:
    answers = scenario(stand.origin)
    path = "repos/octo/demo/pulls/7"
    body = answers["api"][path]["body"]
    earlier = stand.origin["fork_earlier"]
    stale = ok(path, {**body, "head": {**body["head"], "sha": earlier}})
    answers = _api(answers, path, [stale, answers["api"][path]])
    for part, empty in (
        ("check-runs", {"total_count": 0, "check_runs": []}),
        ("status", {"state": "pending", "statuses": []}),
    ):
        listed = page(f"repos/octo/demo/commits/{earlier}/{part}")
        answers = _api(answers, listed, ok(listed, empty))
    stand.answer(answers)
    record = stand.refresh(7)
    assert record.pull.head.sha == stand.origin["fork_head"]
    reads = [call for call in stand.calls() if call["args"][-1] == path]
    assert len(reads) == 2


def test_pages_follow_link_and_stop_at_the_cap(
    stand: _Stand, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(pulls, "MAX_ISSUE_COMMENTS", 150)
    answers = scenario(stand.origin)
    base = "repos/octo/demo/issues/7/comments"
    template = answers["api"][page(base)]["body"][0]

    def comments(start: int, count: int) -> list[dict[str, Any]]:
        return [{**template, "id": start + index} for index in range(count)]

    def listed(number: int, count: int, *, more: bool) -> dict[str, Any]:
        path = f"{base}?per_page=100&page={number}"
        link = (
            {"Link": f'<https://api.github.com/{base}?page={number + 1}>; rel="next"'}
            if more
            else {}
        )
        return ok(path, comments(number * 1000, count), link)

    answers = _api(answers, page(base), listed(1, 100, more=True))
    answers = _api(answers, f"{base}?per_page=100&page=2", listed(2, 100, more=True))
    record = pulls.refresh_pull_request
    stand.answer(answers)
    cut = asyncio.run(record(stand.published, 7))
    assert len(cut.issue_comments) == 150 and cut.truncated.issue_comments
    pages_read = [call["args"][-1] for call in stand.calls() if base in call["args"][-1]]
    assert pages_read == [page(base), f"{base}?per_page=100&page=2"]


def test_bodies_and_hunks_are_cut_and_say_so(stand: _Stand) -> None:
    answers = scenario(stand.origin)
    path = "repos/octo/demo/pulls/7"
    long_body = "é" * MAX_BODY_BYTES
    answers = _api(answers, path, ok(path, {**answers["api"][path]["body"], "body": long_body}))
    comments = page("repos/octo/demo/pulls/7/comments")
    hunk = "@@ -1 +1 @@\n" + "\n".join(f"+line {index}" for index in range(4000))
    listed = [{**answers["api"][comments]["body"][0], "diff_hunk": hunk}]
    answers = _api(answers, comments, ok(comments, listed))
    stand.answer(answers)
    record = stand.refresh(7)
    assert record.pull.body_truncated and len(record.pull.body.encode()) <= MAX_BODY_BYTES
    kept = record.review_comments[0]
    assert kept.diff_hunk_truncated and kept.diff_hunk.endswith("+line 3999")
    assert (
        kept.diff_hunk.startswith("+line ") and len(kept.diff_hunk.encode()) <= MAX_DIFF_HUNK_BYTES
    )


def test_the_text_budget_cuts_later_text_first(stand: _Stand) -> None:
    record = stand.refresh(7)
    budget = escaped_size(record.pull.body) + 10
    cut = apply_text_budget(record, budget)
    assert cut.truncated.text and not cut.pull.body_truncated
    assert cut.issue_comments[0].body_truncated
    assert len(cut.issue_comments[0].body.encode()) == 10
    assert all(comment.body == "" for comment in cut.review_comments)
    assert apply_text_budget(record) == record


def test_cut_text_respects_characters() -> None:
    assert cut_text("aé", 2) == ("a", True)
    assert cut_text("one\ntwo\nthree", 7, keep="tail") == ("three", True)
    assert cut_text("short", 10) == ("short", False)


# ── records on disk ────────────────────────────────────────────


def test_a_record_from_another_schema_or_damaged_is_refetched(stand: _Stand) -> None:
    record = stand.refresh(7)
    path = stand.published.home / source_pull_record(stand.published.slug, 7)
    payload = json.loads(path.read_bytes())
    path.write_text(json.dumps({**payload, "schema_version": 0}), encoding="utf-8")
    assert stand.record(7) == "schema_mismatch"
    path.write_text("{not json", encoding="utf-8")
    assert stand.record(7) == "unreadable"
    path.write_text(json.dumps({**payload, "reader": "anonymous"}), encoding="utf-8")
    assert stand.record(7) == "unreadable"
    path.write_text(json.dumps({**payload, "number": 8}), encoding="utf-8")
    assert stand.record(7) == "unreadable"
    stand.calls()
    pin = asyncio.run(open_pull_request(stand.published, 7, fetch="if_missing"))
    assert pin.head == record.pull.head.sha
    assert any(call["args"][0] == "api" for call in stand.calls())
    assert stand.record(7) == record


def test_a_cached_record_is_read_without_gh(stand: _Stand, monkeypatch: pytest.MonkeyPatch) -> None:
    stand.refresh(7)
    stand.calls()
    monkeypatch.setattr("metabrowser.builtin_plugins.github.gh.gh_executable", lambda: None)
    pin = asyncio.run(open_pull_request(stand.published, 7, fetch="if_missing"))
    assert pin.summary == f"open; fetched 2026-09-17T12:00:00Z by gh:{READER}"
    assert stand.calls() == []
    # A failed refresh beside a usable record answers from it and says why.
    kept = asyncio.run(open_pull_request(stand.published, 7, fetch="always"))
    assert kept.head == pin.head
    assert kept.summary.endswith(
        "; the refresh failed: GitHub CLI (gh) is not on PATH (gh_missing)"
    )
    # With no record to answer from, the failure is raised.
    (stand.published.home / source_pull_record(stand.published.slug, 7)).unlink()
    with pytest.raises(PullDataError) as refused:
        asyncio.run(open_pull_request(stand.published, 7, fetch="if_missing"))
    assert refused.value.state == "gh_missing"


def test_serialization_validates_and_bounds(stand: _Stand, monkeypatch: pytest.MonkeyPatch) -> None:
    record = stand.refresh(7)
    assert json.loads(serialize_pull_record(record))["number"] == 7
    monkeypatch.setattr("metabrowser.builtin_plugins.github.pull_record.MAX_PULL_RECORD_BYTES", 100)
    with pytest.raises(Exception, match="would be"):
        write_pull_record(stand.published.home, stand.published.slug, record)


def test_the_startup_sweep_leaves_records_alone(stand: _Stand) -> None:
    record = stand.refresh(7)
    open_cache(stand.published.home)
    assert stand.record(7) == record


# ── route state ────────────────────────────────────────────────


def test_route_states_follow_age_and_refresh(stand: _Stand) -> None:
    record = stand.refresh(7)
    fresh = FETCHED_AT + timedelta(seconds=FRESHNESS_WINDOW_S)
    assert pull_state(record, now=fresh) == ("current", None)
    assert pull_state(record, now=fresh + timedelta(seconds=1)) == ("stale", None)
    assert pull_state("not_cached", now=fresh) == ("absent", "not_cached")
    assert pull_state("not_cached", now=fresh, refreshing=True) == ("pending", None)


# ── routes on a pinned pull request ────────────────────────────


@pytest.fixture
def pinned_pull(stand: _Stand) -> Iterator[tuple[_Stand, TestClient]]:
    """Pull request 7 cached, its head pinned, and served beside the mirror as the CLI does."""

    stand.refresh(7)
    selected = replace(SOURCE, selection=RepositorySelection(kind="pull_request", pull_request=7))
    published = replace(stand.published, source=selected)

    async def _pin() -> GitRevisionSubject:
        subject = await open_revision(
            home=published.home,
            store_key=published.store_key,
            commit_oid=stand.origin["fork_head"],
            store_identity=published.store_id,
            ref="refs/pull/7/head",
        )
        await subject.aclose()
        return subject

    attach_subject(asyncio.run(_pin()))
    serve_mirror(
        StoreMirror.from_published(published),
        pull_request=7,
        companion=served_pull(published, 7),
    )
    git_repo.clear_repo_cache()
    try:
        with TestClient(app) as client:
            yield stand, client
    finally:
        serve_mirror(None)
        reset_source_session()
        git_repo.clear_repo_cache()


def _changed(body: dict[str, Any]) -> set[str]:
    return {
        (change.get("new") or change.get("old"))["path"] for change in body["manifest"]["files"]
    }


def test_the_pull_route_and_the_comparison_it_names(
    pinned_pull: tuple[_Stand, TestClient],
) -> None:
    stand, client = pinned_pull
    origin = stand.origin
    envelope = client.get("/api/plugin/github/pull").json()
    assert (envelope["state"], envelope["number"], envelope["pin"]) == (
        "current",
        7,
        origin["fork_head"],
    )
    assert envelope["record"]["reader"] == f"gh:{READER}"
    comparison = client.get(envelope["comparison_route"])
    assert comparison.status_code == 200
    body = comparison.json()
    assert body["resolved"]["base_policy"] == "merge_base"
    assert body["resolved"]["left"]["id"] == origin["base"]
    assert _changed(body) == {"docs/new.md", "src/app.txt"}
    # Merge base, not direct: the base branch's own README change is not the PR's.
    direct = client.get(
        "/api/plugin/diff/comparison",
        params={"left": origin["topic"], "right": origin["fork_head"]},
    ).json()
    assert direct["resolved"]["base_policy"] == "direct"
    assert "README.md" in _changed(direct)
    by_merge_base = client.get(
        "/api/plugin/diff/comparison",
        params={"left": origin["topic"], "right": origin["fork_head"], "base_policy": "merge_base"},
    ).json()
    assert by_merge_base["resolved"]["left"]["id"] == origin["base"]
    assert _changed(by_merge_base) == {"docs/new.md", "src/app.txt"}


@pytest.mark.parametrize(
    "params",
    [
        {"left": "HEAD", "right": "HEAD", "base_policy": "first_parent"},
        {"left": "HEAD", "right": "HEAD", "base_policy": "sideways"},
        {"revision": "HEAD", "base_policy": "merge_base"},
    ],
)
def test_the_comparison_route_refuses_a_base_policy_it_cannot_honor(
    pinned_pull: tuple[_Stand, TestClient], params: dict[str, str]
) -> None:
    _stand, client = pinned_pull
    refused = client.get("/api/plugin/diff/comparison", params=params)
    assert refused.status_code == 400
    assert refused.json()["error"] == "diff_comparison"


def test_the_pull_route_reports_a_missing_record(pinned_pull: tuple[_Stand, TestClient]) -> None:
    stand, client = pinned_pull
    (stand.published.home / source_pull_record(stand.published.slug, 7)).unlink()
    envelope = client.get("/api/plugin/github/pull").json()
    assert (envelope["state"], envelope["reason"], envelope["record"]) == (
        "absent",
        "not_cached",
        None,
    )
    stand.monkeypatch.setattr(
        pulls, "utc_now", lambda: FETCHED_AT + timedelta(seconds=FRESHNESS_WINDOW_S + 1)
    )
    stand.refresh(7)
    assert client.get("/api/plugin/github/pull").json()["state"] == "current"


def test_the_pull_route_answers_an_unchanged_record_with_a_304(
    pinned_pull: tuple[_Stand, TestClient],
) -> None:
    stand, client = pinned_pull
    first = client.get("/api/plugin/github/pull")
    etag = first.headers["etag"]
    unchanged = client.get("/api/plugin/github/pull", headers={"if-none-match": etag})
    assert (unchanged.status_code, unchanged.content) == (304, b"")
    assert unchanged.headers["cache-control"] == "no-store"
    # Aging past the freshness window changes the state, and so the tag.
    stand.monkeypatch.setattr(
        pulls, "utc_now", lambda: FETCHED_AT + timedelta(seconds=FRESHNESS_WINDOW_S + 1)
    )
    aged = client.get("/api/plugin/github/pull", headers={"if-none-match": etag})
    assert (aged.status_code, aged.json()["state"]) == (200, "stale")
    assert aged.headers["etag"] != etag


def test_the_markdown_route_renders_one_part_of_the_record(
    pinned_pull: tuple[_Stand, TestClient],
) -> None:
    stand, client = pinned_pull
    record = client.get("/api/plugin/github/pull").json()["record"]
    body = client.get("/api/plugin/github/pull-markdown", params={"part": "body"})
    assert body.status_code == 200
    rendered = body.json()
    assert (rendered["part"], rendered["fetched_at"]) == ("body", record["fetched_at"])
    assert "<strong>two</strong>" in rendered["html"]
    review = record["reviews"][1]
    answer = client.get(
        "/api/plugin/github/pull-markdown", params={"part": f"review/{review['id']}"}
    )
    assert "Looks right." in answer.json()["html"]
    for part, status_code, code in (
        ("", 400, "invalid_part"),
        ("pull/7", 400, "invalid_part"),
        ("review/1", 404, "unknown_part"),
    ):
        refused = client.get("/api/plugin/github/pull-markdown", params={"part": part})
        assert (refused.status_code, refused.json()["code"]) == (status_code, code)
    (stand.published.home / source_pull_record(stand.published.slug, 7)).unlink()
    missing = client.get("/api/plugin/github/pull-markdown", params={"part": "body"})
    assert (missing.status_code, missing.json()["code"]) == (404, "not_cached")


def test_the_markdown_route_never_trusts_raw_html_in_a_text(
    pinned_pull: tuple[_Stand, TestClient], monkeypatch: pytest.MonkeyPatch
) -> None:
    from metabrowser.builtin_plugins.github import pull_markdown

    hostile = (
        "Hi <script>alert(1)</script><img src=x onerror=alert(1)>"
        ' <a href="javascript:alert(1)">x</a> <iframe src="https://example.com"></iframe>'
    )
    monkeypatch.setattr(pull_markdown, "part_text", lambda _record, _part: hostile)
    _stand, client = pinned_pull
    html = client.get("/api/plugin/github/pull-markdown", params={"part": "body"}).json()["html"]
    for forbidden in ("<script", "onerror", "javascript:", "<iframe"):
        assert forbidden not in html


# ── Review hardening: degraded parts, oversized pages, and typed failures ──


def test_a_secondary_rate_limit_is_rate_limited(stand: _Stand) -> None:
    path = "repos/octo/demo/pulls/7"
    stand.answer(
        _api(
            scenario(stand.origin),
            path,
            {
                "status": 403,
                "headers": {"X-Ratelimit-Remaining": "4990"},
                "body": {"message": "You have exceeded a secondary rate limit. Please wait."},
            },
        )
    )
    with pytest.raises(GhError) as limited:
        asyncio.run(gh_api(path))
    assert (limited.value.state, limited.value.reset_at) == ("rate_limited", None)


def test_unreadable_optional_fields_are_left_empty_and_items_left_out(stand: _Stand) -> None:
    answers = scenario(stand.origin)
    head = stand.origin["fork_head"]
    checks = page(f"repos/octo/demo/commits/{head}/check-runs")
    runs = answers["api"][checks]["body"]["check_runs"]
    listed = {
        "total_count": 3,
        "check_runs": [
            {**runs[0], "details_url": "http://ci.example.invalid/job/1"},
            {**runs[1], "details_url": "https://" + "x" * 5000, "conclusion": 7},
            {**runs[1], "id": 3, "name": None},
        ],
    }
    status_path = page(f"repos/octo/demo/commits/{head}/status")
    status = answers["api"][status_path]["body"]
    combined = {
        **status,
        "statuses": [{**status["statuses"][0], "target_url": "http://docs.example.invalid/"}],
    }
    comments = page("repos/octo/demo/issues/7/comments")
    comment = answers["api"][comments]["body"][0]
    odd = [{**comment, "user": {"login": "not a login"}}, {**comment, "id": "seven"}]
    answers = _api(answers, checks, ok(checks, listed))
    answers = _api(answers, status_path, ok(status_path, combined))
    answers = _api(answers, comments, ok(comments, odd))
    stand.answer(answers)
    record = stand.refresh(7)
    assert [run.details_url for run in record.check_runs] == [None, None]
    assert record.check_runs[1].conclusion is None
    assert record.truncated.check_runs
    assert record.status is not None and record.status.statuses[0].target_url is None
    assert [comment.author for comment in record.issue_comments] == [None]
    assert record.truncated.issue_comments


def test_refused_checks_and_status_leave_the_record_standing(stand: _Stand) -> None:
    answers = scenario(stand.origin)
    head = stand.origin["fork_head"]
    checks = page(f"repos/octo/demo/commits/{head}/check-runs")
    status_path = page(f"repos/octo/demo/commits/{head}/status")
    answers = _api(answers, checks, {"status": 403, "body": {"message": "Resource not accessible"}})
    answers = _api(answers, status_path, {"status": 422, "body": {"message": "No commit found"}})
    stand.answer(answers)
    record = stand.refresh(7)
    assert record.check_runs == () and record.status is None
    assert record.unavailable == {"check_runs": "not_found_or_private", "status": "gh_failed"}
    assert record.comparison is not None


def test_a_base_that_cannot_be_fetched_leaves_no_comparison(stand: _Stand) -> None:
    answers = scenario(stand.origin)
    path = "repos/octo/demo/pulls/9"
    body = answers["api"][path]["body"]
    gone = {**body, "base": {**body["base"], "sha": "1" * 40}}
    stand.answer(_api(answers, path, ok(path, gone)))
    record = stand.refresh(9)
    assert record.comparison is None
    assert record.unavailable == {"comparison": "fetch_failed"}


def test_an_oversized_page_is_asked_for_again_smaller(
    stand: _Stand, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr("metabrowser.builtin_plugins.github.gh.GH_API_MAX_BYTES", 4000)
    answers = scenario(stand.origin)
    base = "repos/octo/demo/issues/7/comments"
    template = answers["api"][page(base)]["body"][0]
    comments = [
        {**template, "id": 1, "body": "first"},
        {**template, "id": 2, "body": "big " * 2000},
        {**template, "id": 3, "body": "third"},
    ]
    for size in (100, 50, 25, 5):
        path = f"{base}?per_page={size}&page=1"
        answers = _api(answers, path, ok(path, comments))
    for number, comment in enumerate(comments, start=1):
        path = f"{base}?per_page=1&page={number}"
        more = {"Link": f'<https://api.github.com/{base}?page={number + 1}>; rel="next"'}
        answers = _api(answers, path, ok(path, [comment], more if number < 3 else None))
    stand.answer(answers)
    record = stand.refresh(7)
    assert [comment.id for comment in record.issue_comments] == [1, 3]
    assert record.truncated.issue_comments
    asked = [call["args"][-1] for call in stand.calls() if call["args"][-1].startswith(base)]
    assert asked == [
        f"{base}?per_page=100&page=1",
        f"{base}?per_page=50&page=1",
        f"{base}?per_page=25&page=1",
        f"{base}?per_page=5&page=1",
        f"{base}?per_page=1&page=1",
        f"{base}?per_page=1&page=2",
        f"{base}?per_page=1&page=3",
    ]


def test_a_list_stops_at_its_page_cap(stand: _Stand, monkeypatch: pytest.MonkeyPatch) -> None:
    # Requests, not items: pages asked for again smaller spend the same allowance.
    monkeypatch.setattr(pulls, "_EXTRA_PAGE_REQUESTS", 0)
    monkeypatch.setattr("metabrowser.builtin_plugins.github.gh.GH_API_MAX_BYTES", 4000)
    answers = scenario(stand.origin)
    base = "repos/octo/demo/pulls/7/reviews"
    template = answers["api"][page(base)]["body"][0]
    reviews = [{**template, "id": number, "body": "x" * 1500} for number in range(1, 11)]
    for size in (100, 50, 25, 5):
        path = f"{base}?per_page={size}&page=1"
        answers = _api(answers, path, ok(path, reviews[:size]))
    for number, review in enumerate(reviews, start=1):
        path = f"{base}?per_page=1&page={number}"
        more = {"Link": f'<https://api.github.com/{base}?page={number + 1}>; rel="next"'}
        answers = _api(answers, path, ok(path, [review], more))
    stand.answer(answers)
    record = stand.refresh(7)
    # The cap of 500 reviews allows five requests: four oversized, then one review.
    assert [review.id for review in record.reviews] == [1]
    assert record.truncated.reviews


def test_text_escaping_counts_against_the_read_bound(
    stand: _Stand, monkeypatch: pytest.MonkeyPatch
) -> None:
    answers = scenario(stand.origin)
    comments = page("repos/octo/demo/issues/7/comments")
    control = [{**answers["api"][comments]["body"][0], "body": "\x01" * 60000}]
    stand.answer(_api(answers, comments, ok(comments, control)))
    monkeypatch.setattr(
        "metabrowser.builtin_plugins.github.pull_record.MAX_PULL_RECORD_BYTES", 120_000
    )
    record = stand.refresh(7)
    written = stand.published.home / source_pull_record(stand.published.slug, 7)
    assert written.stat().st_size <= 120_000
    assert record.truncated.text and record.issue_comments[0].body_truncated
    assert escaped_size(record.issue_comments[0].body) < 120_000


def test_a_reused_list_keeps_the_text_budget_cut(
    stand: _Stand, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr("metabrowser.builtin_plugins.github.pull_record.MAX_TEXT_BYTES", 80)
    first = stand.refresh(7)
    assert first.truncated.text
    again = stand.refresh(7)
    assert again.truncated.text
    assert again.issue_comments == first.issue_comments


def test_a_body_that_is_not_json_is_a_typed_failure(stand: _Stand) -> None:
    comments = page("repos/octo/demo/issues/7/comments")
    answers = _api(scenario(stand.origin), comments, {"status": 200, "raw": "<html>"})
    stand.answer(answers)
    with pytest.raises(PullDataError) as refused:
        stand.refresh(7)
    assert refused.value.state == "gh_failed"


def test_a_record_the_cache_cannot_hold_or_read_is_typed(stand: _Stand) -> None:
    record = stand.refresh(7)
    written = stand.published.home / source_pull_record(stand.published.slug, 7)
    elsewhere = stand.tmp_path / "elsewhere.json"
    written.rename(elsewhere)
    written.symlink_to(elsewhere)
    assert stand.record(7) == "unreadable"
    written.unlink()
    pulls_dir = written.parent
    for leftover in pulls_dir.iterdir():
        leftover.unlink()
    pulls_dir.rmdir()
    pulls_dir.write_text("not a directory", encoding="utf-8")
    with pytest.raises(PullDataError) as refused:
        stand.refresh(7)
    assert refused.value.state == "cache_unwritable"
    assert record.number == 7


def test_fetches_are_atomic(stand: _Stand, monkeypatch: pytest.MonkeyPatch) -> None:
    from metabrowser.cache import pull_refs

    seen: list[list[str]] = []
    original = pull_refs.run_git

    async def recording(args: list[str], **kwargs: Any) -> bytes:
        seen.append(list(args))
        return await original(args, **kwargs)

    monkeypatch.setattr(pull_refs, "run_git", recording)
    stand.refresh(9)
    fetches = [args for args in seen if "fetch" in args]
    assert len(fetches) == 2  # refs/pull/9/head, then base.sha by ID
    assert all("--atomic" in args for args in fetches)


def test_the_route_parses_a_record_again_only_when_it_changed(
    stand: _Stand, monkeypatch: pytest.MonkeyPatch
) -> None:
    from metabrowser.builtin_plugins.github import pull_route

    stand.refresh(7)
    reads: list[int] = []
    original = pull_route.read_pull_record

    def counting(home: Path, slug: str, number: int) -> PullRecord | str:
        reads.append(number)
        return original(home, slug, number)

    monkeypatch.setattr(pull_route, "read_pull_record", counting)
    home, slug = stand.published.home, stand.published.slug
    first, _ = pull_route.cached_pull_record(home, slug, 7)
    again, _ = pull_route.cached_pull_record(home, slug, 7)
    assert again is first and reads == [7]
    stand.refresh(7)
    pull_route.cached_pull_record(home, slug, 7)
    assert reads == [7, 7]


# ── served beside the mirror: the fetch lock, the refresh route, and serve mode ──

_JSON = {"content-type": "application/json"}
_REFRESH_ROUTE = "/api/plugin/github/pull-refresh"


def test_a_fetch_takes_the_mirror_fetch_lock_and_hands_it_to_git(
    stand: _Stand, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Leftovers are removed under the lock, Git inherits its descriptor, and a lock
    another refresh keeps past the wait is ``refreshing_elsewhere``."""

    home, store_key = stand.published.home, stand.published.store_key
    claimed: list[int] = []
    cleaned: list[bool] = []
    handed: list[tuple[int, ...]] = []
    claim, cleanup, git = (
        pull_refs._claim_fetch_lock,  # pyright: ignore[reportPrivateUsage]
        pull_refs.remove_interrupted_fetch_leftovers,
        pull_refs.run_git,
    )

    def claiming(published: PublishedSource, owner: Any) -> Any:
        lock = claim(published, owner)
        claimed.append(lock.descriptor)
        return lock

    def cleaning(git_dir: Path) -> tuple[str, ...]:
        with pytest.raises(LockBusyError):
            store_fetch_lock(home, store_key)
        cleaned.append(True)
        return cleanup(git_dir)

    async def recording(args: list[str], **kwargs: Any) -> bytes:
        if "fetch" in args:
            handed.append(tuple(kwargs.get("pass_fds", ())))
        return await git(args, **kwargs)

    monkeypatch.setattr(pull_refs, "_claim_fetch_lock", claiming)
    monkeypatch.setattr(pull_refs, "remove_interrupted_fetch_leftovers", cleaning)
    monkeypatch.setattr(pull_refs, "run_git", recording)
    stand.refresh(7)
    assert claimed and handed == [(descriptor,) for descriptor in claimed]
    assert cleaned == [True] * len(claimed)
    store_fetch_lock(home, store_key).release()  # released after the fetch

    monkeypatch.setattr(pull_refs, "FETCH_LOCK_WAIT_S", 0.0)
    (home / source_pull_record(stand.published.slug, 7)).unlink()
    held = store_fetch_lock(home, store_key)
    try:
        with pytest.raises(PullDataError) as busy:
            stand.refresh(7)
    finally:
        held.release()
    assert busy.value.state == "refreshing_elsewhere"
    assert stand.record(7) == "not_cached"


def test_a_served_pull_request_is_stale_by_its_record_or_its_last_try(
    stand: _Stand, monkeypatch: pytest.MonkeyPatch
) -> None:
    window = FRESHNESS_WINDOW_S
    assert served_pull(stand.published, 7).is_stale(FETCHED_AT, window_s=window)
    stand.refresh(7)
    served = served_pull(stand.published, 7)
    assert served.key == f"{stand.published.store_key}:pull/7"
    assert not served.is_stale(FETCHED_AT + timedelta(seconds=window), window_s=window)
    later = FETCHED_AT + timedelta(seconds=window + 1)
    assert served.is_stale(later, window_s=window)

    async def failing(published: PublishedSource, number: int) -> PullRecord:
        raise PullDataError("gh_missing", f"pull request {number}: gh is not installed")

    monkeypatch.setattr(pulls, "refresh_pull_request", failing)
    monkeypatch.setattr(pulls, "utc_now", lambda: later)
    asyncio.run(served.refresh())
    assert served.last is not None and served.last["outcome"] == "gh_missing"
    assert served.fetched_at == "2026-09-17T12:00:00Z"
    # A failing refresh is tried once a window, not on every poll.
    assert not served.is_stale(later, window_s=window)
    assert served.is_stale(later + timedelta(seconds=window + 1), window_s=window)


def test_a_pull_request_head_is_pinned_by_its_ref(stand: _Stand) -> None:
    stand.refresh(7)
    target = repository_store_target(git_dir=stand.published.git_dir)
    resolved = asyncio.run(resolve_pin(target, ref="refs/pull/7/head"))
    assert (resolved.commit_oid, resolved.ref) == (stand.origin["fork_head"], "refs/pull/7/head")
    for ref in ("refs/pull/0/head", "refs/pull/7/merge", "refs/pull/x/head", "refs/heads/topic"):
        with pytest.raises(InvalidSelectionError):
            asyncio.run(resolve_pin(target, ref=ref))


def _settle(client: TestClient) -> dict[str, Any]:
    deadline = time.monotonic() + 60
    while True:
        status = client.get("/api/source/status").json()
        if not status["refreshing"]:
            return status
        assert time.monotonic() < deadline, "the refresh did not finish"
        time.sleep(0.02)


def test_the_refresh_route_starts_or_joins_one_job(
    pinned_pull: tuple[_Stand, TestClient], monkeypatch: pytest.MonkeyPatch
) -> None:
    _stand, client = pinned_pull
    session = mirror_session(app)
    served = None if session is None else session.companion
    assert isinstance(served, ServedPull)
    release = threading.Event()
    runs: list[int] = []

    async def held() -> None:
        runs.append(7)
        # The test thread sets it; a worker thread waits so the job stays running.
        await asyncio.to_thread(release.wait, 30)

    monkeypatch.setattr(served, "refresh", held)
    first = client.post(_REFRESH_ROUTE, json={}, headers=_JSON)
    assert (first.status_code, first.headers["cache-control"]) == (202, "no-store")
    body = first.json()
    assert (body["refresh"], body["pull"]["number"], body["pull"]["refreshing"]) == (
        "started",
        7,
        True,
    )
    assert client.post(_REFRESH_ROUTE, json={}, headers=_JSON).json()["refresh"] == "joined"
    assert client.get("/api/plugin/github/pull").json()["refreshing"] is True
    assert client.get("/api/source/status").json()["refreshing"] is True
    release.set()
    _settle(client)
    assert runs == [7]
    assert client.get("/api/plugin/github/pull").json()["refreshing"] is False


def test_the_refresh_route_refuses_what_is_not_a_refresh_request(
    pinned_pull: tuple[_Stand, TestClient],
) -> None:
    _stand, client = pinned_pull
    assert client.get(_REFRESH_ROUTE).status_code == 405
    for content, status in ((b"[]", 400), (b"{", 400), (b'{"x": "' + b"y" * 2000 + b'"}', 413)):
        refused = client.post(_REFRESH_ROUTE, content=content, headers=_JSON)
        assert (refused.status_code, refused.json()["code"]) == (status, "invalid_request")
    # The application's own guards: another origin, a body not declared as JSON, and a
    # page for a pin the server no longer serves.
    other = {**_JSON, "origin": "https://example.invalid"}
    assert client.post(_REFRESH_ROUTE, json={}, headers=other).status_code == 403
    plain = {"content-type": "text/plain"}
    assert client.post(_REFRESH_ROUTE, content=b"{}", headers=plain).status_code == 415
    outdated = client.post(_REFRESH_ROUTE, json={}, headers={**_JSON, PIN_HEADER: "0" * 40})
    assert (outdated.status_code, outdated.json()["code"]) == (409, "pin_changed")


def _move_pull_head(stand: _Stand, commit: str) -> None:
    subprocess.run(
        [
            "git",
            "--git-dir",
            str(stand.tmp_path / "github-pull-origin.git"),
            "update-ref",
            "refs/pull/7/head",
            commit,
        ],
        check=True,
        capture_output=True,
        env=git_env(stand.tmp_path),
    )


def _answering_head(stand: _Stand, head: str) -> dict[str, Any]:
    """The scenario, with pull request 7's head at *head* and no checks on it yet."""

    answers = scenario(stand.origin)
    path = "repos/octo/demo/pulls/7"
    body = answers["api"][path]["body"]
    answers = _api(answers, path, ok(path, {**body, "head": {**body["head"], "sha": head}}))
    for part, empty in (
        ("check-runs", {"total_count": 0, "check_runs": []}),
        ("status", {"state": "pending", "statuses": []}),
    ):
        listed = page(f"repos/octo/demo/commits/{head}/{part}")
        answers = _api(answers, listed, ok(listed, empty))
    return answers


def _serve(url: str) -> Any:
    with (
        patch("metabrowser.cli.serve._QuietForceExitServer") as server_class,
        patch("metabrowser.cli.serve.find_available_local_port", return_value=8411),
    ):
        result = CliRunner().invoke(_app, [url, "--no-open"])
    if result.exit_code == 0:
        assert server_class.call_args.args[0].app is app
    return result


def test_a_served_pull_request_pins_its_head_and_refreshes_beside_the_mirror(
    stand: _Stand, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Serve mode: the cold read pins the head, the pull route answers, a refresh runs in
    the coordinator, and a newer head is offered as ``latest`` rather than switched to."""

    monkeypatch.setattr("metabrowser.cli.git_pin_cli.stop_on_interrupt", lambda: None)
    # The session's freshness window reads the wall clock, so records do too here.
    monkeypatch.setattr(pulls, "utc_now", lambda: datetime.now(UTC).replace(microsecond=0))
    earlier, head = stand.origin["fork_earlier"], stand.origin["fork_head"]
    _move_pull_head(stand, earlier)
    stand.answer(_answering_head(stand, earlier))
    try:
        result = _serve(f"{CANONICAL}/pull/7")
        assert result.exit_code == 0, result.output
        assert f"Revision: {earlier} (refs/pull/7/head)\n" in result.stdout
        with TestClient(app) as client:
            status = _settle(client)
            assert (status["pin"], status["pull_request"], status["stale"]) == (earlier, 7, False)
            envelope = client.get("/api/plugin/github/pull").json()
            assert (envelope["state"], envelope["pin"]) == ("current", earlier)
            assert envelope["record"]["pull"]["head"]["sha"] == earlier

            _move_pull_head(stand, head)
            stand.answer(scenario(stand.origin))
            started = client.post(_REFRESH_ROUTE, json={}, headers=_JSON)
            assert started.status_code == 202 and started.json()["pull"]["refreshing"] is True
            status = _settle(client)
            assert (status["pin"], status["latest"]) == (earlier, head)
            envelope = client.get("/api/plugin/github/pull").json()
            assert envelope["last_refresh"]["outcome"] == "succeeded"
            assert (envelope["pin"], envelope["record"]["pull"]["head"]["sha"]) == (earlier, head)

            # Taking the offer switches by the pull request's ref, as the page does.
            taken = client.post("/api/source/pin", json={"ref": "refs/pull/7/head"}, headers=_JSON)
            assert taken.status_code == 200, taken.text
            assert taken.json()["status"]["pin"] == head

            # The record's age alone makes the served source stale.
            session = mirror_session(app)
            served = None if session is None else session.companion
            assert isinstance(served, ServedPull)
            served.fetched_at = "2020-01-01T00:00:00Z"
            served._last_attempt = None  # pyright: ignore[reportPrivateUsage]
            assert client.get("/api/source/status").json()["stale"] is True
    finally:
        serve_mirror(None)
        reset_source_session()
        git_repo.clear_repo_cache()
