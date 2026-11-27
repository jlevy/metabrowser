"""A cached record checked against the catalog's row: current, changed, checks, or unverified.

The route transcripts show the envelope fields; these pin the verdict table, pending
checks and mergeability as the kept status says them, and the held state's due rules,
including its loop guard, the status an open pull request reads once a window and a
record without one reads at once, and a cancelled attempt.
"""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any, Literal

import pytest

from metabrowser.builtin_plugins.github import gh_budget, pulls, served_pull
from metabrowser.builtin_plugins.github.pull_catalog import CatalogState
from metabrowser.builtin_plugins.github.pull_freshness import (
    NO_CHECKS_GRACE_S,
    SCAN_GRACE_S,
    RecordFreshness,
    checks_pending,
    record_freshness,
)
from metabrowser.builtin_plugins.github.pull_list import ListedRepository, PullListRow
from metabrowser.builtin_plugins.github.pull_record import (
    PULL_RECORD_PROJECTION,
    PULL_RECORD_SCHEMA,
    PullRecord,
)
from metabrowser.builtin_plugins.github.pull_route import (
    judged_readiness,
    pull_state,
    shown_checks,
)
from metabrowser.builtin_plugins.github.pull_status import (
    BUCKETS,
    CheckItem,
    PullChecks,
    PullStatus,
    kept_observation,
)
from metabrowser.builtin_plugins.github.pull_status_store import CheckProbes, KeptStatus
from metabrowser.builtin_plugins.github.served_pull import (
    ATTENDED_PROBE_S,
    CHECKS_PROBE_S,
    FULL_REFRESH_S,
    PROBE_FLOOR_S,
    ServedPull,
    ServedPulls,
)
from metabrowser.cli.show_cli import _describe_pull  # pyright: ignore[reportPrivateUsage]
from metabrowser.mirror_refresh import FRESHNESS_WINDOW_S, RefreshCoordinator

SOURCE = "https://github.com/octo/demo"
READER = "gh:octo-reader"
HEAD = "a" * 40
NEWER_HEAD = "b" * 40
NOW = datetime(2026, 9, 17, 12, 0, tzinfo=UTC)
WINDOW = timedelta(seconds=FRESHNESS_WINDOW_S)


def _stamp(moment: datetime) -> str:
    return moment.strftime("%Y-%m-%dT%H:%M:%SZ")


def _record(
    *,
    updated: datetime = NOW - timedelta(hours=3),
    fetched: datetime = NOW - timedelta(hours=2),
    head: str = HEAD,
    state: str = "open",
    reader: str = READER,
    projection: int = PULL_RECORD_PROJECTION,
) -> PullRecord:
    side: dict[str, Any] = {"ref": "topic", "sha": "c" * 40, "repository": "octo/demo"}
    return PullRecord.model_validate(
        {
            "schema_version": PULL_RECORD_SCHEMA,
            "projection_version": projection,
            "source": SOURCE,
            "number": 7,
            "fetched_at": _stamp(fetched),
            "reader": reader,
            "etags": {},
            "pull": {
                "number": 7,
                "title": "Count to two",
                "body": "",
                "body_truncated": False,
                "state": state,
                "draft": False,
                "merged": False,
                "merged_by": None,
                "commits": 1,
                "merge_commit_sha": None,
                "labels": [],
                "author": "octo",
                "created_at": _stamp(updated - timedelta(days=1)),
                "updated_at": _stamp(updated),
                "merged_at": None,
                "closed_at": None if state == "open" else _stamp(updated),
                "base": side,
                "head": {**side, "ref": "work", "sha": head},
                "html_url": f"{SOURCE}/pull/7",
            },
            "issue_comments": [],
            "reviews": [],
            "review_comments": [],
            "comparison": None,
            "truncated": {
                "issue_comments": False,
                "reviews": False,
                "review_comments": False,
                "text": False,
            },
            "unavailable": {},
        }
    )


def _status(
    record: PullRecord,
    *,
    observed: datetime | None = None,
    head: str | None = None,
    rollup: str = "success",
    counts: dict[str, int] | None = None,
    conflicts: str = "mergeable",
    merge_state: str = "clean",
    by: str = "read",
) -> PullStatus:
    """A kept status of *record*'s head, observed as the read after it kept it, by default
    with one passing check and nothing for GitHub still to compute. A read lists its
    checks; *by* ``scan`` lists none (``listed_at``)."""

    stamp = record.fetched_at if observed is None else _stamp(observed)
    tallies: dict[str, int] = dict.fromkeys(BUCKETS, 0)
    if rollup != "none":
        tallies.update({"pass": 1} if counts is None else counts)
    return PullStatus.model_validate(
        {
            "number": record.number,
            "head": head or record.pull.head.sha,
            "base_ref": record.pull.base.ref,
            "observed_at": stamp,
            "observed_by": by,
            "conflicts": conflicts,
            "merge_state": merge_state,
            "checks": {
                "state": rollup,
                "counts": tallies,
                "listed_at": stamp if by == "read" else None,
            },
        }
    )


def _verdict(
    record: PullRecord,
    catalog: CatalogState | None,
    row: PullListRow | None,
    *,
    status: PullStatus | None | Literal["as read"] = "as read",
    now: datetime = NOW,
    **kwargs: Any,
) -> RecordFreshness:
    """The verdict on *record*, with the status its own read kept unless *status* says."""

    kept = _status(record) if status == "as read" else status
    return record_freshness(record, catalog, row, status=kept, now=now, **kwargs)


def _catalog(
    *,
    fetched: datetime = NOW - timedelta(seconds=20),
    published: datetime | None = None,
    reader: str = READER,
    source: str = SOURCE,
) -> CatalogState:
    return CatalogState(
        projection_version=2,
        source=source,
        repository_id="R_demo",
        reader=reader,
        fetched_at=_stamp(fetched),
        count_at=_stamp(published or fetched),
    )


def _row(*, updated: datetime = NOW - timedelta(hours=3), head: str | None = HEAD) -> PullListRow:
    return PullListRow(
        number=7,
        title="Count to two",
        state="open",
        draft=False,
        merged_at=None,
        author="octo",
        created_at=_stamp(updated - timedelta(days=1)),
        updated_at=_stamp(updated),
        closed_at=None,
        base_ref="topic",
        head_ref="work",
        head_repository="octo/demo",
        labels=(),
        head_oid=head,
    )


def test_a_recent_scan_vouches_for_an_old_closed_record_it_has_not_seen_change() -> None:
    record = _record(state="closed")
    verdict = _verdict(record, _catalog(), _row(), now=NOW)
    assert verdict.verdict == "current" and verdict.verified_by == "catalog"
    assert verdict.verified_at == _stamp(NOW - timedelta(seconds=20))
    assert not verdict.head_moved and verdict.changed_row is None
    assert pull_state(record, now=NOW, freshness=verdict) == ("current", None)
    # Without the verdict the same record is two hours past the window.
    assert pull_state(record, now=NOW) == ("stale", None)


@pytest.mark.parametrize(
    "changes",
    [{"rollup": "none"}, {}, {"conflicts": "conflicting", "merge_state": "dirty"}],
    ids=["no checks registered yet", "completed checks a re-run restarts", "a base that moved"],
)
def test_an_open_records_status_past_the_window_is_read_again(changes: dict[str, Any]) -> None:
    """Review A1: ``updated_at`` vouches for the conversation and head, not for the status.

    A check and the mergeability move without it: CI that registers after the status was
    read, a re-run of settled checks, a conflict a moved base made. The record holds none
    of them, so it is current; its status, observed longer ago than the window, is due on
    its own (``checks``), and one observed within it is not.
    """

    record = _record()
    old = _status(record, **changes)
    verdict = _verdict(record, _catalog(), _row(), status=old)
    assert (verdict.verdict, verdict.verified_by, verdict.head_moved) == (
        "checks",
        "catalog",
        False,
    )
    assert verdict.verified_at == _stamp(NOW - timedelta(seconds=20))
    assert not verdict.status_missing
    assert pull_state(record, now=NOW, freshness=verdict) == ("current", None)
    young = _status(record, observed=NOW - WINDOW + timedelta(seconds=1), **changes)
    assert _verdict(record, _catalog(), _row(), status=young).verdict == "current"
    # The record's age is not what decides: a young record whose status is a window old.
    fresh = _record(fetched=NOW - timedelta(seconds=1))
    late = _status(fresh, observed=NOW - WINDOW - timedelta(seconds=1), **changes)
    assert _verdict(fresh, _catalog(), _row(), status=late).verdict == "checks"


@pytest.mark.parametrize(
    "kept",
    [None, "another head"],
    ids=["no status", "a status of another head"],
)
def test_a_record_with_no_status_of_its_head_says_so_whatever_the_verdict(
    kept: str | None,
) -> None:
    """A prefetched record reads no status, and a read that failed after a push leaves the
    one before it: either way no status describes the record's head."""

    record = _record(fetched=NOW - timedelta(seconds=5))
    status = None if kept is None else _status(record, head=NEWER_HEAD)
    vouched = _verdict(record, _catalog(), _row(), status=status)
    assert (vouched.verdict, vouched.status_missing) == ("checks", True)
    assert pull_state(record, now=NOW, freshness=vouched) == ("current", None)
    clock = _verdict(record, None, None, status=status)
    assert (clock.verdict, clock.status_missing) == ("unverified", True)
    closed = _record(state="closed", fetched=NOW - timedelta(seconds=5))
    other = None if kept is None else _status(closed, head=NEWER_HEAD)
    verdict = _verdict(closed, _catalog(), _row(), status=other)
    assert (verdict.verdict, verdict.status_missing) == ("current", True)
    assert not _verdict(record, _catalog(), _row()).status_missing


def test_a_status_of_the_base_before_a_retarget_is_read_again_before_anything_judges_it() -> None:
    """When the layer below a stacked pull request merges, GitHub retargets the one above at
    the merged layer's base and keeps its head; its conflicts, merge verdict, and required
    checks are then the new base's. A status observed against the old base, and the list
    it counts, describe nothing current: the record has a status read due, the verdict is
    ``checking``, the route serves none of its checks, and ``--show`` says so."""

    record = _record(fetched=NOW - timedelta(seconds=5))
    before = _status(record).model_copy(update={"base_ref": "layer-1"})
    verdict = _verdict(record, _catalog(), _row(), status=before)
    assert (verdict.verdict, verdict.status_missing, verdict.checks_pending) == (
        "checks",
        True,
        False,
    )
    failing = CheckItem(name="build", kind="run", bucket="fail", required=True)
    listed = PullChecks(number=7, head=HEAD, observed_at=before.observed_at, items=(failing,))
    kept = KeptStatus(before, listed, None)
    assert kept.listed_checks == listed
    shown = record.pull.model_dump(mode="json")
    judged = judged_readiness(shown, kept)
    assert judged is not None and (judged["verdict"], judged["requirements"]) == ("checking", [])
    assert shown_checks(shown, kept) is None
    envelope = {
        "state": "current",
        "record": record.model_dump(mode="json"),
        "readiness": judged,
        "checks": shown_checks(shown, kept),
        "status_unavailable": None,
    }
    said = _describe_pull(envelope, "checks").split()
    assert {"readiness=checking", "checks=none"} <= set(said)
    # Read again into the new base, the same head and list judge the pull request.
    after = before.model_copy(update={"base_ref": record.pull.base.ref})
    again = KeptStatus(after, listed, None)
    current = judged_readiness(shown, again)
    assert current is not None and current["verdict"] != "checking"
    assert shown_checks(shown, again) == listed.model_dump(mode="json")
    assert not _verdict(record, _catalog(), _row(), status=after).status_missing


def test_a_record_fetched_after_the_scan_is_verified_by_its_own_fetch_time() -> None:
    record = _record(fetched=NOW - timedelta(seconds=5))
    verdict = _verdict(record, _catalog(), _row(), now=NOW)
    assert verdict.verdict == "current" and verdict.verified_at == record.fetched_at


def test_a_newer_row_makes_the_record_changed_whatever_the_scan_age() -> None:
    record = _record()
    for scanned in (NOW - timedelta(seconds=5), NOW - timedelta(hours=1)):
        verdict = _verdict(
            record, _catalog(fetched=scanned), _row(updated=NOW - timedelta(minutes=30)), now=NOW
        )
        assert verdict.verdict == "changed" and not verdict.head_moved
        assert verdict.verified_by == "fetch" and verdict.verified_at == record.fetched_at
        assert verdict.changed_row == f"{_stamp(NOW - timedelta(minutes=30))} {HEAD}"
        assert pull_state(record, now=NOW, freshness=verdict) == ("stale", None)


def test_a_newer_row_with_another_head_says_the_head_moved() -> None:
    newer = _row(updated=NOW - timedelta(minutes=1), head=NEWER_HEAD)
    assert _verdict(_record(), _catalog(), newer, now=NOW).head_moved
    # A row written before the catalog read heads cannot say it moved.
    unknown = _row(updated=NOW - timedelta(minutes=1), head=None)
    verdict = _verdict(_record(), _catalog(), unknown, now=NOW)
    assert verdict.verdict == "changed" and not verdict.head_moved


def test_another_head_at_the_same_update_time_is_a_change() -> None:
    """Review A5: ``updated_at`` has whole seconds, and a push within the record's second
    leaves the times equal and the head not."""

    record = _record(state="closed")
    tie = _row(updated=NOW - timedelta(hours=3), head=NEWER_HEAD)
    verdict = _verdict(record, _catalog(), tie, now=NOW)
    assert (verdict.verdict, verdict.head_moved) == ("changed", True)
    same = _verdict(record, _catalog(), _row(updated=NOW - timedelta(hours=3)), now=NOW)
    assert same.verdict == "current"


@pytest.mark.parametrize(
    ("catalog", "row"),
    [
        (None, _row()),
        (_catalog(), None),
        (_catalog(fetched=NOW - WINDOW - timedelta(seconds=1)), _row()),
        (_catalog(reader="gh:someone-else"), _row()),
        (_catalog(source="https://github.com/octo/other"), _row()),
    ],
    ids=["no catalog", "no row", "old scan", "another reader", "another source"],
)
def test_the_clock_decides_without_a_usable_recent_scan(
    catalog: CatalogState | None, row: PullListRow | None
) -> None:
    record = _record()
    verdict = _verdict(record, catalog, row, now=NOW)
    assert verdict.verdict == "unverified" and verdict.verified_by == "fetch"
    assert verdict.verified_at == record.fetched_at
    assert pull_state(record, now=NOW, freshness=verdict) == ("stale", None)


def test_a_record_of_an_earlier_projection_is_never_vouched_for_so_it_is_refreshed_once(
    tmp_path: Path,
) -> None:
    """Review A1 of #465: an older build's record lacks what this one reads.

    A closed record of an earlier projection, which names its labels alone, read a month
    ago, with a catalog scanned twenty seconds ago and its row unchanged: the catalog says
    nothing of it, so the clock decides, and it is stale and due once a window, until a
    refresh rewrites it at this projection. A change GitHub made is still due at once, and
    a record read within the window is current by the clock.
    """

    earlier = PULL_RECORD_PROJECTION - 1
    record = _record(state="closed", fetched=NOW - timedelta(days=30), projection=earlier)
    verdict = _verdict(record, _catalog(), _row(), now=NOW)
    assert (verdict.verdict, verdict.verified_by) == ("unverified", "fetch")
    assert verdict.verified_at == record.fetched_at
    assert pull_state(record, now=NOW, freshness=verdict) == ("stale", None)
    # The same record at this projection is one the catalog vouches for.
    vouched = _record(state="closed", fetched=NOW - timedelta(days=30))
    assert _verdict(vouched, _catalog(), _row(), now=NOW).verdict == "current"
    held = _held(record, tmp_path)
    held.saw_record(record.fetched_at, freshness=verdict)
    assert held.is_stale(NOW, window_s=FRESHNESS_WINDOW_S)
    # Tried once, whether or not it succeeded, it waits a window.
    held._last_attempt = NOW - timedelta(seconds=10)  # pyright: ignore[reportPrivateUsage]
    assert not held.is_stale(NOW, window_s=FRESHNESS_WINDOW_S)
    # An open one is read in full too, not for its checks alone.
    opened = _record(fetched=NOW - timedelta(days=30), projection=earlier)
    assert _verdict(opened, _catalog(), _row(), now=NOW).verdict == "unverified"
    newer = _row(updated=NOW - timedelta(minutes=1))
    assert _verdict(record, _catalog(), newer, now=NOW).verdict == "changed"
    young = _record(state="closed", fetched=NOW - timedelta(seconds=10), projection=earlier)
    clock = _verdict(young, _catalog(), _row(), now=NOW)
    assert clock.verdict == "unverified"
    assert pull_state(young, now=NOW, freshness=clock) == ("current", None)


def test_another_readers_newer_row_says_nothing() -> None:
    newer = _row(updated=NOW - timedelta(minutes=1), head=NEWER_HEAD)
    verdict = _verdict(_record(), _catalog(reader="gh:someone-else"), newer, now=NOW)
    assert verdict.verdict == "unverified" and not verdict.head_moved


@pytest.mark.parametrize(
    "changes",
    [
        {"rollup": "pending", "counts": {"pass": 1, "pending": 1}},
        {"rollup": "failure", "counts": {"fail": 1, "pending": 1}},
        {"rollup": "expected", "counts": {}},
        {"conflicts": "unknown"},
        {"merge_state": "unknown"},
    ],
    ids=[
        "a run in progress",
        "a run in progress beside a failure",
        "an expected status",
        "conflicts unknown",
        "merge state unknown",
    ],
)
def test_pending_checks_and_mergeability_are_the_status_s(changes: dict[str, Any]) -> None:
    record = _record()
    status = _status(record, **changes)
    assert checks_pending(record, status)
    verdict = _verdict(record, _catalog(), _row(), status=status)
    assert verdict.verdict == "checks" and verdict.checks_pending
    # A status of another head says nothing of this one's, and no status says nothing.
    assert not checks_pending(record, _status(record, head=NEWER_HEAD, **changes))
    assert not checks_pending(record, None)


def test_settled_or_closed_checks_are_not_pending() -> None:
    record = _record()
    assert not checks_pending(record, _status(record))
    assert not checks_pending(record, _status(record, rollup="failure", counts={"fail": 2}))
    closed = _record(state="closed")
    unsettled = _status(closed, rollup="pending", counts={"pending": 1}, conflicts="unknown")
    assert not checks_pending(closed, unsettled)


def test_no_checks_read_soon_after_an_update_are_pending_for_a_bounded_time() -> None:
    """CI that has not registered yet: a status with no checks, read just after a push."""

    updated = NOW - timedelta(hours=3)
    record = _record(updated=updated)
    soon = _status(record, rollup="none", observed=updated + timedelta(seconds=5))
    assert checks_pending(record, soon)
    bound = updated + timedelta(seconds=NO_CHECKS_GRACE_S)
    assert checks_pending(record, _status(record, rollup="none", observed=bound))
    later = _status(record, rollup="none", observed=bound + timedelta(seconds=1))
    assert not checks_pending(record, later)
    # A repository with no CI is not pending forever, and a closed one never.
    closed = _record(state="closed", updated=updated)
    assert not checks_pending(closed, _status(closed, rollup="none", observed=updated))


# ── The held state's due rule ──────────────────────────────────


def _held(record: PullRecord, tmp_path: Path) -> ServedPull:
    published = ListedRepository(home=tmp_path, slug="demo", owner="octo", repo="demo")
    return ServedPull(published=published, number=7, fetched_at=record.fetched_at)


def test_a_vouched_record_is_not_due_and_a_changed_one_is_due_at_once(tmp_path: Path) -> None:
    record = _record(state="closed")
    held = _held(record, tmp_path)
    assert held.is_stale(NOW, window_s=FRESHNESS_WINDOW_S)
    held.saw_record(record.fetched_at, freshness=_verdict(record, _catalog(), _row(), now=NOW))
    assert not held.is_stale(NOW, window_s=FRESHNESS_WINDOW_S)
    # Vouched twenty seconds ago, so fresh for forty more.
    assert held.is_stale(NOW + timedelta(seconds=41), window_s=FRESHNESS_WINDOW_S)

    changed = _verdict(record, _catalog(), _row(updated=NOW - timedelta(minutes=1)), now=NOW)
    held.saw_record(record.fetched_at, freshness=changed)
    assert held.is_stale(NOW, window_s=FRESHNESS_WINDOW_S)


def test_a_change_an_attempt_already_saw_waits_a_window(tmp_path: Path) -> None:
    """A REST answer that lags the catalog leaves the record changed; it cannot loop."""

    record = _record(fetched=NOW - timedelta(seconds=30))
    held = _held(record, tmp_path)
    changed = _verdict(
        record,
        _catalog(published=NOW - timedelta(seconds=20)),
        _row(updated=NOW - timedelta(seconds=25)),
        now=NOW,
    )
    held.saw_record(record.fetched_at, freshness=changed)
    # Fetched thirty seconds ago, which the window alone would call fresh.
    assert held.is_stale(NOW, window_s=FRESHNESS_WINDOW_S)
    # An attempt for that row, as refresh() starts one.
    held._attempted_row = changed.changed_row  # pyright: ignore[reportPrivateUsage]
    held._last_attempt = NOW - timedelta(seconds=10)  # pyright: ignore[reportPrivateUsage]
    assert not held.is_stale(NOW, window_s=FRESHNESS_WINDOW_S)
    assert held.is_stale(NOW + WINDOW, window_s=FRESHNESS_WINDOW_S)
    # A rate limit holds a changed record too.
    held.last = {
        "outcome": "rate_limited",
        "message": None,
        "reset_at": _stamp(NOW + timedelta(minutes=10)),
        "at": _stamp(NOW),
    }
    held._last_attempt = None  # pyright: ignore[reportPrivateUsage]
    assert not held.is_stale(NOW, window_s=FRESHNESS_WINDOW_S)


def test_a_second_publication_of_the_same_change_does_not_rearm_it(tmp_path: Path) -> None:
    """Review A3: the guard is the row that reported the change, not the checkpoint's time.

    ``count_at`` moves with every page any scan publishes, so keyed to it a lagging answer
    was asked again after each page. The same row, published again, waits the window; a
    row that reports another change is due at once.
    """

    record = _record(fetched=NOW - timedelta(seconds=30))
    held = _held(record, tmp_path)
    reported = _row(updated=NOW - timedelta(seconds=25))
    first = _verdict(record, _catalog(published=NOW - timedelta(seconds=20)), reported, now=NOW)
    held.saw_record(record.fetched_at, freshness=first)
    held._attempted_row = first.changed_row  # pyright: ignore[reportPrivateUsage]
    held._last_attempt = NOW - timedelta(seconds=10)  # pyright: ignore[reportPrivateUsage]
    again = _verdict(record, _catalog(published=NOW - timedelta(seconds=1)), reported, now=NOW)
    held.saw_record(record.fetched_at, freshness=again)
    assert not held.is_stale(NOW, window_s=FRESHNESS_WINDOW_S)
    another = _row(updated=NOW - timedelta(seconds=2), head=NEWER_HEAD)
    held.saw_record(record.fetched_at, freshness=_verdict(record, _catalog(), another, now=NOW))
    assert held.is_stale(NOW, window_s=FRESHNESS_WINDOW_S)


def _reading(
    monkeypatch: pytest.MonkeyPatch, record: PullRecord, clock: list[datetime]
) -> list[str]:
    """Answer each read: a record read in full as of *clock*, or the status alone; return
    which each was, ``full`` or ``status``, and with what a full read was asked."""

    read: list[str] = []

    async def refresh(*_args: object, **kwargs: object) -> PullRecord:
        read.append("full" if not kwargs or kwargs == {"adopt_current": False} else repr(kwargs))
        return record.model_copy(update={"fetched_at": _stamp(clock[0])})

    async def status(*_args: object) -> None:
        read.append("status")

    monkeypatch.setattr(pulls, "refresh_pull_request", refresh)
    monkeypatch.setattr(pulls, "refresh_pull_status", status)
    monkeypatch.setattr(pulls, "utc_now", lambda: clock[0])
    return read


def test_an_open_records_status_is_read_once_a_window_on_its_own(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Review A1: the visible page's automatic refresh asks for the status alone, and that
    read moves none of the record's clocks."""

    record = _record()
    held = _held(record, tmp_path)
    held.saw_record(record.fetched_at, freshness=_verdict(record, _catalog(), _row()))
    assert held.checks_due and held.status_due(NOW)
    assert not held.record_due(NOW, window_s=FRESHNESS_WINDOW_S)
    clock = [NOW]
    read = _reading(monkeypatch, record, clock)
    asyncio.run(held.refresh({"due"}))
    assert read == ["status"]
    assert held.fetched_at == record.fetched_at and held._last_attempt is None  # pyright: ignore[reportPrivateUsage]
    # Tried, whether or not it succeeded, it waits a window.
    assert not held.is_stale(NOW, window_s=FRESHNESS_WINDOW_S)
    assert held.status_due(NOW + WINDOW + timedelta(seconds=1))
    # A reader's own refresh reads everything, and the status after it.
    held.request_recovery()
    asyncio.run(held.refresh({"record"}))
    assert read[-1] == repr({"recover": True, "recovery_pair": None, "adopt_current": False})
    assert held._status_attempt == NOW  # pyright: ignore[reportPrivateUsage]


def test_a_visible_record_with_no_status_of_its_head_reads_one_whatever_the_catalog_says(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A prefetched record reads no status, and its page shows no checks until one is read:
    a status read alone, current record or not, and only GitHub's limit and the GraphQL
    floor hold it, never the REST one."""

    record = _record(state="closed", fetched=NOW - timedelta(seconds=5))
    held = _held(record, tmp_path)
    clock = [NOW]
    read = _reading(monkeypatch, record, clock)
    for catalog, row in ((_catalog(), _row()), (None, None)):
        freshness = _verdict(record, catalog, row, status=None)
        held.saw_record(record.fetched_at, freshness=freshness)
        # The ask probes the record first, which GitHub answers for free, so a change it
        # finds reads the record and its status in one job.
        assert held.status_missing and held.status_due(NOW)
        assert held.automatic_due(NOW) == "probe"
    # Once a probe has run, as the ask's own just did, the status is read alone.
    held._probe_attempt = NOW  # pyright: ignore[reportPrivateUsage]
    assert held.automatic_due(NOW) == "full"
    _observe_core(100)
    assert held.below_floor(NOW) and held.automatic_due(NOW) == "full"
    asyncio.run(held.refresh({"page"}))
    assert read == ["status"] and not held.is_stale(NOW, window_s=FRESHNESS_WINDOW_S)
    # A status of another head is none, and one of its head ends the wait.
    held._status_attempt = None  # pyright: ignore[reportPrivateUsage]
    other = _verdict(record, None, None, status=_status(record, head=NEWER_HEAD))
    held.saw_record(record.fetched_at, freshness=other)
    assert held.status_due(NOW)
    held.saw_record(record.fetched_at, freshness=_verdict(record, None, None))
    assert not held.status_missing and not held.status_due(NOW)
    gh_budget.hold(_stamp(NOW + timedelta(minutes=10)), now=NOW)
    held.saw_record(record.fetched_at, freshness=other)
    assert not held.status_due(NOW)


def test_speculative_work_reads_no_status_and_nothing_while_its_record_is_not_due(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A background record reads no operational status, and the prefetch's caps are priced
    without it. A changed record whose row an attempt already saw, prefetched with no
    status, has a status read due on its page; a speculative refresh of it read that status
    alone, spending a record's place in each cap, and now reads nothing. Once its record is
    due it reads the record, and no status after it."""

    record = _record(fetched=NOW - timedelta(seconds=30))
    held = _held(record, tmp_path)
    changed = _verdict(
        record,
        _catalog(published=NOW - timedelta(seconds=20)),
        _row(updated=NOW - timedelta(seconds=25)),
        status=None,
    )
    held.saw_record(record.fetched_at, freshness=changed)
    held._attempted_row = changed.changed_row  # pyright: ignore[reportPrivateUsage]
    held._last_attempt = NOW - timedelta(seconds=10)  # pyright: ignore[reportPrivateUsage]
    assert changed.verdict == "changed" and held.status_missing and held.status_due(NOW)
    assert not held.record_due(NOW, window_s=FRESHNESS_WINDOW_S)
    clock = [NOW]
    read = _reading(monkeypatch, record, clock)

    async def speculative() -> bool:
        with gh_budget.speculative():
            stale = held.is_stale(clock[0], window_s=FRESHNESS_WINDOW_S)
            await held.refresh({"due"})
            return stale

    assert not asyncio.run(speculative())
    assert read == [] and held._status_attempt is None  # pyright: ignore[reportPrivateUsage]
    clock[0] = NOW + WINDOW
    assert asyncio.run(speculative())
    assert read == ["full"] and held._status_attempt is None  # pyright: ignore[reportPrivateUsage]


def test_a_pages_ask_reads_nothing_once_what_it_found_due_no_longer_is(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The ask found the status alone due, and its job waited its turn at the store; a
    rate-limit hold noted meanwhile holds the status and the record alike. The job read
    the record in full all the same, about four ``core`` during the hold, and now reads
    nothing. A reader's own action still reads everything, and an ask for the record, as
    a commit the mirror lacks makes, reads the record."""

    record = _record(fetched=NOW - timedelta(seconds=30))
    held = _held(record, tmp_path)
    held.saw_record(record.fetched_at, freshness=_verdict(record, _catalog(), _row(), status=None))
    # A probe has just run, so the ask reads the status rather than probing first.
    held._probe_attempt = NOW  # pyright: ignore[reportPrivateUsage]
    assert held.status_due(NOW) and not held.record_due(NOW, window_s=FRESHNESS_WINDOW_S)
    assert held.automatic_due(NOW) == "full"
    clock = [NOW]
    read = _reading(monkeypatch, record, clock)
    gh_budget.hold(_stamp(NOW + timedelta(minutes=10)), now=NOW)
    assert not held.status_due(NOW) and not held.record_due(NOW, window_s=FRESHNESS_WINDOW_S)
    asyncio.run(held.refresh({"page"}))
    assert read == [] and held._last_attempt is None  # pyright: ignore[reportPrivateUsage]
    held.request_recovery()
    asyncio.run(held.refresh({"record"}))
    assert read == [repr({"recover": True, "recovery_pair": None, "adopt_current": False})]
    gh_budget.forget()
    assert not held.is_stale(NOW, window_s=FRESHNESS_WINDOW_S)
    asyncio.run(held.refresh({"record"}))
    assert read[1:] == ["full"]


def test_a_record_adopted_while_the_status_alone_is_read_counts_as_read_in_full(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A read of the status alone publishes no record, so one another process published
    while it ran, which the page adopted, is another writer's: the next full read is due
    FULL_REFRESH_S after that record, not up to that much earlier, after the one before."""

    record = _record(fetched=NOW - timedelta(seconds=30))
    held = _held(record, tmp_path)
    held.full_read_at = record.fetched_at
    held.saw_record(record.fetched_at, freshness=_verdict(record, _catalog(), _row(), status=None))
    assert held.status_due(NOW) and not held.record_due(NOW, window_s=FRESHNESS_WINDOW_S)
    clock = [NOW]
    read = _reading(monkeypatch, record, clock)
    published = NOW - timedelta(seconds=1)

    async def status(*_args: object) -> None:
        read.append("status")
        held.saw_record(_stamp(published))

    monkeypatch.setattr(pulls, "refresh_pull_status", status)
    asyncio.run(held.refresh({"page"}))
    assert read == ["status"] and held.fetched_at == _stamp(published)
    full = timedelta(seconds=FULL_REFRESH_S)
    assert not held.full_read_overdue(published + full)
    assert held.full_read_overdue(published + full + timedelta(seconds=1))


def test_a_scans_status_the_page_has_no_list_for_is_read_at_once_and_once(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The Pulls tab's scan keeps the newest status of every open pull request, without its
    checks. Where it finds checks the page's read did not list, of a head the page never
    read, as a prefetched record's, or checks that moved since, the page reads its own at
    once, below the floor as a change a probe finds is, and only once."""

    record = _record(fetched=NOW - timedelta(seconds=5))
    held = _held(record, tmp_path)
    read = _reading(monkeypatch, record, [NOW])
    held._status_attempt = NOW - timedelta(seconds=3)  # pyright: ignore[reportPrivateUsage]
    observed = NOW - timedelta(seconds=1)
    status = _status(record, observed=observed, by="scan", rollup="pending", counts={"pending": 1})
    freshness = _verdict(record, _catalog(), _row(), status=status)
    assert (freshness.status_missing, freshness.unlisted_at) == (True, _stamp(observed))
    held.saw_record(record.fetched_at, freshness=freshness)
    _observe_core(100)
    assert held.status_due(NOW) and held.automatic_due(NOW) == "full"
    asyncio.run(held.refresh({"page"}))
    assert read == ["status"]
    # The read that started after the scan's status answers it: no read again for it.
    held.saw_record(record.fetched_at, freshness=freshness)
    assert not held.status_due(NOW)
    # A scan that finds the read's own checks keeps its list, and asks for nothing.
    listed = _status(record, observed=NOW - timedelta(seconds=2))
    same = _status(record, observed=NOW, by="scan")
    kept = kept_observation(listed, same)
    assert kept.observed_by == "scan" and kept.checks.listed_at == listed.checks.listed_at
    assert not _verdict(record, _catalog(), _row(), status=kept).status_missing


def test_a_verdict_on_another_record_is_not_adopted(tmp_path: Path) -> None:
    record = _record()
    held = _held(record, tmp_path)
    newer = _stamp(NOW - timedelta(seconds=1))
    held.saw_record(newer)
    held.saw_record(record.fetched_at, freshness=_verdict(record, _catalog(), _row(), now=NOW))
    assert held.verified_at is None and held.fetched_at == newer


def test_a_cancelled_refresh_forgets_its_attempt(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A background job a reader preempts must not hold the reader's own automatic refresh."""

    record = _record()
    held = _held(record, tmp_path)
    started = asyncio.Event()

    async def slow(*_args: object, **_kwargs: object) -> PullRecord:
        started.set()
        await asyncio.sleep(3600)
        raise AssertionError("not reached")

    monkeypatch.setattr(pulls, "refresh_pull_request", slow)
    monkeypatch.setattr(pulls, "utc_now", lambda: NOW)

    async def run() -> None:
        task = asyncio.ensure_future(held.refresh({"due"}))
        await started.wait()
        assert held.refreshing and held._last_attempt == NOW  # pyright: ignore[reportPrivateUsage]
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task

    asyncio.run(run())
    assert held._last_attempt is None and not held.refreshing  # pyright: ignore[reportPrivateUsage]
    assert held.is_stale(NOW, window_s=FRESHNESS_WINDOW_S)


def test_a_running_scan_keeps_the_last_verdict_for_a_bounded_time() -> None:
    """At the window's end the next scan decides in a moment; a page asks nothing meanwhile.

    Review A2 and B1: only for :data:`SCAN_GRACE_S` past the window. An older catalog is
    unverified whatever runs, so a page reopened on it refreshes a stale record at once,
    as the clock did before the catalog vouched.
    """

    record = _record(state="closed")
    old = _catalog(fetched=NOW - WINDOW - timedelta(seconds=5))
    assert _verdict(record, old, _row(), now=NOW).verdict == "unverified"
    verdict = _verdict(record, old, _row(), now=NOW, scanning=True)
    assert verdict.verdict == "current" and verdict.verified_at == old.fetched_at
    # A change the last scan saw still decides as before, and an open record's status.
    newer = _row(updated=NOW - timedelta(minutes=5))
    assert _verdict(record, old, newer, now=NOW, scanning=True).verdict == "changed"
    assert _verdict(_record(), old, _row(), now=NOW, scanning=True).verdict == "checks"
    edge = _catalog(fetched=NOW - WINDOW - timedelta(seconds=SCAN_GRACE_S))
    assert _verdict(record, edge, _row(), now=NOW, scanning=True).verdict == "current"
    for age in (WINDOW + timedelta(seconds=SCAN_GRACE_S + 1), timedelta(hours=3)):
        stale = _catalog(fetched=NOW - age)
        verdict = _verdict(record, stale, _row(), now=NOW, scanning=True)
        assert verdict.verdict == "unverified"
        assert pull_state(record, now=NOW, freshness=verdict) == ("stale", None)


def test_the_verified_header_says_a_catalog_verdict_was_given_while_a_scan_ran() -> None:
    """Review B1: the page polls fast while the scan that decides in a moment runs."""

    from typing import cast

    from metabrowser.builtin_plugins.github.pull_route import (
        VERIFIED_HEADER,
        PullEnvelope,
        verified_header,
    )

    def envelope(by: str | None, at: str | None) -> PullEnvelope:
        return cast("PullEnvelope", {"verified_by": by, "verified_at": at})

    at = _stamp(NOW)
    assert verified_header(envelope("catalog", at), scanning=True) == {
        VERIFIED_HEADER: f"catalog {at} scanning"
    }
    assert verified_header(envelope("catalog", at)) == {VERIFIED_HEADER: f"catalog {at}"}
    # The clock's verdict does not wait on the scan, and no record has no header.
    assert verified_header(envelope("fetch", at), scanning=True) == {VERIFIED_HEADER: f"fetch {at}"}
    assert verified_header(envelope(None, None), scanning=True) == {}


# ── Probes ─────────────────────────────────────────────────────


def _probing(
    monkeypatch: pytest.MonkeyPatch, outcomes: list[pulls.PullProbe | pulls.PullDataError]
) -> list[bool]:
    """Answer each probe with the next of *outcomes*; return what each asked of its checks."""

    asked: list[bool] = []

    async def probe(_published: object, _record: object, **kwargs: Any) -> pulls.PullProbe:
        asked.append(bool(kwargs["checks"]))
        found = outcomes.pop(0)
        if isinstance(found, pulls.PullDataError):
            raise found
        return found

    monkeypatch.setattr(pulls, "probe_pull_request", probe)
    return asked


def test_a_visible_record_is_probed_every_few_seconds_and_read_in_full_every_minute_or_two(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Probes vouch for a record past the freshness window, up to FULL_REFRESH_S."""

    record = _record(state="closed", fetched=NOW)
    held = _held(record, tmp_path)
    _probing(monkeypatch, [pulls.PullProbe("unchanged", {})] * 3)
    clock = [NOW]
    monkeypatch.setattr(pulls, "utc_now", lambda: clock[0])
    assert held.automatic_due(NOW) == "probe"
    asyncio.run(held.probe(record))
    assert held.probed_at == _stamp(NOW)
    # Not again within PROBE_FLOOR_S, however many pages ask; an ask that arrives a little
    # before the page's ATTENDED_PROBE_S still probes, so jitter does not skip one.
    assert PROBE_FLOOR_S < ATTENDED_PROBE_S
    assert held.automatic_due(NOW + timedelta(seconds=PROBE_FLOOR_S - 0.1)) is None
    assert held.automatic_due(NOW + timedelta(seconds=ATTENDED_PROBE_S - 0.002)) == "probe"
    # Past the freshness window, the probe that vouched keeps it from a full read...
    clock[0] = NOW + timedelta(seconds=FRESHNESS_WINDOW_S - 1)
    asyncio.run(held.probe(record))
    assert held.automatic_due(NOW + timedelta(seconds=FRESHNESS_WINDOW_S + 5)) == "probe"
    # ...until FULL_REFRESH_S, whatever the probes say.
    assert held.automatic_due(NOW + timedelta(seconds=FULL_REFRESH_S + 1)) == "full"
    # With no probe within a window, the window decides, as before probes.
    unprobed = _held(record, tmp_path)
    assert unprobed.automatic_due(NOW + WINDOW + timedelta(seconds=1)) == "full"


def test_a_change_a_probe_finds_is_due_at_once_and_does_not_loop(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    record = _record(state="closed", fetched=NOW)
    held = _held(record, tmp_path)
    _probing(monkeypatch, [pulls.PullProbe("changed", {})])
    monkeypatch.setattr(pulls, "utc_now", lambda: NOW)
    asyncio.run(held.probe(record))
    assert held.automatic_due(NOW) == "full"
    # An attempt that starts after the probe consumes it; a failed one is not re-armed by
    # the next probe for a window.
    held._last_attempt = NOW + timedelta(seconds=1)  # pyright: ignore[reportPrivateUsage]
    held.last = {"outcome": "gh_failed", "message": "x", "reset_at": None, "at": _stamp(NOW)}
    later = NOW + timedelta(seconds=ATTENDED_PROBE_S + 2)
    assert held.automatic_due(later) is None
    assert not held.probe_due(later)


def _unknown(record: PullRecord) -> PullStatus:
    """The kept status of *record*'s head before GitHub has computed whether it can merge."""

    return _status(record, conflicts="unknown", merge_state="unknown")


def _settling(record: PullRecord) -> PullStatus:
    """The kept status of *record*'s head while one of its two checks still runs."""

    return _status(record, rollup="pending", counts={"pass": 1, "pending": 1})


def test_a_change_to_checks_alone_reads_the_status_alone(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A pending check is probed with the pull, a change reads only the status, and the
    record, whose issue the probe found unchanged, stays vouched for."""

    record = _record(state="open", fetched=NOW)
    status = _settling(record)
    held = _held(record, tmp_path)
    asked = _probing(
        monkeypatch, [pulls.PullProbe("unchanged", {}), pulls.PullProbe("checks_changed", {})]
    )
    clock = [NOW]
    monkeypatch.setattr(pulls, "utc_now", lambda: clock[0])
    asyncio.run(held.probe(record, status=status))
    # The checks are probed only once every CHECKS_PROBE_S.
    clock[0] = NOW + timedelta(seconds=ATTENDED_PROBE_S)
    asyncio.run(held.probe(record, status=status))
    assert asked == [True, False]
    clock[0] = NOW + timedelta(seconds=CHECKS_PROBE_S)
    _probing(monkeypatch, [pulls.PullProbe("checks_changed", {})])
    asyncio.run(held.probe(record, status=status))
    assert held.probed_at == _stamp(clock[0])
    assert held.status_due(clock[0]) and not held.record_due(clock[0], window_s=FULL_REFRESH_S)
    assert held.automatic_due(clock[0]) == "full"
    read = _reading(monkeypatch, record, clock)
    asyncio.run(held.refresh({"page"}))
    assert read == ["status"]
    # The same record, still vouched for, is probed again once ATTENDED_PROBE_S has passed.
    assert held.fetched_at == record.fetched_at and held.probed_at == _stamp(clock[0])
    assert held.automatic_due(clock[0]) is None
    assert held.automatic_due(clock[0] + timedelta(seconds=ATTENDED_PROBE_S)) == "probe"
    # A later change the probe finds is due again, once.
    clock[0] += timedelta(seconds=CHECKS_PROBE_S)
    _probing(monkeypatch, [pulls.PullProbe("checks_changed", {})])
    asyncio.run(held.probe(record, status=status))
    assert held.status_due(clock[0])


def test_a_failed_probe_waits_a_window_and_a_rate_limit_holds_every_probe(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    record = _record(state="closed", fetched=NOW)
    held = _held(record, tmp_path)
    _probing(monkeypatch, [pulls.PullDataError("network_error", "offline")])
    monkeypatch.setattr(pulls, "utc_now", lambda: NOW)
    asyncio.run(held.probe(record))
    assert held.probed_at is None
    assert not held.probe_due(NOW + timedelta(seconds=ATTENDED_PROBE_S + 1))
    assert held.probe_due(NOW + WINDOW + timedelta(seconds=1))
    held.last = {
        "outcome": "rate_limited",
        "message": None,
        "reset_at": _stamp(NOW + timedelta(hours=1)),
        "at": _stamp(NOW),
    }
    assert not held.probe_due(NOW + WINDOW + timedelta(seconds=1))


def test_a_probe_of_an_older_record_says_nothing_of_the_newer_one(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    record = _record(state="closed", fetched=NOW)
    held = _held(record, tmp_path)
    newer = _stamp(NOW + timedelta(seconds=1))

    async def probe(*_args: object, **_kwargs: object) -> pulls.PullProbe:
        held.saw_record(newer)
        return pulls.PullProbe("changed", {})

    monkeypatch.setattr(pulls, "probe_pull_request", probe)
    monkeypatch.setattr(pulls, "utc_now", lambda: NOW)
    asyncio.run(held.probe(record))
    # What it found is dropped: nothing is due until the next probe of the newer record.
    assert held.fetched_at == newer and held.automatic_due(NOW) is None
    assert held.automatic_due(NOW + timedelta(seconds=ATTENDED_PROBE_S)) == "probe"


def test_a_second_page_asking_while_a_probe_runs_starts_none(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """While a probe runs nothing more is due, so the route never starts a second one."""

    record = _record(state="closed", fetched=NOW)
    held = _held(record, tmp_path)
    calls: list[int] = []
    release = asyncio.Event()

    async def probe(*_args: object, **_kwargs: object) -> pulls.PullProbe:
        calls.append(1)
        await release.wait()
        return pulls.PullProbe("unchanged", {})

    monkeypatch.setattr(pulls, "probe_pull_request", probe)
    monkeypatch.setattr(pulls, "utc_now", lambda: NOW)
    later = NOW + timedelta(seconds=ATTENDED_PROBE_S)

    async def run() -> None:
        first = asyncio.ensure_future(held.probe(record))
        await asyncio.sleep(0)
        assert held.probing and held.automatic_due(later) is None
        with pytest.raises(AssertionError):
            await held.probe(record)
        release.set()
        await first

    asyncio.run(run())
    assert calls == [1] and held.probed_at == _stamp(NOW) and not held.probing


@pytest.mark.parametrize("why", ["a page's worth of checks", "pages GitHub refused"])
def test_settling_checks_a_probe_cannot_see_keep_the_window_cadence(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, why: str
) -> None:
    """A head with more checks than a page holds, or whose pages GitHub refuses this reader,
    is not probed for its checks: while they settle it is read once a window, as before
    probes."""

    record = _record(state="open", fetched=NOW)
    held = _held(record, tmp_path)
    probes = None
    if why == "pages GitHub refused":
        status = _settling(record)
        probes = CheckProbes(
            number=7, head=HEAD, reader=READER, seen_at=_stamp(NOW), pages={}, refused=True
        )
    else:
        status = _status(record, rollup="pending", counts={"pass": 99, "pending": 1})
    assert pulls.checks_probe_paths(held.published, record, status, probes) is None
    assert pulls.checks_probe_paths(held.published, record, _settling(record)) is not None
    _probing(monkeypatch, [pulls.PullProbe("unchanged", {})])
    monkeypatch.setattr(pulls, "utc_now", lambda: NOW + WINDOW - timedelta(seconds=1))
    asyncio.run(held.probe(record, status=status, probes=probes))
    assert held.probed_at is None
    assert held.automatic_due(NOW + WINDOW + timedelta(seconds=1)) == "full"


def test_a_full_read_comes_due_every_full_refresh_s_whatever_reads_only_the_status(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Status reads move neither fetched_at nor the full read's clock, and the read that
    interval makes due reads everything, even for a record whose status alone is due."""

    record = _record(state="open", fetched=NOW)
    held = _held(record, tmp_path)
    held.full_read_at = held.probed_at = record.fetched_at
    clock = [NOW]
    read = _reading(monkeypatch, record, clock)
    # CI changes the checks every few seconds; each change a probe sees is a status read.
    for seconds in (10, 40, 70):
        clock[0] = NOW + timedelta(seconds=seconds)
        held.probed_at = _stamp(clock[0])
        held._probe_saw, held._probe_saw_at = "checks", clock[0]  # pyright: ignore[reportPrivateUsage]
        asyncio.run(held.refresh({"page"}))
    assert read == ["status", "status", "status"]
    assert held.full_read_at == held.fetched_at == record.fetched_at
    clock[0] = NOW + timedelta(seconds=FULL_REFRESH_S + 1)
    assert held.automatic_due(clock[0]) == "full"
    held.checks_due = True
    asyncio.run(held.refresh({"page"}))
    assert read[-1] == "full" and held.full_read_at == _stamp(clock[0])
    # A failed full read is not retried on every ask, but once FULL_REFRESH_S later.
    held.full_read_at = _stamp(NOW)
    assert not held.full_read_due(clock[0] + timedelta(seconds=1))


def test_a_probe_failing_for_a_superseded_record_holds_no_probe_of_the_newer_one(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    record = _record(state="closed", fetched=NOW)
    held = _held(record, tmp_path)
    newer = _stamp(NOW + timedelta(seconds=1))

    async def probe(*_args: object, **_kwargs: object) -> pulls.PullProbe:
        held.saw_record(newer)
        raise pulls.PullDataError("network_error", "offline")

    monkeypatch.setattr(pulls, "probe_pull_request", probe)
    monkeypatch.setattr(pulls, "utc_now", lambda: NOW)
    asyncio.run(held.probe(record))
    assert held.probe_due(NOW + timedelta(seconds=ATTENDED_PROBE_S))
    # A newer record forgets a failure an earlier probe saw, too.
    held._probe_failed = NOW  # pyright: ignore[reportPrivateUsage]
    held.saw_record(_stamp(NOW + timedelta(seconds=2)))
    assert held.probe_due(NOW + timedelta(seconds=ATTENDED_PROBE_S))


def test_a_probe_that_raises_anything_waits_a_window_and_is_not_evicted_while_it_runs(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    record = _record(state="closed", fetched=NOW)
    held = _held(record, tmp_path)

    async def probe(*_args: object, **_kwargs: object) -> pulls.PullProbe:
        raise RuntimeError("a bug")

    monkeypatch.setattr(pulls, "probe_pull_request", probe)
    monkeypatch.setattr(pulls, "utc_now", lambda: NOW)
    asyncio.run(held.probe(record))
    assert not held.probe_due(NOW + timedelta(seconds=ATTENDED_PROBE_S))
    assert held.probe_due(NOW + WINDOW + timedelta(seconds=1))

    # A pull request kept while its probe runs is not the one evicted for a new one.
    source = ServedPulls(published=held.published)
    release = asyncio.Event()

    async def slow(*_args: object, **_kwargs: object) -> pulls.PullProbe:
        await release.wait()
        return pulls.PullProbe("unchanged", {})

    monkeypatch.setattr(pulls, "probe_pull_request", slow)

    async def run() -> None:
        probing = source._keep(_held(record, tmp_path))  # pyright: ignore[reportPrivateUsage]
        task = asyncio.ensure_future(probing.probe(record))
        await asyncio.sleep(0)
        for number in range(8, 8 + 64):
            source._keep(ServedPull(published=held.published, number=number))  # pyright: ignore[reportPrivateUsage]
        assert source._kept.get(7) is probing  # pyright: ignore[reportPrivateUsage]
        release.set()
        await task

    asyncio.run(run())


def test_an_overdue_full_read_waits_out_a_failed_refresh(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Review B5 on #709: a failed read of any kind holds the full read for a window."""

    record = _record(state="closed", fetched=NOW - timedelta(seconds=FULL_REFRESH_S + 30))
    held = _held(record, tmp_path)
    held.last = {"outcome": "gh_failed", "message": "x", "reset_at": None, "at": _stamp(NOW)}
    held._last_attempt = NOW - timedelta(seconds=5)  # pyright: ignore[reportPrivateUsage]
    assert held.full_read_overdue(NOW) and not held.full_read_due(NOW)
    assert held.automatic_due(NOW) is None
    assert held.full_read_due(NOW + WINDOW)


def test_a_record_a_running_refresh_published_is_not_taken_as_a_full_read(
    tmp_path: Path,
) -> None:
    """Review B6 on #709: the running refresh, perhaps checks_only, sets the clock itself."""

    record = _record(state="open", fetched=NOW)
    held = _held(record, tmp_path)
    held.full_read_at = record.fetched_at
    held._refreshing = True  # pyright: ignore[reportPrivateUsage]
    held.saw_record(_stamp(NOW + timedelta(seconds=30)))
    assert held.fetched_at == _stamp(NOW + timedelta(seconds=30))
    assert held.full_read_at == record.fetched_at
    held._refreshing = False  # pyright: ignore[reportPrivateUsage]
    held.saw_record(_stamp(NOW + timedelta(seconds=40)))
    assert held.full_read_at == _stamp(NOW + timedelta(seconds=40))


def test_the_checks_probes_keep_their_cadence_through_jitter_and_newer_records(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Review B7 on #709: a probe a little early still asks the checks once CHECKS_PROBE_S
    is nearly up, and a newer record does not restart their clock."""

    record = _record(state="open", fetched=NOW)
    status = _settling(record)
    held = _held(record, tmp_path)
    asked = _probing(monkeypatch, [pulls.PullProbe("unchanged", {})] * 3)
    clock = [NOW]
    monkeypatch.setattr(pulls, "utc_now", lambda: clock[0])
    asyncio.run(held.probe(record, status=status))
    # Two probes PROBE_FLOOR_S apart reach the checks a little before CHECKS_PROBE_S.
    clock[0] = NOW + timedelta(seconds=PROBE_FLOOR_S)
    asyncio.run(held.probe(record, status=status))
    clock[0] = NOW + timedelta(seconds=2 * PROBE_FLOOR_S + 1)
    assert 2 * PROBE_FLOOR_S + 1 < CHECKS_PROBE_S
    asyncio.run(held.probe(record, status=status))
    assert asked == [True, False, True]
    # A newer record keeps the checks probes' clock.
    held.saw_record(_stamp(clock[0] + timedelta(seconds=1)))
    assert held._checks_probe_attempt == clock[0]  # pyright: ignore[reportPrivateUsage]


# ── Below the floor ────────────────────────────────────────────


def _observe_core(remaining: int, *, limit: int = 5000) -> None:
    """The account's core budget as a response just reported it, resetting in an hour."""

    gh_budget.observe(
        {
            "x-ratelimit-limit": str(limit),
            "x-ratelimit-remaining": str(remaining),
            "x-ratelimit-reset": str(int((NOW + timedelta(hours=1)).timestamp())),
            "x-ratelimit-resource": "core",
        },
        resource="core",
    )


def test_below_the_floor_probes_go_on_and_only_a_change_they_find_is_read_in_full(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """mb-qngw, the owner's rule: below ``BACKGROUND_FLOOR`` the periodic full read stops,
    probes keep running, and a change one finds on the page on screen is still read."""

    record = _record(state="closed", fetched=NOW)
    held = _held(record, tmp_path)
    _probing(monkeypatch, [pulls.PullProbe("unchanged", {}), pulls.PullProbe("changed", {})])
    clock = [NOW]
    monkeypatch.setattr(pulls, "utc_now", lambda: clock[0])
    asyncio.run(held.probe(record))
    late = NOW + timedelta(seconds=FULL_REFRESH_S + 1)
    assert held.automatic_due(late) == "full"

    _observe_core(int(gh_budget.BACKGROUND_FLOOR * 5000))
    assert held.below_floor(late)
    # The full read is as overdue as it was, and waits; the probe is what is due.
    assert held.full_read_overdue(late) and not held.full_read_due(late)
    assert not held.is_stale(late, window_s=FRESHNESS_WINDOW_S)
    assert held.automatic_due(late) == "probe"
    # A probe that finds a change starts its full read all the same.
    clock[0] = late
    asyncio.run(held.probe(record))
    assert held.is_stale(late, window_s=FRESHNESS_WINDOW_S)
    assert held.automatic_due(late) == "full"

    # Above the floor again, the periodic read is due as before.
    unprobed = _held(record, tmp_path)
    assert unprobed.automatic_due(late) == "probe"
    _observe_core(int(gh_budget.BACKGROUND_FLOOR * 5000) + 1)
    assert not unprobed.below_floor(late) and unprobed.automatic_due(late) == "full"


def test_below_the_floor_a_change_the_catalog_reports_is_read_and_a_status_window_is_not(
    tmp_path: Path,
) -> None:
    record = _record(fetched=NOW - 2 * WINDOW)
    held = _held(record, tmp_path)
    _observe_core(100)
    # An open record the catalog vouches for has its status read once a window: periodic,
    # and it spends GraphQL, not the REST budget below its floor.
    held.saw_record(record.fetched_at, freshness=_verdict(record, _catalog(), _row()))
    assert held.checks_due and held.is_stale(NOW, window_s=FRESHNESS_WINDOW_S)
    assert not held.record_due(NOW, window_s=FRESHNESS_WINDOW_S)
    gh_budget.observe(
        {
            "x-ratelimit-limit": "5000",
            "x-ratelimit-remaining": "100",
            "x-ratelimit-reset": str(int((NOW + timedelta(hours=1)).timestamp())),
            "x-ratelimit-resource": "graphql",
        },
        resource="graphql",
    )
    assert held.checks_due and not held.is_stale(NOW, window_s=FRESHNESS_WINDOW_S)
    # A row that says GitHub changed it is a change found on the page on screen.
    changed = _verdict(record, _catalog(), _row(updated=NOW - timedelta(minutes=1)), now=NOW)
    held.saw_record(record.fetched_at, freshness=changed)
    assert held.is_stale(NOW, window_s=FRESHNESS_WINDOW_S)
    assert held.automatic_due(NOW) == "full"


def test_a_rate_limit_hold_stops_the_read_of_a_change_a_probe_found_below_the_floor(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    record = _record(state="closed", fetched=NOW)
    held = _held(record, tmp_path)
    _probing(monkeypatch, [pulls.PullProbe("changed", {})])
    monkeypatch.setattr(pulls, "utc_now", lambda: NOW)
    _observe_core(100)
    asyncio.run(held.probe(record))
    assert held.automatic_due(NOW) == "full"
    gh_budget.hold(_stamp(NOW + timedelta(minutes=10)), now=NOW)
    assert held.automatic_due(NOW) is None


# ── Probes in flight ───────────────────────────────────────────


def test_probes_in_flight_are_capped_across_pull_requests(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """mb-et0k: each probe is a ``gh`` process, so a server runs a bounded number at once,
    and a pull request past the bound is not due until one ends."""

    record = _record(state="closed", fetched=NOW)
    published = ListedRepository(home=tmp_path, slug="demo", owner="octo", repo="demo")
    cap = served_pull.MAX_PROBES_IN_FLIGHT
    running: list[int] = []
    monkeypatch.setattr(pulls, "utc_now", lambda: NOW)

    async def run() -> None:
        release = asyncio.Event()

        async def probe(*_args: object, **_kwargs: object) -> pulls.PullProbe:
            running.append(1)
            await release.wait()
            return pulls.PullProbe("unchanged", {})

        monkeypatch.setattr(pulls, "probe_pull_request", probe)
        held = [
            ServedPull(published=published, number=number, fetched_at=record.fetched_at)
            for number in range(1, cap + 2)
        ]
        waits = [asyncio.ensure_future(pull.probe(record)) for pull in held[:cap]]
        for _turn in range(3):
            await asyncio.sleep(0)
        assert served_pull.probes_in_flight() == cap == len(running)
        extra = held[-1]
        assert not extra.probe_due(NOW) and extra.automatic_due(NOW) is None
        release.set()
        await asyncio.gather(*waits)
        assert served_pull.probes_in_flight() == 0
        assert extra.automatic_due(NOW) == "probe"

    asyncio.run(run())


def test_a_probe_is_a_job_of_the_coordinator_so_shutdown_cancels_it(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """mb-et0k: nothing cancelled a running probe when the server shut down."""

    record = _record(state="closed", fetched=NOW)
    held = _held(record, tmp_path)
    ended: list[str] = []
    monkeypatch.setattr(pulls, "utc_now", lambda: NOW)

    async def probe(*_args: object, **_kwargs: object) -> pulls.PullProbe:
        try:
            await asyncio.Event().wait()
        except asyncio.CancelledError:
            ended.append("cancelled")
            raise
        raise AssertionError("unreachable")

    monkeypatch.setattr(pulls, "probe_pull_request", probe)

    async def run() -> None:
        coordinator = RefreshCoordinator()
        asking = asyncio.ensure_future(held.probe(record, coordinator=coordinator))
        for _turn in range(3):
            await asyncio.sleep(0)
        assert held.probing and coordinator.running(held.probe_key)
        assert served_pull.probes_in_flight() == 1
        await coordinator.aclose()
        assert ended == ["cancelled"]
        assert not held.probing and served_pull.probes_in_flight() == 0
        # The request that waited on it ends without an error of its own.
        await asking

    asyncio.run(run())
    # A cancelled probe found nothing and failed nothing.
    assert held.probed_at is None and held.probe_due(NOW + timedelta(seconds=ATTENDED_PROBE_S))


# ── What a probe saw of the issue ──────────────────────────────


def test_what_a_probe_saw_of_the_issue_outlives_the_record_it_ran_beside(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """mb-2ppr: the next record's first probe is conditional too, where a ``checks_only``
    read every few seconds while CI runs would otherwise make each one a paid read."""

    record = _record(state="closed", fetched=NOW)
    held = _held(record, tmp_path)
    seen = pulls.IssueSeen(record.pull.updated_at, 'W/"issue"')
    sent: list[pulls.IssueSeen | None] = []

    async def probe(_published: object, _record: object, **kwargs: Any) -> pulls.PullProbe:
        sent.append(kwargs["seen"])
        return pulls.PullProbe("unchanged", {}, seen)

    monkeypatch.setattr(pulls, "probe_pull_request", probe)
    monkeypatch.setattr(pulls, "utc_now", lambda: NOW)
    asyncio.run(held.probe(record))
    newer = record.model_copy(update={"fetched_at": _stamp(NOW + timedelta(seconds=1))})
    held.saw_record(newer.fetched_at)
    assert held.probed_at is None
    asyncio.run(held.probe(newer))
    assert sent == [None, seen] and held.probed_at == _stamp(NOW)


def test_a_change_the_full_read_did_not_bring_is_read_again_once_a_window(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The pull's own answer can lag its issue's. A read that leaves the record behind the
    change a probe saw is not started again by every probe, as a row the catalog reports
    is not (``_attempted_row``): once a window."""

    record = _record(state="closed", fetched=NOW)
    held = _held(record, tmp_path)
    ahead = pulls.IssueSeen(_stamp(NOW + timedelta(seconds=30)), 'W/"ahead"')
    _probing(monkeypatch, [pulls.PullProbe("changed", {}, ahead, ahead.updated_at)] * 3)
    clock = [NOW]
    monkeypatch.setattr(pulls, "utc_now", lambda: clock[0])
    asyncio.run(held.probe(record))
    assert held.automatic_due(NOW) == "full"

    async def refresh(*_args: object, **_kwargs: object) -> PullRecord:
        # The pull as GitHub's pull endpoint still has it: the same ``updated_at``.
        return record.model_copy(update={"fetched_at": _stamp(clock[0])})

    monkeypatch.setattr(pulls, "refresh_pull_request", refresh)
    clock[0] = NOW + timedelta(seconds=1)
    asyncio.run(held.refresh({"page"}))
    lagging = record.model_copy(update={"fetched_at": held.fetched_at})
    clock[0] = NOW + timedelta(seconds=ATTENDED_PROBE_S + 1)
    asyncio.run(held.probe(lagging))
    # The same change again: the record is not vouched for, and no second read is due.
    assert held.probed_at is None and held.automatic_due(clock[0]) is None
    clock[0] = NOW + WINDOW + timedelta(seconds=2)
    asyncio.run(held.probe(lagging))
    assert held.automatic_due(clock[0]) == "full"


# ── Review A of #726 ───────────────────────────────────────────


def _asking(
    monkeypatch: pytest.MonkeyPatch, outcomes: list[pulls.PullProbe]
) -> list[tuple[bool, bool]]:
    """Answer each probe with the next of *outcomes*; return what each asked beside the
    issue, as ``(mergeability, checks)``."""

    asked: list[tuple[bool, bool]] = []

    async def probe(_published: object, _record: object, **kwargs: Any) -> pulls.PullProbe:
        asked.append((bool(kwargs["mergeability"]), bool(kwargs["checks"])))
        return outcomes.pop(0)

    monkeypatch.setattr(pulls, "probe_pull_request", probe)
    return asked


def test_unknown_mergeability_is_asked_of_the_pull_for_a_bounded_time_and_not_vouched_after(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A1: the issue cannot say when GitHub finishes computing ``mergeable``, so a pull
    request whose kept status holds ``unknown`` has the pull asked too, for
    MERGEABLE_SETTLE_S per head, and is not vouched for once it is asked no more."""

    record = _record(fetched=NOW)
    held = _held(record, tmp_path)
    asked = _asking(monkeypatch, [pulls.PullProbe("unchanged", {})] * 6)
    clock = [NOW]
    monkeypatch.setattr(pulls, "utc_now", lambda: clock[0])
    asyncio.run(held.probe(record, status=_unknown(record)))
    # The pull is asked, and not the check pages, which cannot answer this.
    assert asked == [(True, False)] and held.probed_at == _stamp(NOW)
    clock[0] = NOW + timedelta(seconds=served_pull.MERGEABLE_SETTLE_S)
    asyncio.run(held.probe(record, status=_unknown(record)))
    assert asked[-1] == (True, False) and held.probed_at == _stamp(clock[0])
    # Past the bound the pull is asked no more, and no probe vouches for "unknown".
    vouched = held.probed_at
    clock[0] = NOW + timedelta(seconds=served_pull.MERGEABLE_SETTLE_S + ATTENDED_PROBE_S)
    asyncio.run(held.probe(record, status=_unknown(record)))
    assert asked[-1] == (False, False) and held.probed_at == vouched
    assert not held.probe_vouches(clock[0] + WINDOW)
    # Another record of the same head, as a full read publishes, starts no new wait.
    again = record.model_copy(update={"fetched_at": _stamp(clock[0])})
    held.saw_record(again.fetched_at)
    clock[0] += timedelta(seconds=ATTENDED_PROBE_S)
    asyncio.run(held.probe(again, status=_unknown(again)))
    assert asked[-1] == (False, False) and held.probed_at is None
    # A status that holds an answer ends the wait; the next unknown has its own.
    answered = _record(fetched=clock[0])
    held.saw_record(answered.fetched_at)
    asyncio.run(held.probe(answered, status=_status(answered)))
    assert asked[-1] == (False, False) and held.probed_at == _stamp(clock[0])
    clock[0] += timedelta(seconds=ATTENDED_PROBE_S)
    unknown = _record(fetched=clock[0])
    held.saw_record(unknown.fetched_at)
    asyncio.run(held.probe(unknown, status=_unknown(unknown)))
    assert asked[-1] == (True, False)


def test_mergeability_a_probe_sees_resolve_reads_the_status_alone_below_the_floor_too(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A1: below the floor nothing else would ever read it, of either budget."""

    record = _record(fetched=NOW)
    held = _held(record, tmp_path)
    _asking(monkeypatch, [pulls.PullProbe("checks_changed", {})])
    clock = [NOW]
    read = _reading(monkeypatch, record, clock)
    _observe_core(100)
    gh_budget.observe(
        {
            "x-ratelimit-limit": "5000",
            "x-ratelimit-remaining": "100",
            "x-ratelimit-reset": str(int((NOW + timedelta(hours=1)).timestamp())),
            "x-ratelimit-resource": "graphql",
        },
        resource="graphql",
    )
    asyncio.run(held.probe(record, status=_unknown(record)))
    assert held.status_below_floor(NOW) and held.automatic_due(NOW) == "full"
    asyncio.run(held.refresh({"page"}))
    assert read == ["status"]


def test_a_lagging_read_with_no_issue_etag_is_read_again_once_a_window(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A3: the guard keys on the issue's ``updated_at``, which a probe has without an ETag.
    Before, every probe started the read again: four in 24 s."""

    record = _record(state="closed", fetched=NOW)
    held = _held(record, tmp_path)
    ahead = _stamp(NOW + timedelta(seconds=30))
    _probing(monkeypatch, [pulls.PullProbe("changed", {}, None, ahead)] * 4)
    clock = [NOW]
    monkeypatch.setattr(pulls, "utc_now", lambda: clock[0])

    async def refresh(*_args: object, **_kwargs: object) -> PullRecord:
        return record.model_copy(update={"fetched_at": _stamp(clock[0])})

    monkeypatch.setattr(pulls, "refresh_pull_request", refresh)
    reads = 0
    current = record
    for _round in range(4):
        asyncio.run(held.probe(current))
        if held.automatic_due(clock[0]) == "full":
            clock[0] += timedelta(seconds=1)
            asyncio.run(held.refresh({"page"}))
            reads += 1
            current = record.model_copy(update={"fetched_at": held.fetched_at})
        clock[0] += timedelta(seconds=ATTENDED_PROBE_S)
    assert clock[0] - NOW < WINDOW and reads == 1


def test_below_the_floor_a_lagging_read_is_tried_again_after_a_window_and_not_before(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A5: below the floor the clock asks for nothing, so only the guard's own window
    brings the read of a change back; without it the change is never read again."""

    record = _record(state="closed", fetched=NOW)
    held = _held(record, tmp_path)
    ahead = pulls.IssueSeen(_stamp(NOW + timedelta(seconds=30)), 'W/"ahead"')
    _probing(monkeypatch, [pulls.PullProbe("changed", {}, ahead, ahead.updated_at)] * 3)
    clock = [NOW]
    monkeypatch.setattr(pulls, "utc_now", lambda: clock[0])
    _observe_core(100)
    asyncio.run(held.probe(record))
    assert held.automatic_due(NOW) == "full"

    async def refresh(*_args: object, **_kwargs: object) -> PullRecord:
        return record.model_copy(update={"fetched_at": _stamp(clock[0])})

    monkeypatch.setattr(pulls, "refresh_pull_request", refresh)
    clock[0] = NOW + timedelta(seconds=1)
    asyncio.run(held.refresh({"page"}))
    lagging = record.model_copy(update={"fetched_at": held.fetched_at})
    clock[0] = NOW + timedelta(seconds=ATTENDED_PROBE_S + 1)
    asyncio.run(held.probe(lagging))
    assert held.below_floor(clock[0]) and held.automatic_due(clock[0]) is None
    clock[0] = NOW + WINDOW + timedelta(seconds=2)
    assert held.automatic_due(clock[0]) == "probe"
    asyncio.run(held.probe(lagging))
    assert held.automatic_due(clock[0]) == "full"


def test_an_issue_answer_older_than_the_record_is_neither_vouched_for_nor_read(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A8: the issue's answer lags the pull's the record was read from."""

    record = _record(state="closed", fetched=NOW)
    held = _held(record, tmp_path)
    older = _stamp(NOW - timedelta(days=1))
    _probing(monkeypatch, [pulls.PullProbe("behind", {}, None, older)])
    monkeypatch.setattr(pulls, "utc_now", lambda: NOW)
    asyncio.run(held.probe(record))
    assert held.probed_at is None and held.automatic_due(NOW) is None
    # Nor is it a failed probe: the next one runs at its interval.
    assert held.automatic_due(NOW + timedelta(seconds=ATTENDED_PROBE_S)) == "probe"


def test_past_the_cap_the_pull_requests_refused_go_first_so_all_take_turns(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A4: eight asked in the same order every round. Before, the first four were probed
    every round and the others never."""

    record = _record(state="closed", fetched=NOW)
    published = ListedRepository(home=tmp_path, slug="demo", owner="octo", repo="demo")
    clock = [NOW]
    monkeypatch.setattr(pulls, "utc_now", lambda: clock[0])
    probed: list[int] = []
    rounds = 5

    async def run() -> None:
        ended = [asyncio.Event()]

        async def probe(*_args: object, **_kwargs: object) -> pulls.PullProbe:
            await ended[0].wait()
            return pulls.PullProbe("unchanged", {})

        monkeypatch.setattr(pulls, "probe_pull_request", probe)
        held = [
            ServedPull(published=published, number=number, fetched_at=record.fetched_at)
            for number in range(1, 2 * served_pull.MAX_PROBES_IN_FLIGHT + 1)
        ]
        for _round in range(rounds):
            # Every probe of a round runs until all eight have asked.
            ended[0] = asyncio.Event()
            waits: list[asyncio.Future[None]] = []
            for pull in held:
                if pull.automatic_due(clock[0]) == "probe":
                    probed.append(pull.number)
                    waits.append(asyncio.ensure_future(pull.probe(record)))
                    for _turn in range(3):
                        await asyncio.sleep(0)
            ended[0].set()
            await asyncio.gather(*waits)
            clock[0] += timedelta(seconds=ATTENDED_PROBE_S)

    asyncio.run(run())
    cap = served_pull.MAX_PROBES_IN_FLIGHT
    assert len(probed) == rounds * cap
    counts = {number: probed.count(number) for number in range(1, 2 * cap + 1)}
    assert min(counts.values()) >= rounds // 2, counts
    # A finished probe is forgotten, so the set does not grow by one a probe.
    assert not served_pull._PROBES  # pyright: ignore[reportPrivateUsage]


def test_a_refused_pull_request_that_never_asks_again_holds_no_one_back_for_long(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A4: a page that went away keeps its turn for PROBE_TURN_S and no longer."""

    record = _record(state="closed", fetched=NOW)
    published = ListedRepository(home=tmp_path, slug="demo", owner="octo", repo="demo")
    first, gone, later = (
        ServedPull(published=published, number=number, fetched_at=record.fetched_at)
        for number in (1, 2, 3)
    )
    monkeypatch.setattr(served_pull, "MAX_PROBES_IN_FLIGHT", 1)
    monkeypatch.setattr(pulls, "utc_now", lambda: NOW)

    async def run() -> None:
        release = asyncio.Event()

        async def probe(*_args: object, **_kwargs: object) -> pulls.PullProbe:
            await release.wait()
            return pulls.PullProbe("unchanged", {})

        monkeypatch.setattr(pulls, "probe_pull_request", probe)
        running = asyncio.ensure_future(first.probe(record))
        for _turn in range(3):
            await asyncio.sleep(0)
        assert not gone.probe_due(NOW)
        release.set()
        await running

    asyncio.run(run())
    soon = NOW + timedelta(seconds=1)
    assert not later.probe_due(soon)
    assert later.probe_due(NOW + timedelta(seconds=served_pull.PROBE_TURN_S + 1))


def test_cancelling_a_request_that_waits_on_a_probe_cancels_the_request_and_not_the_probe(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A5: a cancelled request must end cancelled, whatever becomes of the probe."""

    record = _record(state="closed", fetched=NOW)
    held = _held(record, tmp_path)
    monkeypatch.setattr(pulls, "utc_now", lambda: NOW)

    async def run() -> None:
        release = asyncio.Event()

        async def probe(*_args: object, **_kwargs: object) -> pulls.PullProbe:
            await release.wait()
            return pulls.PullProbe("unchanged", {})

        monkeypatch.setattr(pulls, "probe_pull_request", probe)
        coordinator = RefreshCoordinator()
        asking = asyncio.ensure_future(held.probe(record, coordinator=coordinator))
        for _turn in range(3):
            await asyncio.sleep(0)
        asking.cancel()
        with pytest.raises(asyncio.CancelledError):
            await asking
        assert asking.cancelled() and held.probing
        release.set()
        await coordinator.drain(timeout_s=5)
        await coordinator.aclose()

    asyncio.run(run())
    assert held.probed_at == _stamp(NOW)


def test_a_probe_takes_no_network_slot_so_it_does_not_queue_behind_a_fetch(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A5: every slot is taken by a job that does not end, and the probe still runs."""

    record = _record(state="closed", fetched=NOW)
    held = _held(record, tmp_path)
    _probing(monkeypatch, [pulls.PullProbe("unchanged", {})])
    monkeypatch.setattr(pulls, "utc_now", lambda: NOW)
    monkeypatch.setattr(served_pull, "PROBE_WAIT_S", 0.5)

    async def run() -> None:
        coordinator = RefreshCoordinator(limit=1)
        fetching = asyncio.Event()

        async def fetch() -> None:
            fetching.set()
            await asyncio.Event().wait()

        coordinator.start("a fetch", fetch)
        await fetching.wait()
        await held.probe(record, coordinator=coordinator)
        assert coordinator.running("a fetch")
        await coordinator.aclose()

    asyncio.run(run())
    assert held.probed_at == _stamp(NOW)


def test_a_probe_asked_of_a_closed_coordinator_starts_nothing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A7: it raised ``RuntimeError``, which the route answered with a 500."""

    record = _record(state="closed", fetched=NOW)
    held = _held(record, tmp_path)
    asked = _probing(monkeypatch, [pulls.PullProbe("unchanged", {})])
    monkeypatch.setattr(pulls, "utc_now", lambda: NOW)

    async def run() -> None:
        coordinator = RefreshCoordinator()
        await coordinator.aclose()
        await held.probe(record, coordinator=coordinator)

    asyncio.run(run())
    assert asked == [] and held.probed_at is None and not held.probing
    assert held.probe_due(NOW)


def test_a_cancelled_refresh_forgets_the_change_it_was_started_for(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A5: a read that never ran did not fail to bring the change, so the lag guard does
    not hold the next probe's read of it."""

    record = _record(state="closed", fetched=NOW)
    held = _held(record, tmp_path)
    ahead = _stamp(NOW + timedelta(seconds=30))
    _probing(monkeypatch, [pulls.PullProbe("changed", {}, None, ahead)] * 2)
    clock = [NOW]
    monkeypatch.setattr(pulls, "utc_now", lambda: clock[0])
    # An earlier attempt inside the window, as a failed or checks_only read leaves.
    held._last_attempt = NOW - timedelta(seconds=10)  # pyright: ignore[reportPrivateUsage]
    asyncio.run(held.probe(record))
    assert held.automatic_due(NOW) == "full"

    async def run() -> None:
        started = asyncio.Event()

        async def slow(*_args: object, **_kwargs: object) -> PullRecord:
            started.set()
            await asyncio.Event().wait()
            raise AssertionError("not reached")

        monkeypatch.setattr(pulls, "refresh_pull_request", slow)
        task = asyncio.ensure_future(held.refresh({"page"}))
        await started.wait()
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task

    asyncio.run(run())
    # Another writer publishes a record that is no further on, which forgets what the
    # probes of the one before found; the next probe finds the same change.
    clock[0] = NOW + timedelta(seconds=ATTENDED_PROBE_S)
    other = record.model_copy(update={"fetched_at": _stamp(clock[0])})
    held.saw_record(other.fetched_at)
    assert held.automatic_due(clock[0]) == "probe"
    asyncio.run(held.probe(other))
    assert held.automatic_due(clock[0]) == "full"


def test_what_a_probe_saw_of_the_issue_is_kept_when_a_newer_record_arrived_meanwhile(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A5: the ETag is the issue's, whichever record the probe ran beside."""

    record = _record(state="closed", fetched=NOW)
    held = _held(record, tmp_path)
    seen = pulls.IssueSeen(record.pull.updated_at, 'W/"issue"')
    newer = record.model_copy(update={"fetched_at": _stamp(NOW + timedelta(seconds=1))})
    sent: list[pulls.IssueSeen | None] = []

    async def probe(_published: object, _record: object, **kwargs: Any) -> pulls.PullProbe:
        sent.append(kwargs["seen"])
        held.saw_record(newer.fetched_at)
        return pulls.PullProbe("unchanged", {}, seen, seen.updated_at)

    monkeypatch.setattr(pulls, "probe_pull_request", probe)
    monkeypatch.setattr(pulls, "utc_now", lambda: NOW)
    asyncio.run(held.probe(record))
    assert held.probed_at is None
    asyncio.run(held.probe(newer))
    assert sent == [None, seen]


# ── Review B of #726 ───────────────────────────────────────────


@pytest.mark.parametrize(
    "askers",
    [
        13,
        served_pull.MAX_KEPT_PULLS,
        served_pull.MAX_KEPT_PULLS + 1,
        2 * served_pull.MAX_KEPT_PULLS,
    ],
)
def test_however_many_ask_past_the_cap_each_that_keeps_asking_is_probed(askers: int) -> None:
    """B1: a refusal kept the time it was first made and lapsed two intervals later, so
    with the cap at four the thirteenth asker onward went to the back each time and was
    never probed. A refusal renewed each time it is refused lapses only when its asker
    stops asking. D1 of review D on #726: past ``MAX_KEPT_PULLS`` askers each new refusal
    evicted the asker whose turn was next, so after the first round none was probed: 4 of
    240 probes in 60 rounds at 65 askers, and 61 never probed."""

    cap = served_pull.MAX_PROBES_IN_FLIGHT
    assert askers > 3 * cap
    rounds = 60
    counts = dict.fromkeys(range(1, askers + 1), 0)

    async def run() -> None:
        loop = asyncio.get_running_loop()
        for turn in range(rounds):
            started: list[asyncio.Future[None]] = []
            for asker in counts:
                # Every asker of a round asks in the same order, a millisecond apart.
                now = NOW + timedelta(seconds=ATTENDED_PROBE_S * turn + 0.001 * asker)
                if served_pull._may_probe(f"demo:pull/{asker}", now):  # pyright: ignore[reportPrivateUsage]
                    probe: asyncio.Future[None] = loop.create_future()
                    served_pull._PROBES.add(probe)  # pyright: ignore[reportPrivateUsage]
                    started.append(probe)
                    counts[asker] += 1
            assert len(started) == cap
            # Each probe of a round ends before the next round asks.
            for probe in started:
                probe.set_result(None)
            served_pull._PROBES.clear()  # pyright: ignore[reportPrivateUsage]

    asyncio.run(run())
    # Not evenly, since a round's four go in the order they ask, but none is left out:
    # each has at least two thirds of an even share.
    share = rounds * cap // askers
    assert min(counts.values()) >= max(1, 2 * share // 3), counts


def test_the_pull_requests_the_cap_remembers_refusing_are_bounded(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """B3: request text decides how many ask."""

    monkeypatch.setattr(served_pull, "MAX_PROBES_IN_FLIGHT", 0)
    for asker in range(served_pull.MAX_KEPT_PULLS + 5):
        assert not served_pull._may_probe(f"demo:pull/{asker}", NOW)  # pyright: ignore[reportPrivateUsage]
    refused = served_pull._REFUSED  # pyright: ignore[reportPrivateUsage]
    assert len(refused) == served_pull.MAX_KEPT_PULLS
    # Those remembered keep their places, and the newest are not remembered (review D1 of
    # #726: forgetting the oldest forgot whose turn was next).
    assert next(iter(refused)) == "demo:pull/0"
    assert f"demo:pull/{served_pull.MAX_KEPT_PULLS}" not in refused


def test_a_remembered_asker_that_keeps_asking_keeps_its_place_while_the_cap_is_full(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A4 of review A on #761: a refusal remembered is renewed by each ask, though the queue
    is full, so its asker keeps its place past ``PROBE_TURN_S`` while it keeps asking.
    Renewed only while there was room, it lapsed a turn after its first refusal and came
    back at the end, behind refusals that never asked again."""

    monkeypatch.setattr(served_pull, "MAX_PROBES_IN_FLIGHT", 0)
    refused = served_pull._REFUSED  # pyright: ignore[reportPrivateUsage]
    keeper = "demo:pull/1"
    assert not served_pull._may_probe(keeper, NOW)  # pyright: ignore[reportPrivateUsage]
    # Refusals that never ask again fill the queue, half an interval later.
    filled = NOW + timedelta(seconds=ATTENDED_PROBE_S / 2)
    for asker in range(2, served_pull.MAX_KEPT_PULLS + 1):
        assert not served_pull._may_probe(f"demo:pull/{asker}", filled)  # pyright: ignore[reportPrivateUsage]
    assert len(refused) == served_pull.MAX_KEPT_PULLS
    asks = 3
    for turn in range(1, asks + 1):
        now = NOW + timedelta(seconds=ATTENDED_PROBE_S * turn)
        assert not served_pull._may_probe(keeper, now)  # pyright: ignore[reportPrivateUsage]
        assert (next(iter(refused)), refused[keeper][0]) == (keeper, now)
    assert ATTENDED_PROBE_S * asks > served_pull.PROBE_TURN_S


def test_a_settle_wait_that_lapsed_unanswered_is_renewed_for_a_record_read_long_after(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """B2: one probe finds it unknown, GitHub has not answered, and the page is hidden.
    Ten minutes on its full read stores unknown again for the same head. Before, the pull
    was never asked for that record and no probe vouched for it."""

    record = _record(fetched=NOW)
    held = _held(record, tmp_path)
    asked = _asking(monkeypatch, [pulls.PullProbe("unchanged", {})] * 12)
    clock = [NOW]
    monkeypatch.setattr(pulls, "utc_now", lambda: clock[0])
    asyncio.run(held.probe(record, status=_unknown(record)))
    assert asked == [(True, False)]
    clock[0] = NOW + timedelta(minutes=10)
    again = record.model_copy(update={"fetched_at": _stamp(clock[0])})
    held.saw_record(again.fetched_at)
    for _probe in range(3):
        clock[0] += timedelta(seconds=ATTENDED_PROBE_S)
        asyncio.run(held.probe(again, status=_unknown(again)))
    assert asked[1:] == [(True, False)] * 3 and held.probed_at == _stamp(clock[0])
    # The renewed wait is bounded as the first was, and records read meanwhile, as a
    # refresh publishes after each push, renew nothing before FULL_REFRESH_S.
    renewed = clock[0] - timedelta(seconds=2 * ATTENDED_PROBE_S)
    clock[0] = renewed + timedelta(seconds=served_pull.MERGEABLE_SETTLE_S + ATTENDED_PROBE_S)
    newer = record.model_copy(update={"fetched_at": _stamp(clock[0])})
    held.saw_record(newer.fetched_at)
    asyncio.run(held.probe(newer, status=_unknown(newer)))
    assert asked[-1] == (False, False)
    clock[0] = renewed + timedelta(seconds=FULL_REFRESH_S - 1)
    asyncio.run(held.probe(newer, status=_unknown(newer)))
    assert asked[-1] == (False, False)
    clock[0] = renewed + timedelta(seconds=FULL_REFRESH_S)
    asyncio.run(held.probe(newer, status=_unknown(newer)))
    assert asked[-1] == (True, False)
    # A record read before the wait ended is the one the wait was for: it renews nothing.
    clock[0] += timedelta(seconds=FULL_REFRESH_S)
    asyncio.run(held.probe(newer, status=_unknown(newer)))
    assert asked[-1] == (False, False)


def test_a_probe_that_fails_does_not_spend_the_settle_wait(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """B2: a failed probe holds the next for a freshness window, which is longer than
    MERGEABLE_SETTLE_S, so the wait was over when probes resumed and the pull was never
    asked."""

    assert FRESHNESS_WINDOW_S > served_pull.MERGEABLE_SETTLE_S
    record = _record(fetched=NOW)
    held = _held(record, tmp_path)
    asked: list[bool] = []
    failing = [True]

    async def probe(_published: object, _record: object, **kwargs: Any) -> pulls.PullProbe:
        asked.append(bool(kwargs["mergeability"]))
        if failing[0]:
            failing[0] = False
            raise pulls.PullDataError("network_error", "no route")
        return pulls.PullProbe("unchanged", {})

    monkeypatch.setattr(pulls, "probe_pull_request", probe)
    clock = [NOW]
    monkeypatch.setattr(pulls, "utc_now", lambda: clock[0])
    asyncio.run(held.probe(record, status=_unknown(record)))
    clock[0] = NOW + WINDOW + timedelta(seconds=1)
    assert held.probe_due(clock[0])
    asyncio.run(held.probe(record, status=_unknown(record)))
    assert asked == [True, True] and held.probed_at == _stamp(clock[0])


def test_a_head_that_moves_while_mergeability_is_unknown_has_a_wait_of_its_own(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """B3: the wait is a head's, and GitHub computes afresh for a new one."""

    record = _record(fetched=NOW)
    held = _held(record, tmp_path)
    asked = _asking(monkeypatch, [pulls.PullProbe("unchanged", {})] * 3)
    clock = [NOW]
    monkeypatch.setattr(pulls, "utc_now", lambda: clock[0])
    asyncio.run(held.probe(record, status=_unknown(record)))
    clock[0] = NOW + timedelta(seconds=served_pull.MERGEABLE_SETTLE_S + ATTENDED_PROBE_S)
    asyncio.run(held.probe(record, status=_unknown(record)))
    assert asked == [(True, False), (False, False)]
    pushed = _record(fetched=clock[0], head=NEWER_HEAD)
    held.saw_record(pushed.fetched_at)
    clock[0] += timedelta(seconds=ATTENDED_PROBE_S)
    asyncio.run(held.probe(pushed, status=_unknown(pushed)))
    assert asked[-1] == (True, False)


def test_over_the_process_ceiling_probes_slow_to_the_full_read_and_full_reads_to_five_minutes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from metabrowser.builtin_plugins.github import gh_budget

    record = _record(state="closed", fetched=NOW)
    held = _held(record, tmp_path)
    _probing(monkeypatch, [pulls.PullProbe("unchanged", {}), pulls.PullProbe("changed", {})])
    clock = [NOW]
    monkeypatch.setattr(pulls, "utc_now", lambda: clock[0])
    asyncio.run(held.probe(record))
    # The record was read in full just now.
    held._last_attempt = NOW  # pyright: ignore[reportPrivateUsage]
    gh_budget.spent(gh_budget.AUTOMATIC_CORE_PER_HOUR, now=NOW)
    try:
        # The next probe waits FULL_REFRESH_S, not PROBE_FLOOR_S, and the read the window
        # would start once no probe vouches waits with it.
        assert held.automatic_due(NOW + timedelta(seconds=ATTENDED_PROBE_S)) is None
        assert held.automatic_due(NOW + timedelta(seconds=FULL_REFRESH_S - 1)) is None
        # A change a probe finds waits five minutes from the last read.
        clock[0] = NOW + timedelta(seconds=FULL_REFRESH_S)
        assert held.automatic_due(clock[0]) == "probe"
        asyncio.run(held.probe(record))
        assert held._probe_saw == "pull"  # pyright: ignore[reportPrivateUsage]
        assert held.automatic_due(clock[0]) is None
        ceiling = timedelta(seconds=gh_budget.CEILING_FULL_READ_S)
        assert held.automatic_due(NOW + ceiling) is None
        assert held.automatic_due(NOW + ceiling + timedelta(seconds=1)) == "full"
        # Once the hour has rolled, the change is read at once again.
        gh_budget.forget()
        assert held.automatic_due(clock[0]) == "full"
    finally:
        gh_budget.forget()
