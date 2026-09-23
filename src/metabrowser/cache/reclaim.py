"""The startup sweep of ``staging/``: the one thing the cache deletes.

The operation follows its machine in ``tests/fixtures/repository-cache/state-machines.json``
and reports every transition, with the locks held at that moment, to an optional
observer; the fixture replay checks those reports against the frozen machine.

Under the application-home lock, the sweep lists the entry names; releases it; then
deletes each entry whose liveness lock can be taken without blocking. Liveness is the
lock, never age: a crashed holder's lock is already free, and no age tells a slow clone
from a dead one. Deletion runs outside the home lock. Lock files whose entry is gone and
whose lock is free are removed too.

Nothing here deletes a published store. A store no alias names, which a crash between
an acquisition's two renames leaves behind, stays in place until the next acquisition
of its source reuses it.
"""

from __future__ import annotations

import logging
import os
import shutil
import stat
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Final

from metabrowser.cache.locks import (
    LockBusyError,
    application_home_lock,
    held_locks,
    is_entry_name,
    staging_entry_lock,
)
from metabrowser.cache.paths import (
    STAGING,
    STAGING_LOCKS,
)
from metabrowser.home import PrivateStorageError

log = logging.getLogger(__name__)

_LOCK_SUFFIX: Final = ".lock"
# A repair unblocks one directory, and rmtree does not revisit what it already skipped,
# so the walk is repeated while it keeps repairing something. Each round is bounded by
# the tree; the loop only has to outlast the nesting a crashed clone can leave.
_REMOVE_ATTEMPTS: Final = 8
# The rmtree calls that need owner access on the path they name rather than on the
# directory that holds it: opening and scanning read the directory itself, while
# unlinking, removing, and inspecting a name are permitted by its parent.
_DIRECTORY_READS: Final[frozenset[object]] = frozenset({os.open, os.scandir})
# Setting a mode without following a link needs lchmod, which POSIX does not require.
_LINK_SAFE_CHMOD: Final = os.chmod in os.supports_follow_symlinks


@dataclass(frozen=True, slots=True)
class MachineEvent:
    """One transition of a frozen machine and the lock kinds held when it happened."""

    machine: str
    event: str
    holds: frozenset[str]


type MachineObserver = Callable[[MachineEvent], None]


def _emit(observer: MachineObserver | None, machine: str, event: str) -> None:
    if observer is not None:
        holds = frozenset(lock.kind.value for lock in held_locks())
        observer(MachineEvent(machine, event, holds))


def _grant_owner_access(directory: str) -> bool:
    """Restore owner access to *directory*; whether anything was widened.

    The mode is read and set through a descriptor of the directory that holds it, so
    the repair cannot leave the entry being deleted, and an entry that is not a
    directory any more is left alone rather than widened.
    """

    parent, _, name = directory.rpartition(os.sep)
    parent_fd = os.open(
        parent or os.sep, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC
    )
    try:
        status = os.stat(name, dir_fd=parent_fd, follow_symlinks=False)
        mode = stat.S_IMODE(status.st_mode)
        if not stat.S_ISDIR(status.st_mode) or mode & stat.S_IRWXU == stat.S_IRWXU:
            return False
        if _LINK_SAFE_CHMOD:
            os.chmod(name, mode | stat.S_IRWXU, dir_fd=parent_fd, follow_symlinks=False)
        else:
            # Only the owner can write this directory, and the entry was just seen not
            # to be a link, so the name cannot have become one under the same lock.
            os.chmod(name, mode | stat.S_IRWXU, dir_fd=parent_fd)
        return True
    finally:
        os.close(parent_fd)


def _remove_tree(path: Path) -> bool:
    """Delete an entry below the home without following links; ``False`` on failure.

    A crashed acquisition can leave a directory its owner cannot search or read, which
    ``rmtree`` reports through the call that failed and then walks past. Owner access is
    restored on what blocked that call and the walk is repeated, so the entry goes in
    this sweep rather than in some later one. ``rmtree`` raises nothing of its own once
    it has an ``onexc`` handler, so the handler must not raise either: anything left
    behind is reported here, and the next sweep retries the entry.
    """

    def restore_owner_access(
        function: Callable[..., object], failed: str, error: BaseException
    ) -> None:
        if not isinstance(error, PermissionError):
            # A directory this round walked past is reported here as "not empty", which
            # the next round settles, so only a failure that outlives them is logged.
            refused.append(error)
            return
        blocked = failed if function in _DIRECTORY_READS else os.path.dirname(failed)
        try:
            if _grant_owner_access(blocked):
                repaired.append(blocked)
        except OSError as repair_error:
            refused.append(repair_error)

    try:
        status = os.lstat(path)
    except FileNotFoundError:
        return True
    except OSError:
        log.warning("Could not inspect a cache entry; the next sweep retries it", exc_info=True)
        return False
    if not stat.S_ISDIR(status.st_mode):
        try:
            os.unlink(path)
        except OSError:
            log.warning("Could not remove a cache entry; the next sweep retries it", exc_info=True)
            return False
        return True
    repaired: list[str] = []
    refused: list[BaseException] = []
    for _ in range(_REMOVE_ATTEMPTS):
        rounds = len(repaired)
        refused.clear()
        try:
            shutil.rmtree(path, onexc=restore_owner_access)
        except OSError as error:
            refused.append(error)
            break
        if not os.path.lexists(path):
            return True
        if len(repaired) == rounds:
            break
    log.warning(
        "Could not remove a cache entry; the next sweep retries it",
        exc_info=refused[0] if refused else None,
    )
    return False


# ── Startup sweep ──────────────────────────────────────────────────


@dataclass(frozen=True, slots=True)
class SweepReport:
    """What one sweep removed, left for a live owner, or could not handle."""

    removed: tuple[str, ...] = ()
    live: tuple[str, ...] = ()
    unrecognized: tuple[str, ...] = ()
    failed: tuple[str, ...] = ()
    removed_lock_files: tuple[str, ...] = ()


def sweep_staging(home: Path, *, observer: MachineObserver | None = None) -> SweepReport:
    """Delete staging entries whose owner is gone, and their free lock files."""

    machine = "startup_sweep"
    with application_home_lock(home):
        names = sorted(entry.name for entry in os.scandir(home / STAGING))
        lock_names = sorted(entry.name for entry in os.scandir(home / STAGING_LOCKS))
        _emit(observer, machine, "begin")
    _emit(observer, machine, "listed")
    removed: list[str] = []
    live: list[str] = []
    unrecognized: list[str] = []
    failed: list[str] = []
    for name in names:
        logical = f"{STAGING}/{name}"
        if not is_entry_name(name):
            unrecognized.append(logical)
            continue
        try:
            lock = staging_entry_lock(home, name)
        except LockBusyError:
            _emit(observer, machine, "entry_lock_busy")
            live.append(logical)
            continue
        except PrivateStorageError:
            # Its lock cannot be verified, so liveness is unknown: keep the entry and
            # report it rather than abandon the rest of the sweep.
            log.warning("Skipped a cache entry whose lock file is unusable", exc_info=True)
            failed.append(logical)
            continue
        try:
            _emit(observer, machine, "entry_lock_acquired")
            (removed if _remove_tree(home / STAGING / name) else failed).append(logical)
            _emit(observer, machine, "removed")
        finally:
            lock.remove_lock_file()
    removed_lock_files = _remove_orphan_lock_files(home, lock_names, set(names))
    _emit(observer, machine, "exhausted")
    return SweepReport(
        tuple(removed), tuple(live), tuple(unrecognized), tuple(failed), removed_lock_files
    )


def _remove_orphan_lock_files(
    home: Path, lock_names: Sequence[str], entry_names: set[str]
) -> tuple[str, ...]:
    removed: list[str] = []
    for lock_name in lock_names:
        name = lock_name.removesuffix(_LOCK_SUFFIX)
        if name == lock_name or name in entry_names or not is_entry_name(name):
            continue
        try:
            lock = staging_entry_lock(home, name)
        except (LockBusyError, PrivateStorageError):
            continue
        if os.path.lexists(home / STAGING / name):
            lock.release()
            continue
        lock.remove_lock_file()
        removed.append(f"{STAGING_LOCKS}/{lock_name}")
    return tuple(removed)


__all__ = [
    "MachineEvent",
    "MachineObserver",
    "SweepReport",
    "sweep_staging",
]
