"""The size of a change as Git pushes it, and as a patch: a commit's, or a pull request's.

A change is what one commit has that another has not: a commit against its first parent,
or a pull request's head against its merge base. Two numbers describe its size:

- **Pushed bytes**, what the change costs in Git: the thin pack ``git push`` sends for it,
  every object *head* reaches that *base* does not, zlib-compressed and stored as deltas
  against one another and against the objects *base* already has. This is the number a
  reader means by how big a change "really" is: a one-line edit to a large file costs a
  few bytes, not the file.
- **Diff bytes**, the change written out uncompressed: ``git diff --binary`` of the two
  trees.

Neither of the other numbers Git keeps answers the question. The sum of the new objects'
sizes counts every touched file whole, and every rewritten directory, so an 11.6 KB patch
reads as 1.13 MB; and an object's size on disk depends on how this repository's packs
happen to be laid out, not on the change, so one commit read 91 KB here and costs 5.7 KB to
push. Measured 2026-11-19 on this repository with Git 2.43 (thin pack, then patch): one
commit 3.6 KB of an 11.6 KB patch, another 56.9 KB of 194 KB, and an eight-commit pull
request 1.81 MB of a 6.15 MB patch.

**A function of the two commit IDs** and of the zlib Git is built with, which is this
machine's, as the cache is. A commit ID names its whole history, so the objects
a pack holds are fixed by the pair; what could still move the size is how Git compresses
and searches for deltas, and every option that does is pinned (:data:`PACK_ARGS`,
:data:`DIFF_ARGS`), the reader's configuration included. ``--no-reuse-object`` keeps the
store's own packs out of it: without it Git copies the deltas and compressed data this
repository already holds, and the size moved by 0.4% between two clones of one pull
request. So a measured size is kept and never measured again: in memory, and, for a
repository store, in a bank beside the store (:class:`_StoreBank`). A folder's own
repository keeps sizes in memory only, since browsing a folder never touches the cache
(docs/project/architecture/arch-repository-cache.md). :data:`MEASURE` names the pinned
options, so changing one changes every kept size's key.

**What it costs.** Measured 2026-11-20 on this repository (Git 2.43, one thread): 20 to
41 ms for a commit, and 374 ms for the eight-commit pull request whose patch is 6.15 MB
(200 ms reusing the store's deltas). The pack is streamed and counted, never held. A
measurement that takes longer than :data:`MEASURE_TIMEOUT_S` is ``too_costly``, and that
answer is kept in memory too, so a change too large to measure costs that once.

**What it cannot measure** is answered as ``unknown`` with a reason, never as a number
that is wrong: a commit at a shallow boundary, whose parent is not here
(``parent_unavailable``); a walk from *base* to *head* that crosses the boundary, which
would count a whole tree as new (``history_unavailable``); and an object the repository
lacks (``objects_unavailable``).
"""

from __future__ import annotations

import asyncio
import contextlib
import hashlib
import logging
from collections import OrderedDict
from dataclasses import dataclass
from pathlib import Path
from threading import Lock
from typing import Final
from weakref import WeakKeyDictionary

from metabrowser.git.process import (
    GIT_NO_DRIVER_ARGS,
    GitCommandError,
    GitLocation,
    GitTimeoutError,
    ObjectFormat,
    RepositoryStoreTarget,
    empty_tree_oid,
    run_git_at,
    spawn_git_at,
    terminate_git_process,
)
from metabrowser.git.shallow import recorded_parents
from metabrowser.git.wire import GitChangeSize, GitChangeSizeReason, is_full_revision
from metabrowser.loading_cache import LoadingCache
from metabrowser.settings import GIT_SUBPROCESS_TIMEOUT_S

log = logging.getLogger(__name__)

# The pack ``git push`` sends, with every setting that shapes its bytes pinned. Git's own
# defaults, written out so neither the reader's configuration nor the repository's moves
# them: zlib's default level, a delta window of 10 and chain of 50, files up to 512 MiB
# considered for deltas, no window memory limit, and push's sparse walk. Bitmaps are off
# because they change which objects the walk names. One thread, because the delta search
# divides its work among threads and the division moves which bases each object finds.
PACK_ARGS: Final[tuple[str, ...]] = (
    "-c",
    "pack.useBitmaps=false",
    "-c",
    "pack.useSparse=true",
    "-c",
    "core.compression=-1",
    "-c",
    "pack.compression=-1",
    "-c",
    "core.bigFileThreshold=512m",
    "-c",
    "pack.windowMemory=0",
    "pack-objects",
    "--revs",
    "--stdout",
    "--thin",
    "--delta-base-offset",
    "--no-reuse-object",
    "--window=10",
    "--depth=50",
    "--threads=1",
    "-q",
)
# The patch, with every option that shapes its text pinned: Git's defaults written out, and
# no driver, so the text is Git's own for every reader.
DIFF_ARGS: Final[tuple[str, ...]] = (
    "-c",
    "core.quotePath=true",
    "-c",
    "diff.suppressBlankEmpty=false",
    "diff",
    *GIT_NO_DRIVER_ARGS,
    "--binary",
    "--no-color",
    "--find-renames",
    "-l1000",
    "--diff-algorithm=myers",
    "--indent-heuristic",
    "-U3",
    "--inter-hunk-context=0",
    "--no-relative",
    "--src-prefix=a/",
    "--dst-prefix=b/",
    "--submodule=short",
)
# What every kept size answers for: a digest of the pinned options, so changing one makes
# every kept size a miss. Raise the version when what is measured changes in a way the
# arguments do not show.
MEASURE: Final = hashlib.sha256(repr((2, PACK_ARGS, DIFF_ARGS)).encode()).hexdigest()[:32]
# A request waits on a measurement, so it has a request's deadline.
MEASURE_TIMEOUT_S: Final[float] = GIT_SUBPROCESS_TIMEOUT_S
# How much is read from Git's stdout at a time while counting it.
_CHUNK_BYTES: Final = 256 * 1024
# How much of a failing run's stderr is kept to tell a missing object from another failure.
_STDERR_MAX_BYTES: Final = 64 * 1024
# Sizes kept in memory, each a few hundred bytes: a long history walked by hover.
MAX_KEPT_SIZES: Final = 8192

_MISSING_OBJECT_MARKERS: Final = (
    "bad object",
    "not a valid object name",
    "unknown revision",
    "missing blob",
    "missing tree",
    "missing commit",
    "unable to read",
    "could not read",
    "bad revision",
)


class _Unknown(Exception):
    """A measurement that answered ``unknown``, raised so the load that found it keeps nothing."""

    def __init__(self, reason: GitChangeSizeReason) -> None:
        super().__init__(reason)
        self.reason: GitChangeSizeReason = reason


def measured(base: str | None, head: str, commits: int, pushed: int, diff: int) -> GitChangeSize:
    return GitChangeSize(
        base=base,
        head=head,
        state="measured",
        reason=None,
        commits=commits,
        pushed_bytes=pushed,
        diff_bytes=diff,
    )


def unknown(base: str | None, head: str, reason: GitChangeSizeReason) -> GitChangeSize:
    return GitChangeSize(
        base=base,
        head=head,
        state="unknown",
        reason=reason,
        commits=None,
        pushed_bytes=None,
        diff_bytes=None,
    )


async def _count_output(
    args: tuple[str, ...], location: GitLocation, stdin: bytes | None, deadline: float
) -> int:
    """Run Git and count the bytes it writes to stdout, holding none of them.

    Raises :class:`GitTimeoutError` past *deadline* (a loop time), and
    :class:`GitCommandError` when Git fails.
    """

    proc = await spawn_git_at(args, location, pipe_stdin=stdin is not None)
    returncode = 0
    stderr = b""
    try:
        async with asyncio.timeout_at(deadline):
            stderr_task = asyncio.ensure_future(_read_stderr(proc.stderr))
            try:
                if stdin is not None and proc.stdin is not None:
                    proc.stdin.write(stdin)
                    with contextlib.suppress(BrokenPipeError, ConnectionResetError):
                        await proc.stdin.drain()
                    proc.stdin.close()
                total = 0
                assert proc.stdout is not None
                while chunk := await proc.stdout.read(_CHUNK_BYTES):
                    total += len(chunk)
                returncode = await proc.wait()
                stderr = await stderr_task
            finally:
                if not stderr_task.done():
                    stderr_task.cancel()
    except TimeoutError:
        raise GitTimeoutError("measuring a change's size timed out and was terminated") from None
    finally:
        await terminate_git_process(proc)
    if returncode != 0:
        raise GitCommandError(args, returncode, stderr.decode("utf-8", errors="replace"))
    return total


async def _read_stderr(stream: asyncio.StreamReader | None) -> bytes:
    """Drain *stream*, keeping its first :data:`_STDERR_MAX_BYTES`, so Git never blocks."""

    if stream is None:
        return b""
    kept = bytearray()
    while chunk := await stream.read(_CHUNK_BYTES):
        if len(kept) < _STDERR_MAX_BYTES:
            kept += chunk[: _STDERR_MAX_BYTES - len(kept)]
    return bytes(kept)


async def _object_format(location: GitLocation) -> ObjectFormat:
    target = location.target
    if isinstance(target, RepositoryStoreTarget):
        return target.object_format
    raw = await run_git_at(["rev-parse", "--show-object-format"], location)
    return "sha256" if raw.strip() == b"sha256" else "sha1"


async def _walk(location: GitLocation, base: str | None, head: str) -> int | None:
    """How many commits *head* reaches that *base* does not, or ``None`` when the walk
    meets a commit at a shallow boundary.

    Git grafts such a commit into a root, so a pack of the walk would hold its whole tree
    as new. The walk names each commit with the parents it can see; a commit with none
    is a true root or is at the boundary, and its object says which
    (:func:`~metabrowser.git.shallow.recorded_parents`).
    """

    walk = ["rev-list", "--parents", head] + ([f"^{base}"] if base is not None else [])
    raw = await run_git_at(walk, location)
    lines = raw.decode("ascii", errors="replace").splitlines()
    for line in lines:
        words = line.split()
        if len(words) == 1 and await recorded_parents(location, words[0]):
            return None
    return len(lines)


async def measure_change(location: GitLocation, base: str | None, head: str) -> GitChangeSize:
    """Measure what *head* has that *base* has not, at *location*. Nothing is kept here.

    *base* ``None`` measures a root commit against nothing. Both are full commit IDs.
    """

    if not is_full_revision(head) or (base is not None and not is_full_revision(base)):
        raise ValueError("a change's size is measured between full commit IDs")
    loop = asyncio.get_running_loop()
    deadline = loop.time() + MEASURE_TIMEOUT_S
    try:
        commits = await _walk(location, base, head)
        if commits is None:
            return unknown(base, head, "history_unavailable")
        revisions = f"{head}\n" + (f"^{base}\n" if base is not None else "")
        pushed = await _count_output(PACK_ARGS, location, revisions.encode("ascii"), deadline)
        old = base if base is not None else empty_tree_oid(await _object_format(location))
        diff = await _count_output((*DIFF_ARGS, old, head, "--"), location, None, deadline)
    except GitTimeoutError:
        return unknown(base, head, "too_costly")
    except GitCommandError as exc:
        summary = exc.stderr_summary.lower()
        if any(marker in summary for marker in _MISSING_OBJECT_MARKERS):
            return unknown(base, head, "objects_unavailable")
        raise
    return measured(base, head, commits, pushed, diff)


# ---------------------------------------------------------------------------------------
# Kept sizes
# ---------------------------------------------------------------------------------------


class _KeptSizes:
    """Measured sizes this process holds, by key, the least recently used out first.

    Keyed without the location: a measured size is a function of the commit IDs alone,
    whichever repository holds them. ``too_costly`` is kept too, under the location, so a
    change too large to measure is not measured on every hover.
    """

    def __init__(self, limit: int = MAX_KEPT_SIZES) -> None:
        self._limit = limit
        self._sizes: OrderedDict[tuple[str, ...], GitChangeSize] = OrderedDict()
        self._lock = Lock()

    def get(self, key: tuple[str, ...]) -> GitChangeSize | None:
        with self._lock:
            size = self._sizes.get(key)
            if size is not None:
                self._sizes.move_to_end(key)
            return size

    def put(self, key: tuple[str, ...], size: GitChangeSize) -> None:
        with self._lock:
            self._sizes[key] = size
            self._sizes.move_to_end(key)
            while len(self._sizes) > self._limit:
                self._sizes.popitem(last=False)

    def clear(self) -> None:
        with self._lock:
            self._sizes.clear()


KEPT_SIZES: Final = _KeptSizes()
_FLIGHTS: WeakKeyDictionary[
    asyncio.AbstractEventLoop, LoadingCache[tuple[str, ...], GitChangeSize]
] = WeakKeyDictionary()
_FLIGHTS_LOCK = Lock()


def _flights() -> LoadingCache[tuple[str, ...], GitChangeSize]:
    loop = asyncio.get_running_loop()
    with _FLIGHTS_LOCK:
        flights = _FLIGHTS.get(loop)
        if flights is None:
            # Nothing is kept here; it only joins concurrent loads of one key.
            flights = _FLIGHTS[loop] = LoadingCache(max_values=0)
        return flights


def _commit_key(head: str) -> tuple[str, ...]:
    return ("commit", head)


def _range_key(base: str | None, head: str) -> tuple[str, ...]:
    return ("range", base or "", head)


async def change_size(location: GitLocation, base: str, head: str) -> GitChangeSize:
    """The size of what *head* has that *base* has not, measured once and then kept.

    For a pull request: *base* is its merge base. A failure Git reports that is not one
    of the ``unknown`` reasons is raised as a :class:`GitError`.
    """

    key = _range_key(base, head)
    kept = KEPT_SIZES.get(key) or KEPT_SIZES.get((location.identity, *key))
    if kept is not None:
        return kept

    async def load() -> GitChangeSize:
        bank = _StoreBank.for_location(location)
        if bank is not None:
            banked = await asyncio.to_thread(bank.read, key)
            if banked is not None:
                return banked
        size = await measure_change(location, base, head)
        await _keep(location, key, size, bank)
        return size

    try:
        return await _flights().get((location.identity, *key), load)
    except _Unknown as answer:
        return unknown(base, head, answer.reason)


async def commit_size(location: GitLocation, revision: str) -> GitChangeSize | None:
    """The size of commit *revision* against its first parent, measured once and kept.

    ``None`` when the repository has no such commit. A root commit is measured against
    nothing, and a merge against its first parent, as the commit's own view shows it
    (:mod:`metabrowser.git.detail`). Kept by the commit alone: its parents are part of it.
    """

    key = _commit_key(revision)
    kept = KEPT_SIZES.get(key) or KEPT_SIZES.get((location.identity, *key))
    if kept is not None:
        return kept

    async def load() -> GitChangeSize:
        bank = _StoreBank.for_location(location)
        if bank is not None:
            banked = await asyncio.to_thread(bank.read, key)
            if banked is not None:
                return banked
        parents = await _visible_parents(location, revision)
        if parents is None:
            raise _NotFound
        if not parents and await recorded_parents(location, revision):
            # At a shallow boundary: Git would answer as for a root. Not kept: a fetch
            # that deepens the history can measure it.
            raise _Unknown("parent_unavailable")
        size = await measure_change(location, parents[0] if parents else None, revision)
        await _keep(location, key, size, bank)
        return size

    try:
        return await _flights().get((location.identity, *key), load)
    except _NotFound:
        return None
    except _Unknown as answer:
        return unknown(None, revision, answer.reason)


def kept_change_size(location: GitLocation, base: str, head: str) -> GitChangeSize | None:
    """The size kept for *base* to *head*, in memory or beside the store, or ``None``.

    Runs no Git, so a route whose answer is the cache alone can say it. Blocking: it can
    read one bank file. A size kept from memory is not copied back from the bank.
    """

    key = _range_key(base, head)
    kept = KEPT_SIZES.get(key) or KEPT_SIZES.get((location.identity, *key))
    if kept is not None:
        return kept
    bank = _StoreBank.for_location(location)
    if bank is None:
        return None
    banked = bank.read(key)
    if banked is not None:
        KEPT_SIZES.put(key, banked)
    return banked


# Merge bases found certain, by the pair asked for: two commits' merge base never changes.
_MERGE_BASES: OrderedDict[tuple[str, str], str] = OrderedDict()
_MERGE_BASES_LOCK = Lock()


async def pull_change_size(location: GitLocation, left: str, right: str) -> GitChangeSize:
    """The size of a pull request: what *right*, its head, has that the merge base of
    *left* and *right* has not, as its Files changed compares them.

    *location* is a repository store's (:class:`RepositoryStoreTarget`). A merge base on a
    shallow store is believed only when it is certain
    (:func:`~metabrowser.git.shallow.merge_base_answer`); otherwise the size is
    ``history_unavailable``.
    """

    from metabrowser.git.shallow import merge_base_answer

    target = location.target
    if not isinstance(target, RepositoryStoreTarget):
        raise TypeError("a pull request's size is measured in a repository store")
    with _MERGE_BASES_LOCK:
        base = _MERGE_BASES.get((left, right))
    if base is None:
        answer = await merge_base_answer(target, left, right)
        if not answer.certain or answer.merge_base is None:
            return unknown(None, right, "history_unavailable")
        base = answer.merge_base
        with _MERGE_BASES_LOCK:
            _MERGE_BASES[(left, right)] = base
            while len(_MERGE_BASES) > MAX_KEPT_SIZES:
                _MERGE_BASES.popitem(last=False)
    return await change_size(location, base, right)


class _NotFound(Exception):
    """The repository has no such commit."""


async def _visible_parents(location: GitLocation, revision: str) -> list[str] | None:
    """The parents Git sees for *revision*, or ``None`` when it is no commit here."""

    try:
        raw = await run_git_at(
            ["rev-list", "--parents", "--no-walk", f"{revision}^{{commit}}", "--"], location
        )
    except GitCommandError as exc:
        summary = exc.stderr_summary.lower()
        if any(marker in summary for marker in _MISSING_OBJECT_MARKERS):
            return None
        raise
    words = raw.decode("ascii", errors="replace").split()
    if not words or words[0] != revision:
        return None
    return [word for word in words[1:] if is_full_revision(word)]


async def _keep(
    location: GitLocation, key: tuple[str, ...], size: GitChangeSize, bank: _StoreBank | None
) -> None:
    """Keep a measured size everywhere, and ``too_costly`` in memory under *location*.

    Any other unknown answer is raised, so the load keeps nothing and the next asks again.
    """

    if size["state"] == "measured":
        KEPT_SIZES.put(key, size)
        if bank is not None:
            await asyncio.to_thread(bank.write, key, size)
        return
    reason = size["reason"]
    assert reason is not None
    if reason == "too_costly":
        KEPT_SIZES.put((location.identity, *key), size)
    raise _Unknown(reason)


# ---------------------------------------------------------------------------------------
# The bank beside a repository store
# ---------------------------------------------------------------------------------------

# The bank's files: one for each of 256 prefixes of the head commit's ID, so no directory
# grows past 256 entries and a read opens one small file.
BANK_DIRECTORY: Final = "change-sizes"
# Sizes one file keeps, the oldest out first past it, so a store keeps at most 65,536.
# Measured 2026-11-20: a full file of SHA-256 entries with 13-digit counts, the largest
# one can be, is 66.4 KB (test_bank_file_stays_under_its_read_bound); SHA-1 entries and
# real counts make one about half that. The read bound is about twice the largest.
MAX_BANK_FILE_ENTRIES: Final = 256
MAX_BANK_FILE_BYTES: Final = 128 * 1024


@dataclass(frozen=True, slots=True)
class _StoreBank:
    """Measured sizes kept beside one repository store, in ``change-sizes/``.

    Disposable, as the pull manifests beside a store are: a file that cannot be read,
    was written for other options, or does not validate is a miss, and two writers that
    race can lose one another's newest size, which is measured again when it is next
    asked for. Nothing here is ever the only copy of anything.
    """

    home: Path
    store_key: str

    @classmethod
    def for_location(cls, location: GitLocation) -> _StoreBank | None:
        """The bank of the repository store *location* reads, or ``None`` for any other
        repository, such as a checkout's own Git directory.

        A store is ``<home>/repos/<key>/repository.git``, the layout
        :mod:`metabrowser.cache.paths` spells. Anything else is not the cache's to write
        beside. Nothing is imported from the cache for a folder's own repository.
        """

        target = location.target
        if not isinstance(target, RepositoryStoreTarget):
            return None
        from metabrowser.cache.identity import is_store_key
        from metabrowser.cache.paths import REPOSITORY_GIT, REPOSITORY_STORES

        git_dir = target.git_dir
        store = git_dir.parent
        if (
            git_dir.name != REPOSITORY_GIT
            or store.parent.name != REPOSITORY_STORES
            or not is_store_key(store.name)
        ):
            return None
        return cls(home=store.parent.parent, store_key=store.name)

    def _file(self, head: str) -> str:
        from metabrowser.cache.paths import store_directory

        return f"{store_directory(self.store_key)}/{BANK_DIRECTORY}/{head[:2]}.json"

    def _load(self, head: str) -> dict[str, list[object]] | None:
        import json

        from metabrowser.cache.atomic import RecordError, read_bytes_bounded
        from metabrowser.home import PrivateStorageError

        try:
            data = read_bytes_bounded(
                self.home, self._file(head), max_bytes=MAX_BANK_FILE_BYTES, shared="refuse"
            )
            record = json.loads(data)
        except FileNotFoundError:
            return {}
        except (OSError, RecordError, PrivateStorageError, ValueError):
            return None
        if (
            not isinstance(record, dict)
            or record.get("measure") != MEASURE
            or not isinstance(record.get("sizes"), dict)
        ):
            return None
        return record["sizes"]

    def read(self, key: tuple[str, ...]) -> GitChangeSize | None:
        """The size kept for *key*, or ``None``. Blocking and bounded."""

        head = key[-1]
        sizes = self._load(head)
        entry = None if sizes is None else sizes.get("\0".join(key))
        if not isinstance(entry, list) or len(entry) != 4:
            return None
        base: object = entry[0]
        counts = [_count(value) for value in entry[1:]]
        if base is not None and not (isinstance(base, str) and is_full_revision(base)):
            return None
        commits, pushed, diff = counts
        if commits is None or pushed is None or diff is None:
            return None
        if key[0] == "range" and (base or "") != key[1]:
            return None
        return measured(base, head, commits, pushed, diff)

    def write(self, key: tuple[str, ...], size: GitChangeSize) -> None:
        """Add *size* under *key*. Blocking; a failure is logged and dropped."""

        import json

        from metabrowser.cache.paths import store_directory
        from metabrowser.home import (
            PrivateStorageError,
            ensure_private_directory,
            private_directory_is_writable,
            write_private_file_atomic,
        )

        head = key[-1]
        try:
            if not private_directory_is_writable(self.home, store_directory(self.store_key)):
                return
            sizes = self._load(head) or {}
            sizes.pop("\0".join(key), None)
            sizes["\0".join(key)] = [
                size["base"],
                size["commits"],
                size["pushed_bytes"],
                size["diff_bytes"],
            ]
            while len(sizes) > MAX_BANK_FILE_ENTRIES:
                del sizes[next(iter(sizes))]
            data = json.dumps({"measure": MEASURE, "sizes": sizes}, separators=(",", ":")).encode()
            if len(data) > MAX_BANK_FILE_BYTES:
                return
            ensure_private_directory(
                self.home, f"{store_directory(self.store_key)}/{BANK_DIRECTORY}"
            )
            write_private_file_atomic(self.home, self._file(head), data)
        except (OSError, PrivateStorageError):
            # Disposable: a read-only cache still answers with the measured size.
            log.debug("could not keep a change's size beside its store")


def _count(value: object) -> int | None:
    """*value* as a count read back from JSON, or ``None`` when it is not one."""

    return value if isinstance(value, int) and not isinstance(value, bool) and value >= 0 else None


def clear_kept_sizes() -> None:
    """Forget every size and merge base this process holds in memory; for tests."""

    KEPT_SIZES.clear()
    with _MERGE_BASES_LOCK:
        _MERGE_BASES.clear()


__all__ = [
    "BANK_DIRECTORY",
    "DIFF_ARGS",
    "KEPT_SIZES",
    "MAX_BANK_FILE_BYTES",
    "MAX_BANK_FILE_ENTRIES",
    "MEASURE",
    "MEASURE_TIMEOUT_S",
    "PACK_ARGS",
    "change_size",
    "clear_kept_sizes",
    "commit_size",
    "kept_change_size",
    "measure_change",
    "measured",
    "pull_change_size",
    "unknown",
]
