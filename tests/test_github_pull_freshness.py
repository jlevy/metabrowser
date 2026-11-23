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

from metabrowser.builtin_plugins.github import gh_budget, pulls, served_pull
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
from metabrowser.builtin_plugins.github.served_pull import (
    ATTENDED_PROBE_S,
    CHECKS_PROBE_S,
    FULL_REFRESH_S,
    PROBE_FLOOR_S,
    ServedPull,
    ServedPulls,
)
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
    mergeable: str = "mergeable",
    runs: tuple[str, ...] = ("completed",),
    status: str | None = None,
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
    verdict = record_freshness(record, _catalog(), _row(), now=NOW)
    assert (verdict.verdict, verdict.verified_by) == ("unverified", "fetch")
    assert verdict.verified_at == record.fetched_at
    assert pull_state(record, now=NOW, freshness=verdict) == ("stale", None)
    # The same record at this projection is one the catalog vouches for.
    vouched = _record(state="closed", fetched=NOW - timedelta(days=30))
    assert record_freshness(vouched, _catalog(), _row(), now=NOW).verdict == "current"
    held = _held(record, tmp_path)
    held.saw_record(record.fetched_at, freshness=verdict)
    assert held.is_stale(NOW, window_s=FRESHNESS_WINDOW_S)
    # Tried once, whether or not it succeeded, it waits a window.
    held._last_attempt = NOW - timedelta(seconds=10)  # pyright: ignore[reportPrivateUsage]
    assert not held.is_stale(NOW, window_s=FRESHNESS_WINDOW_S)
    # An open one is read in full too, not for its checks alone.
    opened = _record(fetched=NOW - timedelta(days=30), projection=earlier)
    assert record_freshness(opened, _catalog(), _row(), now=NOW).verdict == "unverified"
    newer = _row(updated=NOW - timedelta(minutes=1))
    assert record_freshness(record, _catalog(), newer, now=NOW).verdict == "changed"
    young = _record(state="closed", fetched=NOW - timedelta(seconds=10), projection=earlier)
    clock = record_freshness(young, _catalog(), _row(), now=NOW)
    assert clock.verdict == "unverified"
    assert pull_state(young, now=NOW, freshness=clock) == ("current", None)


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


def test_a_change_to_checks_alone_reads_them_alone(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A pending check run is probed with the pull, and a change reads only the checks."""

    record = _record(state="open", runs=("in_progress",), fetched=NOW)
    held = _held(record, tmp_path)
    asked = _probing(
        monkeypatch, [pulls.PullProbe("unchanged", {}), pulls.PullProbe("checks_changed", {})]
    )
    clock = [NOW]
    monkeypatch.setattr(pulls, "utc_now", lambda: clock[0])
    asyncio.run(held.probe(record))
    # The checks are probed only once every CHECKS_PROBE_S.
    clock[0] = NOW + timedelta(seconds=ATTENDED_PROBE_S)
    asyncio.run(held.probe(record))
    assert asked == [True, False]
    clock[0] = NOW + timedelta(seconds=CHECKS_PROBE_S)
    _probing(monkeypatch, [pulls.PullProbe("checks_changed", {})])
    asyncio.run(held.probe(record))
    assert held.automatic_due(clock[0]) == "full"
    refreshed: list[dict[str, object]] = []

    async def refresh(*_args: object, **kwargs: object) -> PullRecord:
        refreshed.append(kwargs)
        return record.model_copy(update={"fetched_at": _stamp(clock[0])})

    monkeypatch.setattr(pulls, "refresh_pull_request", refresh)
    asyncio.run(held.refresh())
    assert refreshed == [{"adopt_current": False, "checks_only": True}]
    # The new record is probed afresh, once ATTENDED_PROBE_S has passed since the last.
    assert held.probed_at is None and held.automatic_due(clock[0]) is None
    assert held.automatic_due(clock[0] + timedelta(seconds=ATTENDED_PROBE_S)) == "probe"


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


def test_settling_checks_a_probe_cannot_see_keep_the_window_cadence(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """With no status to probe, a pending record is read once a window, as before probes."""

    record = _record(state="open", runs=("in_progress",), fetched=NOW).model_copy(
        update={"status": None}
    )
    assert pulls.checks_probe_paths(_held(record, tmp_path).published, record) is None
    held = _held(record, tmp_path)
    _probing(monkeypatch, [pulls.PullProbe("unchanged", {})])
    monkeypatch.setattr(pulls, "utc_now", lambda: NOW + WINDOW - timedelta(seconds=1))
    asyncio.run(held.probe(record))
    assert held.probed_at is None
    assert held.automatic_due(NOW + WINDOW + timedelta(seconds=1)) == "full"


def test_a_full_read_comes_due_every_full_refresh_s_whatever_reads_only_checks(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """checks_only reads move fetched_at but not the full read's clock, and the read that
    interval makes due reads everything, even for a record whose checks alone are due."""

    record = _record(state="open", runs=("in_progress",), fetched=NOW)
    held = _held(record, tmp_path)
    held.saw_record(record.fetched_at)
    clock = [NOW]
    monkeypatch.setattr(pulls, "utc_now", lambda: clock[0])
    refreshed: list[bool] = []

    async def refresh(*_args: object, **kwargs: object) -> PullRecord:
        refreshed.append(bool(kwargs.get("checks_only")))
        return record.model_copy(update={"fetched_at": _stamp(clock[0])})

    monkeypatch.setattr(pulls, "refresh_pull_request", refresh)
    # CI changes the checks every few seconds; each change is a checks_only read.
    for seconds in (10, 40, 70):
        clock[0] = NOW + timedelta(seconds=seconds)
        held.checks_due = True
        asyncio.run(held.refresh())
    assert refreshed == [True, True, True]
    assert held.full_read_at == record.fetched_at
    clock[0] = NOW + timedelta(seconds=FULL_REFRESH_S + 1)
    assert held.automatic_due(clock[0]) == "full"
    held.checks_due = True
    asyncio.run(held.refresh())
    assert refreshed[-1] is False and held.full_read_at == _stamp(clock[0])
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


def test_the_checks_probes_keep_their_cadence_through_jitter_and_checks_only_reads(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Review B7 on #709: a probe a little early still asks the checks once CHECKS_PROBE_S
    is nearly up, and a checks_only read does not restart their clock."""

    record = _record(state="open", runs=("in_progress",), fetched=NOW)
    held = _held(record, tmp_path)
    asked = _probing(monkeypatch, [pulls.PullProbe("unchanged", {})] * 3)
    clock = [NOW]
    monkeypatch.setattr(pulls, "utc_now", lambda: clock[0])
    asyncio.run(held.probe(record))
    # Two probes PROBE_FLOOR_S apart reach the checks a little before CHECKS_PROBE_S.
    clock[0] = NOW + timedelta(seconds=PROBE_FLOOR_S)
    asyncio.run(held.probe(record))
    clock[0] = NOW + timedelta(seconds=2 * PROBE_FLOOR_S + 1)
    assert 2 * PROBE_FLOOR_S + 1 < CHECKS_PROBE_S
    asyncio.run(held.probe(record))
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
    held._full_asked = False  # pyright: ignore[reportPrivateUsage]

    _observe_core(int(gh_budget.BACKGROUND_FLOOR * 5000))
    assert held.below_floor(late)
    # The full read is as overdue as it was, and waits; the probe is what is due.
    assert held.full_read_overdue(late) and not held.full_read_due(late)
    assert not held.is_stale(late, window_s=FRESHNESS_WINDOW_S)
    assert held.automatic_due(late) == "probe"
    assert not held._full_asked  # pyright: ignore[reportPrivateUsage]
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


def test_below_the_floor_a_change_the_catalog_reports_is_read_and_a_checks_window_is_not(
    tmp_path: Path,
) -> None:
    record = _record(fetched=NOW - 2 * WINDOW)
    held = _held(record, tmp_path)
    _observe_core(100)
    # An open record the catalog vouches for has its checks read once a window: periodic.
    held.saw_record(
        record.fetched_at, freshness=record_freshness(record, _catalog(), _row(), now=NOW)
    )
    assert held.checks_due and not held.is_stale(NOW, window_s=FRESHNESS_WINDOW_S)
    # A row that says GitHub changed it is a change found on the page on screen.
    changed = record_freshness(
        record, _catalog(), _row(updated=NOW - timedelta(minutes=1)), now=NOW
    )
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
    _probing(monkeypatch, [pulls.PullProbe("changed", {}, ahead)] * 3)
    clock = [NOW]
    monkeypatch.setattr(pulls, "utc_now", lambda: clock[0])
    asyncio.run(held.probe(record))
    assert held.automatic_due(NOW) == "full"

    async def refresh(*_args: object, **_kwargs: object) -> PullRecord:
        # The pull as GitHub's pull endpoint still has it: the same ``updated_at``.
        return record.model_copy(update={"fetched_at": _stamp(clock[0])})

    monkeypatch.setattr(pulls, "refresh_pull_request", refresh)
    clock[0] = NOW + timedelta(seconds=1)
    asyncio.run(held.refresh())
    lagging = record.model_copy(update={"fetched_at": held.fetched_at})
    clock[0] = NOW + timedelta(seconds=ATTENDED_PROBE_S + 1)
    asyncio.run(held.probe(lagging))
    # The same change again: the record is not vouched for, and no second read is due.
    assert held.probed_at is None and held.automatic_due(clock[0]) is None
    clock[0] = NOW + WINDOW + timedelta(seconds=2)
    asyncio.run(held.probe(lagging))
    assert held.automatic_due(clock[0]) == "full"
