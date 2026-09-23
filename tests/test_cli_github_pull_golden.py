"""Golden CLI transcript: pull-request URLs fetched, refreshed, and read offline.

Each command runs the production CLI in-process, as ``tests/test_cli_github_url_golden.py``
does, with these substitutions and nothing else:

- ``metabrowser.cache.acquire.remote_url_for`` fetches ``https://github.com/octo/demo``,
  ``refs/pull/<n>/head`` included, from the local origin in
  ``tests/github_pull_fixture.py``;
- a fake ``gh`` first on ``PATH`` replays scrubbed real API responses, and logs every
  call, which the transcript lists after each command;
- the clock is fixed, so ``fetched_at`` and the record's state are the same every run.

The Git floor is patched as in the other acquisition goldens, because CI's Git is below
it. The real ``gh`` and GitHub are the opt-in live smoke test,
``tests/test_github_pull_live_smoke.py``. Cached reads with no ``gh`` at all run as a
subprocess in ``tests/golden/cli-github-pull.tryscript.md``.

Regenerate after an intended change with:

    GOLDEN_UPDATE=1 uv --config-file uv.toml run --frozen pytest tests/test_cli_github_pull_golden.py
"""

from __future__ import annotations

import json
import os
import shutil
from pathlib import Path
from typing import Any

import pytest

from metabrowser.cache.urls import GitSource
from tests.github_pull_fixture import (
    CANONICAL,
    FETCHED_AT,
    Origin,
    account,
    build_origin,
    install_fake_gh,
    ok,
    scenario,
)
from tests.test_cli_cache_acquire_golden import _isolate, _strip_logs
from tests.test_cli_git_pin_golden import _Invocation, _run
from tests.test_cli_golden import check_golden

pytestmark = [
    pytest.mark.skipif(shutil.which("git") is None, reason="git executable is required"),
    pytest.mark.skipif(os.name != "posix", reason="owner-only cache is POSIX-only"),
]

PULL = f"{CANONICAL}/pull"


class _Session:
    """The stand-in origin, the fake gh, and a transcript of what each command did."""

    def __init__(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        self.tmp_path = tmp_path
        self.monkeypatch = monkeypatch
        self.home = _isolate(tmp_path, monkeypatch)
        self.origin: Origin = build_origin(tmp_path)
        local = self.origin.url

        def remote_url_for(source: GitSource) -> str:
            return local if source.normalized == CANONICAL else source.normalized

        monkeypatch.setattr("metabrowser.cache.acquire.remote_url_for", remote_url_for)
        monkeypatch.setattr("metabrowser.builtin_plugins.github.pulls.utc_now", lambda: FETCHED_AT)
        self.blocks: list[str] = []
        self.answer(scenario(self.origin))

    def answer(self, answers: dict[str, Any]) -> None:
        for name, value in install_fake_gh(self.tmp_path, answers).items():
            self.monkeypatch.setenv(name, value)

    def gh_calls(self) -> list[str]:
        log = self.tmp_path / "fake-gh-log.jsonl"
        if not log.exists():
            return []
        calls: list[str] = []
        for line in log.read_text(encoding="utf-8").splitlines():
            args: list[str] = json.loads(line)["args"]
            if args[:2] == ["auth", "status"]:
                calls.append("gh auth status")
                continue
            path = next(arg for arg in args if arg.startswith("repos/"))
            if "--jq" in args:
                calls.append(f"gh api {path} --jq {args[args.index('--jq') + 1]}")
                continue
            conditional = any(arg.startswith("If-None-Match: ") for arg in args)
            calls.append(f"gh api {path}" + (" (If-None-Match)" if conditional else ""))
        log.unlink()
        return calls

    def run(self, *args: str) -> _Invocation:
        result = _run(list(args))
        calls = self.gh_calls()
        quoted = " ".join(f"'{arg}'" if any(ch in arg for ch in "?&") else arg for arg in args)
        self.blocks.append(
            f"# metab {quoted}\n"
            f"exit: {result.exit_code}\n"
            f"--- stdout ---\n{_strip_logs(result.stdout)}"
            f"--- stderr ---\n{_strip_logs(result.stderr)}"
            f"--- gh ---\n" + "".join(f"{call}\n" for call in calls)
        )
        return result


def _with(answers: dict[str, Any], **changes: Any) -> dict[str, Any]:
    return {**answers, **changes}


def _api(answers: dict[str, Any], path: str, entry: Any) -> dict[str, Any]:
    return {**answers, "api": {**answers["api"], path: entry}}


def test_golden_pull_requests_fetch_refresh_and_read_offline(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    session = _Session(tmp_path, monkeypatch)
    origin = session.origin
    online = scenario(origin)

    first = session.run(f"{PULL}/7", "--api", "/api/plugin/github/pull")
    assert first.exit_code == 0, first.stderr
    envelope = json.loads(first.stdout[first.stdout.index("{") :])
    assert envelope["state"] == "current"
    assert envelope["pin"] == origin["fork_head"]
    assert envelope["record"]["comparison"]["base"] == origin["base"]
    refreshed = session.run(f"{PULL}/7", "--no-serve")
    assert refreshed.exit_code == 0, refreshed.stderr
    fork_commit = session.run(
        f"{PULL}/7/commits/{origin['fork_earlier'][:7]}", "--show", "src/app.txt"
    )
    assert fork_commit.exit_code == 0, fork_commit.stderr

    # Offline: every API read fails, and nothing that reads the cache asks gh.
    session.answer(
        _with(online, api_failure={"stderr": "error connecting to api.github.com\n", "exit": 1})
    )
    offline = session.run(f"{PULL}/7", "--api", "/api/plugin/github/pull")
    assert offline.exit_code == 0, offline.stderr
    assert json.loads(offline.stdout[offline.stdout.index("{") :])["record"] == envelope["record"]
    stale = session.run(f"{PULL}/7", "--no-serve")
    assert stale.exit_code == 0 and "; the refresh failed: " in stale.stdout
    assert "(network_error))" in stale.stdout

    session.answer(online)
    for number in (8, 9, 10):
        assert session.run(f"{PULL}/{number}", "--no-serve").exit_code == 0
    merged = session.run(f"{PULL}/8", "--api", "/api/plugin/github/pull")
    assert json.loads(merged.stdout[merged.stdout.index("{") :])["record"]["comparison"] == {
        "base": origin["base"],
        "head": origin["merged_head"],
        "base_commit": origin["topic_before_merge"],
        "base_from": "base_sha",
    }

    refusals: list[tuple[str, dict[str, Any]]] = [
        ("not_found_or_private", online),
        ("not_logged_in", _with(online, auth={"stdout": '{"hosts":{}}\n', "exit": 0})),
        (
            "gh_too_old",
            _with(
                online,
                auth={"stderr": "unknown flag: --json\n\nUsage: gh auth status\n", "exit": 1},
            ),
        ),
        (
            "rate_limited",
            _api(
                online,
                "repos/octo/demo/pulls/11",
                {
                    "status": 403,
                    "headers": {"X-Ratelimit-Remaining": "0", "X-Ratelimit-Reset": "1790181960"},
                    "body": {"message": "API rate limit exceeded"},
                },
            ),
        ),
        (
            "rate_limited",
            _api(
                online,
                "repos/octo/demo/pulls/11",
                {
                    "status": 429,
                    "headers": {"Retry-After": "120"},
                    "body": {"message": "slow down"},
                },
            ),
        ),
        (
            "rate_limited",
            _api(
                online,
                "repos/octo/demo/pulls/11",
                {
                    "status": 403,
                    "headers": {"X-Ratelimit-Remaining": "4990"},
                    "body": {"message": "You have exceeded a secondary rate limit."},
                },
            ),
        ),
        (
            "network_error",
            _with(online, api_failure={"stderr": "dial tcp: i/o timeout\n", "exit": 1}),
        ),
    ]
    for state, answers in refusals:
        session.answer(answers)
        refused = session.run(f"{PULL}/11", "--no-serve")
        assert refused.exit_code == 0, (state, refused.stderr)
        assert f"({state}); the pin is the default branch)" in refused.stdout, (
            state,
            refused.stdout,
        )

    # The account switches between the two account checks around a complete read.
    session.answer(_with(online, auth=[account("octo-reader"), account("someone-else")]))
    switched = session.run(f"{PULL}/7", "--no-serve")
    assert switched.exit_code == 0 and "(account_changed))" in switched.stdout

    # The API names a head that refs/pull/7/head does not: read again once, then give up
    # and answer from the cached record.
    path = "repos/octo/demo/pulls/7"
    body = online["api"][path]["body"]
    moved = ok(path, {**body, "head": {**body["head"], "sha": origin["merged_head"]}})
    session.answer(_api(online, path, moved))
    mismatch = session.run(f"{PULL}/7", "--no-serve")
    assert mismatch.exit_code == 0 and "(head_mismatch))" in mismatch.stdout

    monkeypatch.setattr("metabrowser.builtin_plugins.github.gh.gh_executable", lambda: None)
    missing = session.run(f"{PULL}/11", "--api", "/api/plugin/github/pull")
    assert (
        missing.exit_code == 0 and "(gh_missing); the pin is the default branch)" in missing.stderr
    )
    assert json.loads(missing.stdout[missing.stdout.index("{") :])["reason"] == "not_cached"
    # The cached record outlived every failed refresh.
    kept = session.run(f"{PULL}/7", "--api", "/api/plugin/github/pull")
    assert (
        kept.exit_code == 0
        and json.loads(kept.stdout[kept.stdout.index("{") :])["record"] == envelope["record"]
    )

    rendered = "".join(session.blocks)
    assert str(tmp_path) not in rendered and str(session.home) not in rendered
    assert "file://" not in rendered
    check_golden("cli-github-pull-refresh.txt", rendered)
