"""The Pulls tab's scan of every open pull request's status, and how its statuses are kept.

The scan is :mod:`metabrowser.builtin_plugins.github.pull_status_scan`, given GitHub's pages
here by a stand-in for ``gh_graphql``; the route that answers what it kept is
:mod:`.pull_statuses_route`. A scan and a page's read write one store, so what they keep of
each other is held as invariants over every order of generated sequences of observations
(:func:`~.pull_status.kept_observation`), and so is what the page is then shown and asks
for (:attr:`~.pull_status_store.KeptStatus.listed_checks`, :func:`~.pull_freshness.listing_missing`).
What the scans spend is measured by driving them for an hour of a visible tab's asks.
``tests/test_cli_github_pull_statuses_golden.py`` drives the scan and the route through
``metab --api``.
"""

from __future__ import annotations

import asyncio
import copy
import errno
import itertools
import logging
import os
import random
import subprocess
from collections.abc import Iterable, Mapping, Sequence
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
from metabrowser.builtin_plugins.github.pull_list_probe import LIST_PROBE_S
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
    SCANS_POINTS_PER_HOUR,
    ScanStamp,
    ask_status_scan,
    read_scan_stamp,
    run_scan,
    scan_due,
    status_scan,
    write_scan_stamp,
)
from metabrowser.builtin_plugins.github.pull_status_store import (
    KeptStatus,
    kept_status,
    write_pull_checks,
)
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
    base_ref: str = "main",
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
        base_ref=base_ref,
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
    """Every observation of one pull request at two heads against one base and at one head
    retargeted, at three moments, by both readers, with two summaries of its checks."""

    return [
        _status(f"2026-11-26T12:00:0{second}Z", head=head, base_ref=base, by=by, summary=summary)
        for (head, base), second, by, summary in itertools.product(
            ((HEAD, "main"), (OTHER_HEAD, "main"), (HEAD, "release")),
            (1, 2, 3),
            ("read", "scan"),
            ("one passing", "one pending"),
        )
    ]


def _listing(status: PullStatus) -> tuple[str | None, int | None, int | None]:
    checks = status.checks
    return checks.listed_at, checks.required_failing, checks.required_pending


def _bare(status: PullStatus) -> PullStatus:
    """*status* as it was observed, without what keeping it beside others gave it."""

    return status.model_copy(
        update={
            "checks": status.checks.model_copy(
                update={
                    "listed_at": None,
                    "required_failing": None,
                    "required_pending": None,
                    "moved_at": None,
                }
            )
        }
    )


def _fold(observations: Iterable[PullStatus]) -> PullStatus | None:
    kept: PullStatus | None = None
    for observation in observations:
        kept = kept_observation(kept, observation)
    return kept


def _sets() -> list[tuple[PullStatus, ...]]:
    """Every three of the observations, and a fixed sample of larger sets."""

    observations = _observations()
    sample = random.Random(20261126)
    larger = [tuple(sample.sample(observations, size)) for size in (4, 5) for _ in range(60)]
    return [*itertools.combinations(observations, 3), *larger]


# ── Keeping a scan beside a read ────────────────────────────────


def _holds_for(result: PullStatus, observations: Sequence[PullStatus]) -> None:
    """What the status kept of *observations* must be, whatever order they came in."""

    newest = max(each.observed_at for each in observations)
    latest = [each for each in observations if each.observed_at == newest]
    # Everything but the list behind the checks is the newest observation's, and a read's
    # when one read then.
    assert any(_bare(result) == _bare(each) for each in latest)
    assert result.observed_by == "read" or all(each.observed_by == "scan" for each in latest)
    listed = result.checks.listed_at
    if listed is not None:
        # A list is a read's of the same checks: never another head's, base's, or counts'...
        assert any(
            each.checks.listed_at == listed
            and same_checks(each, result)
            and _listing(each) == _listing(result)
            for each in observations
        )
        # ...and nothing observed since summarized them otherwise.
        assert all(same_checks(each, result) for each in observations if each.observed_at >= listed)
    for read in observations:
        since = read.checks.listed_at
        if since is not None and all(
            same_checks(each, result) for each in observations if each.observed_at >= since
        ):
            # A scan that finds a read's checks as the read left them takes nothing away.
            assert listed is not None and listed >= since


def test_keeping_observations_does_not_depend_on_the_order_they_are_written_in() -> None:
    """Every order of every three observations, ties among them, and of larger samples, is
    kept as one status, which is the newest with the latest list that still counts it."""

    for observations in _sets():
        kept = [_fold(order) for order in itertools.permutations(observations)]
        assert all(each == kept[0] for each in kept)
        assert kept[0] is not None
        _holds_for(kept[0], observations)


def test_a_retargeted_pull_request_loses_the_required_counts_of_its_old_base() -> None:
    """Which checks are required is the base's rules' call, so the same head and checks
    against another base count no list of the old one."""

    read = _status("2026-11-26T12:00:01Z", summary="one pending")
    assert _listing(read) == ("2026-11-26T12:00:01Z", 0, 1)
    retargeted = _status(
        "2026-11-26T12:00:05Z", by="scan", base_ref="release", summary="one pending"
    )
    for kept in (kept_observation(read, retargeted), kept_observation(retargeted, read)):
        assert kept.base_ref == "release" and _listing(kept) == (None, None, None)


@pytest.fixture
def repository(tmp_path: Path) -> ListedRepository:
    home = tmp_path / "home"
    build_empty_home(home)
    _stage_and_publish_source(home, SOURCE, opened=False)
    return ListedRepository(home, SOURCE.slug, "octo", "demo")


def _keep(repository: ListedRepository, observation: PullStatus) -> None:
    """Keep *observation* as its reader does: a read keeps its status and then its list."""

    write_pull_status(repository, observation)
    listed = observation.checks.listed_at
    if observation.observed_by == "read" and listed is not None:
        checks = PullChecks(
            number=observation.number, head=observation.head, observed_at=listed, items=()
        )
        write_pull_checks(repository.home, repository.slug, checks)


def test_the_store_keeps_what_the_rule_keeps_and_the_list_its_status_counts(
    repository: ListedRepository,
) -> None:
    """Written in every order, the store keeps the rule's status, and the checks file is
    the list its ``listed_at`` names whenever it names one."""

    home, slug = repository.home, repository.slug
    sets = list(itertools.combinations(_observations(), 3))[::331]
    orders = [order for each in sets for order in itertools.permutations(each)]
    for number, order in enumerate(orders, start=1):
        numbered = [each.model_copy(update={"number": number}) for each in order]
        for each in numbered:
            _keep(repository, each)
        kept = kept_status(home, slug, number)
        assert kept.status is not None and kept.status == _fold(numbered)
        assert (kept.listed_checks is not None) == (kept.status.checks.listed_at is not None)


def test_a_read_that_ends_late_is_still_the_list_its_status_counts(
    repository: ListedRepository,
) -> None:
    """A read that asked before a scan and ended after it gives the status a later list of
    the same checks than the one the scan kept, and the page is shown it."""

    home, slug = repository.home, repository.slug
    early = _status("2026-11-26T12:00:01Z")
    late = _status("2026-11-26T12:00:03Z")
    scan = _status("2026-11-26T12:00:05Z", by="scan")
    for each in (early, scan, late):
        _keep(repository, each)
    kept = kept_status(home, slug, 5)
    assert kept.status is not None and kept.status.observed_by == "scan"
    assert _listing(kept.status) == _listing(late)
    assert kept.listed_checks is not None and kept.listed_checks.observed_at == late.observed_at


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
    for moved in (
        _status("2026-11-26T12:00:09Z", by="scan", summary="one pending"),
        _status("2026-11-26T12:00:12Z", by="scan", head=OTHER_HEAD),
        _status("2026-11-26T12:00:15Z", by="scan", head=OTHER_HEAD, base_ref="release"),
    ):
        assert write_pull_status(repository, moved)
        kept = read_pull_status(home, slug, 5)
        assert kept is not None and _bare(kept) == moved and _listing(kept) == (None, None, None)


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


class _Walks:
    """A stand-in for ``gh_graphql`` that answers every walk alike, however many there are.

    Each walk is *pages* pages of :data:`SCAN_ROWS` open pull requests, newest first,
    against ``main`` at *base*, GitHub's ``baseRefOid``, which is each pull request's as of
    its own last sync. With *unknown*, the first of every page is an answer GitHub had not
    finished computing, so every walk is read once more. Each page costs one point.
    """

    def __init__(
        self,
        monkeypatch: pytest.MonkeyPatch,
        *,
        pages: int = 1,
        unknown: bool = False,
        base: str = BASE,
    ) -> None:
        self.cursors: list[str | None] = []

        async def answer(
            query: str, variables: Mapping[str, Any], *, now: datetime | None = None
        ) -> dict[str, Any]:
            assert query.startswith("query PullStatuses(")
            cursor = variables.get("cursor")
            self.cursors.append(cursor)
            index = 0 if cursor is None else int(cursor.removeprefix("p"))
            nodes = [
                _node(
                    1000 - index * SCAN_ROWS - row,
                    base=base,
                    **(
                        {"mergeable": "UNKNOWN", "merge_state": "UNKNOWN"}
                        if unknown and not row
                        else {}
                    ),
                )
                for row in range(SCAN_ROWS)
            ]
            return _page(nodes, cursor=f"p{index + 1}" if index + 1 < pages else None)

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
    # It names the pull requests it read, and, with no mirror to look at, no base's tip.
    assert set(stamp.walked_numbers) == set(range(1, 101)) and stamp.bases == {}
    assert stamp.walked_at == utc_stamp(NOW)
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
    assert (settled.walked_at, settled.walked_numbers) == (walked.walked_at, walked.walked_numbers)
    kept = read_pull_status(repository.home, repository.slug, 9)
    assert kept is not None and kept.conflicts == "mergeable"


def test_a_page_github_did_not_send_as_documented_is_refused_and_a_row_left_out(
    repository: ListedRepository, monkeypatch: pytest.MonkeyPatch, clock: list[datetime]
) -> None:
    odd = _node(9) | {"mergeable": "MAYBE"}
    _GitHub(monkeypatch, _page([_node(10), odd]))
    left_out = _scan(repository)
    assert left_out.rows == 1 and left_out.walked_numbers == (10,)
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
    # What the next scan needs of the last whole walk is kept through a failure.
    assert (failed.walked_at, failed.walked_numbers, failed.bases) == (
        first.walked_at,
        first.walked_numbers,
        first.bases,
    )
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
    # The last scan's own rate limit holds a reader's Refresh, as this process's does: a
    # restart forgets the one and not the other.
    reset = NOW + timedelta(hours=1)
    limited = _stamp(outcome="rate_limited", reset_at=utc_stamp(reset))
    assert scan_due(limited, now=periodic, retry=True) is None
    assert scan_due(limited, now=reset, retry=True) == "retry"
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


async def _quiet(coordinator: RefreshCoordinator, source: str) -> None:
    """Wait for the scan and any look at the mirror, which may start the scan itself."""

    scan = status_scan(coordinator, source)
    while coordinator.running(scan.look_key) or coordinator.running(scan.key):
        await coordinator.drain(timeout_s=5)


@pytest.mark.parametrize("writable", [True, False], ids=["kept", "unwritable"])
def test_an_hour_of_asks_spends_what_the_spacing_allows(
    repository: ListedRepository,
    monkeypatch: pytest.MonkeyPatch,
    clock: list[datetime],
    writable: bool,
) -> None:
    """A visible tab asks every ``LIST_PROBE_S`` for an hour, its probe finding a change on
    every ask, each walk of the most pages leaving answers to read once more, and a reader
    asking for Refresh every 20 minutes. The points every scan spends come to at most
    ``SCANS_POINTS_PER_HOUR``, and what the hour's edge and the reader's Refreshes borrow,
    whether or not the cache can keep the stamp."""

    _seeded(repository, {1000: HEAD})
    github = _Walks(monkeypatch, pages=MAX_SCAN_PAGES, unknown=True)
    if not writable:

        def unwritable(*_args: object, **_kwargs: object) -> None:
            raise OSError(errno.ENOSPC, "No space left on device")

        monkeypatch.setattr(pull_status_scan, "write_scan_stamp", unwritable)
    refreshes = range(0, 3600, 1200)
    triggers: list[str] = []

    async def hour() -> None:
        coordinator = RefreshCoordinator()
        last: ScanStamp | None = None
        try:
            for second in range(0, 3600, round(LIST_PROBE_S)):
                clock[0] = NOW + timedelta(seconds=second)
                await ask_status_scan(
                    repository,
                    coordinator,
                    reader=f"gh:{READER}",
                    git_dir=None,
                    changed=True,
                    retry=second in refreshes,
                )
                await _quiet(coordinator, repository.source)
                left = status_scan(coordinator, repository.source).last
                if left is not None and left is not last:
                    triggers.append(left.trigger)
                    last = left
        finally:
            await coordinator.aclose()

    asyncio.run(hour())
    assert {"retry", "changed", "settle"} <= set(triggers)
    # Every page is a point. A walk of the most pages and its settle re-read at the hour's
    # edge borrow from the next hour, as each Refresh's walk and re-read do.
    borrowed = 2 * MAX_SCAN_PAGES * (1 + len(refreshes))
    assert len(github.cursors) <= SCANS_POINTS_PER_HOUR + borrowed
    stamp = read_scan_stamp(repository.home, repository.slug)
    assert (stamp is not None) == writable


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


class _Mirror:
    """A bare store standing in for a repository's mirror, whose base branches a test moves."""

    def __init__(self, path: Path) -> None:
        self.path = path
        subprocess.run(["git", "init", "--bare", "-q", str(path)], check=True)
        self._env = {
            **os.environ,
            "GIT_DIR": str(path),
            "GIT_AUTHOR_NAME": "a",
            "GIT_AUTHOR_EMAIL": "a@example.com",
            "GIT_COMMITTER_NAME": "a",
            "GIT_COMMITTER_EMAIL": "a@example.com",
        }

    def _git(self, *args: str) -> str:
        done = subprocess.run(
            ["git", *args], input="", capture_output=True, text=True, env=self._env, check=True
        )
        return done.stdout.strip()

    def commit(self, message: str) -> str:
        return self._git("commit-tree", self._git("mktree"), "-m", message)

    def fetch(self, branch: str, commit: str) -> None:
        """A fetch that moves *branch* to *commit*."""

        self._git("update-ref", f"refs/remotes/origin/{branch}", commit)

    def pack(self) -> None:
        """A fetch that moves nothing but how the refs are kept, as ``git gc`` does."""

        self._git("pack-refs", "--all", "--prune")


@needs_git
def test_a_fetch_starts_a_scan_only_when_it_moved_a_base_since_the_last_walk(
    repository: ListedRepository,
    monkeypatch: pytest.MonkeyPatch,
    clock: list[datetime],
    tmp_path: Path,
) -> None:
    """GitHub's ``baseRefOid`` is each pull request's own, as of its last sync, so the scan
    compares the mirror with the mirror: its tip of each base as the last walk started."""

    mirror = _Mirror(tmp_path / "store.git")
    one, two, three = (mirror.commit(message) for message in ("one", "two", "three"))
    mirror.fetch("main", one)
    _seeded(repository, {10: HEAD})
    # Every pull request GitHub lists targets main at a commit the mirror never had.
    github = _Walks(monkeypatch, base=MOVED_BASE)
    asked: list[tuple[str, int, str | None]] = []

    def step() -> None:
        clock[0] += timedelta(seconds=SCAN_POINT_GAP_S + 1)

    async def ask(coordinator: RefreshCoordinator, *, retry: bool = False) -> None:
        pages = len(github.cursors)
        answer = await ask_status_scan(
            repository, coordinator, reader=f"gh:{READER}", git_dir=mirror.path, retry=retry
        )
        await _quiet(coordinator, repository.source)
        stamp = read_scan_stamp(repository.home, repository.slug)
        asked.append((answer, len(github.cursors) - pages, stamp.trigger if stamp else None))

    async def scenario() -> None:
        here, elsewhere, restarted = (
            RefreshCoordinator(),
            RefreshCoordinator(),
            RefreshCoordinator(),
        )
        try:
            await ask(here, retry=True)
            step()
            await ask(here)
            # A fetch moves main, and another process's walk starts after it.
            mirror.fetch("main", two)
            await ask(elsewhere, retry=True)
            step()
            mirror.pack()
            await ask(here)
            # A fetch moves main past the last walk; this process restarts before it asks.
            mirror.fetch("main", three)
            await ask(restarted)
            await ask(restarted)
        finally:
            for each in (here, elsewhere, restarted):
                await each.aclose()

    asyncio.run(scenario())
    assert asked == [
        ("started", 1, "retry"),
        # Nothing moved since the walk started, though GitHub reported another base.
        ("not_due", 0, "retry"),
        ("started", 1, "retry"),
        # The fetch moved nothing since the last walk, which started after it.
        ("not_due", 0, "retry"),
        # Moved since the last walk: the look starts exactly one scan, after the answer.
        ("not_due", 1, "base_moved"),
        ("not_due", 0, "base_moved"),
    ]
    stamp = read_scan_stamp(repository.home, repository.slug)
    assert stamp is not None and stamp.bases == {"main": three}


def test_a_mirror_git_cannot_read_moves_nothing_and_holds_no_scan(
    repository: ListedRepository,
    monkeypatch: pytest.MonkeyPatch,
    clock: list[datetime],
    tmp_path: Path,
    caplog: pytest.LogCaptureFixture,
) -> None:
    _seeded(repository, {10: HEAD})
    write_scan_stamp(repository.home, repository.slug, _stamp())
    broken = tmp_path / "not-a-store"
    broken.mkdir()
    github = _Walks(monkeypatch)
    clock[0] = NOW + timedelta(seconds=SCAN_POINT_GAP_S + 1)

    async def scenario() -> list[str]:
        coordinator = RefreshCoordinator()
        answers: list[str] = []
        try:
            for retry in (False, False, False, True):
                answers.append(
                    await ask_status_scan(
                        repository,
                        coordinator,
                        reader=f"gh:{READER}",
                        git_dir=broken,
                        retry=retry,
                    )
                )
                await _quiet(coordinator, repository.source)
            return answers
        finally:
            await coordinator.aclose()

    with caplog.at_level(logging.WARNING, logger=pull_status_scan.__name__):
        answers = asyncio.run(scenario())
    # A reader's Refresh is decided before the mirror is looked at, and is read.
    assert answers == ["not_due", "not_due", "not_due", "started"]
    assert len(github.cursors) == 1
    # Said once, not on every ask, and never as the ask's own failure.
    assert [record.levelno for record in caplog.records] == [logging.WARNING]
    assert "mirror" in caplog.records[0].getMessage()


def test_the_ask_never_waits_on_git(
    repository: ListedRepository,
    monkeypatch: pytest.MonkeyPatch,
    clock: list[datetime],
    tmp_path: Path,
) -> None:
    """A look at the mirror that Git is slow to answer holds neither the list's answer
    nor the scan's start; it runs as a job of its own."""

    from metabrowser.cache import resolve

    _seeded(repository, {10: HEAD})
    write_scan_stamp(repository.home, repository.slug, _stamp())
    store = tmp_path / "store.git"
    store.mkdir()
    clock[0] = NOW + timedelta(seconds=SCAN_POINT_GAP_S + 1)
    released: list[asyncio.Event] = []

    async def slow(_target: object, refs: Sequence[str]) -> dict[str, str]:
        await released[0].wait()
        return dict.fromkeys(refs, BASE)

    monkeypatch.setattr(resolve, "ref_tips", slow)

    async def scenario() -> tuple[str, bool]:
        released.append(asyncio.Event())
        coordinator = RefreshCoordinator()
        try:
            answer = await asyncio.wait_for(
                ask_status_scan(repository, coordinator, reader=f"gh:{READER}", git_dir=store),
                timeout=2,
            )
            looking = coordinator.running(status_scan(coordinator, repository.source).look_key)
            released[0].set()
            await _quiet(coordinator, repository.source)
            return answer, looking
        finally:
            await coordinator.aclose()

    assert asyncio.run(scenario()) == ("not_due", True)


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


def test_a_scanned_status_the_last_walk_did_not_read_is_answered_as_not_scanned(
    repository: ListedRepository,
) -> None:
    """A status the scan kept before the last whole walk, of a pull request that walk did
    not read, has nothing keeping it current; a read's, and any status from after the walk
    started, is answered as kept."""

    walked_at = "2026-11-26T12:00:05Z"
    cases = list(
        itertools.product(
            ("read", "scan"),
            ("2026-11-26T12:00:01Z", walked_at, "2026-11-26T12:00:09Z"),
            (True, False),
        )
    )
    numbers = tuple(range(1, len(cases) + 1))
    _seeded(repository, dict.fromkeys(numbers, HEAD))
    for number, (by, observed_at, _read) in zip(numbers, cases, strict=True):
        write_pull_status(repository, _status(observed_at, number=number, by=by))
    walked = tuple(number for number, case in zip(numbers, cases, strict=True) if case[2])
    for stamp in (None, _stamp(walked_at=None), _stamp(walked_at=walked_at, walked_numbers=walked)):
        if stamp is not None:
            write_scan_stamp(repository.home, repository.slug, stamp)
        rows = pull_statuses(repository, numbers, scanning=False)["rows"]
        for row, (by, observed_at, read) in zip(rows, cases, strict=True):
            unscanned = (
                stamp is not None
                and stamp.walked_at is not None
                and by == "scan"
                and observed_at < stamp.walked_at
                and not read
            )
            assert row["reason"] == ("not_scanned" if unscanned else None)
            assert (row["readiness"] is None) == unscanned


def test_a_pull_request_that_falls_out_of_the_walk_is_not_scanned_until_read(
    repository: ListedRepository, monkeypatch: pytest.MonkeyPatch, clock: list[datetime]
) -> None:
    _seeded(repository, {10: HEAD, 11: HEAD})
    _GitHub(monkeypatch, _page([_node(11), _node(10)]))
    first = _scan(repository)
    clock[0] = NOW + timedelta(seconds=FULL_REFRESH_S + 1)
    # GitHub no longer lists #10 among the newest open pull requests.
    _GitHub(monkeypatch, _page([_node(11)]))
    _scan(repository, previous=first)
    rows = pull_statuses(repository, (11, 10), scanning=False)["rows"]
    assert [(row["state"], row["reason"]) for row in rows] == [
        ("status", None),
        ("absent", "not_scanned"),
    ]
    # The page's own read of it is answered as it is.
    write_pull_status(repository, _status(utc_stamp(clock[0]), number=10))
    rows = pull_statuses(repository, (10,), scanning=False)["rows"]
    assert (rows[0]["state"], rows[0]["reason"]) == ("status", None)


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
