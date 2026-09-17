"""The fixed lock hierarchy and side locks of the ``f01`` cache.

Locks are BSD ``flock`` on lock files under ``cache/locks/``, never POSIX record locks,
which vanish when a process closes any descriptor for the file. The hierarchy, frozen in
``tests/fixtures/repository-cache/state-machines.json``, is:

1. the application-home lock, for layout migration, brief global enumeration, and
   moving quarantined entries to trash;
2. source-alias locks, several in ascending slug order;
3. repository-store locks, several in ascending store-key order; and
4. provider/resource locks, several in ascending key order.

A thread acquires hierarchy locks in ascending rank, and within a rank in ascending key,
and never re-acquires one it holds; :class:`LockOrder` refuses anything else before a
descriptor is opened. Network work and long-running Git processes call
:func:`require_no_hierarchy_locks` first.

Side locks sit outside the order. A staging, trash, or job entry lock marks one owner's
liveness and is only ever tried without blocking. The store lease is the
``<store-key>.maintenance.lock`` file: its shared form may block only while the thread
holds no hierarchy lock, and its exclusive form never blocks.

Every acquisition is its own ``open()`` of the lock file and returns a
:class:`CacheLock` that owns that descriptor. Descriptors are never shared or
duplicated, even within one process: ``flock`` state belongs to the open file
description, so an exclusive attempt through a duplicate of a shared lease would
silently convert the lease rather than be refused. After acquiring, the holder compares
the descriptor with the path and retries if a sweep replaced the file. A lock file found
shared with another principal is replaced atomically, but only while this process holds
the old file's lock, taken without blocking; if that lock is busy the lock is refused.
"""

from __future__ import annotations

import errno
import os
import re
import threading
from dataclasses import dataclass, field
from enum import StrEnum
from pathlib import Path
from types import TracebackType
from typing import Final, Self

from metabrowser.cache.identity import is_slug, is_store_key
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
    TRASH_ENTRY = "trash_entry"
    JOB_ENTRY = "job_entry"
    MAINTENANCE_SHARED = "maintenance_shared"
    MAINTENANCE_EXCLUSIVE = "maintenance_exclusive"


HIERARCHY_RANKS: Final[dict[LockKind, int]] = {
    LockKind.HOME: 1,
    LockKind.SOURCE_ALIAS: 2,
    LockKind.REPOSITORY_STORE: 3,
    LockKind.PROVIDER_RESOURCE: 4,
}
_MULTIPLE: Final = frozenset(
    {LockKind.SOURCE_ALIAS, LockKind.REPOSITORY_STORE, LockKind.PROVIDER_RESOURCE}
)
_MAINTENANCE: Final = frozenset({LockKind.MAINTENANCE_SHARED, LockKind.MAINTENANCE_EXCLUSIVE})


class LockOrderError(RuntimeError):
    """An acquisition would break the frozen lock order or deadlock its own thread."""


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
            # A second shared lease or entry-lock attempt is its own open, so it either
            # coexists or reports busy. Taking a store's maintenance lock in the other mode
            # would wait on this thread's own lease, or refuse maintenance it asked for.
            if kind in _MAINTENANCE:
                other = (
                    LockKind.MAINTENANCE_EXCLUSIVE
                    if kind is LockKind.MAINTENANCE_SHARED
                    else LockKind.MAINTENANCE_SHARED
                )
                if HeldLock(other, key) in self.held:
                    raise LockOrderError(
                        "this thread already holds this store's maintenance lock in the other mode"
                    )
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


def _acquire(
    home: Path,
    kind: LockKind,
    key: str | None,
    relative_path: str,
    *,
    shared: bool,
    blocking: bool,
) -> CacheLock:
    order = lock_order()
    order.check(kind, key, blocking=blocking)
    if fcntl is None:
        raise _unverifiable(home / relative_path, _LOCKS_UNSUPPORTED)
    operation = (fcntl.LOCK_SH if shared else fcntl.LOCK_EX) | (0 if blocking else fcntl.LOCK_NB)
    path = home / relative_path
    for _ in range(_IDENTITY_ATTEMPTS):
        fd = _open_lock_file(home, relative_path)
        try:
            if not _flock(fd, operation, path):
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

    return _acquire(home, LockKind.HOME, None, HOME_LOCK_PATH, shared=False, blocking=blocking)


def source_alias_lock(home: Path, slug: str, *, blocking: bool = True) -> CacheLock:
    """Acquire the lock for one source alias; take several in ascending slug order."""

    _require(is_slug(slug), "source slug")
    return _acquire(
        home,
        LockKind.SOURCE_ALIAS,
        slug,
        f"{LOCKS_DIRECTORY}/sources/{slug}.lock",
        shared=False,
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
        shared=False,
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
        shared=False,
        blocking=blocking,
    )


def store_lease(home: Path, store_key: str, *, blocking: bool = True) -> CacheLock:
    """Acquire a store's shared maintenance lock: the lease that defers reclamation."""

    _require(is_store_key(store_key), "store key")
    return _acquire(
        home,
        LockKind.MAINTENANCE_SHARED,
        store_key,
        f"{LOCKS_DIRECTORY}/stores/{store_key}.maintenance.lock",
        shared=True,
        blocking=blocking,
    )


def store_maintenance_lock(home: Path, store_key: str) -> CacheLock:
    """Try a store's exclusive maintenance lock without blocking."""

    _require(is_store_key(store_key), "store key")
    return _acquire(
        home,
        LockKind.MAINTENANCE_EXCLUSIVE,
        store_key,
        f"{LOCKS_DIRECTORY}/stores/{store_key}.maintenance.lock",
        shared=False,
        blocking=False,
    )


def _entry_lock(home: Path, kind: LockKind, directory: str, entry: str) -> CacheLock:
    _require(_ENTRY_NAME_RE.fullmatch(entry) is not None, f"{kind.value} name")
    return _acquire(
        home,
        kind,
        entry,
        f"{LOCKS_DIRECTORY}/{directory}/{entry}.lock",
        shared=False,
        blocking=False,
    )


def staging_entry_lock(home: Path, entry: str) -> CacheLock:
    """Try the liveness lock of one staging entry without blocking."""

    return _entry_lock(home, LockKind.STAGING_ENTRY, "staging", entry)


def trash_entry_lock(home: Path, entry: str) -> CacheLock:
    """Try the liveness lock of one trash entry without blocking."""

    return _entry_lock(home, LockKind.TRASH_ENTRY, "trash", entry)


def job_entry_lock(home: Path, job_id: str) -> CacheLock:
    """Try the liveness lock of one fetch job without blocking."""

    return _entry_lock(home, LockKind.JOB_ENTRY, "jobs", job_id)


def is_entry_name(value: str) -> bool:
    """Whether *value* is a valid staging, trash, quarantine, or job entry name."""

    return _ENTRY_NAME_RE.fullmatch(value) is not None


__all__ = [
    "HIERARCHY_RANKS",
    "HOME_LOCK_PATH",
    "LOCKS_DIRECTORY",
    "CacheLock",
    "HeldLock",
    "LockBusyError",
    "LockKind",
    "LockOrder",
    "LockOrderError",
    "application_home_lock",
    "held_locks",
    "is_entry_name",
    "job_entry_lock",
    "lock_order",
    "provider_resource_lock",
    "repository_store_lock",
    "require_no_hierarchy_locks",
    "source_alias_lock",
    "staging_entry_lock",
    "store_lease",
    "store_maintenance_lock",
    "trash_entry_lock",
]
