"""The pull request a server serves, as the refresh coordinator keeps it fresh.

:class:`ServedPull` is the GitHub plugin's
:class:`~metabrowser.mirror_refresh.CompanionRefresh`: the CLI asks the provider for one
when a URL names a pull request and hands it to the server with the mirror. Its refresh
is :func:`~metabrowser.builtin_plugins.github.pulls.refresh_pull_request`, run by the
coordinator under the key ``<store key>:pull/<n>``, so requests join one job, it shares
the coordinator's limit on concurrent network work, and shutdown cancels it. It counts
toward the mirror's staleness, so the rules that keep a served page fresh -- a refresh
when a stale mirror opens in serve mode, and when a stale page becomes visible -- keep
the pull request fresh too.

What the pull route and status need is kept in memory: when the record was fetched and
how the last refresh ended, read at startup from what the last command kept beside the
record. A refresh that fails leaves the record as it was; the next attempt waits a
window, so a missing ``gh`` is not asked on every poll, nor again by a command started
just after one that asked.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING, TypedDict

from metabrowser.builtin_plugins.github import pulls
from metabrowser.builtin_plugins.github.pull_record import PullRecord, read_pull_record

if TYPE_CHECKING:
    from metabrowser.cache.acquire import PublishedSource


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


@dataclass(eq=False)
class ServedPull:
    """One served pull request: its source, number, record time, and last refresh."""

    published: PublishedSource
    number: int
    fetched_at: str | None = None
    last: PullRefreshOutcome | None = None
    _last_attempt: datetime | None = field(default=None, repr=False)

    @property
    def key(self) -> str:
        return f"{self.published.store_key}:pull/{self.number}"

    def is_stale(self, now: datetime, *, window_s: float) -> bool:
        """Older than *window_s*, and not tried within it.

        A record fetched within the window is fresh. Without one, or with an older one, a
        refresh attempted within the window counts as fresh too, whether or not it
        succeeded, so a failing ``gh`` is asked once a window rather than on every poll.
        """

        window = timedelta(seconds=window_s)
        if self.fetched_at is not None and now - _parse_stamp(self.fetched_at) <= window:
            return False
        return self._last_attempt is None or now - self._last_attempt > window

    def saw_record(self, fetched_at: str | None) -> None:
        """Adopt a record time the pull route read, if newer, so status and it agree."""

        if fetched_at is not None and (self.fetched_at is None or fetched_at > self.fetched_at):
            self.fetched_at = fetched_at

    async def refresh(self) -> None:
        """Read the pull request again; a failure is kept as :attr:`last`."""

        self._last_attempt = pulls.utc_now()
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
        self.fetched_at = record.fetched_at
        self.last = PullRefreshOutcome(
            outcome="succeeded", message=None, reset_at=None, at=record.fetched_at
        )


def served_pull(published: PublishedSource, number: int) -> ServedPull:
    """The served pull request, knowing when its cached record was fetched, if it was.

    Blocking and bounded: it reads the record and the last refresh's stamp once. Call it
    off the event loop.
    """

    record = read_pull_record(published.home, published.slug, number)
    fetched_at = record.fetched_at if isinstance(record, PullRecord) else None
    stamp = pulls.last_refresh(published, number)
    if stamp is None:
        return ServedPull(published=published, number=number, fetched_at=fetched_at)
    last = PullRefreshOutcome(
        outcome=stamp.outcome, message=stamp.message, reset_at=stamp.reset_at, at=stamp.at
    )
    return ServedPull(
        published=published,
        number=number,
        fetched_at=fetched_at,
        last=last,
        _last_attempt=_parse_stamp(stamp.at),
    )


__all__ = ["PullRefreshOutcome", "ServedPull", "served_pull"]
