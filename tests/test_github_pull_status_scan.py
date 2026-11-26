"""The Pulls tab's scan of every open pull request's status, and how its statuses are kept.

The scan is :mod:`metabrowser.builtin_plugins.github.pull_status_scan`, given GitHub's pages
here by a stand-in for ``gh_graphql``; the route that answers what it kept is
:mod:`.pull_statuses_route`. A scan and a page's read write one store, so what they keep of
each other is held as invariants over generated pairs of observations
(:func:`~.pull_status.kept_observation`), and so is what the page is then shown and asks
for (:attr:`~.pull_status_store.KeptStatus.listed_checks`, :func:`~.pull_freshness.listing_missing`).
``tests/test_cli_github_pull_statuses_golden.py`` drives the scan and the route through
``metab --api``.
"""

from __future__ import annotations

import asyncio
import copy
import itertools
import os
import subprocess
from collections.abc import Mapping
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import pytest

from metabrowser.builtin_plugins.github import (
    gh_budget,
    pull_list,
    pull_status_read,
    pull_status_scan,
)
from metabrowser.builtin_plugins.github.gh import GhError
from metabrowser.builtin_plugins.github.gh_lists import PullDataError, utc_stamp
from metabrowser.builtin_plugins.github.pull_catalog import (
    PAGE_SIZE,
    catalog_statuses,
    read_pull_status,
    write_pull_status,
    write_pull_statuses,
)
from metabrowser.builtin_plugins.github.pull_list import ListedRepository
from metabrowser.builtin_plugins.github.pull_status import (
    BUCKETS,
    ChecksSummary,
    PullChecks,
    PullStatus,
    kept_observation,
    same_checks,
)
from metabrowser.builtin_plugins.github.pull_status_scan import (
    MAX_SCAN_PAGES,
    SCAN_POINT_GAP_S,
    SCAN_ROWS,
    ScanStamp,
    ask_status_scan,
    read_scan_stamp,
    run_scan,
    scan_due,
)
from metabrowser.builtin_plugins.github.pull_status_store import KeptStatus
from metabrowser.builtin_plugins.github.pull_statuses_route import envelope_etag, pull_statuses
from metabrowser.builtin_plugins.github.served_pull import FULL_REFRESH_S, MERGEABLE_SETTLE_S
from metabrowser.mirror_refresh import FRESHNESS_WINDOW_S, RefreshCoordinator
from tests.cache_home_fixture import (  # pyright: ignore[reportPrivateUsage]
    FixtureSource,
    _stage_and_publish_source,
    build_empty_home,
)
from tests.github_pull_fixture import CANONICAL, READER, generated_item, seed_catalog
from tests.required_tools import needs_git

HEAD = "a" * 40
OTHER_HEAD = "b" * 40
BASE = "c" * 40
MOVED_BASE = "d" * 40
NOW = datetime(2026, 11, 26, 12, 0, tzinfo=UTC)
SOURCE = FixtureSource("https", CANONICAL)
SUMMARIES: dict[str, dict[str, int]] = {
    "one passing": {"pass": 1},
    "one pending": {"pending": 1},
    "two passing": {"pass": 2},
}


def _status(
    observed_at: str,
    *,
    head: str = HEAD,
    by: str = "read",
    summary: str = "one passing",
    number: int = 5,
    base: str | None = BASE,
    conflicts: str = "mergeable",
) -> PullStatus:
    """A status as a read (listing its checks, with their required counts) or a scan keeps it."""

    counts = dict.fromkeys(BUCKETS, 0) | SUMMARIES[summary]
    listed = by == "read"
    return PullStatus(
        number=number,
        head=head,
        base_ref="main",
        base=base,
        observed_at=observed_at,
        observed_by=by,  # pyright: ignore[reportArgumentType]
        conflicts=conflicts,  # pyright: ignore[reportArgumentType]
        merge_state="clean" if conflicts != "unknown" else "unknown",
        checks=ChecksSummary(
            state="pending" if counts["pending"] else "success",
            counts=counts,  # pyright: ignore[reportArgumentType]
            required_failing=0 if listed else None,
            required_pending=counts["pending"] if listed else None,
            listed_at=observed_at if listed else None,
        ),
    )


def _observations() -> list[PullStatus]:
    """Every observation of one pull request over two heads, three moments, both readers,
    and three summaries of its checks."""

    return [
        _status(f"2026-11-26T12:00:0{second}Z", head=head, by=by, summary=summary)
        for head, second, by, summary in itertools.product(
            (HEAD, OTHER_HEAD), (1, 2, 3), ("read", "scan"), SUMMARIES
        )
    ]


def _listing(status: PullStatus) -> tuple[str | None, int | None, int | None]:
    checks = status.checks
    return checks.listed_at, checks.required_failing, checks.required_pending


def _without_listing(status: PullStatus) -> PullStatus:
    return status.model_copy(
        update={
            "checks": status.checks.model_copy(
                update={"listed_at": None, "required_failing": None, "required_pending": None}
            )
        }
    )


# ── Keeping a scan beside a read ────────────────────────────────


@pytest.mark.parametrize("kept", [None, *_observations()])
def test_the_newer_observation_is_kept_and_only_its_list_can_come_from_the_older(
    kept: PullStatus | None,
) -> None:
    for incoming in _observations():
        result = kept_observation(kept, incoming)
        if kept is None:
            newer, older = incoming, None
        elif incoming.observed_at >= kept.observed_at:
            newer, older = incoming, kept
        else:
            newer, older = kept, incoming
        # Everything but the list behind the checks is the newer observation's.
        assert _without_listing(result) == _without_listing(newer)
        if result.checks.listed_at is not None:
            # A list is never carried to another head, or to checks it does not sum to.
            source = next(
                each
                for each in (newer, older)
                if each is not None and each.checks.listed_at == result.checks.listed_at
            )
            assert same_checks(source, result) and _listing(source) == _listing(result)
        if (
            older is not None
            and newer.checks.listed_at is None
            and older.checks.listed_at is not None
            and same_checks(newer, older)
        ):
            # A scan that finds a read's checks as the read left them takes nothing away.
            assert _listing(result) == _listing(older)


def test_keeping_two_observations_does_not_depend_on_which_was_written_first() -> None:
    for one, other in itertools.combinations(_observations(), 2):
        if one.observed_at != other.observed_at:
            assert kept_observation(one, other) == kept_observation(other, one)


@pytest.fixture
def repository(tmp_path: Path) -> ListedRepository:
    home = tmp_path / "home"
    build_empty_home(home)
    _stage_and_publish_source(home, SOURCE, opened=False)
    return ListedRepository(home, SOURCE.slug, "octo", "demo")


def test_the_store_keeps_what_the_rule_keeps_in_either_order(
    repository: ListedRepository,
) -> None:
    home, slug = repository.home, repository.slug
    pairs = [
        (one, other)
        for one, other in itertools.permutations(_observations(), 2)
        if one.observed_at != other.observed_at
    ][:60]
    for number, (one, other) in enumerate(pairs, start=1):
        first, second = (each.model_copy(update={"number": number}) for each in (one, other))
        write_pull_status(repository, first)
        write_pull_status(repository, second)
        assert read_pull_status(home, slug, number) == kept_observation(first, second)


def test_a_scan_of_the_same_checks_keeps_the_reads_list_and_one_of_new_checks_drops_it(
    repository: ListedRepository,
) -> None:
    home, slug = repository.home, repository.slug
    read = _status("2026-11-26T12:00:01Z")
    assert write_pull_status(repository, read)
    same = _status("2026-11-26T12:00:05Z", by="scan")
    assert write_pull_status(repository, same)
    kept = read_pull_status(home, slug, 5)
    assert kept is not None and kept.observed_by == "scan" and _listing(kept) == _listing(read)
    moved = _status("2026-11-26T12:00:09Z", by="scan", summary="one pending")
    assert write_pull_status(repository, moved)
    assert read_pull_status(home, slug, 5) == moved
    pushed = _status("2026-11-26T12:00:12Z", by="scan", head=OTHER_HEAD)
    assert write_pull_status(repository, pushed)
    assert read_pull_status(home, slug, 5) == pushed


def test_a_page_of_statuses_is_one_transaction_of_at_most_a_page(
    repository: ListedRepository,
) -> None:
    statuses = [_status("2026-11-26T12:00:01Z", number=n, by="scan") for n in range(1, 4)]
    assert write_pull_statuses(repository, statuses) == 3
    assert write_pull_statuses(repository, statuses) == 3
    older = [_status("2026-11-26T11:00:00Z", number=n, by="scan") for n in range(1, 4)]
    assert write_pull_statuses(repository, older) == 0
    with pytest.raises(ValueError, match="once"):
        write_pull_statuses(repository, [statuses[0], statuses[0]])
    with pytest.raises(ValueError, match="page"):
        write_pull_statuses(
            repository,
            [_status("2026-11-26T12:00:01Z", number=n) for n in range(1, PAGE_SIZE + 2)],
        )


# ── What the page is shown, and what it reads ───────────────────


def _checks(observed_at: str, head: str = HEAD) -> PullChecks:
    return PullChecks(number=5, head=head, observed_at=observed_at, items=())


def test_checks_are_shown_only_beside_the_status_that_counts_them() -> None:
    lists = [
        _checks(f"2026-11-26T12:00:0{n}Z", head) for n in (1, 2, 3) for head in (HEAD, OTHER_HEAD)
    ]
    for status, checks in itertools.product([None, *_observations()], [None, *lists]):
        shown = KeptStatus(status, checks, None).listed_checks
        if shown is None:
            continue
        assert status is not None and shown is checks
        assert shown.head == status.head and shown.observed_at == status.checks.listed_at


# ── The scan's pages ────────────────────────────────────────────


def _node(
    number: int,
    *,
    head: str = HEAD,
    mergeable: str = "MERGEABLE",
    merge_state: str = "CLEAN",
    base: str = BASE,
    base_ref: str = "main",
) -> dict[str, Any]:
    return {
        "number": number,
        "headRefOid": head,
        "baseRefName": base_ref,
        "baseRefOid": base,
        "mergeable": mergeable,
        "mergeStateStatus": merge_state,
        "reviewDecision": None,
        "isInMergeQueue": False,
        "mergeQueueEntry": None,
        "autoMergeRequest": None,
        "statusCheckRollup": {
            "state": "SUCCESS",
            "contexts": {
                "checkRunCountsByState": [{"state": "SUCCESS", "count": 1}],
                "statusContextCountsByState": [],
            },
        },
    }


def _page(
    nodes: list[dict[str, Any]], *, cursor: str | None = None, viewer: str = READER
) -> dict[str, Any]:
    return {
        "viewer": {"login": viewer},
        "rateLimit": {"cost": 1},
        "repository": {
            "nameWithOwner": "octo/demo",
            "pullRequests": {
                "pageInfo": {"hasNextPage": cursor is not None, "endCursor": cursor or "end"},
                "nodes": nodes,
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
            assert query.startswith("query PullStatuses(")
            self.cursors.append(variables.get("cursor"))
            page = self.pages.pop(0)
            if isinstance(page, Exception):
                raise page
            return copy.deepcopy(page)

        monkeypatch.setattr(pull_status_read, "gh_graphql", answer)


@pytest.fixture
def clock(monkeypatch: pytest.MonkeyPatch) -> list[datetime]:
    """The list's clock, which the scan reads, held at :data:`NOW` until a test moves it."""

    now = [NOW]
    monkeypatch.setattr(pull_list, "utc_now", lambda: now[0])
    gh_budget.forget()
    return now


def _scan(
    repository: ListedRepository, trigger: str = "periodic", previous: ScanStamp | None = None
) -> ScanStamp:
    return asyncio.run(
        run_scan(
            repository,
            trigger,  # pyright: ignore[reportArgumentType]
            reader=f"gh:{READER}",
            previous=previous,
        )
    )


def test_a_scan_walks_the_newest_pages_and_keeps_each_as_a_scan(
    repository: ListedRepository, monkeypatch: pytest.MonkeyPatch, clock: list[datetime]
) -> None:
    pages = [
        _page([_node(100 - page * SCAN_ROWS - n) for n in range(SCAN_ROWS)], cursor=f"after-{page}")
        for page in range(MAX_SCAN_PAGES + 1)
    ]
    github = _GitHub(monkeypatch, *pages)
    stamp = _scan(repository)
    # The bound: the newest pages and no more, each asked after the one before.
    assert github.cursors == [None, *(f"after-{page}" for page in range(MAX_SCAN_PAGES - 1))]
    assert (stamp.outcome, stamp.pages, stamp.rows, stamp.cost) == (
        "succeeded",
        MAX_SCAN_PAGES,
        MAX_SCAN_PAGES * SCAN_ROWS,
        MAX_SCAN_PAGES,
    )
    found = catalog_statuses(repository.home, repository.slug, (100, 1))
    status = found.statuses[100]
    assert (status.observed_by, status.observed_at, status.head) == ("scan", utc_stamp(NOW), HEAD)
    # A scan lists no check, so it knows nothing it would take a list to know.
    assert _listing(status) == (None, None, None)
    assert stamp.bases == {"main": BASE} and stamp.walked_at == utc_stamp(NOW)
    assert stamp.next_at == utc_stamp(NOW + timedelta(seconds=MAX_SCAN_PAGES * SCAN_POINT_GAP_S))


def test_unknown_answers_are_read_once_more_on_their_own_pages(
    repository: ListedRepository, monkeypatch: pytest.MonkeyPatch, clock: list[datetime]
) -> None:
    unknown = _node(9, mergeable="UNKNOWN", merge_state="UNKNOWN")
    _GitHub(
        monkeypatch,
        _page([_node(10)], cursor="p2"),
        _page([unknown], cursor="p3"),
        _page([_node(8)]),
    )
    walked = _scan(repository)
    assert (walked.unknown, walked.settle_cursors) == (1, ("p2",))
    assert walked.settle_at == utc_stamp(NOW + timedelta(seconds=MERGEABLE_SETTLE_S))
    clock[0] = NOW + timedelta(seconds=MERGEABLE_SETTLE_S)
    assert scan_due(walked, now=clock[0]) == "settle"
    github = _GitHub(monkeypatch, _page([_node(9)], cursor="p3"))
    settled = _scan(repository, "settle", walked)
    assert github.cursors == ["p2"]
    # Once: a settle re-read leaves none to settle, and the walk's clock stands.
    assert (settled.trigger, settled.unknown, settled.settle_at, settled.settle_cursors) == (
        "settle",
        0,
        None,
        (),
    )
    assert settled.walked_at == walked.walked_at
    kept = read_pull_status(repository.home, repository.slug, 9)
    assert kept is not None and kept.conflicts == "mergeable"


def test_a_page_github_did_not_send_as_documented_is_refused_and_a_row_left_out(
    repository: ListedRepository, monkeypatch: pytest.MonkeyPatch, clock: list[datetime]
) -> None:
    odd = _node(9) | {"mergeable": "MAYBE"}
    _GitHub(monkeypatch, _page([_node(10), odd]))
    assert _scan(repository).rows == 1
    assert read_pull_status(repository.home, repository.slug, 9) is None
    # More pages, and no cursor to follow to them, cannot be read.
    stuck = _page([_node(10)], cursor="more")
    stuck["repository"]["pullRequests"]["pageInfo"]["endCursor"] = None
    refusals: dict[str, dict[str, Any]] = {
        "account_changed": _page([_node(10)], viewer="someone-else"),
        "gh_failed": stuck,
        "not_found_or_private": {"viewer": {"login": READER}, "repository": None},
    }
    for state, answer in refusals.items():
        _GitHub(monkeypatch, answer)
        assert _scan(repository).outcome == state


def test_a_failed_scan_keeps_every_status_and_waits_a_window(
    repository: ListedRepository, monkeypatch: pytest.MonkeyPatch, clock: list[datetime]
) -> None:
    _GitHub(monkeypatch, _page([_node(10)]))
    first = _scan(repository)
    before = read_pull_status(repository.home, repository.slug, 10)
    clock[0] = NOW + timedelta(seconds=FULL_REFRESH_S + 1)
    _GitHub(monkeypatch, GhError("GitHub could not complete the metadata query"))
    failed = _scan(repository, previous=first)
    assert failed.outcome == "gh_failed" and failed.message
    assert read_scan_stamp(repository.home, repository.slug) == failed
    assert read_pull_status(repository.home, repository.slug, 10) == before
    # What the next scan needs of the last that read is kept through a failure.
    assert (failed.walked_at, failed.bases) == (first.walked_at, first.bases)
    assert scan_due(failed, now=clock[0], changed=True) is None
    later = clock[0] + timedelta(seconds=FRESHNESS_WINDOW_S + 1)
    assert scan_due(failed, now=later) == "periodic"
    assert scan_due(failed, now=clock[0], retry=True) == "retry"


# ── When it runs ────────────────────────────────────────────────


def _stamp(**fields: Any) -> ScanStamp:
    stamp = utc_stamp(NOW)
    values: dict[str, Any] = {
        "outcome": "succeeded",
        "at": stamp,
        "started_at": stamp,
        "trigger": "periodic",
        "pages": 1,
        "rows": 1,
        "cost": 1,
        "unknown": 0,
        "walked_at": stamp,
        "next_at": utc_stamp(NOW + timedelta(seconds=SCAN_POINT_GAP_S)),
        "bases": {"main": BASE},
    }
    return ScanStamp.model_validate(values | fields)


def _observe(remaining: int, *, limit: int = 5000) -> None:
    gh_budget.observe(
        {
            "x-ratelimit-limit": str(limit),
            "x-ratelimit-remaining": str(remaining),
            "x-ratelimit-reset": str(int((NOW + timedelta(hours=1)).timestamp())),
            "x-ratelimit-resource": "graphql",
        },
        resource="graphql",
    )


def test_each_trigger_starts_a_scan_when_it_should(clock: list[datetime]) -> None:
    stamp = _stamp()
    soon = NOW + timedelta(seconds=SCAN_POINT_GAP_S - 1)
    spaced = NOW + timedelta(seconds=SCAN_POINT_GAP_S)
    periodic = NOW + timedelta(seconds=FULL_REFRESH_S + 1)
    assert scan_due(None, now=NOW) == "periodic"
    # The spacing holds a change, a moved base, and the clock alike; a reader's Refresh no.
    assert scan_due(stamp, now=soon, changed=True, base_moved=True) is None
    assert scan_due(stamp, now=soon, retry=True) == "retry"
    assert scan_due(stamp, now=spaced, changed=True) == "changed"
    assert scan_due(stamp, now=spaced, base_moved=True) == "base_moved"
    assert scan_due(stamp, now=spaced) is None
    assert scan_due(stamp, now=periodic) == "periodic"
    # Below the GraphQL floor the clock waits and a change does not.
    _observe(int(5000 * gh_budget.BACKGROUND_FLOOR))
    assert scan_due(stamp, now=periodic) is None
    assert scan_due(stamp, now=periodic, changed=True) == "changed"
    # A rate hold stops even a reader's Refresh.
    gh_budget.hold(utc_stamp(NOW + timedelta(hours=1)), now=NOW)
    assert scan_due(stamp, now=periodic, retry=True) is None
    gh_budget.forget()
    with gh_budget.speculative():
        assert scan_due(stamp, now=periodic) is None


def test_the_spacing_bounds_what_the_scans_spend_an_hour(clock: list[datetime]) -> None:
    """Asked every second with a change waiting, scans of the most pages spend at most a
    point a ``SCAN_POINT_GAP_S``."""

    stamp: ScanStamp | None = None
    spent = 0
    for second in range(3600):
        now = NOW + timedelta(seconds=second)
        trigger = scan_due(stamp, now=now, changed=True)
        if trigger is None:
            continue
        spent += MAX_SCAN_PAGES
        moment = utc_stamp(now)
        start = now if stamp is None else max(now, pull_list.parse_stamp(stamp.next_at))
        stamp = _stamp(
            at=moment,
            started_at=moment,
            pages=MAX_SCAN_PAGES,
            walked_at=moment,
            next_at=utc_stamp(start + timedelta(seconds=MAX_SCAN_PAGES * SCAN_POINT_GAP_S)),
        )
    assert spent <= 3600 / SCAN_POINT_GAP_S + MAX_SCAN_PAGES


def _seeded(repository: ListedRepository, heads: Mapping[int, str]) -> None:
    items = []
    for number, head in heads.items():
        item = generated_item(number)
        item["head"] = {**item["head"], "sha": head}
        items.append(item)
    seed_catalog(repository, items)


def test_a_list_ask_starts_the_scan_once_the_catalog_holds_rows_and_never_fails(
    repository: ListedRepository, monkeypatch: pytest.MonkeyPatch, clock: list[datetime]
) -> None:
    async def ask(**kwargs: Any) -> list[str]:
        coordinator = RefreshCoordinator()
        try:
            reader = kwargs.pop("reader", f"gh:{READER}")
            first = await ask_status_scan(
                repository, coordinator, reader=reader, git_dir=None, **kwargs
            )
            second = await ask_status_scan(
                repository, coordinator, reader=reader, git_dir=None, **kwargs
            )
            await coordinator.drain(timeout_s=5)
            return [first, second]
        finally:
            await coordinator.aclose()

    assert asyncio.run(ask(reader=None)) == ["not_due", "not_due"]
    _seeded(repository, {10: HEAD})
    _GitHub(monkeypatch, _page([_node(10)]))
    assert asyncio.run(ask()) == ["started", "joined"]
    stamp = read_scan_stamp(repository.home, repository.slug)
    assert stamp is not None and stamp.trigger == "periodic" and stamp.reader == f"gh:{READER}"
    assert asyncio.run(ask()) == ["not_due", "not_due"]

    def broken(_repository: ListedRepository) -> ScanStamp | None:
        raise OSError("the cache went away")

    monkeypatch.setattr(pull_status_scan, "_scan_inputs", broken)
    assert asyncio.run(ask(retry=True)) == ["not_due", "not_due"]


@needs_git
def test_a_fetch_that_moves_a_scanned_base_asks_once(tmp_path: Path) -> None:
    store = tmp_path / "store.git"
    subprocess.run(["git", "init", "--bare", "-q", str(store)], check=True)
    env = {**os.environ, "GIT_DIR": str(store)}

    def commit(message: str) -> str:
        tree = subprocess.run(
            ["git", "mktree"], input="", capture_output=True, text=True, env=env, check=True
        ).stdout.strip()
        return subprocess.run(
            ["git", "commit-tree", tree, "-m", message],
            capture_output=True,
            text=True,
            env={
                **env,
                "GIT_AUTHOR_NAME": "a",
                "GIT_AUTHOR_EMAIL": "a@example.com",
                "GIT_COMMITTER_NAME": "a",
                "GIT_COMMITTER_EMAIL": "a@example.com",
            },
            check=True,
        ).stdout.strip()

    first, second = commit("one"), commit("two")
    subprocess.run(["git", "update-ref", "refs/remotes/origin/topic", first], env=env, check=True)
    stamp = _stamp(bases={"topic": first})

    async def looks() -> list[bool]:
        scan = pull_status_scan.StatusScan(key="test")
        seen = [await scan.base_moved(stamp, store), await scan.base_moved(stamp, store)]
        await asyncio.to_thread(
            subprocess.run,
            ["git", "update-ref", "refs/remotes/origin/topic", second],
            env=env,
            check=True,
        )
        seen += [await scan.base_moved(stamp, store), await scan.base_moved(stamp, store)]
        # The next scan reads the base GitHub has, which the mirror now has too.
        seen.append(await scan.base_moved(_stamp(bases={"topic": second}), store))
        return seen

    assert asyncio.run(looks()) == [False, False, True, False, False]


# ── The route ───────────────────────────────────────────────────


def test_each_named_pull_request_has_its_status_and_verdict_or_says_why_not(
    repository: ListedRepository,
) -> None:
    _seeded(repository, {5: HEAD, 6: HEAD, 7: HEAD})
    for number, head in ((5, HEAD), (7, OTHER_HEAD), (11, HEAD)):
        write_pull_status(repository, _status("2026-11-26T12:00:01Z", number=number, head=head))
    envelope = pull_statuses(repository, (11, 5, 6, 7), scanning=False)
    assert [(row["number"], row["state"], row["reason"]) for row in envelope["rows"]] == [
        (11, "absent", "not_cached"),
        (5, "status", None),
        (6, "absent", "no_status"),
        (7, "absent", "other_head"),
    ]
    absent = [row for row in envelope["rows"] if row["state"] == "absent"]
    assert all(row["status"] is None and row["readiness"] is None for row in absent)
    row = envelope["rows"][1]
    assert row["status"] is not None and row["status"]["head"] == row["head"] == HEAD
    assert row["readiness"] is not None and row["readiness"]["head"] == HEAD
    before = envelope_etag(envelope)
    write_pull_status(
        repository,
        _status("2026-11-26T12:00:09Z", number=5, by="scan", summary="one pending"),
    )
    after = pull_statuses(repository, (11, 5, 6, 7), scanning=False)
    assert after["rows"][1]["readiness"]["verdict"] == "checks_pending"  # pyright: ignore[reportOptionalSubscript]
    assert envelope_etag(after) != before


def test_a_closed_or_merged_pull_requests_status_has_no_verdict(
    repository: ListedRepository,
) -> None:
    closed: dict[str, Any] = {
        **generated_item(9),
        "state": "closed",
        "closed_at": "2026-09-17T11:00:00Z",
    }
    merged: dict[str, Any] = {
        **generated_item(8),
        "state": "closed",
        "closed_at": "2026-09-17T11:00:00Z",
        "merged_at": "2026-09-17T11:00:00Z",
    }
    for item in (closed, merged):
        item["head"] = {**item["head"], "sha": HEAD}
    seed_catalog(repository, [closed, merged])
    for number in (8, 9):
        write_pull_status(repository, _status("2026-11-26T12:00:01Z", number=number))
    rows = pull_statuses(repository, (8, 9), scanning=True)["rows"]
    assert [(row["lifecycle"], row["state"], row["readiness"]) for row in rows] == [
        ("merged", "status", None),
        ("closed", "status", None),
    ]


def test_a_failed_scan_is_answered_beside_what_it_kept(
    repository: ListedRepository, monkeypatch: pytest.MonkeyPatch, clock: list[datetime]
) -> None:
    _seeded(repository, {10: HEAD})
    _GitHub(monkeypatch, _page([_node(10, mergeable="UNKNOWN")]))
    _scan(repository)
    _GitHub(monkeypatch, PullDataError("rate_limited", "GitHub's API rate limit is exhausted"))
    _scan(repository, previous=read_scan_stamp(repository.home, repository.slug))
    envelope = pull_statuses(repository, (10,), scanning=False)
    assert envelope["scan"] is not None and envelope["scan"]["outcome"] == "rate_limited"
    assert envelope["rows"][0]["state"] == "status"
    assert envelope["rows"][0]["readiness"]["verdict"] == "checking"  # pyright: ignore[reportOptionalSubscript]
