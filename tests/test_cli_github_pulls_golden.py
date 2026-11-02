"""Golden CLI transcript: a repository's lists of pull requests fetched, extended, and refused.

Each command runs the production CLI in-process, as ``tests/test_cli_github_pull_golden.py``
does, with these substitutions and nothing else:

- ``metabrowser.cache.acquire.remote_url_for`` clones ``https://github.com/octo/demo`` from
  the local origin in ``tests/github_pull_fixture.py``;
- a fake ``gh`` first on ``PATH`` replays list pages built on a scrubbed real item, and logs
  every call, which the transcript lists after each command;
- the clock is fixed, and a block says where it moves, so ``fetched_at``, the window, and a
  list's state are the same every run.

Reading a list from a prebuilt home, with no ``gh`` at all, runs as a subprocess in
``tests/golden/cli-github-pulls.tryscript.md``. This transcript is what that one cannot
show: a refresh that completes, the requests it made, and a list that is ``current``.
"""

from __future__ import annotations

import json
import os
from datetime import timedelta
from pathlib import Path
from typing import Any

import pytest

from metabrowser.builtin_plugins.github import gh, pull_list
from metabrowser.cache.urls import GitSource
from tests.github_pull_fixture import (
    ANOTHER_READER,
    CANONICAL,
    FETCHED_AT,
    Origin,
    account,
    generated_item,
    install_fake_gh,
    list_entries,
    list_item,
    list_page,
    logged_gh_calls,
    next_link,
    ok,
    pull_bodies,
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

PULLS = "/api/plugin/github/pulls"
REFRESH = "/api/plugin/github/pulls-refresh"


class _Session:
    """The stand-in origin, the fake gh, the clock, and a transcript of each command."""

    def __init__(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, origin: Origin) -> None:
        self.tmp_path = tmp_path
        self.monkeypatch = monkeypatch
        self.home = isolate_cli(tmp_path, monkeypatch).home
        self.origin = origin
        self.now = FETCHED_AT
        local = origin.url

        def remote_url_for(source: GitSource) -> str:
            return local if source.normalized == CANONICAL else source.normalized

        monkeypatch.setattr("metabrowser.cache.acquire.remote_url_for", remote_url_for)
        monkeypatch.setattr(pull_list, "utc_now", lambda: self.now)
        self.blocks: list[str] = []
        self.answer(scenario(origin))

    def answer(self, answers: dict[str, Any]) -> None:
        for name, value in install_fake_gh(self.tmp_path, answers).items():
            self.monkeypatch.setenv(name, value)

    def say(self, text: str) -> None:
        self.blocks.append(f"## {text}\n")

    def advance(self, seconds: float) -> None:
        self.now += timedelta(seconds=seconds)
        self.say(f"The clock moves on {seconds:g} s, to {self.now:%Y-%m-%dT%H:%M:%SZ}.")

    def _run(self, *args: str, **sections: list[str]) -> Invocation:
        result = run_metab(args)
        shown = [arg.removeprefix(f"{self.tmp_path}/") for arg in args]
        self.blocks.append(
            result.block(
                " ".join(quoted(arg) for arg in shown),
                **sections,
                gh=logged_gh_calls(self.tmp_path),
            )
        )
        return result

    def get(self, query: str = "") -> Invocation:
        return self._run(CANONICAL, "--api", f"{PULLS}{query}")

    def post(self, body: dict[str, Any]) -> Invocation:
        path = self.tmp_path / "request.json"
        text = json.dumps(body)
        path.write_text(text + "\n", encoding="utf-8")
        return self._run(CANONICAL, "--api", REFRESH, "--data", str(path), body=[text])

    def local(self, route: str) -> Invocation:
        """A route read from a local root, which opens no source and asks gh nothing."""

        root = self.tmp_path / "root"
        root.mkdir(exist_ok=True)
        return self._run(str(root), "--api", route)


def _after(result: Invocation) -> dict[str, Any]:
    """The envelope a one-shot refresh printed after the job ended."""

    return json.loads(
        result.stdout[result.stdout.rindex("status: 200\n{") + len("status: 200\n") :]
    )


def _with(answers: dict[str, Any], **changes: Any) -> dict[str, Any]:
    return {**answers, **changes}


def _api(answers: dict[str, Any], path: str, entry: Any) -> dict[str, Any]:
    return {**answers, "api": {**answers["api"], path: entry}}


def _numbers(result: Invocation) -> list[int]:
    return [row["number"] for row in result.payload()["rows"]]


def test_golden_pull_lists_fetch_extend_refresh_and_refuse(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, pull_origin: Origin
) -> None:
    session = _Session(tmp_path, monkeypatch, pull_origin)
    online = scenario(session.origin)
    first_path, second_path = list_page("all"), list_page("all", 2)
    slug = origin_identity(CANONICAL).slug
    known = {
        number: list_item(parts["pull"]) for number, parts in pull_bodies(session.origin).items()
    }

    # Nothing is cached, and a read asks gh nothing.
    empty = session.get()
    assert empty.exit_code == 0, empty.stderr
    assert (empty.payload()["state"], empty.payload()["reason"]) == ("absent", "not_cached")

    # The default list. The command waits for the job and prints the envelope after it.
    started = session.post({})
    assert started.exit_code == 0, started.stderr
    assert _after(started)["list"] == "all"
    assert _after(started)["state"] == "current"
    assert (_after(started)["fetched"], _after(started)["complete"]) == (100, False)

    # Windows of what is cached, with no gh: the newest, the next, and the last, which is
    # where this incomplete list's cached rows end although GitHub has more.
    newest = session.get("?limit=2")
    assert _numbers(newest) == [106, 105]
    assert newest.payload()["next_after"] == 105
    assert _numbers(session.get("?limit=2&after=105")) == [104, 103]
    end = session.get("?limit=4&after=11")
    assert _numbers(end) == [10, 9, 8, 7]
    assert [row["merged"] for row in end.payload()["rows"]] == [False, False, True, False]
    assert end.payload()["next_after"] is None

    # Tried within the window: an automatic request starts nothing.
    waiting = session.post({"state": "all"})
    assert waiting.exit_code == 0 and json.loads(waiting.stdout.split("status: 200\n")[1])[
        "refresh"
    ] == ("not_due")

    # One more GitHub page, asking for that page alone, and now the list is complete.
    extended = session.post({"more": True})
    assert (_after(extended)["fetched"], _after(extended)["complete"]) == (102, True)
    assert _numbers(session.get("?limit=2&after=7")) == [6, 5]

    # A refresh rereads each page it holds, conditionally, and a 304 reuses its rows.
    session.advance(61)
    assert session.get("?limit=0").payload()["state"] == "stale"
    reread = session.post({})
    assert _after(reread)["fetched"] == 102 and _after(reread)["state"] == "current"

    # The list moved between the two page reads: a pull request opened, so the first page
    # is new, and another opened after it, so 8 is on both pages. The number dedupes it.
    session.advance(61)
    moved_first = [
        *(generated_item(number) for number in range(107, 10, -1)),
        *(known[number] for number in (10, 9, 8)),
    ]
    moved_second = [known[8], known[7], generated_item(6), generated_item(5)]
    moved = _api(
        _api(
            online, first_path, ok(first_path, moved_first, next_link("repos/octo/demo/pulls", 1))
        ),
        second_path,
        ok(second_path, moved_second),
    )
    session.answer(moved)
    shifted = session.post({})
    assert _after(shifted)["fetched"] == 103
    assert _numbers(session.get("?limit=3&after=9")) == [8, 7, 6]

    # The other two lists are their own files, each fetched when asked for.
    session.answer(online)
    assert _after(session.post({"state": "open"}))["fetched"] == 2
    assert _numbers(session.get("?state=open")) == [10, 7]
    assert _after(session.post({"state": "closed"}))["fetched"] == 2
    closed = session.get("?state=closed")
    assert [(row["number"], row["merged"]) for row in closed.payload()["rows"]] == [
        (9, False),
        (8, True),
    ]

    # Another account. A refresh that fails under it leaves the list labelled with the
    # reader who fetched it, and stale though it is young.
    session.answer(
        _with(
            online,
            auth=account(ANOTHER_READER),
            api_failure={"stderr": "error connecting to api.github.com\n", "exit": 1},
        )
    )
    assert session.post({"retry": True}).exit_code == 1
    labelled = session.get("?limit=0").payload()
    assert (labelled["state"], labelled["reader"]) == ("stale", "gh:octo-reader")

    # One that succeeds replaces the whole file, sends no other reader's ETag, and starts
    # again from the first page, for Load more as for a refresh.
    session.answer(_with(online, auth=account(ANOTHER_READER)))
    replaced = _after(session.post({"more": True}))
    assert (replaced["reader"], replaced["fetched"]) == (f"gh:{ANOTHER_READER}", 100)

    # The lists and stamps lie beside the source's own records, where the cache reads
    # nothing as damage: the source and its store are published, with no problems.
    cached = session.local(f"/api/cache/source/{slug}")
    assert cached.exit_code == 0, cached.stderr

    rendered = label_home(Labels().apply("".join(session.blocks)), session.home)
    assert str(tmp_path) not in rendered and str(session.home) not in rendered
    assert "file://" not in rendered
    check_golden("cli-github-pulls-refresh.txt", rendered)


def test_golden_pull_list_failures(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, pull_origin: Origin
) -> None:
    session = _Session(tmp_path, monkeypatch, pull_origin)
    online = scenario(session.origin)
    first_path = list_page("all")
    assert session.post({}).exit_code == 0

    # Each typed failure, asked for as a reader's Retry so the window does not hold it.
    # The cached list outlives them all.
    limited_primary = {
        "status": 403,
        "headers": {"X-Ratelimit-Remaining": "0", "X-Ratelimit-Reset": "1790181960"},
        "body": {"message": "API rate limit exceeded"},
    }
    failures: list[tuple[str, dict[str, Any]]] = [
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
                first_path,
                {
                    "status": 429,
                    "headers": {"Retry-After": "120"},
                    "body": {"message": "slow down"},
                },
            ),
        ),
        (
            "not_found_or_private",
            _api(online, first_path, {"status": 404, "body": {"message": "Not Found"}}),
        ),
        (
            "network_error",
            _with(
                online, api_failure={"stderr": "error connecting to api.github.com\n", "exit": 1}
            ),
        ),
        ("gh_failed", _api(online, first_path, {"status": 200, "raw": "not JSON"})),
        ("account_changed", _with(online, auth=[account(), account(ANOTHER_READER)])),
    ]
    for state, answers in failures:
        session.answer(answers)
        refused = session.post({"retry": True})
        assert refused.exit_code == 1, (state, refused.stdout)
        assert _after(refused)["last_refresh"]["outcome"] == state
        assert _after(refused)["fetched"] == 100, state

    with monkeypatch.context() as patched:
        patched.setattr(gh, "gh_executable", lambda: None)
        missing = session.post({"retry": True})
    assert _after(missing)["last_refresh"]["outcome"] == "gh_missing"

    # Offline, the list still opens, and asks gh nothing.
    session.answer(
        _with(online, api_failure={"stderr": "error connecting to api.github.com\n", "exit": 1})
    )
    offline = session.get("?limit=1")
    assert offline.exit_code == 0 and offline.payload()["fetched"] == 100

    # A rate limit with a reset time holds automatic requests past the window, until it.
    session.answer(_api(online, first_path, limited_primary))
    assert session.post({"retry": True}).exit_code == 1
    session.advance(61)
    session.answer(online)
    held = session.post({})
    assert json.loads(held.stdout.split("status: 200\n")[1])["refresh"] == "not_due"
    session.advance(7 * 24 * 3600)
    assert _after(session.post({}))["last_refresh"]["outcome"] == "succeeded"

    # The cache will not take the list, nor the stamp: the command still says why, and
    # the list as it was is still there to read once it can be.
    slug = origin_identity(CANONICAL).slug
    pulls_directory = session.home / "sources" / slug / "pulls"
    pulls_directory.chmod(0o500)
    try:
        unwritable = session.post({"retry": True})
    finally:
        pulls_directory.chmod(0o700)
    assert unwritable.exit_code == 1
    assert _after(unwritable)["last_refresh"]["outcome"] == "cache_unwritable"
    session.answer(online)
    assert _after(session.post({"retry": True}))["last_refresh"]["outcome"] == "succeeded"

    rendered = label_home(Labels().apply("".join(session.blocks)), session.home)
    assert str(tmp_path) not in rendered and str(session.home) not in rendered
    assert "file://" not in rendered
    check_golden("cli-github-pulls-failures.txt", rendered)


def test_list_entries_cover_what_the_transcript_asks_for(pull_origin: Origin) -> None:
    """The fixture's full page is full, since a short page with a next link reads on."""

    entries = list_entries(pull_origin)
    assert len(entries[list_page("all")]["body"]) == 100
    assert "Link" in entries[list_page("all")]["headers"]
    assert "Link" not in entries[list_page("all", 2)]["headers"]
    # GitHub's own shape: merged_at, and no merged flag, unlike a single pull request.
    item = entries[list_page("all")]["body"][-2]
    assert item["merged_at"] is not None and "merged" not in item
    assert {"url", "body", "_links"} <= set(item)
