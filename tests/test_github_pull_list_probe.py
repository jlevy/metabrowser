"""The list probe: what one conditional read of the newest pull request says of the catalog.

:mod:`.pull_list_probe` holds the probe and its cadence, and :mod:`.pull_list_route` what an
ask makes of it. GitHub is a stand-in for ``get_response`` that answers ``304`` to the ETag
it last sent, so each test says which answers cost a ``200``.
"""

from __future__ import annotations

import asyncio
import json
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

import pytest

from metabrowser.builtin_plugins.github import (
    gh_budget,
    pull_list,
    pull_list_probe,
    pull_list_refresh,
    pull_list_route,
)
from metabrowser.builtin_plugins.github.gh import GhResponse
from metabrowser.builtin_plugins.github.gh_lists import PullDataError, utc_stamp
from metabrowser.builtin_plugins.github.pull_freshness import record_freshness
from metabrowser.builtin_plugins.github.pull_list import ListedRepository, write_list_refresh
from metabrowser.builtin_plugins.github.pull_list_probe import (
    LIST_PROBE_FLOOR_S,
    LIST_PROBE_S,
    MAX_PAID_PROBE_S,
    PAID_PROBES_BEFORE_SLOWING,
    PULLS_LAG_S,
    ListProbe,
    probe_path,
    pulls_path,
)
from metabrowser.builtin_plugins.github.pull_list_route import (
    ListView,
    ListWindow,
    RefreshRequest,
    envelope_etag,
    pull_list_envelope,
    refresh_wanted,
)
from metabrowser.builtin_plugins.github.pull_record import PullRefreshStamp
from metabrowser.builtin_plugins.github.served_pull import FULL_REFRESH_S
from metabrowser.mirror_refresh import FRESHNESS_WINDOW_S, RefreshCoordinator
from tests.cache_home_fixture import (  # pyright: ignore[reportPrivateUsage]
    FixtureSource,
    _stage_and_publish_source,
    build_empty_home,
)
from tests.github_pull_fixture import CANONICAL, FETCHED_AT, READER, generated_item, seed_catalog
from tests.test_github_pull_freshness import NOW as RECORD_NOW
from tests.test_github_pull_freshness import (  # pyright: ignore[reportPrivateUsage]
    _catalog,
    _record,
    _row,
)

SOURCE = FixtureSource("https", CANONICAL)
STAMP = utc_stamp(FETCHED_AT)


class _GitHub:
    """GitHub's two one-row pages, and every request each was sent.

    The issues page, which the probe asks, lists the pull request or issue updated last; a
    pull request there carries ``pull_request``. Its ETag moves only when a row changes.
    The pulls page's also moves on a push (``push``), as GitHub's does.
    """

    def __init__(self, monkeypatch: pytest.MonkeyPatch, item: dict[str, Any] | None) -> None:
        self.item = item
        self.issue: dict[str, Any] | None = None
        self.revision = 0
        self.pulls_revision = 0
        self.asked: list[str | None] = []
        self.statuses: list[int] = []
        self.pulls_statuses: list[int] = []
        self.fail: PullDataError | None = None
        self.fail_pulls: PullDataError | None = None
        self.release: asyncio.Event | None = None
        # How long GitHub takes to answer the issues page, on the stand-in's clock.
        self.takes = 0.0
        # The pulls page as it was, while GitHub's list runs behind a change.
        self.behind: tuple[dict[str, Any] | None, int] | None = None
        self.now = FETCHED_AT
        monkeypatch.setattr(pull_list, "utc_now", lambda: self.now)
        monkeypatch.setattr(pull_list_probe, "get_response", self._get)
        gh_budget.forget()

    @property
    def etag(self) -> str:
        return f'W/"issues-{self.revision}"'

    def push(self) -> None:
        """A push to some branch: the pulls page's row embeds its repositories, and moves."""

        self.pulls_revision += 1

    def update(self, item: dict[str, Any]) -> None:
        self.item = item
        self.revision += 1
        self.pulls_revision += 1

    def comment_on_issue(self, number: int, minutes: int) -> None:
        """An issue, not a pull request, becomes the row updated last."""

        when = utc_stamp(FETCHED_AT + timedelta(minutes=minutes))
        self.issue = {"number": number, "updated_at": when}
        self.revision += 1

    def comment_now(self, number: int) -> None:
        """An issue is updated at the stand-in's present moment."""

        self.issue = {"number": number, "updated_at": utc_stamp(self.now)}
        self.revision += 1

    def pulls_page_runs_behind(self) -> None:
        """The pulls page keeps answering as it does now, whatever changes, until told."""

        self.behind = (self.item, self.pulls_revision)

    def _newest(self) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        if self.item is not None:
            rows.append({**self.item, "pull_request": {"url": "https://api.github.com/x"}})
        if self.issue is not None:
            rows.append(self.issue)
        return sorted(rows, key=lambda row: row["updated_at"])[-1:]

    async def _get(self, path: str, *, etag: str | None, now: datetime) -> GhResponse:
        tail = "?state=all&sort=updated&direction=desc&per_page=1"
        if self.release is not None:
            await self.release.wait()
        if self.fail is not None:
            self.asked.append(etag)
            raise self.fail
        if path == f"repos/octo/demo/pulls{tail}":
            if self.fail_pulls is not None:
                raise self.fail_pulls
            item, revision = self.behind or (self.item, self.pulls_revision)
            current = f'W/"pulls-{revision}"'
            status = 304 if etag == current else 200
            self.pulls_statuses.append(status)
            rows = [item] if item else []
        else:
            assert path == f"repos/octo/demo/issues{tail}"
            self.asked.append(etag)
            current = self.etag
            status = 304 if etag == current else 200
            self.statuses.append(status)
            rows = self._newest()
            self.later(self.takes)
        body = b"" if status == 304 else json.dumps(rows).encode()
        return GhResponse(status, {"etag": current}, body)

    def later(self, seconds: float) -> None:
        self.now += timedelta(seconds=seconds)


@pytest.fixture
def repository(tmp_path: Path) -> ListedRepository:
    home = tmp_path / "home"
    build_empty_home(home)
    _stage_and_publish_source(home, SOURCE, opened=False)
    return ListedRepository(home, SOURCE.slug, "octo", "demo")


def _changed(number: int, minutes: int = 1) -> dict[str, Any]:
    """Pull request *number* as GitHub has it after a change the catalog has not read."""

    when = utc_stamp(FETCHED_AT + timedelta(minutes=minutes))
    return {**generated_item(number), "updated_at": when}


def _probe(probe: ListProbe, repository: ListedRepository) -> None:
    asyncio.run(probe.run(repository))


def test_the_probe_asks_for_the_issue_or_pull_request_updated_last(
    repository: ListedRepository,
) -> None:
    tail = "?state=all&sort=updated&direction=desc&per_page=1"
    assert probe_path(repository) == f"repos/octo/demo/issues{tail}"
    assert pulls_path(repository) == f"repos/octo/demo/pulls{tail}"


def test_an_unchanged_probe_moves_checked_at_and_a_304_costs_nothing_more(
    repository: ListedRepository, monkeypatch: pytest.MonkeyPatch
) -> None:
    seed_catalog(repository, [generated_item(1), generated_item(2)], fetched_at=STAMP)
    github = _GitHub(monkeypatch, generated_item(2))
    probe = ListProbe()
    github.later(20)
    _probe(probe, repository)
    assert github.statuses == [200] and github.asked == [None]
    assert probe.checked_at == utc_stamp(github.now) and probe.saw is None
    github.later(LIST_PROBE_S)
    _probe(probe, repository)
    # The second probe sent the first's ETag, and GitHub charged nothing for its answer.
    assert github.statuses == [200, 304] and github.asked[1] == github.etag
    assert probe.checked_at == utc_stamp(github.now)


def test_a_push_costs_nothing_while_a_pull_request_is_the_row_updated_last(
    repository: ListedRepository, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The issues page embeds no repository, so a push leaves its ETag where it was."""

    seed_catalog(repository, [generated_item(2)], fetched_at=STAMP)
    github = _GitHub(monkeypatch, generated_item(2))
    probe = ListProbe()
    _probe(probe, repository)
    for _ in range(3):
        github.push()
        github.later(LIST_PROBE_S)
        _probe(probe, repository)
    assert github.statuses == [200, 304, 304, 304] and github.pulls_statuses == []
    assert probe.checked_at == utc_stamp(github.now)


def test_an_issue_updated_last_asks_the_pulls_page_until_one_ask_is_past_the_lists_lag(
    repository: ListedRepository, monkeypatch: pytest.MonkeyPatch
) -> None:
    seed_catalog(repository, [generated_item(2)], fetched_at=STAMP)
    github = _GitHub(monkeypatch, generated_item(2))
    github.later(3600)
    github.comment_on_issue(40, minutes=30)
    probe = ListProbe()
    _probe(probe, repository)
    # An issue is newest, so the newest pull request is asked for, and the catalog holds it.
    # The issue was updated half an hour ago, far past any lag: one ask settles it.
    assert (github.statuses, github.pulls_statuses) == ([200], [200])
    assert probe.saw is None and probe.checked_at == utc_stamp(github.now)
    # Nothing moves: one free request, and the pulls page is not asked again.
    github.later(LIST_PROBE_S)
    _probe(probe, repository)
    assert (github.statuses, github.pulls_statuses) == ([200, 304], [200])
    settled = probe.checked_at
    assert settled == utc_stamp(github.now)
    # A comment on the issue a probe interval ago: the pulls page answers 304, but it may
    # still run behind a pull request changed just before the comment, so the probe
    # vouches for no later than it already had, and the next asks the pulls page again.
    github.comment_now(40)
    github.later(LIST_PROBE_S)
    assert LIST_PROBE_S < PULLS_LAG_S <= 2 * LIST_PROBE_S
    _probe(probe, repository)
    assert (github.statuses, github.pulls_statuses) == ([200, 304, 200], [200, 304])
    assert probe.saw is None and probe.checked_at == settled
    # That ask is past the lag: a free 304 from each page, and the probe vouches for now.
    github.later(LIST_PROBE_S)
    _probe(probe, repository)
    assert (github.statuses, github.pulls_statuses) == ([200, 304, 200, 304], [200, 304, 304])
    assert probe.checked_at == utc_stamp(github.now)
    # And then the pulls page rests again.
    github.later(LIST_PROBE_S)
    _probe(probe, repository)
    assert github.pulls_statuses == [200, 304, 304]
    assert probe.checked_at == utc_stamp(github.now)


def test_a_pull_request_changed_just_before_an_issue_is_found_though_the_pulls_page_ran_behind(
    repository: ListedRepository, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A3 of review A on #737: a merge that closes an issue, with the pulls page behind.

    The pulls page was asked once for each answer that put an issue first, and the plan
    measured that page up to 14.2 s behind a change. Asked inside that lag it answered
    with the old row, the probe vouched, and the change waited for the periodic scan.
    """

    seed_catalog(repository, [generated_item(2)], fetched_at=STAMP)
    github = _GitHub(monkeypatch, generated_item(2))
    github.later(3600)
    probe = ListProbe()
    _probe(probe, repository)
    assert probe.checked_at == utc_stamp(github.now)
    # The pull request is merged, and a second later the issue it closes is updated.
    github.later(LIST_PROBE_S - 2)
    github.pulls_page_runs_behind()
    merged = {**generated_item(2), "updated_at": utc_stamp(github.now)}
    github.update(merged)
    github.later(1)
    github.comment_now(40)
    github.later(1)
    _probe(probe, repository)
    # The issues page put the issue first, and the pulls page still had the old row.
    assert (github.statuses, github.pulls_statuses) == ([200, 200], [200])
    assert probe.saw is None
    # The probe vouches for nothing past the change the lag can hide.
    assert probe.checked_at is not None
    assert pull_list.parse_stamp(probe.checked_at) < pull_list.parse_stamp(merged["updated_at"])
    # GitHub's list catches up, and the next probe, a 304 from the issues page, asks the
    # pulls page again and finds the pull request.
    github.behind = None
    github.later(LIST_PROBE_S)
    _probe(probe, repository)
    assert (github.statuses, github.pulls_statuses) == ([200, 200, 304], [200, 200])
    assert probe.saw == ((2, merged["updated_at"]),)


def test_the_slowest_probe_still_vouches_from_behind_the_lists_lag() -> None:
    """The arithmetic beside ``MAX_PAID_PROBE_S``: the next probe starts within an ask
    interval of the gap, and 5 s of the window are left beside that (review B2 of #737)."""

    spare = FRESHNESS_WINDOW_S - (MAX_PAID_PROBE_S + PULLS_LAG_S + LIST_PROBE_S)
    assert spare >= 5, "a probe a moment late would let the last one's vouch lapse"


def test_checked_at_is_when_the_probe_asked_not_when_github_answered(
    repository: ListedRepository, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A9 of review A on #737: a slow probe stamped at its end would vouch for changes
    GitHub made while it ran, and the stand-in's clock never moved during a probe."""

    seed_catalog(repository, [generated_item(2)], fetched_at=STAMP)
    github = _GitHub(monkeypatch, generated_item(2))
    github.later(20)
    asked = github.now
    github.takes = 3.0
    probe = ListProbe()
    _probe(probe, repository)
    assert github.now == asked + timedelta(seconds=3)
    assert probe.checked_at == utc_stamp(asked)


def test_a_pull_request_changed_just_before_an_issue_is_still_found(
    repository: ListedRepository, monkeypatch: pytest.MonkeyPatch
) -> None:
    seed_catalog(repository, [generated_item(2)], fetched_at=STAMP)
    github = _GitHub(monkeypatch, generated_item(2))
    probe = ListProbe()
    _probe(probe, repository)
    github.update(_changed(2, minutes=1))
    github.comment_on_issue(40, minutes=2)
    github.later(LIST_PROBE_S)
    _probe(probe, repository)
    assert probe.saw == ((2, _changed(2, minutes=1)["updated_at"]),)


def test_a_pulls_page_that_failed_is_asked_again_though_the_issues_page_holds(
    repository: ListedRepository, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The issue-first answer was kept, the pulls page behind it was not read: the next
    probe, a 304 from the issues page, must not vouch from an older pulls answer."""

    seed_catalog(repository, [generated_item(2)], fetched_at=STAMP)
    github = _GitHub(monkeypatch, generated_item(2))
    github.later(3600)
    github.comment_on_issue(40, minutes=30)
    probe = ListProbe()
    _probe(probe, repository)
    github.update(_changed(2, minutes=31))
    github.comment_on_issue(40, minutes=32)
    first = probe.checked_at
    assert first == utc_stamp(github.now)
    github.fail_pulls = PullDataError("network_error", "no route to GitHub")
    github.later(LIST_PROBE_S)
    _probe(probe, repository)
    assert probe.saw is None and probe.checked_at == first
    github.fail_pulls = None
    github.later(FRESHNESS_WINDOW_S + 1)
    _probe(probe, repository)
    assert github.statuses[-1] == 304 and github.pulls_statuses[-1] == 200
    assert probe.saw == ((2, _changed(2, minutes=31)["updated_at"]),)


def test_probes_that_pay_and_find_nothing_slow_until_one_is_free_or_finds_a_change(
    repository: ListedRepository, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A repository whose issues change before every probe: each probe is a paid 200."""

    seed_catalog(repository, [generated_item(2)], fetched_at=STAMP)
    github = _GitHub(monkeypatch, generated_item(2))
    probe = ListProbe()
    gaps: list[float] = []
    for minute in range(30, 38):
        github.comment_on_issue(40, minutes=minute)
        github.later(probe.gap_s())
        assert probe.due(github.now)
        _probe(probe, repository)
        gaps.append(probe.gap_s())
    assert gaps == [
        LIST_PROBE_FLOOR_S,
        LIST_PROBE_FLOOR_S,
        2 * LIST_PROBE_FLOOR_S,
        MAX_PAID_PROBE_S,
        MAX_PAID_PROBE_S,
        MAX_PAID_PROBE_S,
        MAX_PAID_PROBE_S,
        MAX_PAID_PROBE_S,
    ]
    assert 2 * LIST_PROBE_FLOOR_S < MAX_PAID_PROBE_S < 4 * LIST_PROBE_FLOOR_S
    assert PAID_PROBES_BEFORE_SLOWING == 3
    # Still inside a freshness window of the last, so the catalog still vouches.
    github.later(MAX_PAID_PROBE_S - 1)
    assert not probe.due(github.now) and probe.vouches(github.now)
    # A probe GitHub answers for nothing puts the gap back.
    github.later(1)
    _probe(probe, repository)
    assert github.statuses[-1] == 304 and probe.gap_s() == LIST_PROBE_FLOOR_S
    # And so does one that finds a change, however many paid before it.
    for minute in range(40, 45):
        github.comment_on_issue(40, minutes=minute)
        github.later(probe.gap_s())
        _probe(probe, repository)
    assert probe.gap_s() > LIST_PROBE_FLOOR_S
    github.update(_changed(2, minutes=50))
    github.later(probe.gap_s())
    _probe(probe, repository)
    assert probe.saw is not None and probe.gap_s() == LIST_PROBE_FLOOR_S


@pytest.mark.parametrize("what", ["updated", "new"])
def test_a_row_the_catalog_lacks_is_a_change_that_waits_for_its_scan(
    repository: ListedRepository, monkeypatch: pytest.MonkeyPatch, what: str
) -> None:
    seed_catalog(repository, [generated_item(1), generated_item(2)], fetched_at=STAMP)
    github = _GitHub(monkeypatch, _changed(2) if what == "updated" else generated_item(3))
    probe = ListProbe()
    _probe(probe, repository)
    assert probe.saw is not None and probe.checked_at is None
    # Nothing probes again until a scan has started for it, however long that takes.
    github.later(10 * LIST_PROBE_S)
    assert not probe.due(github.now)
    probe.scan_started()
    assert probe.saw is None and probe.due(github.now)


def test_a_row_still_missing_after_its_scan_starts_no_second_scan_and_vouches_for_nothing(
    repository: ListedRepository, monkeypatch: pytest.MonkeyPatch
) -> None:
    """GraphQL lagging REST: the scan the change started did not read the row."""

    seed_catalog(repository, [generated_item(2)], fetched_at=STAMP)
    github = _GitHub(monkeypatch, _changed(2))
    probe = ListProbe()
    _probe(probe, repository)
    probe.scan_started()
    github.later(LIST_PROBE_S)
    _probe(probe, repository)
    # A 304: the row is the one the last 200 gave, and the catalog still lacks it.
    assert github.statuses == [200, 304]
    assert probe.saw is None and probe.checked_at is None and not probe.vouches(github.now)
    # The scan that reads it lets the next probe vouch, again for a 304.
    seed_catalog(repository, [_changed(2)], fetched_at=utc_stamp(github.now))
    github.later(LIST_PROBE_S)
    _probe(probe, repository)
    assert github.statuses == [200, 304, 304] and probe.checked_at == utc_stamp(github.now)
    # And another change after it is a change again.
    github.update(_changed(2, minutes=5))
    github.later(LIST_PROBE_S)
    _probe(probe, repository)
    assert probe.saw is not None


def test_a_repository_with_no_pull_request_is_unchanged_while_the_catalog_has_none(
    repository: ListedRepository, monkeypatch: pytest.MonkeyPatch
) -> None:
    seed_catalog(repository, [], fetched_at=STAMP)
    github = _GitHub(monkeypatch, None)
    probe = ListProbe()
    _probe(probe, repository)
    assert probe.saw is None and probe.checked_at is not None
    github.update(generated_item(1))
    github.later(LIST_PROBE_S)
    _probe(probe, repository)
    assert probe.saw == ((1, generated_item(1)["updated_at"]),)


def test_probes_keep_a_floor_between_them_and_one_runs_at_a_time(
    repository: ListedRepository, monkeypatch: pytest.MonkeyPatch
) -> None:
    seed_catalog(repository, [generated_item(2)], fetched_at=STAMP)
    github = _GitHub(monkeypatch, generated_item(2))
    probe = ListProbe()

    async def two_tabs() -> None:
        github.release = asyncio.Event()
        first = asyncio.ensure_future(probe.run(repository))
        await asyncio.sleep(0)
        # The second tab's ask finds one in flight, and starts none.
        assert probe.probing and not probe.due(github.now)
        github.release.set()
        await first

    asyncio.run(two_tabs())
    assert len(github.asked) == 1
    github.later(LIST_PROBE_FLOOR_S - 0.5)
    assert not probe.due(github.now)
    github.later(0.5)
    assert probe.due(github.now)


def test_a_probe_slower_than_its_wait_ends_on_its_own(
    repository: ListedRepository, monkeypatch: pytest.MonkeyPatch
) -> None:
    seed_catalog(repository, [generated_item(2)], fetched_at=STAMP)
    github = _GitHub(monkeypatch, generated_item(2))
    monkeypatch.setattr(pull_list_probe, "PROBE_WAIT_S", 0.01)
    probe = ListProbe()

    async def slow() -> None:
        github.release = asyncio.Event()
        with pytest.raises(TimeoutError):
            await probe.run(repository)
        assert probe.probing and probe.checked_at is None
        github.release.set()
        task = probe._task  # pyright: ignore[reportPrivateUsage]
        assert task is not None
        await task

    asyncio.run(slow())
    assert probe.checked_at is not None


def test_a_failed_probe_holds_the_next_for_a_window_and_a_rate_hold_stops_them(
    repository: ListedRepository, monkeypatch: pytest.MonkeyPatch
) -> None:
    seed_catalog(repository, [generated_item(2)], fetched_at=STAMP)
    github = _GitHub(monkeypatch, generated_item(2))
    github.fail = PullDataError("network_error", "no route to GitHub")
    probe = ListProbe()
    _probe(probe, repository)
    assert probe.checked_at is None and probe.saw is None
    github.later(FRESHNESS_WINDOW_S)
    assert not probe.due(github.now)
    github.later(1)
    assert probe.due(github.now)
    gh_budget.hold(utc_stamp(github.now + timedelta(minutes=5)), now=github.now)
    assert not probe.due(github.now)
    gh_budget.forget()


def test_a_probe_vouches_for_a_record_as_a_scan_run_when_it_asked() -> None:
    """Past the scan's window the catalog vouches again from the probe's time."""

    record = _record(fetched=RECORD_NOW - timedelta(minutes=5), state="closed")
    late = RECORD_NOW + timedelta(seconds=FRESHNESS_WINDOW_S + 30)
    assert (
        record_freshness(record, _catalog(), _row(), status=None, now=late).verdict == "unverified"
    )
    checked = utc_stamp(late - timedelta(seconds=5))
    verdict = record_freshness(
        record, _catalog(), _row(), status=None, now=late, checked_at=checked
    )
    assert (verdict.verdict, verdict.verified_at, verdict.verified_by) == (
        "current",
        checked,
        "catalog",
    )
    # A probe older than the window vouches for nothing, and never hides a changed row.
    stale = utc_stamp(late - timedelta(seconds=FRESHNESS_WINDOW_S + 1))
    assert (
        record_freshness(
            record, _catalog(), _row(), status=None, now=late, checked_at=stale
        ).verdict
        == "unverified"
    )
    newer = _row(updated=RECORD_NOW)
    assert (
        record_freshness(
            record, _catalog(), newer, status=None, now=late, checked_at=checked
        ).verdict
        == "changed"
    )


def _view(repository: ListedRepository, probe: ListProbe | None) -> ListView:
    return ListView(repository, None, False, probe, probe.checked_at if probe is not None else None)


def _succeeded(repository: ListedRepository) -> None:
    stamp = PullRefreshStamp(outcome="succeeded", at=STAMP, reader=f"gh:{READER}")
    write_list_refresh(repository.home, repository.slug, "all", stamp)


def test_the_list_stays_current_while_probes_vouch_and_its_tag_does_not_move(
    repository: ListedRepository, monkeypatch: pytest.MonkeyPatch
) -> None:
    seed_catalog(repository, [generated_item(2)], fetched_at=STAMP)
    _succeeded(repository)
    github = _GitHub(monkeypatch, generated_item(2))
    probe = ListProbe()
    window = ListWindow("all")
    github.later(FRESHNESS_WINDOW_S + 10)
    before = pull_list_envelope(_view(repository, probe), window)
    assert (before["state"], before["checked_at"], before["probe_every_s"]) == (
        "stale",
        None,
        LIST_PROBE_S,
    )
    _probe(probe, repository)
    after = pull_list_envelope(_view(repository, probe), window)
    assert (after["state"], after["checked_at"]) == ("current", utc_stamp(github.now))
    github.later(LIST_PROBE_S)
    _probe(probe, repository)
    again = pull_list_envelope(_view(repository, probe), window)
    assert again["checked_at"] != after["checked_at"]
    assert envelope_etag(again, window) == envelope_etag(after, window)
    assert envelope_etag(after, window) != envelope_etag(before, window)
    # With no coordinator there is nothing to probe with, and the envelope says so.
    assert pull_list_envelope(_view(repository, None), window)["probe_every_s"] is None


def test_an_ask_scans_every_full_refresh_while_probes_vouch_and_every_window_otherwise(
    repository: ListedRepository, monkeypatch: pytest.MonkeyPatch
) -> None:
    seed_catalog(repository, [generated_item(2)], fetched_at=STAMP)
    _succeeded(repository)
    github = _GitHub(monkeypatch, generated_item(2))
    probe = ListProbe()
    ask = RefreshRequest("all", background=True)
    # Inside the window nothing is due but the probe.
    github.later(LIST_PROBE_S)
    assert refresh_wanted(_view(repository, probe), ask) == "probe"
    _probe(probe, repository)
    assert refresh_wanted(_view(repository, probe), ask) is False
    # Past the window, a catalog the probes vouch for is not scanned, and one they do not is.
    while github.now < FETCHED_AT + timedelta(seconds=FRESHNESS_WINDOW_S + 10):
        github.later(LIST_PROBE_S)
        assert refresh_wanted(_view(repository, probe), ask) == "probe"
        _probe(probe, repository)
    assert refresh_wanted(_view(repository, ListProbe()), ask) == "scan"
    assert refresh_wanted(_view(repository, None), ask) == "scan"
    # Past FULL_REFRESH_S the scan is due whatever the probes say.
    while github.now <= FETCHED_AT + timedelta(seconds=FULL_REFRESH_S):
        assert refresh_wanted(_view(repository, probe), ask) in {"probe", False}
        github.later(LIST_PROBE_S)
        _probe(probe, repository)
    assert refresh_wanted(_view(repository, probe), ask) == "scan"


def test_a_change_a_probe_found_starts_the_delta_scan_at_once_and_only_once(
    repository: ListedRepository, monkeypatch: pytest.MonkeyPatch
) -> None:
    seed_catalog(repository, [generated_item(2)], fetched_at=STAMP)
    _succeeded(repository)
    github = _GitHub(monkeypatch, _changed(2))
    ask = RefreshRequest("all", background=True)

    async def exercise() -> list[Any]:
        coordinator = RefreshCoordinator(limit=1)
        probe = pull_list_probe.list_probe(coordinator, repository.source)
        scans: list[Any] = []

        async def scan(*_args: Any, **kwargs: Any) -> None:
            scans.append((kwargs["demand"](), kwargs["take_retry"]()))

        monkeypatch.setattr(pull_list_refresh, "refresh_pull_list", scan)
        view = ListView(repository, coordinator, False, probe, None)
        github.later(LIST_PROBE_S)
        assert await asyncio.to_thread(refresh_wanted, view, ask) == "probe"
        wanted = await pull_list_route.probe_list(view)
        assert wanted == "changed"
        assert pull_list_route.start_refresh(view, ask, wanted=wanted) == "started"
        await coordinator.drain(timeout_s=2)
        # The catalog still lacks the row (the stand-in scan read nothing): no second scan.
        github.later(LIST_PROBE_S)
        assert await asyncio.to_thread(refresh_wanted, view, ask) == "probe"
        assert await pull_list_route.probe_list(view) is False
        assert pull_list_route.start_refresh(view, ask, wanted=False) == "not_due"
        await coordinator.aclose()
        return scans

    # The scan it started was told to read the delta first, as a reader's Refresh is.
    assert asyncio.run(exercise()) == [(("all", 500), True)]
    assert github.statuses == [200, 304]


def test_two_asks_that_both_found_the_probe_due_start_one_probe_and_neither_fails(
    repository: ListedRepository, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A2 of review A on #737: the second raised ``AssertionError``, a 500 from the route.

    A Pulls tab and a second window's tab, or a pull request page's ask: each decides in a
    worker thread, and both decide before either is back on the loop.
    """

    seed_catalog(repository, [generated_item(2)], fetched_at=STAMP)
    _succeeded(repository)
    github = _GitHub(monkeypatch, generated_item(2))
    ask = RefreshRequest("all", background=True)

    async def exercise() -> tuple[Any, Any]:
        coordinator = RefreshCoordinator(limit=1)
        probe = pull_list_probe.list_probe(coordinator, repository.source)
        view = ListView(repository, coordinator, False, probe, None)
        github.later(LIST_PROBE_S)
        github.release = asyncio.Event()
        first, second = await asyncio.gather(
            asyncio.to_thread(refresh_wanted, view, ask),
            asyncio.to_thread(refresh_wanted, view, ask),
        )
        assert first == second == "probe"
        one = asyncio.ensure_future(pull_list_route.probe_list(view))
        await asyncio.sleep(0)
        assert probe.probing
        # The second ask finds the first's probe running, and starts none.
        other = await pull_list_route.probe_list(view)
        github.release.set()
        answers = (await one, other)
        await coordinator.aclose()
        return answers

    assert asyncio.run(exercise()) == (False, False)
    assert len(github.asked) == 1


def test_an_ask_that_reaches_the_loop_after_anothers_probe_found_a_change_leaves_it_to_that_ask(
    repository: ListedRepository, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The later of two asks that both found the probe due starts nothing, so the change
    is scanned for once, by the ask whose probe found it or, past its wait, the next ask."""

    seed_catalog(repository, [generated_item(2)], fetched_at=STAMP)
    _succeeded(repository)
    github = _GitHub(monkeypatch, _changed(2))
    ask = RefreshRequest("all", background=True)

    async def exercise() -> tuple[Any, Any, Any]:
        coordinator = RefreshCoordinator(limit=1)
        probe = pull_list_probe.list_probe(coordinator, repository.source)
        view = ListView(repository, coordinator, False, probe, None)
        github.later(LIST_PROBE_S)
        first, second = await asyncio.gather(
            asyncio.to_thread(refresh_wanted, view, ask),
            asyncio.to_thread(refresh_wanted, view, ask),
        )
        assert first == second == "probe"
        found = await pull_list_route.probe_list(view)
        other = await pull_list_route.probe_list(view)
        # The change waits in ``saw`` for its scan, which the next ask reads first.
        after = await asyncio.to_thread(refresh_wanted, view, ask)
        await coordinator.aclose()
        return found, other, after

    assert asyncio.run(exercise()) == ("changed", False, "changed")
    assert len(github.asked) == 1


def test_a_change_a_probe_found_is_asked_for_before_a_periodic_scan_due_at_the_same_ask(
    repository: ListedRepository, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A8 of review A on #737: the periodic scan started the job, the probe was not told,
    and the next ask started a second scan for the same row."""

    seed_catalog(repository, [generated_item(2)], fetched_at=STAMP)
    _succeeded(repository)
    github = _GitHub(monkeypatch, _changed(2))
    ask = RefreshRequest("all", background=True)

    async def exercise() -> list[Any]:
        coordinator = RefreshCoordinator(limit=1)
        probe = pull_list_probe.list_probe(coordinator, repository.source)
        scans: list[Any] = []

        async def scan(*_args: Any, **kwargs: Any) -> None:
            scans.append(kwargs["take_retry"]())

        monkeypatch.setattr(pull_list_refresh, "refresh_pull_list", scan)
        view = ListView(repository, coordinator, False, probe, None)
        # No probe vouches, and the last scan is more than a window old: the periodic
        # scan is due, and a probe that outlasted its ask's wait has found a change.
        github.later(FRESHNESS_WINDOW_S + 1)
        await probe.run(repository, coordinator=coordinator)
        assert probe.saw is not None
        wanted = await asyncio.to_thread(refresh_wanted, view, ask)
        assert wanted == "changed"
        assert pull_list_route.start_refresh(view, ask, wanted=wanted) == "started"
        assert probe.saw is None
        await coordinator.drain(timeout_s=2)
        # The catalog still lacks the row (the stand-in read nothing), and the probe knows
        # its scan was started: the next finds it behind, not changed again.
        github.later(LIST_PROBE_S)
        await probe.run(repository, coordinator=coordinator)
        assert probe.saw is None and not probe.vouches(github.now)
        await coordinator.aclose()
        return scans

    assert asyncio.run(exercise()) == [True]


def test_a_change_found_while_the_job_runs_makes_its_next_page_the_delta_scan(
    repository: ListedRepository, monkeypatch: pytest.MonkeyPatch
) -> None:
    seed_catalog(repository, [generated_item(2)], fetched_at=STAMP)
    _GitHub(monkeypatch, _changed(2))

    async def exercise() -> list[bool]:
        coordinator = RefreshCoordinator(limit=1)
        probe = pull_list_probe.list_probe(coordinator, repository.source)
        entered, release = asyncio.Event(), asyncio.Event()
        taken: list[bool] = []

        async def backfill(*_args: Any, **kwargs: Any) -> None:
            taken.append(kwargs["take_retry"]())
            entered.set()
            await release.wait()
            taken.append(kwargs["take_retry"]())

        monkeypatch.setattr(pull_list_refresh, "refresh_pull_list", backfill)
        view = ListView(repository, coordinator, False, probe, None)
        ask = RefreshRequest("all", background=True)
        assert pull_list_route.start_refresh(view, ask, wanted=True) == "started"
        await entered.wait()
        assert await pull_list_route.probe_list(view) == "changed"
        assert pull_list_route.start_refresh(view, ask, wanted="changed") == "joined"
        assert probe.saw is None
        release.set()
        await coordinator.drain(timeout_s=2)
        await coordinator.aclose()
        return taken

    assert asyncio.run(exercise()) == [False, True]


def test_a_visible_pages_ask_keeps_its_repositorys_list_probed_and_scanned(
    repository: ListedRepository, monkeypatch: pytest.MonkeyPatch
) -> None:
    """What ``POST pull-refresh`` does for the list on a page's automatic ask."""

    seed_catalog(repository, [generated_item(2)], fetched_at=STAMP)
    _succeeded(repository)
    github = _GitHub(monkeypatch, generated_item(2))
    clock = [100.0]
    monkeypatch.setattr(pull_list_route, "monotonic", lambda: clock[0])

    async def exercise() -> list[Any]:
        coordinator = RefreshCoordinator(limit=1)
        probe = pull_list_probe.list_probe(coordinator, repository.source)
        scans: list[Any] = []

        async def scan(*_args: Any, **kwargs: Any) -> None:
            scans.append(kwargs["take_retry"]())

        monkeypatch.setattr(pull_list_refresh, "refresh_pull_list", scan)

        async def page_asks() -> bool:
            attending = pull_list_route.attend_list(
                ListView(repository, coordinator, False, probe, probe.checked_at)
            )
            if attending is not None:
                await attending
            return attending is not None

        github.later(LIST_PROBE_S)
        assert await page_asks()
        assert github.statuses == [200] and probe.checked_at == utc_stamp(github.now)
        # A second page's ask a moment later, and this page's next one, ask nothing more.
        clock[0] += LIST_PROBE_FLOOR_S - 1
        assert not await page_asks()
        assert github.statuses == [200] and scans == []
        # GitHub changes a pull request: the next ask past the floor starts the scan.
        github.update(_changed(2))
        github.later(LIST_PROBE_S)
        clock[0] += 1
        assert await page_asks()
        await coordinator.drain(timeout_s=2)
        await coordinator.aclose()
        return scans

    assert asyncio.run(exercise()) == [True]
    assert github.statuses == [200, 200]


def test_a_visible_pages_ask_never_starts_the_first_read_of_a_list_nobody_opened(
    repository: ListedRepository, monkeypatch: pytest.MonkeyPatch
) -> None:
    github = _GitHub(monkeypatch, generated_item(2))

    async def exercise() -> None:
        coordinator = RefreshCoordinator(limit=1)
        probe = pull_list_probe.list_probe(coordinator, repository.source)
        attending = pull_list_route.attend_list(ListView(repository, coordinator, False, probe))
        assert attending is not None
        await attending
        assert not coordinator.running(pull_list_route.catalog_job_key(repository.source))
        await coordinator.aclose()
        # And with no coordinator, or no repository, there is nothing to ask with.
        assert pull_list_route.attend_list(ListView(repository, None, False)) is None
        assert pull_list_route.attend_list(ListView(None, coordinator, False)) is None

    asyncio.run(exercise())
    assert github.asked == []


def test_a_list_probe_counts_toward_the_servers_cap_with_its_pull_requests_probes(
    repository: ListedRepository, monkeypatch: pytest.MonkeyPatch
) -> None:
    from metabrowser.builtin_plugins.github import served_pull

    seed_catalog(repository, [generated_item(2)], fetched_at=STAMP)
    _succeeded(repository)
    github = _GitHub(monkeypatch, generated_item(2))
    cap = served_pull.MAX_PROBES_IN_FLIGHT

    async def exercise() -> None:
        coordinator = RefreshCoordinator(limit=1)
        probe = pull_list_probe.list_probe(coordinator, repository.source)
        view = ListView(repository, coordinator, False, probe, None)
        records = [asyncio.get_running_loop().create_future() for _ in range(cap)]
        for running in records:
            served_pull.track_probe(running)
        try:
            # The cap is full of pull requests' probes: the list's ask probes nothing.
            github.later(LIST_PROBE_S)
            assert await pull_list_route.probe_list(view) is False
            assert github.asked == [] and probe.checked_at is None
            # One ends, and the list's probe takes its place and is counted itself.
            records[0].set_result(None)
            await asyncio.sleep(0)
            github.release = asyncio.Event()
            asking = asyncio.ensure_future(pull_list_route.probe_list(view))
            await asyncio.sleep(0.05)
            assert probe.probing and served_pull.probes_in_flight() == cap
            # It is the coordinator's job, so shutdown would cancel it.
            assert coordinator.running(probe.key)
            github.release.set()
            assert await asking is False
            assert probe.checked_at == utc_stamp(github.now)
            assert served_pull.probes_in_flight() == cap - 1
        finally:
            for running in records:
                if not running.done():
                    running.set_result(None)
            await asyncio.sleep(0)
            served_pull._REFUSED.clear()  # pyright: ignore[reportPrivateUsage]
            await coordinator.aclose()

    asyncio.run(exercise())


def test_a_list_probe_the_cap_refused_keeps_its_place_until_its_next_ask() -> None:
    """A5 of review A on #737: its refusal lapsed a page's turn later, before the list's
    next ask, so a pull request refused after it went first."""

    from metabrowser.builtin_plugins.github import served_pull

    served_pull.forget_probes()
    probe = ListProbe()
    now = FETCHED_AT

    async def exercise() -> None:
        loop = asyncio.get_running_loop()
        running = [loop.create_future() for _ in range(served_pull.MAX_PROBES_IN_FLIGHT)]
        for each in running:
            served_pull.track_probe(each)
        try:
            assert not probe.may_start(now)
            # A fifth pull request's page asks every few seconds, and is refused after it.
            for seconds in (1, 6):
                assert not served_pull._may_probe("pull/5", now + timedelta(seconds=seconds))  # pyright: ignore[reportPrivateUsage]
            # One probe ends. The list's next ask is its interval and a timer's lateness
            # after its last, and the one free place is the list's.
            running[0].set_result(None)
            await asyncio.sleep(0)
            later = now + timedelta(seconds=LIST_PROBE_S, milliseconds=20)
            assert not served_pull._may_probe("pull/5", later)  # pyright: ignore[reportPrivateUsage]
            assert probe.may_start(later)
            # A list whose tab went away holds no one back past two of its intervals.
            assert not probe.may_start(later)
            gone = later + timedelta(seconds=2 * LIST_PROBE_S + 1)
            assert served_pull._may_probe("pull/5", gone)  # pyright: ignore[reportPrivateUsage]
        finally:
            for each in running[1:]:
                each.set_result(None)
            await asyncio.sleep(0)
            served_pull.forget_probes()

    asyncio.run(exercise())
