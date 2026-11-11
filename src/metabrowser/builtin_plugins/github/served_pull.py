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
from collections import OrderedDict
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import TYPE_CHECKING, Any, Final, Literal, TypedDict

from metabrowser.builtin_plugins.github import pulls
from metabrowser.builtin_plugins.github.pull_list import ListedRepository
from metabrowser.builtin_plugins.github.pull_record import (
    PullRecord,
    PullRefreshStamp,
    PullRequest,
    read_pull_record,
)
from metabrowser.mirror_refresh import FRESHNESS_WINDOW_S

if TYPE_CHECKING:
    from collections.abc import Callable

    from metabrowser.builtin_plugins.github.pull_catalog import CatalogState
    from metabrowser.builtin_plugins.github.pull_cores import CoreAdmission, CoreAttempt, CoreWindow
    from metabrowser.builtin_plugins.github.pull_freshness import RecordFreshness
    from metabrowser.cache.acquire import PublishedSource

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


# A measured selected-core path is about 1.7 s. This bounds only the POST's wait,
# never the provider job; a late core remains available through the ordinary GET.
CORE_WAIT_TIMEOUT_S: Final = 2.0
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
    # last vouched for it, the row that reported a change the record predates, and whether
    # only its checks are due. `_attempted_row` is the changed row the last attempt saw.
    verified_at: str | None = field(default=None, repr=False)
    changed_row: str | None = field(default=None, repr=False)
    checks_due: bool = field(default=False, repr=False)
    _attempted_row: str | None = field(default=None, repr=False)
    # Set when another writer published this job's record first: how a refresh last ended
    # is then the stamp beside the record, read each time, not anything this job kept.
    outcome_on_disk: bool = field(default=False, repr=False)
    _last_attempt: datetime | None = field(default=None, repr=False)
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
        the catalog cannot loop. One whose checks alone are due (``checks_due``, an open pull
        request the catalog vouches for but read longer ago than the window) is due once a
        window.
        """

        window = timedelta(seconds=window_s)
        unserved = self.without_store and not isinstance(self.published, ListedRepository)
        last = self.last
        held = (
            last is not None
            and last["outcome"] == "rate_limited"
            and last["reset_at"] is not None
            and now < _parse_stamp(last["reset_at"])
        )
        attempted_within = self._last_attempt is not None and now - self._last_attempt <= window
        if self.changed_row is not None and self.fetched_at is not None:
            # GitHub changed it after this record: due unless an attempt saw that very row.
            return not held and (self._attempted_row != self.changed_row or not attempted_within)
        if self.checks_due and not unserved and self.fetched_at is not None:
            return not held and not attempted_within
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
        return self._last_attempt is None or now - self._last_attempt > window

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
            self.without_store = without_store
            self.display_core = None
            self.verified_at = self.changed_row = None
            self.checks_due = False
        if freshness is not None and fetched_at is not None and fetched_at == self.fetched_at:
            self.verified_at = freshness.verified_at if freshness.verified_by == "catalog" else None
            self.changed_row = freshness.changed_row
            self.checks_due = freshness.verdict == "checks"

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
        An automatic refresh of a record whose checks alone are due (``checks_due``) reads
        them on their own (``checks_only`` in :func:`.pulls.refresh_pull_request`).
        """
        previous_attempt, self._last_attempt = self._last_attempt, pulls.utc_now()
        previous_row, self._attempted_row = self._attempted_row, self.changed_row
        self._refreshing = True
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
                checks_only = self.checks_due and not recover and self.changed_row is None
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
                            checks_only=checks_only,
                        )
                    elif checks_only:
                        record = await pulls.refresh_pull_request(
                            published, self.number, adopt_current=False, checks_only=True
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
                    self.fetched_at = exc.current.fetched_at
                    self.without_store = written_without_store(exc.current)
                    self.verified_at = self.changed_row = None
                    self.checks_due = False
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
                    self.fetched_at = record.fetched_at
                    self.without_store = written_without_store(record)
                    self.verified_at = self.changed_row = None
                    self.checks_due = False
                    if record.comparison is not None:
                        self.note_comparison((record.comparison.base, record.comparison.head))
                    self.last = PullRefreshOutcome(
                        outcome="succeeded", message=None, reset_at=None, at=record.fetched_at
                    )
                if not self._recoveries:
                    return
        except asyncio.CancelledError:
            self._last_attempt, self._attempted_row = previous_attempt, previous_row
            raise
        finally:
            self.display_core = None
            self._clear_core_preview()
            self._core_requested = False
            self._core_ready.set()
            self._refreshing = False


def served_pull(published: PublishedSource | ListedRepository, number: int) -> ServedPull:
    """One pull request, knowing when its cached record was fetched, if it was.

    Blocking and bounded: it reads the record and the last refresh's stamp once. Call it
    off the event loop.
    """

    record = read_pull_record(published.home, published.slug, number)
    fetched_at = record.fetched_at if isinstance(record, PullRecord) else None
    without_store = isinstance(record, PullRecord) and written_without_store(record)
    last = last_refresh(published, number)
    issued = OrderedDict[tuple[str, str], None]()
    if isinstance(record, PullRecord) and record.comparison is not None:
        issued[(record.comparison.base, record.comparison.head)] = None
    if last is None:
        return ServedPull(
            published=published,
            number=number,
            fetched_at=fetched_at,
            without_store=without_store,
            _issued=issued,
        )
    return ServedPull(
        published=published,
        number=number,
        fetched_at=fetched_at,
        last=last,
        without_store=without_store,
        _last_attempt=_parse_stamp(last["at"]),
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
                if number != self._attended and held is not self.active and not held.refreshing:
                    del self._kept[number]
                    break
        return pull


__all__ = [
    "MAX_KEPT_PULLS",
    "PullRefreshOutcome",
    "ServedPull",
    "ServedPulls",
    "cached_comparison_record",
    "last_refresh",
    "record_revision",
    "served_pull",
    "written_without_store",
]
