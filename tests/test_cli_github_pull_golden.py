"""Golden CLI transcript: pull-request URLs fetched, refreshed, and read offline.

Each command runs the production CLI in-process, as ``tests/test_cli_github_url_golden.py``
does, with these substitutions and nothing else:

- ``metabrowser.cache.acquire.remote_url_for`` fetches ``https://github.com/octo/demo``,
  ``refs/pull/<n>/head`` included, from the local origin in
  ``tests/github_pull_fixture.py``;
- a fake ``gh`` first on ``PATH`` replays scrubbed real API responses, and logs every
  call, which the transcript lists after each command;
- the clock is fixed, so ``fetched_at`` and the record's state are the same every run.

The Git floor is replaced as in the other acquisition goldens
(``tests/golden_harness.py``). The real ``gh`` and GitHub are the opt-in live smoke test,
``tests/test_github_pull_live_smoke.py``. Cached reads with no ``gh`` at all run as a
subprocess in ``tests/golden/cli-github-pull.tryscript.md``.

A pull envelope carries the whole record, and this story reads pull request 7's a
dozen times. The transcript prints a record in full once and after that as
``<RECORD n>``: the record of pull request *n*, equal to the last one printed in full.
A record that differs is printed in full again, so a read that changed it shows as the
whole record appearing where the label was.
"""

from __future__ import annotations

import json
import os
import re
from dataclasses import replace
from pathlib import Path
from typing import Any

import pytest

from metabrowser.cache import pull_refs
from metabrowser.cache.urls import GitSource
from metabrowser.git.process import GitCommandError
from tests.github_pull_fixture import (
    CANONICAL,
    FETCHED_AT,
    Origin,
    account,
    install_fake_gh,
    ok,
    scenario,
)
from tests.golden_harness import (
    Invocation,
    Labels,
    check_golden,
    isolate_cli,
    label_home,
    origin_identity,
    quoted,
    run_metab,
)
from tests.required_tools import needs_git

pytestmark = [
    needs_git,
    pytest.mark.skipif(os.name != "posix", reason="owner-only cache is POSIX-only"),
]

PULL = f"{CANONICAL}/pull"
# A record as the CLI prints it inside an envelope: the key, then the object up to the
# brace that closes it, which is the first one at the key's own indentation.
_RECORD = re.compile(r'^( *)"record": (\{\n.*?\n\1\})', re.MULTILINE | re.DOTALL)


class _Session:
    """The stand-in origin, the fake gh, and a transcript of what each command did."""

    def __init__(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, origin: Origin) -> None:
        self.tmp_path = tmp_path
        self.monkeypatch = monkeypatch
        self.home = isolate_cli(tmp_path, monkeypatch).home
        self.origin = origin
        # Each pull request's record as last printed in full, by number, and the
        # numbers printed in full, in order. The record is kept as JSON text, which
        # holds the order of its keys: a dictionary comparison would not.
        self.printed: dict[int, str] = {}
        self.in_full: list[int] = []
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

    def _once(self, found: re.Match[str]) -> str:
        record = json.loads(found.group(2))
        number, text = record["number"], json.dumps(record)
        if self.printed.get(number) == text:
            return f'{found.group(1)}"record": "<RECORD {number}>"'
        self.printed[number] = text
        self.in_full.append(number)
        return found.group(0)

    def run(self, *args: str) -> Invocation:
        result = run_metab(args)
        # A request body lives in the sandbox; the transcript names the file alone.
        shown = [arg.removeprefix(f"{self.tmp_path}/") for arg in args]
        printed = replace(result, stdout=_RECORD.sub(self._once, result.stdout))
        self.blocks.append(
            printed.block(" ".join(quoted(arg) for arg in shown), gh=self.gh_calls())
        )
        return result


def _with(answers: dict[str, Any], **changes: Any) -> dict[str, Any]:
    return {**answers, **changes}


def _api(answers: dict[str, Any], path: str, entry: Any) -> dict[str, Any]:
    return {**answers, "api": {**answers["api"], path: entry}}


def test_golden_pull_requests_fetch_refresh_and_read_offline(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, pull_origin: Origin
) -> None:
    session = _Session(tmp_path, monkeypatch, pull_origin)
    origin = session.origin
    online = scenario(origin)

    session.blocks.append(
        "## <RECORD n> is the record of pull request n, equal to the last one printed in "
        "full above; a record that differs is printed in full.\n"
    )
    first = session.run(f"{PULL}/7", "--api", "/api/plugin/github/pull")
    assert first.exit_code == 0, first.stderr
    envelope = first.payload()
    assert envelope["state"] == "current"
    assert envelope["pin"] == origin["fork_head"]
    assert envelope["record"]["comparison"]["base"] == origin["base"]
    refreshed = session.run(f"{PULL}/7", "--no-serve")
    assert refreshed.exit_code == 0, refreshed.stderr
    # The route a page posts to, through a refresh that completes: the one-shot command
    # prints the 202, waits, prints the record after it, and exits 0. A subprocess
    # transcript cannot show this, because it has no `gh` and no origin to fetch from.
    body = tmp_path / "refresh.json"
    body.write_text("{}\n", encoding="utf-8")
    routed = session.run(
        f"{PULL}/7", "--api", "/api/plugin/github/pull-refresh", "--data", str(body)
    )
    assert routed.exit_code == 0, routed.stderr
    started, _after, ended = routed.stdout.partition(
        "after: /api/plugin/github/pull\nstatus: 200\n"
    )
    assert started.startswith("api: /api/plugin/github/pull-refresh\nstatus: 202\n")
    assert json.loads(started[started.index("{") :])["refresh"] == "started"
    assert json.loads(ended)["state"] == "current"
    assert json.loads(ended)["record"] == envelope["record"]
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
    assert offline.payload()["record"] == envelope["record"]
    stale = session.run(f"{PULL}/7", "--no-serve")
    assert stale.exit_code == 0 and "; the refresh failed: " in stale.stdout
    assert "(network_error))" in stale.stdout

    session.answer(online)
    for number in (8, 9, 10):
        assert session.run(f"{PULL}/{number}", "--no-serve").exit_code == 0
    merged = session.run(f"{PULL}/8", "--api", "/api/plugin/github/pull")
    assert merged.payload()["record"]["comparison"] == {
        "base": origin["base"],
        "head": origin["merged_head"],
        "base_commit": origin["topic_before_merge"],
        "base_from": "base_sha",
    }

    # A secondary limit: requests remain and nothing says when it lifts.
    secondary = _api(
        online,
        "repos/octo/demo/pulls/11",
        {
            "status": 403,
            "headers": {"X-Ratelimit-Remaining": "4990"},
            "body": {"message": "You have exceeded a secondary rate limit."},
        },
    )
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
        ("rate_limited", secondary),
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

    # With no reset time to give, the refusal's stamp says null, and is kept: the route
    # answers from it, so the next command within the window does not ask gh again.
    session.answer(secondary)
    limited = session.run(f"{PULL}/11", "--api", "/api/plugin/github/pull")
    last = limited.payload()["last_refresh"]
    assert (last["outcome"], last["reset_at"]) == ("rate_limited", None)

    # The API shows the pull request while Git's fetch of its head is answered as a
    # repository GitHub does not show, as for credentials that stopped opening it
    # between the two. The one substitution: that fetch raises with the text Git
    # printed for such a repository; classifying it and the message are production code.
    session.answer(online)
    real_git = pull_refs.run_git

    async def head_not_shown(args: list[str], **kwargs: Any) -> bytes:
        if "fetch" in args and any("refs/pull/" in arg for arg in args):
            raise GitCommandError(
                args,
                128,
                "remote: Repository not found.\n"
                "fatal: repository 'https://github.com/octo/demo/' not found",
            )
        return await real_git(args, **kwargs)

    with monkeypatch.context() as patched:
        patched.setattr(pull_refs, "run_git", head_not_shown)
        session.blocks.append(
            "## Git's fetch of refs/pull/7/head is answered here with the text Git printed "
            "for a repository GitHub does not show.\n"
        )
        hidden = session.run(f"{PULL}/7", "--no-serve")
    assert hidden.exit_code == 0 and "(not_found_or_private))" in hidden.stdout

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
    assert missing.payload()["reason"] == "not_cached"
    # The cached record outlived every failed refresh.
    kept = session.run(f"{PULL}/7", "--api", "/api/plugin/github/pull")
    assert kept.exit_code == 0 and kept.payload()["record"] == envelope["record"]

    # The records and refresh stamps lie beside the source's own records, where the
    # cache reads nothing as damage: the source and its store are published, with no
    # problems. Read from a local root, which opens no source and asks gh nothing.
    (tmp_path / "root").mkdir()
    slug = origin_identity(CANONICAL).slug
    cached = session.run(str(tmp_path / "root"), "--api", f"/api/cache/source/{slug}")
    assert cached.exit_code == 0, cached.stderr

    rendered = label_home(Labels().apply("".join(session.blocks)), session.home)
    assert str(tmp_path) not in rendered and str(session.home) not in rendered
    assert "file://" not in rendered
    # One full print of each distinct record: pull request 7's and pull request 8's.
    assert session.in_full == [7, 8]
    check_golden("cli-github-pull-refresh.txt", rendered)
