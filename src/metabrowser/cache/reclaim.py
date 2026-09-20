"""Reclaiming ``staging/``, ``trash/``, quarantine, and unreferenced stores.

Each operation follows its machine in ``tests/fixtures/repository-cache/state-machines.json``
and reports every transition, with the locks held at that moment, to an optional
observer; the fixture replay checks those reports against the frozen machines.

- **Startup sweep** (``startup_sweep``). Under the application-home lock, list the entry
  names; release it; then delete each entry whose liveness lock can be taken without
  blocking. Liveness is the lock, never age: a crashed holder's lock is already free,
  and no age tells a slow clone from a dead one. Deletion runs outside the home lock.
  Lock files whose entry is gone and whose lock is free are removed too.
- **Recoverable trash.** An entry moves into ``trash/<entry>/`` under its owning lock
  while the trash entry's liveness lock is held, and is deleted at the end of the same
  operation; the sweep removes anything a crashed operation left.
- **Quarantine** (``quarantine``). Never reclaimed automatically. Under the exclusive
  maintenance locks and the ordered source-alias and store locks, a store that still
  fails revalidation moves to ``quarantine/<entry>/`` after the aliases naming it, so a
  crash between the two leaves the aliases retained and an ordinary unreferenced store.
  A store no alias was seen to name is quarantined under its store lock alone, after
  verifying there that no alias names it. Only an explicit purge moves a quarantined
  entry to trash, under the application-home lock.
- **Store reclamation** (``store_reclamation``). A store no alias names is moved to
  trash under its exclusive maintenance lock, which a live lease makes busy, and its
  store lock. Provider references are not modeled yet, so any provider binding or
  provider repository in the home counts as a reference. Startup lists
  ``repository-stores`` and runs this for each published store after the staging/trash
  sweep. Read routes do not.
"""

from __future__ import annotations

import logging
import os
import secrets
import shutil
import stat
from collections.abc import Callable, Sequence
from contextlib import ExitStack
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from typing import Final

from metabrowser.cache.atomic import RecordError, publish_entry, read_record
from metabrowser.cache.identity import IDENTITY_PREFIX, is_slug, is_store_key
from metabrowser.cache.locks import (
    CacheLock,
    LockBusyError,
    application_home_lock,
    held_locks,
    is_entry_name,
    repository_store_lock,
    source_alias_lock,
    staging_entry_lock,
    store_maintenance_lock,
    trash_entry_lock,
)
from metabrowser.cache.paths import (
    PROVIDER_BINDINGS,
    PROVIDER_REPOSITORIES,
    REPOSITORY_STORES,
    SOURCES,
    STAGING,
    STAGING_LOCKS,
    TRASH,
    TRASH_LOCKS,
    quarantine_entry,
    source_directory,
    source_record,
    store_directory,
    trash_entry,
)
from metabrowser.cache.records import REPOSITORY_STORE_ALIAS_CONTRACT_ID, RepositoryStoreAlias
from metabrowser.home import PrivateStorageError, ensure_private_directory

log = logging.getLogger(__name__)

_ENTRY_ATTEMPTS: Final = 4
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

    def __add__(self, other: SweepReport) -> SweepReport:
        return SweepReport(
            self.removed + other.removed,
            self.live + other.live,
            self.unrecognized + other.unrecognized,
            self.failed + other.failed,
            self.removed_lock_files + other.removed_lock_files,
        )


def _sweep(
    home: Path,
    directory: str,
    locks_directory: str,
    entry_lock: Callable[[Path, str], CacheLock],
    observer: MachineObserver | None,
) -> SweepReport:
    machine = "startup_sweep"
    with application_home_lock(home):
        names = sorted(entry.name for entry in os.scandir(home / directory))
        lock_names = sorted(entry.name for entry in os.scandir(home / locks_directory))
        _emit(observer, machine, "begin")
    _emit(observer, machine, "listed")
    removed: list[str] = []
    live: list[str] = []
    unrecognized: list[str] = []
    failed: list[str] = []
    for name in names:
        logical = f"{directory}/{name}"
        if not is_entry_name(name):
            unrecognized.append(logical)
            continue
        try:
            lock = entry_lock(home, name)
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
            (removed if _remove_tree(home / directory / name) else failed).append(logical)
            _emit(observer, machine, "removed")
        finally:
            lock.remove_lock_file()
    removed_lock_files = _remove_orphan_lock_files(
        home, directory, locks_directory, lock_names, set(names), entry_lock
    )
    _emit(observer, machine, "exhausted")
    return SweepReport(
        tuple(removed), tuple(live), tuple(unrecognized), tuple(failed), removed_lock_files
    )


def _remove_orphan_lock_files(
    home: Path,
    directory: str,
    locks_directory: str,
    lock_names: Sequence[str],
    entry_names: set[str],
    entry_lock: Callable[[Path, str], CacheLock],
) -> tuple[str, ...]:
    removed: list[str] = []
    for lock_name in lock_names:
        name = lock_name.removesuffix(_LOCK_SUFFIX)
        if name == lock_name or name in entry_names or not is_entry_name(name):
            continue
        try:
            lock = entry_lock(home, name)
        except (LockBusyError, PrivateStorageError):
            continue
        if os.path.lexists(home / directory / name):
            lock.release()
            continue
        lock.remove_lock_file()
        removed.append(f"{locks_directory}/{lock_name}")
    return tuple(removed)


def reclaim_staging(home: Path, *, observer: MachineObserver | None = None) -> SweepReport:
    """Delete staging entries whose owner is gone."""

    return _sweep(home, STAGING, STAGING_LOCKS, staging_entry_lock, observer)


def reclaim_trash(home: Path, *, observer: MachineObserver | None = None) -> SweepReport:
    """Delete trash a crashed purge, quarantine, or reclamation left behind."""

    return _sweep(home, TRASH, TRASH_LOCKS, trash_entry_lock, observer)


def sweep_staging_and_trash(home: Path, *, observer: MachineObserver | None = None) -> SweepReport:
    """Run the startup sweep over ``staging/`` and then ``trash/``."""

    return reclaim_staging(home, observer=observer) + reclaim_trash(home, observer=observer)


# ── Recoverable trash ──────────────────────────────────────────────


@dataclass(slots=True)
class TrashEntry:
    """A trash entry this process owns, with its held liveness lock."""

    name: str
    lock: CacheLock

    @property
    def relative_path(self) -> str:
        return trash_entry(self.name)


def begin_trash_entry(home: Path, purpose: str) -> TrashEntry:
    """Create and lock a new, empty ``trash/<purpose>-<random>/`` entry."""

    for _ in range(_ENTRY_ATTEMPTS):
        name = f"{purpose}-{secrets.token_hex(8)}"
        try:
            lock = trash_entry_lock(home, name)
        except LockBusyError:
            continue
        try:
            ensure_private_directory(home, trash_entry(name))
        except BaseException:
            lock.remove_lock_file()
            raise
        return TrashEntry(name, lock)
    raise RuntimeError("could not allocate a trash entry")


def move_to_trash(home: Path, entry: TrashEntry, relative_path: str, *, owner: CacheLock) -> str:
    """Move a cache path into *entry* under its owning lock; return where it went.

    The path keeps its logical location inside the entry, so
    ``cache/sources/<slug>`` becomes ``cache/trash/<entry>/sources/<slug>``.
    """

    if not entry.lock.held:
        raise RuntimeError("the trash entry's liveness lock must be held")
    target = f"{entry.relative_path}/{relative_path.removeprefix('cache/')}"
    publish_entry(home, relative_path, target, owner=owner)
    return target


def delete_trash_entry(home: Path, entry: TrashEntry) -> bool:
    """Delete a trash entry and its lock file; ``False`` leaves it for the sweep."""

    try:
        return _remove_tree(home / entry.relative_path)
    finally:
        entry.lock.remove_lock_file()


def _move_into_new_trash(
    home: Path, purpose: str, relative_path: str, owner: CacheLock
) -> TrashEntry:
    trash = begin_trash_entry(home, purpose)
    try:
        move_to_trash(home, trash, relative_path, owner=owner)
    except BaseException:
        delete_trash_entry(home, trash)
        raise
    return trash


# ── Store reclamation ──────────────────────────────────────────────


class StoreReclamation(StrEnum):
    """How a store reclamation ended."""

    BUSY = "exclusive_busy"
    ABSENT = "store_absent"
    REFERENCED = "still_referenced"
    RECLAIMED = "reclaimed"
    DELETE_FAILED = "delete_failed"


def store_is_referenced(home: Path, store_key: str) -> bool:
    """Whether any alias names the store, failing safe on anything it cannot read.

    Aliases that name a store are written under that store's lease, so a caller holding
    its exclusive maintenance lock sees a stable answer.
    """

    for directory in (PROVIDER_BINDINGS, PROVIDER_REPOSITORIES):
        try:
            if any(True for _ in os.scandir(home / directory)):
                return True
        except FileNotFoundError:
            continue
    store_id = f"{IDENTITY_PREFIX}{store_key}"
    for entry in os.scandir(home / SOURCES):
        if not is_slug(entry.name):
            return True
        try:
            alias = read_record(
                home,
                source_record(entry.name, "store-alias.yml"),
                REPOSITORY_STORE_ALIAS_CONTRACT_ID,
            )
        except FileNotFoundError:
            continue
        except (RecordError, PrivateStorageError, OSError):
            return True
        if not isinstance(alias, RepositoryStoreAlias) or alias.store_id == store_id:
            return True
    return False


def reclaim_store(
    home: Path, store_key: str, *, observer: MachineObserver | None = None
) -> StoreReclamation:
    """Move an unreferenced, unleased store to trash and delete it."""

    machine = "store_reclamation"
    try:
        maintenance = store_maintenance_lock(home, store_key)
    except LockBusyError:
        _emit(observer, machine, "exclusive_busy")
        return StoreReclamation.BUSY
    try:
        _emit(observer, machine, "try_exclusive")
        with repository_store_lock(home, store_key) as store_lock:
            if not os.path.lexists(home / store_directory(store_key)):
                _emit(observer, machine, "store_absent")
                return StoreReclamation.ABSENT
            if store_is_referenced(home, store_key):
                _emit(observer, machine, "still_referenced")
                return StoreReclamation.REFERENCED
            trash = _move_into_new_trash(home, "reclaim", store_directory(store_key), store_lock)
            _emit(observer, machine, "move_to_trash")
    finally:
        maintenance.release()
    try:
        deleted = _remove_tree(home / trash.relative_path)
        _emit(observer, machine, "delete_completed")
    finally:
        # Whatever deletion did, the trash entry's liveness lock is released, or the
        # sweep would read the leaked descriptor as a live owner for this process's life.
        trash.lock.remove_lock_file()
    return StoreReclamation.RECLAIMED if deleted else StoreReclamation.DELETE_FAILED


def reclaim_unreferenced_stores(
    home: Path, *, observer: MachineObserver | None = None
) -> tuple[str, ...]:
    """Reclaim published stores no alias names.

    A live lease makes exclusive maintenance busy, so a concurrent publish is skipped
    and retried on a later open. Directory names that are not store keys stay in place.
    """

    try:
        names = sorted(entry.name for entry in os.scandir(home / REPOSITORY_STORES))
    except FileNotFoundError:
        return ()
    reclaimed: list[str] = []
    for name in names:
        if not is_store_key(name):
            continue
        if store_is_referenced(home, name):
            continue
        try:
            outcome = reclaim_store(home, name, observer=observer)
        except PrivateStorageError:
            log.warning("Skipped a repository store whose lock file is unusable", exc_info=True)
            continue
        if outcome is StoreReclamation.RECLAIMED:
            reclaimed.append(name)
        elif outcome is StoreReclamation.DELETE_FAILED:
            log.warning("Could not delete a reclaimed store; the next sweep retries it")
    return tuple(reclaimed)


# ── Quarantine ─────────────────────────────────────────────────────


@dataclass(frozen=True, slots=True)
class QuarantineOutcome:
    """How a quarantine attempt ended and, if it moved anything, where it is retained."""

    state: str
    entry: str | None = None
    retained: tuple[str, ...] = ()


def aliases_naming_stores(home: Path, store_keys: Sequence[str]) -> tuple[str, ...]:
    """Return the slugs of sources whose alias names any of *store_keys*, in slug order.

    An alias record that cannot be read may name one of them, so its slug is included:
    the caller then locks and retains it rather than trusting that it does not. An entry
    whose name is not a slug cannot be an alias Metabrowser wrote and is ignored.
    """

    store_ids = {f"{IDENTITY_PREFIX}{key}" for key in store_keys}
    naming: list[str] = []
    for entry in os.scandir(home / SOURCES):
        if not is_slug(entry.name):
            continue
        try:
            alias = read_record(
                home,
                source_record(entry.name, "store-alias.yml"),
                REPOSITORY_STORE_ALIAS_CONTRACT_ID,
            )
        except FileNotFoundError:
            continue
        except (RecordError, PrivateStorageError, OSError):
            naming.append(entry.name)
            continue
        if not isinstance(alias, RepositoryStoreAlias) or alias.store_id in store_ids:
            naming.append(entry.name)
    return tuple(sorted(naming))


def quarantine_entries(
    home: Path,
    *,
    source_slugs: Sequence[str],
    store_keys: Sequence[str],
    revalidate: Callable[[], bool],
    observer: MachineObserver | None = None,
) -> QuarantineOutcome:
    """Quarantine stores, and the aliases naming them, that still fail *revalidate*.

    Takes each store's exclusive maintenance lock without blocking and defers if any is
    busy. *revalidate* runs under the locks that follow and must not do network or
    long-running work.

    With *source_slugs*, the sources the stores were resolved through, it takes their
    alias locks and the store locks in order; their alias locks are held even when an
    alias entry is already gone, as the frozen machine requires. Every alias moves
    before any store, so a crash between the two leaves the aliases retained in
    quarantine and the stores ordinary unreferenced stores.

    Without *source_slugs*, for stores no alias was seen to name, it takes the store
    locks alone. That is safe because the exclusive maintenance lock excludes every
    lease and an alias naming a store is written only under that store's lease, so no
    alias can come to name a store while it is held; and an acquisition that begins
    after the move re-verifies the store under the store lock before publishing its
    alias. An alias published before the exclusive lock was taken is still possible, so
    the absence of one is verified under the store locks, and if one names a store the
    store locks are released and the alias-first path runs with those sources.

    When no store is present there is nothing to quarantine.
    """

    if not store_keys:
        raise ValueError("quarantine needs at least one repository store")
    machine = "quarantine"
    keys = sorted(set(store_keys))
    slugs = sorted(set(source_slugs))
    maintenance: list[CacheLock] = []
    try:
        try:
            for key in keys:
                maintenance.append(store_maintenance_lock(home, key))
        except LockBusyError:
            _emit(observer, machine, "exclusive_busy")
            return QuarantineOutcome("deferred")
        _emit(observer, machine, "try_exclusive")
        if not slugs:
            with ExitStack() as store_locks:
                locked = [
                    store_locks.enter_context(repository_store_lock(home, key)) for key in keys
                ]
                if not any(os.path.lexists(home / store_directory(key)) for key in keys):
                    _emit(observer, machine, "unreferenced_store_absent")
                    return QuarantineOutcome("nothing_to_quarantine")
                slugs = list(aliases_naming_stores(home, keys))
                if slugs:
                    _emit(observer, machine, "alias_now_names_store")
                elif revalidate():
                    _emit(observer, machine, "unreferenced_store_revalidated_ok")
                    return QuarantineOutcome("healthy")
                else:
                    entry, retained = _move_into_quarantine(
                        home,
                        [
                            (store_directory(key), lock)
                            for key, lock in zip(keys, locked, strict=True)
                        ],
                    )
                    _emit(observer, machine, "move_unreferenced_store_to_quarantine")
                    return QuarantineOutcome("quarantined", entry, retained)
        return _quarantine_with_aliases(home, slugs, keys, revalidate, observer)
    finally:
        for lock in reversed(maintenance):
            lock.release()


def _quarantine_with_aliases(
    home: Path,
    slugs: Sequence[str],
    keys: Sequence[str],
    revalidate: Callable[[], bool],
    observer: MachineObserver | None,
) -> QuarantineOutcome:
    machine = "quarantine"
    with ExitStack() as held:
        alias_locks = [held.enter_context(source_alias_lock(home, slug)) for slug in slugs]
        store_locks = [held.enter_context(repository_store_lock(home, key)) for key in keys]
        if not any(os.path.lexists(home / store_directory(key)) for key in keys):
            _emit(observer, machine, "store_absent")
            return QuarantineOutcome("nothing_to_quarantine")
        if revalidate():
            _emit(observer, machine, "revalidated_ok")
            return QuarantineOutcome("healthy")
        entry = f"quarantine-{secrets.token_hex(8)}"
        retained: list[str] = []
        for moves, event in (
            (
                [(source_directory(s), lock) for s, lock in zip(slugs, alias_locks, strict=True)],
                "move_alias_to_quarantine",
            ),
            (
                [(store_directory(k), lock) for k, lock in zip(keys, store_locks, strict=True)],
                "move_store_to_quarantine",
            ),
        ):
            moved = _move_into_quarantine(home, moves, entry=entry)[1]
            if moved:
                retained.extend(moved)
                _emit(observer, machine, event)
        return QuarantineOutcome("quarantined", entry, tuple(retained))


def _move_into_quarantine(
    home: Path, moves: Sequence[tuple[str, CacheLock]], *, entry: str | None = None
) -> tuple[str, tuple[str, ...]]:
    """Move each present path into one quarantine entry under its owning lock."""

    entry = f"quarantine-{secrets.token_hex(8)}" if entry is None else entry
    ensure_private_directory(home, quarantine_entry(entry))
    retained: list[str] = []
    for relative_path, lock in moves:
        if not os.path.lexists(home / relative_path):
            continue
        target = f"{quarantine_entry(entry)}/{relative_path.removeprefix('cache/')}"
        publish_entry(home, relative_path, target, owner=lock)
        retained.append(target)
    if retained:
        log.warning(
            "Quarantined %d cache entries that failed validation; retained at %s",
            len(retained),
            home / quarantine_entry(entry),
        )
    return entry, tuple(retained)


def purge_quarantined(home: Path, entry: str, *, observer: MachineObserver | None = None) -> bool:
    """Explicitly purge one quarantine entry: to trash under the home lock, then delete."""

    machine = "quarantine"
    with application_home_lock(home) as home_lock:
        relative_path = quarantine_entry(entry)
        os.lstat(home / relative_path)
        trash = _move_into_new_trash(home, "purge", relative_path, home_lock)
        _emit(observer, machine, "explicit_purge")
    try:
        deleted = _remove_tree(home / trash.relative_path)
        _emit(observer, machine, "delete_completed")
    finally:
        trash.lock.remove_lock_file()
    return deleted


__all__ = [
    "MachineEvent",
    "MachineObserver",
    "QuarantineOutcome",
    "StoreReclamation",
    "SweepReport",
    "TrashEntry",
    "begin_trash_entry",
    "delete_trash_entry",
    "move_to_trash",
    "purge_quarantined",
    "quarantine_entries",
    "reclaim_staging",
    "reclaim_store",
    "reclaim_trash",
    "reclaim_unreferenced_stores",
    "store_is_referenced",
    "sweep_staging_and_trash",
]
