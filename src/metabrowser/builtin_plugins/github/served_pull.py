"""A repository's pull requests, as the refresh coordinator keeps them fresh.

:class:`ServedPull` is the GitHub plugin's
:class:`~metabrowser.mirror_refresh.CompanionRefresh` for one number. Its refresh is
:func:`~metabrowser.builtin_plugins.github.pulls.refresh_pull_request`, run by the
coordinator under the key ``<store key>:pull/<n>``, so requests join one job, it shares
the coordinator's limit on concurrent network work, and shutdown cancels it.

:class:`ServedPulls` is the :class:`~metabrowser.mirror_refresh.PullRequestSet` the
provider hands the server for any GitHub mirror, whether or not its URL named a pull
request. It gives a :class:`ServedPull` for a number. The session attends to one, which
counts toward the mirror's staleness, so the rules that keep a served page fresh -- a
refresh when a stale mirror opens in serve mode, and when a stale page becomes visible --
keep that pull request fresh too.

What the pull route and status need is kept in memory: when the record was fetched and
how the last refresh ended, read from what the last command kept beside the record. A
refresh that fails leaves the record as it was. The next automatic attempt waits a
window, so a missing ``gh`` is not asked on every poll, nor again by a command started
just after one that asked, and after ``rate_limited`` it waits for GitHub's ``reset_at``.

A checkout served as a folder has a set too (:mod:`.checkout`). Before a store is
attached, its page withholds comparisons as ``no_store``. Its metadata refresh preserves
an unchanged comparison another session wrote to their shared record. An explicit
comparison Fetch can attach a store without changing the served folder. A server that
has a store treats a record explicitly marked no_store as stale whatever its age.
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import logging
from collections import OrderedDict
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from functools import partial
from pathlib import Path
from typing import TYPE_CHECKING, Any, Final, Literal, TypedDict

from metabrowser.builtin_plugins.github import gh_budget, pulls
from metabrowser.builtin_plugins.github.pull_catalog import read_pull_status
from metabrowser.builtin_plugins.github.pull_freshness import (
    checks_settling,
    mergeability_pending,
)
from metabrowser.builtin_plugins.github.pull_list import ListedRepository
from metabrowser.builtin_plugins.github.pull_record import (
    PullRecord,
    PullRefreshStamp,
    PullRequest,
    read_pull_record,
)
from metabrowser.builtin_plugins.github.pull_status_store import (
    CheckProbes,
    read_check_probes,
    read_status_outcome,
    write_check_probes,
)
from metabrowser.cache.locks import run_lock_section
from metabrowser.home import PrivateStorageError
from metabrowser.mirror_refresh import FRESHNESS_WINDOW_S, RefreshCoordinator

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable

    from metabrowser.builtin_plugins.github.pull_catalog import CatalogState
    from metabrowser.builtin_plugins.github.pull_cores import CoreAdmission, CoreAttempt, CoreWindow
    from metabrowser.builtin_plugins.github.pull_freshness import RecordFreshness
    from metabrowser.builtin_plugins.github.pull_status import PullStatus
    from metabrowser.cache.acquire import PublishedSource

log = logging.getLogger(__name__)

# Pull requests whose state is kept in memory. The numbers are request text, so this is a
# bound, as ``MAX_REMEMBERED_MISSES`` is on the selections a session remembers. A
# steady-state entry without a selected-core payload was about 1.1 KB; one dropped
# costs a read again: 0.4 ms with no record and 3 ms for a 295 KB record,
# pallets/click#3030 (median of 30 on 2026-11-02, load average 17). Sixty-four is more
# than a reader refreshes in one session, about 72 KB of that measured overhead.
# A selected core also holds its bounded body and metadata until its active job ends;
# the existing active-job limit bounds these additional temporary payloads.
MAX_KEPT_PULLS: Final = 64
# Eight revisions per PR; metadata updates cannot evict the comparison actually displayed.
# Two 64-character IDs per entry keep this below 2 KiB per held PR even with SHA-256.
MAX_ISSUED_COMPARISONS: Final = 8


# How often a visible page's pull request is probed: one conditional ``GET`` of its issue
# (:func:`.pulls.probe_pull_request`), which GitHub does not count against the rate limit
# when it answers ``304``. One probe took 0.56 to 0.96 s with gh 2.98.0 and 0.06 s of CPU
# (2026-11-22, load average near 300), so a change shows half an interval and one probe
# after GitHub's ETag moves, on average, with one ``gh`` process each time.
# How soon that is after the change is GitHub's: reading 12 NixOS/nixpkgs issues every
# 3.8 s for 20 minutes on 2026-11-23 (315 rounds) caught two changes, one answered 2 s
# after its ``updated_at`` and one between about 8 and 13 s after, and reads 15 to 20 s
# apart had seen two more inside 10 and 19 s. Too few to state an average.
# See docs/project/specs/active/plan-2026-11-22-pull-request-update-cadence.md.
ATTENDED_PROBE_S: Final = 5.0
# The shortest gap the server keeps between two probes of one pull request, however many
# pages ask. Below the page's ATTENDED_PROBE_S, so an ask that arrives a little early, as
# timers and thread hops make them, still probes instead of waiting for the next one: at
# the same value an ask at +5 s minus 2 ms was refused and the cadence slipped toward 10 s.
PROBE_FLOOR_S: Final = 4.0
# How often an open pull request's settling checks are probed with it: the first pages of
# its head's check runs and status, two more conditional ``GET``s, while its kept status
# says they settle (:func:`.pull_freshness.checks_settling`). While CI runs they change
# every few seconds; each change costs, beyond the probe's own ``200``, a status read: one
# account check and one GraphQL point and no ``core`` (:func:`.pulls.refresh_pull_status`),
# where reading the checks into the record cost about 2 ``core``. 10 s holds that to about
# 6 status reads a minute. The status read has no ETag, so the probes keep their
# own beside the status (:class:`.pull_status_store.CheckProbes`), and the first probe of a
# head seeds them with one paid ``200`` for each page and one status read.
# Their ETags move with the head's own checks and not with its repository, so these
# probes have no bound on paid answers that change nothing, as the list's has
# (``MAX_PAID_PROBE_S``). Measured 2026-11-23, 06:44 to 07:12 UTC, with gh 2.98.0: of 504
# conditional reads of both pages for six heads, four with runs in progress, the 56
# answered ``200`` after a page's first each changed a run's status or conclusion, added
# a run, or changed the status, all of which a status keeps; and for four pull requests
# whose checks had ended, both pages answered ``304`` in all 96 reads of each page over
# 7 minutes in which the pull's own ETag moved seven times.
# That is a sample, mostly of GitHub Actions runs. A check app that rewrites a run's
# output while it stays in progress would answer a paid ``200`` that changes nothing a
# status keeps (:func:`.pulls.checks_digest`), one ``core`` each interval and no status
# read; what bounds those is the checks ending and the process's ceiling
# (:func:`.gh_budget.over_ceiling`), past which :meth:`ServedPull.probe_due` slows every
# probe to :data:`FULL_REFRESH_S`.
CHECKS_PROBE_S: Final = 10.0
# How long a record the probes vouch for goes without a full read. A probe cannot see an
# edited comment, a reaction, a re-run check of a finished head, or a mergeability GitHub
# recomputes for a status that holds an answer, as when its base moves, so a visible
# page's record, and its status after it, is read in full this often whatever the probes
# say: the "every minute or two" the plan sets, and an unchanged full read is all
# ``304``s, its account checks, and the status's one GraphQL point.
FULL_REFRESH_S: Final = 90.0
# How long, from the first probe that finds a head's kept status with its mergeability
# unknown, its ``conflicts`` or its ``merge_state``, the pull itself is asked with each
# probe (:func:`.pulls.mergeability_probe_path`), and an answer GitHub has since computed
# starts a status read. GitHub computes ``mergeable`` after the read that first asks, and
# ``mergeStateStatus`` with it: of 12 open NixOS/nixpkgs pull requests
# read cold on 2026-11-23, all 12 answered ``null``, and all 12 an answer on the next
# read 3 to 4 s later; review A of #726 saw ``null`` on 8 of 10 and an answer on all 10
# 8 s later. Thirty seconds is six probes, several times the slowest of those. A probe
# that fails does not spend it, and one that ends unanswered is renewed for a record read
# later, at most once a :data:`FULL_REFRESH_S` (:meth:`ServedPull._probe`). That is the
# bound on what these asks can spend on a pull whose answer never comes; of 10 more read
# cold that day and then every 5 s, all 10 answered on the next read, and none was a
# ``200`` that still said ``null``. Those were REST's ``mergeable``; the status's GraphQL
# answer is computed by the same background job. Past it
# the pull is asked no more, since its ETag moves with the whole repository and each move
# costs a call, and the record is no longer vouched for: the window's read asks again.
MERGEABLE_SETTLE_S: Final = 30.0
# How long a ``POST`` that started a probe waits for it. A probe normally ends in about a
# second; past this the request answers ``not_due`` and the probe ends on its own, so a
# slow network never holds the page's request for gh's own 30 s deadline.
PROBE_WAIT_S: Final = 3.0
# Probes running at once in one server, across every pull request; an automatic ask past
# it answers ``not_due`` and the page asks again at its next interval, so nothing queues.
# Each probe is one ``gh`` process, three while checks settle (the issue, the head's check
# runs, and its status) and one more while mergeability is unknown (the pull), and one
# conditional ``gh api`` used 45 MB for 0.6 s (three runs, 2026-11-22, load average 295).
# A probe is one pull request's, one at a time, so the bound is on pull requests probed in
# the same second: a reader's visible pages, and a script asking many cached numbers,
# which ran that many ``gh`` at once before this (review K3 on #709). Four is more visible
# pull request pages than one server's reader keeps in view. The issue has answered before
# a probe's other three start, so a probe runs at most three at once, and four hold the
# worst case to twelve processes and about 540 MB for under a second, 180 MB when nothing
# settles. It is a cost argument, not a measured limit.
MAX_PROBES_IN_FLIGHT: Final = 4
# How long after its last ask a pull request the cap refused keeps its place ahead of those
# probed since (:func:`_may_probe`): two of a page's intervals, so one whose page keeps
# asking has its turn however many are ahead, and one whose page went away holds no one
# back for longer.
PROBE_TURN_S: Final = 2 * ATTENDED_PROBE_S
# The probes running in this process, which is one server.
_PROBES: set[asyncio.Future[None]] = set()
# Pull requests the cap refused, oldest first, by the refresh key each asks under, with
# when and how long its place is kept. Request text decides how many ask, so it is bounded
# as the kept pulls are.
_REFUSED: OrderedDict[str, tuple[datetime, float]] = OrderedDict()


def probes_in_flight() -> int:
    """How many probes run now in this server, against :data:`MAX_PROBES_IN_FLIGHT`."""

    return sum(not task.done() for task in _PROBES)


def may_probe(key: str, now: datetime, *, turn_s: float) -> bool:
    """:func:`_may_probe` for a probe that is not a pull request's: the list's.

    One cap for the server, shared by both kinds (:mod:`.pull_list_probe`). *turn_s* is
    how long a refusal keeps its place, twice the asker's own interval as
    :data:`PROBE_TURN_S` is twice a page's: the list asks half as often as a page, and
    kept for a page's turn its refusal lapsed before its next ask (review A5 on #737). On
    the event loop, as every caller of the cap is.
    """

    return _may_probe(key, now, turn_s=turn_s)


def track_probe(task: asyncio.Future[None]) -> None:
    """Count *task*, a probe that just started, against the cap until it ends."""

    _PROBES.add(task)
    task.add_done_callback(_PROBES.discard)


def _may_probe(key: str, now: datetime, *, turn_s: float = PROBE_TURN_S) -> bool:
    """Whether the pull request asking under *key* may start a probe at *now*, under the cap.

    Past the cap an ask is refused and remembered. A free probe then goes to those
    refused longest ago before one that was not, so askers that arrive in the same order
    each round, as a script's loop over cached numbers does, take turns: before this the
    first :data:`MAX_PROBES_IN_FLIGHT` were probed every round and the rest never (review
    A4 on #726), and a record never probed is read in full once a window instead. A
    refusal is forgotten *turn_s* after its asker last asked, :data:`PROBE_TURN_S` for a
    pull request, or when it probes; with :data:`MAX_KEPT_PULLS` remembered, a new one is
    not, so those remembered keep their places.
    """

    for other, (since, kept_s) in list(_REFUSED.items()):
        if not timedelta(0) <= now - since <= timedelta(seconds=kept_s):
            del _REFUSED[other]
    free = MAX_PROBES_IN_FLIGHT - probes_in_flight()
    ahead = 0
    for other in _REFUSED:
        if other == key:
            break
        ahead += 1
    if ahead < free:
        _REFUSED.pop(key, None)
        return True
    # Refused again, it keeps its place and its refusal is as new as this ask, so it
    # lapses only once its asker stops asking: dated from the first refusal, it lapsed
    # before the turn of any asker past the twelfth came (review B1 on #726). A new one is
    # remembered only while there is room, and asks again: evicting the oldest to make room
    # forgot the asker whose turn was next, so past MAX_KEPT_PULLS askers each round's
    # newcomers evicted one another and none was probed after the first (review D1 on
    # #726).
    if key in _REFUSED or len(_REFUSED) < MAX_KEPT_PULLS:
        _REFUSED[key] = (now, turn_s)
    return False


def forget_probes() -> None:
    """Forget every probe and refusal, as a new process holds none; for tests."""

    _PROBES.clear()
    _REFUSED.clear()


# A measured selected-core path is about 1.7 s. This bounds only the POST's wait,
# never the provider job; a late core remains available through the ordinary GET.
CORE_WAIT_TIMEOUT_S: Final = 2.0
# How long one ``GET pull`` with ``wait_full_after`` waits for that preview's full record or
# its revocation. It is shorter than the page's fast poll interval (``FAST_POLL_MS`` in
# ``pull-page.js``), which the page counts from the read's start.
FULL_WAIT_TIMEOUT_S: Final = 0.9


class PullCorePreview(TypedDict):
    """Provisional validated core; discussion and checks have not finished."""

    source: str
    number: int
    reader: str
    observed_at: str
    revision: str
    pull: dict[str, Any]
    comparison_state: Literal["pending", "no_store", "not_started"]


def make_core_preview(
    source: str,
    reader: str,
    core: PullRequest,
    observed_at: datetime,
    comparison_state: Literal["pending", "no_store", "not_started"],
) -> PullCorePreview:
    content = PullCorePreview(
        source=source,
        number=core.number,
        reader=reader,
        pull=core.model_dump(mode="json"),
        comparison_state=comparison_state,
        observed_at=_stamp(observed_at),
        revision="",
    )
    identity = {
        key: value for key, value in content.items() if key not in {"revision", "observed_at"}
    }
    content["revision"] = hashlib.sha256(
        json.dumps(identity, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    return content


class PullRefreshOutcome(TypedDict):
    """How this server's last refresh of the pull request ended.

    ``outcome`` is ``succeeded`` or a typed failure state; ``message`` says why for a
    failure, and ``reset_at`` when GitHub's rate limit lifts, when it said.
    """

    outcome: str
    message: str | None
    reset_at: str | None
    at: str


def _parse_stamp(stamp: str) -> datetime:
    return datetime.strptime(stamp, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=UTC)


def _stamp(moment: datetime) -> str:
    return moment.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def _source_of(published: PublishedSource | ListedRepository) -> str:
    return (
        published.source if isinstance(published, ListedRepository) else published.source.normalized
    )


def _job_prefix(published: PublishedSource | ListedRepository) -> str:
    """What a refresh's key starts with: the store a mirror fetches into, or a checkout's slug."""

    return published.slug if isinstance(published, ListedRepository) else published.store_key


def written_without_store(record: PullRecord) -> bool:
    """Whether *record* was written by a server with no store, so it has no Files changed."""

    return record.unavailable.get("comparison") == "no_store"


def record_revision(dumped: dict[str, Any]) -> str:
    """Reader-owned content identity, unaffected by refresh time and provider ETags."""

    content = {key: value for key, value in dumped.items() if key not in {"fetched_at", "etags"}}
    return hashlib.sha256(
        json.dumps(content, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()


def cached_comparison_record(
    published: PublishedSource | ListedRepository,
    reader: str | None,
    number: int,
    revision: str | None = None,
) -> PullRecord | None:
    """The cached record a comparison may be prepared from without reading GitHub again.

    That is a record of *published*'s source by the observed *reader*, fetched within the
    freshness window, with no failed refresh recorded since, and of *revision* when one is
    named. Without an observed reader nothing is admitted: a record another account read
    is refreshed first. Blocking and bounded; run it off the event loop.
    """

    record = read_pull_record(published.home, published.slug, number)
    if (
        not isinstance(record, PullRecord)
        or record.source != _source_of(published)
        or reader is None
        or record.reader != reader
        or (revision is not None and record_revision(record.model_dump(mode="json")) != revision)
    ):
        return None
    now = pulls.utc_now()
    window = timedelta(seconds=FRESHNESS_WINDOW_S)
    if now - _parse_stamp(record.fetched_at) > window:
        return None
    last = pulls.last_refresh(published, number)
    if (
        last is not None
        and last.outcome != "succeeded"
        and (
            now - _parse_stamp(last.at) <= window
            or (last.reset_at is not None and now < _parse_stamp(last.reset_at))
        )
    ):
        return None
    return record


def probe_inputs(
    published: PublishedSource | ListedRepository, number: int
) -> tuple[PullStatus | None, CheckProbes | None]:
    """What a probe of pull request *number* compares with: its kept status, and what the
    last probe of its checks saw. Blocking and bounded: one catalog row and one small file.

    Read with the record the probe runs beside, off the loop, before :meth:`ServedPull.probe`.
    A probe that ran meanwhile may keep newer baselines than these, and the next probe
    then counts a change it already saw once more, a status read at most.
    """

    return (
        read_pull_status(published.home, published.slug, number),
        read_check_probes(published.home, published.slug, number),
    )


@dataclass(eq=False)
class ServedPull:
    """One pull request: its source, number, record time, and last refresh.

    *published* is a mirror's source, or a checkout's repository, which has no store.
    ``without_store`` says the record held was written with no store.
    """

    published: PublishedSource | ListedRepository
    number: int
    fetched_at: str | None = None
    last: PullRefreshOutcome | None = None
    without_store: bool = False
    # The catalog's newest verdict on the held record (:mod:`.pull_freshness`): when it
    # last vouched for it, the row that reported a change the record predates, whether only
    # its status is due (``checks``), and whether no kept status describes its head.
    # `_attempted_row` is the changed row the last attempt saw.
    verified_at: str | None = field(default=None, repr=False)
    changed_row: str | None = field(default=None, repr=False)
    checks_due: bool = field(default=False, repr=False)
    status_missing: bool = field(default=False, repr=False)
    _attempted_row: str | None = field(default=None, repr=False)
    # Set when another writer published this job's record first: how a refresh last ended
    # is then the stamp beside the record, read each time, not anything this job kept.
    outcome_on_disk: bool = field(default=False, repr=False)
    _last_attempt: datetime | None = field(default=None, repr=False)
    # When the status was last read, alone (:func:`.pulls.refresh_pull_status`) or after a
    # full read: a status due by the clock waits a window after it, so a failing GraphQL
    # read is asked once a window. A read of the status alone moves no record clock.
    _status_attempt: datetime | None = field(default=None, repr=False)
    _refreshing: bool = field(default=False, repr=False)
    core_preview: PullCorePreview | None = field(default=None, repr=False)
    display_core: tuple[PullCorePreview, CoreAdmission] | None = field(default=None, repr=False)
    _source_pulls: ServedPulls | None = field(default=None, repr=False)
    _core_requested: bool = field(default=False, repr=False)
    _core_ready: asyncio.Event = field(default_factory=asyncio.Event, repr=False)
    _core_waiter: bool = field(default=False, repr=False)
    _full_waiter: asyncio.Event | None = field(default=None, repr=False)
    _core_epoch: object = field(default_factory=object, repr=False)
    _recoveries: OrderedDict[tuple[str, str] | None, None] = field(
        default_factory=OrderedDict, repr=False
    )
    _issued: OrderedDict[tuple[str, str], None] = field(default_factory=OrderedDict, repr=False)
    _displayed: tuple[str, str] | None = field(default=None, repr=False)
    # Probes (:func:`.pulls.probe_pull_request`) of the record held: when one last found it
    # unchanged (``probed_at``), when one was last tried, for the pull and for its checks,
    # and when one last failed. ``_probe_etags`` are newer ETags GitHub sent for the pull
    # whose mergeability the status already holds. ``_probe_saw`` is a change a probe found,
    # ``pull``, which makes the record due until an attempt starts after it, or only
    # ``checks``, its status, which makes a read of the status due until one starts after.
    # ``_issue_seen`` is the pull request's issue as the last probe found it, kept across
    # records. ``_probe_saw_updated`` is the issue ``updated_at`` of the change a probe
    # found, and ``_attempted_updated`` the one the last refresh was started for: a read
    # that did not bring the record up to it is tried again once a window, not on every
    # probe, as an answer that lags the catalog's row is (``_attempted_row``).
    probed_at: str | None = field(default=None, repr=False)
    _probe_attempt: datetime | None = field(default=None, repr=False)
    _checks_probe_attempt: datetime | None = field(default=None, repr=False)
    _probe_failed: datetime | None = field(default=None, repr=False)
    _probe_etags: dict[str, str] = field(default_factory=dict, repr=False)
    _probe_saw: Literal["pull", "checks"] | None = field(default=None, repr=False)
    _probe_saw_at: datetime | None = field(default=None, repr=False)
    _issue_seen: pulls.IssueSeen | None = field(default=None, repr=False)
    _probe_saw_updated: str | None = field(default=None, repr=False)
    _attempted_updated: str | None = field(default=None, repr=False)
    # The head whose unknown mergeability a probe first asked the pull about, and when:
    # :data:`MERGEABLE_SETTLE_S` is counted from it.
    _mergeability_asked: tuple[str, datetime] | None = field(default=None, repr=False)
    _probe_task: asyncio.Future[None] | None = field(default=None, repr=False)
    # When the record held was last read in full, and when a full read was last tried:
    # :data:`FULL_REFRESH_S` is measured from these. A read of the status alone moves
    # neither. A record another writer published counts as read in full when this server
    # adopts it.
    full_read_at: str | None = field(default=None, repr=False)
    _full_attempt: datetime | None = field(default=None, repr=False)
    # A visible page's ask found the full read overdue (:meth:`automatic_due`): the next
    # refresh reads everything, even for a record whose status alone is due.
    _full_asked: bool = field(default=False, repr=False)

    def note_comparison(self, pair: tuple[str, str], *, displayed: bool = False) -> None:
        """Remember a comparison this PR issued; metadata cannot evict the displayed pair."""
        if displayed:
            self._displayed = pair
        self._issued[pair] = None
        self._issued.move_to_end(pair)
        while len(self._issued) > MAX_ISSUED_COMPARISONS:
            oldest = next(key for key in self._issued if key != self._displayed)
            del self._issued[oldest]

    def issued_comparison(self, pair: tuple[str, str]) -> bool:
        return pair in self._issued

    def request_recovery(self, pair: tuple[str, str] | None = None) -> bool:
        """Retain explicit actions joining a running job, coalescing identical selections."""
        if pair not in self._recoveries and len(self._recoveries) >= MAX_ISSUED_COMPARISONS:
            return False
        self._recoveries[pair] = None
        return True

    @property
    def recovery_pending(self) -> bool:
        """Whether an explicit refresh joined another producer and still needs work."""
        return bool(self._recoveries)

    def discard_recovery(self, pair: tuple[str, str] | None) -> None:
        """A refused job must not leave new network work for a later automatic refresh."""
        self._recoveries.pop(pair, None)

    @property
    def key(self) -> str:
        return f"{_job_prefix(self.published)}:pull/{self.number}"

    @property
    def probe_key(self) -> str:
        """The coordinator's key for its probe, beside :attr:`key`, its refresh's."""

        return f"{self.key}:probe"

    @property
    def refreshing(self) -> bool:
        """Whether its refresh is running now, so its state is about to change."""

        return self._refreshing

    def outcome(self) -> PullRefreshOutcome | None:
        """How the last refresh ended, as the pull route reports it. Blocking and bounded.

        Normally this job's own outcome. After another writer published first it is the
        stamp on disk, read again on each call: usually that writer's own success, written
        just after its record, and never a success claimed for this job.
        """

        if self.outcome_on_disk:
            return last_refresh(self.published, self.number)
        return self.last

    def is_stale(self, now: datetime, *, window_s: float) -> bool:
        """Whether the record (:meth:`record_due`) or its status (:meth:`status_due`) is due."""

        return self.record_due(now, window_s=window_s) or self.status_due(now)

    def record_due(self, now: datetime, *, window_s: float) -> bool:
        """Older than *window_s*, and not tried within it or before GitHub's limit lifts.

        A record fetched within the window, or one the catalog vouched for within it
        (``verified_at``), is fresh. Without one, or with an older one, a refresh attempted
        within the window counts as fresh too, whether or not it succeeded, so a failing
        ``gh`` is asked once a window rather than on every poll. After ``rate_limited`` no
        attempt is due before ``reset_at``, when GitHub said. A record written with no
        store is fresh only where there is none, a checkout's: a mirror refreshes it
        whatever its age, for its Files changed. A record the catalog says GitHub changed
        since (``changed_row``) is due at once unless an attempt already saw that row, and
        then once a window, so a head that moved is read at once and an answer that lags
        the catalog cannot loop. A change a probe found in the pull request is due until
        an attempt starts after it.

        Below :data:`~.gh_budget.BACKGROUND_FLOOR` (:meth:`below_floor`) only a change is
        due, one a probe found or the catalog reports: the read the clock alone asks for,
        a record's age, waits until the account's budget is back above it, as background
        work does. A reader's own action never asks this.
        """

        window = timedelta(seconds=window_s)
        unserved = self.without_store and not isinstance(self.published, ListedRepository)
        last = self.last
        held = self._held(now)
        attempted_within = self._last_attempt is not None and now - self._last_attempt <= window
        # A probe found GitHub changed the pull request since this record: due until an
        # attempt follows.
        if (
            self._probe_saw == "pull"
            and self._probe_saw_at is not None
            and self.fetched_at is not None
            and not held
            and (self._last_attempt is None or self._last_attempt < self._probe_saw_at)
        ):
            return True
        if self.changed_row is not None and self.fetched_at is not None:
            # GitHub changed it after this record: due unless an attempt saw that very row.
            return not held and (self._attempted_row != self.changed_row or not attempted_within)
        newest = max(
            (stamp for stamp in (self.fetched_at, self.verified_at) if stamp is not None),
            default=None,
        )
        if not unserved and newest is not None and now - _parse_stamp(newest) <= window:
            return False
        if held:
            return False
        if unserved and last is not None and last["outcome"] == "succeeded":
            # What succeeded was a server with no store writing that record. This one's
            # refresh, which fetches the head into its store, has not been tried.
            return True
        spare = not self.below_floor(now)
        return spare and (self._last_attempt is None or now - self._last_attempt > window)

    def status_due(self, now: datetime) -> bool:
        """Whether a read of the status alone is due at *now* (:func:`.pulls.refresh_pull_status`).

        A change a probe found in the status alone, a check or a mergeability GitHub has
        since computed (``checks_changed``), is due until a read of the status starts after
        it, the one after a full read among them. A status the catalog's verdict says is a
        window old (``checks_due``, an open pull request the catalog vouches for), and a
        record with no kept status of its head (``status_missing``), as a prefetched one
        has, are due once a window from the last read of the status, whether or not the
        record is current. GitHub's limit holds each, and below the GraphQL floor
        (:meth:`status_below_floor`) the last two wait, as the reads the clock asks for do.
        Only a held record has a status read.
        """

        if self.fetched_at is None or self._held(now):
            return False
        if self._status_change_found():
            return True
        if not (self.checks_due or self.status_missing):
            return False
        attempted = self._status_attempt
        within = attempted is not None and now - attempted <= timedelta(seconds=FRESHNESS_WINDOW_S)
        return not within and not self.status_below_floor(now)

    def _held(self, now: datetime) -> bool:
        """Whether GitHub's rate limit holds an automatic read of this record at *now*."""

        last = self.last
        return (
            last is not None
            and last["outcome"] == "rate_limited"
            and last["reset_at"] is not None
            and now < _parse_stamp(last["reset_at"])
        ) or gh_budget.held_until(now) is not None

    def below_floor(self, now: datetime) -> bool:
        """Whether a budget a refresh spends is at or below the background floor at *now*.

        A refresh spends ``core`` on the record and ``graphql`` on its status
        (:func:`.pull_status_read.keep_pull_status`). Then this record's periodic reads
        stop (:meth:`record_due`, :meth:`full_read_due`), while its probes go on, since a
        ``304`` is free, and a change one finds is still read in full: the owner's rule of
        2026-11-22, in :mod:`.gh_budget`'s docstring.
        """

        return gh_budget.admission(("core", "graphql"), now=now).reason == "below_floor"

    def _status_change_found(self) -> bool:
        """Whether a probe found the status alone changed after its last read started."""

        attempted, saw = self._status_attempt, self._probe_saw_at
        return (
            self._probe_saw == "checks"
            and saw is not None
            and (attempted is None or attempted < saw)
        )

    def status_below_floor(self, now: datetime) -> bool:
        """Whether the GraphQL budget a read of the status alone spends is below the floor.

        That read spends no ``core`` beyond an account check, a ``304`` while the login is
        the same, so only ``graphql`` holds its clock-driven reads (:meth:`status_due`).
        """

        return gh_budget.admission(("graphql",), now=now).reason == "below_floor"

    def probe_vouches(self, now: datetime) -> bool:
        """Whether a probe found the record held unchanged within a freshness window."""

        return self.probed_at is not None and now - _parse_stamp(self.probed_at) <= timedelta(
            seconds=FRESHNESS_WINDOW_S
        )

    def automatic_due(self, now: datetime) -> Literal["full", "probe"] | None:
        """What a visible page's automatic ask is due to start at *now*, if anything.

        ``full`` when the record is stale (:meth:`record_due`), over a window of
        :data:`FULL_REFRESH_S` while probes vouch for it and :data:`FRESHNESS_WINDOW_S`
        otherwise, or when its full read is overdue (:meth:`full_read_due`), so even a
        record the catalog or the probes vouch for is read in full that often while a page
        shows it. ``probe`` when none of that holds and a probe is due (:meth:`probe_due`).
        Below the background floor neither clock asks for a full read, so the ask probes,
        and ``full`` is then only a change a probe or the catalog found.

        When only the status is due (:meth:`status_due`), a change a probe found in it is
        read at once; one the clock or a missing status asks for is probed for first when
        a probe is due, so a change the probe finds in the record reads the record and the
        status after it in one job, and otherwise the next ask reads the status alone.
        Either is ``full``: the refresh job decides what it reads (:meth:`refresh`).
        """

        window = self.record_window(now)
        if (
            gh_budget.over_ceiling(now)
            and self._last_attempt is not None
            and now - self._last_attempt <= timedelta(seconds=gh_budget.CEILING_FULL_READ_S)
        ):
            # Over the process's own ceiling (AUTOMATIC_CORE_PER_HOUR) a full read, even
            # one a probe found a change for, waits five minutes after the last; a change
            # that waits is not probed for again.
            return "probe" if self._probe_saw_at is None and self.probe_due(now) else None
        if self.full_read_due(now):
            self._full_asked = True
            return "full"
        if self.record_due(now, window_s=window):
            return "full"
        if not self.status_due(now):
            return "probe" if self.probe_due(now) else None
        return "full" if self._status_change_found() or not self.probe_due(now) else "probe"

    def full_read_overdue(self, now: datetime) -> bool:
        """Whether the record held was last read in full longer than FULL_REFRESH_S ago.

        A record adopted with no full read of this server's known counts from ``fetched_at``.
        """

        stamp = self.full_read_at or self.fetched_at
        return stamp is not None and now - _parse_stamp(stamp) > timedelta(seconds=FULL_REFRESH_S)

    def full_read_due(self, now: datetime) -> bool:
        """Whether a full read is overdue (:meth:`full_read_overdue`) and may start at *now*.

        Not while GitHub's limit holds, below the background floor (:meth:`below_floor`),
        within a freshness window of a failed refresh of any kind
        (:meth:`_failed_recently`), nor within :data:`FULL_REFRESH_S` of the last full
        read tried, so a failing one is not retried on every ask. Reads of the status alone,
        which neither count as one nor hold one back, do not move either clock.
        """

        return (
            self.full_read_overdue(now)
            and not self._held(now)
            and not self.below_floor(now)
            and not self._failed_recently(now)
            and (
                self._full_attempt is None
                or now - self._full_attempt > timedelta(seconds=FULL_REFRESH_S)
            )
        )

    def _failed_recently(self, now: datetime) -> bool:
        """Whether the last refresh failed and was tried within a freshness window."""

        last = self.last
        return (
            last is not None
            and last["outcome"] != "succeeded"
            and self._last_attempt is not None
            and now - self._last_attempt <= timedelta(seconds=FRESHNESS_WINDOW_S)
        )

    def probe_due(self, now: datetime) -> bool:
        """Whether a probe of the record held may start at *now*.

        Not while a refresh or another probe runs, while GitHub's limit holds, within a
        freshness window of a failed refresh or a failed probe (so a missing ``gh`` or a
        lost network is asked once a window, not every few seconds), nor within
        :data:`PROBE_FLOOR_S` of the last probe, however many pages ask, nor while
        :data:`MAX_PROBES_IN_FLIGHT` probes of other pull requests run in this server or
        one the cap refused earlier is still to have its turn (:func:`_may_probe`, which
        remembers this ask when it refuses it).
        """

        window = timedelta(seconds=FRESHNESS_WINDOW_S)
        return not (
            self.fetched_at is None
            or self._refreshing
            or (self._probe_task is not None and not self._probe_task.done())
            or self._held(now)
            or self._failed_recently(now)
            or (self._probe_failed is not None and now - self._probe_failed <= window)
            or (
                self._probe_attempt is not None
                and now - self._probe_attempt
                # Over the process's own ceiling, probes slow to the full-read interval.
                < timedelta(
                    seconds=FULL_REFRESH_S if gh_budget.over_ceiling(now) else PROBE_FLOOR_S
                )
            )
            or not _may_probe(self.key, now)
        )

    async def probe(
        self,
        record: PullRecord,
        *,
        status: PullStatus | None = None,
        probes: CheckProbes | None = None,
        coordinator: RefreshCoordinator | None = None,
    ) -> None:
        """Probe *record*, the record held, when :meth:`probe_due` says one may start.

        *status* is the kept status of its number and *probes* what the last probe of its
        head's checks saw (:func:`probe_inputs`), which the probe compares GitHub's answers
        with: with neither, it asks the issue alone.

        Waits at most :data:`PROBE_WAIT_S` and then raises :class:`TimeoutError`, leaving
        the probe to end on its own; cancelling the wait never cancels the probe.

        With *coordinator*, the server's, the probe is its job under :attr:`probe_key`, so
        shutdown cancels it with every other job, which kills its ``gh``; it takes no
        network slot and no turn at the store. A probe shutdown cancelled ends the wait
        without an error: it found nothing, and nothing is due from it. Asked of a
        coordinator that has closed, it starts nothing, for the same reason.
        """

        if self._probe_task is not None and not self._probe_task.done():
            raise AssertionError("probe_due holds a second probe while one runs")
        if coordinator is not None and coordinator.closed:
            return
        work: Callable[[], Awaitable[None]] = partial(self._probe, record, status, probes)
        task: asyncio.Future[None] | None = None
        if coordinator is not None:
            coordinator.start(self.probe_key, work, network=False)
            task = coordinator.job(self.probe_key)
        if task is None:
            task = asyncio.ensure_future(work())
        self._probe_task = task
        track_probe(task)
        try:
            await asyncio.wait_for(asyncio.shield(task), PROBE_WAIT_S)
        except asyncio.CancelledError:
            waiter = asyncio.current_task()
            if not task.cancelled() or (waiter is not None and waiter.cancelling()):
                # The wait was cancelled, as a request is; the probe goes on.
                raise

    @property
    def probing(self) -> bool:
        """Whether a probe of this pull request runs."""

        return self._probe_task is not None and not self._probe_task.done()

    async def _probe(
        self, record: PullRecord, status: PullStatus | None, probes: CheckProbes | None
    ) -> None:
        now = pulls.utc_now()
        self._probe_attempt = now
        # A pull request whose status has not settled its mergeability has the pull asked
        # too, for MERGEABLE_SETTLE_S from the first probe that found this head's unknown. A
        # status that holds an answer ends the wait, so the next unknown has its own, and
        # so does a new head. A wait that ended unanswered is renewed for a record read
        # after it ended, as a page shown again reads one, and no sooner than
        # FULL_REFRESH_S after it began: that bounds the asks for a pull request GitHub
        # never answers, however many records of it are read meanwhile.
        asked = self._mergeability_asked
        head = record.pull.head.sha
        settle = timedelta(seconds=MERGEABLE_SETTLE_S)
        pending = mergeability_pending(record, status)
        settling = checks_settling(record, status)
        if not pending:
            asked = self._mergeability_asked = None
        elif (
            asked is None
            or asked[0] != head
            or (
                now - asked[1] >= timedelta(seconds=FULL_REFRESH_S)
                and _parse_stamp(record.fetched_at) > asked[1] + settle
            )
        ):
            asked = self._mergeability_asked = (head, now)
        mergeability = asked is not None and now - asked[1] <= settle
        checks = settling and (
            self._checks_probe_attempt is None
            # Less the slack PROBE_FLOOR_S allows each probe, so jitter does not push
            # the checks to every third probe (review B7 on #709).
            or now - self._checks_probe_attempt
            >= timedelta(seconds=CHECKS_PROBE_S - (ATTENDED_PROBE_S - PROBE_FLOOR_S))
        )
        if checks:
            self._checks_probe_attempt = now
        # Settling checks a probe cannot see (:func:`.pulls.checks_probe_paths`), and a
        # mergeability still unknown once the pull is asked no more, are read once a
        # freshness window, as without probes, so no probe vouches for the record.
        vouches = not (
            settling and pulls.checks_probe_paths(self.published, record, status, probes) is None
        ) and not (pending and not mergeability)
        try:
            found = await pulls.probe_pull_request(
                self.published,
                record,
                etags=dict(self._probe_etags),
                checks=checks,
                seen=self._issue_seen,
                mergeability=mergeability,
                status=status,
                probes=probes,
            )
        except Exception as exc:
            # Nothing waits on a probe's result but this record's freshness: any failure,
            # GitHub's or a bug's, leaves the record to the window cadence for a window,
            # where a raised error would answer each 5 s ask with a 500 and no backoff.
            if self.fetched_at == record.fetched_at:
                self._probe_failed = now
            if mergeability:
                # A failed probe holds the next for longer than the settle wait lasts, and
                # may not have reached the pull: the wait starts over when probes resume.
                self._mergeability_asked = None
            if isinstance(exc, pulls.PullDataError):
                log.debug("probing pull request %s failed: %s", self.number, exc)
            else:
                log.exception("probing pull request %s failed", self.number)
            return
        # The issue as GitHub has it now, whichever record this probe ran beside, and the
        # head's checks as it saw them, whichever record of that head is held.
        self._issue_seen = found.seen
        if found.checks is not None:
            await self._keep_check_probes(found.checks)
        if self.fetched_at != record.fetched_at:
            # A newer record arrived while it ran; what it found is about the older one.
            return
        self._probe_failed = None
        self._probe_etags.update(found.etags)
        if found.outcome in ("unchanged", "checks_changed") and vouches:
            # The issue is as the record has it, so the record is GitHub's; a change a
            # probe found in the status alone is the status's to read.
            self.probed_at = _stamp(now)
        if found.outcome == "unchanged":
            return
        if found.outcome == "behind":
            # GitHub's issue answer is older than the record: it lags, and a read would
            # bring nothing, so the record is neither vouched for nor read.
            return
        updated = found.updated_at
        if (
            found.outcome == "changed"
            and updated is not None
            and updated == self._attempted_updated
            and self._last_attempt is not None
            and now - self._last_attempt <= timedelta(seconds=FRESHNESS_WINDOW_S)
        ):
            # The read this change started did not bring the record up to it, as when
            # the pull's own answer lags its issue's: no vouching, and no read again
            # until a window has passed.
            return
        if found.outcome == "changed":
            self._probe_saw_updated = updated
        self._probe_saw = (
            "pull" if found.outcome == "changed" or self._probe_saw == "pull" else "checks"
        )
        self._probe_saw_at = now

    async def _keep_check_probes(self, probes: CheckProbes) -> None:
        """Keep what a probe saw of the head's checks; one that cannot be kept is seeded again."""

        try:
            await run_lock_section(
                partial(write_check_probes, self.published.home, self.published.slug, probes)
            )
        except (PrivateStorageError, OSError, ValueError) as exc:
            log.debug("could not keep what probing pull request %s saw: %s", self.number, exc)

    def _forget_probes(self) -> None:
        """A newer record is held: what probes found was about the one before it."""

        self.probed_at = None
        self._probe_etags = {}
        self._probe_saw = self._probe_saw_at = None
        self._probe_saw_updated = None
        self._probe_failed = None
        # ``_checks_probe_attempt`` is kept: the checks probes keep their own cadence across
        # the records read meanwhile, rather than starting afresh after each one.

    def saw_record(
        self,
        fetched_at: str | None,
        *,
        without_store: bool = False,
        freshness: RecordFreshness | None = None,
    ) -> None:
        """Adopt a record the pull route read, if newer, so status and it agree.

        *freshness* is the catalog's verdict on that record, adopted only while it is the
        record held: a verdict on an older one says nothing about this one.
        """

        if fetched_at is not None and (self.fetched_at is None or fetched_at > self.fetched_at):
            self.fetched_at = fetched_at
            if not self._refreshing:
                # Another writer's record, taken as read in full; a refresh of this server's
                # that is running sets ``full_read_at`` itself when it ends, and may be the
                # read that published this record (review B6 on #709).
                self.full_read_at = fetched_at
            self.without_store = without_store
            self._forget_probes()
            self.display_core = None
            self.verified_at = self.changed_row = None
            self.checks_due = self.status_missing = False
        if freshness is not None and fetched_at is not None and fetched_at == self.fetched_at:
            self.verified_at = freshness.verified_at if freshness.verified_by == "catalog" else None
            self.changed_row = freshness.changed_row
            self.checks_due = freshness.verdict == "checks"
            self.status_missing = freshness.status_missing

    def request_core_preview(self) -> None:
        """Prepare only a selected missing record, never replace a full cached record."""
        if self.fetched_at is None:
            if not self._core_requested:
                self._core_ready.clear()
            self._core_requested = True

    def _clear_core_preview(self) -> None:
        self.core_preview = None
        self._core_epoch = object()
        self._core_ready.clear()
        if self._full_waiter is not None:
            self._full_waiter.set()

    def bind(self, published: PublishedSource | ListedRepository) -> None:
        """A changed publication relinquishes a preview and any in-flight stage callback."""
        if published is not self.published:
            self.display_core = None
            self._clear_core_preview()
            self._core_requested = False
            self._core_ready.set()
        self.published = published

    async def wait_for_core(self) -> None:
        """One bounded HTTP waiter; cancelling it cannot cancel the refresh producer."""
        if not self._core_requested or self._core_waiter or self._full_waiter is not None:
            return
        self._core_waiter = True
        try:
            await asyncio.wait_for(self._core_ready.wait(), CORE_WAIT_TIMEOUT_S)
        except TimeoutError:
            pass
        finally:
            self._core_waiter = False

    async def wait_for_full(self, preview: PullCorePreview) -> bool:
        """Wait for the exact pending preview to settle or be revoked, without owning its job."""
        if (
            not self._refreshing
            or not self._core_requested
            or self.core_preview is not preview
            or self._core_waiter
            or self._full_waiter is not None
        ):
            return False
        waiter = asyncio.Event()
        self._full_waiter = waiter
        try:
            await asyncio.wait_for(waiter.wait(), FULL_WAIT_TIMEOUT_S)
        except TimeoutError:
            pass
        finally:
            self._full_waiter = None
        return True

    async def refresh(self) -> None:
        """Read again, consuming explicit recovery requests before the ordinary PR fetch.

        A refresh cancelled before it ended, as a background job a reader's work preempts
        is, forgets its attempt, so the next automatic request is not held for a window.
        An automatic refresh of a held record whose status alone is due
        (:meth:`status_due`), and which is not due itself (:meth:`record_due`), reads the
        status alone (:func:`.pulls.refresh_pull_status`), unless a visible page's ask
        found its full read overdue (:meth:`automatic_due`) or a reader's own action asked
        for everything. That read moves none of the record's clocks.
        """
        started = pulls.utc_now()
        self._refreshing = True
        try:
            if (
                not self._recoveries
                and not self._full_asked
                and self.status_due(started)
                and not self.record_due(started, window_s=self.record_window(started))
            ):
                await self._refresh_status(started)
                if not self._recoveries:
                    return
                # A reader's own refresh joined while the status was read: it reads all.
                started = pulls.utc_now()
            await self._refresh_record(started)
        finally:
            self.display_core = None
            self._clear_core_preview()
            self._core_requested = False
            self._core_ready.set()
            self._refreshing = False

    def record_window(self, now: datetime) -> float:
        """How old the record held may be before the clock asks for it: :data:`FULL_REFRESH_S`
        while a probe vouches for it (:meth:`probe_vouches`), and a freshness window otherwise."""

        return FULL_REFRESH_S if self.probe_vouches(now) else FRESHNESS_WINDOW_S

    async def _refresh_status(self, started: datetime) -> None:
        """Read and keep the status alone; a failure is the status's, kept beside it."""

        previous, self._status_attempt = self._status_attempt, started
        try:
            await pulls.refresh_pull_status(self.published, self.number)
        except asyncio.CancelledError:
            self._status_attempt = previous
            raise
        except pulls.PullDataError as exc:
            log.debug("reading the status of pull request %s failed: %s", self.number, exc)

    async def _refresh_record(self, started: datetime) -> None:
        """Read the record, and its status after it, consuming each recovery request."""

        previous_attempt, self._last_attempt = self._last_attempt, started
        previous_full, previous_asked = self._full_attempt, self._full_asked
        previous_row, self._attempted_row = self._attempted_row, self.changed_row
        previous_updated, self._attempted_updated = (
            self._attempted_updated,
            self._probe_saw_updated,
        )
        previous_status = self._status_attempt
        if not gh_budget.speculating():
            # The status is read after the record (the prefetch's records read none).
            self._status_attempt = started
        try:
            while True:
                recover = bool(self._recoveries)
                pair = self._recoveries.popitem(last=False)[0] if recover else None
                published = self.published
                epoch: object | None = None

                def observe_reader(
                    reader: str, *, selected: PublishedSource | ListedRepository = published
                ) -> None:
                    if self.published is not selected:
                        return
                    # Failure stamp I/O can still be pending after a reader mismatch.
                    if self.core_preview is not None and self.core_preview["reader"] != reader:
                        self._clear_core_preview()
                    if self.display_core is not None and self.display_core[0]["reader"] != reader:
                        self.display_core = None
                    if self._source_pulls is not None:
                        self._source_pulls.observe_reader(selected, reader)

                async def stage_core(
                    core: PullRequest | None,
                    reader: str | None,
                    *,
                    selected: PublishedSource | ListedRepository = published,
                ) -> None:
                    nonlocal epoch
                    if self.published is not selected:
                        return
                    if core is None:
                        self._clear_core_preview()
                        epoch = self._core_epoch
                        return
                    if not self._core_requested or epoch is not self._core_epoch:
                        return
                    # _read_graph_core verified this reader against the actual response
                    # viewer before this callback; the full read retains its final check.
                    if reader is None:
                        raise AssertionError("a staged core must name its verified reader")
                    source = (
                        selected.source
                        if isinstance(selected, ListedRepository)
                        else selected.source.normalized
                    )
                    self.display_core = None
                    self.core_preview = make_core_preview(
                        source,
                        reader,
                        core,
                        pulls.utc_now(),
                        "no_store" if isinstance(selected, ListedRepository) else "pending",
                    )
                    self._core_ready.set()

                progress = stage_core if self._core_requested and self.fetched_at is None else None
                self._full_attempt = started
                self._full_asked = False
                try:
                    if progress is not None or self._source_pulls is not None:
                        record = await pulls.refresh_pull_request(
                            published,
                            self.number,
                            recover=recover,
                            recovery_pair=pair,
                            on_core=progress,
                            observe_reader=observe_reader,
                            adopt_current=False,
                        )
                    else:
                        record = (
                            await pulls.refresh_pull_request(
                                published,
                                self.number,
                                recover=True,
                                recovery_pair=pair,
                                adopt_current=False,
                            )
                            if recover
                            else await pulls.refresh_pull_request(
                                published, self.number, adopt_current=False
                            )
                        )
                except pulls.PullObservationSuperseded as exc:
                    # Another writer's record is what this server now shows, and this
                    # refresh published nothing. Its writer stamps how it ended just after
                    # the record, possibly after this, so the outcome is read from disk
                    # until this job's next refresh (see outcome()).
                    self.fetched_at = self.full_read_at = exc.current.fetched_at
                    self.without_store = written_without_store(exc.current)
                    self._forget_probes()
                    self.verified_at = self.changed_row = None
                    self.checks_due = self.status_missing = False
                    self.outcome_on_disk = True
                except pulls.PullDataError as exc:
                    self.outcome_on_disk = False
                    self.last = PullRefreshOutcome(
                        outcome=exc.state,
                        message=str(exc),
                        reset_at=exc.reset_at,
                        at=_stamp(pulls.utc_now()),
                    )
                else:
                    self.outcome_on_disk = False
                    self.full_read_at = self.fetched_at = record.fetched_at
                    self.without_store = written_without_store(record)
                    self._forget_probes()
                    self.verified_at = self.changed_row = None
                    self.checks_due = self.status_missing = False
                    if record.comparison is not None:
                        self.note_comparison((record.comparison.base, record.comparison.head))
                    self.last = PullRefreshOutcome(
                        outcome="succeeded", message=None, reset_at=None, at=record.fetched_at
                    )
                if not self._recoveries:
                    return
        except asyncio.CancelledError:
            self._last_attempt, self._attempted_row = previous_attempt, previous_row
            self._attempted_updated = previous_updated
            self._full_attempt, self._full_asked = previous_full, previous_asked
            self._status_attempt = previous_status
            raise


def served_pull(published: PublishedSource | ListedRepository, number: int) -> ServedPull:
    """One pull request, knowing when its cached record was fetched, if it was.

    Blocking and bounded: it reads the record and the stamps of its last refresh and its
    status's last read once. Call it off the event loop.
    """

    record = read_pull_record(published.home, published.slug, number)
    fetched_at = record.fetched_at if isinstance(record, PullRecord) else None
    without_store = isinstance(record, PullRecord) and written_without_store(record)
    last = last_refresh(published, number)
    issued = OrderedDict[tuple[str, str], None]()
    if isinstance(record, PullRecord) and record.comparison is not None:
        issued[(record.comparison.base, record.comparison.head)] = None
    # How the status's last read ended, in any process, so a failing one waits its window.
    read = read_status_outcome(published.home, published.slug, number)
    status_attempt = None if read is None else _parse_stamp(read.at)
    if last is None:
        return ServedPull(
            published=published,
            number=number,
            fetched_at=fetched_at,
            without_store=without_store,
            _status_attempt=status_attempt,
            _issued=issued,
        )
    return ServedPull(
        published=published,
        number=number,
        fetched_at=fetched_at,
        last=last,
        without_store=without_store,
        _last_attempt=_parse_stamp(last["at"]),
        _status_attempt=status_attempt,
        _issued=issued,
    )


def last_refresh(
    published: PublishedSource | ListedRepository, number: int
) -> PullRefreshOutcome | None:
    """How the last refresh of *number* ended, in any process. Blocking and bounded."""

    stamp = pulls.last_refresh(published, number)
    if stamp is None:
        return None
    return PullRefreshOutcome(
        outcome=stamp.outcome, message=stamp.message, reset_at=stamp.reset_at, at=stamp.at
    )


@dataclass(eq=False)
class ServedPulls:
    """A repository's pull requests: the state of a bounded number in memory, the rest on disk.

    The set is changed only on the event loop. A pull request's state is dropped oldest
    first, but the attended one, active acquisition, and running refreshes stay held so
    their jobs cannot go on changing a state nothing reads any more.
    """

    published: PublishedSource | ListedRepository
    _kept: OrderedDict[int, ServedPull] = field(default_factory=OrderedDict[int, ServedPull])
    _attended: int | None = None
    active: ServedPull | None = field(default=None, repr=False)
    core_window: CoreWindow | None = field(default=None, repr=False)
    core_hold_until: datetime | None = field(default=None, repr=False)
    core_failure: PullRefreshStamp | None = field(default=None, repr=False)
    core_attempts: dict[CoreAttempt, float] = field(default_factory=dict, repr=False)
    foreground_intents: int = field(default=0, repr=False)
    observed_reader: str | None = field(default=None, repr=False)
    core_catalog_identity: tuple[str, str, str, str] | None = field(default=None, repr=False)

    @property
    def home(self) -> Path:
        return self.published.home

    @property
    def slug(self) -> str:
        return self.published.slug

    @property
    def source(self) -> str:
        return _source_of(self.published)

    @property
    def git_dir(self) -> Path | None:
        """The store a refresh fetches into, or ``None`` before one is attached."""

        published = self.published
        return None if isinstance(published, ListedRepository) else published.git_dir

    def bind(self, published: PublishedSource | ListedRepository) -> None:
        """Use the published source for later reads and refreshes, retaining each number's state."""

        if published is not self.published:
            window, self.core_window = self.core_window, None
            if window is not None:
                window.cancel()
            self.core_hold_until = None
            self.core_failure = None
            # The reader is the gh account this server observed for the source, not a
            # property of the store: attaching one, or a claimed slug, keeps it, so the
            # reader-scoped checks go on applying where no refresh follows the bind. The
            # catalog it was observed with stays too, so a catalog another account writes
            # later still changes the reader (`observe_catalog`).
            if _source_of(published) != self.source:
                self.observed_reader = None
                self.core_catalog_identity = None
        self.published = published
        for held in self._kept.values():
            held.bind(published)
        if self.active is not None:
            self.active.bind(published)

    def observe_catalog(self, catalog: CatalogState | None) -> None:
        """Adopt a newly authenticated catalog without reviving a refused old reader."""
        if catalog is None or catalog.source != self.source:
            return
        identity = catalog.source, catalog.repository_id, catalog.reader, catalog.epoch
        previous = self.core_catalog_identity
        if previous == identity:
            return
        self.core_catalog_identity = identity
        if previous is not None or self.observed_reader is None:
            self.observed_reader = catalog.reader
        self.core_hold_until = None
        self.core_failure = None
        self.core_attempts.clear()
        window = self.core_window
        if window is not None and (
            (window.admission is not None and not window.admission.matches_identity(catalog))
            or window.ask.generation.split(":", 1)[0] != catalog.epoch
        ):
            self.core_window = None
            window.cancel()

    def observe_reader(self, publication: PublishedSource | ListedRepository, reader: str) -> None:
        """Revoke lookahead owned by a different reader in this exact source binding."""
        if self.published is not publication:
            return
        self.observed_reader = reader
        window = self.core_window
        if (
            window is not None
            and window.admission is not None
            and window.admission.reader != reader
        ):
            self.core_window = None
            window.cancel()
        for held in self._kept.values():
            if (
                held.published is publication
                and held.display_core is not None
                and held.display_core[0]["reader"] != reader
            ):
                held.display_core = None

    def key(self, number: int) -> str:
        return f"{_job_prefix(self.published)}:pull/{number}"

    def foreground_pending(self, running: Callable[[int], bool]) -> bool:
        """A foreground start is in progress or a selected missing pull still owns its job."""
        return bool(self.foreground_intents) or any(
            held.published is self.published and held._core_requested and running(held.number)
            for held in self._kept.values()
        )

    def held(self, number: int) -> ServedPull | None:
        """Pull request *number*'s state when it is in memory. Reads nothing."""

        pull = self._kept.get(number)
        if pull is not None:
            self._kept.move_to_end(number)
        return pull

    async def companion(self, number: int) -> ServedPull:
        from metabrowser.builtin_plugins.github.pull_catalog import read_catalog

        catalog = await asyncio.to_thread(read_catalog, self.home, self.slug)
        self.observe_catalog(catalog)
        held = self.held(number)
        if held is not None:
            return held
        read = await asyncio.to_thread(served_pull, self.published, number)
        # A different pull's Fetch may have attached the store while this read waited.
        # Rebind before adoption; a newer already-held companion still wins below.
        read.bind(self.published)
        return self.held(number) or self._keep(read)

    async def attend(self, number: int) -> ServedPull:
        self._attended = number
        return await self.companion(number)

    def last_refresh(self, number: int) -> PullRefreshOutcome | None:
        """How the last refresh of *number* ended, in any process. Blocking and bounded."""

        return last_refresh(self.published, number)

    def _keep(self, pull: ServedPull) -> ServedPull:
        pull._source_pulls = self
        self._kept[pull.number] = pull
        if len(self._kept) > MAX_KEPT_PULLS:
            for number, held in self._kept.items():
                if (
                    number != self._attended
                    and held is not self.active
                    and not held.refreshing
                    and not held.probing
                ):
                    del self._kept[number]
                    break
        return pull


__all__ = [
    "ATTENDED_PROBE_S",
    "PROBE_FLOOR_S",
    "CHECKS_PROBE_S",
    "FULL_REFRESH_S",
    "MAX_KEPT_PULLS",
    "MAX_PROBES_IN_FLIGHT",
    "MERGEABLE_SETTLE_S",
    "PROBE_TURN_S",
    "PROBE_WAIT_S",
    "PullRefreshOutcome",
    "ServedPull",
    "ServedPulls",
    "cached_comparison_record",
    "forget_probes",
    "last_refresh",
    "may_probe",
    "probe_inputs",
    "probes_in_flight",
    "record_revision",
    "served_pull",
    "track_probe",
    "written_without_store",
]
