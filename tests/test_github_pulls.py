"""Pull-request records: the gh runner, the account check, refresh, bounds, and reads.

Everything runs against ``tests/github_pull_fixture.py``: a ``file://`` origin with
GitHub's ``refs/pull/<n>/head`` standing in for ``https://github.com/octo/demo``, and a
fake ``gh`` replaying scrubbed real responses. Nothing reaches the network or the
``gh`` a developer has signed in.
"""

from __future__ import annotations

import asyncio
import contextlib
import copy
import itertools
import json
import os
import signal
import subprocess
import threading
import time
from collections.abc import Awaitable, Callable, Generator, Iterable, Iterator
from dataclasses import dataclass, replace
from dataclasses import field as dataclass_field
from datetime import UTC, datetime, timedelta
from functools import partial
from pathlib import Path
from typing import Any, Final, Literal
from unittest.mock import patch

import pytest
from pydantic import ValidationError
from starlette.testclient import TestClient
from typer.testing import CliRunner

from metabrowser.builtin_plugins.github import gh_budget, gh_lists, pulls
from metabrowser.builtin_plugins.github.gh import (
    GhError,
    GhFailureState,
    GhResponse,
    gh_account,
    gh_api,
    parse_active_account,
    parse_included_response,
    rate_limit_reset,
)
from metabrowser.builtin_plugins.github.gh_lists import active_account
from metabrowser.builtin_plugins.github.pull_catalog import read_pull_status, write_pull_status
from metabrowser.builtin_plugins.github.pull_file_anchor import path_digest
from metabrowser.builtin_plugins.github.pull_list import ListedRepository
from metabrowser.builtin_plugins.github.pull_markdown import render_part
from metabrowser.builtin_plugins.github.pull_record import (
    MAX_BODY_BYTES,
    MAX_DIFF_HUNK_BYTES,
    MAX_PULL_COMMITS,
    PULL_RECORD_PROJECTION,
    PullRecord,
    PullRefreshStamp,
    PullRequest,
    apply_text_budget,
    cut_text,
    escaped_size,
    read_pull_record,
    read_pull_refresh,
    serialize_pull_record,
    write_pull_record,
    write_pull_refresh,
)
from metabrowser.builtin_plugins.github.pull_route import PullView, pull_state
from metabrowser.builtin_plugins.github.pull_status import PullStatus
from metabrowser.builtin_plugins.github.pull_status_store import (
    CheckProbes,
    kept_status,
    read_pull_checks,
    read_status_outcome,
)
from metabrowser.builtin_plugins.github.pulls import PullDataError, open_pull_request
from metabrowser.builtin_plugins.github.served_pull import (
    MAX_KEPT_PULLS,
    ServedPull,
    ServedPulls,
    served_pull,
)
from metabrowser.cache import pull_refs
from metabrowser.cache.acquire import PublishedSource, acquire_source
from metabrowser.cache.layout import open_cache
from metabrowser.cache.locks import LockBusyError, store_fetch_lock
from metabrowser.cache.paths import source_pull_record, source_pull_refresh
from metabrowser.cache.pull_refs import ref_commit
from metabrowser.cache.repository_store import open_revision
from metabrowser.cache.resolve import resolve_pin, store_ignores_case
from metabrowser.cache.served_mirror import StoreMirror
from metabrowser.cache.urls import GitSource, RepositorySelection
from metabrowser.cli.main import _app
from metabrowser.git import process as git_process
from metabrowser.git import repo as git_repo
from metabrowser.git.process import GitError, kill_live_process_groups, repository_store_target
from metabrowser.git.tree_source import GitRevisionSubject
from metabrowser.mirror_refresh import (
    FRESHNESS_WINDOW_S,
    MAX_PULL_JOBS,
    InvalidSelectionError,
    mirror_session,
    serve_mirror,
)
from metabrowser.server import app
from metabrowser.source import attach_subject
from metabrowser.source_routes import PIN_CHANGED_HEADER, PIN_HEADER
from tests.diff_fixture_repo import git
from tests.git_pin_harness import git_env
from tests.github_pull_fixture import (
    CANONICAL,
    DEFAULT_BRANCH,
    FETCHED_AT,
    READER,
    Origin,
    account,
    graph_core_data,
    graph_core_entry,
    graph_status_entry,
    install_fake_gh,
    logged_gh_calls,
    ok,
    page,
    pull_bodies,
    scenario,
)
from tests.golden_harness import read_recording, settle
from tests.held_port import listener_on
from tests.loop_gate import held_until
from tests.required_tools import needs_git
from tests.test_cache_acquire import _allow_installed_git

pytestmark = [
    needs_git,
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
def stand(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, pull_origin: Origin) -> _Stand:
    home = tmp_path / "home"
    monkeypatch.setenv("METABROWSER_CACHE_DIR", str(home))
    _allow_installed_git(monkeypatch)
    origin = pull_origin
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


def _move_origin_ref(stand: _Stand, ref: str, commit: str) -> None:
    subprocess.run(
        ["git", "--git-dir", str(stand.origin.path), "update-ref", ref, commit],
        check=True,
        capture_output=True,
        env=git_env(stand.tmp_path),
    )


def _move_pull_head(stand: _Stand, commit: str) -> None:
    _move_origin_ref(stand, "refs/pull/7/head", commit)


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


@pytest.mark.parametrize(
    "headers",
    [
        # Past what a timedelta holds, past what a date holds, and past what int() reads.
        {"retry-after": "99999999999999"},
        {"retry-after": "999999999999"},
        {"retry-after": "9" * 5000},
        # A character that isdigit() takes and int() refuses, which a header can carry.
        {"retry-after": "\u00b2"},
        {"x-ratelimit-remaining": "0", "x-ratelimit-reset": "99999999999999"},
        {"x-ratelimit-remaining": "0", "x-ratelimit-reset": "9" * 5000},
        {"x-ratelimit-remaining": "0", "x-ratelimit-reset": "\u00b2"},
    ],
)
def test_a_rate_limit_time_no_clock_can_hold_says_a_limit_without_a_time(
    headers: dict[str, str],
) -> None:
    """An exception here would end the refresh job with no stamp, and the page would keep
    the previous outcome; a typed ``rate_limited`` with no ``reset_at`` is what it means."""

    now = datetime(2026, 9, 17, 12, 0, tzinfo=UTC)
    assert rate_limit_reset(GhResponse(403, headers, b"{}"), now=now) == "unknown"


def test_gh_api_runs_isolated_with_fixed_arguments(
    stand: _Stand, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("GH_DEBUG", "api")
    monkeypatch.setenv("GH_HOST", "enterprise.example.com")
    monkeypatch.setenv("GH_REPO", "other/repo")
    # Common in dotfiles: either makes gh colorize --include headers and JSON.
    monkeypatch.setenv("CLICOLOR_FORCE", "1")
    monkeypatch.setenv("GH_FORCE_TTY", "1")
    # Under pytest's capture this process's own stdin is already the null device, which
    # a gh that inherited it would pass for one given none. A pipe there tells them apart.
    read_end, write_end = os.pipe()
    own_stdin = os.dup(0)
    os.dup2(read_end, 0)
    try:
        response = asyncio.run(gh_api("repos/octo/demo/pulls/7", etag='W/"x"'))
    finally:
        os.dup2(own_stdin, 0)
        for descriptor in (own_stdin, read_end, write_end):
            os.close(descriptor)
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
    "path",
    [
        "../repos/x",
        "repos/octo/../demo",
        "repos/octo/demo --paginate",
        "-X",
        # Only ``user`` itself is admitted outside a repository (the account check).
        "users/octo",
        "user/repos",
        "user?per_page=1",
        "user/",
        "rate_limit",
    ],
)
def test_gh_api_refuses_a_path_it_did_not_build(path: str) -> None:
    with pytest.raises(ValueError, match="not an API path Metabrowser reads"):
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
    # GitHub itself refusing the credentials, in a response gh printed, is the same state.
    path = "repos/octo/demo/pulls/7"
    refusal = {"status": 401, "body": {"message": "Requires authentication"}}
    stand.answer(_api(scenario(stand.origin), path, refusal))
    with pytest.raises(GhError) as refused:
        asyncio.run(gh_api(path))
    assert refused.value.state == "not_logged_in"

    stand.answer(_api(scenario(stand.origin), path, {"status": 502}))
    with pytest.raises(GhError) as upstream:
        asyncio.run(gh_api(path))
    assert upstream.value.state == "network_error"

    api_failure = {
        "stderr": "error connecting to api.github.com\nPlease try gh auth login\n",
        "exit": 1,
    }
    stand.answer({**scenario(stand.origin), "api_failure": api_failure})
    with pytest.raises(GhError) as offline:
        asyncio.run(gh_api(path))
    assert offline.value.state == "network_error"


def test_account_is_the_active_login_even_in_an_error_state() -> None:
    errored = parse_active_account(account("octo", state="error")["stdout"].encode())
    assert errored is not None and errored.login == "octo"
    assert parse_active_account(b'{"hosts":{}}') is None
    inactive = {"hosts": {"github.com": [{"active": False, "login": "other", "state": "success"}]}}
    assert parse_active_account(json.dumps(inactive).encode()) is None
    with pytest.raises(GhError):
        parse_active_account(b'{"hosts":{"github.com":[{"active":true,"login":"bad login"}]}}')


def _gh_commands(stand: _Stand) -> list[str]:
    """Each logged gh call as its command, with the ETag a conditional one sent."""

    commands: list[str] = []
    for call in stand.calls():
        args: list[str] = call["args"]
        sent = next((arg for arg in args if arg.startswith("If-None-Match: ")), None)
        named = "auth status" if args[:2] == ["auth", "status"] else f"api {args[-1]}"
        commands.append(named + (f" [{sent.split(': ', 1)[1]}]" if sent else ""))
    return commands


def test_the_account_check_is_a_conditional_read_that_a_304_answers(stand: _Stand) -> None:
    """mb-1bir: ``gh auth status`` cost one core call each time; a ``304`` costs none."""

    assert asyncio.run(active_account()) == READER
    assert asyncio.run(active_account()) == READER
    # The second carries the first's ETag, GitHub answers 304, and the login stands.
    assert _gh_commands(stand) == ["api user", 'api user ["user-octo-reader"]']
    # Another account's token gets a 200 for the old ETag, and its own from then on.
    stand.answer({**scenario(stand.origin), "auth": account("someone-else")})
    assert asyncio.run(active_account()) == "someone-else"
    assert asyncio.run(active_account()) == "someone-else"
    assert _gh_commands(stand) == [
        'api user ["user-octo-reader"]',
        'api user ["user-someone-else"]',
    ]


def test_an_account_check_that_finds_no_account_asks_gh_auth_status_why(stand: _Stand) -> None:
    stand.answer({**scenario(stand.origin), "auth": {"stdout": '{"hosts":{}}\n', "exit": 0}})
    with pytest.raises(PullDataError) as signed_out:
        asyncio.run(active_account())
    assert signed_out.value.state == "not_logged_in"
    assert "gh auth login --hostname github.com" in str(signed_out.value)
    assert _gh_commands(stand) == ["api user", "auth status"]
    # A refused token in the environment: only gh auth status names the variable.
    refused = {
        "active": True,
        "login": "",
        "state": "error",
        "error": "HTTP 401: Bad credentials",
        "tokenSource": "GH_TOKEN",
    }
    stand.answer(
        {
            **scenario(stand.origin),
            "auth": {"stdout": json.dumps({"hosts": {"github.com": [refused]}}), "exit": 0},
        }
    )
    with pytest.raises(PullDataError) as token:
        asyncio.run(active_account())
    assert token.value.state == "not_logged_in"
    assert "replace the token in GH_TOKEN" in str(token.value)


def test_an_account_check_that_cannot_reach_github_names_the_account_gh_has_saved(
    stand: _Stand,
) -> None:
    """Offline, ``gh auth status`` still names the saved account, so a switch is seen."""

    assert asyncio.run(active_account()) == READER
    stand.calls()
    offline = {"stderr": "error connecting to api.github.com\n", "exit": 1}
    stand.answer(
        {**scenario(stand.origin), "auth": account("someone-else"), "api_failure": offline}
    )
    assert asyncio.run(active_account()) == "someone-else"
    assert _gh_commands(stand) == ['api user ["user-octo-reader"]', "auth status"]


def test_a_gh_too_old_for_auth_status_json_still_passes_the_account_check(
    stand: _Stand,
) -> None:
    old = {"stderr": "unknown flag: --json\n\nUsage: gh auth status\n", "exit": 1}
    named = {"status": 200, "headers": {"Etag": '"old"'}, "body": {"login": READER}}
    stand.answer(_api({**scenario(stand.origin), "auth": old}, "user", named))
    assert asyncio.run(active_account()) == READER
    assert _gh_commands(stand) == ["api user"]
    # Signed out, it is asked why and cannot say: the status check's own state.
    stand.answer({**scenario(stand.origin), "auth": old})
    with pytest.raises(PullDataError) as too_old:
        asyncio.run(active_account())
    assert too_old.value.state == "gh_too_old"
    assert _gh_commands(stand) == ['api user ["old"]', "auth status"]


def test_an_account_check_github_refuses_keeps_the_last_login_for_the_next(
    stand: _Stand,
) -> None:
    assert asyncio.run(active_account()) == READER
    limited = {
        "status": 403,
        "headers": {"X-Ratelimit-Remaining": "0", "X-Ratelimit-Reset": "1790181960"},
        "body": {"message": "API rate limit exceeded"},
    }
    stand.answer(_api(scenario(stand.origin), "user", limited))
    with pytest.raises(PullDataError) as refused:
        asyncio.run(active_account())
    assert (refused.value.state, refused.value.reset_at) == (
        "rate_limited",
        "2026-09-23T16:46:00Z",
    )
    stand.answer(scenario(stand.origin))
    stand.calls()
    assert asyncio.run(active_account()) == READER
    assert _gh_commands(stand) == ['api user ["user-octo-reader"]']


def test_a_304_names_the_account_to_the_budget_as_a_200_does(stand: _Stand) -> None:
    """Review A5 on #726: the status check can name another account between two checks,
    and the budget then belongs to the one this check answers for."""

    from metabrowser.builtin_plugins.github import gh_budget

    assert asyncio.run(active_account()) == READER
    gh_budget.note_account("someone-else")
    gh_budget.hold("2026-09-17T13:00:00Z", now=FETCHED_AT)
    assert gh_budget.held_until(FETCHED_AT) is not None
    assert asyncio.run(active_account()) == READER
    assert _gh_commands(stand) == ["api user", 'api user ["user-octo-reader"]']
    # The 304 named octo-reader, so someone-else's hold is forgotten.
    assert gh_budget.held_until(FETCHED_AT) is None


def test_a_saved_token_github_refuses_fails_as_gh_auth_status_says(stand: _Stand) -> None:
    """Review A5 on #726: gh names the saved account and says GitHub refused its token."""

    refused = {
        "active": True,
        "login": READER,
        "state": "error",
        "error": "HTTP 401: Bad credentials",
        "tokenSource": "keyring",
    }
    stand.answer(
        {
            **scenario(stand.origin),
            "auth": {"stdout": json.dumps({"hosts": {"github.com": [refused]}}), "exit": 0},
        }
    )
    with pytest.raises(PullDataError) as failed:
        asyncio.run(active_account())
    assert failed.value.state == "not_logged_in"
    # The step gh auth status's own verdict names, not the bare 401's.
    assert "gh auth login --hostname github.com" in str(failed.value)
    assert _gh_commands(stand) == ["api user", "auth status"]


@pytest.mark.parametrize(
    ("entry", "message"),
    [
        # The login becomes the record's reader, so it is checked as gh auth status's is.
        (ok("user", {"login": "not a login"}), "not a GitHub login"),
        (ok("user", {"login": 7}), "not a GitHub login"),
        ({"status": 404, "body": {"message": "Not Found"}}, "would not name the account"),
        # A 304 for a request that sent no ETag names no one.
        ({"status": 304}, "not conditional"),
    ],
)
def test_an_account_answer_that_names_no_login_fails_the_check(
    stand: _Stand, entry: dict[str, Any], message: str
) -> None:
    stand.answer(_api(scenario(stand.origin), "user", entry))
    with pytest.raises(PullDataError) as failed:
        asyncio.run(active_account())
    assert failed.value.state == "gh_failed" and message in str(failed.value)
    assert "pull request" not in str(failed.value)


def test_an_account_answer_with_no_etag_is_asked_for_unconditionally_next(
    stand: _Stand,
) -> None:
    """Review A5 on #726: the old ETag would be another answer's."""

    assert asyncio.run(active_account()) == READER
    bare = {
        "status": 200,
        "headers": {"X-Ratelimit-Limit": "5000"},
        "body": {"login": "someone-else"},
    }
    stand.answer(_api(scenario(stand.origin), "user", bare))
    assert asyncio.run(active_account()) == "someone-else"
    assert asyncio.run(active_account()) == "someone-else"
    assert _gh_commands(stand) == ["api user", 'api user ["user-octo-reader"]', "api user"]


@pytest.mark.parametrize(
    ("state", "diagnostic", "outcome", "message"),
    [
        (
            "error",
            "dial tcp: no such host",
            "network_error",
            "api.github.com did not resolve (DNS)",
        ),
        ("timeout", None, "network_error", "GitHub did not answer in time"),
        ("error", "HTTP 503: private diagnostic", "network_error", "GitHub answered HTTP 503"),
        ("error", "HTTP 401: private diagnostic", "not_logged_in", "gh auth login"),
        ("error", "private diagnostic", "gh_failed", "not a GitHub login"),
    ],
)
def test_environment_token_login_resolution_failure_is_typed(
    state: str, diagnostic: str | None, outcome: str, message: str
) -> None:
    active = {"active": True, "login": "", "state": state, "error": diagnostic}
    payload = {"hosts": {"github.com": [active]}}
    with pytest.raises(GhError) as failure:
        parse_active_account(json.dumps(payload).encode())
    assert failure.value.state == outcome
    assert message in str(failure.value) and "private diagnostic" not in str(failure.value)


# ── refresh ────────────────────────────────────────────────────


def test_merged_and_closed_pull_requests_compare_from_base_sha(stand: _Stand) -> None:
    origin = stand.origin
    merged = stand.refresh(8)
    assert merged.pull.merged and merged.comparison is not None
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
    assert draft.pull.draft and draft.comparison is not None
    assert draft.comparison.base == origin["topic"]
    # Whether each can merge is its status's, read after its record.
    home, slug = stand.published.home, stand.published.slug
    conflicts = {number: read_pull_status(home, slug, number) for number in (8, 9, 10)}
    assert {number: kept and kept.conflicts for number, kept in conflicts.items()} == {
        8: "unknown",
        9: "unknown",
        10: "conflicting",
    }


def test_etags_are_not_sent_for_another_reader(stand: _Stand) -> None:
    stand.refresh(7)
    stand.answer({**scenario(stand.origin), "auth": account("someone-else")})
    stand.calls()
    record = stand.refresh(7)
    assert record.reader == "gh:someone-else"
    # The pull request's own reads; the account check's ``user`` is conditional on the
    # account, not on a record.
    sent = [
        call["args"]
        for call in stand.calls()
        if call["args"][0] == "api" and call["args"][-1] != "user"
    ]
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
    # What a record may hold is checked again when it is read, not only when it is
    # written: a login that is not one, a link that is not https, and a field the record
    # does not have, such as GitHub's own rendering of a body.
    pull = payload["pull"]
    for damaged in (
        {**payload, "pull": {**pull, "author": "not a login"}},
        {**payload, "pull": {**pull, "html_url": "javascript:alert(1)"}},
        {**payload, "pull": {**pull, "body_html": "<script>alert(1)</script>"}},
        # A field an earlier schema had, now the status's.
        {**payload, "pull": {**pull, "mergeable": "mergeable"}},
    ):
        path.write_text(json.dumps(damaged), encoding="utf-8")
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
        "; the refresh failed: Metabrowser could not find GitHub CLI (gh). Install it from https://cli.github.com/, then run gh auth login --hostname github.com. (gh_missing)"
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
    """The cache is opened, and swept, only for a source it does not hold yet.

    No transcript opens it while a record exists, so none would show a sweep that took
    the records with it.
    """

    record = stand.refresh(7)
    home, slug = stand.published.home, stand.published.slug
    stamp = read_pull_refresh(home, slug, 7)
    assert stamp is not None and stamp.outcome == "succeeded"
    open_cache(home)
    assert stand.record(7) == record
    assert read_pull_refresh(home, slug, 7) == stamp


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

    with _serving_pinned(stand) as client:
        yield stand, client


@pytest.fixture
def pinned_pull_on_one_worker(
    stand: _Stand, monkeypatch: pytest.MonkeyPatch
) -> Iterator[tuple[_Stand, TestClient]]:
    """``pinned_pull`` on a server whose default executor runs one thread.

    On it, a step that keeps a worker thread while it waits for work that needs one waits
    forever, which on the production pool only CPython's miscount makes possible (see
    ``tests/loop_gate.py``).
    """

    from metabrowser import events_route

    monkeypatch.setattr(events_route, "DEFAULT_EXECUTOR_WORKERS", 1)
    with _serving_pinned(stand) as client:
        # The patch reaches the pool only while the lifespan reads that global. Were the
        # size to come from elsewhere, the server would run its full pool and the tests on
        # this fixture would pass whatever production keeps a worker for, so check it.
        assert client.portal is not None

        async def pool_size() -> int:
            loop: Any = asyncio.get_running_loop()
            return loop._default_executor._max_workers

        assert client.portal.call(pool_size) == 1, "the server's pool is not one thread"
        yield stand, client


@contextlib.contextmanager
def _serving_pinned(stand: _Stand) -> Generator[TestClient]:
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
        pull_requests=ServedPulls(published),
    )
    git_repo.clear_repo_cache()
    try:
        with TestClient(app) as client:
            yield client
    finally:
        serve_mirror(None)
        git_repo.clear_repo_cache()


def _read(client: TestClient, number: int, *, etag: str | None = None) -> Any:
    headers = {} if etag is None else {"if-none-match": etag}
    return client.get("/api/plugin/github/pull", params={"number": number}, headers=headers)


def _changed(body: dict[str, Any]) -> set[str]:
    return {
        (change.get("new") or change.get("old"))["path"] for change in body["manifest"]["files"]
    }


def test_the_pull_route_and_the_comparison_it_names(
    pinned_pull: tuple[_Stand, TestClient],
) -> None:
    stand, client = pinned_pull
    origin = stand.origin
    envelope = _read(client, 7).json()
    assert (envelope["state"], envelope["number"], envelope["pin"]) == (
        "current",
        7,
        origin["fork_head"],
    )
    assert envelope["pin_ref"] == "refs/pull/7/head"
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


def test_the_pull_route_answers_an_unchanged_record_with_a_304(
    pinned_pull: tuple[_Stand, TestClient],
) -> None:
    stand, client = pinned_pull
    first = _read(client, 7)
    etag = first.headers["etag"]
    unchanged = _read(client, 7, etag=etag)
    assert (unchanged.status_code, unchanged.content) == (304, b"")
    assert unchanged.headers["cache-control"] == "no-store"
    # Aging past the freshness window changes the state, and so the tag.
    stand.monkeypatch.setattr(
        pulls, "utc_now", lambda: FETCHED_AT + timedelta(seconds=FRESHNESS_WINDOW_S + 1)
    )
    aged = _read(client, 7, etag=etag)
    assert (aged.status_code, aged.json()["state"]) == (200, "stale")
    assert aged.headers["etag"] != etag


def test_labels_pending_holds_while_the_label_job_runs_and_the_set_lacks_a_shown_label(
    pinned_pull: tuple[_Stand, TestClient], monkeypatch: pytest.MonkeyPatch
) -> None:
    """A record cached before label colors names its labels alone (``mb-varu``).

    The pull route reads the set from the cache alone. Only ``labels-refresh`` starts its
    job, and while that job runs and the set does not hold a label the record names,
    ``labels_pending`` says so, which makes the page poll fast. Once the job has published,
    the label the set holds has its entry, and one it does not hold leaves nothing pending.
    """

    from metabrowser.builtin_plugins.github import pull_labels

    stand, client = pinned_pull
    path = stand.published.home / source_pull_record(stand.published.slug, 7)
    old = json.loads(path.read_bytes())
    old["projection_version"] = 1
    old["pull"]["labels"] = ["enhancement", "deleted-on-github"]
    path.write_text(json.dumps(old))
    stand.calls()
    bare = _read(client, 7).json()
    assert (bare["repository_labels"], bare["labels_pending"]) == ([], False)
    # A read is cache-only: it asked GitHub for nothing, the label set included.
    assert stand.calls() == []
    release = threading.Event()
    real = pull_labels.gh_api

    async def held(path: str, *, etag: str | None = None) -> GhResponse:
        await held_until(release, 30)
        return await real(path, etag=etag)

    monkeypatch.setattr(pull_labels, "gh_api", held)
    started = client.post("/api/plugin/github/labels-refresh", json={})
    assert (started.status_code, started.json()["refresh"]) == (202, "started")
    assert client.post("/api/plugin/github/labels-refresh", json={}).json()["refresh"] == "joined"
    running = _read(client, 7, etag=None).json()
    assert (running["repository_labels"], running["labels_pending"]) == ([], True)
    release.set()
    deadline = time.monotonic() + 30
    while client.get("/api/plugin/github/labels").json()["refreshing"]:
        assert time.monotonic() < deadline, "the label job did not end"
        time.sleep(0.05)
    colored = _read(client, 7).json()
    assert colored["repository_labels"] == [
        {
            "name": "enhancement",
            "color": "2700af",
            "description": "A label's description is its chip's tooltip",
        }
    ]
    # The set does not hold the other label, and no job runs: nothing is pending.
    assert colored["labels_pending"] is False
    assert [label["color"] for label in colored["record"]["pull"]["labels"]] == [None, None]


@pytest.mark.parametrize(
    ("part", "answer"),
    [
        ("", (400, "invalid_part")),
        ("pull/7", (400, "invalid_part")),
        ("../body", (400, "invalid_part")),
        ("body/1", (400, "invalid_part")),
        ("review/", (400, "invalid_part")),
        (f"issue_comment/{'1' * 21}", (400, "invalid_part")),
        # A part's name is judged before anything is read, so these two reach the next
        # check, which finds no GitHub repository.
        ("body", (409, "not_github")),
        ("review_comment/1", (409, "not_github")),
    ],
)
def test_the_markdown_route_names_a_part_before_it_reads_anything(
    part: str, answer: tuple[int, str]
) -> None:
    nothing = PullView(number=7, host=None, pin=None, pin_ref=None, refreshing=False, kept=None)
    status, body = asyncio.run(render_part(nothing, part))
    assert (status, body["code"]) == answer


def test_a_core_description_and_its_record_share_one_render(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A text renders by its part, its page, and itself, not by when it was read (mb-d59o).

    The record that follows a core preview usually carries the same description. Keyed by
    the core's ``observed_at`` and the record's ``fetched_at``, the two asked the Markdown
    child for two renders of one text, so the record's could not join the core's in flight.
    """

    from types import SimpleNamespace

    from metabrowser.builtin_plugins.github import pull_markdown, pull_text_render

    fixtures = Path(__file__).parent / "fixtures" / "github-pull-page-responses.json"
    recorded = json.loads(fixtures.read_text(encoding="utf-8"))
    record = PullRecord.model_validate(recorded["current"]["body"]["record"])
    asked: list[Any] = []

    class Child:
        async def render_inert(self, request: Any) -> dict[str, Any]:
            asked.append(request)
            return {"html": "<p>rendered</p>"}

    cached: list[Any] = ["not_cached", record]
    monkeypatch.setattr(pull_text_render, "shared_worker", Child)
    monkeypatch.setattr(pull_markdown.kpress_adapter, "document_stylesheets", dict)
    monkeypatch.setattr(
        pull_markdown, "cached_pull_record", lambda *_: (cached.pop(0), None, "f" * 64)
    )
    preview: Any = {
        "pull": record.pull.model_dump(mode="json"),
        "observed_at": "2026-09-17T11:59:00Z",
        "revision": "a" * 64,
    }

    async def core() -> Any:
        return preview

    view = PullView(
        number=7,
        host=SimpleNamespace(pulls=SimpleNamespace(home=Path(), slug="octo/demo")),  # pyright: ignore[reportArgumentType]
        pin=None,
        pin_ref=None,
        refreshing=False,
        kept=None,
    )
    early = asyncio.run(render_part(view, "body", current_core=core))
    later = asyncio.run(render_part(view, "body", current_core=core))
    assert (early[0], early[1]["core_revision"], later[0], later[1]["record_revision"]) == (
        200,
        "a" * 64,
        200,
        "f" * 64,
    )
    assert record.fetched_at != preview["observed_at"]
    assert len(asked) == 2
    assert asked[0].flight_key == asked[1].flight_key


def test_the_envelope_carries_the_status_its_verdict_and_checks_beside_the_record(
    pinned_pull: tuple[_Stand, TestClient],
) -> None:
    stand, client = pinned_pull
    answered = _read(client, 7)
    envelope = answered.json()
    head = envelope["record"]["pull"]["head"]["sha"]
    assert envelope["status"]["head"] == envelope["checks"]["head"] == head
    readiness = envelope["readiness"]
    assert (readiness["verdict"], readiness["head"]) == ("checks_pending", head)
    assert [row["kind"] for row in readiness["requirements"]] == ["conflicts", "checks", "reviews"]
    assert envelope["status_unavailable"] is None
    assert "readiness" not in envelope["record"]
    etag = answered.headers["etag"]
    assert _read(client, 7, etag=etag).status_code == 304
    # A newer read of the same head moves its observed_at, and so the tag.
    status = PullStatus.model_validate(envelope["status"])
    later = status.model_copy(update={"observed_at": "2026-09-17T12:05:00Z"})
    repository = ListedRepository(stand.published.home, stand.published.slug, "octo", "demo")
    assert write_pull_status(repository, later)
    moved = _read(client, 7, etag=etag)
    assert moved.status_code == 200 and moved.headers["etag"] != etag
    assert moved.json()["status"]["observed_at"] == "2026-09-17T12:05:00Z"
    # One for another head is kept and shown, and judges nothing: the verdict is checking.
    pushed = later.model_copy(update={"head": "f" * 40, "observed_at": "2026-09-17T12:06:00Z"})
    assert write_pull_status(repository, pushed)
    other = _read(client, 7, etag=moved.headers["etag"])
    assert other.status_code == 200
    assert other.json()["readiness"] == {
        "verdict": "checking",
        "tone": "attention",
        "label": "Checking",
        "head": head,
        "observed_at": None,
        "requirements": [],
        "auto_merge": None,
        "auto_merge_summary": None,
    }


def test_a_record_that_is_gone_or_replaced_stops_being_answered(
    pinned_pull: tuple[_Stand, TestClient],
) -> None:
    """The route keeps a parsed record in memory, and only while its file is the same."""

    stand, client = pinned_pull

    def answers() -> tuple[tuple[str, str | None, Any], tuple[int, str | None]]:
        envelope = _read(client, 7).json()
        text = client.get("/api/plugin/github/pull-markdown", params={"number": 7, "part": "body"})
        return (
            (envelope["state"], envelope["reason"], envelope["record"]),
            (text.status_code, text.json().get("code")),
        )

    read, rendered = answers()
    assert (read[0], rendered) == ("current", (200, None)) and read[2] is not None
    record = stand.published.home / source_pull_record(stand.published.slug, 7)
    elsewhere = stand.tmp_path / "elsewhere.json"
    record.rename(elsewhere)
    assert answers() == (("absent", "not_cached", None), (404, "not_cached"))
    # A link to the same bytes is not the record: the cache reads regular files only.
    record.symlink_to(elsewhere)
    assert answers() == (("absent", "unreadable", None), (404, "unreadable"))


def test_the_markdown_route_drops_the_kpress_icon_sprite(
    pinned_pull: tuple[_Stand, TestClient], monkeypatch: pytest.MonkeyPatch
) -> None:
    from metabrowser import kpress_adapter

    # KPress puts its icon sprite (several KB of SVG symbols) in every render. A long
    # conversation must not carry one copy per text, so the route answers none. The route
    # renders in the Markdown child, so KPress's own render of the text is made here.
    stand, client = pinned_pull
    record = stand.record(7)
    assert isinstance(record, PullRecord)
    raw = kpress_adapter.render_kpress_view(
        source_text=record.pull.body or "",
        source_path="pull-7-body.md",
        kind="markdown",
        view="document",
        ext=".md",
        mtime_hash="sprite",
        size=0,
        include_toc="off",
        plain_code=True,
    )
    assert "<symbol" in str(raw["html"])
    answered = client.get("/api/plugin/github/pull-markdown", params={"number": 7, "part": "body"})
    # A refusal names its code in the body; indexing it would say only that a key is missing.
    assert answered.status_code == 200, answered.text
    html = answered.json()["html"]
    for gone in ("<svg", "<symbol", "<use"):
        assert gone not in html, gone


def test_the_markdown_route_keeps_a_mermaid_block_for_the_page_to_draw(
    pinned_pull: tuple[_Stand, TestClient],
) -> None:
    """A text's Mermaid fence reaches the page as GitHub's fallback markup, the one block it
    draws as an image (pull-page.js, `drawTextDiagrams`); any other fence stays code."""

    stand, client = pinned_pull
    record = stand.record(7)
    assert isinstance(record, PullRecord)
    text = "Two boxes:\n\n```mermaid\nflowchart LR\n  A --> B\n```\n\n```python\nx = 1\n```\n"
    write_pull_record(
        stand.published.home,
        stand.published.slug,
        record.model_copy(update={"pull": record.pull.model_copy(update={"body": text})}),
    )
    answered = client.get("/api/plugin/github/pull-markdown", params={"number": 7, "part": "body"})
    # A refusal names its code in the body; indexing it would say only that a key is missing.
    assert answered.status_code == 200, answered.text
    html = answered.json()["html"]
    assert '<pre lang="mermaid"><code>flowchart LR\n  A --&gt; B\n</code></pre>' in html
    assert (html.count("<pre"), html.count("lang=")) == (2, 1)


def test_the_markdown_route_names_only_kpress_stylesheets_and_the_same_ones_for_any_text(
    pinned_pull: tuple[_Stand, TestClient],
) -> None:
    """A page sets a text in KPress's stylesheets; a comment must not choose what it loads."""

    _stand, client = pinned_pull
    answered = client.get("/api/plugin/github/pull-markdown", params={"number": 7, "part": "body"})
    assert answered.status_code == 200, answered.text
    answer = answered.json()
    assets = answer["assets"]["assets"]
    assert {asset["id"] for asset in assets} >= {"css/document.css", "css/components.css"}
    assert {asset["loading"] for asset in assets} == {"stylesheet"}
    assert "import_map" not in answer["assets"]
    # Computed once, from no text at all.
    from metabrowser import kpress_adapter

    assert answer["assets"] == kpress_adapter.document_stylesheets()


def test_harden_keeps_the_allowlist_and_is_idempotent() -> None:
    from metabrowser.inert_html import harden

    base = "https://github.com/o/r/pull/1"
    source = (
        '<p class="x">a &amp; b &lt;c&gt; <code class="language-py">x</code></p>'
        '<img alt="&quot;q&quot;"><ol start="3" id="o"><li>i</li></ol>'
        '<table><tr><td colspan="2" rowspan="100" align="CENTER" style="x">t</td></tr></table>'
        '<details open data-x="1"><summary>s</summary>d</details><custom-tag>kept text</custom-tag>'
    )
    once = harden(source, base)
    assert once == (
        '<p>a &amp; b &lt;c&gt; <code>x</code></p><span class="mb-image-fallback">"q"</span>'
        '<ol start="3"><li>i</li></ol>'
        '<table><tr><td colspan="2" align="center">t</td></tr></table>'
        "<details open><summary>s</summary>d</details>kept text"
    )
    assert harden(once, base) == once


# ── Review hardening: degraded parts, oversized pages, and typed failures ──


def test_unreadable_optional_fields_are_left_empty_and_items_left_out(stand: _Stand) -> None:
    answers = scenario(stand.origin)
    comments = page("repos/octo/demo/issues/7/comments")
    comment = answers["api"][comments]["body"][0]
    odd = [{**comment, "user": {"login": "not a login"}}, {**comment, "id": "seven"}]
    answers = _api(answers, comments, ok(comments, odd))
    stand.answer(answers)
    record = stand.refresh(7)
    assert [comment.author for comment in record.issue_comments] == [None]
    assert record.truncated.issue_comments


def test_a_record_reads_no_checks_so_refused_check_pages_change_nothing(stand: _Stand) -> None:
    """Whether a pull request conflicts and how its checks stand are its status's, read
    with GraphQL: the full read asks neither check page, so a token without checks access
    leaves the record whole, and its status is read all the same."""

    answers = scenario(stand.origin)
    head = stand.origin["fork_head"]
    checks = page(f"repos/octo/demo/commits/{head}/check-runs")
    status_path = page(f"repos/octo/demo/commits/{head}/status")
    answers = _api(answers, checks, {"status": 403, "body": {"message": "Resource not accessible"}})
    answers = _api(answers, status_path, {"status": 422, "body": {"message": "No commit found"}})
    stand.answer(answers)
    record = stand.refresh(7)
    assert record.unavailable == {} and record.comparison is not None
    asked = [" ".join(call["args"]) for call in stand.calls()]
    assert not any("/commits/" in call for call in asked)
    assert sum("query=query PullStatus(" in call for call in asked) == 1
    assert set(record.model_dump()) >= {"pull", "issue_comments", "reviews", "review_comments"}
    assert not {"check_runs", "status"} & set(record.model_dump())
    assert "mergeable" not in record.pull.model_dump()


def _status_calls(stand: _Stand) -> list[str]:
    return [
        call["args"][call["args"].index("-F") + 1]
        for call in stand.calls()
        if any(arg.startswith("query=query PullStatus(") for arg in call["args"])
    ]


def test_a_refresh_keeps_the_status_beside_the_record_and_out_of_it(stand: _Stand) -> None:
    """The status is read after the record is published, and kept apart from it."""

    record = stand.refresh(7)
    assert _status_calls(stand) == ["number=7"]
    kept = kept_status(stand.published.home, stand.published.slug, 7)
    assert kept.status is not None and kept.checks is not None and kept.unavailable is None
    assert kept.status.head == kept.checks.head == record.pull.head.sha
    assert (kept.status.merge_state, kept.status.checks.state) == ("blocked", "pending")
    assert {item.name for item in kept.checks.items} == {
        "tests (3.13)",
        "docs",
        "docs/readthedocs.org:demo",
    }
    # The record is what it was before there was a status: nothing of it lives there.
    assert stand.record(7) == record and "merge_state" not in record.model_dump_json()


def test_a_status_read_github_refuses_leaves_the_record_and_the_status_before_it(
    stand: _Stand,
) -> None:
    first = stand.refresh(7)
    home, slug = stand.published.home, stand.published.slug
    before = kept_status(home, slug, 7)
    stand.monkeypatch.setattr(pulls, "utc_now", lambda: FETCHED_AT + timedelta(minutes=5))
    path = "graphql:status:7:start"
    stand.answer(_api(scenario(stand.origin), path, {"status": 502, "body": {"message": "bad"}}))
    record = stand.refresh(7)
    assert record.fetched_at > first.fetched_at
    assert pulls.last_refresh(stand.published, 7).outcome == "succeeded"  # pyright: ignore[reportOptionalMemberAccess]
    kept = kept_status(home, slug, 7)
    assert (kept.status, kept.checks) == (before.status, before.checks)
    assert kept.unavailable is not None and kept.unavailable != "succeeded"


def test_the_prefetch_leaves_the_status_to_the_page(stand: _Stand) -> None:
    """A record nobody is looking at reads no status: the prefetch's caps leave it out."""

    async def speculative() -> PullRecord:
        with gh_budget.speculative():
            return await pulls.refresh_pull_request(stand.published, 7)

    asyncio.run(speculative())
    assert _status_calls(stand) == []
    assert kept_status(stand.published.home, stand.published.slug, 7).status is None


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
    monkeypatch.setattr(gh_lists, "EXTRA_PAGE_REQUESTS", 0)
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


def test_a_fetch_that_cannot_write_one_ref_writes_none(stand: _Stand) -> None:
    """The head is not left in the store beside a base branch Git could not update."""

    mirrored = "refs/remotes/origin/topic"
    _move_origin_ref(stand, "refs/heads/topic", stand.origin["draft_head"])
    # Git cannot take the base branch's lock while a directory has the lock's name.
    (stand.published.git_dir / f"{mirrored}.lock").mkdir(parents=True)
    with pytest.raises(PullDataError) as refused:
        stand.refresh(7)
    # The whole message: Git's own, which names the lock's path in the home, is not in it.
    assert (refused.value.state, str(refused.value)) == (
        "fetch_failed",
        "Git could not fetch the pull request",
    )
    assert asyncio.run(ref_commit(stand.published, "refs/pull/7/head")) is None
    assert asyncio.run(ref_commit(stand.published, mirrored)) == stand.origin["topic"]


def test_a_pull_requests_fetch_brings_no_tags(stand: _Stand) -> None:
    """A tag pointing into what is fetched would otherwise follow it into the store, where
    a tag is a name the mirror resolves; only the mirror's own update changes those."""

    _move_origin_ref(stand, "refs/tags/follows-the-head", stand.origin["fork_head"])
    stand.refresh(7)
    head = asyncio.run(ref_commit(stand.published, "refs/pull/7/head"))
    assert head == stand.origin["fork_head"]
    assert asyncio.run(ref_commit(stand.published, "refs/tags/follows-the-head")) is None


@pytest.mark.parametrize("number", [8, 9])
def test_only_an_open_pull_requests_refresh_fetches_its_base_branch(
    stand: _Stand, number: int
) -> None:
    """A merged or closed one compares from ``base.sha``, so it has no reason to move the
    mirror's branch, which a reader's pin may name. An open one compares from that branch."""

    mirrored = "refs/remotes/origin/topic"
    _move_origin_ref(stand, "refs/heads/topic", stand.origin["draft_head"])
    assert stand.refresh(number).pull.state == "closed"
    assert asyncio.run(ref_commit(stand.published, mirrored)) == stand.origin["topic"]
    assert stand.refresh(7).pull.state == "open"
    assert asyncio.run(ref_commit(stand.published, mirrored)) == stand.origin["draft_head"]


def test_a_git_failure_is_reported_without_gits_own_text(
    stand: _Stand, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Git's message can name a path inside the application home; the refusal never does."""

    said = f"fatal: unable to read {stand.published.git_dir}/packed-refs"
    git = pull_refs.run_git

    async def failing(args: list[str], **kwargs: Any) -> bytes:
        if "show-ref" in args:
            raise GitError(said)
        return await git(args, **kwargs)

    monkeypatch.setattr(pull_refs, "run_git", failing)
    with pytest.raises(PullDataError) as refused:
        stand.refresh(7)
    message = "a Git command failed while reading it (--log-level debug shows Git's own message)"
    assert (refused.value.state, str(refused.value)) == ("git_failed", message)
    # The stamp is what the route and the next command show of it.
    stamp = read_pull_refresh(stand.published.home, stand.published.slug, 7)
    assert stamp is not None and (stamp.outcome, stamp.message) == ("git_failed", message)


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
    first, _, first_revision = pull_route.cached_pull_record(home, slug, 7)
    again, _, again_revision = pull_route.cached_pull_record(home, slug, 7)
    assert again is first and reads == [7] and again_revision == first_revision
    stand.refresh(7)
    pull_route.cached_pull_record(home, slug, 7)
    assert reads == [7, 7]


# ── served beside the mirror: the fetch lock, the refresh route, and serve mode ──

_JSON = {"content-type": "application/json"}
_REFRESH_ROUTE = "/api/plugin/github/pull-refresh"
_ASK_7 = {"number": 7, "retry": True}


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
    """A failing refresh is tried once a window, by this server and by the next command."""

    window = FRESHNESS_WINDOW_S
    assert served_pull(stand.published, 7).is_stale(FETCHED_AT, window_s=window)
    stand.refresh(7)
    served = served_pull(stand.published, 7)
    assert served.key == f"{stand.published.store_key}:pull/7"
    assert served.last is not None and served.last["outcome"] == "succeeded"
    assert not served.is_stale(FETCHED_AT + timedelta(seconds=window), window_s=window)
    later = FETCHED_AT + timedelta(seconds=window + 1)
    assert served.is_stale(later, window_s=window)

    # gh goes missing. The server's refresh fails and keeps how it ended beside the
    # record, where the next command reads it.
    monkeypatch.setattr(pulls, "utc_now", lambda: later)
    monkeypatch.setattr("metabrowser.builtin_plugins.github.gh.gh_executable", lambda: None)
    asyncio.run(served.refresh({"record"}))
    for tried in (served, served_pull(stand.published, 7)):
        assert tried.last is not None and tried.last["outcome"] == "gh_missing"
        assert tried.fetched_at == "2026-09-17T12:00:00Z"
        # Asked a moment ago, so gh is not asked again within the window.
        assert not tried.is_stale(later, window_s=window)
        assert tried.is_stale(later + timedelta(seconds=window + 1), window_s=window)


def test_after_a_rate_limit_no_automatic_attempt_runs_before_it_lifts(stand: _Stand) -> None:
    """``reset_at`` is obeyed, and not only reported; a limit with no reset waits a window."""

    window = FRESHNESS_WINDOW_S
    tried_at = FETCHED_AT + timedelta(hours=1)
    lifts_at = tried_at + timedelta(minutes=10)
    stamp = "%Y-%m-%dT%H:%M:%SZ"
    write_pull_refresh(
        stand.published.home,
        stand.published.slug,
        7,
        PullRefreshStamp(
            outcome="rate_limited",
            message="API rate limit exceeded",
            reset_at=lifts_at.strftime(stamp),
            at=tried_at.strftime(stamp),
        ),
        expected=read_pull_record(stand.published.home, stand.published.slug, 7),
    )
    limited = served_pull(stand.published, 7)
    past_the_window = tried_at + timedelta(seconds=window + 1)
    assert not limited.is_stale(past_the_window, window_s=window)
    assert not limited.is_stale(lifts_at - timedelta(seconds=1), window_s=window)
    assert limited.is_stale(lifts_at, window_s=window)

    assert limited.last is not None
    limited.last = {**limited.last, "reset_at": None}
    assert not limited.is_stale(tried_at, window_s=window)
    assert limited.is_stale(past_the_window, window_s=window)
    # Only a rate limit holds a refresh back past the window.
    limited.last = {**limited.last, "outcome": "gh_failed", "reset_at": lifts_at.strftime(stamp)}
    assert limited.is_stale(past_the_window, window_s=window)


def test_the_set_gives_one_state_for_a_number_and_keeps_a_bounded_number(stand: _Stand) -> None:
    """The numbers are request text, so memory is bounded, oldest first. The attended pull
    request and one whose refresh is running are never dropped, because something still
    writes to their state, and a second object for the number would miss it."""

    async def scenario() -> None:
        pulls_set = ServedPulls(stand.published)
        assert pulls_set.held(1) is None, "held reads nothing"
        attended = await pulls_set.attend(1)
        assert await pulls_set.companion(1) is attended
        running = await pulls_set.companion(2)
        running._refreshing = True  # pyright: ignore[reportPrivateUsage]
        oldest = await pulls_set.companion(3)
        for number in range(4, MAX_KEPT_PULLS + 1):
            await pulls_set.companion(number)
        assert pulls_set.held(MAX_KEPT_PULLS) is not None, "at the bound, nothing has gone"
        assert pulls_set.held(3) is oldest, "and asking for one renews it"
        await pulls_set.companion(MAX_KEPT_PULLS + 1)
        # Past the bound: 4 is now the oldest that may go, after 1 and 2, which may not.
        assert pulls_set.held(1) is attended and pulls_set.held(2) is running
        assert pulls_set.held(3) is oldest
        assert pulls_set.held(4) is None
        # Read again from disk, it is a new state, and the set still holds the bound.
        assert (await pulls_set.companion(4)).number == 4
        kept = [n for n in range(1, MAX_KEPT_PULLS + 2) if pulls_set.held(n) is not None]
        assert len(kept) == MAX_KEPT_PULLS
        assert pulls_set.key(9) == f"{stand.published.store_key}:pull/9"

    asyncio.run(scenario())


def test_a_pull_request_head_is_pinned_by_its_ref(stand: _Stand) -> None:
    stand.refresh(7)
    target = repository_store_target(git_dir=stand.published.git_dir)
    resolved = asyncio.run(resolve_pin(target, ref="refs/pull/7/head"))
    assert (resolved.commit_oid, resolved.ref) == (stand.origin["fork_head"], "refs/pull/7/head")
    for ref in ("refs/pull/0/head", "refs/pull/7/merge", "refs/pull/x/head", "refs/heads/topic"):
        with pytest.raises(InvalidSelectionError):
            asyncio.run(resolve_pin(target, ref=ref))


def test_a_commit_is_pinned_under_the_head_of_any_pull_request_it_is_the_tip_of(
    stand: _Stand,
) -> None:
    """View file on any pull request's Files changed switches by commit ID. The newest pull
    request wins by number, not by the text of its ref, and a ref the server was serving
    comes before any of them."""

    target = repository_store_target(git_dir=stand.published.git_dir)
    merged = stand.origin["merged_head"]
    assert asyncio.run(resolve_pin(target, oid=merged)).ref is None
    stand.refresh(8)
    assert asyncio.run(resolve_pin(target, oid=merged)).ref == "refs/pull/8/head"

    def also_at(ref: str) -> None:
        subprocess.run(
            ["git", "--git-dir", str(stand.published.git_dir), "update-ref", ref, merged],
            check=True,
        )

    # "9" sorts after "123" as text, and "refs/pull/200/merge" is no pull request's head.
    for ref in ("refs/pull/9/head", "refs/pull/123/head", "refs/pull/200/merge"):
        also_at(ref)
    assert asyncio.run(resolve_pin(target, oid=merged)).ref == "refs/pull/123/head"
    kept = asyncio.run(resolve_pin(target, oid=merged, keep_refs=("refs/pull/9/head",)))
    assert kept.ref == "refs/pull/9/head"
    # A commit no head has is served under no ref, as before.
    assert asyncio.run(resolve_pin(target, oid=stand.origin["topic"])).ref is None


def test_a_switch_by_commit_is_served_under_the_ref_it_names(
    pinned_pull: tuple[_Stand, TestClient],
) -> None:
    """View on branch switches by commit ID and names its pull request's head ref, so of two
    pull requests that share a head the page's own is the one served. A ref the commit is
    not the tip of is refused, as is a name no pin could be under."""

    stand, client = pinned_pull
    merged = stand.origin["merged_head"]
    stand.refresh(8)
    subprocess.run(
        [
            "git",
            "--git-dir",
            str(stand.published.git_dir),
            "update-ref",
            "refs/pull/12/head",
            merged,
        ],
        check=True,
    )

    def switch(body: dict[str, str]) -> Any:
        return client.post("/api/source/pin", json=body, headers=_JSON)

    newest = switch({"oid": merged})
    assert newest.status_code == 200, newest.text
    assert newest.json()["status"]["ref"] == "refs/pull/12/head"
    named = switch({"oid": merged, "under": "refs/pull/8/head", "view": "/view/"})
    assert named.status_code == 200, named.text
    assert (named.json()["changed"], named.json()["status"]["ref"]) == (True, "refs/pull/8/head")
    assert named.json()["view_href"] == "/view/"
    # The pull request's ref is elsewhere: the commit is the tip of pull request 7's head,
    # which the server would otherwise serve it under, and nothing is switched.
    elsewhere = switch({"oid": stand.origin["fork_head"], "under": "refs/pull/8/head"})
    assert (elsewhere.status_code, elsewhere.json()["code"]) == (409, "ref_moved")
    served = client.get("/api/source/status").json()
    assert (served["pin"], served["ref"]) == (merged, "refs/pull/8/head")
    for body in (
        {"ref": "refs/pull/8/head", "under": "refs/pull/8/head"},
        {"oid": merged, "under": "refs/pull/8/merge"},
        {"oid": merged, "under": "refs/heads/topic"},
        {"oid": merged, "under": 8},
    ):
        refused = client.post("/api/source/pin", json=body, headers=_JSON)
        assert refused.status_code == 400, (body, refused.text)
        assert refused.json()["code"] == "invalid_selection"


def test_a_switch_under_a_pull_requests_head_that_moved_on_switches_nothing(
    pinned_pull: tuple[_Stand, TestClient],
) -> None:
    """Review M1 on #511: a Changes diff drawn for an earlier head keeps View on branch.

    Its switch, and Browse code on a page whose record is as old, names that earlier head
    under ``refs/pull/7/head``, which is now at the newer one. Served under no ref, the
    page would land on a bare commit under a tooltip that called it this pull request's
    head; the route refuses with ``ref_moved``, says why in words, and the pin stays.
    """

    stand, client = pinned_pull
    earlier, head = stand.origin["fork_earlier"], stand.origin["fork_head"]
    away = client.post("/api/source/pin", json={"oid": stand.origin["topic"]}, headers=_JSON)
    assert away.status_code == 200, away.text
    before = client.get("/api/source/status").json()

    refused = client.post(
        "/api/source/pin",
        json={"oid": earlier, "under": "refs/pull/7/head", "view": "/view/"},
        headers=_JSON,
    )
    assert refused.status_code == 409, refused.text
    assert refused.json() == {
        "error": "refs/pull/7/head is no longer at that commit",
        "code": "ref_moved",
    }
    after = client.get("/api/source/status").json()
    assert (after["generation"], after["pin"], after["ref"]) == (
        before["generation"],
        stand.origin["topic"],
        before["ref"],
    )
    # The head the ref is at now is the pull request's, and is served under it.
    current = client.post(
        "/api/source/pin", json={"oid": head, "under": "refs/pull/7/head"}, headers=_JSON
    )
    assert current.status_code == 200, current.text
    assert current.json()["status"]["ref"] == "refs/pull/7/head"


def test_the_refresh_route_starts_or_joins_one_job(
    pinned_pull: tuple[_Stand, TestClient], monkeypatch: pytest.MonkeyPatch
) -> None:
    _stand, client = pinned_pull
    session = mirror_session(app)
    served = None if session is None else session.companion
    assert isinstance(served, ServedPull)
    release = threading.Event()
    runs: list[int] = []

    async def held(_asks: object) -> None:
        runs.append(7)
        # The job stays running until the test thread sets it.
        await held_until(release, 30)

    monkeypatch.setattr(served, "refresh", held)
    first = client.post(_REFRESH_ROUTE, json=_ASK_7, headers=_JSON)
    assert (first.status_code, first.headers["cache-control"]) == (202, "no-store")
    body = first.json()
    assert (body["refresh"], body["pull"]["number"], body["pull"]["refreshing"]) == (
        "started",
        7,
        True,
    )
    assert client.post(_REFRESH_ROUTE, json=_ASK_7, headers=_JSON).json()["refresh"] == "joined"
    assert _read(client, 7).json()["refreshing"] is True
    assert client.get("/api/source/status").json()["refreshing"] is True
    release.set()
    settle(client)
    assert runs == [7]
    assert _read(client, 7).json()["refreshing"] is False


def test_the_refresh_route_refuses_what_is_not_a_refresh_request(
    pinned_pull: tuple[_Stand, TestClient],
) -> None:
    _stand, client = pinned_pull
    assert client.get(_REFRESH_ROUTE).status_code == 405
    for content, status in (
        (b"[]", 400),
        (b"{", 400),
        (b'{"x": "' + b"y" * 2000 + b'"}', 413),
        # The number is required, whole, and within what a pull request's number can be.
        (b"{}", 400),
        (b'{"retry": true}', 400),
        (b'{"number": "7"}', 400),
        (b'{"number": true}', 400),
        (b'{"number": 0}', 400),
        (b'{"number": 7.5}', 400),
        (b'{"number": 10000000000}', 400),
        (b'{"number": 7, "retry": "yes"}', 400),
        (b'{"number": 7, "comparison": true}', 400),
        (b'{"number": 7, "prepare_comparison": null}', 400),
        (b'{"number": 7, "prepare_comparison": true}', 400),
        (b'{"number": 7, "prepare_comparison": "abc"}', 400),
        (b'{"number": 7, "retry": true, "prepare_comparison": "' + b"a" * 64 + b'"}', 400),
        (b'{"number": 7, "retry": true, "comparison": "yes"}', 400),
        (b'{"number": 7, "state": "open"}', 400),
        # The record an asker holds is named by its whole revision, and not while idle.
        (b'{"number": 7, "held": null}', 400),
        (b'{"number": 7, "held": "abc"}', 400),
        (b'{"number": 7, "held": 7}', 400),
        (
            b'{"number": 7, "held": "'
            + b"a" * 64
            + b'", "prepare_comparison": "'
            + b"a" * 64
            + b'"}',
            400,
        ),
    ):
        refused = client.post(_REFRESH_ROUTE, content=content, headers=_JSON)
        assert (refused.status_code, refused.json()["code"]) == (status, "invalid_request")
    # The application's own guards: another origin, a body not declared as JSON, and a
    # page for a pin the server no longer serves.
    other = {**_JSON, "origin": "https://example.invalid"}
    assert client.post(_REFRESH_ROUTE, json=_ASK_7, headers=other).status_code == 403
    plain = {"content-type": "text/plain"}
    assert client.post(_REFRESH_ROUTE, content=b"{}", headers=plain).status_code == 415
    outdated = client.post(_REFRESH_ROUTE, json=_ASK_7, headers={**_JSON, PIN_HEADER: "0" * 40})
    assert (outdated.status_code, outdated.json()["code"]) == (409, "pin_changed")


def test_a_refresh_answer_leaves_out_the_record_its_asker_holds(
    pinned_pull: tuple[_Stand, TestClient],
) -> None:
    """An ask that names the record it holds gets every field but that record (mb-jd08).

    A visible page asks every ``probe_every_s``; what the whole envelope cost each time
    is recorded beside ``pull_route.refresh_answer_pull``.
    """

    _stand, client = pinned_pull

    def ask(**fields: Any) -> tuple[int, dict[str, Any]]:
        answer = client.post(_REFRESH_ROUTE, json={"number": 7, **fields}, headers=_JSON)
        return answer.status_code, answer.json()["pull"]

    status, whole = ask()
    assert status == 200 and whole["record"]["number"] == 7 and "record_held" not in whole
    revision = whole["record_revision"]

    status, held = ask(held=revision)
    assert status == 200 and held["record_held"] is True and "record" not in held
    # Everything else an envelope says still arrives: the state, the verdict, the outcome.
    assert set(held) - {"record_held"} == set(whole) - {"record"}
    assert (held["record_revision"], held["state"], held["fetched_at"]) == (
        revision,
        whole["state"],
        whole["fetched_at"],
    )
    # The answer is smaller by the record, and by nothing else: the status, its verdict,
    # and the checks are not the record's, and change without it.
    saved = len(json.dumps(whole)) - len(json.dumps(held))
    assert abs(saved - len(json.dumps(whole["record"]))) < 32
    assert held["checks"] == whole["checks"] and held["readiness"] == whole["readiness"]

    # Another revision is a record the asker does not have, so it is sent.
    status, other = ask(held="0" * 64)
    assert status == 200 and other["record"] == whole["record"] and "record_held" not in other

    # A reader's own refresh may name it too, and its answer as it starts holds that record.
    status, started = ask(retry=True, held=revision)
    assert status == 202 and started["record_held"] is True and "record" not in started


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
        patch(
            "metabrowser.cli.serve.listen_on_available_local_port", return_value=listener_on(8411)
        ),
    ):
        result = CliRunner().invoke(_app, [url, "--no-open"])
    if result.exit_code == 0:
        assert server_class.call_args.args[0].app is app
    return result


def test_a_served_pull_request_pins_its_head_and_refreshes_beside_the_mirror(
    stand: _Stand, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Serve mode: the cold read pins the head, the pull route answers, a refresh runs in
    the coordinator, and the pin follows a newer head that refresh finds (mb-6a6w)."""

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
            status = settle(client)
            assert (status["pin"], status["pull_request"], status["stale"]) == (earlier, 7, False)
            envelope = _read(client, 7).json()
            assert (envelope["state"], envelope["pin"]) == ("current", earlier)
            assert envelope["record"]["pull"]["head"]["sha"] == earlier

            _move_pull_head(stand, head)
            stand.answer(scenario(stand.origin))
            started = client.post(_REFRESH_ROUTE, json=_ASK_7, headers=_JSON)
            assert started.status_code == 202 and started.json()["pull"]["refreshing"] is True
            status = settle(client)
            # The pull request's own job observed the mirror when it ended, and the pin,
            # served under the pull request's head, went with the ref it had just fetched.
            assert (status["follows"], status["ref"]) == (True, "refs/pull/7/head")
            assert (status["pin"], status["latest"]) == (head, head)
            envelope = _read(client, 7).json()
            assert envelope["last_refresh"]["outcome"] == "succeeded"
            assert (envelope["pin"], envelope["record"]["pull"]["head"]["sha"]) == (head, head)

            # A page drawn for the earlier head asks for the ref, which changes nothing now.
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
        git_repo.clear_repo_cache()


def test_a_commit_pinned_by_its_id_stays_when_the_pull_request_it_heads_moves(
    stand: _Stand, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A commit opened by its ID stays put, also while it is a pull request's head.

    The mirror names such a pin by the pull request whose head it is, so the selector can
    say so, but the reader asked for a commit: the next push must not move it, and a pull
    request they never opened is not attended, so nothing probes it (A2 of review A on
    #745, reproduced as the review did: from a page on the branch, with no pull request
    attended, pin the head by ID and refresh). The newer head is reported as ``latest``.
    A request that names the ref, as Browse code and View on branch do with ``under``,
    follows it.
    """

    monkeypatch.setattr("metabrowser.cli.git_pin_cli.stop_on_interrupt", lambda: None)
    monkeypatch.setattr(pulls, "utc_now", lambda: datetime.now(UTC).replace(microsecond=0))
    earlier, head = stand.origin["fork_earlier"], stand.origin["fork_head"]
    _move_pull_head(stand, earlier)
    stand.answer(_answering_head(stand, earlier))

    def pin(client: TestClient, body: dict[str, str]) -> dict[str, Any]:
        answer = client.post("/api/source/pin", json=body, headers=_JSON)
        assert answer.status_code == 200, answer.text
        return answer.json()["status"]

    try:
        result = _serve(CANONICAL)
        assert result.exit_code == 0, result.output
        with TestClient(app) as client:
            assert settle(client)["pull_request"] is None
            assert client.post(_REFRESH_ROUTE, json=_ASK_7, headers=_JSON).status_code == 202
            _until(client, 7)
            by_id = pin(client, {"oid": earlier})
            assert (by_id["pin"], by_id["ref"]) == (earlier, "refs/pull/7/head")
            assert (by_id["follows"], by_id["pull_request"]) == (False, None)

            _move_pull_head(stand, head)
            stand.answer(scenario(stand.origin))
            assert client.post(_REFRESH_ROUTE, json=_ASK_7, headers=_JSON).status_code == 202
            deadline = time.monotonic() + 30
            while _read(client, 7).json()["record"]["pull"]["head"]["sha"] != head:
                assert time.monotonic() < deadline, "the refresh did not read the newer head"
                time.sleep(0.01)
            _until(client, 7)
            status = client.get("/api/source/status").json()
            assert (status["pin"], status["latest"]) == (earlier, head)
            assert (status["follows"], status["pull_request"]) == (False, None)

            named = pin(client, {"oid": head, "under": "refs/pull/7/head"})
            assert (named["pin"], named["follows"], named["pull_request"]) == (head, True, 7)
    finally:
        serve_mirror(None)
        git_repo.clear_repo_cache()


def test_a_record_another_process_published_moves_the_pin_on_that_pull_requests_head(
    stand: _Stand, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Two servers on one store: the one that only reads the other's record follows too.

    The other process's refresh fetched the newer head into the shared store and wrote the
    record. This server ran no job, so nothing observed the mirror; the read that adopts
    the record asks for that (A7 of review A on #745).
    """

    monkeypatch.setattr("metabrowser.cli.git_pin_cli.stop_on_interrupt", lambda: None)
    monkeypatch.setattr(pulls, "utc_now", lambda: datetime.now(UTC).replace(microsecond=0))
    earlier, head = stand.origin["fork_earlier"], stand.origin["fork_head"]
    _move_pull_head(stand, earlier)
    stand.answer(_answering_head(stand, earlier))
    try:
        result = _serve(f"{CANONICAL}/pull/7")
        assert result.exit_code == 0, result.output
        with TestClient(app) as client:
            assert settle(client)["pin"] == earlier
            _move_pull_head(stand, head)
            stand.answer(scenario(stand.origin))
            time.sleep(1.1)  # A record's time has one-second resolution; this one is newer.
            assert stand.refresh(7).pull.head.sha == head
            assert client.get("/api/source/status").json()["pin"] == earlier
            assert _read(client, 7).json()["record"]["pull"]["head"]["sha"] == head
            deadline = time.monotonic() + 30
            while client.get("/api/source/status").json()["pin"] != head:
                assert time.monotonic() < deadline, "the pin did not follow the adopted head"
                time.sleep(0.01)
    finally:
        serve_mirror(None)
        git_repo.clear_repo_cache()


def test_a_switch_by_commit_id_back_to_the_head_keeps_the_pull_requests_ref(
    stand: _Stand, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A commit asked for by its ID alone: the merge base, and back to the head.

    Back on the head, the server serves it under ``refs/pull/7/head`` again, so the
    selector names the pull request rather than a bare commit, also after a branch was
    served in between. Asked for by ID, the head stays put (``follows`` is false) and the
    attended pull request stays the one the URL named: only a request that names the ref,
    as View on branch does with ``under``, follows it (A2 of review A, B5 of review B on
    #745).
    """

    monkeypatch.setattr("metabrowser.cli.git_pin_cli.stop_on_interrupt", lambda: None)
    monkeypatch.setattr(pulls, "utc_now", lambda: datetime.now(UTC).replace(microsecond=0))
    head = stand.origin["fork_head"]
    try:
        result = _serve(f"{CANONICAL}/pull/7")
        assert result.exit_code == 0, result.output
        with TestClient(app) as client:
            assert settle(client)["ref"] == "refs/pull/7/head"
            base = _read(client, 7).json()["record"]["comparison"]["base"]

            def pin(body: dict[str, str]) -> dict[str, Any]:
                answer = client.post("/api/source/pin", json=body, headers=_JSON)
                assert answer.status_code == 200, answer.text
                return answer.json()["status"]

            at_base = pin({"oid": base})
            assert (at_base["pin"], at_base["ref"], at_base["pull_request"]) == (base, None, 7)
            at_head = pin({"oid": head})
            assert (at_head["pin"], at_head["ref"]) == (head, "refs/pull/7/head")
            assert (at_head["follows"], at_head["pull_request"]) == (False, 7)
            # A branch served in between is the ref last served; the head is still the
            # pull request's.
            assert pin({"ref": DEFAULT_BRANCH})["ref"] == f"refs/remotes/origin/{DEFAULT_BRANCH}"
            assert pin({"oid": base})["ref"] is None
            again = pin({"oid": head})
            assert (again["pin"], again["ref"]) == (head, "refs/pull/7/head")
            assert (again["follows"], again["pull_request"]) == (False, 7)
    finally:
        serve_mirror(None)
        git_repo.clear_repo_cache()


def test_a_changes_url_anchoring_one_file_is_served_at_that_file(
    stand: _Stand, monkeypatch: pytest.MonkeyPatch
) -> None:
    """GitHub's `#diff-<sha256 of the path>` opens the file it names on the Changes tab.

    The first open fetches the record, whose comparison lists the changed files; an
    anchor that names none of them opens the tab itself, and the banner says why.
    """

    monkeypatch.setattr("metabrowser.cli.git_pin_cli.stop_on_interrupt", lambda: None)
    app_txt = path_digest("src/app.txt")
    try:
        result = _serve(f"{CANONICAL}/pull/7/files#diff-{app_txt}R2")
        assert result.exit_code == 0, result.output
        served = next(line for line in result.stdout.splitlines() if line.startswith("Serving "))
        assert served.split()[3] == "http://127.0.0.1:8411/pull/7/files/src/app.txt"
        assert "Selection: pull_request files\nFile: src/app.txt\n" in result.stdout
        assert "Diff line: R2 (the Changes tab opens at the file, not the line)\n" in (
            result.stdout
        )
        with TestClient(app) as client:
            assert client.get("/pull/7/files/src/app.txt").status_code == 200
    finally:
        serve_mirror(None)
        git_repo.clear_repo_cache()
    try:
        result = _serve(f"{CANONICAL}/pull/7/files#diff-{path_digest('README.md')}")
        assert result.exit_code == 0, result.output
        served = next(line for line in result.stdout.splitlines() if line.startswith("Serving "))
        assert served.split()[3] == "http://127.0.0.1:8411/pull/7/files"
        note = next(line for line in result.stdout.splitlines() if line.startswith("File: "))
        assert note.startswith("File: not resolved: no file pull request 7 changes ")
        assert note.endswith("(file_not_changed); opening the Changes tab")
    finally:
        serve_mirror(None)
        git_repo.clear_repo_cache()


def test_a_pin_on_another_pull_requests_head_makes_it_the_attended_one(
    pinned_pull: tuple[_Stand, TestClient],
) -> None:
    """Status and staleness follow the pull request the code on screen belongs to, and a
    branch leaves the attended one as it was, since a way back to it is still its head."""

    stand, client = pinned_pull
    stand.refresh(8)
    session = mirror_session(app)
    assert session is not None
    assert client.get("/api/source/status").json()["pull_request"] == 7

    def pin(body: dict[str, str]) -> dict[str, Any]:
        answer = client.post("/api/source/pin", json=body, headers=_JSON)
        assert answer.status_code == 200, answer.text
        return answer.json()["status"]

    assert pin({"ref": "refs/pull/8/head"})["pull_request"] == 8
    attended = session.companion
    assert isinstance(attended, ServedPull) and attended.number == 8
    assert attended.key == f"{stand.published.store_key}:pull/8"
    assert pin({"ref": DEFAULT_BRANCH})["pull_request"] == 8
    assert session.companion is attended
    assert pin({"ref": "refs/pull/7/head"})["pull_request"] == 7
    # A switch by commit ID alone is named by the head it is, and attends nothing new: the
    # reader opened a commit. Naming the head too, as View on branch does, attends it.
    by_commit = pin({"oid": stand.origin["merged_head"]})
    assert (by_commit["ref"], by_commit["pull_request"]) == ("refs/pull/8/head", 7)
    assert by_commit["follows"] is False
    # The same commit asked for by the head's name is the same pin, which now follows the
    # head and attends its pull request.
    flipped = pin({"ref": "refs/pull/8/head"})
    assert (flipped["pin"], flipped["pull_request"], flipped["follows"]) == (
        stand.origin["merged_head"],
        8,
        True,
    )
    assert pin({"ref": "refs/pull/7/head"})["pull_request"] == 7
    assert pin({"ref": DEFAULT_BRANCH})["follows"] is True
    named = pin({"oid": stand.origin["merged_head"], "under": "refs/pull/8/head"})
    assert (named["ref"], named["pull_request"], named["follows"]) == ("refs/pull/8/head", 8, True)


def _serving_repository_url(stand: _Stand, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("metabrowser.cli.git_pin_cli.stop_on_interrupt", lambda: None)
    result = _serve(CANONICAL)
    assert result.exit_code == 0, result.output


def _gh_reads(stand: _Stand) -> list[list[str]]:
    return [call["args"] for call in stand.calls() if call["args"][:1] == ["api"]]


def test_on_a_repository_url_only_a_readers_action_adds_a_pull_request_to_the_cache(
    stand: _Stand, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The checkpoint, and the rule behind it: a read, a link, and a request that is not a
    reader's own run no gh and write nothing, and a reader's Fetch opens the page.

    The fake gh's log and the source's directory are the evidence. A folder's guarantee is
    the import boundary; this is what holds on a mirror, where gh is always one call away.
    """

    stand.calls()
    home, slug = stand.published.home, stand.published.slug
    pulls_dir = (home / source_pull_record(slug, 8)).parent
    try:
        _serving_repository_url(stand, monkeypatch)
        stand.calls()
        with TestClient(app) as client:
            settle(client)
            assert client.get("/pull/8").status_code == 200
            before = sorted(pulls_dir.iterdir()) if pulls_dir.exists() else []
            for _ in range(2):
                assert _read(client, 8).json()["reason"] == "not_cached"
            markdown = client.get(
                "/api/plugin/github/pull-markdown", params={"number": 8, "part": "body"}
            )
            assert (markdown.status_code, markdown.json()["code"]) == (404, "not_cached")
            automatic = client.post(_REFRESH_ROUTE, json={"number": 8}, headers=_JSON)
            assert (automatic.status_code, automatic.json()["refresh"]) == (200, "not_cached")
            assert automatic.json()["pull"]["refreshing"] is False
            for _ in range(10):
                assert not client.get("/api/source/status").json()["refreshing"]
            assert _gh_reads(stand) == []
            assert (sorted(pulls_dir.iterdir()) if pulls_dir.exists() else []) == before

            fetched = client.post(_REFRESH_ROUTE, json={"number": 8, "retry": True}, headers=_JSON)
            assert (fetched.status_code, fetched.json()["refresh"]) == (202, "started")
            assert fetched.json()["pull"]["state"] == "pending"
            while _read(client, 8).json()["refreshing"]:
                time.sleep(0.01)
            page = _read(client, 8).json()
            assert (page["state"], page["record"]["pull"]["number"]) == ("current", 8)
            assert any("pulls/8" in " ".join(args) for args in _gh_reads(stand))
            # Files changed compares the pull request's own commits, whatever is pinned.
            assert client.get(page["comparison_route"]).status_code == 200
            # Opening it moved no pin, and left the status naming no pull request.
            status = client.get("/api/source/status").json()
            assert (status["pull_request"], status["ref"]) == (
                None,
                f"refs/remotes/origin/{DEFAULT_BRANCH}",
            )
    finally:
        serve_mirror(None)
        git_repo.clear_repo_cache()


def test_an_automatic_request_refreshes_a_record_once_a_window_and_waits_for_a_rate_limit(
    stand: _Stand, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Each number is held to one attempt per window, and a rate limit to its reset; a
    reader's own request is not held to either."""

    stand.refresh(8)
    now = [FETCHED_AT]
    monkeypatch.setattr(pulls, "utc_now", lambda: now[0])

    def ask(client: TestClient, **fields: Any) -> tuple[int, str]:
        answer = client.post(_REFRESH_ROUTE, json={"number": 8, **fields}, headers=_JSON)
        while _read(client, 8).json()["refreshing"]:
            time.sleep(0.01)
        return answer.status_code, answer.json()["refresh"]

    try:
        _serving_repository_url(stand, monkeypatch)
        with TestClient(app) as client:
            settle(client)
            assert ask(client) == (200, "not_due"), "just fetched"
            now[0] = FETCHED_AT + timedelta(seconds=FRESHNESS_WINDOW_S + 1)
            assert ask(client) == (202, "started"), "stale"
            assert _read(client, 8).json()["state"] == "current"
            assert ask(client) == (200, "not_due")

            # A failing refresh: asked again only after a window.
            stand.answer({**scenario(stand.origin), "api_failure": {"stderr": "x\n", "exit": 1}})
            now[0] += timedelta(seconds=FRESHNESS_WINDOW_S + 1)
            assert ask(client) == (202, "started")
            assert _read(client, 8).json()["last_refresh"]["outcome"] != "succeeded"
            assert ask(client) == (200, "not_due")
            assert ask(client, retry=True) == (202, "started"), "a reader is not held to it"
            now[0] += timedelta(seconds=FRESHNESS_WINDOW_S + 1)

            # A rate limit: past the window, and still not due until it lifts.
            lifts_at = now[0] + timedelta(minutes=30)
            path = "repos/octo/demo/pulls/8"
            stand.answer(
                _api(
                    scenario(stand.origin),
                    path,
                    {
                        "status": 403,
                        "headers": {
                            "X-Ratelimit-Remaining": "0",
                            "X-Ratelimit-Reset": str(int(lifts_at.timestamp())),
                        },
                        "body": {"message": "API rate limit exceeded"},
                    },
                )
            )
            assert ask(client) == (202, "started")
            last = _read(client, 8).json()["last_refresh"]
            assert (last["outcome"], last["reset_at"]) == (
                "rate_limited",
                lifts_at.strftime("%Y-%m-%dT%H:%M:%SZ"),
            )
            now[0] += timedelta(seconds=FRESHNESS_WINDOW_S + 1)
            assert ask(client) == (200, "not_due"), "past the window, before the reset"
            now[0] = lifts_at
            stand.answer(scenario(stand.origin))
            assert ask(client) == (202, "started"), "the limit has lifted"
            assert _read(client, 8).json()["state"] == "current"
    finally:
        serve_mirror(None)
        git_repo.clear_repo_cache()


def test_past_the_bound_on_jobs_a_request_is_refused_and_starts_nothing(
    pinned_pull: tuple[_Stand, TestClient], monkeypatch: pytest.MonkeyPatch
) -> None:
    """A number already running is joined at the bound. The attended pull request's refresh
    is never refused, and a job that ends makes room. Asserted over the jobs that ran, with
    no gh, since what is bounded is starting them."""

    _stand, client = pinned_pull
    gate = threading.Event()
    ran: list[int] = []

    async def waiting(served: ServedPull, _asks: object) -> None:
        ran.append(served.number)
        await held_until(gate, 30)

    monkeypatch.setattr(ServedPull, "refresh", waiting)

    def ask(number: int) -> tuple[int, str]:
        answer = client.post(_REFRESH_ROUTE, json={"number": number, "retry": True}, headers=_JSON)
        return answer.status_code, answer.json()["refresh"]

    first_past = 100 + MAX_PULL_JOBS
    for number in range(100, first_past):
        assert ask(number) == (202, "started")
    assert ask(first_past) == (429, "too_many")
    refused = client.post(
        _REFRESH_ROUTE, json={"number": first_past, "retry": True}, headers=_JSON
    ).json()
    assert refused["code"] == "too_many" and refused["pull"]["refreshing"] is False
    assert ask(100) == (202, "joined"), "a number already running is joined at the bound"
    session = mirror_session(app)
    assert session is not None
    assert client.portal is not None
    assert client.portal.call(_attended_refresh, session) == "started"
    assert _read(client, first_past).json()["refreshing"] is False
    gate.set()
    while (
        _read(client, 100 + MAX_PULL_JOBS - 1).json()["refreshing"]
        or _read(client, 7).json()["refreshing"]
    ):
        time.sleep(0.01)
    assert ask(first_past) == (202, "started"), "the jobs ended, so there is room"
    while _read(client, first_past).json()["refreshing"]:
        time.sleep(0.01)
    assert sorted(ran) == sorted({*range(100, first_past), 7, first_past})
    assert len(ran) == MAX_PULL_JOBS + 2, "one job for each"


async def _attended_refresh(session: Any) -> Any:
    return session.request_companion_refresh("due")


def test_on_a_real_session_a_queue_of_pull_requests_delays_neither_the_mirror_nor_the_attended(
    pinned_pull: tuple[_Stand, TestClient], monkeypatch: pytest.MonkeyPatch
) -> None:
    """Through the routes, with the real mirror and the real set, and only the time a refresh
    takes held on a gate: both go next after the job running, whatever is queued."""

    _stand, client = pinned_pull
    ran: list[object] = []
    release = threading.Semaphore(0)

    async def waiting(served: ServedPull, _asks: object) -> None:
        ran.append(served.number)
        await held_until(release, 30)

    original = StoreMirror.refresh

    async def recording(self: StoreMirror) -> Any:
        ran.append("mirror")
        await held_until(release, 30)
        return await original(self)

    monkeypatch.setattr(ServedPull, "refresh", waiting)
    monkeypatch.setattr(StoreMirror, "refresh", recording)

    def wait_for(count: int) -> None:
        deadline = time.monotonic() + 30
        while len(ran) < count and time.monotonic() < deadline:
            time.sleep(0.01)
        assert len(ran) >= count, ran

    def ask(number: int) -> None:
        answer = client.post(_REFRESH_ROUTE, json={"number": number, "retry": True}, headers=_JSON)
        assert answer.status_code == 202, answer.text

    for number in (100, 101, 102):
        ask(number)
    wait_for(1)
    # A reader's own request for the fetch a commit waits for: the attended job and the mirror's.
    fetch = client.post("/api/source/refresh", json={"for": "commit", "retry": True}, headers=_JSON)
    assert fetch.status_code == 202, fetch.text
    time.sleep(0.2)
    assert ran == [100], "the store has one job at a time"
    for count in range(2, 6):
        release.release()
        wait_for(count)
    release.release()
    session = mirror_session(app)
    assert session is not None
    while session.pull_refreshing(102) or session.pull_refreshing(7) or session.refreshing():
        time.sleep(0.01)
    assert ran == [100, 7, "mirror", 101, 102]


def test_the_attended_pull_request_may_run_one_over_the_bound_and_no_more(
    pinned_pull: tuple[_Stand, TestClient], monkeypatch: pytest.MonkeyPatch
) -> None:
    """Through the page's route as through the freshness row's, the attended number is not
    refused because other numbers filled the bound. It is one over the bound and not one per
    attended switch: past that it is refused like any other, and asking again finds room."""

    _stand, client = pinned_pull
    gate = threading.Event()
    ran: list[int] = []

    async def waiting(served: ServedPull, _asks: object) -> None:
        ran.append(served.number)
        await held_until(gate, 30)

    monkeypatch.setattr(ServedPull, "refresh", waiting)

    def ask(number: int) -> tuple[int, str]:
        answer = client.post(_REFRESH_ROUTE, json={"number": number, "retry": True}, headers=_JSON)
        return answer.status_code, answer.json()["refresh"]

    session = mirror_session(app)
    assert session is not None and client.portal is not None
    assert client.get("/api/source/status").json()["pull_request"] == 7
    for number in range(100, 100 + MAX_PULL_JOBS):
        assert ask(number) == (202, "started")
    assert ask(100 + MAX_PULL_JOBS) == (429, "too_many")
    assert ask(7) == (202, "started"), "the attended number, at the bound, on the page's route"
    assert ask(7) == (202, "joined")

    # Each switch onto another head used to start one more job past the bound.
    for number in (8, 9, 10):
        client.portal.call(session.attend, number)
        assert client.portal.call(_attended_refresh, session) == "too_many"
        assert ask(number) == (429, "too_many")
        assert _read(client, number).json()["refreshing"] is False

    # A source refresh that would refresh only that pull request says so, and starts nothing.
    monkeypatch.setattr(session, "_fetch_on_miss", True)
    monkeypatch.setattr(type(session), "_mirror_stale", lambda _self, _now: False)
    refused = client.post("/api/source/refresh", json={}, headers=_JSON)
    assert refused.status_code == 429, refused.text
    assert (refused.json()["refresh"], refused.json()["code"]) == ("too_many", "too_many")
    assert refused.json()["status"]["pull_request"] == 10
    assert session.pull_refreshing(10) is False

    gate.set()
    while any(session.pull_refreshing(number) for number in (*range(100, 100 + MAX_PULL_JOBS), 7)):
        time.sleep(0.01)
    assert sorted(ran) == sorted({*range(100, 100 + MAX_PULL_JOBS), 7}), "nothing past the bound"
    assert client.portal.call(_attended_refresh, session) == "started", "there is room now"
    while session.pull_refreshing(10):
        time.sleep(0.01)


# ── What a job reads, whoever started it (mb-ucnu) ─────────────


def _gated_mirror_fetch(monkeypatch: pytest.MonkeyPatch) -> threading.Event:
    """Hold the mirror's fetch, and with it the store's turn, until the event is set."""

    release = threading.Event()
    original = StoreMirror.refresh

    async def gated(self: StoreMirror) -> Any:
        await held_until(release, 30)
        return await original(self)

    monkeypatch.setattr(StoreMirror, "refresh", gated)
    return release


def _at(monkeypatch: pytest.MonkeyPatch, seconds: float) -> datetime:
    """Move the server's clocks, the record's and the mirror's, *seconds* past the fetch."""

    now = FETCHED_AT + timedelta(seconds=seconds)
    monkeypatch.setattr(pulls, "utc_now", lambda: now)
    monkeypatch.setattr("metabrowser.mirror_refresh._now_utc", lambda: now)
    return now


def _quiet(session: Any, numbers: Iterable[int] = (7,)) -> None:
    deadline = time.monotonic() + 30
    while session.refreshing() or any(session.pull_refreshing(number) for number in numbers):
        assert time.monotonic() < deadline, "a refresh did not finish"
        time.sleep(0.01)


def _read_the_record(calls: list[str]) -> bool:
    """Whether pull request 7's record was read: its REST pull, which a read of the status
    alone never asks for."""

    return any(call.startswith("gh api repos/octo/demo/pulls/7") for call in calls)


def test_a_source_refresh_for_a_due_status_reads_nothing_once_a_hold_is_noted_before_its_turn(
    pinned_pull: tuple[_Stand, TestClient], monkeypatch: pytest.MonkeyPatch
) -> None:
    """The attended pull request's status alone is due, so the source's refresh starts its
    job beside the mirror's fetch, and the job waits behind that fetch for its turn at the
    store. A rate-limit hold noted meanwhile holds the status and the record alike. The job
    was asked for what was due and none of it still is, so it reads nothing; it read the
    record in full, as an ask for the record would have."""

    stand, client = pinned_pull
    # Past the status's window, and inside the record's while a probe vouches for it.
    now = _at(monkeypatch, FRESHNESS_WINDOW_S + 1)
    session = mirror_session(app)
    assert session is not None and client.portal is not None
    companion = session.companion
    assert isinstance(companion, ServedPull)

    def only_the_status_due() -> tuple[bool, bool]:
        companion.checks_due = True
        companion.probed_at = now.strftime("%Y-%m-%dT%H:%M:%SZ")
        return (
            companion.status_due(now),
            companion.record_due(now, window_s=companion.record_window(now)),
        )

    assert client.portal.call(only_the_status_due) == (True, False)
    release = _gated_mirror_fetch(monkeypatch)
    logged_gh_calls(stand.tmp_path)
    answer = client.post("/api/source/refresh", json={}, headers=_JSON)
    assert answer.status_code == 202, answer.text
    assert session.pull_refreshing(7), "the status alone was due, so its job started"
    client.portal.call(partial(gh_budget.hold, "2026-09-17T13:00:00Z", now=now))
    release.set()
    _quiet(session)
    assert logged_gh_calls(stand.tmp_path) == []


def test_a_pages_ask_that_joins_a_job_for_the_record_leaves_it_reading_the_record(
    pinned_pull: tuple[_Stand, TestClient], monkeypatch: pytest.MonkeyPatch
) -> None:
    """A page's ask probes the pull request and finds its checks changed, and by then a
    reader's retry of a commit fetch has started its job, which waits behind the mirror's
    fetch for its turn at the store; the page's ask joins it. The retry asked for the
    record, which is what brings a newer head, so the job reads the record and its status
    after it, whoever joined. It read the status alone, as the page's ask would have."""

    from metabrowser.builtin_plugins.github import served_pull as served_module

    stand, client = pinned_pull
    # After the status was last read, so a change a probe finds in it is due.
    _at(monkeypatch, 5)
    # The probe is held below for as long as the test takes, not the page's usual wait.
    monkeypatch.setattr(served_module, "PROBE_WAIT_S", 30)
    session = mirror_session(app)
    assert session is not None
    probing, probed = threading.Event(), threading.Event()

    async def probe(*_args: object, **_kwargs: object) -> pulls.PullProbe:
        probing.set()
        await held_until(probed, 30)
        return pulls.PullProbe("checks_changed", {})

    monkeypatch.setattr(pulls, "probe_pull_request", probe)
    release = _gated_mirror_fetch(monkeypatch)
    fetch = client.post("/api/source/refresh", json={}, headers=_JSON)
    assert fetch.status_code == 202, fetch.text
    assert not session.pull_refreshing(7), "nothing of the pull request was due"
    logged_gh_calls(stand.tmp_path)
    answers: list[str] = []

    def page_ask() -> None:
        answer = client.post(_REFRESH_ROUTE, json={"number": 7}, headers=_JSON)
        answers.append(answer.json()["refresh"])

    page = threading.Thread(target=page_ask, name="page-ask")
    page.start()
    try:
        assert probing.wait(30), "the page's ask did not probe"
        retry = client.post(
            "/api/source/refresh", json={"for": "commit", "retry": True}, headers=_JSON
        )
        assert retry.status_code == 202, retry.text
        assert session.pull_refreshing(7)
    finally:
        probed.set()
        page.join(30)
    assert answers == ["joined"]
    release.set()
    _quiet(session)
    assert _read_the_record(logged_gh_calls(stand.tmp_path))


def test_a_pages_ask_refused_too_many_leaves_nothing_for_the_next_job(
    pinned_pull: tuple[_Stand, TestClient], monkeypatch: pytest.MonkeyPatch
) -> None:
    """Past the bound, a page's ask that found the status alone due is refused and starts
    nothing, and nothing of it is left for the pull request's next job: the reader's retry
    of a commit fetch that starts one later reads the record, as it asked. It read the
    status alone, as the refused ask would have."""

    stand, client = pinned_pull
    # After the status was last read, so a change a probe finds in it is due.
    _at(monkeypatch, 5)
    session = mirror_session(app)
    assert session is not None and client.portal is not None
    gate = threading.Event()
    queued = {*range(100, 100 + MAX_PULL_JOBS), 8}
    original = ServedPull.refresh

    async def held_or_read(served: ServedPull, *asks: Any) -> None:
        if served.number in queued:
            await held_until(gate, 30)
            return
        await original(served, *asks)

    async def checks_changed(*_args: object, **_kwargs: object) -> pulls.PullProbe:
        return pulls.PullProbe("checks_changed", {})

    monkeypatch.setattr(ServedPull, "refresh", held_or_read)
    monkeypatch.setattr(pulls, "probe_pull_request", checks_changed)

    def ask(number: int, **fields: Any) -> str:
        answer = client.post(_REFRESH_ROUTE, json={"number": number, **fields}, headers=_JSON)
        return answer.json()["refresh"]

    for number in range(100, 100 + MAX_PULL_JOBS):
        assert ask(number, retry=True) == "started"
    # The attended pull request's one place past the bound is held by an earlier attended.
    client.portal.call(session.attend, 8)
    assert ask(8, retry=True) == "started"
    client.portal.call(session.attend, 7)
    logged_gh_calls(stand.tmp_path)
    assert ask(7) == "too_many"
    gate.set()
    _quiet(session, queued)
    retry = client.post("/api/source/refresh", json={"for": "commit", "retry": True}, headers=_JSON)
    assert retry.status_code == 202, retry.text
    _quiet(session)
    assert _read_the_record(logged_gh_calls(stand.tmp_path))


def test_a_commit_url_newer_than_the_record_refreshes_the_pull_request_to_serve_it(
    stand: _Stand, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Only the pull request's refresh fetches refs/pull/7/head, which brings the commit."""

    monkeypatch.setattr("metabrowser.cli.git_pin_cli.stop_on_interrupt", lambda: None)
    earlier, head = stand.origin["fork_earlier"], stand.origin["fork_head"]
    _move_pull_head(stand, earlier)
    stand.answer(_answering_head(stand, earlier))
    stand.refresh(7)
    _move_pull_head(stand, head)
    stand.answer(scenario(stand.origin))
    stand.calls()
    try:
        result = _serve(f"{CANONICAL}/pull/7/commits/{head[:7]}")
        assert result.exit_code == 0, result.output
        assert f"Revision: {head}" in result.stdout
        reads = [call for call in stand.calls() if call["args"][:1] == ["api"]]
        assert reads, "the pull request was read again"
        with TestClient(app) as client:
            status = client.get("/api/source/status").json()
            assert (status["pin"], status["selection_state"]) == (head, None)
    finally:
        serve_mirror(None)
        git_repo.clear_repo_cache()


def test_a_base_branch_folded_by_case_is_put_back(
    stand: _Stand, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The mirror update's check and restore wrap the pull request's fetch too.

    A fold needs a filesystem that ignores case, so the check is told it found one. The
    fetch and the restore are Git's: the base branch the fetch advanced is back.
    """

    async def ignores_case(target: Any) -> bool:
        return True

    monkeypatch.setattr(pull_refs, "store_ignores_case", ignores_case)
    monkeypatch.setattr(pull_refs, "folded_refs", lambda **_: ("refs/remotes/origin/x",))
    _move_origin_ref(stand, "refs/heads/topic", stand.origin["draft_head"])
    with pytest.raises(PullDataError) as folded:
        stand.refresh(7)
    assert folded.value.state == "fetch_failed" and "letter case" in str(folded.value)
    mirrored = asyncio.run(ref_commit(stand.published, "refs/remotes/origin/topic"))
    assert mirrored == stand.origin["topic"]


def test_gh_runs_in_a_group_the_stop_path_can_kill(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A gh that is still answering when the server stops is killed, and then forgotten."""

    pid_file = tmp_path / "gh-pid"
    started = tmp_path / "gh-started"
    gh = tmp_path / "bin" / "gh"
    gh.parent.mkdir()
    # Only shell builtins before the exec, so the group never holds a second process. An
    # external `mv` here was still running when the stop came, and killed as an orphan it
    # stayed in the group until init reaped it, so the group outlived the stop on CI.
    gh.write_text(
        f'#!/bin/sh\necho $$ > "{pid_file}"\n: > "{started}"\nexec sleep 50\n',
        encoding="utf-8",
    )
    gh.chmod(0o755)
    monkeypatch.setenv("PATH", f"{gh.parent}{os.pathsep}{os.environ['PATH']}")

    async def stopped_while_asking() -> int:
        asking = asyncio.ensure_future(gh_account())
        deadline = time.monotonic() + 20
        while not started.exists():
            assert time.monotonic() < deadline, "gh did not start"
            await asyncio.sleep(0.01)
        pid = int(pid_file.read_text(encoding="utf-8"))
        # gh can start before its spawn returns and registers the group, and a stop in
        # that window is stop_process_groups' case, which kill_live_process_groups leaves
        # alone: stopped then, gh ran on to its own deadline, as it did on 3.14t in CI run
        # 44032890807. This test is of a gh still answering, so it waits for the group.
        while pid not in git_process._LIVE_PROCESS_GROUPS:
            assert time.monotonic() < deadline, "gh's group was never registered"
            await asyncio.sleep(0.01)
        try:
            # The leader of a group of its own, so the kill cannot reach this process.
            assert os.getpgid(pid) == pid != os.getpgid(0)
            kill_live_process_groups()
            # Ended by the signal, not by gh's own deadline, which is a different error.
            with pytest.raises(GhError, match=f"gh exited -{signal.SIGKILL.value} "):
                await asyncio.wait_for(asking, 20)
        finally:
            with contextlib.suppress(ProcessLookupError):
                os.kill(pid, signal.SIGKILL)
        return pid

    pid = asyncio.run(stopped_while_asking())
    with pytest.raises(ProcessLookupError):
        os.killpg(pid, 0)
    assert pid not in git_process._LIVE_PROCESS_GROUPS


# ── final review: case folds, bad stamps, one-shot judgment, commit pins ──


def test_a_base_branch_the_store_spells_otherwise_is_neither_fetched_nor_compared_from(
    stand: _Stand, monkeypatch: pytest.MonkeyPatch
) -> None:
    """``Feature/x`` kept as ``feature/x``: writing it would pass for a fold, so base.sha."""

    async def ignores_case(target: Any) -> bool:
        return True

    async def listed(target: Any) -> dict[str, str]:
        return {"refs/remotes/origin/feature/x": stand.origin["base"]}

    specs: list[list[str]] = []
    git = pull_refs.run_git

    async def recording(args: list[str], **kwargs: Any) -> bytes:
        if "fetch" in args:
            specs.append([arg for arg in args if arg.startswith("+")])
        return await git(args, **kwargs)

    monkeypatch.setattr(pull_refs, "store_ignores_case", ignores_case)
    monkeypatch.setattr(pull_refs, "mirror_refs", listed)
    monkeypatch.setattr(pull_refs, "run_git", recording)
    published = stand.published
    assert not asyncio.run(pull_refs.base_branch_usable(published, "Feature/x"))
    assert asyncio.run(pull_refs.base_branch_usable(published, "feature/x"))
    head = asyncio.run(pull_refs.fetch_pull_head(published, 7, base_branch="Feature/x"))
    assert head == stand.origin["fork_head"]
    assert specs == [["+refs/pull/7/head:refs/pull/7/head"]]
    endpoints = asyncio.run(
        pull_refs.comparison_endpoints(
            published,
            head=stand.origin["fork_head"],
            base_sha=stand.origin["topic"],
            base_branch="Feature/x",
            open_pull=True,
        )
    )
    assert endpoints.base_from == "base_sha"


@pytest.mark.macos_tier
def test_a_base_branch_folded_on_disk_does_not_fail_the_record(stand: _Stand) -> None:
    """On a case-insensitive filesystem only: the store keeps ``Feature/x`` as ``feature/x``."""

    target = repository_store_target(git_dir=stand.published.git_dir)
    if not asyncio.run(store_ignores_case(target)):
        pytest.skip("the store's filesystem tells letter case apart")
    env = git_env(stand.tmp_path)
    store = str(stand.published.git_dir)
    origin = str(stand.tmp_path / "github-pull-origin.git")
    topic, base = stand.origin["topic"], stand.origin["base"]
    for git_dir, ref, oid in (
        (store, "refs/remotes/origin/feature/y", base),
        (store, "refs/remotes/origin/feature/x", base),
        (origin, "refs/heads/Feature/x", topic),
    ):
        subprocess.run(
            ["git", "--git-dir", git_dir, "update-ref", ref, oid],
            check=True,
            capture_output=True,
            env=env,
        )
    answers = scenario(stand.origin)
    path = "repos/octo/demo/pulls/7"
    body = answers["api"][path]["body"]
    moved = {**body, "base": {**body["base"], "ref": "Feature/x", "sha": topic}}
    stand.answer(_api(answers, path, ok(path, moved)))
    record = stand.refresh(7)
    assert record.comparison is not None and record.comparison.base_from == "base_sha"


def test_an_unusable_refresh_stamp_is_no_stamp(stand: _Stand) -> None:
    stand.refresh(7)
    home, slug = stand.published.home, stand.published.slug
    stamp = home / source_pull_refresh(slug, 7)
    stamp.write_text('{"outcome": "succeeded", "at": "2026-13-45T25:61:61Z"}', encoding="utf-8")
    assert read_pull_refresh(home, slug, 7) is None
    served = served_pull(stand.published, 7)
    assert served.last is None and served.fetched_at == "2026-09-17T12:00:00Z"


@pytest.mark.parametrize(
    ("status", "outcome"),
    [
        ({"last_refresh": {"outcome": "succeeded"}}, None),
        ({"last_refresh": {"outcome": "refreshing_elsewhere"}}, "refreshing_elsewhere"),
        ({"last_outcome": {"operation": "refresh", "outcome": "refreshing_elsewhere"}}, None),
        ({"last_outcome": {"operation": "refresh", "outcome": "fetch_failed"}}, "fetch_failed"),
    ],
)
def test_a_one_shot_refresh_is_judged_by_its_own_outcome(
    status: dict[str, Any], outcome: str | None
) -> None:
    from metabrowser.cli import api_cli
    from metabrowser.cli.asgi_client import ApiResponse

    after = ApiResponse(200, json.dumps({"refreshing": False, **status}).encode())
    judged = api_cli._refresh_outcome(after)  # pyright: ignore[reportPrivateUsage]
    assert judged == (False, outcome)


def test_a_one_shot_refresh_still_running_after_its_wait_is_an_error(tmp_path: Path) -> None:
    """The command's wait ran out, and leaving stops the refresh, so it did not finish;
    however the last one ended, that is not this one's success."""

    from metabrowser.cli import api_cli
    from metabrowser.cli.asgi_client import ApiResponse
    from metabrowser.errors import CLIError

    running = {"refreshing": True, "last_refresh": {"outcome": "succeeded"}}
    with pytest.raises(CLIError, match="did not finish"):
        api_cli._emit_api_response(  # pyright: ignore[reportPrivateUsage]
            "/api/plugin/github/pull-refresh",
            ApiResponse(202, b"{}"),
            "skipped",
            fmt="json",
            normalize_root=tmp_path,
            after=(
                "/api/plugin/github/pull?number=7",
                ApiResponse(200, json.dumps(running).encode()),
            ),
        )


def test_a_served_pull_requests_newer_commit_is_fetched_for_a_pin(
    stand: _Stand, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A server asked to pin a fork commit newer than the record refreshes the PR too."""

    monkeypatch.setattr("metabrowser.cli.git_pin_cli.stop_on_interrupt", lambda: None)
    monkeypatch.setattr(pulls, "utc_now", lambda: datetime.now(UTC).replace(microsecond=0))
    earlier, head = stand.origin["fork_earlier"], stand.origin["fork_head"]
    _move_pull_head(stand, earlier)
    stand.answer(_answering_head(stand, earlier))
    try:
        result = _serve(f"{CANONICAL}/pull/7")
        assert result.exit_code == 0, result.output
        with TestClient(app) as client:
            settle(client)
            _move_pull_head(stand, head)
            stand.answer(scenario(stand.origin))
            asked = client.post("/api/source/pin", json={"oid": head}, headers=_JSON)
            assert asked.status_code == 202, asked.text
            settle(client)
            taken = client.post("/api/source/pin", json={"oid": head}, headers=_JSON)
            assert taken.status_code == 200, taken.text
            assert taken.json()["status"]["pin"] == head
    finally:
        serve_mirror(None)
        git_repo.clear_repo_cache()


@pytest.mark.parametrize(
    ("value", "kept"),
    [
        (6, 6),
        (0, 0),
        (MAX_PULL_COMMITS, MAX_PULL_COMMITS),
        (MAX_PULL_COMMITS + 1, None),
        (-1, None),
        (True, None),
        ("6", None),
        (None, None),
    ],
)
def test_the_commit_count_is_kept_only_within_its_bound(value: object, kept: int | None) -> None:
    """A count outside the bound is dropped when GitHub sends it and refused in a record."""

    assert pulls._count(value) == kept
    if type(value) is int:
        recorded = read_recording("github-pull-page-responses.json")["current"]["body"]
        stored = {**recorded["record"]["pull"], "commits": value}
        if kept is None:
            with pytest.raises(ValidationError):
                PullRequest.model_validate(stored)
        else:
            assert PullRequest.model_validate(stored).commits == kept


def test_the_parts_are_in_flight_together_and_read_as_they_did_in_sequence(
    stand: _Stand, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Three requests at once, and a record whose bytes do not say in what order they answered."""
    real = gh_lists.gh_api
    running = 0
    most = 0
    seen: list[str] = []

    async def counted(path: str, **kwargs: Any) -> Any:
        nonlocal running, most
        running += 1
        most = max(most, running)
        seen.append(path)
        # Later parts answer sooner, the opposite of the order they were asked in.
        await asyncio.sleep(0.05 / len(seen))
        try:
            return await real(path, **kwargs)
        finally:
            running -= 1

    monkeypatch.setattr(gh_lists, "gh_api", counted)
    stand.answer(scenario(stand.origin))
    record = stand.refresh(7)
    assert most == 3, "the pull is read first, for its head, and then the other three together"
    assert seen[0] == "repos/octo/demo/pulls/7"
    # The ETags are written in the order the parts are named, whichever answered first.
    parts = ["/issues/7/comments", "/pulls/7/reviews", "/pulls/7/comments"]
    written = [next(i for i, part in enumerate(parts) if part in p) for p in list(record.etags)[1:]]
    assert written == sorted(written) and len(written) > 1


def test_the_first_refusal_in_order_is_the_one_raised(stand: _Stand) -> None:
    """A refusal reads as it did in sequence, whichever part got its answer first."""
    answers = scenario(stand.origin)
    refused = {"status": 404, "body": {"message": "Not Found"}}
    answers = _api(answers, page("repos/octo/demo/pulls/7/reviews"), refused)
    answers = _api(answers, page("repos/octo/demo/pulls/7/comments"), {"status": 500, "body": {}})
    stand.answer(answers)
    with pytest.raises(pulls.PullDataError) as raised:
        stand.refresh(7)
    assert raised.value.state == "not_found_or_private"


@pytest.mark.parametrize("attended", [False, True])
def test_pull_routes_require_a_number_before_reading_or_refreshing(
    pinned_pull: tuple[_Stand, TestClient], monkeypatch: pytest.MonkeyPatch, attended: bool
) -> None:
    stand, client = pinned_pull
    settle(client)
    if not attended:
        serve_mirror(None)
    stand.calls()

    def forbidden(*_args: Any, **_kwargs: Any) -> Any:
        raise AssertionError("a missing number must be refused before looking up a pull request")

    monkeypatch.setattr("metabrowser.builtin_plugins.github.pull_route.pull_host", forbidden)
    monkeypatch.setattr(ServedPulls, "companion", forbidden)
    monkeypatch.setattr(git_process, "run_git", forbidden)
    expected = {"error": '"number" is a pull-request number', "code": "invalid_request"}
    for route in ("pull", "pull-markdown?part=body"):
        response = client.get(f"/api/plugin/github/{route}")
        assert (response.status_code, response.json()) == (400, expected)
    for body in ({}, {"retry": True}, {"retry": False}):
        response = client.post(_REFRESH_ROUTE, json=body, headers=_JSON)
        assert (response.status_code, response.json()) == (400, expected)
    assert stand.calls() == []


@pytest.mark.parametrize("value", ["", "null", "true", "0", "-7", "7.0", "7x"])
def test_pull_routes_refuse_invalid_numbers(
    pinned_pull: tuple[_Stand, TestClient], value: str
) -> None:
    stand, client = pinned_pull
    stand.calls()
    for route in ("pull", "pull-markdown"):
        response = client.get(
            f"/api/plugin/github/{route}", params={"number": value, "part": "body"}
        )
        assert (response.status_code, response.json()["code"]) == (400, "invalid_request")
    for number in (None, value, True):
        response = client.post(_REFRESH_ROUTE, json={"number": number}, headers=_JSON)
        assert (response.status_code, response.json()["code"]) == (400, "invalid_request")
    assert stand.calls() == []


def test_duplicate_numbers_keep_the_last_value_rule(
    pinned_pull: tuple[_Stand, TestClient],
) -> None:
    stand, client = pinned_pull
    stand.calls()
    last = client.get("/api/plugin/github/pull?number=7&number=8")
    assert (last.status_code, last.json()["number"], last.json()["reason"]) == (
        200,
        8,
        "not_cached",
    )
    for route in ("pull", "pull-markdown"):
        refused = client.get(f"/api/plugin/github/{route}?number=7&number=&part=body")
        assert (refused.status_code, refused.json()["code"]) == (400, "invalid_request")
    accepted = client.post(_REFRESH_ROUTE, content=b'{"number": null, "number": 8}', headers=_JSON)
    assert (
        accepted.status_code,
        accepted.json()["refresh"],
        accepted.json()["pull"]["number"],
    ) == (200, "not_cached", 8)
    refused = client.post(_REFRESH_ROUTE, content=b'{"number": 7, "number": null}', headers=_JSON)
    assert (refused.status_code, refused.json()["code"]) == (400, "invalid_request")
    assert stand.calls() == []


@pytest.mark.parametrize("metadata_first", [False, True])
def test_pull_record_publications_serialize_both_writer_orderings(
    stand: _Stand, monkeypatch: pytest.MonkeyPatch, metadata_first: bool
) -> None:
    from threading import Event

    from metabrowser.builtin_plugins.github import pull_record
    from metabrowser.builtin_plugins.github.pull_list import ListedRepository
    from metabrowser.cache.locks import LockBusyError, source_alias_lock

    shared = stand.refresh(7)
    assert shared.comparison is not None
    metadata = shared.model_copy(update={"comparison": None, "unavailable": {}})
    initial = metadata.model_copy(
        update={"pull": metadata.pull.model_copy(update={"title": "initial"})}
    )
    write_pull_record(stand.published.home, stand.published.slug, initial)
    listed = ListedRepository(stand.published.home, stand.published.slug, "octo", "demo")
    first_record = metadata if metadata_first else shared
    second_record = shared if metadata_first else metadata
    first_record = first_record.model_copy(
        update={"pull": first_record.pull.model_copy(update={"title": "first"})}
    )
    second_record = second_record.model_copy(
        update={"pull": second_record.pull.model_copy(update={"title": "second"})}
    )
    entered, release, second_validated = Event(), Event(), Event()
    write = pull_record.write_private_file_atomic
    serialize = pull_record.serialize_pull_record

    def delayed(home: Path, relative_path: str, data: bytes) -> None:
        if json.loads(data)["pull"]["title"] == "first":
            entered.set()
            assert release.wait(10)
        write(home, relative_path, data)

    def validated(record: PullRecord) -> bytes:
        data = serialize(record)
        if record.pull.title == "second":
            second_validated.set()
        return data

    monkeypatch.setattr(pull_record, "write_private_file_atomic", delayed)
    monkeypatch.setattr(pull_record, "serialize_pull_record", validated)

    async def run() -> None:
        first = asyncio.create_task(
            pulls._write(listed if metadata_first else stand.published, first_record)
        )  # pyright: ignore[reportPrivateUsage]
        second = None
        try:
            assert await held_until(entered, 5)
            with (
                pytest.raises(LockBusyError),
                source_alias_lock(stand.published.home, stand.published.slug, blocking=False),
            ):
                pass
            assert await asyncio.to_thread(stand.record, 7) == initial, "readers wait for no lock"
            second = asyncio.create_task(
                pulls._write(stand.published if metadata_first else listed, second_record)
            )  # pyright: ignore[reportPrivateUsage]
            assert await held_until(second_validated, 5)
            assert not second.done(), "the other canonical writer bypassed the source lock"
            release.set()
            await asyncio.wait_for(first, 5)
            saved = await asyncio.wait_for(second, 5)
            assert saved.pull.title == "second"
            assert saved.comparison == shared.comparison
            assert "comparison" not in saved.unavailable
            assert await asyncio.to_thread(stand.record, 7) == saved
        finally:
            release.set()
            await first
            if second is not None:
                await second

    asyncio.run(run())


@pytest.mark.parametrize("metadata_only", [False, True])
def test_cancelled_pull_publication_does_not_write_after_its_lock_is_released(
    stand: _Stand, monkeypatch: pytest.MonkeyPatch, metadata_only: bool
) -> None:
    from threading import Event

    from metabrowser.builtin_plugins.github.pull_list import ListedRepository
    from metabrowser.cache import locks
    from tests.test_cache_async_locks import _BoundedHolder  # pyright: ignore[reportPrivateUsage]

    original = stand.refresh(7)
    changed = original.model_copy(
        update={"pull": original.pull.model_copy(update={"title": "abandoned"})}
    )
    published = (
        ListedRepository(stand.published.home, stand.published.slug, "octo", "demo")
        if metadata_only
        else stand.published
    )
    entered = Event()
    wait = locks._wait_for_flock  # pyright: ignore[reportPrivateUsage]

    def waiting(*args: Any, **kwargs: Any) -> None:
        entered.set()
        wait(*args, **kwargs)

    monkeypatch.setattr(locks, "_wait_for_flock", waiting)
    holder = _BoundedHolder(
        stand.published.home, f"locks.source_alias_lock(home, {stand.published.slug!r})"
    )
    try:

        async def cancel() -> None:
            job = asyncio.create_task(pulls._write(published, changed))  # pyright: ignore[reportPrivateUsage]
            assert await held_until(entered, 5)
            assert not job.done()
            job.cancel()
            with pytest.raises(asyncio.CancelledError):
                await asyncio.wait_for(job, 5)
            assert await asyncio.to_thread(stand.record, 7) == original

        asyncio.run(cancel())
        assert holder.release() == "asked", "cancellation waited for the other process to release"
    finally:
        holder.close()
    assert stand.record(7) == original
    saved = asyncio.run(pulls._write(published, changed))  # pyright: ignore[reportPrivateUsage]
    assert saved.pull.title == "abandoned" and stand.record(7) == saved


def test_metadata_publication_refits_after_merge_and_preserves_record_on_rename_failure(
    stand: _Stand, monkeypatch: pytest.MonkeyPatch
) -> None:
    from metabrowser.builtin_plugins.github import pull_record
    from metabrowser.builtin_plugins.github.pull_list import ListedRepository

    shared = stand.refresh(7)
    assert shared.comparison is not None
    unclaimed = stand.tmp_path / "unclaimed"
    with pytest.raises(FileNotFoundError, match="no source is published"):
        write_pull_record(unclaimed, stand.published.slug, shared)
    assert not unclaimed.exists()
    listed = ListedRepository(stand.published.home, stand.published.slug, "octo", "demo")
    limit = len(serialize_pull_record(shared)) + 1000
    monkeypatch.setattr(pull_record, "MAX_PULL_RECORD_BYTES", limit)
    # Consume the usual spare space to exercise merging at the exact byte budget.
    monkeypatch.setattr(pull_record, "_FLAG_SLACK_BYTES", 0)
    metadata = shared.model_copy(
        update={
            "comparison": None,
            "pull": shared.pull.model_copy(update={"body": "x" * MAX_BODY_BYTES}),
        }
    )
    merged = asyncio.run(pulls._write(listed, metadata))  # pyright: ignore[reportPrivateUsage]
    assert merged.comparison == shared.comparison
    assert merged.pull.body_truncated and len(serialize_pull_record(merged)) <= limit
    assert stand.record(7) == merged
    rename = os.replace
    target = stand.published.home / source_pull_record(stand.published.slug, 7)

    def refused(source: Any, destination: Any) -> None:
        if Path(destination) == target:
            raise PermissionError("private path detail")
        rename(source, destination)

    monkeypatch.setattr(os, "replace", refused)
    with pytest.raises(PullDataError) as error:
        asyncio.run(pulls._write(listed, metadata))  # pyright: ignore[reportPrivateUsage]
    assert error.value.state == "cache_unwritable"
    assert str(error.value) == (
        "the record of pull request #7 could not be written to the cache: the file system "
        "refused it. To clear the GitHub cache of octo/demo, run `echo '{}' | metab "
        "https://github.com/octo/demo --api /api/plugin/github/cache-clear --data -`, "
        "then retry"
    )
    assert "private path detail" not in str(error.value)
    assert stand.record(7) == merged


def test_author_and_merger_avatars_come_from_existing_detail_responses(stand: _Stand) -> None:
    answers = scenario(stand.origin)
    wanted = "https://avatars.githubusercontent.com/u/123?s=40"
    for entry in answers["api"].values():
        body = entry.get("body")
        records = body if isinstance(body, list) else [body]
        for item in records:
            if not isinstance(item, dict):
                continue
            if isinstance(item.get("user"), dict):
                item["user"]["avatar_url"] = "https://avatars.githubusercontent.com/u/123?v=4"
            if "merged_by" in item:
                item["merged_by"] = {
                    "login": "merger",
                    "avatar_url": "https://avatars.githubusercontent.com/in/456?size=100",
                }
    stand.answer(answers)
    record = stand.refresh(7)
    assert record.pull.author_avatar_url == wanted
    assert record.pull.merged_by_avatar_url == "https://avatars.githubusercontent.com/in/456?s=40"
    assert record.issue_comments and all(
        item.author_avatar_url == wanted for item in record.issue_comments
    )
    assert record.reviews and all(item.author_avatar_url == wanted for item in record.reviews)
    assert record.review_comments and all(
        item.author_avatar_url == wanted for item in record.review_comments
    )
    stand.calls()
    path = stand.published.home / source_pull_record(stand.published.slug, 7)
    old = json.loads(path.read_bytes())
    del old["projection_version"]
    actors = [old["pull"], *old["issue_comments"], *old["reviews"], *old["review_comments"]]
    for actor in actors:
        del actor["author_avatar_url"]
    del old["pull"]["merged_by_avatar_url"]
    path.write_text(json.dumps(old))
    old_bytes = path.read_bytes()
    cached = stand.record(7)
    assert isinstance(cached, PullRecord) and cached.projection_version == 0
    assert cached.pull.author_avatar_url is None and stand.calls() == []
    stand.answer({**answers, "api_failure": {"stderr": "HTTP 503: Service Unavailable"}})
    with pytest.raises(PullDataError):
        stand.refresh(7)
    assert path.read_bytes() == old_bytes
    stand.calls()
    stand.answer(answers)
    upgraded = stand.refresh(7)
    assert upgraded.projection_version == PULL_RECORD_PROJECTION
    assert upgraded.pull.author_avatar_url == wanted
    assert all(item.author_avatar_url == wanted for item in upgraded.issue_comments)
    # The pull request's own REST reads; the account check's ``user`` is conditional on
    # the account, not on a record, and its status is one GraphQL query, never conditional.
    sent = [
        call["args"]
        for call in stand.calls()
        if call["args"][0] == "api" and call["args"][-1] != "user" and "graphql" not in call["args"]
    ]
    assert sent and not any(arg.startswith("If-None-Match: ") for args in sent for arg in args)
    assert not any("users/" in str(args) for args in sent)
    warm = stand.refresh(7)
    assert warm.pull.author_avatar_url == wanted
    assert warm.projection_version == PULL_RECORD_PROJECTION
    reused = [
        call["args"]
        for call in stand.calls()
        if call["args"][0] == "api" and call["args"][-1] != "user" and "graphql" not in call["args"]
    ]
    assert len(reused) == len(sent) == 4
    assert all(any(arg.startswith("If-None-Match: ") for arg in args) for args in reused)


def test_a_record_of_bare_label_names_is_shown_neutral_until_its_refresh_colors_it(
    stand: _Stand,
) -> None:
    """A record of projection 1, as 0.12.0 and the builds since wrote it, names its labels.

    It is read as it is, each label without a color or a description, so its chips are
    neutral and nothing is asked of GitHub. Its next refresh asks for every part without an
    ETag, since a 304 would keep the names alone, and colors them.
    """

    stand.answer(scenario(stand.origin))
    record = stand.refresh(7)
    assert [label.model_dump() for label in record.pull.labels] == [
        {
            "name": "enhancement",
            "color": "2700af",
            "description": "A label's description is its chip's tooltip",
        }
    ]
    stand.calls()
    path = stand.published.home / source_pull_record(stand.published.slug, 7)
    old = json.loads(path.read_bytes())
    old["projection_version"] = 1
    old["pull"]["labels"] = ["enhancement"]
    path.write_text(json.dumps(old))
    cached = stand.record(7)
    assert isinstance(cached, PullRecord) and cached.projection_version == 1
    assert [label.model_dump() for label in cached.pull.labels] == [
        {"name": "enhancement", "color": None, "description": None}
    ]
    assert stand.calls() == []
    upgraded = stand.refresh(7)
    assert upgraded.projection_version == PULL_RECORD_PROJECTION
    assert upgraded.pull.labels == record.pull.labels
    # The pull request's own reads; the account check's ``user`` is conditional on the
    # account, not on a record.
    sent = [
        call["args"]
        for call in stand.calls()
        if call["args"][0] == "api" and call["args"][-1] != "user"
    ]
    assert sent and not any(arg.startswith("If-None-Match: ") for args in sent for arg in args)


def test_markdown_revision_tracks_content_not_refresh_metadata(
    pinned_pull: tuple[_Stand, TestClient], monkeypatch: pytest.MonkeyPatch
) -> None:
    """Same-second changes invalidate HTML; warm reads reuse one parsed content digest."""
    from metabrowser.builtin_plugins.github import pull_route

    stand, client = pinned_pull
    stand.calls()
    pull_route._PARSED.clear()
    hashed: list[dict[str, Any]] = []
    digest = pull_route._record_revision

    def counting(dumped: dict[str, Any]) -> str:
        hashed.append(dumped)
        return digest(dumped)

    monkeypatch.setattr(pull_route, "_record_revision", counting)
    first = _read(client, 7).json()
    revision = first["record_revision"]
    assert isinstance(revision, str) and len(revision) == 64
    for _ in range(5):
        assert _read(client, 7).json()["record_revision"] == revision
    markdown = client.get(
        "/api/plugin/github/pull-markdown", params={"number": 7, "part": "body"}
    ).json()
    assert markdown["record_revision"] == revision and len(hashed) == 1
    # Canonical ordering and all ownership/content fields are part of the identity.
    dumped = hashed[0]
    assert digest(dict(reversed(list(dumped.items())))) == revision
    for field, value in (
        ("reader", "gh:another-reader"),
        ("source", "https://github.com/o/r"),
        ("number", 8),
    ):
        assert digest({**dumped, field: value}) != revision
    record = stand.record(7)
    assert isinstance(record, PullRecord)
    refreshed = record.model_copy(
        update={
            "fetched_at": (FETCHED_AT + timedelta(seconds=1)).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "etags": {**record.etags, "fixture": '"new-provider-tag"'},
        }
    )
    write_pull_record(stand.published.home, stand.published.slug, refreshed)
    same = _read(client, 7).json()
    assert same["fetched_at"] != first["fetched_at"]
    assert same["record_revision"] == revision and len(hashed) == 2
    newer = refreshed.model_copy(
        update={
            "pull": refreshed.pull.model_copy(update={"body": "Different text in the same second."})
        }
    )
    write_pull_record(stand.published.home, stand.published.slug, newer)
    changed = _read(client, 7).json()
    assert changed["fetched_at"] == same["fetched_at"]
    assert changed["record_revision"] != revision and len(hashed) == 3
    markdown = client.get(
        "/api/plugin/github/pull-markdown", params={"number": 7, "part": "body"}
    ).json()
    assert markdown["record_revision"] == changed["record_revision"]
    assert "Different text in the same second." in markdown["html"]
    assert stand.calls() == []


def test_markdown_response_keeps_the_record_it_actually_rendered(
    pinned_pull: tuple[_Stand, TestClient], monkeypatch: pytest.MonkeyPatch
) -> None:
    """A replacement during rendering cannot pair old text with a newer revision."""
    from metabrowser.diff.markdown_projection_worker import InertRender, ProjectionWorker

    stand, client = pinned_pull
    first = _read(client, 7).json()
    record = stand.record(7)
    assert isinstance(record, PullRecord)
    newer = record.model_copy(
        update={
            "pull": record.pull.model_copy(
                update={"body": "A replacement published while rendering."}
            )
        }
    )
    render = ProjectionWorker.render_inert
    replaced = False

    async def replace_during_render(
        worker: ProjectionWorker, request: InertRender
    ) -> dict[str, Any]:
        nonlocal replaced
        if not replaced:
            replaced = True
            assert request.source_text == record.pull.body
            await asyncio.to_thread(
                write_pull_record, stand.published.home, stand.published.slug, newer
            )
        return await render(worker, request)

    monkeypatch.setattr(ProjectionWorker, "render_inert", replace_during_render)
    old = client.get(
        "/api/plugin/github/pull-markdown", params={"number": 7, "part": "body"}
    ).json()
    current = _read(client, 7).json()
    assert old["fetched_at"] == current["fetched_at"]
    assert old["record_revision"] == first["record_revision"] != current["record_revision"]
    assert "replacement published" not in old["html"]
    fresh = client.get(
        "/api/plugin/github/pull-markdown", params={"number": 7, "part": "body"}
    ).json()
    assert fresh["record_revision"] == current["record_revision"]
    assert "A replacement published while rendering." in fresh["html"]


# A text past a shortened deadline: the shape the review of mb-273l timed at 23.1 s for 239 KB
# takes seconds at the text bound, far past 0.2 s.
_SLOW_TEXT = "[" * 100 + "%" * (60 * 1024)
REFUSED_TEXT_FIXTURE = (
    Path(__file__).resolve().parent / "fixtures" / "github-pull-text-refusal.json"
)


def test_a_text_past_the_render_deadline_is_refused_and_refused_again_at_once(
    pinned_pull: tuple[_Stand, TestClient], monkeypatch: pytest.MonkeyPatch
) -> None:
    """A pull request text renders in the Markdown child; one past its deadline is refused.

    The answer is the one ``tests/dom/github-pull-text-refusal-session.js`` gives the page,
    from ``tests/fixtures/github-pull-text-refusal.json``, which this pins to the route.
    The refusal is kept by the text, so asking again renders nothing.
    """
    from metabrowser.diff import markdown_projection_worker as worker_module
    from metabrowser.diff.markdown_projection_worker import ProjectionWorker

    monkeypatch.setattr(worker_module, "_RENDER_DEADLINE_S", 0.2)
    exchanges: list[int] = []
    exchange = ProjectionWorker._exchange_render  # pyright: ignore[reportPrivateUsage]

    async def counted(
        self: ProjectionWorker, process: asyncio.subprocess.Process, frame: bytes
    ) -> object:
        exchanges.append(process.pid)
        return await exchange(self, process, frame)

    monkeypatch.setattr(ProjectionWorker, "_exchange_render", counted)
    stand, client = pinned_pull
    record = stand.record(7)
    assert isinstance(record, PullRecord)
    slow = record.model_copy(update={"pull": record.pull.model_copy(update={"body": _SLOW_TEXT})})
    write_pull_record(stand.published.home, stand.published.slug, slow)
    params = {"number": 7, "part": "body"}
    refused = client.get("/api/plugin/github/pull-markdown", params=params)
    again = client.get("/api/plugin/github/pull-markdown", params=params)
    body: dict[str, Any] = refused.json()
    answer = {"status": refused.status_code, "body": body}
    assert answer == {
        "status": 422,
        "body": {
            "code": "render_deadline",
            "error": "Rendering took longer than 0.2 seconds, so it was stopped",
            "deadline_ms": 200,
            "remembered": False,
            "number": 7,
            "part": "body",
        },
    }
    assert (again.status_code, again.json()) == (422, {**body, "remembered": True})
    assert len(exchanges) == 1, "the kept refusal renders nothing"
    assert json.loads(REFUSED_TEXT_FIXTURE.read_text(encoding="utf-8")) == answer


def test_a_pull_read_starts_the_markdown_child_its_texts_will_need(
    pinned_pull: tuple[_Stand, TestClient], monkeypatch: pytest.MonkeyPatch
) -> None:
    """A served page's first read starts the child, so its first text does not wait for a
    start; a one-shot read, as `--api` makes, starts none (review A of #527, A16)."""
    from metabrowser.diff import markdown_projection_worker as worker_module
    from metabrowser.diff.markdown_projection_worker import shared_worker

    _stand, client = pinned_pull

    def starting() -> bool:
        worker = shared_worker()
        return worker._process is not None or worker._starting is not None  # pyright: ignore[reportPrivateUsage]

    # A worker no request has used yet: the one these reads reach, which the server's
    # lifespan stops as it ends.
    shared_worker.cache_clear()
    _read(client, 7)
    one_shot = starting()
    monkeypatch.setattr(worker_module._SERVING, "pages", True)  # pyright: ignore[reportPrivateUsage]
    _read(client, 7)
    assert one_shot is False
    assert starting() is True


def test_an_uncacheable_read_keeps_its_parsed_record_revision(
    pinned_pull: tuple[_Stand, TestClient], monkeypatch: pytest.MonkeyPatch
) -> None:
    """A file appearing after the cache-key stat still answers a coherent parsed record."""
    from metabrowser.builtin_plugins.github import pull_route

    _stand, client = pinned_pull
    monkeypatch.setattr(pull_route, "_file_stamp", lambda *_args: None)
    core = _read(client, 7).json()
    markdown = client.get(
        "/api/plugin/github/pull-markdown", params={"number": 7, "part": "body"}
    ).json()
    assert core["record"] is not None
    assert isinstance(core["record_revision"], str)
    assert markdown["record_revision"] == core["record_revision"]


def test_selected_core_wait_publishes_no_unread_parts(
    pinned_pull: tuple[_Stand, TestClient], monkeypatch: pytest.MonkeyPatch
) -> None:
    _exercise_selected_core_wait(pinned_pull, monkeypatch)


def test_revoked_core_cannot_escape_an_already_captured_get_worker(
    pinned_pull: tuple[_Stand, TestClient], monkeypatch: pytest.MonkeyPatch
) -> None:
    _exercise_selected_core_wait(pinned_pull, monkeypatch, revoke_in_thread=True)


@pytest.mark.parametrize("settlement", ["same_pin", "switch_pin"])
def test_selected_full_wait_returns_the_settled_conditional_read(
    pinned_pull: tuple[_Stand, TestClient],
    monkeypatch: pytest.MonkeyPatch,
    settlement: Literal["same_pin", "switch_pin"],
) -> None:
    _exercise_selected_core_wait(pinned_pull, monkeypatch, settle_in_get=settlement)


def test_h82_selected_publication_during_snapshot(
    pinned_pull: tuple[_Stand, TestClient], monkeypatch: pytest.MonkeyPatch
) -> None:
    _exercise_selected_core_wait(pinned_pull, monkeypatch, settle_in_get="captured_snapshot")


# How long the selected-core scenario's three reads stay held when nothing opens them, as
# this module's refresh stubs are bounded. A hold that gives up lets its read go on, so a
# stall at the scenario's POST fails that one test instead of ending the run at the
# suite's timeout, as it did in mb-xorh.
CORE_HOLD_S: Final = 30.0
# How long the one-thread scenario below may take before it counts as stuck: its held
# reads, five then, and its requests took 0.3 to 0.4 s on 3.14t (2026-11-17). Stuck, it waits until
# its holds give up, so the bound has to sit well past a loaded run and under CORE_HOLD_S.
ONE_WORKER_SCENARIO_S: Final = 20.0


@pytest.mark.parametrize(
    ("revoke_in_thread", "settle_in_get"),
    [(False, None), (True, None), (False, "same_pin"), (False, "switch_pin")],
    ids=["core", "revoked", "same_pin", "switch_pin"],
)
def test_a_selected_core_wait_and_its_settlement_run_on_one_worker_thread(
    pinned_pull_on_one_worker: tuple[_Stand, TestClient],
    monkeypatch: pytest.MonkeyPatch,
    revoke_in_thread: bool,
    settle_in_get: Literal["same_pin", "switch_pin"] | None,
) -> None:
    """The selected-core scenarios answer while their three reads are held, on one thread.

    The hold is a read in flight, as GitHub's slow answer is, and nothing in the refresh,
    its ``wait_core`` request, or the reads that settle it may keep a worker thread while
    it waits for work that needs one. The production pool starts a thread for each job it
    has none idle for, so only CPython's miscount (``tests/loop_gate.py``) brings it to the
    state a one-thread pool is always in: every live thread busy, the next job queued.
    A hold kept in a worker thread then queues the request's own next step behind it, as
    ``asyncio.to_thread(release.wait)`` did in mb-xorh. The snapshot scenario keeps one
    worker in its captured read on purpose, so it is not run here.
    """

    assert ONE_WORKER_SCENARIO_S < CORE_HOLD_S, "a stuck scenario would end before it counts"
    release = threading.Event()
    failures: list[BaseException] = []

    def exercise() -> None:
        try:
            _exercise_selected_core_wait(
                pinned_pull_on_one_worker,
                monkeypatch,
                revoke_in_thread=revoke_in_thread,
                settle_in_get=settle_in_get,
                release=release,
            )
        except BaseException as exc:
            failures.append(exc)

    thread = threading.Thread(target=exercise, name="one-worker-scenario", daemon=True)
    thread.start()
    thread.join(ONE_WORKER_SCENARIO_S)
    stuck = thread.is_alive()
    # Open the holds either way, so a stuck scenario unwinds before the server stops.
    release.set()
    thread.join(ONE_WORKER_SCENARIO_S)
    assert not stuck, "a request waited on the one worker thread its own held reads kept"
    if failures:
        raise failures[0]


def _exercise_selected_core_wait(
    pinned_pull: tuple[_Stand, TestClient],
    monkeypatch: pytest.MonkeyPatch,
    *,
    revoke_in_thread: bool = False,
    settle_in_get: Literal["same_pin", "switch_pin", "captured_snapshot"] | None = None,
    release: threading.Event | None = None,
) -> None:
    """Hold pull request 8's three reads while its core is staged, then settle it.

    *release* opens the holds; a caller that bounds the scenario passes its own, to open
    them when the bound passes.
    """

    stand, client = pinned_pull
    answers = scenario(stand.origin)
    answers["api"]["repos/octo/demo/pulls/8"]["body"]["body"] = "Early **core** description"
    answers["api"]["graphql:core:8"] = graph_core_entry(
        answers["api"]["repos/octo/demo/pulls/8"]["body"]
    )
    stand.answer(answers)
    release = threading.Event() if release is None else release
    started: set[str] = set()
    gave_up: list[str] = []
    read_list, get = pulls._read_list, pulls._get  # pyright: ignore[reportPrivateUsage]

    async def hold(path: str) -> None:
        started.add(path)
        if not await held_until(release, CORE_HOLD_S):
            gave_up.append(path)

    async def held_list(path: str, **kwargs: Any) -> Any:
        await hold(path)
        return await read_list(path, **kwargs)

    async def held_get(path: str, **kwargs: Any) -> Any:
        assert "/commits/" not in path, "a record reads no checks"
        return await get(path, **kwargs)

    monkeypatch.setattr(pulls, "_read_list", held_list)
    monkeypatch.setattr(pulls, "_get", held_get)
    try:
        response = client.post(
            "/api/plugin/github/pull-refresh",
            headers={"content-type": "application/json"},
            json={"number": 8, "retry": True, "wait_core": True},
        )
        assert response.status_code == 202, response.text
        envelope = response.json()["pull"]
        assert envelope["state"] == "pending" and envelope["refreshing"]
        assert envelope["record"] is None
        assert envelope["record_revision"] is None and envelope["fetched_at"] is None
        assert envelope["comparison_route"] is None
        preview = envelope["core_preview"]
        assert preview["source"] == CANONICAL and preview["number"] == 8
        assert preview["reader"] == f"gh:{READER}"
        assert preview["pull"]["number"] == 8
        assert preview["pull"]["body"] == "Early **core** description"
        assert preview["comparison_state"] == "pending"
        assert len(preview["revision"]) == 64
        assert set(preview) == {
            "source",
            "number",
            "reader",
            "observed_at",
            "revision",
            "pull",
            "comparison_state",
        }
        assert len(started) == 3
        assert stand.record(8) == "not_cached"
        first = client.get("/api/plugin/github/pull?number=8")
        assert first.json()["core_preview"] == preview
        assert (
            client.get(
                "/api/plugin/github/pull?number=8", headers={"if-none-match": first.headers["etag"]}
            ).status_code
            == 304
        )
        if settle_in_get == "captured_snapshot":
            _assert_full_after_captured_snapshot(client, monkeypatch, first, release)
        elif settle_in_get is not None:
            new_pin = stand.origin["base"] if settle_in_get == "switch_pin" else None
            _assert_selected_full_wait(client, monkeypatch, first, release, new_pin=new_pin)
        if revoke_in_thread:
            from metabrowser.builtin_plugins.github import pull_route

            entered, release_worker = threading.Event(), threading.Event()
            captured: list[PullView] = []
            responses: list[Any] = []
            original = pull_route.pull_answer

            def blocked(view: PullView) -> Any:
                answer = original(view)
                if view.number == 8 and answer[0]["core_preview"] is not None:
                    captured.append(view)
                    entered.set()
                    assert release_worker.wait(5)
                return answer

            monkeypatch.setattr(pull_route, "pull_answer", blocked)
            stand.calls()
            thread = threading.Thread(
                target=lambda: responses.append(
                    client.get(
                        "/api/plugin/github/pull?number=8",
                        headers={"if-none-match": first.headers["etag"]},
                    )
                )
            )
            thread.start()
            try:
                assert entered.wait(5)
                view = captured[0]
                assert view.core_preview is not None
                assert client.portal is not None

                def revoke() -> None:
                    assert view.host is not None
                    published = view.host.pulls.published
                    assert isinstance(published, PublishedSource)
                    view.host.pulls.bind(replace(published, fetched=not published.fetched))

                client.portal.call(revoke)
            finally:
                release_worker.set()
                thread.join(5)
            assert not thread.is_alive() and len(responses) == 1
            revoked = responses[0]
            assert revoked.status_code == 200 and revoked.json()["core_preview"] is None
            assert revoked.headers["etag"] != first.headers["etag"]
            assert (
                client.get(
                    "/api/plugin/github/pull?number=8",
                    headers={"if-none-match": revoked.headers["etag"]},
                ).status_code
                == 304
            )
            assert stand.calls() == []
    finally:
        release.set()
    deadline = time.monotonic() + 5
    final = client.get("/api/plugin/github/pull?number=8").json()
    while time.monotonic() < deadline:
        final = client.get("/api/plugin/github/pull?number=8").json()
        if not final["refreshing"]:
            break
        time.sleep(0.005)
    assert not final["refreshing"] and final["core_preview"] is None
    assert final["record"] is not None and isinstance(stand.record(8), PullRecord)
    # A read that gave up went on, so a stalled request answered late and the rest may
    # have passed: the stall is the failure.
    assert not gave_up, f"held reads gave up before the test opened them: {sorted(gave_up)}"


def _assert_full_after_captured_snapshot(
    client: TestClient, monkeypatch: pytest.MonkeyPatch, pending: Any, release: threading.Event
) -> None:
    from metabrowser.builtin_plugins.github import pull_route

    original = pull_route.pull_answer
    captured, resume = threading.Event(), threading.Event()
    responses: list[Any] = []
    initial = pending.json()
    revision = initial["core_preview"]["revision"]
    route = "/api/plugin/github/pull?number=8"

    def hold_snapshot(view: PullView) -> Any:
        answer = original(view)
        envelope = answer[0]
        if view.number == 8 and envelope["core_preview"] is not None:
            assert (
                envelope["core_preview"] == initial["core_preview"] and envelope["record"] is None
            )
            captured.set()
            assert resume.wait(10)
        return answer

    monkeypatch.setattr(pull_route, "pull_answer", hold_snapshot)
    read = threading.Thread(
        target=lambda: responses.append(
            client.get(
                f"{route}&wait_full_after={revision}",
                headers={"if-none-match": pending.headers["etag"], PIN_HEADER: initial["pin"]},
            )
        )
    )
    read.start()
    try:
        assert captured.wait(5)
        release.set()
        _drain_visible_cores(client)
        complete = client.get(route).json()
        assert not complete["refreshing"] and complete["record"] is not None
        assert read.is_alive()
    finally:
        release.set()
        resume.set()
        read.join(10)
    assert not read.is_alive() and len(responses) == 1
    answered = responses[0]
    assert answered.status_code == 200 and answered.headers["etag"] != pending.headers["etag"]
    assert answered.json() == complete


def _assert_selected_full_wait(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
    pending: Any,
    release: threading.Event,
    *,
    new_pin: str | None,
) -> None:
    from metabrowser.builtin_plugins.github import served_pull as served_module
    from metabrowser.builtin_plugins.github.pull_route import pull_host

    route = "/api/plugin/github/pull?number=8"
    revision = pending.json()["core_preview"]["revision"]
    opted = f"{route}&wait_full_after={revision}"
    headers = {"if-none-match": pending.headers["etag"], PIN_HEADER: pending.json()["pin"]}
    # A matching conditional response remains a 304 when the bounded wait expires.
    with monkeypatch.context() as patcher:
        patcher.setattr(served_module, "FULL_WAIT_TIMEOUT_S", 0, raising=False)
        assert client.get(opted, headers=headers).status_code == 304
    assert client.get(f"{route}&wait_full_after={'0' * 64}", headers=headers).status_code == 304
    assert client.get(f"{route}&wait_full_after=wrong").status_code == 400
    assert client.portal is not None
    replies: list[Any] = []
    responded = threading.Event()

    def read() -> None:
        try:
            replies.append(client.get(opted, headers=headers))
        finally:
            responded.set()

    async def waiting_or_returned() -> bool:
        host = pull_host(app)
        assert host is not None
        kept = host.pulls.held(8)
        assert kept is not None
        async with asyncio.timeout(5):
            while not responded.is_set():
                if getattr(kept, "_full_waiter", None) is not None:
                    return True
                await asyncio.sleep(0.001)
        return False

    # Make the fixture independent of host scheduling during concurrent TestClient calls.
    # The separate zero-timeout case exercises the timeout path without a real sleep.
    monkeypatch.setattr(served_module, "FULL_WAIT_TIMEOUT_S", 5, raising=False)
    thread = threading.Thread(target=read)
    thread.start()
    try:
        assert client.portal.call(waiting_or_returned), (
            "the selected GET returned before settlement"
        )
        assert client.get(route, headers=headers).status_code == 304
        assert client.get(opted, headers=headers).status_code == 304
        assert not responded.is_set()
        if new_pin is not None:
            switched = client.post("/api/source/pin", json={"oid": new_pin}, headers=_JSON)
            assert switched.status_code == 200, switched.text
            assert switched.json()["changed"] and switched.json()["status"]["pin"] == new_pin
            unclaimed = client.get(opted)
            assert unclaimed.status_code == 200 and unclaimed.json()["pin"] == new_pin
            assert not responded.is_set()
        release.set()
    finally:
        release.set()
        thread.join(10)
    assert not thread.is_alive() and len(replies) == 1
    complete = replies[0]
    if new_pin is not None:
        body = complete.json()
        assert (complete.status_code, body.get("code"), body.get("pin")) == (
            409,
            "pin_changed",
            new_pin,
        )
        assert complete.headers[PIN_CHANGED_HEADER] == new_pin
        assert complete.headers["cache-control"] == "no-store"
        assert "etag" not in complete.headers and "record" not in body
        return
    assert complete.status_code == 200 and complete.headers["etag"] != pending.headers["etag"]
    assert complete.json()["record"]["pull"]["body"] == "Early **core** description"
    assert complete.json()["core_preview"] is None


@dataclass
class _CoreGate:
    release: asyncio.Event
    core: dict[str, Any]
    accounts: tuple[str, ...] = (READER,)
    viewer: str = READER
    started: int = 0
    finished: int = 0
    account_reads: int = 0
    core_reads: int = 0
    parts_started: asyncio.Event = dataclass_field(default_factory=asyncio.Event)
    core_started: asyncio.Event = dataclass_field(default_factory=asyncio.Event)
    release_core: asyncio.Event | None = None
    second_core: asyncio.Event | None = None
    release_second: asyncio.Event | None = None

    def install(self, stand: _Stand, monkeypatch: pytest.MonkeyPatch) -> None:
        async def account() -> str:
            self.account_reads += 1
            return self.accounts[min(self.account_reads - 1, len(self.accounts) - 1)]

        async def part() -> None:
            self.started += 1
            if self.started == 3:
                self.parts_started.set()
            try:
                await self.release.wait()
            finally:
                self.finished += 1

        async def core() -> dict[str, Any]:
            self.core_reads += 1
            self.core_started.set()
            if self.release_core is not None:
                await self.release_core.wait()
            body = json.loads(json.dumps(self.core))
            if self.second_core is not None and self.core_reads == 2:
                self.second_core.set()
                assert self.release_second is not None
                await self.release_second.wait()
            if self.second_core is not None and self.core_reads == 1:
                body["head"]["sha"] = stand.origin["fork_earlier"]
            return body

        async def graph(query: str, variables: Any, **_kwargs: Any) -> dict[str, Any]:
            assert query == pulls._CORE_QUERY
            assert variables == {"owner": "octo", "name": "demo", "number": 7}
            return graph_core_data(await core(), reader=self.viewer)

        async def get(path: str, **_kwargs: Any) -> GhResponse:
            assert "/pulls/7" in path, "a record reads no checks"
            return GhResponse(200, {}, json.dumps(await core()).encode())

        async def listed(_path: str, **_kwargs: Any) -> gh_lists.ListRead:
            await part()
            return gh_lists.ListRead([], False, False, None)

        monkeypatch.setattr(pulls, "active_account", account)
        monkeypatch.setattr(pulls, "gh_graphql", graph)
        monkeypatch.setattr(pulls, "_get", get)
        monkeypatch.setattr(pulls, "_read_list", listed)


def _core_gate(stand: _Stand, monkeypatch: pytest.MonkeyPatch) -> _CoreGate:
    gate = _CoreGate(
        asyncio.Event(), scenario(stand.origin)["api"]["repos/octo/demo/pulls/7"]["body"]
    )
    gate.install(stand, monkeypatch)
    return gate


@pytest.mark.parametrize("when", ["before_preview", "after_preview"])
def test_selected_core_account_change_revokes_and_drains_without_publication(
    stand: _Stand, monkeypatch: pytest.MonkeyPatch, when: str
) -> None:
    entered, release_stamp = threading.Event(), threading.Event()
    keep_stamp = pulls._keep_stamp

    def hold_stamp(*args: Any) -> None:
        entered.set()
        assert release_stamp.wait(5)
        keep_stamp(*args)

    monkeypatch.setattr(pulls, "_keep_stamp", hold_stamp)

    async def run() -> None:
        gate = _core_gate(stand, monkeypatch)
        gate.viewer = "changed" if when == "before_preview" else READER
        gate.accounts = (READER,) if when == "before_preview" else (READER, "changed")
        held = ServedPull(stand.published, 7)
        held.request_core_preview()
        job = asyncio.create_task(held.refresh({"record"}))
        if when == "after_preview":
            await held.wait_for_core()
            assert held.core_preview is not None
            assert held.core_preview["reader"] == f"gh:{READER}"
            gate.release.set()
        try:
            assert await held_until(entered, 5)
            assert held.core_preview is None
        finally:
            release_stamp.set()
            await asyncio.wait_for(job, 5)
        assert held.core_preview is None
        assert held.last is not None and held.last["outcome"] == "account_changed"
        assert gate.started == gate.finished == (0 if when == "before_preview" else 3)
        assert gate.account_reads == (1 if when == "before_preview" else 2)
        assert stand.record(7) == "not_cached"

    asyncio.run(run())


@pytest.mark.parametrize("end_wait", ["cancel", "rebind"])
def test_selected_full_wait_does_not_own_the_refresh(
    stand: _Stand, monkeypatch: pytest.MonkeyPatch, end_wait: str
) -> None:
    from metabrowser.builtin_plugins.github import served_pull as served_module

    monkeypatch.setattr(served_module, "FULL_WAIT_TIMEOUT_S", 5)

    async def run() -> None:
        gate = _core_gate(stand, monkeypatch)
        held = ServedPull(stand.published, 7)
        held.request_core_preview()
        job = asyncio.create_task(held.refresh({"record"}))
        try:
            await held.wait_for_core()
            preview = held.core_preview
            assert preview is not None
            waiter = asyncio.create_task(held.wait_for_full(preview))
            await asyncio.sleep(0)
            assert held._full_waiter is not None
            assert not await held.wait_for_full(preview)
            if end_wait == "cancel":
                waiter.cancel()
                with pytest.raises(asyncio.CancelledError):
                    await waiter
                assert held.core_preview is preview
            else:
                held.bind(replace(stand.published, store_id="rebound-store"))
                assert await asyncio.wait_for(waiter, 1)
                assert held.core_preview is None
            assert held._full_waiter is None and not job.done()
        finally:
            gate.release.set()
            await asyncio.wait_for(job, 5)

    asyncio.run(run())


def test_selected_core_does_not_add_auth_or_replace_an_existing_full_record(
    stand: _Stand, monkeypatch: pytest.MonkeyPatch
) -> None:
    original = stand.refresh(7)
    held = served_pull(stand.published, 7)

    async def run() -> None:
        gate = _core_gate(stand, monkeypatch)
        held.request_core_preview()
        job = asyncio.create_task(held.refresh({"record"}))
        await gate.parts_started.wait()
        await held.wait_for_core()
        assert not job.done()
        assert held.core_preview is None
        assert stand.record(7) == original
        gate.release.set()
        await asyncio.wait_for(job, 5)
        assert gate.account_reads == 2
        assert held.last is not None and held.last["outcome"] == "succeeded"

    asyncio.run(run())


def test_selected_core_head_retry_removes_the_old_attempt_before_the_next_core(
    stand: _Stand, monkeypatch: pytest.MonkeyPatch
) -> None:
    async def run() -> None:
        gate = _core_gate(stand, monkeypatch)
        gate.second_core, gate.release_second = asyncio.Event(), asyncio.Event()
        gate.release.set()
        held = ServedPull(stand.published, 7)
        held.request_core_preview()
        job = asyncio.create_task(held.refresh({"record"}))
        await asyncio.wait_for(gate.second_core.wait(), 5)
        assert held.core_preview is None
        assert stand.record(7) == "not_cached"
        gate.release_second.set()
        await asyncio.wait_for(job, 5)
        assert gate.core_reads == 2 and gate.account_reads == 4
        assert held.core_preview is None
        assert held.last is not None and held.last["outcome"] == "succeeded"
        final = stand.record(7)
        assert isinstance(final, PullRecord) and final.pull.head.sha == stand.origin["fork_head"]

    asyncio.run(run())


def test_selected_core_binding_change_rejects_an_inflight_viewer_checked_core(
    stand: _Stand, monkeypatch: pytest.MonkeyPatch
) -> None:
    async def run() -> None:
        gate = _core_gate(stand, monkeypatch)
        gate.release_core = asyncio.Event()
        held = ServedPull(stand.published, 7)
        held.request_core_preview()
        job = asyncio.create_task(held.refresh({"record"}))
        await asyncio.wait_for(gate.core_started.wait(), 5)
        held.bind(replace(stand.published, store_id="rebound-store"))
        gate.release_core.set()
        await asyncio.wait_for(gate.parts_started.wait(), 5)
        assert held.core_preview is None
        gate.release.set()
        await asyncio.wait_for(job, 5)
        assert held.core_preview is None

    asyncio.run(run())


@pytest.mark.parametrize("finish", ["cancel_waiter", "timeout_waiter", "cancel_job"])
def test_selected_core_wait_owns_no_producer_and_has_one_lease(
    stand: _Stand, monkeypatch: pytest.MonkeyPatch, finish: str
) -> None:
    from metabrowser.builtin_plugins.github import served_pull as served_module

    async def run() -> None:
        gate = _core_gate(stand, monkeypatch)
        gate.release_core = asyncio.Event()
        held = ServedPull(stand.published, 7)
        held.request_core_preview()
        job = asyncio.create_task(held.refresh({"record"}))
        await asyncio.wait_for(gate.core_started.wait(), 5)
        waiter = asyncio.create_task(held.wait_for_core())
        await asyncio.sleep(0)
        assert held._core_waiter
        await held.wait_for_core()
        assert not waiter.done() and not job.done()
        if finish == "timeout_waiter":
            waiter.cancel()
            with pytest.raises(asyncio.CancelledError):
                await waiter
            monkeypatch.setattr(served_module, "CORE_WAIT_TIMEOUT_S", 0)
            await held.wait_for_core()
            assert not held._core_waiter and not job.done()
        elif finish == "cancel_waiter":
            waiter.cancel()
            with pytest.raises(asyncio.CancelledError):
                await waiter
            assert not held._core_waiter and not job.done()
        else:
            job.cancel()
            with pytest.raises(asyncio.CancelledError):
                await job
            await waiter
            assert gate.finished == gate.started == 0
            assert held.core_preview is None and stand.record(7) == "not_cached"
            return
        gate.release_core.set()
        gate.release.set()
        await asyncio.wait_for(job, 5)
        assert held.last is not None and held.last["outcome"] == "succeeded"

    asyncio.run(run())


def test_selected_checkout_core_has_no_store_or_git_acquisition(
    stand: _Stand, monkeypatch: pytest.MonkeyPatch
) -> None:
    from metabrowser.builtin_plugins.github.pull_list import ListedRepository

    repository = ListedRepository(stand.published.home, stand.published.slug, "octo", "demo")

    async def forbidden(*_args: Any, **_kwargs: Any) -> Any:
        raise AssertionError("metadata-only checkout acquired or fetched Git")

    monkeypatch.setattr(pulls, "fetch_pull_head", forbidden)
    monkeypatch.setattr(pulls, "_with_comparison", forbidden)

    async def run() -> None:
        gate = _core_gate(stand, monkeypatch)
        held = ServedPull(repository, 7)
        held.request_core_preview()
        job = asyncio.create_task(held.refresh({"record"}))
        await held.wait_for_core()
        assert held.core_preview is not None
        assert held.core_preview["comparison_state"] == "no_store"
        held.bind(stand.published)
        assert held.core_preview is None
        gate.release.set()
        await asyncio.wait_for(job, 5)
        assert held.core_preview is None
        record = stand.record(7)
        assert isinstance(record, PullRecord) and record.unavailable["comparison"] == "no_store"

    asyncio.run(run())


@pytest.mark.parametrize(
    "extra",
    [
        {"wait_core": "yes", "retry": True},
        {"wait_core": True},
        {"wait_core": True, "retry": True, "comparison": True},
        {"wait_core": True, "retry": True, "recovery": {"base": "a" * 40, "head": "b" * 40}},
    ],
)
def test_core_wait_request_requires_only_a_selected_metadata_retry(extra: dict[str, Any]) -> None:
    from metabrowser.builtin_plugins.github.pull_route import PullRequestError, refresh_request

    with pytest.raises(PullRequestError, match="wait_core"):
        refresh_request({"number": 7, **extra})


# H80 draft: fixed GraphQL answer from the same deterministic core fixture.
def _h80_graph_answer(rest: dict[str, Any], *, viewer: str = READER) -> dict[str, Any]:
    return graph_core_data(rest, reader=viewer)


@pytest.mark.parametrize("number", [7, 8, 9, 10])
def test_h80_graph_core_keeps_the_complete_validated_rest_model(stand: _Stand, number: int) -> None:
    rest = scenario(stand.origin)["api"][f"repos/octo/demo/pulls/{number}"]["body"]
    answer = _h80_graph_answer(rest)
    assert pulls._graph_pull(answer["repository"]["pull"], number) == pulls._pull(rest, number)


def test_h80_graph_core_of_a_renamed_repository_is_read_under_its_new_name(
    stand: _Stand, monkeypatch: pytest.MonkeyPatch
) -> None:
    """GitHub answers a renamed repository's old name with its new one, as ``tiangolo/fastapi``
    answers ``fastapi/fastapi``, and as the REST reads after the core follow its redirect."""

    rest = scenario(stand.origin)["api"]["repos/octo/demo/pulls/7"]["body"]
    answer = _h80_graph_answer(rest)
    answer["repository"]["nameWithOwner"] = "octo-org/demo-renamed"

    async def graph(_query: str, _variables: Any, **_kwargs: Any) -> dict[str, Any]:
        return answer

    monkeypatch.setattr(pulls, "gh_graphql", graph)
    core = asyncio.run(pulls._read_graph_core("octo", "demo", 7, f"gh:{READER}"))
    assert core == pulls._pull(rest, 7)


@pytest.mark.parametrize(
    "damage,expected",
    [
        ("viewer_changed", "account_changed"),
        ("viewer_malformed", "gh_failed"),
        ("repository_missing", "not_found_or_private"),
        ("repository_unnamed", "gh_failed"),
        ("pull_missing", "not_found_or_private"),
        ("number_wrong", "gh_failed"),
        ("head_invalid", "gh_failed"),
    ],
)
def test_h80_graph_core_refuses_before_any_preview_or_part_can_start(
    stand: _Stand,
    monkeypatch: pytest.MonkeyPatch,
    damage: str,
    expected: str,
) -> None:
    rest = scenario(stand.origin)["api"]["repos/octo/demo/pulls/7"]["body"]
    answer = _h80_graph_answer(rest)
    if damage == "viewer_changed":
        answer["viewer"]["login"] = "changed"
    elif damage == "viewer_malformed":
        answer["viewer"]["login"] = 12
    elif damage == "repository_missing":
        answer["repository"] = None
    elif damage == "repository_unnamed":
        answer["repository"]["nameWithOwner"] = None
    elif damage == "pull_missing":
        answer["repository"]["pull"] = None
    elif damage == "number_wrong":
        answer["repository"]["pull"]["number"] = 8
    else:
        answer["repository"]["pull"]["headRefOid"] = "not-a-sha"
    seen: list[str] = []

    async def graph(query: str, variables: Any, **_kwargs: Any) -> dict[str, Any]:
        assert query == pulls._CORE_QUERY
        assert variables == {"owner": "octo", "name": "demo", "number": 7}
        seen.append("graph")
        return answer

    async def unexpected(*_args: Any, **_kwargs: Any) -> Any:
        pytest.fail("refused core must not stage or read any other part")

    monkeypatch.setattr(pulls, "gh_graphql", graph)
    monkeypatch.setattr(pulls, "_get", unexpected)
    monkeypatch.setattr(pulls, "_read_list", unexpected)
    with pytest.raises(PullDataError) as error:
        asyncio.run(
            pulls._read_api(
                "octo", "demo", 7, previous=None, reader=f"gh:{READER}", on_core=unexpected
            )
        )
    assert error.value.state == expected and seen == ["graph"]


def test_h80_full_record_refresh_never_enters_the_graph_path(
    stand: _Stand, monkeypatch: pytest.MonkeyPatch
) -> None:
    original = stand.refresh(7)
    calls: list[tuple[str, str | None]] = []
    real_get = pulls._get

    async def unexpected(*_args: Any, **_kwargs: Any) -> Any:
        pytest.fail("existing full record must retain its conditional REST path")

    async def counted(path: str, *, etag: str | None) -> GhResponse:
        calls.append((path, etag))
        return await real_get(path, etag=etag)

    monkeypatch.setattr(pulls, "gh_graphql", unexpected)
    monkeypatch.setattr(pulls, "_get", counted)
    held = served_pull(stand.published, 7)
    held.request_core_preview()
    asyncio.run(held.refresh({"record"}))
    assert held.last is not None and held.last["outcome"] == "succeeded"
    assert ("repos/octo/demo/pulls/7", original.etags["repos/octo/demo/pulls/7"]) in calls
    assert held.core_preview is None


@pytest.mark.parametrize("damage", ["ghost_merger", "deleted_repositories", "no_merge_commit"])
def test_h80_graph_core_preserves_nullable_metadata(stand: _Stand, damage: str) -> None:
    rest = scenario(stand.origin)["api"]["repos/octo/demo/pulls/8"]["body"]
    if damage == "ghost_merger":
        rest["merged_by"] = None
    elif damage == "deleted_repositories":
        rest["base"]["repo"] = None
        rest["head"]["repo"] = None
    else:
        rest["merge_commit_sha"] = None
    data = graph_core_data(rest)
    assert pulls._graph_pull(data["repository"]["pull"], 8) == pulls._pull(rest, 8)


def test_h80_cancel_after_verified_core_drains_all_three_parts(
    stand: _Stand, monkeypatch: pytest.MonkeyPatch
) -> None:
    async def run() -> None:
        gate = _core_gate(stand, monkeypatch)
        held = ServedPull(stand.published, 7)
        held.request_core_preview()
        job = asyncio.create_task(held.refresh({"record"}))
        await held.wait_for_core()
        await asyncio.wait_for(gate.parts_started.wait(), 5)
        assert held.core_preview is not None and gate.started == 3
        job.cancel()
        with pytest.raises(asyncio.CancelledError):
            await job
        assert gate.finished == 3 and held.core_preview is None
        assert stand.record(7) == "not_cached"

    asyncio.run(run())


def test_h80_initial_graph_core_then_real_rest_etag_then_304(
    stand: _Stand, monkeypatch: pytest.MonkeyPatch
) -> None:
    path = "repos/octo/demo/pulls/7"
    replies: list[tuple[int, str | None]] = []
    original_api = gh_lists.gh_api

    async def observed_api(route: str, **kwargs: Any) -> GhResponse:
        response = await original_api(route, **kwargs)
        if route == path:
            replies.append((response.status, kwargs.get("etag")))
        return response

    monkeypatch.setattr(gh_lists, "gh_api", observed_api)
    stand.calls()
    held = ServedPull(stand.published, 7)
    held.request_core_preview()
    asyncio.run(held.refresh({"record"}))
    first = stand.record(7)
    assert isinstance(first, PullRecord) and path not in first.etags and replies == []
    initial_calls = stand.calls()
    assert sum(c["args"][-1] == "user" for c in initial_calls) == 2
    # The core, and then the status read after the record (``pull_status_read``).
    assert [
        next(arg for arg in c["args"] if arg.startswith("query=")).split("(", 1)[0]
        for c in initial_calls
        if "graphql" in c["args"]
    ] == ["query=query PullCore", "query=query PullStatus"]
    second = stand.refresh(7)
    assert replies == [(200, None)] and second.etags[path]
    assert sum(c["args"][-1] == "user" for c in stand.calls()) == 2
    third = stand.refresh(7)
    assert replies == [(200, None), (304, second.etags[path])]
    assert third.pull == first.pull
    assert sum(c["args"][-1] == "user" for c in stand.calls()) == 2


@pytest.mark.parametrize("state,draft", [("open", False), ("open", True), ("closed", False)])
def test_h80_unmerged_core_keeps_the_non_null_test_merge_sha(
    stand: _Stand, state: str, draft: bool
) -> None:
    rest = scenario(stand.origin)["api"]["repos/octo/demo/pulls/7"]["body"]
    test_merge = "c" * 40
    rest.update(
        state=state,
        draft=draft,
        merged=False,
        merged_at=None,
        merged_by=None,
        merge_commit_sha=test_merge,
        closed_at="2026-09-17T12:00:00Z" if state == "closed" else None,
    )
    graph = graph_core_data(rest)["repository"]["pull"]
    assert graph["mergeCommit"] is None
    assert graph["potentialMergeCommit"] == {"oid": test_merge}
    mapped = pulls._graph_pull(graph, 7)
    assert mapped.merge_commit_sha == test_merge
    assert mapped == pulls._pull(rest, 7)


_PREPARE_CORES = "/api/plugin/github/pull-cores-prepare"


def _drain_visible_cores(client: TestClient) -> None:
    from metabrowser.mirror_refresh import drain_refreshes

    assert client.portal is not None
    client.portal.call(partial(drain_refreshes, app, timeout_s=5))


def _visible_core_fixture(
    pinned_pull: tuple[_Stand, TestClient],
    monkeypatch: pytest.MonkeyPatch,
    *,
    sibling: bool = False,
    visible: tuple[int, ...] | None = None,
    provider_stamp: str | None = None,
    untrustworthy: bool = False,
    hold_batch: Callable[[], Awaitable[None]] | None = None,
    lane: Literal["visible", "background"] | None = None,
) -> tuple[dict[str, Any], dict[int, dict[str, Any]], list[tuple[int, ...]]]:
    from metabrowser.builtin_plugins.github import pull_cores
    from metabrowser.builtin_plugins.github.pull_list import ListedRepository
    from tests.github_pull_fixture import seed_catalog

    stand, client = pinned_pull
    home, slug = stand.published.home, stand.published.slug
    entries = scenario(stand.origin)["api"]
    numbers = (8, 9, 7) if sibling else (8, 7)
    rest = {number: entries[f"repos/octo/demo/pulls/{number}"]["body"] for number in numbers}
    catalog = seed_catalog(
        ListedRepository(home, slug, "octo", "demo"), list(rest.values()), reader=READER
    )
    if untrustworthy:
        (home / source_pull_record(slug, 8)).symlink_to("missing-untrusted-target")
    calls: list[tuple[int, ...]] = []

    async def graph(query: str, variables: dict[str, str | int], **_kwargs: Any) -> dict[str, Any]:
        requested = tuple(
            int(value) for key, value in variables.items() if key.startswith("n") and key != "name"
        )
        calls.append(requested)
        assert variables["owner"] == "octo" and variables["name"] == "demo"
        assert "potentialMergeCommit" in query
        if hold_batch is not None:
            await hold_batch()
        data = graph_core_data(rest[8])
        repo = data["repository"]
        repo.pop("pull")
        for i, number in enumerate(requested):
            core = graph_core_data(rest[number])["repository"]["pull"]
            if provider_stamp is not None:
                core["updatedAt"] = provider_stamp
            repo[f"p{i}"] = core
        return data

    monkeypatch.setattr(pull_cores, "gh_graphql", graph)
    owner = {"id": "visible-8", "generation": catalog.generation("all")}
    ask: dict[str, Any] = {"state": "all", "window": owner, "numbers": list(visible or numbers)}
    if lane is not None:
        ask["lane"] = lane
    started = client.post(_PREPARE_CORES, json=ask)
    assert started.status_code == 202
    assert started.json() == {
        "preparation": "started",
        "status_route": "/api/plugin/github/pull?number=8",
    }
    if hold_batch is None:
        _drain_visible_cores(client)
    return ask, rest, calls


@pytest.mark.parametrize("first_full", [False, True])
def test_visible_core_exact_owner_release_and_first_full_precedence(
    pinned_pull: tuple[_Stand, TestClient], monkeypatch: pytest.MonkeyPatch, first_full: bool
) -> None:
    stand, client = pinned_pull
    ask, _rest, calls = _visible_core_fixture(pinned_pull, monkeypatch)
    first = _read(client, 8).json()
    assert first["record"] is None and first["refreshing"] is False
    assert first["core_preview"]["comparison_state"] == "not_started"
    assert first["core_preview"]["reader"] == f"gh:{READER}"
    assert _read(client, 7).json()["core_preview"] is None
    assert client.post(_PREPARE_CORES, json=ask).json() == {
        "preparation": "ready",
        "ready_numbers": [8],
        "skipped_numbers": [7],
    }
    assert client.post(
        _PREPARE_CORES, json={**ask, "window": {**ask["window"], "id": "obsolete"}, "numbers": []}
    ).json() == {"preparation": "not_owner"}
    assert _read(client, 8).json()["core_preview"] == first["core_preview"]
    if first_full:
        stand.refresh(8)
        # A full record is classified separately from a still-useful lightweight core.
        assert client.post(_PREPARE_CORES, json=ask).json() == {
            "preparation": "ready",
            "ready_numbers": [],
            "skipped_numbers": [8, 7],
        }
        current = _read(client, 8).json()
        assert current["record"] is not None and current["core_preview"] is None
    else:
        assert client.post(_PREPARE_CORES, json={**ask, "numbers": []}).json() == {
            "preparation": "released"
        }
    assert (_read(client, 8).json()["core_preview"] is None) is first_full
    assert calls == [(8,)]


def test_visible_core_running_window_survives_second_tab(
    pinned_pull: tuple[_Stand, TestClient], monkeypatch: pytest.MonkeyPatch
) -> None:
    _stand, client = pinned_pull
    entered, release = threading.Event(), threading.Event()

    async def hold_batch() -> None:
        entered.set()
        assert await held_until(release, 5)

    first, _rest, calls = _visible_core_fixture(pinned_pull, monkeypatch, hold_batch=hold_batch)
    second = {**first, "window": {**first["window"], "id": "second-tab"}}
    try:
        assert entered.wait(5)
        response = client.post(_PREPARE_CORES, json=second)
        assert response.status_code == 200 and response.json() == {"preparation": "busy"}
        assert client.post(_PREPARE_CORES, json={**second, "numbers": []}).json() == {
            "preparation": "not_owner"
        }
        assert client.post(_PREPARE_CORES, json=first).json()["preparation"] == "joined"
    finally:
        release.set()
    _drain_visible_cores(client)
    assert _read(client, 8).json()["core_preview"]["number"] == 8 and calls == [(8,)]


def _core_job_state() -> tuple[bool, object]:
    """Whether a core job runs for the served source, and the window that owns its cores."""
    from metabrowser.builtin_plugins.github.pull_cores import preparation_key
    from metabrowser.builtin_plugins.github.pull_route import pull_host

    host = pull_host(app)
    assert host is not None and host.coordinator is not None
    window = host.pulls.core_window
    running = host.coordinator.running(preparation_key(host.pulls.source))
    return running, window.ask.owner if window is not None else None


def test_visible_core_preempts_a_running_background_batch(
    pinned_pull: tuple[_Stand, TestClient], monkeypatch: pytest.MonkeyPatch
) -> None:
    _stand, client = pinned_pull
    entered, release, cancelled = threading.Event(), threading.Event(), threading.Event()
    batches = 0

    async def hold_background_batch() -> None:
        nonlocal batches
        batches += 1
        if batches > 1:
            return
        entered.set()
        try:
            assert await held_until(release, 5)
        except asyncio.CancelledError:
            cancelled.set()
            raise

    background, _rest, calls = _visible_core_fixture(
        pinned_pull,
        monkeypatch,
        sibling=True,
        visible=(8,),
        hold_batch=hold_background_batch,
        lane="background",
    )
    visible = {
        **background,
        "window": {**background["window"], "id": "viewport"},
        "numbers": [9],
        "lane": "visible",
    }
    assert client.portal is not None
    try:
        assert entered.wait(5)
        assert client.portal.call(_core_job_state) == (True, "visible-8")
        # The reader's rows are admitted at once, not after the walk's batch.
        response = client.post(_PREPARE_CORES, json=visible)
        assert response.status_code == 202 and response.json() == {
            "preparation": "started",
            "status_route": "/api/plugin/github/pull?number=9",
        }
        # The background job ended before the visible one started: its read was cancelled
        # and its window revoked, so its owner neither joins nor releases another's window.
        assert cancelled.is_set()
        assert client.post(_PREPARE_CORES, json={**background, "numbers": []}).json() == {
            "preparation": "not_owner"
        }
    finally:
        release.set()
    _drain_visible_cores(client)
    assert calls == [(8,), (9,)]
    assert _read(client, 9).json()["core_preview"]["number"] == 9
    assert _read(client, 8).json()["core_preview"] is None
    # The cancelled read keeps its attempt lease, so the walk's next ask does not read 8
    # again before the lease ends.
    walk = {**background, "window": {**background["window"], "id": "walk-again"}}
    again = client.post(_PREPARE_CORES, json=walk).json()
    assert again["preparation"] == "partial" and again["retry_numbers"] == [8]
    assert calls == [(8,), (9,)]
    # Nothing is left running, and only the visible owner releases its window.
    assert client.portal.call(_core_job_state) == (False, "viewport")
    assert client.post(_PREPARE_CORES, json={**walk, "numbers": []}).json() == {
        "preparation": "not_owner"
    }
    assert client.post(_PREPARE_CORES, json={**visible, "numbers": []}).json() == {
        "preparation": "released"
    }
    assert client.portal.call(_core_job_state) == (False, None)


@pytest.mark.parametrize(
    ("first", "second", "numbers"),
    [
        # A background batch already reading a visible row is doing the reader's work.
        ("background", "visible", [8, 9]),
        # Only the reader's own demand preempts, and never another reader's.
        ("visible", "background", [9]),
        ("visible", "visible", [9]),
    ],
)
def test_visible_core_preempts_only_a_background_batch_reading_other_rows(
    pinned_pull: tuple[_Stand, TestClient],
    monkeypatch: pytest.MonkeyPatch,
    first: Literal["visible", "background"],
    second: Literal["visible", "background"],
    numbers: list[int],
) -> None:
    _stand, client = pinned_pull
    entered, release, cancelled = threading.Event(), threading.Event(), threading.Event()

    async def hold_batch() -> None:
        entered.set()
        try:
            assert await held_until(release, 5)
        except asyncio.CancelledError:
            cancelled.set()
            raise

    running, _rest, calls = _visible_core_fixture(
        pinned_pull, monkeypatch, sibling=True, visible=(8,), hold_batch=hold_batch, lane=first
    )
    competitor = {
        **running,
        "window": {**running["window"], "id": "competitor"},
        "numbers": numbers,
        "lane": second,
    }
    try:
        assert entered.wait(5)
        response = client.post(_PREPARE_CORES, json=competitor)
        assert response.status_code == 200 and response.json() == {"preparation": "busy"}
        assert not cancelled.is_set()
        assert client.post(_PREPARE_CORES, json=running).json()["preparation"] == "joined"
    finally:
        release.set()
    _drain_visible_cores(client)
    assert not cancelled.is_set() and calls == [(8,)]
    assert _read(client, 8).json()["core_preview"]["number"] == 8


def test_visible_core_preemption_honors_a_failure_recorded_during_its_checks(
    pinned_pull: tuple[_Stand, TestClient], monkeypatch: pytest.MonkeyPatch
) -> None:
    from metabrowser.builtin_plugins.github import pull_cores

    _stand, client = pinned_pull
    entered, fail = threading.Event(), threading.Event()

    async def fail_batch() -> None:
        entered.set()
        assert await held_until(fail, 5)
        raise GhError("GitHub did not answer", state="network_error")

    background, _rest, calls = _visible_core_fixture(
        pinned_pull,
        monkeypatch,
        sibling=True,
        visible=(8,),
        hold_batch=fail_batch,
        lane="background",
    )
    visible = {
        **background,
        "window": {**background["window"], "id": "viewport"},
        "numbers": [9],
        "lane": "visible",
    }
    eligible = pull_cores._eligible  # pyright: ignore[reportPrivateUsage]
    checking, resume = threading.Event(), threading.Event()

    def paused(window: Any) -> Any:
        if window.ask.lane == "visible":
            checking.set()
            assert resume.wait(5)
        return eligible(window)

    monkeypatch.setattr(pull_cores, "_eligible", paused)
    replies: list[Any] = []
    sending = threading.Thread(
        target=lambda: replies.append(client.post(_PREPARE_CORES, json=visible))
    )
    assert client.portal is not None
    try:
        assert entered.wait(5)
        sending.start()
        # The visible batch is checking its rows when the background read fails.
        assert checking.wait(5)
        fail.set()
        deadline = time.monotonic() + 5
        while client.portal.call(_core_job_state)[0] and time.monotonic() < deadline:
            time.sleep(0.01)
        assert client.portal.call(_core_job_state) == (False, "visible-8")
    finally:
        fail.set()
        resume.set()
        sending.join(10)
    assert not sending.is_alive() and len(replies) == 1
    answer = replies[0].json()
    assert answer["preparation"] == "held"
    assert answer["failure"]["outcome"] == "network_error"
    # The source-wide failure hold covers the visible batch: no second provider read.
    _drain_visible_cores(client)
    assert calls == [(8,)]


# Each route that may start a refresh for a reader's own click: the module and name of the
# start it calls inside ``_whose``, and what else its body must name.
_RETRY_ROUTES: Final[dict[str, tuple[str, str, dict[str, Any]]]] = {
    "pull-refresh": ("pull_route", "start_refresh", {"number": 7}),
    "pulls-refresh": ("pull_list_route", "start_refresh", {}),
    "stacks-refresh": ("pull_stacks_route", "start_refresh", {}),
    "labels-refresh": ("pull_labels_route", "start_refresh", {}),
    "pull-files-refresh": ("pull_files_route", "start_files_refresh", {"number": 7}),
}


@pytest.mark.parametrize("retry", [True, False], ids=["reader", "automatic"])
@pytest.mark.parametrize("route", sorted(_RETRY_ROUTES))
def test_each_refresh_route_starts_a_readers_click_where_the_ceiling_does_not_count_it(
    pinned_pull: tuple[_Stand, TestClient],
    monkeypatch: pytest.MonkeyPatch,
    route: str,
    retry: bool,
) -> None:
    """A9 of review A on #737: the unit tests proved the context and the coordinator's copy
    of it, and nothing proved a route enters it, so a handler that dropped ``_whose`` would
    count a reader's Refresh against the process's ceiling unseen.

    The start each route calls is replaced by one that spends where it is called, which is
    where the job it starts would copy its context from.
    """

    import importlib
    import inspect

    from metabrowser.builtin_plugins.github import gh_budget, pull_list_route

    module_name, name, body = _RETRY_ROUTES[route]
    module = importlib.import_module(f"metabrowser.builtin_plugins.github.{module_name}")
    counted: list[tuple[int, int]] = []

    def spend() -> str:
        now = datetime.now(UTC)
        before = (gh_budget.automatic_spent(now), gh_budget.speculative_spent(now))
        gh_budget.spent(5, now=now)
        after = (gh_budget.automatic_spent(now), gh_budget.speculative_spent(now))
        counted.append((after[0] - before[0], after[1] - before[1]))
        return "not_due"

    async def started_async(*_args: object, **_kwargs: object) -> str:
        return spend()

    def started(*_args: object, **_kwargs: object) -> str:
        return spend()

    real = getattr(module, name)
    monkeypatch.setattr(
        module, name, started_async if inspect.iscoroutinefunction(real) else started
    )
    # A page's automatic ask also probes the list, which spends on its own.
    monkeypatch.setattr(pull_list_route, "attend_list", lambda _view: None)
    _stand, client = pinned_pull
    response = client.post(
        f"/api/plugin/github/{route}", json={**body, "retry": retry}, headers=_JSON
    )
    assert response.status_code == 200, response.text
    # A reader's click is not counted; an automatic ask is, and the label set's periodic
    # read is speculative work as well (A1 of review A on #737).
    speculative = 5 if route == "labels-refresh" else 0
    assert counted == ([(0, 0)] if retry else [(5, speculative)])


def test_cores_for_rows_on_screen_are_held_over_the_process_ceiling(
    pinned_pull: tuple[_Stand, TestClient], monkeypatch: pytest.MonkeyPatch
) -> None:
    """A9 of review A on #737: no test spent the ceiling before asking for visible cores.

    The rows on screen are the visible lane, which the floor does not hold; the ceiling
    and a rate-limit hold do.
    """

    from metabrowser.builtin_plugins.github import gh_budget, pulls

    visible, _rest, calls = _visible_core_fixture(
        pinned_pull, monkeypatch, sibling=True, visible=(8,), lane="visible"
    )
    _stand, client = pinned_pull
    ninth = {**visible, "window": {**visible["window"], "id": "viewport"}, "numbers": [9]}
    assert ninth["lane"] == "visible"
    gh_budget.spent(gh_budget.AUTOMATIC_CORE_PER_HOUR, now=pulls.utc_now())
    assert client.post(_PREPARE_CORES, json=ninth).json()["preparation"] == "held"
    # What the cache covers is answered all the same, with no request.
    assert client.post(_PREPARE_CORES, json=visible).json()["preparation"] == "ready"
    assert calls == [(8,)]
    gh_budget.forget()
    assert client.post(_PREPARE_CORES, json=ninth).json()["preparation"] == "started"
    _drain_visible_cores(client)
    assert calls == [(8,), (9,)]


def test_a_spent_speculative_share_holds_the_cores_walk_and_not_the_rows_on_screen(
    pinned_pull: tuple[_Stand, TestClient], monkeypatch: pytest.MonkeyPatch
) -> None:
    """A1 of review A on #737: the walk's batches are speculative, and counted as such."""

    from metabrowser.builtin_plugins.github import gh_budget, pulls

    async def spend() -> None:
        gh_budget.spent(1, now=pulls.utc_now())

    walk, _rest, calls = _visible_core_fixture(
        pinned_pull, monkeypatch, sibling=True, visible=(8,), hold_batch=spend, lane="background"
    )
    _stand, client = pinned_pull
    _drain_visible_cores(client)
    now = pulls.utc_now()
    assert gh_budget.speculative_spent(now) == 1
    # What the stand's own reads spent, which were not the walk's.
    others = gh_budget.automatic_spent(now) - 1
    with gh_budget.speculative():
        gh_budget.spent(gh_budget.SPECULATIVE_CORE_PER_HOUR - 1, now=now)
    assert not gh_budget.over_ceiling(now)
    ninth = {**walk, "window": {**walk["window"], "id": "walk-9"}, "numbers": [9]}
    assert client.post(_PREPARE_CORES, json=ninth).json()["preparation"] == "held"
    assert calls == [(8,)]
    # The same row on screen is read, and its batch is not speculative work.
    on_screen = {**ninth, "window": {**walk["window"], "id": "viewport"}, "lane": "visible"}
    assert client.post(_PREPARE_CORES, json=on_screen).json()["preparation"] == "started"
    _drain_visible_cores(client)
    assert calls == [(8,), (9,)]
    now = pulls.utc_now()
    assert gh_budget.speculative_spent(now) == gh_budget.SPECULATIVE_CORE_PER_HOUR
    assert gh_budget.automatic_spent(now) == others + gh_budget.SPECULATIVE_CORE_PER_HOUR + 1


def test_the_cores_walk_leaves_a_prefetch_with_work_its_caps_and_spends_what_an_idle_one_leaves(
    pinned_pull: tuple[_Stand, TestClient], monkeypatch: pytest.MonkeyPatch
) -> None:
    """D1 and D2 of review D on #737: the walk stopped at 8 points an hour whatever the
    prefetch was doing, so a cold walk of 800 rows took about 13 hours, and no test asked
    for a walk batch through ``request_preparation`` with that part spent. Its batches are
    counted as the walk's; while the served repository's prefetch lane has work the walk
    is held once the share less what the lane's caps can still spend is spent, though the
    share has room; with the lane idle it is read."""

    from collections import deque

    from metabrowser.builtin_plugins.github import gh_budget, pull_prefetch, pulls
    from metabrowser.builtin_plugins.github.pull_prefetch import Item
    from metabrowser.builtin_plugins.github.pull_route import pull_host

    async def spend() -> None:
        gh_budget.spent(1, now=pulls.utc_now())

    walk, _rest, calls = _visible_core_fixture(
        pinned_pull, monkeypatch, sibling=True, visible=(8,), hold_batch=spend, lane="background"
    )
    _stand, client = pinned_pull
    _drain_visible_cores(client)
    now = pulls.utc_now()
    assert (gh_budget.walk_spent(now), gh_budget.speculative_spent(now)) == (1, 1)
    host = pull_host(app)
    assert host is not None
    lane = pull_prefetch.lane_of(host.pulls)
    ninth = {**walk, "window": {**walk["window"], "id": "walk-9"}, "numbers": [9]}
    lane.queue = deque([Item("record", 103)])
    try:
        reserve = pull_prefetch.reserved(now)
        assert reserve == (
            pull_prefetch.RECORDS_PER_HOUR * pull_prefetch.POINTS_PER_RECORD
            + pull_prefetch.FILES_PER_HOUR * pull_prefetch.POINTS_PER_FILES_LIST
        )
        with gh_budget.speculative():
            gh_budget.spent(gh_budget.SPECULATIVE_CORE_PER_HOUR - reserve - 1, now=now)
        assert gh_budget.speculative_spent(now) < gh_budget.SPECULATIVE_CORE_PER_HOUR
        assert client.post(_PREPARE_CORES, json=ninth).json()["preparation"] == "held"
        assert calls == [(8,)]
    finally:
        lane.queue.clear()
    # A lane no page asked for reserves nothing: the walk spends what is left of the share.
    assert client.post(_PREPARE_CORES, json=ninth).json()["preparation"] == "started"
    _drain_visible_cores(client)
    assert calls == [(8,), (9,)]
    assert gh_budget.walk_spent(pulls.utc_now()) == 2


@pytest.mark.parametrize("releases", ["done", "failed"])
def test_the_cores_walk_waits_for_a_backfill_that_is_running_or_due_and_runs_once_done(
    pinned_pull: tuple[_Stand, TestClient], monkeypatch: pytest.MonkeyPatch, releases: str
) -> None:
    """A2 of review A on #761: the walk and the catalog's backfill were first come in
    speculative work's share, so a cold catalog of 5,000 rows, whose Quick Search and ref
    chooser wait for the backfill, read it in about an hour in review A's model. While the
    catalog's backfill has pages and the budget admits them, a background batch is held;
    the rows on screen are not. A backfill whose last refresh failed is not due, so it
    does not hold the walk; once the backfill is done the walk runs."""

    from metabrowser.builtin_plugins.github import pull_cores
    from metabrowser.builtin_plugins.github.gh_lists import utc_stamp
    from metabrowser.builtin_plugins.github.pull_record import PullRefreshStamp

    real_catalog, real_listed = pull_cores.read_catalog, pull_cores.read_list_refresh
    done = [False]
    failed: list[PullRefreshStamp] = []

    def catalog(home: Path, slug: str) -> Any:
        state = real_catalog(home, slug)
        if state is None or done[0]:
            return state
        return state.model_copy(update={"done": {**state.done, "all": False}})

    def listed(home: Path, slug: str, name: Any) -> Any:
        return failed[0] if failed else real_listed(home, slug, name)

    monkeypatch.setattr(pull_cores, "read_catalog", catalog)
    monkeypatch.setattr(pull_cores, "read_list_refresh", listed)
    walk, _rest, calls = _visible_core_fixture(
        pinned_pull, monkeypatch, sibling=True, visible=(8,), lane="visible"
    )
    _stand, client = pinned_pull
    _drain_visible_cores(client)
    assert calls == [(8,)]
    ninth = {
        **walk,
        "window": {**walk["window"], "id": "walk-9"},
        "numbers": [9],
        "lane": "background",
    }
    # The backfill has pages and nothing refuses them: the walk waits for it.
    assert client.post(_PREPARE_CORES, json=ninth).json()["preparation"] == "held"
    assert calls == [(8,)]
    if releases == "done":
        # Done, the backfill holds nothing: the walk runs.
        done[0] = True
    else:
        # A backfill whose last refresh failed, longer ago than the failure itself holds
        # the walk, is due only at its retry: it does not hold the walk meanwhile.
        failed.append(
            PullRefreshStamp(
                outcome="network_error", at=utc_stamp(pulls.utc_now() - timedelta(minutes=5))
            )
        )
    assert client.post(_PREPARE_CORES, json=ninth).json()["preparation"] == "started"
    _drain_visible_cores(client)
    assert calls == [(8,), (9,)]


def _unfinished_catalog(monkeypatch: pytest.MonkeyPatch) -> None:
    """The catalog the walk reads, with its backfill not done, as a first visit's is."""

    from metabrowser.builtin_plugins.github import pull_cores

    real = pull_cores.read_catalog

    def catalog(home: Path, slug: str) -> Any:
        state = real(home, slug)
        return (
            None
            if state is None
            else state.model_copy(update={"done": {**state.done, "all": False}})
        )

    monkeypatch.setattr(pull_cores, "read_catalog", catalog)


def _ninth(walk: dict[str, Any]) -> dict[str, Any]:
    """The background walk's next batch after the rows on screen, pull request 9."""

    return {
        **walk,
        "window": {**walk["window"], "id": "walk-9"},
        "numbers": [9],
        "lane": "background",
    }


@pytest.mark.parametrize(
    ("outcome", "job_running", "preparation"),
    [
        ("succeeded", False, "held"),
        ("network_error", True, "held"),
        ("network_error", False, "started"),
    ],
)
def test_the_catalog_jobs_written_stamp_says_whether_its_backfill_holds_the_walk(
    pinned_pull: tuple[_Stand, TestClient],
    monkeypatch: pytest.MonkeyPatch,
    outcome: str,
    job_running: bool,
    preparation: str,
) -> None:
    """B4 of review B on #761: the catalog job writes a stamp after every page, so the walk
    reads one in production, not none. A stamp that succeeded on an unfinished catalog is a
    backfill the next catalog ask resumes, even with no job running, such as one the budget
    paused: the walk waits. A failed one longer ago than the failure holds the walk is due
    only at its retry: the walk waits while that retry, the catalog job, runs, and not
    otherwise."""

    from metabrowser.builtin_plugins.github.gh_lists import utc_stamp
    from metabrowser.builtin_plugins.github.pull_list import write_list_refresh
    from metabrowser.builtin_plugins.github.pull_list_route import catalog_job_key
    from metabrowser.builtin_plugins.github.pull_record import PullRefreshStamp
    from metabrowser.builtin_plugins.github.pull_route import pull_host

    _unfinished_catalog(monkeypatch)
    walk, _rest, calls = _visible_core_fixture(
        pinned_pull, monkeypatch, sibling=True, visible=(8,), lane="visible"
    )
    stand, client = pinned_pull
    _drain_visible_cores(client)
    assert calls == [(8,)]
    now = pulls.utc_now()
    at = now if outcome == "succeeded" else now - timedelta(minutes=5)
    write_list_refresh(
        stand.published.home,
        stand.published.slug,
        "all",
        PullRefreshStamp(outcome=outcome, at=utc_stamp(at)),
    )
    host = pull_host(app)
    assert host is not None and host.coordinator is not None and client.portal is not None
    coordinator, key = host.coordinator, catalog_job_key(host.pulls.source)
    release: list[asyncio.Event] = []

    async def start_catalog_job() -> None:
        release.append(asyncio.Event())

        async def job() -> None:
            await release[0].wait()

        assert coordinator.start(key, job, network=False) == "started"

    if job_running:
        client.portal.call(start_catalog_job)
    try:
        assert client.post(_PREPARE_CORES, json=_ninth(walk)).json()["preparation"] == preparation
    finally:
        for each in release:
            client.portal.call(each.set)
    _drain_visible_cores(client)
    assert calls == ([(8,)] if preparation == "held" else [(8,), (9,)])


def test_a_walk_held_after_a_rate_limit_lifts_names_no_lapsed_failure(
    pinned_pull: tuple[_Stand, TestClient], monkeypatch: pytest.MonkeyPatch
) -> None:
    """B1 of review B on #761: the walk's last failure is kept until a batch succeeds, and a
    held answer named it. After a rate limit lifted, with the walk held for the catalog's
    backfill, it named the lapsed limit, and the panel, which waits for a reset it is told
    of, asked again every second for the rest of the backfill. Held while the limit holds,
    the answer names it, so the panel wakes once at its reset; held for the backfill after,
    it names none."""

    from metabrowser.builtin_plugins.github.gh_lists import utc_stamp
    from metabrowser.builtin_plugins.github.pull_list import write_list_refresh
    from metabrowser.builtin_plugins.github.pull_record import PullRefreshStamp

    _unfinished_catalog(monkeypatch)
    walk, _rest, calls = _visible_core_fixture(
        pinned_pull, monkeypatch, sibling=True, visible=(8,), lane="visible"
    )
    stand, client = pinned_pull
    _drain_visible_cores(client)
    home, slug = stand.published.home, stand.published.slug
    clock = [pulls.utc_now()]
    monkeypatch.setattr(pulls, "utc_now", lambda: clock[0])
    reset = utc_stamp(clock[0] + timedelta(seconds=2))
    write_list_refresh(
        home,
        slug,
        "all",
        PullRefreshStamp(
            outcome="rate_limited", message="limit", reset_at=reset, at=utc_stamp(clock[0])
        ),
    )
    during = client.post(_PREPARE_CORES, json=_ninth(walk)).json()
    assert (during["preparation"], during["failure"]["outcome"], during["failure"]["reset_at"]) == (
        "held",
        "rate_limited",
        reset,
    )
    # The limit lifts, and the backfill reads its next page.
    clock[0] += timedelta(seconds=3)
    write_list_refresh(
        home, slug, "all", PullRefreshStamp(outcome="succeeded", at=utc_stamp(clock[0]))
    )
    assert client.post(_PREPARE_CORES, json=_ninth(walk)).json() == {
        "preparation": "held",
        "failure": None,
    }
    assert calls == [(8,)]


def test_visible_core_preempts_a_background_batch_that_reads_none_of_its_rows(
    pinned_pull: tuple[_Stand, TestClient], monkeypatch: pytest.MonkeyPatch
) -> None:
    from metabrowser.builtin_plugins.github import pull_cores
    from metabrowser.builtin_plugins.github.pull_list import ListedRepository
    from tests.github_pull_fixture import seed_catalog

    stand, client = pinned_pull
    entries = scenario(stand.origin)["api"]
    rest = {n: entries[f"repos/octo/demo/pulls/{n}"]["body"] for n in (10, 9, 8, 7)}
    repository = ListedRepository(stand.published.home, stand.published.slug, "octo", "demo")
    catalog = seed_catalog(repository, list(rest.values()), reader=READER)
    entered, release, cancelled = threading.Event(), threading.Event(), threading.Event()
    calls: list[tuple[int, ...]] = []

    async def graph(_query: str, variables: dict[str, str | int], **_kwargs: Any) -> dict[str, Any]:
        numbers = tuple(int(v) for k, v in variables.items() if k.startswith("n") and k != "name")
        calls.append(numbers)
        if numbers == (9,):
            entered.set()
            try:
                assert await held_until(release, 5)
            except asyncio.CancelledError:
                cancelled.set()
                raise
        result = graph_core_data(rest[8])
        repo = result["repository"]
        repo.pop("pull")
        for i, number in enumerate(numbers):
            # GitHub has no answer for 8, which keeps its attempt lease.
            repo[f"p{i}"] = (
                None if number == 8 else graph_core_data(rest[number])["repository"]["pull"]
            )
        return result

    monkeypatch.setattr(pull_cores, "gh_graphql", graph)

    def ask(owner: str, numbers: list[int], lane: str) -> dict[str, Any]:
        return {
            "state": "all",
            "window": {"id": owner, "generation": catalog.generation("all")},
            "numbers": numbers,
            "lane": lane,
        }

    assert client.post(_PREPARE_CORES, json=ask("lease", [8], "background")).status_code == 202
    _drain_visible_cores(client)
    assert calls == [(8,)]
    # The walk asks for 8 and 9, but reads only 9: 8 is leased.
    walk = ask("walk", [8, 9], "background")
    visible = ask("viewport", [8, 10], "visible")
    assert client.portal is not None
    try:
        assert client.post(_PREPARE_CORES, json=walk).status_code == 202
        assert entered.wait(5) and calls == [(8,), (9,)]
        # The visible batch also asks for 8, which the walk is not reading, so it does not
        # wait for the walk: it preempts it and reads 10.
        response = client.post(_PREPARE_CORES, json=visible)
        assert (response.status_code, response.json()["preparation"]) == (202, "started")
        assert cancelled.is_set()
    finally:
        release.set()
    _drain_visible_cores(client)
    assert calls == [(8,), (9,), (10,)]
    assert client.portal.call(_core_job_state) == (False, "viewport")
    assert client.post(_PREPARE_CORES, json={**visible, "numbers": []}).json() == {
        "preparation": "released"
    }
    settled = client.post(_PREPARE_CORES, json=visible).json()
    assert settled["preparation"] == "partial"
    assert settled["ready_numbers"] == [10] and settled["retry_numbers"] == [8]
    assert calls == [(8,), (9,), (10,)], "8 keeps its lease"
    assert client.portal.call(_core_job_state) == (False, None)


def test_core_request_lane_is_visible_or_background(
    pinned_pull: tuple[_Stand, TestClient],
) -> None:
    _stand, client = pinned_pull
    ask = {"state": "all", "window": {"id": "lane", "generation": "g"}, "numbers": []}
    for lane in ("viewport", None, 1):
        refused = client.post(_PREPARE_CORES, json={**ask, "lane": lane})
        assert refused.status_code == 400
        assert refused.json()["code"] == "invalid_request"
    for lane in ("visible", "background"):
        assert client.post(_PREPARE_CORES, json={**ask, "lane": lane}).json() == {
            "preparation": "not_owner"
        }


def test_visible_core_attempt_cooldown_ignores_owner_and_filter(
    pinned_pull: tuple[_Stand, TestClient], monkeypatch: pytest.MonkeyPatch
) -> None:
    from metabrowser.builtin_plugins.github.pull_list import ListedRepository
    from tests.github_pull_fixture import seed_catalog

    stand, client = pinned_pull
    ask, rest, calls = _visible_core_fixture(pinned_pull, monkeypatch, sibling=True, visible=(8, 7))
    repository = ListedRepository(stand.published.home, stand.published.slug, "octo", "demo")
    catalog = seed_catalog(repository, list(rest.values()), reader=READER)
    preview = _read(client, 8).json()["core_preview"]
    assert preview is not None
    for state in ("all", "open"):
        rotated = {
            "state": state,
            "window": {"id": f"rotate-{state}", "generation": catalog.generation(state)},
            "numbers": [8],
        }
        response = client.post(_PREPARE_CORES, json=rotated)
        assert response.status_code == 200
        assert response.json() == (
            {"preparation": "ready", "ready_numbers": [8], "skipped_numbers": []}
            if state == "all"
            else {"preparation": "not_owner"}
        )
        assert _read(client, 8).json()["core_preview"] == preview
    assert client.post(_PREPARE_CORES, json={**ask, "numbers": []}).json() == {
        "preparation": "released"
    }
    client.post(_PREPARE_CORES, json=rotated)
    _drain_visible_cores(client)
    assert calls == [(8,)]
    assert client.post(_PREPARE_CORES, json={**rotated, "numbers": []}).json() == {
        "preparation": "not_owner"
    }

    # Overlap alone cannot refetch #8, but it must not stop the unseen #9.
    mixed = {**ask, "window": {**ask["window"], "id": "mixed"}, "numbers": [8, 9]}
    assert client.post(_PREPARE_CORES, json=mixed).status_code == 202
    _drain_visible_cores(client)
    assert calls == [(8,), (9,)]

    corrected = {**rest[8], "title": "Corrected summary at the same timestamp"}
    updated = seed_catalog(repository, [rest[7], corrected, rest[9]], reader=READER)
    changed = {
        **ask,
        "window": {"id": "changed", "generation": updated.generation("all")},
        "numbers": [8],
    }
    assert client.post(_PREPARE_CORES, json=changed).status_code == 202
    _drain_visible_cores(client)
    assert calls == [(8,), (9,), (8,)]


def test_visible_core_mixed_viewport_keeps_durable_overlap_after_freshness_window(
    pinned_pull: tuple[_Stand, TestClient], monkeypatch: pytest.MonkeyPatch
) -> None:
    from types import SimpleNamespace

    from metabrowser.builtin_plugins.github import pull_cores

    now = 1000.0
    monkeypatch.setattr(pull_cores, "time", SimpleNamespace(monotonic=lambda: now))
    _stand, client = pinned_pull
    ask, _rest, calls = _visible_core_fixture(
        pinned_pull, monkeypatch, sibling=True, visible=(8, 7)
    )
    original = _read(client, 8).json()["core_preview"]
    assert original is not None

    now += 10
    successor = {**ask, "window": {**ask["window"], "id": "scrolled"}, "numbers": [8, 9]}
    assert client.post(_PREPARE_CORES, json=successor).status_code == 202
    _drain_visible_cores(client)
    assert calls == [(8,), (9,)]
    assert _read(client, 8).json()["core_preview"] == original
    assert _read(client, 9).json()["core_preview"]["number"] == 9
    assert client.post(_PREPARE_CORES, json={**ask, "numbers": []}).json() == {
        "preparation": "not_owner"
    }

    now = 1000 + pull_cores.FRESHNESS_WINDOW_S + 1
    assert _read(client, 8).json()["core_preview"] == original
    assert _read(client, 9).json()["core_preview"]["number"] == 9
    assert client.post(_PREPARE_CORES, json=successor).json() == {
        "preparation": "ready",
        "ready_numbers": [8, 9],
        "skipped_numbers": [],
    }


def test_visible_core_stale_competitor_preserves_ready_window(
    pinned_pull: tuple[_Stand, TestClient], monkeypatch: pytest.MonkeyPatch
) -> None:
    _stand, client = pinned_pull
    first, _rest, calls = _visible_core_fixture(
        pinned_pull, monkeypatch, sibling=True, visible=(8, 7)
    )
    preview = _read(client, 8).json()["core_preview"]
    assert preview is not None
    stale = {
        **first,
        "window": {"id": "second-tab", "generation": f"old-{first['window']['generation']}"},
        "numbers": [9],
    }
    response = client.post(_PREPARE_CORES, json=stale)
    assert response.status_code == 200 and response.json() == {"preparation": "not_owner"}
    assert _read(client, 8).json()["core_preview"] == preview and calls == [(8,)]

    replacement = {**stale, "window": {**first["window"], "id": "second-tab"}}
    response = client.post(_PREPARE_CORES, json=replacement)
    assert response.status_code == 202 and response.json() == {
        "preparation": "started",
        "status_route": "/api/plugin/github/pull?number=9",
    }
    _drain_visible_cores(client)
    assert client.post(_PREPARE_CORES, json={**first, "numbers": []}).json() == {
        "preparation": "not_owner"
    }
    assert _read(client, 8).json()["core_preview"] == preview
    assert _read(client, 9).json()["core_preview"]["number"] == 9 and calls == [(8,), (9,)]


def test_visible_core_release_during_last_worker_prevents_adoption(
    pinned_pull: tuple[_Stand, TestClient], monkeypatch: pytest.MonkeyPatch
) -> None:
    from metabrowser.builtin_plugins.github import pull_cores

    _stand, client = pinned_pull
    ask, rest, _calls = _visible_core_fixture(pinned_pull, monkeypatch)
    assert _read(client, 8).json()["core_preview"]["comparison_state"] == "not_started"
    catalog_entered, catalog_release = threading.Event(), threading.Event()
    fresh_entered, fresh_release = threading.Event(), threading.Event()
    real_check = pull_cores.CoreWindow.catalog_matches

    def held_check(window: pull_cores.CoreWindow, number: int) -> bool:
        catalog_entered.set()
        assert catalog_release.wait(5)
        return real_check(window, number)

    async def fresh(_query: str, _variables: Any, **_kwargs: Any) -> dict[str, Any]:
        fresh_entered.set()
        assert await held_until(fresh_release, 5)
        return graph_core_data(rest[8])

    monkeypatch.setattr(pull_cores.CoreWindow, "catalog_matches", held_check)
    monkeypatch.setattr(pulls, "gh_graphql", fresh)
    replies: list[Any] = []
    selecting = threading.Thread(
        target=lambda: replies.append(
            client.post(
                "/api/plugin/github/pull-refresh",
                json={"number": 8, "retry": True, "wait_core": True},
            )
        )
    )
    selecting.start()
    try:
        assert catalog_entered.wait(5)
        replacement = {**ask, "window": {**ask["window"], "id": "new-window"}}
        assert client.post(_PREPARE_CORES, json=replacement).json() == {
            "preparation": "ready",
            "ready_numbers": [8],
            "skipped_numbers": [7],
        }
        assert client.post(_PREPARE_CORES, json={**ask, "numbers": []}).json() == {
            "preparation": "released"
        }
        catalog_release.set()
        assert fresh_entered.wait(5)
        pending = _read(client, 8).json()
        assert pending["refreshing"] and pending["core_preview"]["number"] == 8
    finally:
        catalog_release.set()
        fresh_release.set()
        selecting.join(10)
    assert not selecting.is_alive() and len(replies) == 1 and replies[0].status_code == 202


@pytest.mark.parametrize("when", ["initial", "viewer", "final"])
def test_visible_core_observed_reader_change_revokes_old_viewer_sibling(
    pinned_pull: tuple[_Stand, TestClient], monkeypatch: pytest.MonkeyPatch, when: str
) -> None:
    _stand, client = pinned_pull
    _ask, rest, calls = _visible_core_fixture(pinned_pull, monkeypatch, sibling=True)
    assert _read(client, 9).json()["core_preview"]["reader"] == f"gh:{READER}"
    accounts = 0

    async def account() -> str:
        nonlocal accounts
        accounts += 1
        return "changed" if when == "initial" or (when == "final" and accounts == 2) else READER

    async def graph(_query: str, _variables: Any, **_kwargs: Any) -> dict[str, Any]:
        return graph_core_data(
            rest[8], reader="changed" if when in {"initial", "viewer"} else READER
        )

    monkeypatch.setattr(pulls, "active_account", account)
    monkeypatch.setattr(pulls, "gh_graphql", graph)
    started = client.post(
        "/api/plugin/github/pull-refresh", json={"number": 8, "retry": True, "wait_core": True}
    )
    assert started.status_code == 202
    _drain_visible_cores(client)
    assert _read(client, 9).json()["core_preview"] is None and calls == [(8, 9)]
    selected = _read(client, 8).json()
    if when == "initial":
        assert selected["record"]["reader"] == "gh:changed"
    else:
        assert (
            selected["record"] is None and selected["last_refresh"]["outcome"] == "account_changed"
        )


@pytest.mark.parametrize(
    "stamp,visible", [("2000-01-01T00:00:00Z", False), ("2090-01-01T00:00:00Z", True)]
)
def test_visible_core_requires_provider_at_least_as_new_as_admitted_row(
    pinned_pull: tuple[_Stand, TestClient],
    monkeypatch: pytest.MonkeyPatch,
    stamp: str,
    visible: bool,
) -> None:
    _stand, client = pinned_pull
    _ask, _rest, calls = _visible_core_fixture(pinned_pull, monkeypatch, provider_stamp=stamp)
    preview = _read(client, 8).json()["core_preview"]
    assert (preview is not None) is visible and calls == [(8,)]
    if preview is not None:
        assert preview["pull"]["updated_at"] == stamp


def test_visible_core_does_not_follow_an_untrustworthy_record_entry(
    pinned_pull: tuple[_Stand, TestClient], monkeypatch: pytest.MonkeyPatch
) -> None:
    stand, client = pinned_pull
    _ask, _rest, calls = _visible_core_fixture(pinned_pull, monkeypatch, untrustworthy=True)
    assert calls == [(8,)] and _read(client, 8).json()["core_preview"]["number"] == 8
    assert (stand.published.home / source_pull_record(stand.published.slug, 8)).is_symlink()
    assert not (stand.published.home / "missing-untrusted-target").exists()


@pytest.mark.parametrize(
    "field,value",
    [("updated_at", "2090-01-01T00:00:00Z"), ("title", "Corrected summary title")],
    ids=["changed-timestamp", "same-timestamp-summary"],
)
def test_visible_core_keeps_stale_display_but_changed_row_requires_revalidation(
    pinned_pull: tuple[_Stand, TestClient], monkeypatch: pytest.MonkeyPatch, field: str, value: str
) -> None:
    from metabrowser.builtin_plugins.github.pull_catalog import catalog_row
    from metabrowser.builtin_plugins.github.pull_list import ListedRepository
    from tests.github_pull_fixture import seed_catalog

    stand, client = pinned_pull
    ask, rest, calls = _visible_core_fixture(pinned_pull, monkeypatch)
    repository = ListedRepository(stand.published.home, stand.published.slug, "octo", "demo")
    appended = [*rest.values(), {**rest[7], "number": 6}]
    catalog = seed_catalog(repository, appended, reader=READER)
    assert catalog.generation("all") == ask["window"]["generation"]
    assert client.post(_PREPARE_CORES, json=ask).json() == {
        "preparation": "ready",
        "ready_numbers": [8],
        "skipped_numbers": [7],
    }
    before = _read(client, 8)
    assert before.json()["core_preview"] is not None

    prepended = [*appended, {**rest[7], "number": 109}]
    shifted = seed_catalog(repository, prepended, reader=READER)
    assert shifted.epoch == catalog.epoch
    assert shifted.revision == catalog.revision + 1
    assert shifted.generations == {
        **catalog.generations,
        "all": catalog.generations["all"] + 1,
        "open": catalog.generations["open"] + 1,
    }
    assert _read(client, 8, etag=before.headers["etag"]).status_code == 304
    # A new token with an old generation is not an admitted preparation. Replaying
    # the old exact ask does not grant a ready receipt or revoke the held description.
    stale = {**ask, "window": {**ask["window"], "id": "stale-after-prepend"}}
    assert client.post(_PREPARE_CORES, json=stale).json() == {"preparation": "not_owner"}
    assert client.post(_PREPARE_CORES, json=ask).json() == {"preparation": "not_owner"}
    assert _read(client, 8).json()["core_preview"] == before.json()["core_preview"]

    corrected = {**rest[8], field: value}
    changed = [corrected if item["number"] == 8 else item for item in prepended]
    catalog = seed_catalog(repository, changed, reader=READER)
    assert catalog.generation("all") != shifted.generation("all")
    stored = catalog_row(repository.home, repository.slug, 8)
    assert stored is not None
    assert (stored.updated_at, stored.title) == (corrected["updated_at"], corrected["title"])
    assert client.post(_PREPARE_CORES, json=ask).json() == {"preparation": "not_owner"}
    # The old description remains readable, but its fingerprint cannot claim this
    # newly changed catalog row as prepared.
    assert _read(client, 8).json()["core_preview"] == before.json()["core_preview"]
    assert calls == [(8,)]


def test_visible_core_revokes_staged_reader_while_failure_stamp_is_held(
    pinned_pull: tuple[_Stand, TestClient], monkeypatch: pytest.MonkeyPatch
) -> None:
    _stand, client = pinned_pull
    _ask, rest, _calls = _visible_core_fixture(pinned_pull, monkeypatch, sibling=True)
    final_entered, final_release = threading.Event(), threading.Event()
    stamp_entered, stamp_release = threading.Event(), threading.Event()
    actual_keep_stamp = pulls._keep_stamp
    accounts = 0

    async def account() -> str:
        nonlocal accounts
        accounts += 1
        if accounts == 1:
            return READER
        assert accounts == 2
        final_entered.set()
        assert await held_until(final_release, 5)
        return "changed"

    async def graph(_query: str, _variables: Any, **_kwargs: Any) -> dict[str, Any]:
        return graph_core_data(rest[8])

    def held_stamp(published: Any, number: int, fields: dict[str, Any], expected: Any) -> None:
        if number == 8 and fields["outcome"] == "account_changed":
            stamp_entered.set()
            assert stamp_release.wait(5)
        actual_keep_stamp(published, number, fields, expected)

    monkeypatch.setattr(pulls, "active_account", account)
    monkeypatch.setattr(pulls, "gh_graphql", graph)
    monkeypatch.setattr(pulls, "_keep_stamp", held_stamp)
    try:
        started = client.post(
            "/api/plugin/github/pull-refresh", json={"number": 8, "retry": True, "wait_core": True}
        )
        assert started.status_code == 202 and final_entered.wait(5)
        first = _read(client, 8)
        preview = first.json()["core_preview"]
        assert preview["reader"] == f"gh:{READER}" and preview["comparison_state"] == "pending"
        assert _read(client, 9).json()["core_preview"]["reader"] == f"gh:{READER}"

        final_release.set()
        assert stamp_entered.wait(5)
        pending = _read(client, 8, etag=first.headers["etag"])
        assert pending.status_code == 200 and pending.headers["etag"] != first.headers["etag"]
        assert pending.json()["refreshing"] is True
        assert pending.json()["record"] is None and pending.json()["core_preview"] is None
        assert _read(client, 9).json()["core_preview"] is None
    finally:
        final_release.set()
        stamp_release.set()
        _drain_visible_cores(client)
    selected = _read(client, 8).json()
    assert (
        selected["core_preview"] is None
        and selected["last_refresh"]["outcome"] == "account_changed"
    )


def test_visible_core_batch_keeps_unchanged_member_after_sibling_update(
    pinned_pull: tuple[_Stand, TestClient], monkeypatch: pytest.MonkeyPatch
) -> None:
    from metabrowser.builtin_plugins.github.pull_list import ListedRepository
    from tests.github_pull_fixture import seed_catalog

    stand, client = pinned_pull
    entered, release = threading.Event(), threading.Event()

    async def hold_batch() -> None:
        entered.set()
        assert await held_until(release, 5)

    ask, rest, calls = _visible_core_fixture(
        pinned_pull, monkeypatch, sibling=True, hold_batch=hold_batch
    )
    try:
        assert entered.wait(5)
        repository = ListedRepository(stand.published.home, stand.published.slug, "octo", "demo")
        changed = {**rest[9], "updated_at": "2090-01-01T00:00:00Z"}
        catalog = seed_catalog(repository, [rest[7], rest[8], changed], reader=READER)
        assert catalog.generation("all") != ask["window"]["generation"]
    finally:
        release.set()
        _drain_visible_cores(client)
    stable = _read(client, 8).json()
    assert stable["record"] is None and stable["core_preview"] is not None
    assert stable["core_preview"]["number"] == 8
    assert _read(client, 9).json()["core_preview"] is None
    assert calls == [(8, 9)]


def test_visible_core_adopted_display_keeps_stale_cache_until_selected_refresh(
    pinned_pull: tuple[_Stand, TestClient], monkeypatch: pytest.MonkeyPatch
) -> None:
    from metabrowser.builtin_plugins.github.pull_list import ListedRepository
    from tests.github_pull_fixture import seed_catalog

    stand, client = pinned_pull
    ask, rest, calls = _visible_core_fixture(pinned_pull, monkeypatch, sibling=True)
    held = _read(client, 8)
    prepared = held.json()["core_preview"]
    assert prepared["comparison_state"] == "not_started"
    assert _read(client, 9).json()["core_preview"] is not None
    repository = ListedRepository(stand.published.home, stand.published.slug, "octo", "demo")
    corrected = {**rest[9], "title": "Corrected sibling summary"}
    members = [rest[7], rest[8], corrected]
    corrected_catalog = seed_catalog(repository, members, reader=READER)
    assert corrected_catalog.generation("all") != ask["window"]["generation"]
    assert _read(client, 9).json()["core_preview"]["pull"]["title"] == rest[9]["title"]
    assert _read(client, 8, etag=held.headers["etag"]).status_code == 304
    opted = f"/api/plugin/github/pull?number=8&wait_full_after={prepared['revision']}"

    async def unexpected_wait(_served: ServedPull, _preview: Any) -> bool:
        pytest.fail("a prepared or adopted description cannot take the settlement lease")

    monkeypatch.setattr(ServedPull, "wait_for_full", unexpected_wait)
    assert client.get(opted).json()["core_preview"] == prepared
    fresh_entered, fresh_release = threading.Event(), threading.Event()
    new_body = {
        **rest[8],
        "updated_at": "2090-01-01T00:00:00Z",
        "body": "Fresh selected description",
    }

    async def fresh(_query: str, _variables: Any, **_kwargs: Any) -> dict[str, Any]:
        fresh_entered.set()
        assert await held_until(fresh_release, 5)
        return graph_core_data(new_body)

    monkeypatch.setattr(pulls, "gh_graphql", fresh)
    replies: list[Any] = []
    selecting = threading.Thread(
        target=lambda: replies.append(
            client.post(
                "/api/plugin/github/pull-refresh",
                json={"number": 8, "retry": True, "wait_core": True},
            )
        )
    )
    selecting.start()
    try:
        assert fresh_entered.wait(5)
        pending = client.get(opted).json()
        assert pending["refreshing"] and pending["core_preview"] == prepared
        assert client.post(_PREPARE_CORES, json={**ask, "numbers": []}).json() == {
            "preparation": "released"
        }
        appended = [*members, {**rest[7], "number": 6}]
        catalog = seed_catalog(repository, appended, reader=READER)
        assert catalog.generation("all") == corrected_catalog.generation("all")
        unchanged = _read(client, 8)
        assert unchanged.json()["core_preview"] == prepared
        prepended = [*appended, {**rest[7], "number": 109}]
        shifted = seed_catalog(repository, prepended, reader=READER)
        assert shifted.epoch == catalog.epoch
        assert shifted.generation("all") != catalog.generation("all")
        assert _read(client, 8, etag=unchanged.headers["etag"]).status_code == 304
        changed = [new_body if item["number"] == 8 else item for item in prepended]
        catalog = seed_catalog(repository, changed, reader=READER)
        assert catalog.generation("all") != shifted.generation("all")
        # The stale durable description remains useful until the selected read
        # publishes its new core. An unrelated catalog write cannot blank it.
        assert _read(client, 8, etag=unchanged.headers["etag"]).status_code == 304
        assert _read(client, 8).json()["core_preview"] == prepared
    finally:
        fresh_release.set()
        selecting.join(10)
    assert not selecting.is_alive() and len(replies) == 1 and replies[0].status_code == 202
    _drain_visible_cores(client)
    final = _read(client, 8).json()
    assert not final["refreshing"] and final["core_preview"] is None
    assert final["record"]["pull"]["body"] == "Fresh selected description"
    assert calls == [(8, 9)]


def test_visible_core_competitor_waits_for_selected_acquisition_to_settle(
    pinned_pull: tuple[_Stand, TestClient], monkeypatch: pytest.MonkeyPatch
) -> None:
    from types import SimpleNamespace

    from metabrowser.builtin_plugins.github import pull_cores
    from metabrowser.builtin_plugins.github.pull_route import pull_host

    now = 1000.0
    monkeypatch.setattr(pull_cores, "time", SimpleNamespace(monotonic=lambda: now))
    _stand, client = pinned_pull
    ask, rest, calls = _visible_core_fixture(pinned_pull, monkeypatch, sibling=True)
    ready = _read(client, 9).json()["core_preview"]
    assert ready is not None
    competitor = {**ask, "window": {**ask["window"], "id": "next-window"}, "numbers": [9]}
    final_entered, final_release = threading.Event(), threading.Event()
    accounts = 0

    async def account() -> str:
        nonlocal accounts
        accounts += 1
        if accounts == 2:
            final_entered.set()
            assert await held_until(final_release, 5)
        return READER

    async def graph(_query: str, variables: Any, **_kwargs: Any) -> dict[str, Any]:
        assert variables["number"] == 8
        return graph_core_data(rest[8])

    def selected_state() -> tuple[bool, bool, int]:
        host = pull_host(app)
        assert host is not None and host.coordinator is not None
        return host.running(8), host.coordinator.slot().locked(), host.pulls.foreground_intents

    monkeypatch.setattr(pulls, "active_account", account)
    monkeypatch.setattr(pulls, "gh_graphql", graph)
    try:
        selected = client.post(
            "/api/plugin/github/pull-refresh", json={"number": 8, "retry": True, "wait_core": True}
        )
        assert selected.status_code == 202 and final_entered.wait(5)
        assert selected.json()["pull"]["core_preview"]["comparison_state"] == "pending"
        assert client.portal is not None
        assert client.portal.call(selected_state) == (True, False, 0)
        assert _read(client, 8).json()["record"] is None
        refused = client.post(_PREPARE_CORES, json=competitor)
        assert refused.status_code == 200 and refused.json() == {
            "preparation": "ready",
            "ready_numbers": [9],
            "skipped_numbers": [],
        }
        assert _read(client, 9).json()["core_preview"] == ready and calls == [(8, 9)]
        assert client.post(_PREPARE_CORES, json={**ask, "numbers": []}).json() == {
            "preparation": "released"
        }
        assert _read(client, 9).json()["core_preview"] == ready
    finally:
        final_release.set()
        _drain_visible_cores(client)
    assert _read(client, 8).json()["record"]["number"] == 8
    client.post(_PREPARE_CORES, json=competitor)
    _drain_visible_cores(client)
    assert _read(client, 9).json()["core_preview"] == ready and calls == [(8, 9)]

    now += pull_cores.FRESHNESS_WINDOW_S
    admitted = client.post(_PREPARE_CORES, json=competitor)
    assert admitted.status_code == 200 and admitted.json()["preparation"] == "ready"
    assert _read(client, 9).json()["core_preview"] == ready
    assert calls == [(8, 9)]


@pytest.mark.parametrize("number", [8, 9], ids=["matching", "unrelated"])
def test_visible_core_running_batch_drains_before_selected_refresh(
    pinned_pull: tuple[_Stand, TestClient], monkeypatch: pytest.MonkeyPatch, number: int
) -> None:
    stand, client = pinned_pull
    batch_entered, cleanup_entered, cleanup_release = (
        threading.Event(),
        threading.Event(),
        threading.Event(),
    )
    fresh_entered, fresh_release = threading.Event(), threading.Event()

    async def hold_batch() -> None:
        batch_entered.set()
        try:
            await asyncio.Future()
        except asyncio.CancelledError:
            cleanup_entered.set()
            assert await held_until(cleanup_release, 5)
            raise

    ask, rest, calls = _visible_core_fixture(pinned_pull, monkeypatch, hold_batch=hold_batch)
    fresh_rest = (
        rest[8] if number == 8 else scenario(stand.origin)["api"]["repos/octo/demo/pulls/9"]["body"]
    )

    async def fresh(_query: str, variables: Any, **_kwargs: Any) -> dict[str, Any]:
        assert variables["number"] == number
        fresh_entered.set()
        assert await held_until(fresh_release, 5)
        return graph_core_data(fresh_rest)

    monkeypatch.setattr(pulls, "gh_graphql", fresh)
    replies: list[Any] = []
    selecting = threading.Thread(
        target=lambda: replies.append(
            client.post(
                "/api/plugin/github/pull-refresh",
                json={"number": number, "retry": True, "wait_core": True},
            )
        )
    )
    assert batch_entered.wait(5)
    selecting.start()
    try:
        assert cleanup_entered.wait(5)
        # Read through the same server loop while cancellation cleanup is held.
        pending = _read(client, number).json()
        assert not pending["refreshing"] and pending["core_preview"] is None
        assert not fresh_entered.is_set()
        assert client.post(_PREPARE_CORES, json={**ask, "numbers": []}).json() == {
            "preparation": "not_owner"
        }
        cleanup_release.set()
        assert fresh_entered.wait(5)
        assert _read(client, 8).json()["core_preview"] is None
    finally:
        cleanup_release.set()
        fresh_release.set()
        selecting.join(10)
    assert not selecting.is_alive() and len(replies) == 1 and replies[0].status_code == 202
    _drain_visible_cores(client)
    final = _read(client, number).json()
    assert final["record"]["pull"]["number"] == number and not final["refreshing"]
    assert final["core_preview"] is None and calls == [(8,)]


_TIMELINE_ROUTE = "/api/plugin/github/pull-timeline"


def _timeline_page(
    record: PullRecord,
    nodes: list[dict[str, Any]],
    cursor: str | None,
    *,
    reader: str = READER,
    base_ref: str | None = None,
) -> dict[str, Any]:
    return {
        "viewer": {"login": reader},
        "repository": {
            "nameWithOwner": "octo/demo",
            "pullRequest": {
                "number": record.number,
                "baseRefName": record.pull.base.ref if base_ref is None else base_ref,
                "baseRefOid": "f" * 40,  # The provider target tip can advance.
                "headRefOid": record.pull.head.sha,
                "timelineItems": {
                    "nodes": nodes,
                    "pageInfo": {"hasNextPage": cursor is not None, "endCursor": cursor},
                },
            },
        },
    }


def test_timeline_bounds_and_reuses_the_ordered_discussion(
    pinned_pull: tuple[_Stand, TestClient], monkeypatch: pytest.MonkeyPatch
) -> None:
    from metabrowser.builtin_plugins.github import pull_timeline
    from metabrowser.cache.paths import source_pull_timeline
    from metabrowser.mirror_refresh import refresh_coordinator

    stand, client = pinned_pull
    home, slug = stand.published.home, stand.published.slug
    record = stand.record(7)
    assert isinstance(record, PullRecord)
    ident = (1 << 53) + 1
    comment = record.issue_comments[0].model_copy(update={"id": ident})
    record = record.model_copy(update={"issue_comments": (comment,), "projection_version": 0})
    write_pull_record(home, slug, record)
    record_path = home / source_pull_record(slug, 7)
    before = record_path.read_bytes()
    envelope = _read(client, 7).json()
    revision = envelope["record_revision"]
    assert envelope["record"]["issue_comments"][0]["timeline_id"] == str(ident)
    assert (
        client.get(
            "/api/plugin/github/pull-markdown",
            params={"number": 7, "part": f"issue_comment/{ident}"},
        ).status_code
        == 200
    )
    page_one = [
        {
            "__typename": "PullRequestCommit",
            "commit": {
                "oid": record.pull.head.sha,
                "messageHeadline": "A subject",
                "committedDate": record.pull.created_at,
            },
        },
        {"__typename": "IssueComment", "fullDatabaseId": ident},
        {"__typename": "PullRequestReview", "state": "PENDING", "fullDatabaseId": None},
        *({"__typename": "IssueComment", "fullDatabaseId": value} for value in range(1, 98)),
    ]
    page_two = [
        {"__typename": "IssueComment", "fullDatabaseId": str(ident)},
        {
            "__typename": "PullRequestReview",
            "state": "APPROVED",
            "fullDatabaseId": str(record.reviews[0].id),
        },
        *({"__typename": "IssueComment", "fullDatabaseId": value} for value in range(98, 196)),
    ]
    cursors: list[str | None] = []

    async def graph(query: str, variables: dict[str, Any], *, max_bytes: int) -> dict[str, Any]:
        assert "first: 100" in query and "fullDatabaseId" in query
        assert "baseRefName" in query and "baseRefOid" not in query
        assert max_bytes == pull_timeline.MAX_PROVIDER_BYTES
        assert [variables[key] for key in ("owner", "name", "number")] == ["octo", "demo", 7]
        cursor = variables["cursor"]
        cursors.append(cursor)
        if cursor is None:
            return _timeline_page(record, page_one, "page-two")
        assert cursor == "page-two"
        return _timeline_page(record, page_two, "still-more")

    monkeypatch.setattr(pull_timeline, "gh_graphql", graph)
    ask = {"number": 7, "record_revision": revision}
    cache_only = {**ask, "cached_only": True}
    assert client.post(_TIMELINE_ROUTE, json=cache_only, headers=_JSON).json() == {
        "record_revision": revision,
        "state": "unavailable",
        "events": [],
    }
    assert (
        client.post(_TIMELINE_ROUTE, json={**ask, "cached_only": "true"}, headers=_JSON).status_code
        == 400
    )
    assert cursors == []
    coordinator = refresh_coordinator(app)
    assert coordinator is not None and client.portal is not None
    slot = coordinator.slot()

    async def take_foreground_slots() -> int:
        count = 0
        while not slot.locked():
            await slot.acquire()
            count += 1
        return count

    held_slots = client.portal.call(take_foreground_slots)
    assert held_slots > 0
    try:
        # The optional provider must run even while the foreground pool is occupied.
        response = client.post(_TIMELINE_ROUTE, json=ask, headers=_JSON)
    finally:
        for _ in range(held_slots):
            client.portal.call(slot.release)
    assert response.status_code == 200 and response.headers["cache-control"] == "no-store"
    timeline = response.json()
    assert timeline["record_revision"] == revision and timeline["state"] == "partial"
    events = timeline["events"]
    assert len(events) == 198
    assert [item["kind"] for item in events[:2]] == ["commit", "comment"]
    assert events[1] == {"kind": "comment", "id": str(ident)}
    assert [item["kind"] for item in events if item["kind"] == "review"] == ["review"]
    assert cursors == [None, "page-two"]
    assert record_path.read_bytes() == before
    cache = home / source_pull_timeline(slug, 7)
    assert cache.is_file()
    held = cache.read_bytes()
    assert client.post(_TIMELINE_ROUTE, json=cache_only, headers=_JSON).json() == timeline

    # Text and base-tip changes alter the full revision while preserving timeline inputs.
    advanced = record.pull.base.model_copy(update={"sha": "f" * 40})
    newer = record.model_copy(
        update={"pull": record.pull.model_copy(update={"body": "Edit", "base": advanced})}
    )
    write_pull_record(home, slug, newer)
    next_revision = _read(client, 7).json()["record_revision"]
    assert next_revision != revision
    assert client.post(_TIMELINE_ROUTE, json=ask, headers=_JSON).json()["state"] == "unavailable"
    assert client.post(
        _TIMELINE_ROUTE, json={**cache_only, "record_revision": next_revision}, headers=_JSON
    ).json() == {**timeline, "record_revision": next_revision}
    retargeted = advanced.model_copy(update={"ref": "another-target"})
    write_pull_record(
        home,
        slug,
        newer.model_copy(update={"pull": newer.pull.model_copy(update={"base": retargeted})}),
    )
    retargeted_revision = _read(client, 7).json()["record_revision"]
    assert (
        client.post(
            _TIMELINE_ROUTE,
            json={**cache_only, "record_revision": retargeted_revision},
            headers=_JSON,
        ).json()["state"]
        == "unavailable"
    )
    assert cursors == [None, "page-two"] and cache.read_bytes() == held


def test_timeline_refuses_a_changed_viewer_or_superseded_record(
    pinned_pull: tuple[_Stand, TestClient], monkeypatch: pytest.MonkeyPatch
) -> None:
    from metabrowser.builtin_plugins.github import pull_timeline
    from metabrowser.cache.paths import source_pull_timeline

    stand, client = pinned_pull
    home, slug = stand.published.home, stand.published.slug
    record = stand.record(7)
    assert isinstance(record, PullRecord)
    revision = _read(client, 7).json()["record_revision"]
    cache = home / source_pull_timeline(slug, 7)
    ask = {"number": 7, "record_revision": revision}
    absent = {"record_revision": revision, "state": "unavailable", "events": []}
    cursors: list[str | None] = []
    failure = "viewer"

    async def graph(_query: str, variables: dict[str, Any], **_kwargs: Any) -> dict[str, Any]:
        cursor = variables["cursor"]
        cursors.append(cursor)
        if cursor is None:
            return _timeline_page(
                record,
                [{"__typename": "IssueComment", "fullDatabaseId": "7"}],
                "page-two",
            )
        if failure == "viewer":
            return _timeline_page(record, [], None, reader="someone-else")
        if failure == "target":
            return _timeline_page(record, [], None, base_ref="another-target")
        if failure == "malformed":
            return _timeline_page(record, [{"__typename": "IssueComment"}], None)
        newer = record.model_copy(update={"pull": record.pull.model_copy(update={"body": "Edit"})})
        await asyncio.to_thread(write_pull_record, home, slug, newer)
        return _timeline_page(record, [], None)

    monkeypatch.setattr(pull_timeline, "gh_graphql", graph)
    for reason in ("viewer", "target", "malformed", "superseded"):
        failure = reason
        assert client.post(_TIMELINE_ROUTE, json=ask, headers=_JSON).json() == absent
        assert not cache.exists()
    assert client.post(_TIMELINE_ROUTE, json=ask, headers=_JSON).json() == absent
    assert cursors == [None, "page-two"] * 4


def test_timeline_disconnect_cancels_a_held_second_page(
    pinned_pull: tuple[_Stand, TestClient], monkeypatch: pytest.MonkeyPatch
) -> None:
    from starlette.types import Message, Receive, Scope, Send

    from metabrowser.builtin_plugins.github import pull_timeline
    from metabrowser.cache.paths import source_pull_timeline

    stand, client = pinned_pull
    record = stand.record(7)
    assert isinstance(record, PullRecord)
    revision = _read(client, 7).json()["record_revision"]
    ask = {"number": 7, "record_revision": revision}
    started = asyncio.Event()
    cancelled = False

    async def graph(_query: str, variables: dict[str, Any], **_kwargs: Any) -> dict[str, Any]:
        nonlocal cancelled
        if variables["cursor"] is None:
            return _timeline_page(
                record,
                [{"__typename": "IssueComment", "fullDatabaseId": "7"}],
                "page-two",
            )
        started.set()
        try:
            await asyncio.Event().wait()
        except asyncio.CancelledError:
            cancelled = True
            raise
        raise AssertionError("the disconnected request kept its provider process")

    async def disconnected(scope: Scope, receive: Receive, send: Send) -> None:
        body_read = False

        async def disconnect_after_second_page_starts() -> Message:
            nonlocal body_read
            if not body_read:
                body_read = True
                return await receive()
            await started.wait()
            return {"type": "http.disconnect"}

        await app(scope, disconnect_after_second_page_starts, send)

    monkeypatch.setattr(pull_timeline, "gh_graphql", graph)
    with TestClient(disconnected) as disconnected_client:
        response = disconnected_client.post(_TIMELINE_ROUTE, json=ask, headers=_JSON)
    assert response.json() == {
        "record_revision": revision,
        "state": "unavailable",
        "events": [],
    }
    assert cancelled
    assert not (stand.published.home / source_pull_timeline(stand.published.slug, 7)).exists()


def test_timeline_keeps_only_verified_transient_results_in_the_current_view(
    pinned_pull: tuple[_Stand, TestClient], monkeypatch: pytest.MonkeyPatch
) -> None:
    from metabrowser.builtin_plugins.github import pull_timeline
    from metabrowser.cache.paths import source_pull_timeline

    stand, client = pinned_pull
    record = stand.record(7)
    assert isinstance(record, PullRecord)
    revision = _read(client, 7).json()["record_revision"]
    ask = {"number": 7, "record_revision": revision}
    absent = {"record_revision": revision, "state": "unavailable", "events": []}
    first = {"kind": "comment", "id": "7"}
    cache = stand.published.home / source_pull_timeline(stand.published.slug, 7)
    provider_error: Exception | None = None
    failure_cursor: str | None = None
    cursors: list[str | None] = []

    async def graph(_query: str, variables: dict[str, Any], **_kwargs: Any) -> dict[str, Any]:
        cursor = variables["cursor"]
        cursors.append(cursor)
        if provider_error is not None and cursor == failure_cursor:
            if isinstance(provider_error, TimeoutError):
                await asyncio.Event().wait()
            raise provider_error
        if cursor is None:
            return _timeline_page(
                record, [{"__typename": "IssueComment", "fullDatabaseId": "7"}], "page-two"
            )
        return _timeline_page(record, [{"__typename": "IssueComment", "fullDatabaseId": "8"}], None)

    monkeypatch.setattr(pull_timeline, "gh_graphql", graph)
    gate = asyncio.Lock()
    monkeypatch.setattr(app.state, "github_pull_timeline_gate", gate, raising=False)
    assert client.portal is not None
    client.portal.call(gate.acquire)
    try:
        with monkeypatch.context() as fast:
            fast.setattr(pull_timeline, "TIMEOUT_S", 0.05)
            assert client.post(_TIMELINE_ROUTE, json=ask, headers=_JSON).json() == {
                **absent,
                "retryable": True,
            }
    finally:
        client.portal.call(gate.release)
    assert cursors == []

    network_error = GhError("connection reset", state="network_error")
    provider_error = network_error
    assert client.post(_TIMELINE_ROUTE, json=ask, headers=_JSON).json() == {
        **absent,
        "retryable": True,
    }
    failure_cursor = "page-two"
    with monkeypatch.context() as fast:
        fast.setattr(pull_timeline, "TIMEOUT_S", 1.0)
        for error in (network_error, TimeoutError()):
            provider_error = error
            assert client.post(_TIMELINE_ROUTE, json=ask, headers=_JSON).json() == {
                "record_revision": revision,
                "state": "partial",
                "events": [first],
                "retryable": True,
            }
            assert not cache.exists()
    for error in (
        GhError("gh missing", state="gh_missing"),
        GhError("sign in", state="not_logged_in"),
        GhError("rate limit", state="rate_limited"),
    ):
        provider_error = error
        assert client.post(_TIMELINE_ROUTE, json=ask, headers=_JSON).json() == absent
        assert not cache.exists()

    provider_error = None
    complete = client.post(_TIMELINE_ROUTE, json=ask, headers=_JSON).json()
    assert complete == {
        "record_revision": revision,
        "state": "complete",
        "events": [first, {"kind": "comment", "id": "8"}],
    }
    assert cache.is_file()


def test_durable_core_batches_cross_viewports_and_restart_offline(
    pinned_pull: tuple[_Stand, TestClient], monkeypatch: pytest.MonkeyPatch
) -> None:
    from metabrowser.builtin_plugins.github import pull_cores
    from metabrowser.builtin_plugins.github.pull_list import ListedRepository
    from tests.github_pull_fixture import seed_catalog

    stand, client = pinned_pull
    first, rest, calls = _visible_core_fixture(pinned_pull, monkeypatch, visible=(8, 7))
    # Deliberately more total candidates than both the transport batch and this
    # reduced transient attempt capacity. Successful batches must free that budget.
    monkeypatch.setattr(pull_cores, "_MAX_CORE_ATTEMPTS", 8)
    for number in range(20, 36):
        rest[number] = {
            **rest[8],
            "number": number,
            "title": f"Work {number}",
            "body": f"Description {number}",
        }
    repository = ListedRepository(stand.published.home, stand.published.slug, "octo", "demo")
    catalog = seed_catalog(repository, list(rest.values()), reader=READER)
    for offset in (20, 28):
        numbers = list(range(offset, offset + 8))
        ask = {
            "state": "all",
            "window": {"id": f"batch-{offset}", "generation": catalog.generation("all")},
            "numbers": numbers,
        }
        assert client.post(_PREPARE_CORES, json=ask).status_code == 202
        _drain_visible_cores(client)
        assert client.post(_PREPARE_CORES, json=ask).json() == {
            "preparation": "ready",
            "ready_numbers": numbers,
            "skipped_numbers": [],
        }
        assert client.post(_PREPARE_CORES, json={**ask, "numbers": []}).json() == {
            "preparation": "released"
        }
    assert calls == [(8,), tuple(range(20, 28)), tuple(range(28, 36))]
    original = _read(client, 8).json()["core_preview"]
    assert original is not None

    def restart() -> None:
        session = mirror_session(app)
        assert session is not None
        session.pull_requests = ServedPulls(stand.published)

    assert client.portal is not None
    client.portal.call(restart)
    monkeypatch.setattr(pulls, "utc_now", lambda: datetime(2090, 1, 1, tzinfo=UTC))

    async def offline(*_args: Any, **_kwargs: Any) -> Any:
        raise AssertionError("cached core replay must not invoke GitHub")

    monkeypatch.setattr(pull_cores, "gh_graphql", offline)
    for number in (8, *range(20, 36)):
        body = _read(client, number).json()
        assert body["record"] is None and body["core_preview"]["number"] == number
    assert _read(client, 8).json()["core_preview"] == original
    replay = {**first, "window": {"id": "new-process", "generation": catalog.generation("all")}}
    assert client.post(_PREPARE_CORES, json=replay).json() == {
        "preparation": "ready",
        "ready_numbers": [8],
        "skipped_numbers": [7],
    }
    # A changed reader replaces the catalog epoch; old private cores cannot answer.
    seed_catalog(repository, list(rest.values()), reader="different-reader")
    assert _read(client, 8).json()["core_preview"] is None


@pytest.mark.parametrize(
    "outcome",
    ["gh_missing", "not_logged_in", "network_error", "not_found_or_private", "rate_limited"],
)
def test_core_failure_holds_later_batches_and_survives_restart(
    pinned_pull: tuple[_Stand, TestClient], monkeypatch: pytest.MonkeyPatch, outcome: GhFailureState
) -> None:
    from metabrowser.builtin_plugins.github import pull_cores
    from metabrowser.builtin_plugins.github.gh import GhError

    stand, client = pinned_pull
    first, _rest, calls = _visible_core_fixture(
        pinned_pull, monkeypatch, sibling=True, visible=(8, 7)
    )
    failures = 0

    async def fail(*_args: Any, **_kwargs: Any) -> Any:
        nonlocal failures
        failures += 1
        raise GhError("GitHub is temporarily unavailable", state=outcome)

    monkeypatch.setattr(pull_cores, "gh_graphql", fail)
    missing: dict[str, Any] = {
        **first,
        "window": {**first["window"], "id": "next-batch"},
        "numbers": [9],
    }
    assert client.post(_PREPARE_CORES, json=missing).status_code == 202
    _drain_visible_cores(client)
    held = client.post(_PREPARE_CORES, json=missing).json()
    assert held["preparation"] == "failed" and held["failure"]["outcome"] == outcome
    if outcome == "rate_limited":
        assert held["failure"]["reset_at"] is not None
    assert _read(client, 8).json()["core_preview"] is not None

    def restart() -> None:
        session = mirror_session(app)
        assert session is not None
        session.pull_requests = ServedPulls(stand.published)

    assert client.portal is not None
    client.portal.call(restart)
    later = {**missing, "window": {**missing["window"], "id": "restart-next-batch"}}
    assert client.post(_PREPARE_CORES, json=later).json() == {**held, "preparation": "held"}
    assert failures == 1 and calls == [(8,)]
    # A held provider does not hold already-cached initial rendering hostage.
    assert client.post(_PREPARE_CORES, json=first).json()["preparation"] == "ready"


def test_new_authenticated_catalog_resumes_core_warming_after_reader_switch(
    pinned_pull: tuple[_Stand, TestClient], monkeypatch: pytest.MonkeyPatch
) -> None:
    from metabrowser.builtin_plugins.github import pull_cores
    from metabrowser.builtin_plugins.github.pull_catalog import read_catalog
    from metabrowser.builtin_plugins.github.pull_core_cache import write_core_failure
    from metabrowser.builtin_plugins.github.pull_list import ListedRepository
    from tests.github_pull_fixture import seed_catalog

    stand, client = pinned_pull
    _ask, rest, calls = _visible_core_fixture(pinned_pull, monkeypatch)
    old = read_catalog(stand.published.home, stand.published.slug)
    assert old is not None
    failure = PullRefreshStamp(
        outcome="rate_limited",
        at="2026-10-01T12:00:00Z",
        reset_at="2099-01-01T00:00:00Z",
        reader=f"gh:{READER}",
    )
    write_core_failure(stand.published.home, stand.published.slug, old, failure)

    def remember_hold() -> None:
        session = mirror_session(app)
        assert session is not None and isinstance(session.pull_requests, ServedPulls)
        session.pull_requests.core_failure = failure
        session.pull_requests.core_hold_until = datetime(2099, 1, 1, tzinfo=UTC)

    assert client.portal is not None
    client.portal.call(remember_hold)
    repository = ListedRepository(stand.published.home, stand.published.slug, "octo", "demo")
    new = seed_catalog(repository, list(rest.values()), reader="new-reader")
    assert new.epoch != old.epoch
    assert _read(client, 8).json()["core_preview"] is None

    async def graph(_query: str, variables: dict[str, str | int], **_kwargs: Any) -> dict[str, Any]:
        assert variables["n0"] == 8
        data = graph_core_data(rest[8], reader="new-reader")
        data["repository"]["p0"] = data["repository"].pop("pull")
        return data

    monkeypatch.setattr(pull_cores, "gh_graphql", graph)
    ask = {
        "state": "all",
        "window": {"id": "new-reader", "generation": new.generation("all")},
        "numbers": [8],
    }
    assert client.post(_PREPARE_CORES, json=ask).status_code == 202
    _drain_visible_cores(client)
    assert client.post(_PREPARE_CORES, json=ask).json() == {
        "preparation": "ready",
        "ready_numbers": [8],
        "skipped_numbers": [],
    }
    assert _read(client, 8).json()["core_preview"]["reader"] == "gh:new-reader"
    assert calls == [(8,)]


def test_core_ready_receipt_rechecks_complete_cache_coverage(
    pinned_pull: tuple[_Stand, TestClient], monkeypatch: pytest.MonkeyPatch
) -> None:
    from metabrowser.builtin_plugins.github import pull_cores
    from metabrowser.cache.paths import source_pull_core

    stand, client = pinned_pull
    ask, _rest, calls = _visible_core_fixture(pinned_pull, monkeypatch)
    read = pull_cores.cached_batch
    checks = 0

    def lose_entry(pulls_set: ServedPulls, request: pull_cores.CoreRequest) -> Any:
        nonlocal checks
        checks += 1
        if checks == 2:
            (stand.published.home / source_pull_core(stand.published.slug, 8)).unlink()
        return read(pulls_set, request)

    monkeypatch.setattr(pull_cores, "cached_batch", lose_entry)
    assert client.post(_PREPARE_CORES, json=ask).json() == {"preparation": "not_owner"}
    assert checks == 2 and calls == [(8,)]


def test_core_ready_receipt_opens_the_catalog_the_same_number_of_times_for_any_batch(
    pinned_pull: tuple[_Stand, TestClient], monkeypatch: pytest.MonkeyPatch
) -> None:
    """Once for the checkpoint and once per coverage check, never once per core.

    Every catalog open verifies the catalog and its three journal files as private files.
    When each core reopened the catalog to check itself, a receipt for eight cached cores
    opened it 19 times, and a busy server spent seconds on it in thread switches.
    """
    from metabrowser.builtin_plugins.github import pull_catalog
    from metabrowser.builtin_plugins.github.pull_catalog import catalog_members
    from metabrowser.builtin_plugins.github.pull_core_cache import write_cached_cores
    from metabrowser.builtin_plugins.github.pull_list import ListedRepository
    from tests.github_pull_fixture import generated_item, seed_catalog

    stand, client = pinned_pull
    home, slug = stand.published.home, stand.published.slug
    items = [generated_item(number) for number in range(11, 19)]
    catalog = seed_catalog(ListedRepository(home, slug, "octo", "demo"), items, reader=READER)
    numbers = [item["number"] for item in items]
    _, members = catalog_members(home, slug, "all", tuple(numbers))
    cores = {
        item["number"]: pulls._graph_pull(  # pyright: ignore[reportPrivateUsage]
            graph_core_data(item)["repository"]["pull"], item["number"]
        )
        for item in items
    }
    written = write_cached_cores(home, slug, catalog, members, cores, FETCHED_AT)
    assert sorted(written) == numbers
    database = pull_catalog._database  # pyright: ignore[reportPrivateUsage]
    opened = 0

    def counted(*args: Any, **kwargs: Any) -> Any:
        nonlocal opened
        opened += 1
        return database(*args, **kwargs)

    monkeypatch.setattr(pull_catalog, "_database", counted)
    receipts: dict[int, tuple[Any, int]] = {}
    for size in (1, 8):
        opened = 0
        owner = {"id": f"batch-{size}", "generation": catalog.generation("all")}
        ask = {"state": "all", "window": owner, "numbers": numbers[:size]}
        receipts[size] = (client.post(_PREPARE_CORES, json=ask).json(), opened)
    assert receipts == {
        size: (
            {"preparation": "ready", "ready_numbers": numbers[:size], "skipped_numbers": []},
            3,
        )
        for size in (1, 8)
    }


def test_core_batch_whose_client_left_starts_no_provider_read(
    pinned_pull: tuple[_Stand, TestClient], monkeypatch: pytest.MonkeyPatch
) -> None:
    """The panel abandons a batch it scrolled past or waited on too long; the server stops.

    The client leaves during the batch's first cache check, in a worker thread. That check
    runs to its end, but nothing after it does: no provider read, and no window owned.
    """
    from starlette.requests import Request
    from starlette.responses import Response
    from starlette.types import Message

    from metabrowser.builtin_plugins.github import pull_cores
    from metabrowser.builtin_plugins.github.pull_list import ListedRepository
    from metabrowser.builtin_plugins.github.sidekick import pull_cores_prepare_handler
    from tests.github_pull_fixture import seed_catalog

    stand, client = pinned_pull
    entries = scenario(stand.origin)["api"]
    rest = {number: entries[f"repos/octo/demo/pulls/{number}"]["body"] for number in (8, 7)}
    repository = ListedRepository(stand.published.home, stand.published.slug, "octo", "demo")
    catalog = seed_catalog(repository, list(rest.values()), reader=READER)
    calls: list[tuple[int, ...]] = []

    async def graph(_query: str, variables: dict[str, Any], **_kwargs: Any) -> dict[str, Any]:
        calls.append((int(variables["n0"]),))
        data = graph_core_data(rest[8])
        data["repository"]["p0"] = data["repository"].pop("pull")
        return data

    entered, left = threading.Event(), threading.Event()
    check = pull_cores.cached_batch

    def checked_while_leaving(pulls_set: ServedPulls, request: pull_cores.CoreRequest) -> Any:
        entered.set()
        # A server that never listens for the client goes on after this wait.
        left.wait(1)
        return check(pulls_set, request)

    owner = {"id": "scrolled-past", "generation": catalog.generation("all")}
    ask = {"state": "all", "window": owner, "numbers": [8]}

    async def abandoned_batch() -> Response:
        delivered = False

        async def leave_during_the_check() -> Message:
            nonlocal delivered
            if not delivered:
                delivered = True
                return {"type": "http.request", "body": json.dumps(ask).encode()}
            await held_until(entered, 5)
            left.set()
            return {"type": "http.disconnect"}

        # The handler itself, on the served app's loop, where its coordinator runs.
        scope = {
            "type": "http",
            "method": "POST",
            "path": _PREPARE_CORES,
            "query_string": b"",
            "headers": [(b"content-type", b"application/json")],
            "app": app,
        }
        return await pull_cores_prepare_handler(Request(scope, leave_during_the_check))

    monkeypatch.setattr(pull_cores, "gh_graphql", graph)
    monkeypatch.setattr(pull_cores, "cached_batch", checked_while_leaving)
    assert client.portal is not None
    abandoned = client.portal.call(abandoned_batch)
    _drain_visible_cores(client)
    assert (abandoned.status_code, calls) == (499, [])
    # A client that stays is admitted as before, and its batch is read.
    monkeypatch.setattr(pull_cores, "cached_batch", check)
    assert client.post(_PREPARE_CORES, json=ask).json()["preparation"] == "started"
    _drain_visible_cores(client)
    assert calls == [(8,)]


def test_core_transient_capacity_does_not_claim_unattempted_rows(
    pinned_pull: tuple[_Stand, TestClient], monkeypatch: pytest.MonkeyPatch
) -> None:
    from metabrowser.builtin_plugins.github import pull_cores
    from metabrowser.builtin_plugins.github.pull_list import ListedRepository
    from tests.github_pull_fixture import seed_catalog

    stand, client = pinned_pull
    first, rest, calls = _visible_core_fixture(
        pinned_pull, monkeypatch, sibling=True, visible=(8, 7)
    )
    rest[10] = scenario(stand.origin)["api"]["repos/octo/demo/pulls/10"]["body"]
    repository = ListedRepository(stand.published.home, stand.published.slug, "octo", "demo")
    catalog = seed_catalog(repository, list(rest.values()), reader=READER)
    monkeypatch.setattr(pull_cores, "_MAX_CORE_ATTEMPTS", 1)
    ask: dict[str, Any] = {
        **first,
        "window": {"id": "constrained", "generation": catalog.generation("all")},
        "numbers": [9, 10],
    }
    assert client.post(_PREPARE_CORES, json=ask).status_code == 202
    _drain_visible_cores(client)
    assert _read(client, 9).json()["core_preview"] is not None
    assert _read(client, 10).json()["core_preview"] is None
    # A settled partial batch accounts for every member without pretending complete
    # coverage, and retires its owner so the same token can make further progress.
    partial = client.post(_PREPARE_CORES, json=ask).json()
    assert partial["preparation"] == "partial"
    assert partial["ready_numbers"] == [9] and partial["retry_numbers"] == [10]
    assert partial["skipped_numbers"] == []
    assert client.post(_PREPARE_CORES, json=ask).status_code == 202
    _drain_visible_cores(client)
    assert client.post(_PREPARE_CORES, json=ask).json() == {
        "preparation": "ready",
        "ready_numbers": [9, 10],
        "skipped_numbers": [],
    }
    assert calls == [(8,), (9,), (10,)]


@pytest.mark.parametrize("content", [b"{broken", b'{"schema_version":999}'])
def test_unreadable_full_records_are_not_prepared_core_coverage(
    pinned_pull: tuple[_Stand, TestClient], monkeypatch: pytest.MonkeyPatch, content: bytes
) -> None:
    stand, client = pinned_pull
    path = stand.published.home / source_pull_record(stand.published.slug, 8)
    path.write_bytes(content)
    ask, _rest, calls = _visible_core_fixture(pinned_pull, monkeypatch)
    assert client.post(_PREPARE_CORES, json=ask).json() == {
        "preparation": "ready",
        "ready_numbers": [8],
        "skipped_numbers": [7],
    }
    shown = _read(client, 8).json()
    assert shown["record"] is None and shown["core_preview"]["number"] == 8
    assert calls == [(8,)] and path.read_bytes() == content


def test_malformed_core_failure_holds_across_restart(
    pinned_pull: tuple[_Stand, TestClient], monkeypatch: pytest.MonkeyPatch
) -> None:
    from metabrowser.builtin_plugins.github import pull_cores

    stand, client = pinned_pull
    first, _rest, _calls = _visible_core_fixture(
        pinned_pull, monkeypatch, sibling=True, visible=(8, 7)
    )
    attempts = 0

    async def malformed(*_args: Any, **_kwargs: Any) -> Any:
        nonlocal attempts
        attempts += 1
        return {"unexpected": "shape"}

    monkeypatch.setattr(pull_cores, "gh_graphql", malformed)
    ask = {**first, "window": {**first["window"], "id": "malformed"}, "numbers": [9]}
    assert client.post(_PREPARE_CORES, json=ask).status_code == 202
    _drain_visible_cores(client)
    failure = client.post(_PREPARE_CORES, json=ask).json()
    assert failure["preparation"] == "failed" and failure["failure"]["outcome"] == "gh_failed"

    def restart() -> None:
        session = mirror_session(app)
        assert session is not None
        session.pull_requests = ServedPulls(stand.published)

    assert client.portal is not None
    client.portal.call(restart)
    assert client.post(_PREPARE_CORES, json=ask).json() == {**failure, "preparation": "held"}
    assert attempts == 1


def test_success_replaces_an_expired_durable_core_failure(
    pinned_pull: tuple[_Stand, TestClient], monkeypatch: pytest.MonkeyPatch
) -> None:
    from metabrowser.builtin_plugins.github.pull_catalog import read_catalog
    from metabrowser.builtin_plugins.github.pull_core_cache import (
        read_core_failure,
        write_core_failure,
    )
    from metabrowser.cache.paths import source_pull_cores_refresh

    stand, client = pinned_pull
    first, _rest, _calls = _visible_core_fixture(
        pinned_pull, monkeypatch, sibling=True, visible=(8, 7)
    )
    catalog = read_catalog(stand.published.home, stand.published.slug)
    assert catalog is not None
    path = stand.published.home / source_pull_cores_refresh(stand.published.slug)
    path.unlink()
    expired = PullRefreshStamp(
        outcome="rate_limited",
        at=gh_lists.utc_stamp(pulls.utc_now() - timedelta(seconds=120)),
        reset_at=gh_lists.utc_stamp(pulls.utc_now() - timedelta(seconds=60)),
        reader=catalog.reader,
    )
    write_core_failure(stand.published.home, stand.published.slug, catalog, expired)
    ask = {**first, "window": {**first["window"], "id": "recovered"}, "numbers": [9]}
    assert client.post(_PREPARE_CORES, json=ask).status_code == 202
    _drain_visible_cores(client)
    assert client.post(_PREPARE_CORES, json=ask).json()["preparation"] == "ready"
    saved = read_core_failure(stand.published.home, stand.published.slug)
    assert saved is not None and saved.outcome == "succeeded"
    # A delayed writer cannot reinstate the older refusal after the successful batch.
    write_core_failure(stand.published.home, stand.published.slug, catalog, expired)
    assert read_core_failure(stand.published.home, stand.published.slug) == saved


@pytest.mark.parametrize("route", ["read", "refresh"])
def test_disk_core_revocation_after_worker_check_is_rejected_on_loop(
    pinned_pull: tuple[_Stand, TestClient], monkeypatch: pytest.MonkeyPatch, route: str
) -> None:
    from metabrowser.builtin_plugins.github import pull_route, sidekick

    stand, client = pinned_pull
    _ask, _rest, _calls = _visible_core_fixture(pinned_pull, monkeypatch)
    assert client.portal is not None

    def disk_only() -> None:
        session = mirror_session(app)
        assert session is not None and isinstance(session.pull_requests, ServedPulls)
        session.pull_requests.core_window = None

    client.portal.call(disk_only)
    original = asyncio.to_thread
    revoked = False

    async def revoke_after_read(function: Any, *args: Any, **kwargs: Any) -> Any:
        nonlocal revoked
        result = await original(function, *args, **kwargs)
        if function is pull_route.cached_core_preview_current and result:
            view = args[0]
            view.host.pulls.observe_reader(view.host.pulls.published, "gh:different-reader")
            revoked = True
        return result

    monkeypatch.setattr(sidekick.asyncio, "to_thread", revoke_after_read)
    if route == "read":
        body = _read(client, 8).json()
    else:
        # A recent full-record refresh stamp refuses provider work, leaving the
        # durable core as the candidate carried by the POST response.
        write_pull_refresh(
            stand.published.home,
            stand.published.slug,
            8,
            PullRefreshStamp(
                outcome="succeeded", at=gh_lists.utc_stamp(pulls.utc_now()), reader=f"gh:{READER}"
            ),
            expected=read_pull_record(stand.published.home, stand.published.slug, 8),
        )
        body = client.post("/api/plugin/github/pull-refresh", json={"number": 8}).json()["pull"]
    assert revoked and body["core_preview"] is None
    # Nor the label entries or the fast poll that only the dropped core asked for.
    assert (body["repository_labels"], body["labels_pending"]) == ([], False)


def test_unavailable_member_does_not_block_later_cohorts_or_lose_ready_siblings(
    pinned_pull: tuple[_Stand, TestClient], monkeypatch: pytest.MonkeyPatch
) -> None:
    from types import SimpleNamespace

    from metabrowser.builtin_plugins.github import pull_cores
    from metabrowser.builtin_plugins.github.pull_list import ListedRepository
    from tests.github_pull_fixture import seed_catalog

    stand, client = pinned_pull
    first, rest, _calls = _visible_core_fixture(
        pinned_pull, monkeypatch, sibling=True, visible=(8, 7)
    )
    rest[10] = scenario(stand.origin)["api"]["repos/octo/demo/pulls/10"]["body"]
    repository = ListedRepository(stand.published.home, stand.published.slug, "octo", "demo")
    catalog = seed_catalog(repository, list(rest.values()), reader=READER)
    absent = True
    calls: list[tuple[int, ...]] = []

    async def graph(_query: str, variables: dict[str, str | int], **_kwargs: Any) -> dict[str, Any]:
        numbers = tuple(int(v) for k, v in variables.items() if k.startswith("n") and k != "name")
        calls.append(numbers)
        result = graph_core_data(rest[8])
        repo = result["repository"]
        repo.pop("pull")
        for i, number in enumerate(numbers):
            repo[f"p{i}"] = (
                None
                if absent and number == 9
                else graph_core_data(rest[number])["repository"]["pull"]
            )
        return result

    monkeypatch.setattr(pull_cores, "gh_graphql", graph)
    ask: dict[str, Any] = {
        **first,
        "window": {"id": "partial", "generation": catalog.generation("all")},
        "numbers": [9, 8],
    }
    assert client.post(_PREPARE_CORES, json=ask).status_code == 202
    _drain_visible_cores(client)
    partial = client.post(_PREPARE_CORES, json=ask).json()
    assert partial["preparation"] == "partial" and partial["ready_numbers"] == [8]
    assert partial["retry_numbers"] == [9] and partial["skipped_numbers"] == []
    assert datetime.fromisoformat(partial["retry_at"].replace("Z", "+00:00")) > pulls.utc_now()
    assert client.post(_PREPARE_CORES, json=ask).json()["preparation"] == "partial"
    assert calls == [(9,)], "lease-held retries must not repeat the provider batch"

    later = {**ask, "window": {**ask["window"], "id": "later"}, "numbers": [10]}
    assert client.post(_PREPARE_CORES, json=later).status_code == 202
    _drain_visible_cores(client)
    assert client.post(_PREPARE_CORES, json=later).json()["ready_numbers"] == [10]
    assert _read(client, 8).json()["core_preview"] is not None
    now = pull_cores.time.monotonic()
    monkeypatch.setattr(
        pull_cores, "time", SimpleNamespace(monotonic=lambda: now + FRESHNESS_WINDOW_S + 1)
    )
    absent = False
    assert client.post(_PREPARE_CORES, json=ask).status_code == 202
    _drain_visible_cores(client)
    assert client.post(_PREPARE_CORES, json=ask).json() == {
        "preparation": "ready",
        "ready_numbers": [9, 8],
        "skipped_numbers": [],
    }
    assert calls == [(9,), (10,), (9,)], "only the missing member needs provider recovery"


def test_partial_receipt_becomes_ready_when_its_last_member_appears_during_recheck(
    pinned_pull: tuple[_Stand, TestClient], monkeypatch: pytest.MonkeyPatch
) -> None:
    from metabrowser.builtin_plugins.github import pull_cores

    _stand, client = pinned_pull
    ask, _rest, calls = _visible_core_fixture(pinned_pull, monkeypatch)

    async def settled_partial(*_args: Any, **_kwargs: Any) -> str:
        return "partial"

    monkeypatch.setattr(pull_cores, "request_preparation", settled_partial)
    assert client.post(_PREPARE_CORES, json=ask).json() == {
        "preparation": "ready",
        "ready_numbers": [8],
        "skipped_numbers": [7],
    }
    assert calls == [(8,)]


def test_same_window_admitted_during_preflight_is_joined_without_revocation(
    pinned_pull: tuple[_Stand, TestClient], monkeypatch: pytest.MonkeyPatch
) -> None:
    from metabrowser.builtin_plugins.github import pull_cores

    _stand, client = pinned_pull
    first, rest, _calls = _visible_core_fixture(
        pinned_pull, monkeypatch, sibling=True, visible=(8, 7)
    )
    ask = {**first, "window": {**first["window"], "id": "concurrent"}, "numbers": [9]}
    blocked, release_check = threading.Event(), threading.Event()
    provider, release_provider = threading.Event(), threading.Event()
    cached = pull_cores.cached_batch
    checks = 0

    def preflight(served: ServedPulls, request: pull_cores.CoreRequest) -> Any:
        nonlocal checks
        checks += 1
        if checks == 1:
            blocked.set()
            assert release_check.wait(5)
        return cached(served, request)

    async def graph(_query: str, _variables: Any, **_kwargs: Any) -> Any:
        provider.set()
        assert await held_until(release_provider, 5)
        data = graph_core_data(rest[9])
        data["repository"]["p0"] = data["repository"].pop("pull")
        return data

    monkeypatch.setattr(pull_cores, "cached_batch", preflight)
    monkeypatch.setattr(pull_cores, "gh_graphql", graph)
    replies: list[Any] = []
    waiting = threading.Thread(target=lambda: replies.append(client.post(_PREPARE_CORES, json=ask)))
    waiting.start()
    try:
        assert blocked.wait(5)
        assert client.post(_PREPARE_CORES, json=ask).json()["preparation"] == "started"
        assert provider.wait(5)
        release_check.set()
        waiting.join(5)
        assert not waiting.is_alive()
        assert replies[0].json()["preparation"] == "joined"
    finally:
        release_check.set()
        release_provider.set()
        waiting.join(5)
    _drain_visible_cores(client)
    assert client.post(_PREPARE_CORES, json=ask).json()["preparation"] == "ready"


def test_obsolete_observation_cannot_replace_the_current_record_or_stamp(stand: _Stand) -> None:
    record = stand.refresh(7)
    published = stand.published
    newer = record.model_copy(update={"fetched_at": "2026-09-17T12:00:01Z"})
    write_pull_record(published.home, published.slug, newer, expected=record)
    with pytest.raises(pulls.PullObservationSuperseded) as rejected:
        write_pull_record(published.home, published.slug, record, expected=record)
    assert rejected.value.current == newer == stand.record(7)
    original = read_pull_refresh(published.home, published.slug, 7)
    assert original is not None
    failed = original.model_copy(update={"outcome": "network_error"})
    write_pull_refresh(published.home, published.slug, 7, failed, expected=record)
    assert read_pull_refresh(published.home, published.slug, 7) == original


def test_cached_comparison_uses_observed_base_instead_of_a_stale_mirror(stand: _Stand) -> None:
    record = stand.refresh(7)
    published = stand.published
    base = git(published.git_dir, "rev-parse", record.pull.head.sha + "^").decode().strip()
    assert record.comparison is not None and record.comparison.base != base
    observed = record.model_copy(
        update={
            "pull": record.pull.model_copy(
                update={"base": record.pull.base.model_copy(update={"sha": base})}
            ),
            "comparison": None,
        }
    )
    write_pull_record(published.home, published.slug, observed)
    stand.calls()
    prepared = asyncio.run(pulls.prepare_pull_comparison(published, observed))
    assert prepared is not None and prepared.comparison is not None
    assert prepared.comparison.base == prepared.comparison.base_commit == base
    assert stand.calls() == []


# ── A reader's refresh is never queued behind a prefetch ────────────────


_PREFETCH_ROUTE = "/api/plugin/github/pulls-prefetch"
# Each gh request a prefetch of pull request 8 makes is held this long, so its refresh holds
# the store's turn for seconds, as a real one does (4.7 to 7.0 s, MAX_PULL_JOBS's note).
_SLOW_S = 2.0


def _until(client: TestClient, number: int, *, deadline_s: float = 30.0) -> float:
    """Poll the pull route as a page does until *number* has a record; when that was.

    Then wait for its job to end, which observes the mirror after the record is written,
    so the next step does not find a reader's job still running.
    """

    deadline = time.monotonic() + deadline_s
    while _read(client, number).json()["record"] is None:
        assert time.monotonic() < deadline, f"pull request {number} was not read"
        time.sleep(0.01)
    read = time.monotonic()
    while _read(client, number).json()["refreshing"]:
        assert time.monotonic() < deadline, f"pull request {number}'s job did not end"
        time.sleep(0.01)
    return read


def test_a_readers_refresh_is_never_queued_behind_a_prefetch(
    pinned_pull: tuple[_Stand, TestClient], monkeypatch: pytest.MonkeyPatch
) -> None:
    """The prefetch holding the store's turn is cancelled, so the reader waits for it to
    unwind, not to end. The bound is relative to a refresh measured in the same test with
    nothing in the background, so it is not a machine's speed.

    That baseline is pull request 10's first refresh, and the one behind the prefetch is 9's,
    after it, so they differ in more than the prefetch. Like for like, the same sequence with
    no prefetch (review B3), on 2026-11-11 at a load average of 16 to 17 in back-to-back
    pairs: 9 took 0.51 to 0.53 s alone and 0.49 to 0.56 s behind the prefetch, about the
    same, and 4.61 to 4.71 s in three earlier runs with the store turn's preemption switched
    off, which is the wait this test exists to forbid.
    """

    stand, client = pinned_pull
    fake = stand.tmp_path / "fake-gh-bin" / "gh"
    assert fake.is_file()
    slow = stand.tmp_path / "slow-gh"
    slow.mkdir()
    (slow / "gh").write_text(
        "#!/bin/sh\n"
        f'case "$*" in *pulls/8*|*issues/8*) sleep {_SLOW_S};; esac\n'
        f'exec "{fake}" "$@"\n',
        encoding="utf-8",
    )
    (slow / "gh").chmod(0o755)
    monkeypatch.setenv("PATH", f"{slow}:{os.environ['PATH']}")

    started = time.monotonic()
    assert (
        client.post(_REFRESH_ROUTE, json={"number": 10, "retry": True}, headers=_JSON).status_code
        == 202
    )
    baseline = _until(client, 10) - started
    settle(client)

    ask = client.post(_PREFETCH_ROUTE, json={"records": [8]}, headers=_JSON)
    assert (ask.status_code, ask.json()["prefetch"]) == (202, "started")
    deadline = time.monotonic() + 10
    while (client.get(_PREFETCH_ROUTE).json()["running"] or {}).get("number") != 8:
        assert time.monotonic() < deadline, client.get(_PREFETCH_ROUTE).json()["recent"]
        time.sleep(0.01)
    time.sleep(0.2)  # well inside its first slow request
    started = time.monotonic()
    assert (
        client.post(_REFRESH_ROUTE, json={"number": 9, "retry": True}, headers=_JSON).status_code
        == 202
    )
    behind = _until(client, 9) - started
    print(f"foreground refresh: {baseline:.2f} s alone, {behind:.2f} s behind a prefetch")
    settle(client)
    report = client.get(_PREFETCH_ROUTE).json()
    assert [(entry["number"], entry["outcome"]) for entry in report["recent"]] == [(8, "preempted")]
    assert _read(client, 8).json()["record"] is None
    # Unpreempted, 9 would wait for 8's refresh: at least two slow requests in sequence.
    assert behind < baseline + _SLOW_S, (behind, baseline)


def test_a_catalog_scan_does_not_send_a_polled_record_again(
    pinned_pull: tuple[_Stand, TestClient], monkeypatch: pytest.MonkeyPatch
) -> None:
    """A scan moves ``verified_at`` once a window; a polled page gets it in a header on 304.

    A page polls every ``SLOW_POLL_MS`` (30 s) and the catalog is scanned once a window, so
    with the verdict's time in the entity tag every other poll sent the whole record again.
    Measured 2026-11-11 on pull request 8's 3,834-byte envelope: 3,836 bytes a minute
    polled with the time in the tag, and none, two 304s a minute, with it in the header.
    """

    from metabrowser.builtin_plugins.github.pull_list import ListedRepository
    from tests.github_pull_fixture import seed_catalog

    stand, client = pinned_pull
    # Merged, so no check of it is still settling, and the catalog can vouch for it.
    stand.refresh(8)
    repository = ListedRepository(stand.published.home, stand.published.slug, "octo", "demo")
    rest = scenario(stand.origin)["api"]["repos/octo/demo/pulls/8"]["body"]
    stamp = "%Y-%m-%dT%H:%M:%SZ"
    first = _read(client, 8)
    etag, sent = first.headers["etag"], len(first.content)
    record_bytes = sent
    for minute in range(1, 4):
        scanned = FETCHED_AT + timedelta(minutes=minute)
        seed_catalog(repository, [rest], reader=READER, fetched_at=scanned.strftime(stamp))
        for offset in (0, 30):
            moment = scanned + timedelta(seconds=offset)
            monkeypatch.setattr(pulls, "utc_now", lambda moment=moment: moment)
            polled = _read(client, 8, etag=etag)
            sent += len(polled.content)
            if polled.status_code == 200:
                etag = polled.headers["etag"]
            assert polled.headers["x-metabrowser-verified"] == f"catalog {scanned.strftime(stamp)}"
    print(f"record {record_bytes} bytes; {(sent - record_bytes) / 3:.0f} bytes a minute polled")
    assert sent == record_bytes, "a scan sent the record again"


def _api_paths(stand: _Stand) -> list[str]:
    """The repository paths asked for, leaving out the account check's ``user``.

    A GraphQL query is named by its operation, as ``graphql PullStatus``.
    """

    def asked(args: list[str]) -> str:
        if "graphql" in args:
            query = next(arg for arg in args if arg.startswith("query="))
            return "graphql " + query.removeprefix("query=query ").split("(", 1)[0]
        return args[-1]

    paths = (asked(call["args"]) for call in stand.calls() if call["args"][:1] == ["api"])
    return sorted(path for path in paths if path != "user")


_STATUS_QUERY: Final = "graphql PullStatus"


def test_a_status_read_asks_the_status_alone_and_leaves_the_record(
    stand: _Stand, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Review A1: ``updated_at`` covers the conversation, not checks or mergeability.

    The three cases a record the catalog vouched for went on showing wrong: no CI
    registered yet when it was read, a re-run of completed checks, and a conflict a moved
    base made. Each leaves ``updated_at`` and the head alone, and each is the status's: a
    status read sees each with its account check and one GraphQL query, and nothing else,
    no REST read of the record, no fetch into the store, and no new record, so the
    record's revision, its comparison, and how its last refresh ended stand.
    """

    answers = scenario(stand.origin)
    parts = pull_bodies(stand.origin)[7]
    status_entry = "graphql:status:7:start"
    none_yet = {
        **parts,
        "check_runs": {"total_count": 0, "check_runs": []},
        "status": {"state": "pending", "total_count": 0, "statuses": []},
    }
    stand.answer(_api(answers, status_entry, graph_status_entry(none_yet)))
    first = stand.refresh(7)
    assert first.comparison is not None
    home, slug = stand.published.home, stand.published.slug
    kept = read_pull_status(home, slug, 7)
    assert kept is not None and kept.checks.state == "none"
    stamp = read_pull_refresh(home, slug, 7)
    stand.calls()

    async def no_fetch(*_args: object, **_kwargs: object) -> str:
        raise AssertionError("a status read fetched into the store")

    monkeypatch.setattr(pulls, "fetch_pull_head", no_fetch)
    moments = itertools.count(1)

    def status_read() -> PullStatus | None:
        # Each read observes a moment after the last: two of one moment are kept by what
        # they observed, not by which was written last (:func:`.pull_status.observation_key`).
        later = FETCHED_AT + timedelta(seconds=next(moments))
        monkeypatch.setattr(pulls, "utc_now", lambda: later)
        return asyncio.run(pulls.refresh_pull_status(stand.published, 7))

    # No CI registered when it was read; now it has.
    stand.answer(answers)
    registered = status_read()
    assert registered is not None and registered.checks.total > 0
    assert _api_paths(stand) == [_STATUS_QUERY]
    assert stand.record(7) == first and read_pull_refresh(home, slug, 7) == stamp

    # Completed checks re-run.
    rerun = copy.deepcopy(parts)
    for run in rerun["check_runs"]["check_runs"]:
        run.update(status="in_progress", conclusion=None, completed_at=None)
    stand.answer(_api(answers, status_entry, graph_status_entry(rerun)))
    rerunning = status_read()
    assert rerunning is not None and rerunning.checks.state == "pending"
    checks = read_pull_checks(home, slug, 7)
    assert checks is not None
    assert {item.bucket for item in checks.items if item.kind == "run"} == {"pending"}
    assert _api_paths(stand) == [_STATUS_QUERY]

    # The base moved and the pull request now conflicts: GitHub says so in the status.
    shape = {"mergeable": "CONFLICTING", "mergeStateStatus": "DIRTY", "reviewDecision": None}
    stand.answer(_api(answers, status_entry, graph_status_entry(parts, shape=shape)))
    conflict = status_read()
    assert conflict is not None and conflict.conflicts == "conflicting"
    assert _api_paths(stand) == [_STATUS_QUERY]
    assert stand.record(7) == first
    held = read_pull_status(home, slug, 7)
    assert held is not None and held.observed_at == conflict.observed_at
    # An account check that fails fails the status alone, and is kept as how it ended.
    stand.answer({**answers, "auth": {"stdout": '{"hosts":{}}\n', "exit": 0}})
    assert status_read() is None
    outcome = read_status_outcome(home, slug, 7)
    assert outcome is not None and outcome.outcome != "succeeded"
    assert read_pull_status(home, slug, 7) == held


ISSUE_PATH = "repos/octo/demo/issues/7"


def _probe(
    stand: _Stand,
    record: PullRecord,
    *,
    checks: bool,
    etags: dict[str, str] | None = None,
    seen: pulls.IssueSeen | None = None,
    mergeability: bool = False,
    status: PullStatus | None = None,
    probes: CheckProbes | None = None,
) -> pulls.PullProbe:
    """One probe, comparing with *status*, by default the one the stand keeps."""

    kept = read_pull_status(stand.published.home, stand.published.slug, record.number)
    return asyncio.run(
        pulls.probe_pull_request(
            stand.published,
            record,
            etags=etags or {},
            checks=checks,
            seen=seen,
            mergeability=mergeability,
            status=kept if status is None else status,
            probes=probes,
        )
    )


def _sent_etags(stand: _Stand) -> list[tuple[str, str | None]]:
    """Each ``gh api`` call's path and the ETag it sent, if it was conditional."""

    sent: list[tuple[str, str | None]] = []
    for call in stand.calls():
        args: list[str] = call["args"]
        etag = next((arg for arg in args if arg.startswith("If-None-Match: ")), None)
        sent.append((args[-1], etag.split(": ", 1)[1] if etag else None))
    return sent


def test_a_probe_asks_only_the_issue_and_never_the_account(stand: _Stand) -> None:
    """The first probe of a number reads its issue once; after that an unchanged pull
    request is one conditional read that GitHub answers ``304``."""

    record = stand.refresh(7)
    assert pulls.probe_path(stand.published, 7) == ISSUE_PATH
    stand.calls()
    first = _probe(stand, record, checks=False)
    assert first.outcome == "unchanged" and first.etags == {}
    assert first.seen is not None and first.seen.updated_at == record.pull.updated_at
    assert _sent_etags(stand) == [(ISSUE_PATH, None)]
    again = _probe(stand, record, checks=False, seen=first.seen)
    assert again == pulls.PullProbe("unchanged", {}, first.seen, record.pull.updated_at)
    assert _sent_etags(stand) == [(ISSUE_PATH, first.seen.etag)]


def test_a_push_to_the_repository_moves_the_pulls_etag_and_not_the_probes(
    stand: _Stand,
) -> None:
    """mb-2ppr: the pull embeds its repositories, whose ``pushed_at`` and counts move with
    every push and every issue opened; the issue a probe reads embeds neither, so its
    ETag holds (measured 2026-11-23, beside ``pulls.PROBE_RESOURCE``)."""

    answers = scenario(stand.origin)
    pull_path = "repos/octo/demo/pulls/7"
    record = stand.refresh(7)
    seen = _probe(stand, record, checks=False).seen
    body = answers["api"][pull_path]["body"]
    base = {**body["base"], "repo": {"pushed_at": "2026-09-17T11:59:00Z", "open_issues": 12}}
    pushed = ok(pull_path, {**body, "base": base})
    assert pushed["headers"]["Etag"] != record.etags[pull_path]
    stand.answer(_api(answers, pull_path, pushed))
    stand.calls()
    assert _probe(stand, record, checks=False, seen=seen) == pulls.PullProbe(
        "unchanged", {}, seen, record.pull.updated_at
    )
    assert seen is not None and _sent_etags(stand) == [(ISSUE_PATH, seen.etag)]


def test_a_probe_finds_a_change_by_the_issues_updated_at_and_keeps_what_it_saw(
    stand: _Stand,
) -> None:
    answers = scenario(stand.origin)
    pull_path = "repos/octo/demo/pulls/7"
    record = stand.refresh(7)
    seen = _probe(stand, record, checks=False).seen
    body = answers["api"][pull_path]["body"]
    merged = {**body, "state": "closed", "merged": True, "updated_at": "2026-09-17T11:00:00Z"}
    stand.answer(_api(answers, pull_path, ok(pull_path, merged)))
    stand.calls()
    found = _probe(stand, record, checks=True, seen=seen)
    assert found.outcome == "changed" and found.seen is not None and found.seen != seen
    assert found.seen.updated_at == "2026-09-17T11:00:00Z"
    # The checks are not asked once the pull request itself changed.
    assert _api_paths(stand) == [ISSUE_PATH]
    # A 304 for what that probe saw is still a change beside the older record, for free...
    assert _probe(stand, record, checks=False, seen=found.seen) == pulls.PullProbe(
        "changed", {}, found.seen, "2026-09-17T11:00:00Z"
    )
    assert _sent_etags(stand) == [(ISSUE_PATH, found.seen.etag)]
    # ...and no change beside the record the full read brings.
    newer = stand.refresh(7)
    assert newer.pull.updated_at == "2026-09-17T11:00:00Z"
    assert _probe(stand, newer, checks=False, seen=found.seen) == pulls.PullProbe(
        "unchanged", {}, found.seen, "2026-09-17T11:00:00Z"
    )


def test_a_new_issue_etag_with_the_same_updated_at_changes_nothing(stand: _Stand) -> None:
    """A reaction moves the issue's ETag and not its ``updated_at``: one paid read, the new
    ETag kept, and no full read."""

    answers = scenario(stand.origin)
    record = stand.refresh(7)
    seen = _probe(stand, record, checks=False).seen
    reacted = ok(
        ISSUE_PATH,
        {"number": 7, "updated_at": record.pull.updated_at, "reactions": {"+1": 1}},
        {"Etag": 'W/"rotated"'},
    )
    stand.answer(_api(answers, ISSUE_PATH, reacted))
    found = _probe(stand, record, checks=False, seen=seen)
    assert found == pulls.PullProbe(
        "unchanged",
        {},
        pulls.IssueSeen(record.pull.updated_at, 'W/"rotated"'),
        record.pull.updated_at,
    )
    # An issue GitHub answers for another number, or without a time, fails the probe.
    for wrong in (
        {"number": 8, "updated_at": record.pull.updated_at},
        {"number": 7, "updated_at": None},
    ):
        stand.answer(_api(answers, ISSUE_PATH, ok(ISSUE_PATH, wrong)))
        with pytest.raises(PullDataError) as unreadable:
            _probe(stand, record, checks=False, seen=seen)
        assert unreadable.value.state == "gh_failed"


def test_an_app_authored_pull_reads_the_same_through_graphql_and_rest(stand: _Stand) -> None:
    """GraphQL names an app by its slug and REST by its bot account; the core read projects
    REST's, so the first probe after a cold open finds no change (review B2 on #709)."""

    answers = scenario(stand.origin)
    rest = copy.deepcopy(answers["api"]["repos/octo/demo/pulls/7"]["body"])
    rest["user"] = {"login": "dependabot[bot]", "type": "Bot"}
    rest["merged_by"] = {"login": "renovate[bot]", "type": "Bot"}
    graph = graph_core_data(rest)["repository"]["pull"]
    graph["author"] = {"__typename": "Bot", "login": "dependabot"}
    graph["mergedBy"] = {"__typename": "Bot", "login": "renovate"}
    assert pulls._graph_pull(graph, 7) == pulls._pull(rest, 7)  # pyright: ignore[reportPrivateUsage]
    # Review C1 on #709: the Copilot coding agent is not named <slug>[bot] through REST.
    rest["user"] = {"login": "Copilot", "type": "Bot"}
    graph["author"] = {"__typename": "Bot", "login": "copilot-swe-agent"}
    assert pulls._graph_pull(graph, 7) == pulls._pull(rest, 7)  # pyright: ignore[reportPrivateUsage]
    assert pulls._graph_pull(graph, 7).author == "Copilot"  # pyright: ignore[reportPrivateUsage]
    # A person is named the same both ways, whatever their login.
    graph["author"] = {"__typename": "User", "login": "octocat"}
    assert pulls._graph_pull(graph, 7).author == "octocat"  # pyright: ignore[reportPrivateUsage]


def _computing(stand: _Stand) -> dict[str, Any]:
    """The stand's answers while GitHub computes whether 7 can merge, in REST and GraphQL."""

    answers = scenario(stand.origin)
    pull_path = "repos/octo/demo/pulls/7"
    body = answers["api"][pull_path]["body"]
    computing = {**body, "state": "open", "merged": False, "mergeable": None}
    shape = {"mergeable": "UNKNOWN", "mergeStateStatus": "UNKNOWN", "reviewDecision": None}
    parts = {**pull_bodies(stand.origin)[7], "pull": computing}
    answers = _api(answers, pull_path, ok(pull_path, computing))
    return _api(answers, "graphql:status:7:start", graph_status_entry(parts, shape=shape))


def test_a_probe_of_unknown_mergeability_asks_the_pull_and_sees_github_answer(
    stand: _Stand,
) -> None:
    """Review A1 on #726: GitHub computes ``mergeable`` after the read that first asks, and
    nothing the issue carries moves when it does. Before, three probes asked the issue and
    never the pull, and each vouched for "Merge status unknown". The status holds it now,
    so the pull is asked while the status's mergeability is unknown, and an answer starts
    a status read."""

    answers = _computing(stand)
    pull_path = "repos/octo/demo/pulls/7"
    stand.answer(answers)
    record = stand.refresh(7)
    home, slug = stand.published.home, stand.published.slug
    status = read_pull_status(home, slug, 7)
    assert status is not None and status.conflicts == "unknown"
    assert pulls.mergeability_probe_path(stand.published, record, status) == pull_path
    seen = _probe(stand, record, checks=False).seen
    stand.calls()
    # Not asked for: the issue alone.
    assert _probe(stand, record, checks=False, seen=seen).outcome == "unchanged"
    assert _api_paths(stand) == [ISSUE_PATH]
    # Still computing: the pull answers 304 to the record's own ETag.
    waiting = _probe(stand, record, checks=False, seen=seen, mergeability=True)
    assert (waiting.outcome, waiting.etags) == ("unchanged", {})
    assert sorted(_sent_etags(stand)) == sorted(
        [(ISSUE_PATH, seen.etag if seen else None), (pull_path, record.etags[pull_path])]
    )
    # The repository moved and GitHub is still computing: the new ETag is kept.
    computing = answers["api"][pull_path]["body"]
    base = {**computing["base"], "repo": {"pushed_at": "2026-09-17T11:59:00Z"}}
    moved = ok(pull_path, {**computing, "base": base})
    stand.answer(_api(answers, pull_path, moved))
    still = _probe(stand, record, checks=False, seen=seen, mergeability=True)
    assert (still.outcome, still.etags) == ("unchanged", {pull_path: moved["headers"]["Etag"]})
    # A draft's mergeable_state is no news either.
    drafted = ok(pull_path, {**computing, "mergeable_state": "draft"})
    stand.answer(_api(answers, pull_path, drafted))
    assert _probe(stand, record, checks=False, seen=seen, mergeability=True).outcome == (
        "unchanged"
    )
    # GitHub answers, with the same updated_at: the status is read again, alone.
    computed = ok(pull_path, {**computing, "mergeable": True, "mergeable_state": "clean"})
    stand.answer(_api(scenario(stand.origin), pull_path, computed))
    assert _probe(stand, record, checks=False, seen=seen, mergeability=True).outcome == (
        "checks_changed"
    )
    # The read that follows observes a later moment than the one that left it unknown.
    stand.monkeypatch.setattr(pulls, "utc_now", lambda: FETCHED_AT + timedelta(seconds=1))
    resolved = asyncio.run(pulls.refresh_pull_status(stand.published, 7))
    assert resolved is not None and resolved.conflicts == "mergeable"
    # A status that holds an answer, or a closed pull request, never has the pull asked.
    assert pulls.mergeability_probe_path(stand.published, record, resolved) is None
    stand.calls()
    assert _probe(stand, record, checks=False, seen=seen, mergeability=True).outcome == (
        "unchanged"
    )
    assert _api_paths(stand) == [ISSUE_PATH]
    closed = record.model_copy(update={"pull": record.pull.model_copy(update={"state": "closed"})})
    assert pulls.mergeability_probe_path(stand.published, closed, status) is None
    # Nor does a status of another head: a status read comes first.
    other = status.model_copy(update={"head": stand.origin["fork_earlier"]})
    assert pulls.mergeability_probe_path(stand.published, record, other) is None


def test_a_pull_answer_that_cannot_be_read_is_not_taken_for_still_unknown(
    stand: _Stand,
) -> None:
    """Review B3 on #726: read as "the same", a malformed 200 would be vouched for and its
    ETag kept, so the pull would answer 304 from then on."""

    answers = _computing(stand)
    pull_path = "repos/octo/demo/pulls/7"
    stand.answer(answers)
    record = stand.refresh(7)
    seen = _probe(stand, record, checks=False).seen
    issue = ok(ISSUE_PATH, {"number": 7, "updated_at": record.pull.updated_at})
    malformed = ok(pull_path, {"number": 7, "message": "?"})
    stand.answer(_api(_api(answers, ISSUE_PATH, issue), pull_path, malformed))
    found = _probe(stand, record, checks=False, seen=seen, mergeability=True)
    assert (found.outcome, found.etags) == ("checks_changed", {})


def test_an_issue_older_than_the_record_is_behind_and_not_a_change(stand: _Stand) -> None:
    """Review A8 on #726: an answer that lags the pull's would have cost a full read."""

    answers = scenario(stand.origin)
    record = stand.refresh(7)
    older = "2000-01-01T00:00:00Z"
    assert older < record.pull.updated_at
    stand.answer(_api(answers, ISSUE_PATH, ok(ISSUE_PATH, {"number": 7, "updated_at": older})))
    stand.calls()
    found = _probe(stand, record, checks=True)
    assert (found.outcome, found.updated_at) == ("behind", older)
    assert _api_paths(stand) == [ISSUE_PATH]
    # A time in another spelling would not compare as text, so it is not read as one.
    offset = ok(ISSUE_PATH, {"number": 7, "updated_at": "2030-01-01T00:00:00+00:00"})
    stand.answer(_api(answers, ISSUE_PATH, offset))
    with pytest.raises(PullDataError) as unreadable:
        _probe(stand, record, checks=False)
    assert unreadable.value.state == "gh_failed"


def test_a_checks_probe_seeds_its_baseline_and_then_sees_only_a_real_change(
    stand: _Stand,
) -> None:
    """The status is read with GraphQL, which has no ETag, so the probe keeps its own: the
    first probe of a head asks both pages unconditionally, a ``200`` each that seeds the
    baseline and counts as a change, and later probes are conditional on it. A ``200``
    that changes nothing a status keeps, such as a run's output, is no change."""

    answers = scenario(stand.origin)
    head = stand.origin["fork_head"]
    runs_path = page(f"repos/octo/demo/commits/{head}/check-runs")
    status_path = page(f"repos/octo/demo/commits/{head}/status")
    record = stand.refresh(7)
    status = read_pull_status(stand.published.home, stand.published.slug, 7)
    assert status is not None and status.head == head
    assert pulls.checks_probe_paths(stand.published, record, status) == (runs_path, status_path)
    seen = _probe(stand, record, checks=False).seen
    stand.calls()
    first = _probe(stand, record, checks=True, seen=seen)
    assert first.outcome == "checks_changed" and first.checks is not None
    assert sorted(_sent_etags(stand)) == sorted(
        [(ISSUE_PATH, seen.etag if seen else None), (runs_path, None), (status_path, None)]
    )
    baseline = first.checks
    assert (baseline.head, baseline.reader, baseline.refused) == (head, record.reader, False)
    assert set(baseline.pages) == {runs_path, status_path}
    # Unchanged: both pages answer 304 to the baseline's ETags, and nothing is to be kept.
    again = _probe(stand, record, checks=True, seen=seen, probes=baseline)
    assert (again.outcome, again.checks) == ("unchanged", None)
    assert sorted(_sent_etags(stand)) == sorted(
        [
            (ISSUE_PATH, seen.etag if seen else None),
            (runs_path, baseline.pages[runs_path].etag),
            (status_path, baseline.pages[status_path].etag),
        ]
    )
    # A run's output moved, and nothing a status keeps: a paid 200, its ETag kept.
    runs = copy.deepcopy(answers["api"][runs_path]["body"])
    runs["check_runs"][0]["output"] = {"title": "still going"}
    stand.answer(_api(answers, runs_path, ok(runs_path, runs)))
    quiet = _probe(stand, record, checks=True, seen=seen, probes=baseline)
    assert quiet.outcome == "unchanged" and quiet.checks is not None
    assert quiet.checks.pages[runs_path].digest == baseline.pages[runs_path].digest
    assert quiet.checks.pages[runs_path].etag != baseline.pages[runs_path].etag
    # A re-run is a change, and the baseline the next probe compares with.
    rerun = copy.deepcopy(answers["api"][runs_path]["body"])
    for run in rerun["check_runs"]:
        run.update(status="in_progress", conclusion=None)
    stand.answer(_api(answers, runs_path, ok(runs_path, rerun)))
    changed = _probe(stand, record, checks=True, seen=seen, probes=quiet.checks)
    assert changed.outcome == "checks_changed" and changed.checks is not None
    assert _probe(stand, record, checks=True, seen=seen, probes=changed.checks).outcome == (
        "unchanged"
    )
    # A baseline of another head, or another reader, is none: the pages are asked afresh.
    elsewhere = changed.checks.model_copy(update={"head": stand.origin["fork_earlier"]})
    assert _probe(stand, record, checks=True, seen=seen, probes=elsewhere).outcome == (
        "checks_changed"
    )
    # A page GitHub refuses marks the head's pages refused, which are then not probed.
    refusing = _api(answers, status_path, {"status": 403, "body": {"message": "Forbidden"}})
    stand.answer(_api(refusing, runs_path, ok(runs_path, rerun)))
    refused = _probe(stand, record, checks=True, seen=seen, probes=changed.checks)
    assert refused.outcome == "unchanged" and refused.checks is not None
    assert refused.checks.refused
    assert pulls.checks_probe_paths(stand.published, record, status, refused.checks) is None
    # More checks than a page holds cannot be probed by its first page.
    counts = {**status.checks.counts, "pass": 100}
    full = status.model_copy(update={"checks": status.checks.model_copy(update={"counts": counts})})
    assert pulls.checks_probe_paths(stand.published, record, full) is None
