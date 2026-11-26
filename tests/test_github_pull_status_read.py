"""Reading a pull request's operational status from GitHub, and keeping it.

The read is :mod:`metabrowser.builtin_plugins.github.pull_status_read`, given GitHub's
answers here by a stand-in for ``gh_graphql``; the store is the catalog's ``pull_status``
table and the checks file beside the record (:mod:`.pull_status_store`). A refresh that
reads the status beside a record, through the fake ``gh``, is in
``tests/test_github_pulls.py``.
"""

from __future__ import annotations

import asyncio
import copy
import sqlite3
from collections.abc import Callable, Mapping
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest

from metabrowser.builtin_plugins.github import pull_status_read, pull_status_store
from metabrowser.builtin_plugins.github.gh import GhError
from metabrowser.builtin_plugins.github.gh_lists import PullDataError, utc_stamp
from metabrowser.builtin_plugins.github.pull_catalog import (
    read_catalog,
    read_pull_status,
    write_pull_status,
)
from metabrowser.builtin_plugins.github.pull_list import ListedRepository
from metabrowser.builtin_plugins.github.pull_record import clear_pulls
from metabrowser.builtin_plugins.github.pull_status import (
    MAX_CHECK_ITEMS,
    CheckItem,
    PullChecks,
    PullStatus,
)
from metabrowser.builtin_plugins.github.pull_status_read import (
    CONTEXTS_PAGE,
    StatusRead,
    keep_pull_status,
    latest_of_each,
)
from metabrowser.builtin_plugins.github.pull_status_read import (
    read_pull_status as read_from_github,
)
from metabrowser.builtin_plugins.github.pull_status_store import (
    kept_status,
    read_pull_checks,
    read_status_outcome,
    write_pull_checks,
)
from tests.cache_home_fixture import (  # pyright: ignore[reportPrivateUsage]
    FixtureSource,
    _stage_and_publish_source,
    build_empty_home,
)
from tests.github_pull_fixture import CANONICAL, READER, generated_item, seed_catalog

HEAD = "a" * 40
OTHER_HEAD = "b" * 40
BASE = "c" * 40
NOW = datetime(2026, 11, 26, 12, 0, tzinfo=UTC)
SOURCE = FixtureSource("https", CANONICAL)


def _run(
    number: int, started: str | None = None, *, status: str = "COMPLETED", **fields: Any
) -> dict[str, Any]:
    return {
        "__typename": "CheckRun",
        "name": f"check {number}",
        "status": status,
        "conclusion": "SUCCESS" if status == "COMPLETED" else None,
        "isRequired": False,
        "detailsUrl": f"https://ci.example/run/{number}",
        "startedAt": started,
        "checkSuite": {"app": {"name": "GitHub Actions"}},
        **fields,
    }


def _context(name: str, state: str = "SUCCESS", **fields: Any) -> dict[str, Any]:
    return {
        "__typename": "StatusContext",
        "context": name,
        "state": state,
        "isRequired": False,
        "targetUrl": "https://ci.example/status",
        "description": "done",
        **fields,
    }


def _answer(
    nodes: list[dict[str, Any]],
    *,
    head: str = HEAD,
    rollup: str | None = "SUCCESS",
    cursor: str | None = None,
    runs: Mapping[str, int] | None = None,
    statuses: Mapping[str, int] | None = None,
    **pull: Any,
) -> dict[str, Any]:
    """One page of the status query's answer for pull request 5 of octo/demo."""

    contexts = {
        "pageInfo": {"hasNextPage": cursor is not None, "endCursor": cursor or "end"},
        "checkRunCountsByState": [
            {"state": state, "count": count} for state, count in (runs or {}).items()
        ],
        "statusContextCountsByState": [
            {"state": state, "count": count} for state, count in (statuses or {}).items()
        ],
        "nodes": nodes,
    }
    return {
        "viewer": {"login": READER},
        "rateLimit": {"cost": 1},
        "repository": {
            "nameWithOwner": "octo/demo",
            "pull": {
                "number": 5,
                "headRefOid": head,
                "baseRefName": "main",
                "baseRefOid": BASE,
                "isDraft": False,
                "mergeable": "MERGEABLE",
                "mergeStateStatus": "CLEAN",
                "reviewDecision": None,
                "isInMergeQueue": False,
                "mergeQueueEntry": None,
                "autoMergeRequest": None,
                "statusCheckRollup": None
                if rollup is None
                else {"state": rollup, "contexts": contexts},
                **pull,
            },
        },
    }


class _GitHub:
    """A stand-in for ``gh_graphql`` that answers each page in turn and records cursors."""

    def __init__(self, monkeypatch: pytest.MonkeyPatch, *pages: dict[str, Any] | Exception) -> None:
        self.pages = list(pages)
        self.cursors: list[str | None] = []

        async def answer(
            query: str, variables: Mapping[str, Any], *, now: datetime | None = None
        ) -> dict[str, Any]:
            assert query.startswith("query PullStatus(")
            self.cursors.append(variables.get("cursor"))
            page = self.pages.pop(0)
            if isinstance(page, Exception):
                raise page
            return copy.deepcopy(page)

        monkeypatch.setattr(pull_status_read, "gh_graphql", answer)


def _read(monkeypatch: pytest.MonkeyPatch, *pages: dict[str, Any] | Exception) -> StatusRead:
    _GitHub(monkeypatch, *pages)
    return asyncio.run(read_from_github("octo", "demo", 5, reader=f"gh:{READER}", now=lambda: NOW))


def _refused(monkeypatch: pytest.MonkeyPatch, *pages: dict[str, Any] | Exception) -> str:
    with pytest.raises(PullDataError) as caught:
        _read(monkeypatch, *pages)
    return caught.value.state


# ── Reading ─────────────────────────────────────────────────────


def test_a_read_is_the_status_and_checks_github_answered(monkeypatch: pytest.MonkeyPatch) -> None:
    answer = _answer(
        [
            _run(1, "2026-11-26T10:00:00Z", isRequired=True),
            _run(2, "2026-11-26T10:00:00Z", status="IN_PROGRESS", isRequired=True),
            _context("lint", "FAILURE"),
        ],
        rollup="FAILURE",
        runs={"SUCCESS": 1, "IN_PROGRESS": 1, "FAILURE": 0},
        statuses={"FAILURE": 1},
        mergeStateStatus="UNSTABLE",
        reviewDecision="APPROVED",
        isInMergeQueue=True,
        mergeQueueEntry={
            "state": "AWAITING_CHECKS",
            "position": 2,
            "enqueuedAt": "2026-11-26T11:00:00Z",
            "estimatedTimeToMerge": 600,
            "mergeQueue": {"url": "https://github.com/octo/demo/queue/main"},
        },
        autoMergeRequest={
            "mergeMethod": "REBASE",
            "enabledAt": "2026-11-26T11:00:00Z",
            "enabledBy": {"login": "maintainer"},
        },
    )
    read = _read(monkeypatch, answer)
    status = read.status
    assert (status.number, status.head, status.base_ref, status.base) == (5, HEAD, "main", BASE)
    assert (status.observed_at, status.observed_by) == (utc_stamp(NOW), "read")
    assert (status.conflicts, status.merge_state, status.review_decision) == (
        "mergeable",
        "unstable",
        "approved",
    )
    assert status.checks.state == "failure"
    assert status.checks.counts == {"pass": 1, "fail": 1, "pending": 1, "skipping": 0, "cancel": 0}
    assert (status.checks.required_failing, status.checks.required_pending) == (0, 1)
    assert status.queue is not None and (status.queue.state, status.queue.position) == (
        "awaiting_checks",
        2,
    )
    assert status.auto_merge is not None and (
        status.auto_merge.method,
        status.auto_merge.enabled_by,
    ) == (
        "rebase",
        "maintainer",
    )
    checks = read.checks
    assert (checks.number, checks.head, checks.observed_at, checks.truncated) == (
        5,
        HEAD,
        status.observed_at,
        False,
    )
    assert [(item.name, item.kind, item.bucket, item.required) for item in checks.items] == [
        ("check 1", "run", "pass", True),
        ("check 2", "run", "pending", True),
        ("lint", "status", "fail", False),
    ]
    assert checks.items[2].conclusion == "FAILURE" and checks.items[2].status is None


def test_a_head_with_no_checks_has_no_rollup(monkeypatch: pytest.MonkeyPatch) -> None:
    read = _read(monkeypatch, _answer([], rollup=None))
    assert read.status.checks.state == "none" and read.status.checks.total == 0
    assert read.checks.items == () and not read.checks.truncated


def test_the_checks_are_paged_until_github_says_there_are_no_more(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    first = [_run(n, "2026-11-26T10:00:00Z") for n in range(CONTEXTS_PAGE)]
    second = [_run(CONTEXTS_PAGE + n, "2026-11-26T10:00:00Z") for n in range(20)]
    github = _GitHub(
        monkeypatch,
        _answer(first, cursor="page-2", runs={"SUCCESS": 120}),
        _answer(second, runs={"SUCCESS": 120}),
    )
    read = asyncio.run(read_from_github("octo", "demo", 5, reader=f"gh:{READER}", now=lambda: NOW))
    assert github.cursors == [None, "page-2"]
    assert len(read.checks.items) == 120 and not read.checks.truncated
    assert read.status.checks.counts["pass"] == 120
    assert read.status.checks.required_failing == 0


def test_past_the_bound_the_list_is_cut_and_the_required_counts_unknown(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    pages = [
        _answer(
            [_run(page * CONTEXTS_PAGE + n) for n in range(CONTEXTS_PAGE)],
            cursor=f"page-{page + 2}",
            runs={"SUCCESS": 1000},
        )
        for page in range(MAX_CHECK_ITEMS // CONTEXTS_PAGE + 1)
    ]
    github = _GitHub(monkeypatch, *pages)
    read = asyncio.run(read_from_github("octo", "demo", 5, reader=f"gh:{READER}", now=lambda: NOW))
    assert len(github.cursors) == MAX_CHECK_ITEMS // CONTEXTS_PAGE
    assert len(read.checks.items) == MAX_CHECK_ITEMS and read.checks.truncated
    assert read.status.checks.counts["pass"] == 1000
    assert (read.status.checks.required_failing, read.status.checks.required_pending) == (
        None,
        None,
    )


def test_a_push_between_pages_ends_the_list_at_the_first_head(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    first = _answer([_run(n) for n in range(CONTEXTS_PAGE)], cursor="page-2")
    moved = _answer([_run(500)], head=OTHER_HEAD)
    read = _read(monkeypatch, first, moved)
    assert read.status.head == HEAD == read.checks.head
    assert len(read.checks.items) == CONTEXTS_PAGE and read.checks.truncated
    assert "check 500" not in {item.name for item in read.checks.items}


def test_only_the_latest_run_of_each_check_is_kept() -> None:
    def item(name: str, conclusion: str) -> CheckItem:
        return CheckItem(name=name, kind="run", bucket="pass", conclusion=conclusion)

    listed = [
        (item("build", "FAILURE"), "2026-11-26T10:00:00Z"),
        (item("lint", "SUCCESS"), ""),
        (item("build", "SUCCESS"), "2026-11-26T10:05:00Z"),
        (item("build", "CANCELLED"), "2026-11-26T09:00:00Z"),
        (item("lint", "FAILURE"), ""),
    ]
    kept = latest_of_each(listed)
    # The newest build, and of two runs that never started, the one listed first, each
    # where GitHub listed it.
    assert [(each.name, each.conclusion) for each in kept] == [
        ("lint", "SUCCESS"),
        ("build", "SUCCESS"),
    ]


def test_a_rerun_check_is_listed_once_and_its_latest_run_judges_it(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    answer = _answer(
        [
            _run(1, "2026-11-26T10:00:00Z", conclusion="FAILURE", isRequired=True),
            _run(1, "2026-11-26T10:09:00Z", isRequired=True),
        ],
        runs={"SUCCESS": 1, "FAILURE": 1},
    )
    read = _read(monkeypatch, answer)
    assert [(item.name, item.conclusion) for item in read.checks.items] == [("check 1", "SUCCESS")]
    assert read.status.checks.required_failing == 0
    # The counts are GitHub's own, of every context, as the Pulls tab's scan reads them.
    assert read.status.checks.counts["fail"] == 1


def test_a_cancelled_required_check_counts_as_failing(monkeypatch: pytest.MonkeyPatch) -> None:
    answer = _answer(
        [_run(1, conclusion="CANCELLED", isRequired=True), _run(2, conclusion="CANCELLED")],
        rollup="FAILURE",
        runs={"CANCELLED": 2},
    )
    read = _read(monkeypatch, answer)
    assert [item.bucket for item in read.checks.items] == ["cancel", "cancel"]
    assert (read.status.checks.required_failing, read.status.checks.required_pending) == (1, 0)


def test_a_check_that_cannot_be_read_is_left_out_and_the_list_cut(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    answer = _answer(
        [_run(1), {"__typename": "CheckRun", "name": None}, {"__typename": "Deployment"}, {}],
        runs={"SUCCESS": 4},
    )
    read = _read(monkeypatch, answer)
    assert [item.name for item in read.checks.items] == ["check 1"] and read.checks.truncated
    assert read.status.checks.required_failing is None


def test_a_check_that_does_not_say_whether_it_is_required_leaves_the_counts_unknown(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    read = _read(monkeypatch, _answer([_run(1, isRequired=None)], runs={"SUCCESS": 1}))
    assert read.checks.items[0].required is None and not read.checks.truncated
    assert (read.status.checks.required_failing, read.status.checks.required_pending) == (
        None,
        None,
    )


def test_an_http_link_and_an_unknown_time_are_left_empty(monkeypatch: pytest.MonkeyPatch) -> None:
    answer = _answer(
        [_run(1, "yesterday", detailsUrl="http://ci.example/run/1")],
        runs={"SUCCESS": 1},
        autoMergeRequest={"mergeMethod": "OCTOPUS", "enabledAt": "soon", "enabledBy": None},
    )
    read = _read(monkeypatch, answer)
    assert read.checks.items[0].details_url is None
    assert read.status.auto_merge is not None
    assert (read.status.auto_merge.method, read.status.auto_merge.enabled_at) == (None, None)


def _break(path: tuple[str | int, ...], value: object) -> Callable[[dict[str, Any]], None]:
    def apply(answer: dict[str, Any]) -> None:
        node: Any = answer
        for key in path[:-1]:
            node = node[key]
        if value is KeyError:
            del node[path[-1]]
        else:
            node[path[-1]] = value

    return apply


_PULL = ("repository", "pull")
_CONTEXTS = (*_PULL, "statusCheckRollup", "contexts")


@pytest.mark.parametrize(
    "broken",
    [
        _break(("viewer",), None),
        _break(("repository", "nameWithOwner"), "someone/else"),
        _break((*_PULL, "number"), 6),
        _break((*_PULL, "number"), "5"),
        _break((*_PULL, "headRefOid"), "not a commit"),
        _break((*_PULL, "baseRefName"), ""),
        _break((*_PULL, "mergeable"), "MAYBE"),
        _break((*_PULL, "mergeStateStatus"), KeyError),
        _break((*_PULL, "statusCheckRollup", "state"), "SPARKLY"),
        _break((*_CONTEXTS, "checkRunCountsByState"), None),
        _break((*_CONTEXTS, "statusContextCountsByState", 0, "count"), -1),
        _break((*_CONTEXTS, "nodes"), [_run(n) for n in range(CONTEXTS_PAGE + 1)]),
        _break((*_CONTEXTS, "pageInfo"), "next"),
        _break(("repository",), []),
    ],
)
def test_an_answer_github_does_not_document_is_unreadable_and_raises_nothing_else(
    monkeypatch: pytest.MonkeyPatch, broken: Callable[[dict[str, Any]], None]
) -> None:
    answer = _answer([_run(1)], runs={"SUCCESS": 1}, statuses={"SUCCESS": 0})
    broken(answer)
    assert _refused(monkeypatch, answer) == "gh_failed"


def test_another_viewer_or_a_missing_pull_request_is_a_typed_refusal(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    other = _answer([])
    other["viewer"] = {"login": "someone-else"}
    assert _refused(monkeypatch, other) == "account_changed"
    gone = _answer([])
    gone["repository"]["pull"] = None
    assert _refused(monkeypatch, gone) == "not_found_or_private"
    hidden = _answer([])
    hidden["repository"] = None
    assert _refused(monkeypatch, hidden) == "not_found_or_private"
    limited = GhError("GitHub's API rate limit is exhausted", state="rate_limited")
    assert _refused(monkeypatch, limited) == "rate_limited"


# ── Keeping ─────────────────────────────────────────────────────


@pytest.fixture
def repository(tmp_path: Path) -> ListedRepository:
    home = tmp_path / "home"
    build_empty_home(home)
    _stage_and_publish_source(home, SOURCE, opened=False)
    return ListedRepository(home, SOURCE.slug, "octo", "demo")


def _status(observed_at: str, *, head: str = HEAD, number: int = 5) -> PullStatus:
    return PullStatus.model_validate(
        {
            "number": number,
            "head": head,
            "base_ref": "main",
            "observed_at": observed_at,
            "observed_by": "read",
            "conflicts": "mergeable",
            "merge_state": "clean",
            "checks": {
                "state": "none",
                "counts": {"pass": 0, "fail": 0, "pending": 0, "skipping": 0, "cancel": 0},
            },
        }
    )


def _checks(observed_at: str, count: int = 1, *, name: str = "check") -> PullChecks:
    items = tuple(
        CheckItem(name=f"{name} {n}", kind="run", bucket="pass", description="x" * 200)
        for n in range(count)
    )
    return PullChecks(number=5, head=HEAD, observed_at=observed_at, items=items)


def test_a_status_keeps_the_newer_observation_whatever_its_head(
    repository: ListedRepository,
) -> None:
    home, slug = repository.home, repository.slug
    assert read_pull_status(home, slug, 5) is None
    assert write_pull_status(repository, _status("2026-11-26T12:00:05Z"))
    # A read that ended later but asked earlier, for the head before a push, is dropped.
    assert not write_pull_status(repository, _status("2026-11-26T12:00:01Z", head=OTHER_HEAD))
    assert read_pull_status(home, slug, 5) == _status("2026-11-26T12:00:05Z")
    # The same moment replaces: it is the later write.
    assert write_pull_status(repository, _status("2026-11-26T12:00:05Z", head=OTHER_HEAD))
    assert write_pull_status(repository, _status("2026-11-26T12:00:09Z", number=6))
    assert read_pull_status(home, slug, 5) == _status("2026-11-26T12:00:05Z", head=OTHER_HEAD)
    assert read_pull_status(home, slug, 6) == _status("2026-11-26T12:00:09Z", number=6)


def test_a_status_moves_no_catalog_row_revision_or_generation(
    repository: ListedRepository,
) -> None:
    before = seed_catalog(repository, [generated_item(5), generated_item(6)])
    assert write_pull_status(repository, _status("2026-11-26T12:00:00Z"))
    assert read_catalog(repository.home, repository.slug) == before


def test_a_status_outlives_the_catalog_pages_another_account_reads(
    repository: ListedRepository,
) -> None:
    """A catalog's rows start over for another account; its statuses stay, as records do."""

    home, slug = repository.home, repository.slug
    # Kept before any page, as when a pull request page opens before its Pulls tab.
    assert write_pull_status(repository, _status("2026-11-26T12:00:00Z"))
    seed_catalog(repository, [generated_item(5)])
    seed_catalog(repository, [generated_item(6)], reader="someone-else")
    assert read_pull_status(home, slug, 5) == _status("2026-11-26T12:00:00Z")


def test_a_row_whose_columns_disagree_with_its_status_is_none(
    repository: ListedRepository,
) -> None:
    assert write_pull_status(repository, _status("2026-11-26T12:00:00Z"))
    path = repository.home / f"sources/{repository.slug}/pulls/catalog.sqlite3"
    with sqlite3.connect(path) as db:
        db.execute("UPDATE pull_status SET head=?", (OTHER_HEAD,))
    assert read_pull_status(repository.home, repository.slug, 5) is None
    with sqlite3.connect(path) as db:
        db.execute("UPDATE pull_status SET head=?, body=?", (HEAD, '{"number": 5}'))
    assert read_pull_status(repository.home, repository.slug, 5) is None


def test_checks_keep_the_newer_list_and_always_fit_their_bound(
    repository: ListedRepository, monkeypatch: pytest.MonkeyPatch
) -> None:
    home, slug = repository.home, repository.slug
    assert read_pull_checks(home, slug, 5) is None
    assert write_pull_checks(home, slug, _checks("2026-11-26T12:00:05Z", name="new"))
    assert not write_pull_checks(home, slug, _checks("2026-11-26T12:00:01Z", name="old"))
    kept = read_pull_checks(home, slug, 5)
    assert kept is not None and kept.items[0].name == "new 0"
    monkeypatch.setattr(pull_status_store, "MAX_PULL_CHECKS_BYTES", 4096)
    many = _checks("2026-11-26T12:00:09Z", 100)
    assert len(many.model_dump_json()) > 4096
    assert write_pull_checks(home, slug, many)
    cut = read_pull_checks(home, slug, 5)
    assert cut is not None and cut.truncated and 0 < len(cut.items) < 100
    assert cut.items == many.items[: len(cut.items)]


def test_clearing_the_cache_clears_the_status_and_its_checks(
    repository: ListedRepository,
) -> None:
    home, slug = repository.home, repository.slug
    seed_catalog(repository, [generated_item(5)])
    assert write_pull_status(repository, _status("2026-11-26T12:00:00Z"))
    assert write_pull_checks(home, slug, _checks("2026-11-26T12:00:00Z"))
    clear_pulls(home, slug)
    assert kept_status(home, slug, 5) == pull_status_store.KeptStatus(None, None, None)


def test_a_failed_read_keeps_what_an_earlier_one_kept_and_says_why(
    repository: ListedRepository, monkeypatch: pytest.MonkeyPatch
) -> None:
    home, slug = repository.home, repository.slug

    def keep() -> PullStatus | None:
        return asyncio.run(
            keep_pull_status(repository, "octo", "demo", 5, reader=f"gh:{READER}", now=lambda: NOW)
        )

    _GitHub(monkeypatch, _answer([_run(1)], runs={"SUCCESS": 1}))
    status = keep()
    assert status is not None and kept_status(home, slug, 5).unavailable is None
    outcome = read_status_outcome(home, slug, 5)
    assert outcome is not None and (outcome.outcome, outcome.at) == ("succeeded", utc_stamp(NOW))
    _GitHub(monkeypatch, GhError("GitHub could not complete the metadata query"))
    assert keep() is None
    kept = kept_status(home, slug, 5)
    assert (kept.status, kept.unavailable) == (status, "gh_failed")
    assert kept.checks is not None and [item.name for item in kept.checks.items] == ["check 1"]


def test_a_catalog_a_newer_release_wrote_is_left_as_it_is(
    repository: ListedRepository, monkeypatch: pytest.MonkeyPatch
) -> None:
    seed_catalog(repository, [generated_item(5)])
    path = repository.home / f"sources/{repository.slug}/pulls/catalog.sqlite3"
    with sqlite3.connect(path) as db:
        db.execute("PRAGMA user_version=999")
    _GitHub(monkeypatch, _answer([_run(1)], runs={"SUCCESS": 1}))
    kept = asyncio.run(
        keep_pull_status(repository, "octo", "demo", 5, reader=f"gh:{READER}", now=lambda: NOW)
    )
    assert kept is None
    assert kept_status(repository.home, repository.slug, 5).unavailable == "newer_cache"
    with sqlite3.connect(path) as db:
        assert db.execute("PRAGMA user_version").fetchone()[0] == 999
