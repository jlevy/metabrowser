"""The fixed lock hierarchy and side locks of the ``f01`` cache.

Locks are BSD ``flock`` on lock files under ``cache/locks/``, never POSIX record locks,
which vanish when a process closes any descriptor for the file. The hierarchy, frozen in
``tests/fixtures/repository-cache/state-machines.json``, is:

1. the application-home lock, for layout migration and brief global enumeration;
2. source-alias locks, several in ascending slug order;
3. repository-store locks, several in ascending store-key order; and
4. provider/resource locks, several in ascending key order.

A thread acquires hierarchy locks in ascending rank, and within a rank in ascending key,
and never re-acquires one it holds; :class:`LockOrder` refuses anything else before a
descriptor is opened. Network work and long-running Git processes call
:func:`require_no_hierarchy_locks` first.

Side locks sit outside the order and are only ever tried without blocking. A staging
entry lock marks one owner's liveness. A store's fetch lock marks the one refresh that may
fetch into that published store; it is held across network work, which is why it cannot be
a hierarchy lock, and a second refresh that finds it busy reports that another process is
refreshing rather than waiting.

No lock protects a reader. A published store is never changed in place: nothing runs
``gc``, ``prune``, or ``repack`` on it, and a reader reaches it only through a source
alias, so a reader pinned to a commit ID holds no lock.

Which thread owns a lock follows from how long it is kept. A lock taken and released
inside one synchronous section belongs to the thread running that section. A lock that
async code keeps across ``await`` (a staging entry) belongs to the thread that keeps it,
the event-loop thread, even when a worker thread performs its ``open()`` and ``flock``
and records it in that thread's order. A pooled worker never records a lock it hands
back, so it cannot carry one into the unrelated work it runs next. No lock blocks a
thread that is running an event loop: :func:`_acquire` refuses it, and blocking sections
run in worker threads.

Every acquisition is its own ``open()`` of the lock file and returns a
:class:`CacheLock` that owns that descriptor. Descriptors are never shared or
duplicated, even within one process: ``flock`` state belongs to the open file
description, so a second attempt through a duplicate would be granted the first
holder's lock rather than refused. After acquiring, the holder compares the descriptor
with the path and retries if a sweep replaced the file. A lock file found shared with
another principal is replaced atomically, but only while this process holds the old
file's lock, taken without blocking; if that lock is busy the lock is refused.
"""

from __future__ import annotations

import asyncio
import errno
import functools
import os
import re
import threading
from collections.abc import Callable, Generator
from contextlib import contextmanager
from dataclasses import dataclass, field
from enum import StrEnum
from pathlib import Path
from types import TracebackType
from typing import Final, Self

from metabrowser.cache.identity import is_slug, is_store_key
from metabrowser.cancellable_thread import run_acquiring_thread, run_cancellable_thread
from metabrowser.home import (
    PrivateStorageError,
    PrivateStorageLocation,
    PrivateStorageViolation,
    open_private_file,
    write_private_file_atomic,
)

try:
    import fcntl
except ImportError:  # Windows: open_private_file refuses first as unverifiable.
    fcntl = None

LOCKS_DIRECTORY: Final = "cache/locks"
HOME_LOCK_PATH: Final = "cache/locks/home.lock"

_ENTRY_NAME_RE: Final = re.compile(r"^[a-z0-9][a-z0-9-]{0,63}$")
_RESOURCE_KEY_RE: Final = re.compile(r"^[a-z0-9][a-z0-9_-]{0,127}$")
_IDENTITY_ATTEMPTS: Final = 8
# How often an abandonable wait in a worker thread retries a busy lock. One busy attempt
# cost a median 2.4 ms (p90 9 ms) on a machine at load average 23; doubling from 5 ms to
# a 100 ms cap spends one attempt per 100 ms per waiter and notices an abandoned wait
# within one cap.
WAIT_RETRY_FIRST_S: Final = 0.005
WAIT_RETRY_MAX_S: Final = 0.1
_UNSUPPORTED_LOCK_ERRNOS: Final = frozenset(
    {errno.ENOLCK, errno.EOPNOTSUPP, errno.ENOTSUP, errno.EINVAL, errno.ENOSYS}
)
_LOCK_CHANGED: Final = (
    "its lock file kept being replaced while it was being locked. Make sure nothing else "
    "is modifying the application home, then retry"
)
_LOCKS_UNSUPPORTED: Final = (
    "its file system does not support the file locks the cache relies on. Set "
    "METABROWSER_HOME to a directory on a local file system"
)
_SHARED_LOCK_HELD: Final = (
    "a lock file that was shared with other users is locked by another process, so it "
    "cannot be replaced safely. Stop other Metabrowser processes and remove the lock "
    "file, or set METABROWSER_HOME to a private directory you own"
)


class LockKind(StrEnum):
    """Every lock the cache takes."""

    HOME = "home"
    SOURCE_ALIAS = "source_alias"
    REPOSITORY_STORE = "repository_store"
    PROVIDER_RESOURCE = "provider_resource"
    STAGING_ENTRY = "staging_entry"
    STORE_FETCH = "store_fetch"


HIERARCHY_RANKS: Final[dict[LockKind, int]] = {
    LockKind.HOME: 1,
    LockKind.SOURCE_ALIAS: 2,
    LockKind.REPOSITORY_STORE: 3,
    LockKind.PROVIDER_RESOURCE: 4,
}
_MULTIPLE: Final = frozenset(
    {LockKind.SOURCE_ALIAS, LockKind.REPOSITORY_STORE, LockKind.PROVIDER_RESOURCE}
)


class LockOrderError(RuntimeError):
    """An acquisition would break the frozen lock order or deadlock its own thread."""


class LockWaitAbandonedError(Exception):
    """A blocking lock wait in a worker thread was abandoned because its caller was cancelled."""


class LockBusyError(Exception):
    """A lock tried without blocking is held by another holder."""

    def __init__(self, kind: LockKind, key: str | None) -> None:
        super().__init__(f"the {kind.value} lock is held by another holder")
        self.kind: LockKind = kind
        self.key: str | None = key


@dataclass(frozen=True, slots=True)
class HeldLock:
    """One lock a thread holds: its kind and key."""

    kind: LockKind
    key: str | None


@dataclass(slots=True)
class LockOrder:
    """The locks one holder has, and the rules its next acquisition must follow.

    This is the production order check; :class:`CacheLock` consults the calling
    thread's instance, and the frozen lock-sequence fixtures replay against it.
    """

    held: list[HeldLock] = field(default_factory=list[HeldLock])
    _mutex: threading.Lock = field(default_factory=threading.Lock)

    def hierarchy(self) -> tuple[HeldLock, ...]:
        with self._mutex:
            return tuple(lock for lock in self.held if lock.kind in HIERARCHY_RANKS)

    def snapshot(self) -> tuple[HeldLock, ...]:
        with self._mutex:
            return tuple(self.held)

    def check(self, kind: LockKind, key: str | None, *, blocking: bool) -> None:
        """Raise :class:`LockOrderError` unless *kind* may be acquired now."""

        with self._mutex:
            ordered = [lock for lock in self.held if lock.kind in HIERARCHY_RANKS]
            if kind in HIERARCHY_RANKS:
                if kind in _MULTIPLE and not key:
                    raise LockOrderError(f"a {kind.value} lock needs a key")
                if ordered:
                    top = ordered[-1]
                    rank, top_rank = HIERARCHY_RANKS[kind], HIERARCHY_RANKS[top.kind]
                    if rank < top_rank:
                        raise LockOrderError(
                            f"the {kind.value} lock cannot be taken while holding the "
                            f"narrower {top.kind.value} lock"
                        )
                    if rank == top_rank and (
                        kind not in _MULTIPLE or key is None or top.key is None or key <= top.key
                    ):
                        raise LockOrderError(
                            f"{kind.value} locks are taken once each, in ascending key order"
                        )
                return
            if blocking and ordered:
                raise LockOrderError(
                    f"blocking on the {kind.value} lock while holding the "
                    f"{ordered[-1].kind.value} lock could deadlock"
                )

    def check_network(self, operation: str) -> None:
        """Raise :class:`LockOrderError` if any hierarchy lock is held."""

        with self._mutex:
            ordered = [lock for lock in self.held if lock.kind in HIERARCHY_RANKS]
        if ordered:
            raise LockOrderError(
                f"{operation} must not run while the {ordered[-1].kind.value} lock is held"
            )

    def acquired(self, kind: LockKind, key: str | None) -> None:
        with self._mutex:
            self.held.append(HeldLock(kind, key))

    def released(self, kind: LockKind, key: str | None) -> None:
        with self._mutex:
            for index in range(len(self.held) - 1, -1, -1):
                if self.held[index] == HeldLock(kind, key):
                    del self.held[index]
                    return
        raise LockOrderError(f"the {kind.value} lock is not held")


_THREAD_LOCKS = threading.local()


def lock_order() -> LockOrder:
    """Return the calling thread's lock order."""

    order = getattr(_THREAD_LOCKS, "order", None)
    if not isinstance(order, LockOrder):
        order = LockOrder()
        _THREAD_LOCKS.order = order
    return order


def held_locks() -> tuple[HeldLock, ...]:
    """Return the locks the calling thread holds, in acquisition order."""

    return lock_order().snapshot()


def require_no_hierarchy_locks(operation: str) -> None:
    """Refuse *operation*, such as network work, while a hierarchy lock is held."""

    lock_order().check_network(operation)


@dataclass(eq=False, slots=True)
class CacheLock:
    """One acquired lock, owning the one descriptor its ``flock`` lives on."""

    home: Path
    kind: LockKind
    key: str | None
    relative_path: str
    _fd: int | None
    _order: LockOrder

    @property
    def held(self) -> bool:
        return self._fd is not None

    @property
    def path(self) -> Path:
        return self.home / self.relative_path

    def release(self) -> None:
        """Release the lock; releasing twice is a no-op."""

        fd, self._fd = self._fd, None
        if fd is None:
            return
        try:
            os.close(fd)
        finally:
            self._order.released(self.kind, self.key)

    def remove_lock_file(self) -> None:
        """Unlink this lock's file while still holding it, then release.

        A process waiting on the old file acquires an unlinked inode, sees that the path
        no longer names it, and retries on a fresh file.
        """

        try:
            if self._fd is not None and _same_inode(self._fd, self.path):
                os.unlink(self.path)
        finally:
            self.release()

    def __enter__(self) -> Self:
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        self.release()


def _same_inode(fd: int, path: Path) -> bool:
    opened = os.fstat(fd)
    try:
        current = os.lstat(path)
    except FileNotFoundError:
        return False
    return (opened.st_dev, opened.st_ino) == (current.st_dev, current.st_ino)


def _unverifiable(path: Path, detail: str) -> PrivateStorageError:
    return PrivateStorageError(
        PrivateStorageViolation.UNVERIFIABLE, PrivateStorageLocation.ENTRY, path, detail=detail
    )


def _flock(fd: int, operation: int, path: Path) -> bool:
    """Apply *operation*; ``False`` when a non-blocking attempt found the lock busy."""

    if fcntl is None:
        raise _unverifiable(path, _LOCKS_UNSUPPORTED)
    try:
        fcntl.flock(fd, operation)
    except BlockingIOError:
        return False
    except OSError as error:
        if error.errno in _UNSUPPORTED_LOCK_ERRNOS:
            raise _unverifiable(path, _LOCKS_UNSUPPORTED) from error
        raise
    return True


def _replace_shared_lock_file(home: Path, relative_path: str) -> None:
    """Replace a lock file that was shared, holding the old file's lock while doing it."""

    assert fcntl is not None
    path = home / relative_path
    # "keep": the old lock file must stay exactly as it is until the replacement is
    # renamed over it, and the write below repairs the directories it goes through.
    fd = open_private_file(home, relative_path, os.O_RDONLY | os.O_NONBLOCK, shared="keep")
    try:
        if not _flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB, path):
            raise _unverifiable(path, _SHARED_LOCK_HELD)
        if not _same_inode(fd, path):
            return
        write_private_file_atomic(home, relative_path, b"")
    finally:
        os.close(fd)


def _open_lock_file(home: Path, relative_path: str) -> int:
    """Open a private lock file with write access, creating it if it is missing.

    Write access makes :func:`open_private_file` refuse a file that was ever shared
    instead of tightening it in place.
    """

    for _ in range(_IDENTITY_ATTEMPTS):
        try:
            return open_private_file(home, relative_path, os.O_RDWR | os.O_CREAT)
        except PrivateStorageError as error:
            if error.violation is not PrivateStorageViolation.PERMISSIVE:
                raise
        _replace_shared_lock_file(home, relative_path)
    raise _unverifiable(home / relative_path, _LOCK_CHANGED)


# The abandon signal for blocking waits on this thread; see :func:`run_lock_section`.
_WAITS = threading.local()


@contextmanager
def _abandonable_waits(abandon: threading.Event) -> Generator[None]:
    previous: threading.Event | None = getattr(_WAITS, "abandon", None)
    _WAITS.abandon = abandon
    try:
        yield
    finally:
        _WAITS.abandon = previous


def _wait_for_flock(fd: int, operation: int, path: Path, abandon: threading.Event) -> None:
    """Take a lock by retrying without blocking, until it is free or *abandon* is set.

    A thread blocked in ``flock`` cannot be interrupted, so a cancelled caller, and
    interpreter exit after it, would wait for as long as another process held the
    lock: a second Ctrl-C no longer stopped a command queued behind a busy home.
    """

    assert fcntl is not None
    delay = WAIT_RETRY_FIRST_S
    while not _flock(fd, operation | fcntl.LOCK_NB, path):
        if abandon.wait(delay):
            raise LockWaitAbandonedError(f"abandoned a wait for {path.name}")
        delay = min(delay * 2, WAIT_RETRY_MAX_S)


async def run_lock_section[ResultT](
    work: Callable[[], ResultT], /, *, release: Callable[[ResultT], None] | None = None
) -> ResultT:
    """Run a synchronous locked section in a worker thread; cancellation abandons its waits.

    Without *release*, a cancelled caller waits for the section to finish (it stops
    within one retry interval if it is still waiting for a lock), so nothing the
    section covers is still running when the caller's own cleanup starts. With
    *release*, the section keeps something past its return; cancellation propagates at
    once and whatever the section goes on to acquire is released, as
    :func:`run_acquiring_thread` does.

    An abandoned section returns a private marker instead of raising: its caller is
    already cancelled, and an exception left in the shielded worker is logged as
    unretrieved on Python 3.14.
    """

    def section(abandon: threading.Event) -> ResultT | _Abandoned:
        with _abandonable_waits(abandon):
            try:
                return work()
            except LockWaitAbandonedError:
                if abandon.is_set():
                    return _ABANDONED
                raise

    if release is None:
        result = await run_cancellable_thread(section)
    else:
        abandon = threading.Event()

        def release_kept(kept: ResultT | _Abandoned) -> None:
            if not isinstance(kept, _Abandoned):
                release(kept)

        try:
            result = await run_acquiring_thread(
                functools.partial(section, abandon), release=release_kept
            )
        except asyncio.CancelledError:
            abandon.set()
            raise
    if isinstance(result, _Abandoned):
        # Only reached if the abandon event was set without cancelling this caller.
        raise LockWaitAbandonedError("a lock wait was abandoned")
    return result


class _Abandoned:
    """What an abandoned locked section returns in place of its result."""


_ABANDONED: Final = _Abandoned()


def _refuse_blocking_on_event_loop(kind: LockKind) -> None:
    """Refuse a blocking ``flock`` on a thread that is running an event loop.

    The wait would stall every coroutine on that loop for as long as another process
    holds the lock, and a holder in this process that needs the loop to finish would
    never get it. Blocking acquisition belongs in a worker thread, as one synchronous
    section with the work it covers.
    """

    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return
    raise LockOrderError(
        f"blocking on the {kind.value} lock would stall the event loop; take it in a worker thread"
    )


def _acquire(
    home: Path,
    kind: LockKind,
    key: str | None,
    relative_path: str,
    *,
    blocking: bool,
    order: LockOrder | None = None,
) -> CacheLock:
    if blocking:
        _refuse_blocking_on_event_loop(kind)
    order = lock_order() if order is None else order
    order.check(kind, key, blocking=blocking)
    if fcntl is None:
        raise _unverifiable(home / relative_path, _LOCKS_UNSUPPORTED)
    operation = fcntl.LOCK_EX | (0 if blocking else fcntl.LOCK_NB)
    path = home / relative_path
    abandon: threading.Event | None = getattr(_WAITS, "abandon", None) if blocking else None
    for _ in range(_IDENTITY_ATTEMPTS):
        fd = _open_lock_file(home, relative_path)
        try:
            if abandon is not None:
                _wait_for_flock(fd, operation, path, abandon)
            elif not _flock(fd, operation, path):
                raise LockBusyError(kind, key)
            if _same_inode(fd, path):
                order.acquired(kind, key)
                return CacheLock(home, kind, key, relative_path, fd, order)
        except BaseException:
            os.close(fd)
            raise
        os.close(fd)
    raise _unverifiable(path, _LOCK_CHANGED)


def _require(valid: bool, what: str) -> None:
    if not valid:
        raise ValueError(f"invalid {what}")


def application_home_lock(home: Path, *, blocking: bool = True) -> CacheLock:
    """Acquire the application-home lock."""

    return _acquire(home, LockKind.HOME, None, HOME_LOCK_PATH, blocking=blocking)


def source_alias_lock(home: Path, slug: str, *, blocking: bool = True) -> CacheLock:
    """Acquire the lock for one source alias; take several in ascending slug order."""

    _require(is_slug(slug), "source slug")
    return _acquire(
        home,
        LockKind.SOURCE_ALIAS,
        slug,
        f"{LOCKS_DIRECTORY}/sources/{slug}.lock",
        blocking=blocking,
    )


def repository_store_lock(home: Path, store_key: str, *, blocking: bool = True) -> CacheLock:
    """Acquire the lock for one repository store; take several in ascending key order."""

    _require(is_store_key(store_key), "store key")
    return _acquire(
        home,
        LockKind.REPOSITORY_STORE,
        store_key,
        f"{LOCKS_DIRECTORY}/stores/{store_key}.lock",
        blocking=blocking,
    )


def provider_resource_lock(home: Path, resource_key: str, *, blocking: bool = True) -> CacheLock:
    """Acquire the lock for one provider resource.

    The rank is frozen; the key's spelling belongs to the provider storage plan.
    """

    _require(_RESOURCE_KEY_RE.fullmatch(resource_key) is not None, "provider resource key")
    return _acquire(
        home,
        LockKind.PROVIDER_RESOURCE,
        resource_key,
        f"{LOCKS_DIRECTORY}/providers/{resource_key}.lock",
        blocking=blocking,
    )


def _entry_lock(
    home: Path,
    kind: LockKind,
    directory: str,
    entry: str,
    *,
    order: LockOrder | None = None,
) -> CacheLock:
    _require(_ENTRY_NAME_RE.fullmatch(entry) is not None, f"{kind.value} name")
    return _acquire(
        home,
        kind,
        entry,
        f"{LOCKS_DIRECTORY}/{directory}/{entry}.lock",
        blocking=False,
        order=order,
    )


def staging_entry_lock(home: Path, entry: str, *, order: LockOrder | None = None) -> CacheLock:
    """Try the liveness lock of one staging entry without blocking.

    *order* records the lock for a holder other than the calling thread: a worker
    thread that claims an entry for a coroutine passes the coroutine's thread's order,
    because that thread keeps the entry after the worker returns.
    """

    return _entry_lock(home, LockKind.STAGING_ENTRY, "staging", entry, order=order)


def store_fetch_lock(home: Path, store_key: str, *, order: LockOrder | None = None) -> CacheLock:
    """Try the fetch side lock of one published store without blocking.

    Held by the one refresh fetching into the store, across its network work, so it
    sits outside the hierarchy and is never waited on: :class:`LockBusyError` means
    another holder is refreshing the store now. *order* is as for
    :func:`staging_entry_lock`.
    """

    _require(is_store_key(store_key), "store key")
    return _acquire(
        home,
        LockKind.STORE_FETCH,
        store_key,
        f"{LOCKS_DIRECTORY}/stores/{store_key}.fetch.lock",
        blocking=False,
        order=order,
    )


def is_entry_name(value: str) -> bool:
    """Whether *value* is a valid staging entry name."""

    return _ENTRY_NAME_RE.fullmatch(value) is not None


__all__ = [
    "HIERARCHY_RANKS",
    "HOME_LOCK_PATH",
    "LOCKS_DIRECTORY",
    "WAIT_RETRY_FIRST_S",
    "WAIT_RETRY_MAX_S",
    "CacheLock",
    "HeldLock",
    "LockBusyError",
    "LockKind",
    "LockOrder",
    "LockOrderError",
    "application_home_lock",
    "held_locks",
    "is_entry_name",
    "lock_order",
    "provider_resource_lock",
    "repository_store_lock",
    "require_no_hierarchy_locks",
    "source_alias_lock",
    "staging_entry_lock",
    "store_fetch_lock",
]
