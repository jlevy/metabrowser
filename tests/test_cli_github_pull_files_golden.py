"""Golden CLI transcript: a pull request's changed files listed, refreshed, and refused.

Each command runs the production CLI in-process, as ``tests/test_cli_github_pulls_golden.py``
does, with the same substitutions: the stand-in origin for ``https://github.com/octo/demo``,
a fake ``gh`` first on ``PATH`` that replays full-size pages of changed files built on a
scrubbed real item and logs every call, which the transcript lists after each command, and
a fixed clock that a block says when it moves.

Reading lists from a prebuilt home, with no ``gh`` at all, runs as a subprocess in
``tests/golden/cli-github-pull-files.tryscript.md``. This transcript is what that one
cannot show: a refresh that completes, from GitHub's pages or from the local comparison,
the requests it made, and a list that is ``current``.
"""

from __future__ import annotations

import json
import os
from datetime import timedelta
from pathlib import Path
from typing import Any

import pytest

from metabrowser.builtin_plugins.github import gh, pull_list, pulls
from metabrowser.cache.urls import GitSource
from tests.github_pull_fixture import (
    ANOTHER_READER,
    CANONICAL,
    CAPPED_PULL,
    FETCHED_AT,
    TREE_PULL,
    Origin,
    account,
    file_item,
    file_pages,
    files_page,
    files_scenario,
    generated_item,
    in_a_stable_order,
    install_fake_gh,
    list_page,
    logged_gh_calls,
    ok,
    tree_files,
)
from tests.golden_harness import (
    Invocation,
    Labels,
    check_golden,
    isolate_cli,
    label_home,
    normalize_pull_comparison_scopes,
    origin_identity,
    quoted,
    run_metab,
)
from tests.required_tools import needs_git

pytestmark = [
    needs_git,
    pytest.mark.skipif(os.name != "posix", reason="owner-only cache is POSIX-only"),
]

FILES = "/api/plugin/github/pull-files"
REFRESH = "/api/plugin/github/pull-files-refresh"


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
        monkeypatch.setattr(pulls, "utc_now", lambda: self.now)
        self.blocks: list[str] = []
        self.answer(files_scenario(origin))

    def answer(self, answers: dict[str, Any]) -> None:
        for name, value in install_fake_gh(self.tmp_path, answers).items():
            self.monkeypatch.setenv(name, value)

    def say(self, text: str) -> None:
        self.blocks.append(f"## {text}\n")

    def advance(self, seconds: float) -> None:
        self.now += timedelta(seconds=seconds)
        self.say(f"The clock moves on {seconds:g} s, to {self.now:%Y-%m-%dT%H:%M:%SZ}.")

    def run(self, *args: str, **sections: list[str]) -> Invocation:
        result = run_metab(args)
        shown = [arg.removeprefix(f"{self.tmp_path}/") for arg in args]
        self.blocks.append(
            result.block(
                " ".join(quoted(arg) for arg in shown),
                **sections,
                gh=in_a_stable_order(logged_gh_calls(self.tmp_path)),
            )
        )
        return result

    def get(self, query: str) -> Invocation:
        return self.run(CANONICAL, "--api", f"{FILES}{query}")

    def post(self, body: dict[str, Any]) -> Invocation:
        path = self.tmp_path / "request.json"
        text = json.dumps(body)
        path.write_text(text + "\n", encoding="utf-8")
        return self.run(CANONICAL, "--api", REFRESH, "--data", str(path), body=[text])


def _first(result: Invocation) -> dict[str, Any]:
    """What a refresh request answered at once."""

    text = result.stdout
    start = text.index("{")
    return json.JSONDecoder().raw_decode(text[start:])[0]


def _after(result: Invocation) -> dict[str, Any]:
    """The envelope a one-shot refresh printed after the job ended."""

    return json.loads(
        result.stdout[result.stdout.rindex("status: 200\n{") + len("status: 200\n") :]
    )


def _api(answers: dict[str, Any], path: str, entry: Any) -> dict[str, Any]:
    return {**answers, "api": {**answers["api"], path: entry}}


def _with(answers: dict[str, Any], **changes: Any) -> dict[str, Any]:
    return {**answers, **changes}


def _paths(result: Invocation) -> list[str]:
    return [row["path"] for row in result.payload()["rows"]]


def test_golden_pull_files_listed_refreshed_and_refused(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, pull_origin: Origin
) -> None:
    session = _Session(tmp_path, monkeypatch, pull_origin)
    online = files_scenario(session.origin)

    # Nothing is cached, and a read asks gh nothing.
    empty = session.get(f"?number={TREE_PULL}")
    assert (empty.payload()["state"], empty.payload()["reason"]) == ("absent", "not_cached")

    # A pull request the mirror has never fetched: GitHub's list, three pages and the account
    # around them, and no Git. The command waits for the job and prints the envelope after it.
    listed = session.post({"number": TREE_PULL})
    assert listed.exit_code == 0, listed.stderr
    after = _after(listed)
    assert (after["state"], after["listed_from"], after["fetched"]) == ("current", "github", 249)
    assert (after["complete"], after["pages"], after["last_page"]) == (True, 3, 3)

    # A window of the rows: a rename keeps the old path, and a name that holds a control or a
    # zero-width character is displayed with each replaced, while its path stays the identity.
    head = session.get(f"?number={TREE_PULL}&limit=3")
    assert _paths(head) == ["README.md", "assets/logo.png", "docs/guide.md"]
    assert head.payload()["rows"][2]["previous_path"] == "docs/old-guide.md"
    tail = session.get(f"?number={TREE_PULL}&offset=245")
    assert [row["display"] for row in tail.payload()["rows"]] == [
        "src/app/views/two.py",
        "tools/new/script.sh",
        "weird/bell�name.txt",
        "weird/zero�width.md",
    ]
    assert tail.payload()["rows"][2]["path"] == "weird/bell\u0007name.txt"

    # Expanded again while current, it starts nothing and asks gh nothing.
    current = session.post({"number": TREE_PULL})
    assert _first(current)["refresh"] == "not_due"

    # A pull request the mirror has fetched: its record's comparison is in the store, so the
    # list is that comparison's manifest, with no gh and no network.
    cached = session.run(f"{CANONICAL}/pull/7", "--api", "/api/plugin/github/pull?number=7")
    assert cached.exit_code == 0, cached.stderr
    local = _after(session.post({"number": 7}))
    assert (local["state"], local["listed_from"]) == ("current", "comparison")
    assert _paths(session.get("?number=7")) == ["docs/new.md", "src/app.txt"]

    # GitHub stops listing at 3,000 files, and the list says so.
    capped = _after(session.post({"number": CAPPED_PULL}))
    assert (capped["fetched"], capped["complete"], capped["capped"]) == (3000, True, True)
    assert (capped["pages"], capped["last_page"]) == (30, 30)

    # A force-push. The pull request's row says it changed after the list was read, so the
    # list is stale; expanding it rereads each page conditionally, and the pages that
    # changed come back whole while the rest are reused.
    session.advance(120)
    pushed_row = {**generated_item(TREE_PULL), "updated_at": "2026-09-17T12:01:00Z"}
    moved = tree_files()
    moved[0] = file_item("README.md", "modified", None, 5, 1)
    first_page = files_page(TREE_PULL, 1)
    pushed = _api(
        _api(online, list_page("all"), ok(list_page("all"), [pushed_row])),
        first_page,
        file_pages(TREE_PULL, moved)[first_page],
    )
    session.answer(pushed)
    request = tmp_path / "list-request.json"
    request.write_text('{"retry": true}\n', encoding="utf-8")
    listed_again = session.run(
        CANONICAL, "--api", "/api/plugin/github/pulls-refresh", "--data", str(request)
    )
    assert listed_again.exit_code == 0, listed_again.stderr
    stale = session.get(f"?number={TREE_PULL}&limit=1")
    assert stale.payload()["state"] == "stale"
    reread = _after(session.post({"number": TREE_PULL}))
    assert (reread["state"], reread["fetched"]) == ("current", 249)
    assert session.get(f"?number={TREE_PULL}&limit=1").payload()["rows"][0]["additions"] == 5

    # Another account. A refresh that fails under it leaves the list labelled with the reader
    # who read it, and stale.
    session.answer(
        _with(
            online,
            auth=account(ANOTHER_READER),
            api_failure={"stderr": "error connecting to api.github.com\n", "exit": 1},
        )
    )
    assert session.post({"number": TREE_PULL, "retry": True}).exit_code == 1
    labelled = session.get(f"?number={TREE_PULL}&limit=0").payload()
    assert (labelled["state"], labelled["reader"]) == ("stale", "gh:octo-reader")

    rendered = normalize_pull_comparison_scopes(
        label_home(Labels().apply("".join(session.blocks)), session.home)
    )
    assert str(tmp_path) not in rendered and str(session.home) not in rendered
    assert "file://" not in rendered
    check_golden("cli-github-pull-files-refresh.txt", rendered)


def test_golden_pull_files_failures(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, pull_origin: Origin
) -> None:
    session = _Session(tmp_path, monkeypatch, pull_origin)
    online = files_scenario(session.origin)
    first = files_page(TREE_PULL, 1)
    assert session.post({"number": TREE_PULL}).exit_code == 0

    # Each typed failure, asked for as a reader's Retry so the window does not hold it. The
    # cached list outlives them all.
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
            "not_found_or_private",
            _api(online, first, {"status": 404, "body": {"message": "Not Found"}}),
        ),
        (
            "network_error",
            _with(
                online, api_failure={"stderr": "error connecting to api.github.com\n", "exit": 1}
            ),
        ),
        ("gh_failed", _api(online, first, {"status": 200, "raw": "not JSON"})),
    ]
    for state, answers in failures:
        session.answer(answers)
        refused = session.post({"number": TREE_PULL, "retry": True})
        assert refused.exit_code == 1, (state, refused.stdout)
        assert _after(refused)["last_refresh"]["outcome"] == state
        assert _after(refused)["fetched"] == 249, state

    # The account changed during the pages.
    session.answer(_with(online, auth=[account(), account(ANOTHER_READER)]))
    switched = session.post({"number": TREE_PULL, "retry": True})
    assert _after(switched)["last_refresh"]["outcome"] == "account_changed"
    assert _after(switched)["state"] == "stale"

    with monkeypatch.context() as patched:
        patched.setattr(gh, "gh_executable", lambda: None)
        missing = session.post({"number": TREE_PULL, "retry": True})
    assert _after(missing)["last_refresh"]["outcome"] == "gh_missing"

    # A list that stops part-way keeps the pages it published: the first two of three, with
    # the page count GitHub gave, and it says it is not complete. Here GitHub's limit stops
    # it at the third page.
    halted = CAPPED_PULL - 1
    limited = {
        "status": 403,
        "headers": {"X-Ratelimit-Remaining": "0", "X-Ratelimit-Reset": "1790181960"},
        "body": {"message": "API rate limit exceeded"},
    }
    session.answer(
        {
            **online,
            "api": {
                **online["api"],
                **file_pages(halted, tree_files()),
                files_page(halted, 3): limited,
            },
        }
    )
    stopped = session.post({"number": halted, "retry": True})
    part = _after(stopped)
    assert (part["fetched"], part["complete"], part["pages"], part["last_page"]) == (
        200,
        False,
        2,
        3,
    )
    assert part["last_refresh"]["outcome"] == "rate_limited"

    # A limit with a time on it holds a reader's Retry as well, asking gh nothing.
    held = session.post({"number": halted, "retry": True})
    assert _first(held)["refresh"] == "not_due"

    # The cache will not take the list: the command still says why.
    session.answer(online)
    slug = origin_identity(CANONICAL).slug
    pulls_directory = session.home / "sources" / slug / "pulls"
    pulls_directory.chmod(0o500)
    try:
        unwritable = session.post({"number": CAPPED_PULL, "retry": True})
    finally:
        pulls_directory.chmod(0o700)
    assert _after(unwritable)["last_refresh"]["outcome"] == "cache_unwritable"

    rendered = normalize_pull_comparison_scopes(
        label_home(Labels().apply("".join(session.blocks)), session.home)
    )
    assert str(tmp_path) not in rendered and str(session.home) not in rendered
    check_golden("cli-github-pull-files-failures.txt", rendered)
