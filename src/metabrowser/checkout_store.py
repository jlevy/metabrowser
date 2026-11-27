"""Metabrowser's own store beside a served checkout: its origin's branches and tags.

A folder that is a repository's root shows its origin's branches and tags as Metabrowser
last fetched them, from a store of Metabrowser's own
(``docs/project/architecture/arch-open-modes.md``, "Origin Branches in a Repository
Folder"). The store is the cache's for the address the checkout's ``origin`` remote
names, the one ``metab <URL> --checkout <folder>`` would make: an overlay that borrows
the checkout's objects through ``objects/info/alternates`` and holds only what the
checkout lacks, or a full store of that address when the cache already has one.

**The checkout is never written, and no Git runs in it.** The origin is read from the
checkout's configuration file (:func:`~metabrowser.cache.lender.checkout_origin`), the
lender checks read its files, and every Git process here, the acquisition, each fetch,
and each probe's ``ls-remote``, runs with the store as its Git directory.
``tests/test_checkout_store.py`` compares every file under a checkout, its ``.git``
included, before and after the store is made, fetched, probed, and read.

**Which checkouts.** One whose ``origin`` is an ``https`` address the command line's
grammar accepts. A checkout with no ``origin``, or one whose origin is a path or a
``file://`` address, keeps no store and is served as before: its remote-tracking
branches are already that repository's, a file read away. An origin reached another way,
over SSH on a host no provider reduces to HTTPS, or by ``http://``, ``git://``, or any
other scheme, is one Metabrowser cannot fetch, and the chooser says so.

**When it is fetched.** By the rules of every store Metabrowser keeps
(:class:`~metabrowser.mirror_refresh.StoreSession`): from the moment a server serves the
folder, the idle refresh keeps it at most ``STORE_IDLE_REFRESH_S`` old with no page
visible, and a visible page's own ask fetches it once it is older than the freshness
window and probes a served origin branch every ``STORE_PROBE_S``. A failed acquisition
is tried again unasked after ``STORE_IDLE_REFRESH_S``, then twice as long after each
failure in a row up to :data:`ACQUISITION_RETRY_CAP_S`, a checkout that could not lend
included, and one that ran out its deadline is not tried again until a reader asks
(:meth:`CheckoutStore.retry_at`). A one-shot command
reads the store the cache has and fetches only when it asks. Nothing prompts: the
acquisition policy gives Git no terminal, so an origin that needs credentials the
provider's helper lacks is ``not_found_or_private``, and the chooser shows the origin as
not fetched with that reason.

**One store, one turn.** The GitHub plugin fetches pull requests' heads into the same
store. It takes the turn this module keeps for the store (:func:`store_turn`) and
acquires through :func:`acquire_checkout_store`, so the plugin's jobs and the folder's
fetch take turns in one queue, and neither finds the other holding the store's fetch
lock and reports a refresh running elsewhere.

The cache's modules are imported where a store is first needed, so a plain folder's
server never loads them.
"""

from __future__ import annotations

import asyncio
import hashlib
import logging
import os
import weakref
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any, Final, Literal, TypedDict

from metabrowser.checkout_revisions import (
    checkout_revisions,
    set_origin_opener,
    set_origin_session,
)
from metabrowser.mirror_refresh import (
    STORE_IDLE_REFRESH_S,
    LastOutcome,
    MirrorSession,
    PullJobStart,
    RefreshCoordinator,
    StoreTurn,
    mirror_session,
    refresh_coordinator,
)
from metabrowser.paths_safe import register_root_callback

if TYPE_CHECKING:
    from metabrowser.cache.acquire import PublishedSource
    from metabrowser.cache.urls import GitSource
    from metabrowser.git.process import GitLocation
    from metabrowser.git.tree_source import GitRevisionSubject

log = logging.getLogger(__name__)

# The transport a checkout's store is fetched over. A path or ``file://`` origin is on
# this machine, where the checkout's own remote-tracking branches already are.
_STORE_TRANSPORT: Final = "https"
# The longest the timer waits between unasked tries of an acquisition that keeps failing.
# The first wait is ``STORE_IDLE_REFRESH_S`` and each failure in a row doubles it, so an
# origin that refuses is asked 5 times in its first 2 hours and once an hour after that,
# where every idle interval was 24 times in those 2 hours and 12 an hour after. An
# attempt that fails early costs the origin's probe, one ``ls-remote`` with the
# provider's credential helper run for it; one that gets as far as the fetch is the cost
# measured at :func:`acquire_checkout_store`. An hour is a choice, not a measurement: a
# laptop back on its network has its origin within the hour with nobody asking, and at
# once when a reader refreshes.
ACQUISITION_RETRY_CAP_S: Final = 3600.0

type OriginStoreState = Literal["ready", "acquiring", "absent"]
# Why a checkout has no store to list its origin from. ``not_fetched`` is a store nothing
# has made yet, which only a one-shot command reports, since a server makes it;
# ``transport_unsupported`` an origin Metabrowser cannot fetch; the rest are how the last
# acquisition failed (:func:`acquire_checkout_store`).
type AcquisitionFailure = Literal[
    "lender_missing",
    "not_found_or_private",
    "network_error",
    "timed_out",
    "git_failed",
    "refreshing_elsewhere",
    "fetch_failed",
]
type OriginAbsence = (
    Literal["not_fetched", "transport_unsupported", "cache_unavailable"] | AcquisitionFailure
)
# The failures the timer does not try again: only a reader's own refresh does. An
# acquisition has no size bound of its own, since what an overlay fetches is what the
# checkout lacks and nothing says how much that is before the fetch, so its bound is the
# deadline, ``GIT_ACQUISITION_TIMEOUT_S``. One that ran it out downloaded for all of it
# and kept nothing, and would again: a single-branch clone of a large repository lacks
# most of it. So nobody's asking costs at most one deadline of download for as long as
# the server runs. At the slowest rate measured for a first clone, 1,820 KB/s (beside
# ``GIT_ACQUISITION_TIMEOUT_S`` in ``git/process.py``, 2026-09-23), that is about 1.5 GB
# once; the acquisition measured at :func:`acquire_checkout_store` took 21 s and kept
# 1.26 MB.
_NOT_RETRIED_UNASKED: Final[frozenset[OriginAbsence]] = frozenset({"timed_out"})

# Why the store is absent, for an agent reading `metab --api`; the page says only that the
# origin is not fetched (docs/design-system-messages.md). No path and no address: the
# envelope names the origin.
ABSENCE_DETAIL: Final[dict[OriginAbsence, str]] = {
    "not_fetched": "Metabrowser has not fetched this repository's origin yet.",
    "transport_unsupported": (
        "Metabrowser fetches over HTTPS, and this checkout's origin is reached another way."
    ),
    "cache_unavailable": "Metabrowser's cache directory could not be used.",
    "lender_missing": (
        "This checkout cannot lend its objects to Metabrowser's store: a partial clone, "
        "or a checkout that borrows objects itself, cannot."
    ),
    "not_found_or_private": (
        "The origin was not found, or it is private and Metabrowser has no credentials "
        "for it. Metabrowser never asks for a password."
    ),
    "network_error": "The origin could not be reached.",
    "timed_out": (
        "Fetching what this checkout lacks of its origin took longer than Metabrowser "
        "waits. It is not tried again until you refresh."
    ),
    "git_failed": "Git could not prepare Metabrowser's store.",
    "refreshing_elsewhere": "Another Metabrowser process is preparing this store.",
    "fetch_failed": "Metabrowser's store could not be prepared.",
}


class OriginStore(TypedDict):
    """What ``GET /api/source/refs`` says of the store a checkout's origin is listed from.

    ``state`` is ``ready`` once the store exists, and the list of remote-tracking
    branches and of tags then has the origin's from it; ``acquiring`` while its first
    fetch runs; ``absent`` otherwise, with ``reason`` (:data:`OriginAbsence`) and
    ``detail``, a sentence for the page. ``address`` is the origin as a page shows it,
    ``None`` until it is read. ``last_fetch_at`` and ``last_outcome`` are the store's, as
    ``/api/source/status`` reports a mirror's, and ``refreshing`` is whether a fetch or
    the acquisition runs now. All of it is answered from memory.
    """

    state: OriginStoreState
    reason: OriginAbsence | None
    detail: str | None
    address: str | None
    last_fetch_at: str | None
    last_outcome: LastOutcome | None
    refreshing: bool


class CheckoutStoreError(Exception):
    """A checkout's store could not be acquired. ``code`` is an :data:`AcquisitionFailure`.

    ``str()`` is safe to show only for ``refreshing_elsewhere``, where it can name the
    cache's reservation lock for a reader to find its holder. ``hint`` is what the
    origin's provider says to do about it, a clause safe to show, or ``None``.
    """

    def __init__(self, code: AcquisitionFailure, message: str, *, hint: str | None = None) -> None:
        super().__init__(message)
        self.code: AcquisitionFailure = code
        self.hint = hint


# Held weakly: a turn lives while anything holds it, a session, the GitHub plugin's
# record of the checkout, or a job inside its block, and every one of those gets the same
# object. A turn nothing holds has no holder and no queue, so making it again loses
# nothing; a bounded table that dropped the oldest could drop one in use, and the next
# caller would get a second turn for the same store.
_TURNS: weakref.WeakValueDictionary[tuple[str, str], StoreTurn] = weakref.WeakValueDictionary()


def store_turn(home: Path, source: GitSource) -> StoreTurn:
    """The one turn this process keeps for the store of *source* in *home*.

    Everything in a server that fetches into that store takes it: the folder's own fetch
    and each pull request's. The caller keeps it for as long as it may be taken; one
    made for a root no longer served goes with the last thing that held it.
    """

    key = (str(home), source.normalized)
    held = _TURNS.get(key)
    if held is None:
        held = _TURNS[key] = StoreTurn()
    return held


async def acquire_checkout_store(
    source: GitSource, *, home: Path, checkout: Path
) -> PublishedSource:
    """The store of *source* that borrows from *checkout*, made now if the cache has none.

    A healthy published store is reused with no fetch, a full one included. A miss
    fetches from the origin only what the checkout lacks; a checkout that cannot lend is
    refused, never cloned in full unasked. The caller holds the store's turn
    (:func:`store_turn`), so two acquisitions in one server never run at once. Raises
    :class:`CheckoutStoreError` for every failure it can name.

    Measured 2026-11-22 on this repository's own checkout, whose origin is on
    github.com over HTTPS, with Git 2.56.1 at a load average of about 416, counting
    processes at ``spawn_git_process``: the first acquisition ran 15 Git processes
    and took 21.1 s of wall time and 2.3 s of child CPU, and the store it made held
    1.26 MB, the branches and tags the checkout lacked. A refresh with nothing new
    straight after ran 9 Git processes in 3.6 s, 0.25 s of CPU. The 2026-11-11 count
    for a checkout with no store was 21 Git calls. Reading the origin from the
    checkout's configuration took 65 ms, which included loading the cache's modules.
    An idle machine was not to hand; the wall times include the load.
    """

    from metabrowser.cache.acquire import (
        AcquiringElsewhereError,
        AcquisitionError,
        LenderMissingError,
        RemoteAccessError,
        acquire_source,
    )
    from metabrowser.cache.atomic import RecordError
    from metabrowser.cache.identity import SlugCollisionError, StoreKeyCollisionError
    from metabrowser.cache.layout import FutureLayoutFormatError, LayoutError
    from metabrowser.cache.lender import CheckoutRefusedError
    from metabrowser.cache.locks import LockBusyError
    from metabrowser.cache.providers import provider_credential_hint
    from metabrowser.git.process import GitError, GitTimeoutError
    from metabrowser.home import PrivateStorageError, StorageDirectoryError

    try:
        return await acquire_source(
            source, home=home, checkout=checkout, allow_clone_fallback=False
        )
    except (LenderMissingError, CheckoutRefusedError) as exc:
        raise CheckoutStoreError("lender_missing", "the checkout cannot lend its objects") from exc
    except RemoteAccessError as exc:
        unreadable = "the repository could not be read from its origin"
        if exc.state == "not_found_or_private":
            # What to do is the provider's to say, as the command line's refusal has it:
            # for GitHub, how to sign gh in, or which account it is signed in as.
            hint = provider_credential_hint(source.normalized)
            raise CheckoutStoreError("not_found_or_private", unreadable, hint=hint) from exc
        raise CheckoutStoreError("network_error", unreadable) from exc
    except GitTimeoutError as exc:
        raise CheckoutStoreError("timed_out", "the acquisition ran out its deadline") from exc
    except GitError as exc:
        raise CheckoutStoreError("git_failed", "Git could not prepare the store") from exc
    except LockBusyError as exc:
        raise CheckoutStoreError(
            "refreshing_elsewhere", "another refresh is preparing the store"
        ) from exc
    except AcquiringElsewhereError as exc:
        # Its message names the reservation's lock file, for a reader to find the holder.
        raise CheckoutStoreError("refreshing_elsewhere", str(exc)) from exc
    except (
        AcquisitionError,
        RecordError,
        SlugCollisionError,
        StoreKeyCollisionError,
        LayoutError,
        FutureLayoutFormatError,
        PrivateStorageError,
        StorageDirectoryError,
        OSError,
    ) as exc:
        raise CheckoutStoreError("fetch_failed", "the store could not be prepared") from exc


@dataclass(frozen=True, slots=True)
class _Origin:
    """What a checkout's origin is to its store: the source and home, or why there is none."""

    source: GitSource | None = None
    home: Path | None = None
    address: str | None = None
    absent: OriginAbsence | None = None


def _read_origin(root: Path) -> _Origin | None:
    """The origin of the checkout at *root*, or ``None`` for one that keeps no store.

    Blocking and bounded: the checkout's configuration file, and the cache directory's
    name. No Git process and no write.
    """

    from metabrowser.cache.lender import checkout_origin, unfetched_origin_address
    from metabrowser.cache.served_mirror import display_origin
    from metabrowser.cache.urls import GitSource
    from metabrowser.home import StorageDirectoryError, application_cache

    named = checkout_origin(root)
    if named is None:
        # No origin, or one the grammar refuses: ``http://`` and ``git://`` name another
        # machine too, by a transport Metabrowser does not fetch over.
        elsewhere = unfetched_origin_address(root)
        if elsewhere is None:
            return None
        return _Origin(address=display_origin(elsewhere), absent="transport_unsupported")
    if named.transport == "file":
        return None
    address = display_origin(named.normalized)
    if named.transport != _STORE_TRANSPORT:
        return _Origin(address=address, absent="transport_unsupported")
    try:
        home = application_cache()
    except StorageDirectoryError:
        return _Origin(address=address, absent="cache_unavailable")
    # The repository alone: a remote names no branch or file to select.
    return _Origin(GitSource(named.transport, named.form, named.normalized), home, address)


def _cached(source: GitSource, home: Path) -> PublishedSource | None:
    """The store the cache already has for *source*, read with no fetch and no write."""

    from metabrowser.cache.acquire import AcquisitionError, cached_source
    from metabrowser.cache.atomic import RecordError
    from metabrowser.cache.identity import SlugCollisionError, StoreKeyCollisionError
    from metabrowser.cache.layout import FutureLayoutFormatError, LayoutError
    from metabrowser.home import PrivateStorageError, StorageDirectoryError

    try:
        return cached_source(source, home)
    except (
        AcquisitionError,
        RecordError,
        SlugCollisionError,
        StoreKeyCollisionError,
        LayoutError,
        FutureLayoutFormatError,
        PrivateStorageError,
        StorageDirectoryError,
        OSError,
    ):
        # A store that cannot be read as it is: the acquisition reports why, or repairs it.
        log.debug("the checkout's cached store could not be read", exc_info=True)
        return None


class CheckoutStore:
    """One served checkout's store of its origin: acquiring it, and its session once made.

    ``session`` is ``None`` until the store exists. It is a
    :class:`~metabrowser.mirror_refresh.MirrorSession` that owns only revisions read from
    this store, so while the working tree or one of the checkout's own revisions is
    served it is the store's half alone: it fetches, keeps the turn, and reports the last
    fetch, and follows and probes nothing.
    """

    def __init__(self, root: Path, coordinator: RefreshCoordinator, *, serving: bool) -> None:
        self.root = root
        self._coordinator = coordinator
        self._serving = serving
        self._origin: _Origin | None = None
        self._opened = False
        self._absent: OriginAbsence | None = None
        # What the origin's provider says to do about the last failure, if anything.
        self._hint: str | None = None
        # When the acquisition last failed, on the loop's clock, and how many times in a
        # row it has: what the next unasked try waits for (:meth:`retry_at`).
        self._failed_at: float | None = None
        self._failures = 0
        # Whether an acquisition this store asked for has yet to end, and the event set
        # each time one ends, however it ends, for the timer to look again.
        self._pending = False
        self._settled = asyncio.Event()
        self.session: MirrorSession | None = None
        self._refs_location: GitLocation | None = None
        # Set as the application stops: an acquisition still unwinding adopts nothing,
        # so no session of a stopped application is left named for the root.
        self._closed = False
        self._opening = asyncio.Lock()
        self._tasks: list[asyncio.Task[None]] = []
        self._key = "checkout-store:" + hashlib.sha256(str(root).encode()).hexdigest()[:24]

    # ── What the routes read ────────────────────────────────────

    @property
    def fetchable(self) -> bool:
        """Whether this checkout has an origin Metabrowser fetches, with a store or not yet.

        True until the origin is read, which a server does in the background: a request
        that arrives first is told the acquisition is on its way.
        """

        return not self._opened or self._fetchable()

    def acquiring(self) -> bool:
        return not self._opened or self._coordinator.running(self._key)

    def refs_location(self) -> GitLocation | None:
        """Where the store's refs are, for the state a kept listing is keyed on."""

        return self._refs_location

    def state(self) -> OriginStore | None:
        """The store's state for a page, from memory; ``None`` for a checkout that keeps none."""

        origin = self._origin
        if self._opened and origin is None:
            return None
        address = origin.address if origin is not None else None
        session = self.session
        if session is not None:
            fields = session.store_fields()
            return OriginStore(
                state="ready",
                reason=None,
                detail=None,
                address=address,
                last_fetch_at=fields["last_fetch_at"],
                last_outcome=fields["last_outcome"],
                refreshing=fields["refreshing"],
            )
        failed = self._absent if self._failed_at is not None else None
        if self.acquiring() and failed is None:
            return OriginStore(
                state="acquiring",
                reason=None,
                detail=None,
                address=address,
                last_fetch_at=None,
                last_outcome=None,
                refreshing=True,
            )
        reason: OriginAbsence = self._absent or "not_fetched"
        hint = self._hint
        said = "" if hint is None else f" {hint[:1].upper()}{hint[1:]}."
        return OriginStore(
            state="absent",
            reason=reason,
            detail=ABSENCE_DETAIL[reason] + said,
            address=address,
            last_fetch_at=None,
            last_outcome=None,
            # Tried again now, with why the last try failed still said.
            refreshing=failed is not None and self.acquiring(),
        )

    # ── Opening and acquiring ───────────────────────────────────

    async def open(self) -> None:
        """Read the checkout's origin and adopt the store the cache has, with no network.

        A server then acquires a store it lacks and starts the timer that keeps it fresh.
        """

        try:
            origin = await asyncio.to_thread(_read_origin, self.root)
            self._origin = origin
            if origin is not None:
                self._absent = origin.absent
            if origin is not None and origin.source is not None and origin.home is not None:
                cached = await asyncio.to_thread(_cached, origin.source, origin.home)
                if cached is not None:
                    await self._adopt(cached)
        finally:
            self._opened = True
        if self._serving and self._fetchable():
            if self.session is None:
                self.request_acquisition()
            self._tasks.append(
                asyncio.create_task(self._keep_fresh(), name="metabrowser-checkout-store-idle")
            )

    def start(self) -> None:
        """Open in the background, so a server's first page waits for none of it."""

        self._tasks.append(
            asyncio.create_task(self.ensure_open(), name="metabrowser-checkout-store")
        )

    async def ensure_open(self) -> None:
        """Open once, whoever asks first: a server's start, or the first route that reads it.

        A one-shot command opens here, at the request that needs the store, so a page
        that never asks about the origin loads none of the cache's modules. A failure to
        read is logged and leaves the checkout with no store, as a plain one has.
        """

        if self._opened:
            return
        async with self._opening:
            if self._opened:
                return
            try:
                await self.open()
            except Exception:
                log.warning("could not open the checkout's store of its origin", exc_info=True)

    async def opened_fetchable(self) -> bool:
        """Open, and say whether this checkout has an origin Metabrowser fetches."""

        await self.ensure_open()
        return self._fetchable()

    def _fetchable(self) -> bool:
        origin = self._origin
        return origin is not None and origin.source is not None and origin.home is not None

    def request_acquisition(self) -> Literal["started", "joined"]:
        """Start the store's first fetch as a background job, or join the one running."""

        if self._coordinator.running(self._key):
            return "joined"
        # It waits for its turn at the store first and takes a network slot itself.
        started = self._coordinator.start(self._key, self._acquire_job, network=False)
        self._pending = True
        return started

    async def _acquire_job(self) -> None:
        origin = self._origin
        assert origin is not None and origin.source is not None and origin.home is not None
        # Not background work at the store: a pull request's job that needs this store
        # waits for it and then finds it made, where stopping this would start it again.
        try:
            async with store_turn(origin.home, origin.source)(lambda: False, acquisition=True):
                await self._acquire(origin.source, origin.home)
        finally:
            self._pending = False
            self._settled.set()

    async def _acquire(self, source: GitSource, home: Path) -> None:
        """Acquire the store and adopt it, or record why not. The caller holds the store's turn."""

        from metabrowser.cache.acquire import AcquiringElsewhereError, wait_for_source_reservation
        from metabrowser.cache.locks import LockBusyError
        from metabrowser.home import PrivateStorageError, StorageDirectoryError

        try:
            try:
                # Another process's cold open is waited out holding no network slot.
                await wait_for_source_reservation(source, home=home)
            except AcquiringElsewhereError as exc:
                raise CheckoutStoreError("refreshing_elsewhere", str(exc)) from exc
            except (LockBusyError, PrivateStorageError, StorageDirectoryError, OSError):
                # The acquisition that follows meets the same condition and reports it.
                log.debug("could not wait for another cold open", exc_info=True)
            async with self._coordinator.slot():
                published = await acquire_checkout_store(source, home=home, checkout=self.root)
        except CheckoutStoreError as exc:
            log.info("the checkout's store was not acquired: %s", exc.code)
            self._failed(exc.code, exc.hint)
            return
        except asyncio.CancelledError:
            raise
        except Exception:
            log.exception("acquiring the checkout's store failed")
            self._failed("fetch_failed", None)
            return
        await self._adopt(published)

    def _failed(self, reason: AcquisitionFailure, hint: str | None) -> None:
        self._absent = reason
        self._hint = hint
        self._failed_at = asyncio.get_running_loop().time()
        self._failures += 1

    def retry_at(self) -> float | None:
        """When the next unasked try of a failed acquisition is due, on the loop's clock.

        ``STORE_IDLE_REFRESH_S`` after the attempt ended, and twice as long after each
        failure in a row, up to :data:`ACQUISITION_RETRY_CAP_S`. ``None`` when nothing has
        failed, and for a failure only a reader's refresh tries again
        (:data:`_NOT_RETRIED_UNASKED`). The timer and a visible page's own ask both wait
        for it; a reader's refresh waits for nothing.
        """

        failed = self._failed_at
        if failed is None or self._absent in _NOT_RETRIED_UNASKED:
            return None
        doubled = STORE_IDLE_REFRESH_S * 2 ** min(self._failures - 1, 32)
        return failed + min(doubled, ACQUISITION_RETRY_CAP_S)

    async def _adopt(self, published: PublishedSource) -> None:
        from metabrowser.cache.served_mirror import StoreMirror
        from metabrowser.git.process import GitLocation, repository_store_target

        if self.session is not None or self._closed:
            return
        mirror = StoreMirror.from_published(published)
        own = f"{published.store_id}:"

        def owns(subject: GitRevisionSubject) -> bool:
            return subject.identity.startswith(own)

        origin = self._origin
        assert origin is not None and origin.source is not None and origin.home is not None
        session = MirrorSession(
            mirror,
            self._coordinator,
            follow_elsewhere=self._serving,
            store_turn=store_turn(origin.home, origin.source),
            owns=owns,
        )
        try:
            await session.observe()
        except Exception:
            log.warning("could not read the checkout store's freshness", exc_info=True)
        target = await asyncio.to_thread(repository_store_target, git_dir=published.git_dir)
        # The commit only names the location; the state read is of the store's refs.
        self._refs_location = GitLocation.revision(target, published.default_revision)
        if self._closed:
            return
        self.session = session
        self._absent = None
        self._hint = None
        self._failed_at = None
        self._failures = 0
        set_origin_session(self.root, session)

    async def _keep_fresh(self) -> None:
        """Try a failed acquisition again when it is due until the store exists, then keep it.

        An origin that could not be reached when the folder opened is asked again no more
        often than a store with no page visible is fetched, and less often each time it
        fails again (:meth:`retry_at`). So is a checkout that could not lend: a partial
        clone can be made whole, and one that borrowed objects can repack, and the check
        that refused it reads a few of its files. A failure that is not tried again
        unasked waits here for the acquisition a reader's refresh starts.
        """

        loop = asyncio.get_running_loop()
        while self.session is None:
            self._settled.clear()
            # While one runs, the last failure's time says nothing of the next try.
            due = None if self._pending else self.retry_at()
            if due is None and (self._pending or self._failed_at is None):
                # One runs, or was stopped before it began or ended: looked at again
                # after an idle interval, in case its end never arrives.
                due = loop.time() + STORE_IDLE_REFRESH_S
            wait = None if due is None else max(due - loop.time(), 0.0)
            try:
                await asyncio.wait_for(self._settled.wait(), wait)
            except TimeoutError:
                # A try that ended in the same loop iteration as the timeout, one a page's
                # own ask started, still times the wait out: its end moved when the next
                # is due, so that is worked out again before anything starts.
                if self._settled.is_set():
                    continue
                if self.session is None:
                    try:
                        self.request_acquisition()
                    except RuntimeError:
                        return
        await self.session.run_idle_refresh()

    # ── Refresh ─────────────────────────────────────────────────

    async def refresh(
        self, purpose: Literal["commit", "page"] | None, *, retry: bool = False
    ) -> tuple[str, PullJobStart | None]:
        """Answer ``POST /api/source/refresh`` for a folder: fetch the store, or make it.

        With a store it is the store session's answer, as a mirror's. Without one it
        starts or joins the acquisition; a page's own ask starts none before the timer's
        own next try of one that failed (:meth:`retry_at`), so a visible page asks a
        failing origin no more often than a hidden one. The second value is how a pull
        request's refresh was answered, which only a commit's fetch asks for.
        """

        session = self.session
        if session is not None:
            if purpose == "commit":
                fetch = session.request_commit_fetch(retry=retry)
                return fetch.refresh, fetch.pull_refresh
            if purpose == "page":
                return await session.page_ask(), None
            return session.request_refresh(), None
        if self._coordinator.running(self._key):
            return "joined", None
        if not self._opened:
            return "joined", None
        if purpose == "page" and self._failed_at is not None:
            due = self.retry_at()
            if due is None or asyncio.get_running_loop().time() < due:
                return "not_due", None
        return self.request_acquisition(), None

    async def aclose(self) -> None:
        """Stop the timer and any probe, and leave the working tree served."""

        self._closed = True
        for task in self._tasks:
            task.cancel()
        await asyncio.gather(*self._tasks, return_exceptions=True)
        session = self.session
        if session is not None:
            await session.stop_probe()
            if session.served() is not None:
                checkout = checkout_revisions()
                if checkout is not None:
                    await checkout.serve_working_tree()
        set_origin_session(self.root, None)
        set_origin_opener(self.root, None)


# ``0`` (or ``false``, ``no``, ``off``) keeps every application of a folder, a server's
# and a one-shot ``--api``, ``--show``, or ``--ref``, from keeping any store of its
# checkout's origin: the folder is served as one whose origin is on this machine, with
# its own remote-tracking branches listed, nothing is fetched for it, and a refresh asked
# of it is refused as a folder's with no store. The lifespan reads it
# (:func:`lifespan_checkout_store`), so a transcript answers what a served page does.
# A pull request's comparison, which a reader asks a provider plugin for, still makes the
# store and fetches it from the origin (:func:`acquire_checkout_store`); a plugin's
# background work asks :func:`origin_store_wanted` first, as the GitHub plugin's prefetch
# does before it attaches a store for its lists. The test suite sets it, so that no
# server a test starts as a process of its own reaches a repository's origin, which one
# in process reaches through ``remote_url_for``; a test of the store unsets it
# (``tests/conftest.py``, bead mb-i4x0).
ORIGIN_STORE_ENV: Final = "METABROWSER_ORIGIN_STORE"
_OFF: Final = frozenset({"0", "false", "no", "off"})

# Whether the next application lifespan is a server's; see :func:`serve_checkout_store`.
_serving = False


def origin_store_wanted() -> bool:
    """Whether an application keeps a store of its checkout's origin (:data:`ORIGIN_STORE_ENV`)."""

    return os.environ.get(ORIGIN_STORE_ENV, "").strip().lower() not in _OFF


def serve_checkout_store(serving: bool = True) -> None:
    """Say that the next application lifespan serves its folder, so its store is kept fresh.

    A server acquires the store its checkout lacks and fetches it on the idle timer. A
    one-shot ``--show`` or ``--api`` says nothing, so it reads the store the cache has
    and reaches the network only through an explicit ``POST /api/source/refresh``.
    """

    global _serving
    _serving = serving


def _forget_serving() -> None:
    # Choosing a filesystem root starts over; the command that serves it says so again.
    serve_checkout_store(False)


register_root_callback(_forget_serving)


def checkout_store(app: Any) -> CheckoutStore | None:
    """The served checkout's store on *app*, or ``None``: a mirror, or a plain folder."""

    store = getattr(app.state, "checkout_store", None)
    return store if isinstance(store, CheckoutStore) else None


@asynccontextmanager
async def lifespan_checkout_store(app: Any) -> AsyncGenerator[None]:
    """Own the store a folder's server keeps beside its checkout.

    Entered after the refresh coordinator and before the checkout's revisions, so a ref
    named with ``--ref`` finds the store's opener set; a revision read from the store is
    closed, and the folder served again, as the checkout's lifespan is left, while the
    coordinator still runs. A server opens the store in the background, so its
    first page waits for no file read here; a one-shot command opens it at the request
    that reads it (:meth:`CheckoutStore.ensure_open`), so one that never asks about the
    origin loads nothing of the cache. Where :data:`ORIGIN_STORE_ENV` says to keep none,
    no application has a store, whichever command opened it.
    """

    app.state.checkout_store = None
    store: CheckoutStore | None = None
    coordinator = refresh_coordinator(app)
    checkout = checkout_revisions() if mirror_session(app) is None else None
    if checkout is not None and coordinator is not None and origin_store_wanted():
        # Nothing an earlier application in this process kept for the root is this one's.
        set_origin_session(checkout.root, None)
        store = CheckoutStore(checkout.root, coordinator, serving=_serving)
        app.state.checkout_store = store
        # A switch of what the folder serves opens the store first, so a ref named as
        # the application starts reads the origin's from it.
        set_origin_opener(checkout.root, store.opened_fetchable)
        if _serving:
            store.start()
    try:
        yield
    finally:
        app.state.checkout_store = None
        if store is not None:
            await store.aclose()


__all__ = [
    "ABSENCE_DETAIL",
    "ACQUISITION_RETRY_CAP_S",
    "ORIGIN_STORE_ENV",
    "AcquisitionFailure",
    "CheckoutStore",
    "CheckoutStoreError",
    "OriginAbsence",
    "OriginStore",
    "OriginStoreState",
    "acquire_checkout_store",
    "checkout_store",
    "lifespan_checkout_store",
    "origin_store_wanted",
    "serve_checkout_store",
    "store_turn",
]
