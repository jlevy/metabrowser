"""Whether a repository's catalog of pull requests still describes GitHub, asked cheaply.

The list probe is one conditional ``GET`` of the repository's most recently updated issue
or pull request (:func:`probe_path`), sent with the last answer's ETag, which is kept here
and nowhere else. GitHub lists pull requests among issues, and ``sort=updated`` puts the
one changed last first, so that one-row page, and its ETag, change whenever any pull
request's ``updated_at`` moves or a new one appears. GitHub does not count a ``304``
against the rate limit.

The issues page is asked, not the pulls page, because a pull request's row embeds its
repositories: the pulls page's ETag moved with no pull request changed whenever a push,
an opened or closed issue, or a recomputed ``mergeable`` touched them, and each such
``200`` costs a call (the measurements are beside :data:`LIST_PROBE_S`). An issue's row
embeds none. The cost is that an issue's own update moves it too. When the newest row is
an issue, a pull request may have changed just before it, so the one-row pulls page
(:func:`pulls_path`) is asked as well, with its own ETag, once for each answer that put an
issue first; a ``304`` there says the newest pull request is still the one last seen.

Either way a ``200`` is a hint, not proof. The newest pull request's row is compared with
the catalog's row of the same number, and the catalog is behind only when it has no such
row or another ``updated_at`` (an issue's ``updated_at`` equalled its pull request's on 24
of 24 rows, and the delta scan's GraphQL ``updatedAt`` equals REST's character for
character, as :mod:`.pull_freshness` records). The comparison is made on a ``304`` too,
from the rows the last ``200``s gave, so what a probe says never depends on which answer
carried the row:

- **unchanged**: the catalog holds that row. ``checked_at`` moves, and for a freshness
  window the catalog vouches for its records and its list as a scan just run would
  (:func:`.pull_freshness.record_freshness`), so the scan itself is due only once every
  ``FULL_REFRESH_S`` (:func:`.pull_list_route.refresh_wanted`).
- **changed**: the catalog lacks that row, and no scan has been tried for it. ``saw`` holds
  the row until a scan starts (:meth:`ListProbe.scan_started`), which the route starts at
  once, and nothing probes meanwhile.
- **behind**: the catalog still lacks a row a scan was already started for, as when
  GraphQL lags REST. Nothing moves: no probe vouches, so the scan runs once a freshness
  window as it did before probes, and the probe that follows the scan that reads the row
  finds it unchanged. A probe therefore never starts two scans for one row.

A repository whose issues change every few seconds would make every probe a paid ``200``
that finds no pull request changed. After :data:`PAID_PROBES_BEFORE_SLOWING` such probes
in a row the gap to the next doubles, up to :data:`MAX_PAID_PROBE_S`; a probe GitHub
answered for nothing, or one that found a change, puts it back (:meth:`ListProbe.gap_s`).

A probe runs no account check and writes nothing; the scan a change starts checks the
account and publishes. A failed probe holds the next for a freshness window. One probe per
repository runs at a time, and :data:`LIST_PROBE_FLOOR_S` is the least gap between two,
however many tabs ask. The state is this process's, per refresh coordinator and source.
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import TYPE_CHECKING, Final, Literal
from weakref import WeakKeyDictionary

from metabrowser.builtin_plugins.github import gh_budget, pull_list
from metabrowser.builtin_plugins.github.gh_lists import (
    READ_FAILURES,
    PageTooLargeError,
    PullDataError,
    as_dict,
    get_response,
    response_json,
    utc_stamp,
)
from metabrowser.builtin_plugins.github.pull_catalog import catalog_member
from metabrowser.builtin_plugins.github.served_pull import FULL_REFRESH_S, PROBE_WAIT_S
from metabrowser.mirror_refresh import FRESHNESS_WINDOW_S, RefreshCoordinator

if TYPE_CHECKING:
    from metabrowser.builtin_plugins.github.pull_list import ListedRepository

log = logging.getLogger(__name__)

# How often a visible Pulls list, or the repository of a visible pull request page, is
# probed. A ``304`` took 0.85 to 1.33 s with gh 2.98.0 over ten probes of jlevy/metabrowser
# and cli/cli (2026-11-22, load average near 250). GitHub's ETag for the pulls page moved
# 1.3 to 14.2 s after a change, median 3.4 s (the plan's "How Soon GitHub Reports a
# Change"). A change then costs a delta scan, one GraphQL point and an account check, where
# the record probe's costs one record read, so the list is probed half as often as the page
# (``ATTENDED_PROBE_S``): a change shows about 5 s after GitHub reports it on average, 10 s
# at worst, plus the scan, for one ``gh`` process each time.
#
# Which page: both one-row pages of jlevy/metabrowser, cli/cli, and microsoft/vscode were
# asked every 10 s with their last ETags for 20 minutes (2026-11-23, 120 rounds each). The
# pulls page answered ``200`` with its row's number and ``updated_at`` unmoved 8 times (5,
# 1, and 2) and for a changed pull request 4 times; the issues page never answered ``200``
# for an unmoved row, 4 times for a changed pull request, and twice for an issue
# (vscode's). So the issues page pays only for a change, a pull request's or an issue's.
# The record probe's measurement of single pull requests found the same (661 rounds on ten
# open pulls): 90 ``200``s with ``updated_at`` unmoved, from
# ``base.repo.open_issues_count`` (56), ``pushed_at`` (40), and ``mergeable`` (20), where
# the issue answered ``304`` all 90 times.
# See docs/project/specs/active/plan-2026-11-22-pull-request-update-cadence.md.
LIST_PROBE_S: Final = 10.0
# The shortest gap the server keeps between two probes of one repository, however many
# tabs ask. Below LIST_PROBE_S by the second ``PROBE_FLOOR_S`` leaves the record probe, so
# an ask that arrives a little early, as timers and thread hops make them, still probes.
LIST_PROBE_FLOOR_S: Final = 9.0
# How many probes in a row may each pay for a ``200`` that found no pull request changed
# before the gap to the next doubles: three allows a burst of issue comments or pushes
# without slowing the list, at three calls.
PAID_PROBES_BEFORE_SLOWING: Final = 3
# The longest that gap grows. Not ``FULL_REFRESH_S``, the plan's bound for the record's
# probe: an unchanged probe vouches for the catalog for a freshness window (60 s), and a
# list probed less often than that would stop vouching, so its scan would run every window,
# one GraphQL point and an account check each, which costs more than the probes saved.
# At 40 s a repository whose issues never rest costs 90 calls an hour, where every probe
# paid would cost 360.
MAX_PAID_PROBE_S: Final = 40.0

type ListProbeOutcome = Literal["unchanged", "changed", "behind"]
# The first row's number and ``updated_at``; ``None`` for a repository with no pull request.
type FirstRow = tuple[int, str] | None


_ONE_NEWEST: Final = "?state=all&sort=updated&direction=desc&per_page=1"


def probe_path(repository: ListedRepository) -> str:
    """The one-row page a list probe asks for: the issue or pull request updated last."""

    return f"repos/{repository.owner}/{repository.repo}/issues{_ONE_NEWEST}"


def pulls_path(repository: ListedRepository) -> str:
    """The one-row page asked when an issue is newest: the pull request updated last."""

    return f"repos/{repository.owner}/{repository.repo}/pulls{_ONE_NEWEST}"


def _first_row(payload: object) -> tuple[FirstRow, bool]:
    """A one-row page's row, and whether it is a pull request (an issue's row says so)."""

    if not isinstance(payload, list) or len(payload) > 1:  # pyright: ignore[reportUnknownArgumentType]
        raise TypeError("not a one-row page")
    if not payload:
        return None, False
    row = as_dict(payload[0])
    number, updated_at = row["number"], row["updated_at"]
    if type(number) is not int or not isinstance(updated_at, str):
        raise TypeError("not an issue or pull request row")
    pull_list.parse_stamp(updated_at)
    return (number, updated_at), "pull_request" in row


def _catalog_holds(repository: ListedRepository, first: FirstRow) -> bool:
    """Whether the catalog of *repository* holds *first* as GitHub has it. Blocking, bounded."""

    state, row = catalog_member(repository.home, repository.slug, first[0] if first else 1)
    if state is None or state.source != repository.source:
        return False
    if first is None:
        return state.totals["all"] == 0
    return row is not None and row.updated_at == first[1]


@dataclass(eq=False)
class ListProbe:
    """One repository's list probe: its ETag, what it last found, and when it may run."""

    # When a probe last found the catalog unchanged, as the envelope's ``checked_at``.
    checked_at: str | None = None
    # A row the catalog lacks that no scan has been started for: a scan is due at once.
    saw: tuple[FirstRow] | None = field(default=None, repr=False)
    # The ETag of each page's last answer, by path.
    _etags: dict[str, str] = field(default_factory=dict[str, str], repr=False)
    # The row the issues page's last ``200`` gave, and whether it is a pull request; and
    # the pulls page's, in a tuple so "no pull request" is not "no answer".
    _newest: tuple[FirstRow, bool] | None = field(default=None, repr=False)
    _newest_pull: tuple[FirstRow] | None = field(default=None, repr=False)
    # Whether the pulls page was read since the issues page last answered ``200``.
    _pulls_asked: bool = field(default=False, repr=False)
    # Probes in a row that each paid for a ``200`` and found no pull request changed.
    _paid_idle: int = field(default=0, repr=False)
    _scanned_for: tuple[FirstRow] | None = field(default=None, repr=False)
    _attempt: datetime | None = field(default=None, repr=False)
    _failed: datetime | None = field(default=None, repr=False)
    _task: asyncio.Future[None] | None = field(default=None, repr=False)
    _attended: float | None = field(default=None, repr=False)

    def attend(self, at: float) -> bool:
        """Whether a visible pull request page's ask at monotonic *at* may ask for the list.

        At most once every :data:`LIST_PROBE_FLOOR_S`, so the pages of a repository, each
        asking for its own record every few seconds, cost the list one read of its state.
        """

        if self._attended is not None and at - self._attended < LIST_PROBE_FLOOR_S:
            return False
        self._attended = at
        return True

    @property
    def probing(self) -> bool:
        return self._task is not None and not self._task.done()

    def vouches(self, now: datetime) -> bool:
        """Whether a probe found the catalog unchanged within a freshness window of *now*."""

        return self.checked_at is not None and now - pull_list.parse_stamp(
            self.checked_at
        ) <= timedelta(seconds=FRESHNESS_WINDOW_S)

    def gap_s(self) -> float:
        """The least gap to the next probe: the floor, doubled for each paid idle probe
        past :data:`PAID_PROBES_BEFORE_SLOWING`, up to :data:`MAX_PAID_PROBE_S`."""

        doublings = self._paid_idle - PAID_PROBES_BEFORE_SLOWING + 1
        if doublings <= 0:
            return LIST_PROBE_FLOOR_S
        return min(MAX_PAID_PROBE_S, LIST_PROBE_FLOOR_S * 2 ** min(doublings, 8))

    def due(self, now: datetime) -> bool:
        """Whether a probe may start at *now*.

        Not while one runs, while a change it found waits for its scan, while GitHub's
        limit holds, within a freshness window of a failed probe, nor within
        :meth:`gap_s` of the last, or ``FULL_REFRESH_S`` while the process is over its own
        ceiling (:func:`.gh_budget.over_ceiling`).
        """

        # Over the process's own ceiling, probes slow to the full-read interval.
        gap = max(self.gap_s(), FULL_REFRESH_S) if gh_budget.over_ceiling(now) else self.gap_s()
        return not (
            self.probing
            or self.saw is not None
            or gh_budget.held_until(now) is not None
            or (
                self._failed is not None
                and now - self._failed <= timedelta(seconds=FRESHNESS_WINDOW_S)
            )
            or (self._attempt is not None and now - self._attempt < timedelta(seconds=gap))
        )

    async def run(self, repository: ListedRepository) -> None:
        """Probe *repository*, when :meth:`due` says one may start.

        Waits at most ``PROBE_WAIT_S`` and then raises :class:`TimeoutError`, leaving the
        probe to end on its own; cancelling the wait never cancels the probe.
        """

        if self.probing:
            raise AssertionError("due holds a second probe while one runs")
        task = asyncio.ensure_future(self._run(repository))
        self._task = task
        await asyncio.wait_for(asyncio.shield(task), PROBE_WAIT_S)

    async def _run(self, repository: ListedRepository) -> None:
        now = pull_list.utc_now()
        self._attempt = now
        try:
            outcome = await self._ask(repository)
        except Exception as exc:
            # Nothing waits on a probe but the catalog's freshness: any failure leaves the
            # scan to its window cadence for a window, as a failed record probe does.
            self._failed = now
            if isinstance(exc, PullDataError):
                log.debug("probing the pull requests of %s failed: %s", repository.source, exc)
            else:
                log.exception("probing the pull requests of %s failed", repository.source)
            return
        self._failed = None
        if outcome == "unchanged":
            self.checked_at = utc_stamp(now)

    async def _get(self, path: str) -> tuple[FirstRow, bool] | None:
        """Ask *path* with its last ETag: its row and kind from a ``200``, ``None`` for a ``304``."""

        try:
            response = await get_response(path, etag=self._etags.get(path), now=pull_list.utc_now())
        except PageTooLargeError as exc:
            raise PullDataError("gh_failed", "GitHub's newest pull request is too large") from exc
        if response.status == 304:
            if path not in self._etags:
                raise PullDataError("gh_failed", "GitHub answered 304 to an unconditional request")
            return None
        try:
            found = _first_row(response_json(response))
        except (*READ_FAILURES, ValueError) as exc:
            raise PullDataError(
                "gh_failed", "GitHub answered with an unreadable pull request"
            ) from exc
        # Kept whatever it says: the comparison below is with the catalog, not with the
        # last answer, so a changed row costs one ``200``, not one per probe.
        if response.etag is not None:
            self._etags[path] = response.etag
        else:
            self._etags.pop(path, None)
        return found

    async def _ask(self, repository: ListedRepository) -> ListProbeOutcome:
        answered = await self._get(probe_path(repository))
        paid = answered is not None
        if answered is not None:
            self._newest = answered
            # Whatever the pulls page last said was said before this answer.
            self._pulls_asked = False
        assert self._newest is not None
        row, is_pull = self._newest
        if row is not None and not is_pull:
            # An issue is newest, and a pull request may have changed just before it: the
            # pulls page says, asked once for each answer that put an issue first, and
            # again after a read of it that failed.
            if not self._pulls_asked:
                newest_pull = await self._get(pulls_path(repository))
                self._pulls_asked = True
                paid = paid or newest_pull is not None
                if newest_pull is not None:
                    self._newest_pull = (newest_pull[0],)
            assert self._newest_pull is not None
            row = self._newest_pull[0]
        held = (row,)
        if await asyncio.to_thread(_catalog_holds, repository, row):
            self._scanned_for = None
            outcome: ListProbeOutcome = "unchanged"
        elif self._scanned_for == held:
            outcome = "behind"
        else:
            self.saw = held
            outcome = "changed"
        self._paid_idle = self._paid_idle + 1 if paid and outcome != "changed" else 0
        return outcome

    def scan_started(self) -> None:
        """A delta scan starts now: the change a probe saw, if any, has had its scan."""

        if self.saw is not None:
            self._scanned_for, self.saw = self.saw, None


_PROBES: WeakKeyDictionary[RefreshCoordinator, dict[str, ListProbe]] = WeakKeyDictionary()
# A server lists one repository, and a checkout whose origin changes another: the sources
# kept are bounded, oldest dropped first, though no served session reaches the bound.
_MAX_PROBED_SOURCES: Final = 8


def list_probe(coordinator: RefreshCoordinator, source: str) -> ListProbe:
    """The probe of *source* under *coordinator*, made on first use. On the event loop."""

    probes = _PROBES.setdefault(coordinator, {})
    probe = probes.get(source)
    if probe is None:
        while len(probes) >= _MAX_PROBED_SOURCES:
            del probes[next(iter(probes))]
        probe = probes[source] = ListProbe()
    return probe


def checked_at(coordinator: RefreshCoordinator | None, source: str) -> str | None:
    """When a probe last found *source*'s catalog unchanged, with no read."""

    probe = _PROBES.get(coordinator, {}).get(source) if coordinator is not None else None
    return probe.checked_at if probe is not None else None


__all__ = [
    "LIST_PROBE_FLOOR_S",
    "LIST_PROBE_S",
    "MAX_PAID_PROBE_S",
    "PAID_PROBES_BEFORE_SLOWING",
    "ListProbe",
    "ListProbeOutcome",
    "checked_at",
    "list_probe",
    "probe_path",
    "pulls_path",
]
