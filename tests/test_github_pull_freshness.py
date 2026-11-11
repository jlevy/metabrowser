"""A cached record checked against the catalog's row: current, changed, checks, or unverified.

The route transcripts show the envelope fields; these pin the verdict table, pending
checks, and the held state's due rule, including its loop guard, the checks an open pull
request reads once a window, and a cancelled attempt.
"""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import pytest

from metabrowser.builtin_plugins.github import pulls
from metabrowser.builtin_plugins.github.pull_catalog import CatalogState
from metabrowser.builtin_plugins.github.pull_freshness import (
    NO_CHECKS_GRACE_S,
    SCAN_GRACE_S,
    checks_pending,
    record_freshness,
)
from metabrowser.builtin_plugins.github.pull_list import ListedRepository, PullListRow
from metabrowser.builtin_plugins.github.pull_record import (
    PULL_RECORD_PROJECTION,
    PULL_RECORD_SCHEMA,
    PullRecord,
)
from metabrowser.builtin_plugins.github.pull_route import pull_state
from metabrowser.builtin_plugins.github.served_pull import ServedPull
from metabrowser.mirror_refresh import FRESHNESS_WINDOW_S

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
    mergeable: str = "mergeable",
    runs: tuple[str, ...] = ("completed",),
    status: str | None = None,
    reader: str = READER,
) -> PullRecord:
    side: dict[str, Any] = {"ref": "topic", "sha": "c" * 40, "repository": "octo/demo"}
    return PullRecord.model_validate(
        {
            "schema_version": PULL_RECORD_SCHEMA,
            "projection_version": PULL_RECORD_PROJECTION,
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
                "mergeable": mergeable,
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
            "check_runs": [
                {
                    "id": index,
                    "name": f"check {index}",
                    "status": run,
                    "conclusion": "success" if run == "completed" else None,
                    "details_url": None,
                    "app": None,
                }
                for index, run in enumerate(runs, start=1)
            ],
            "status": None
            if status is None
            else {
                "state": status,
                "statuses": [
                    {"context": "ci", "state": status, "description": None, "target_url": None}
                ],
            },
            "comparison": None,
            "truncated": {
                "issue_comments": False,
                "reviews": False,
                "review_comments": False,
                "check_runs": False,
                "statuses": False,
                "text": False,
            },
            "unavailable": {},
        }
    )


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
    verdict = record_freshness(record, _catalog(), _row(), now=NOW)
    assert verdict.verdict == "current" and verdict.verified_by == "catalog"
    assert verdict.verified_at == _stamp(NOW - timedelta(seconds=20))
    assert not verdict.head_moved and verdict.changed_row is None
    assert pull_state(record, now=NOW, freshness=verdict) == ("current", None)
    # Without the verdict the same record is two hours past the window.
    assert pull_state(record, now=NOW) == ("stale", None)


@pytest.mark.parametrize(
    "changes",
    [{"runs": ()}, {"runs": ("completed",)}, {"mergeable": "mergeable"}],
    ids=["no checks registered yet", "completed checks a re-run restarts", "a base that moved"],
)
def test_an_open_record_past_the_window_has_its_checks_read_again(changes: dict[str, Any]) -> None:
    """Review A1: ``updated_at`` vouches for the conversation and head, not for checks.

    A check run, a commit status, and ``mergeable`` move without it: CI that registers
    after the record was read, a re-run of settled checks, a conflict a moved base made.
    So an open record read longer ago than the window is ``checks``, stale, and a fresh one
    is current.
    """

    record = _record(**changes)
    verdict = record_freshness(record, _catalog(), _row(), now=NOW)
    assert (verdict.verdict, verdict.verified_by, verdict.head_moved) == (
        "checks",
        "catalog",
        False,
    )
    assert verdict.verified_at == _stamp(NOW - timedelta(seconds=20))
    assert pull_state(record, now=NOW, freshness=verdict) == ("stale", None)
    young = _record(fetched=NOW - WINDOW + timedelta(seconds=1), **changes)
    assert record_freshness(young, _catalog(), _row(), now=NOW).verdict == "current"


def test_a_record_fetched_after_the_scan_is_verified_by_its_own_fetch_time() -> None:
    record = _record(fetched=NOW - timedelta(seconds=5))
    verdict = record_freshness(record, _catalog(), _row(), now=NOW)
    assert verdict.verdict == "current" and verdict.verified_at == record.fetched_at


def test_a_newer_row_makes_the_record_changed_whatever_the_scan_age() -> None:
    record = _record()
    for scanned in (NOW - timedelta(seconds=5), NOW - timedelta(hours=1)):
        verdict = record_freshness(
            record, _catalog(fetched=scanned), _row(updated=NOW - timedelta(minutes=30)), now=NOW
        )
        assert verdict.verdict == "changed" and not verdict.head_moved
        assert verdict.verified_by == "fetch" and verdict.verified_at == record.fetched_at
        assert verdict.changed_row == f"{_stamp(NOW - timedelta(minutes=30))} {HEAD}"
        assert pull_state(record, now=NOW, freshness=verdict) == ("stale", None)


def test_a_newer_row_with_another_head_says_the_head_moved() -> None:
    newer = _row(updated=NOW - timedelta(minutes=1), head=NEWER_HEAD)
    assert record_freshness(_record(), _catalog(), newer, now=NOW).head_moved
    # A row written before the catalog read heads cannot say it moved.
    unknown = _row(updated=NOW - timedelta(minutes=1), head=None)
    verdict = record_freshness(_record(), _catalog(), unknown, now=NOW)
    assert verdict.verdict == "changed" and not verdict.head_moved


def test_another_head_at_the_same_update_time_is_a_change() -> None:
    """Review A5: ``updated_at`` has whole seconds, and a push within the record's second
    leaves the times equal and the head not."""

    record = _record(state="closed")
    tie = _row(updated=NOW - timedelta(hours=3), head=NEWER_HEAD)
    verdict = record_freshness(record, _catalog(), tie, now=NOW)
    assert (verdict.verdict, verdict.head_moved) == ("changed", True)
    same = record_freshness(record, _catalog(), _row(updated=NOW - timedelta(hours=3)), now=NOW)
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
    verdict = record_freshness(record, catalog, row, now=NOW)
    assert verdict.verdict == "unverified" and verdict.verified_by == "fetch"
    assert verdict.verified_at == record.fetched_at
    assert pull_state(record, now=NOW, freshness=verdict) == ("stale", None)


def test_another_readers_newer_row_says_nothing() -> None:
    newer = _row(updated=NOW - timedelta(minutes=1), head=NEWER_HEAD)
    verdict = record_freshness(_record(), _catalog(reader="gh:someone-else"), newer, now=NOW)
    assert verdict.verdict == "unverified" and not verdict.head_moved


@pytest.mark.parametrize(
    "changes",
    [
        {"runs": ("completed", "in_progress")},
        {"runs": ("queued",)},
        {"status": "pending"},
        {"mergeable": "unknown"},
    ],
    ids=["a run in progress", "a queued run", "a pending status", "mergeability unknown"],
)
def test_pending_checks_keep_their_own_age(changes: dict[str, Any]) -> None:
    record = _record(**changes)
    assert checks_pending(record)
    verdict = record_freshness(record, _catalog(), _row(), now=NOW)
    assert verdict.verdict == "checks" and verdict.checks_pending
    assert pull_state(record, now=NOW, freshness=verdict) == ("stale", None)
    young = _record(fetched=NOW - timedelta(seconds=10), **changes)
    assert pull_state(
        young, now=NOW, freshness=record_freshness(young, _catalog(), _row(), now=NOW)
    ) == (
        "current",
        None,
    )


def test_settled_or_closed_checks_are_not_pending() -> None:
    assert not checks_pending(_record(status="success"))
    assert not checks_pending(_record(state="closed", runs=("in_progress",), mergeable="unknown"))


def test_no_checks_read_soon_after_an_update_are_pending_for_a_bounded_time() -> None:
    """CI that has not registered yet: no check run and no status, read just after a push."""

    updated = NOW - timedelta(hours=3)
    soon = _record(runs=(), updated=updated, fetched=updated + timedelta(seconds=5))
    assert checks_pending(soon)
    bound = updated + timedelta(seconds=NO_CHECKS_GRACE_S)
    assert checks_pending(_record(runs=(), updated=updated, fetched=bound))
    later = _record(runs=(), updated=updated, fetched=bound + timedelta(seconds=1))
    assert not checks_pending(later)
    # A repository with no CI is not pending forever, and a closed one never.
    assert not checks_pending(_record(runs=(), state="closed", updated=updated, fetched=updated))


# ── The held state's due rule ──────────────────────────────────


def _held(record: PullRecord, tmp_path: Path) -> ServedPull:
    published = ListedRepository(home=tmp_path, slug="demo", owner="octo", repo="demo")
    return ServedPull(published=published, number=7, fetched_at=record.fetched_at)


def test_a_vouched_record_is_not_due_and_a_changed_one_is_due_at_once(tmp_path: Path) -> None:
    record = _record(state="closed")
    held = _held(record, tmp_path)
    assert held.is_stale(NOW, window_s=FRESHNESS_WINDOW_S)
    held.saw_record(
        record.fetched_at, freshness=record_freshness(record, _catalog(), _row(), now=NOW)
    )
    assert not held.is_stale(NOW, window_s=FRESHNESS_WINDOW_S)
    # Vouched twenty seconds ago, so fresh for forty more.
    assert held.is_stale(NOW + timedelta(seconds=41), window_s=FRESHNESS_WINDOW_S)

    changed = record_freshness(
        record, _catalog(), _row(updated=NOW - timedelta(minutes=1)), now=NOW
    )
    held.saw_record(record.fetched_at, freshness=changed)
    assert held.is_stale(NOW, window_s=FRESHNESS_WINDOW_S)


def test_a_change_an_attempt_already_saw_waits_a_window(tmp_path: Path) -> None:
    """A REST answer that lags the catalog leaves the record changed; it cannot loop."""

    record = _record(fetched=NOW - timedelta(seconds=30))
    held = _held(record, tmp_path)
    changed = record_freshness(
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
    first = record_freshness(
        record, _catalog(published=NOW - timedelta(seconds=20)), reported, now=NOW
    )
    held.saw_record(record.fetched_at, freshness=first)
    held._attempted_row = first.changed_row  # pyright: ignore[reportPrivateUsage]
    held._last_attempt = NOW - timedelta(seconds=10)  # pyright: ignore[reportPrivateUsage]
    again = record_freshness(
        record, _catalog(published=NOW - timedelta(seconds=1)), reported, now=NOW
    )
    held.saw_record(record.fetched_at, freshness=again)
    assert not held.is_stale(NOW, window_s=FRESHNESS_WINDOW_S)
    another = _row(updated=NOW - timedelta(seconds=2), head=NEWER_HEAD)
    held.saw_record(
        record.fetched_at, freshness=record_freshness(record, _catalog(), another, now=NOW)
    )
    assert held.is_stale(NOW, window_s=FRESHNESS_WINDOW_S)


def test_an_open_records_checks_are_read_once_a_window_on_their_own(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Review A1: the visible page's automatic refresh asks for the checks alone."""

    record = _record()
    held = _held(record, tmp_path)
    held.saw_record(
        record.fetched_at, freshness=record_freshness(record, _catalog(), _row(), now=NOW)
    )
    assert held.checks_due and held.is_stale(NOW, window_s=FRESHNESS_WINDOW_S)
    asked: list[dict[str, object]] = []

    async def refresh(*_args: object, **kwargs: object) -> PullRecord:
        asked.append(kwargs)
        return record.model_copy(update={"fetched_at": _stamp(NOW)})

    monkeypatch.setattr(pulls, "refresh_pull_request", refresh)
    monkeypatch.setattr(pulls, "utc_now", lambda: NOW)
    asyncio.run(held.refresh())
    assert asked == [{"adopt_current": False, "checks_only": True}]
    assert not held.checks_due and not held.is_stale(NOW, window_s=FRESHNESS_WINDOW_S)
    # A reader's own refresh, and a changed record's, read everything.
    held.checks_due = True
    held.request_recovery()
    asyncio.run(held.refresh())
    assert asked[-1] == {"recover": True, "recovery_pair": None, "adopt_current": False}


def test_a_verdict_on_another_record_is_not_adopted(tmp_path: Path) -> None:
    record = _record()
    held = _held(record, tmp_path)
    newer = _stamp(NOW - timedelta(seconds=1))
    held.saw_record(newer)
    held.saw_record(
        record.fetched_at, freshness=record_freshness(record, _catalog(), _row(), now=NOW)
    )
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
        task = asyncio.ensure_future(held.refresh())
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
    assert record_freshness(record, old, _row(), now=NOW).verdict == "unverified"
    verdict = record_freshness(record, old, _row(), now=NOW, scanning=True)
    assert verdict.verdict == "current" and verdict.verified_at == old.fetched_at
    # A change the last scan saw still decides as before, and an open record's checks.
    newer = _row(updated=NOW - timedelta(minutes=5))
    assert record_freshness(record, old, newer, now=NOW, scanning=True).verdict == "changed"
    assert record_freshness(_record(), old, _row(), now=NOW, scanning=True).verdict == "checks"
    edge = _catalog(fetched=NOW - WINDOW - timedelta(seconds=SCAN_GRACE_S))
    assert record_freshness(record, edge, _row(), now=NOW, scanning=True).verdict == "current"
    for age in (WINDOW + timedelta(seconds=SCAN_GRACE_S + 1), timedelta(hours=3)):
        stale = _catalog(fetched=NOW - age)
        verdict = record_freshness(record, stale, _row(), now=NOW, scanning=True)
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
