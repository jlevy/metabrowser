"""Golden CLI transcript: a pull request's changed files listed, refreshed, and refused.

Each command runs the production CLI in-process, as ``tests/test_cli_github_pulls_golden.py``
does, with the same substitutions: the stand-in origin for ``https://github.com/octo/demo``,
a fake ``gh`` first on ``PATH`` that replays full-size pages of changed files built on a
scrubbed real item and logs every call, which the transcript lists after each command, and
a fixed clock that a block says when it moves.

Reading lists from a prebuilt home, with no ``gh`` at all, runs as a subprocess in
``tests/golden/cli-github-pull-files.tryscript.md``. This transcript is what that one
cannot show: a refresh that completes, from GitHub's pages or from the local comparison,
the requests it made, and a list that is ``current``. ``cli-github-pull-file-anchor.txt``
is the file a Changes tab URL's ``#diff-<hash>`` names, against those lists.
"""

from __future__ import annotations

import asyncio
import json
import os
import threading
from datetime import timedelta
from itertools import count
from pathlib import Path
from typing import Any
from uuid import UUID

import pytest

from metabrowser.builtin_plugins.github import (
    gh,
    pull_files_refresh,
    pull_files_route,
    pull_list,
    pulls,
)
from metabrowser.builtin_plugins.github.pull_catalog import read_catalog
from metabrowser.builtin_plugins.github.pull_file_anchor import path_digest
from metabrowser.builtin_plugins.github.pull_record import PullRefreshStamp
from metabrowser.cache.urls import GitSource
from tests.github_pull_fixture import (
    ANOTHER_READER,
    CANONICAL,
    CAPPED_PULL,
    FETCHED_AT,
    TREE_PULL,
    Origin,
    account,
    catalog_entries,
    file_item,
    file_pages,
    files_page,
    files_scenario,
    generated_item,
    in_a_stable_order,
    install_fake_gh,
    logged_gh_calls,
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
        elapsed = count(step=300_000_000)
        monkeypatch.setattr(
            "metabrowser.builtin_plugins.github.pull_list_refresh.monotonic_ns", elapsed.__next__
        )
        monkeypatch.setattr(pulls, "utc_now", lambda: self.now)
        generations = count(1)
        monkeypatch.setattr(pull_files_refresh, "uuid4", lambda: UUID(int=next(generations)))
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
    pushed = _api(online, first_page, file_pages(TREE_PULL, moved)[first_page])
    pushed = {**pushed, "api": {**pushed["api"], **catalog_entries([pushed_row])}}
    session.answer(pushed)
    request = tmp_path / "list-request.json"
    request.write_text('{"state": "all", "target": 500, "retry": true}\n', encoding="utf-8")
    listed_again = session.run(
        CANONICAL, "--api", "/api/plugin/github/pulls-refresh", "--data", str(request)
    )
    assert listed_again.exit_code == 0, listed_again.stderr
    assert _after(listed_again)["repository_total"] == 1
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

    labels = Labels()
    catalog = read_catalog(session.home, origin_identity(CANONICAL).slug)
    assert catalog is not None
    labels.add(catalog.epoch, "<CATALOG_EPOCH_1>")
    rendered = normalize_pull_comparison_scopes(
        label_home(labels.apply("".join(session.blocks)), session.home)
    )
    assert str(tmp_path) not in rendered and str(session.home) not in rendered
    assert "file://" not in rendered
    check_golden("cli-github-pull-files-refresh.txt", rendered)


def test_golden_a_changes_url_anchor_opens_the_file_it_names(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, pull_origin: Origin
) -> None:
    """GitHub's ``#diff-<hash>``, the SHA-256 of a changed file's path, on a Changes URL.

    It resolves against the list the files route answers from, then the record's
    comparison, and never asks gh; the ``file`` line of each command says what it named.
    An anchor no list names opens the Changes tab itself, and is not an error.
    """

    session = _Session(tmp_path, monkeypatch, pull_origin)
    online = files_scenario(session.origin)
    changes = f"{CANONICAL}/pull/7/files"
    app_txt, new_md = path_digest("src/app.txt"), path_digest("docs/new.md")
    assert app_txt is not None and new_md is not None

    session.say(
        "No list is cached. Opening the pull request fetches its record, whose comparison "
        "in the store names the file."
    )
    first = session.run(f"{changes}#diff-{app_txt}R2", "--no-serve")
    assert first.exit_code == 0, first.stderr
    assert "\nfile: src/app.txt\ndiff_line: R2 (the Changes tab opens at the file, not " in (
        first.stdout
    )

    session.say("Once the list is cached, the files route's own list names it, with no Git.")
    assert session.post({"number": 7}).exit_code == 0
    listed = session.run(f"{changes}#diff-{new_md}L1-R1", "--api", f"{FILES}?number=7")
    assert listed.exit_code == 0, listed.stderr
    assert _paths(listed) == ["docs/new.md", "src/app.txt"]
    assert "\nfile: docs/new.md\ndiff_line: L1-R1 " in listed.stderr

    session.say(
        "GitHub's Changes page is `/changes` since 2026-01-22, and `/files` its older "
        "spelling: both carry the same anchor."
    )
    moved = session.run(f"{CANONICAL}/pull/7/changes#diff-{app_txt}R2", "--no-serve")
    assert moved.exit_code == 0, moved.stderr
    assert "\ntab: files\nfile: src/app.txt\ndiff_line: R2 " in moved.stdout

    session.say("A file the pull request does not change, and a hash GitHub never writes.")
    unchanged = session.run(f"{changes}#diff-{path_digest('README.md')}", "--no-serve")
    assert unchanged.exit_code == 0, unchanged.stderr
    assert "(file_not_changed); opening the Changes tab\n" in unchanged.stdout
    dropped = session.run(f"{changes}#diff-{app_txt[:32]}", "--no-serve")
    assert dropped.exit_code == 0 and "file:" not in dropped.stdout

    session.say(
        "Offline, a pull request with no record and no list: nothing names the file, and "
        "the pin is the default branch."
    )
    session.answer(
        _with(online, api_failure={"stderr": "error connecting to api.github.com\n", "exit": 1})
    )
    unknown = session.run(f"{CANONICAL}/pull/11/files#diff-{app_txt}", "--no-serve")
    assert unknown.exit_code == 0, unknown.stderr
    assert "(files_unknown); opening the Changes tab\n" in unknown.stdout

    rendered = normalize_pull_comparison_scopes(
        label_home(Labels().apply("".join(session.blocks)), session.home)
    )
    assert str(tmp_path) not in rendered and str(session.home) not in rendered
    assert "file://" not in rendered
    check_golden("cli-github-pull-file-anchor.txt", rendered)


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


def test_a_started_refresh_answers_with_the_list_as_its_job_found_it(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, pull_origin: Origin
) -> None:
    """``files`` in the answer that starts a job is read before that job can write.

    Here the job's stamp lands as it starts, the earliest it can. Without a ``gh`` the job
    writes its ``gh_missing`` within microseconds, and in CI run 44043888346 it did so
    while the route read ``files`` for the transcript above (mb-kq72). Mutation check:
    read ``files`` after the start, as the route did, and the job that is still
    ``refreshing`` reports its own outcome as the last refresh.
    """

    session = _Session(tmp_path, monkeypatch, pull_origin)
    assert session.post({"number": TREE_PULL}).exit_code == 0
    session.advance(1)
    real_start = pull_files_route.start_files_refresh
    written: list[pull_files_route.FilesRefreshStart] = []

    def start_then_write(
        view: pull_files_route.FilesView, ask: pull_files_route.FilesRefreshRequest, **kw: Any
    ) -> pull_files_route.FilesRefreshStart:
        started = real_start(view, ask, **kw)
        repository = view.repository
        assert repository is not None
        ended = PullRefreshStamp(outcome="gh_missing", at=f"{session.now:%Y-%m-%dT%H:%M:%SZ}")
        pull_list.write_files_refresh(repository.home, repository.slug, ask.number, ended)
        written.append(started)
        return started

    monkeypatch.setattr(pull_files_route, "start_files_refresh", start_then_write)
    monkeypatch.setattr(gh, "gh_executable", lambda: None)
    missing = session.post({"number": TREE_PULL, "retry": True})

    # The route reaches the start through the module, so the write ran, once.
    assert written == ["started"]
    answer = _first(missing)
    assert (answer["refresh"], answer["files"]["refreshing"]) == ("started", True)
    assert answer["files"]["last_refresh"]["outcome"] == "succeeded"
    assert answer["files"]["last_refresh"]["at"] == f"{FETCHED_AT:%Y-%m-%dT%H:%M:%SZ}"
    assert answer["files"]["state"] == "current"
    assert _after(missing)["last_refresh"]["outcome"] == "gh_missing"


def test_an_answer_that_starts_no_job_is_read_after_the_one_that_ended(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, pull_origin: Origin
) -> None:
    """``files`` in an answer that says nothing is refreshing is read after nothing was.

    A job another request started ends while this request reads ``files`` before its
    start, and this request then starts none: ``not_due``, nothing refreshing. Read only
    before the start, the answer showed the list as it was before that job ended,
    ``current`` and ``succeeded``, which the tree holds as current for a freshness window
    (review A1 on #513). Mutation check: drop the read after the start, and it does.
    """

    session = _Session(tmp_path, monkeypatch, pull_origin)
    assert session.post({"number": TREE_PULL}).exit_code == 0
    session.advance(1)
    real_view, real_read = pull_files_route.files_view, pull_files_route.read_files
    ended = threading.Event()
    releases: list[tuple[asyncio.AbstractEventLoop, asyncio.Event]] = []
    reads: list[pull_files_route.FilesFound | None] = []

    def view_beside_a_job(app: Any, number: int) -> pull_files_route.FilesView:
        view = real_view(app, number)
        repository, coordinator = view.repository, view.coordinator
        if releases or repository is None or coordinator is None:
            return view
        release = asyncio.Event()
        changed = PullRefreshStamp(
            outcome="account_changed", at=f"{session.now:%Y-%m-%dT%H:%M:%SZ}"
        )

        async def another_requests_job() -> None:
            await release.wait()
            await asyncio.to_thread(
                pull_list.write_files_refresh, repository.home, repository.slug, number, changed
            )

        key = pull_files_route.files_job_key(repository, number)
        assert coordinator.start(key, another_requests_job, network=False) == "started"
        job = coordinator.job(key)
        assert job is not None
        job.add_done_callback(lambda _job: ended.set())
        releases.append((asyncio.get_running_loop(), release))
        return real_view(app, number)

    def read_as_that_job_ends(
        view: pull_files_route.FilesView,
    ) -> pull_files_route.FilesFound | None:
        found = real_read(view)
        if not reads:
            loop, release = releases[0]
            loop.call_soon_threadsafe(release.set)
            assert ended.wait(timeout=30)
        reads.append(found)
        return found

    monkeypatch.setattr(pull_files_route, "files_view", view_beside_a_job)
    monkeypatch.setattr(pull_files_route, "read_files", read_as_that_job_ends)
    answered = session.post({"number": TREE_PULL})

    # The job ran beside the request, and the first read was made before it ended.
    assert len(releases) == 1 and ended.is_set()
    first = reads[0]
    assert first is not None and first.stamp is not None and first.stamp.outcome == "succeeded"
    answer = _first(answered)
    assert (answer["refresh"], answer["files"]["refreshing"]) == ("not_due", False)
    assert answer["files"]["last_refresh"]["outcome"] == "account_changed"
    assert answer["files"]["state"] == "stale"
    listed = session.get(f"?number={TREE_PULL}&limit=0").payload()
    assert (listed["state"], listed["last_refresh"]["outcome"]) == ("stale", "account_changed")
