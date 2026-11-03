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
attached, its records have no comparison, ``no_store``. An explicit comparison Fetch can
attach a store without changing the served folder. A server that has a store treats a
record written without one as stale whatever its age.
"""

from __future__ import annotations

import asyncio
from collections import OrderedDict
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import TYPE_CHECKING, Final, TypedDict

from metabrowser.builtin_plugins.github import pulls
from metabrowser.builtin_plugins.github.pull_list import ListedRepository
from metabrowser.builtin_plugins.github.pull_record import PullRecord, read_pull_record

if TYPE_CHECKING:
    from metabrowser.cache.acquire import PublishedSource

# Pull requests whose state is kept in memory. The numbers are request text, so this is a
# bound, as ``MAX_REMEMBERED_MISSES`` is on the selections a session remembers. One is
# about 1.1 KB, and one the set dropped costs a read again: 0.4 ms with no record and 3 ms
# for a 295 KB record, pallets/click#3030 (median of 30 on 2026-11-02, load average 17).
# Sixty-four is more pull requests than a reader refreshes in one session, for 72 KB.
MAX_KEPT_PULLS: Final = 64


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


def _job_prefix(published: PublishedSource | ListedRepository) -> str:
    """What a refresh's key starts with: the store a mirror fetches into, or a checkout's slug."""

    return published.slug if isinstance(published, ListedRepository) else published.store_key


def written_without_store(record: PullRecord) -> bool:
    """Whether *record* was written by a server with no store, so it has no Files changed."""

    return record.unavailable.get("comparison") == "no_store"


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
    _last_attempt: datetime | None = field(default=None, repr=False)
    _refreshing: bool = field(default=False, repr=False)

    @property
    def key(self) -> str:
        return f"{_job_prefix(self.published)}:pull/{self.number}"

    @property
    def refreshing(self) -> bool:
        """Whether its refresh is running now, so its state is about to change."""

        return self._refreshing

    def is_stale(self, now: datetime, *, window_s: float) -> bool:
        """Older than *window_s*, and not tried within it or before GitHub's limit lifts.

        A record fetched within the window is fresh. Without one, or with an older one, a
        refresh attempted within the window counts as fresh too, whether or not it
        succeeded, so a failing ``gh`` is asked once a window rather than on every poll.
        After ``rate_limited`` no attempt is due before ``reset_at``, when GitHub said.
        A record written with no store is fresh only where there is none, a checkout's: a
        mirror refreshes it whatever its age, for its Files changed.
        """

        window = timedelta(seconds=window_s)
        unserved = self.without_store and not isinstance(self.published, ListedRepository)
        if (
            not unserved
            and self.fetched_at is not None
            and now - _parse_stamp(self.fetched_at) <= window
        ):
            return False
        last = self.last
        if (
            last is not None
            and last["outcome"] == "rate_limited"
            and last["reset_at"] is not None
            and now < _parse_stamp(last["reset_at"])
        ):
            return False
        if unserved and last is not None and last["outcome"] == "succeeded":
            # What succeeded was a server with no store writing that record. This one's
            # refresh, which fetches the head into its store, has not been tried.
            return True
        return self._last_attempt is None or now - self._last_attempt > window

    def saw_record(self, fetched_at: str | None, *, without_store: bool = False) -> None:
        """Adopt a record the pull route read, if newer, so status and it agree."""

        if fetched_at is not None and (self.fetched_at is None or fetched_at > self.fetched_at):
            self.fetched_at = fetched_at
            self.without_store = without_store

    async def refresh(self) -> None:
        """Read the pull request again; a failure is kept as :attr:`last`."""

        self._last_attempt = pulls.utc_now()
        self._refreshing = True
        try:
            record = await pulls.refresh_pull_request(self.published, self.number)
        except pulls.PullDataError as exc:
            self.last = PullRefreshOutcome(
                outcome=exc.state,
                message=str(exc),
                reset_at=exc.reset_at,
                at=_stamp(pulls.utc_now()),
            )
            return
        finally:
            self._refreshing = False
        self.fetched_at = record.fetched_at
        self.without_store = written_without_store(record)
        self.last = PullRefreshOutcome(
            outcome="succeeded", message=None, reset_at=None, at=record.fetched_at
        )


def served_pull(published: PublishedSource | ListedRepository, number: int) -> ServedPull:
    """One pull request, knowing when its cached record was fetched, if it was.

    Blocking and bounded: it reads the record and the last refresh's stamp once. Call it
    off the event loop.
    """

    record = read_pull_record(published.home, published.slug, number)
    fetched_at = record.fetched_at if isinstance(record, PullRecord) else None
    without_store = isinstance(record, PullRecord) and written_without_store(record)
    last = last_refresh(published, number)
    if last is None:
        return ServedPull(
            published=published,
            number=number,
            fetched_at=fetched_at,
            without_store=without_store,
        )
    return ServedPull(
        published=published,
        number=number,
        fetched_at=fetched_at,
        last=last,
        without_store=without_store,
        _last_attempt=_parse_stamp(last["at"]),
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
    first, and never the attended one's or one whose refresh is running, which would go
    on changing a state nothing reads any more.
    """

    published: PublishedSource | ListedRepository
    _kept: OrderedDict[int, ServedPull] = field(default_factory=OrderedDict[int, ServedPull])
    _attended: int | None = None

    @property
    def home(self) -> Path:
        return self.published.home

    @property
    def slug(self) -> str:
        return self.published.slug

    @property
    def source(self) -> str:
        published = self.published
        if isinstance(published, ListedRepository):
            return published.source
        return published.source.normalized

    @property
    def git_dir(self) -> Path | None:
        """The store a refresh fetches into, or ``None`` before one is attached."""

        published = self.published
        return None if isinstance(published, ListedRepository) else published.git_dir

    def attach_store(self, published: PublishedSource) -> None:
        """Use the acquired store for later refreshes, retaining each number's state."""

        self.published = published
        for held in self._kept.values():
            held.published = published

    def key(self, number: int) -> str:
        return f"{_job_prefix(self.published)}:pull/{number}"

    def held(self, number: int) -> ServedPull | None:
        """Pull request *number*'s state when it is in memory. Reads nothing."""

        pull = self._kept.get(number)
        if pull is not None:
            self._kept.move_to_end(number)
        return pull

    async def companion(self, number: int) -> ServedPull:
        held = self.held(number)
        if held is not None:
            return held
        read = await asyncio.to_thread(served_pull, self.published, number)
        # A different pull's Fetch may have attached the store while this read waited.
        # Rebind before adoption; a newer already-held companion still wins below.
        read.published = self.published
        return self.held(number) or self._keep(read)

    async def attend(self, number: int) -> ServedPull:
        self._attended = number
        return await self.companion(number)

    def last_refresh(self, number: int) -> PullRefreshOutcome | None:
        """How the last refresh of *number* ended, in any process. Blocking and bounded."""

        return last_refresh(self.published, number)

    def _keep(self, pull: ServedPull) -> ServedPull:
        self._kept[pull.number] = pull
        if len(self._kept) > MAX_KEPT_PULLS:
            for number, held in self._kept.items():
                if number != self._attended and not held.refreshing:
                    del self._kept[number]
                    break
        return pull


__all__ = [
    "MAX_KEPT_PULLS",
    "PullRefreshOutcome",
    "ServedPull",
    "ServedPulls",
    "last_refresh",
    "served_pull",
    "written_without_store",
]
