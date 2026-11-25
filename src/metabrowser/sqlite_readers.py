"""Reader processes: where every connection to a database Metabrowser does not own runs.

A POSIX lock belongs to a process and a file, so a handle the server opens and closes on
a database or its ``-shm`` (the magic check, a header read, inventory sniffing, hashing)
would drop every lock a connection in the same process holds there. Connections to
other applications' databases therefore never run in the server: they run here, in a
small pool of reader processes, each a fresh interpreter that loads only
:mod:`metabrowser.sqlite_access` and the standard library, serves one request at a
time, and opens a database's files only while it has no connection
(`explorations/sqlite-guest-reads/README.md#process` records what this rests on).

- **Start.** A worker is a fresh interpreter (``subprocess`` runs ``python -I``, the
  exec that ``multiprocessing``'s ``spawn`` also uses; never ``fork``, which would copy
  a threaded server and its open handles), with its working directory at ``/`` and no
  inherited descriptors. It is started on first use, so a one-shot ``metab --api`` or
  ``--show`` starts one, and goldens run the same path as the server.
- **Work.** One request at a time over the worker's pipes, one JSON line each way. A
  request's deadline counts from when the route accepted it; the worker's watchdog
  interrupts its connection at the deadline, and the parent kills the worker at the
  later hard deadline (:data:`READER_KILL_GRACE_SECONDS`). A full queue or a kill answers
  ``busy``; a worker that exits or crashes is replaced, and its request answers
  ``reader_stopped`` with no automatic retry.
- **Subjects.** A worker serves the one subject (served folder or pin) it was started
  for and is retired when another subject needs its place, so under the untrusted
  profile no worker reads two subjects' files.
- **Private folders.** The parent creates and removes every private folder: one per
  process under the system's temporary directory, held by an advisory lock, with a
  folder per request for private copies and a folder of Git blobs written once. Folders
  left by a process that died are swept when the next pool starts. These hold only
  copies a later request recreates, so a transient location is the right one.
- **Lifecycle.** A worker exits when its stdin closes, which is how the pool stops it
  and how one whose parent died exits.
"""

from __future__ import annotations

import atexit
import contextlib
import fcntl
import itertools
import json
import os
import select
import shutil
import stat
import subprocess
import sys
import sysconfig
import tempfile
import threading
import time
from collections import OrderedDict
from collections.abc import Callable, Generator
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Final

from metabrowser import sqlite_access
from metabrowser.sqlite_access import SqliteAccessError

# Workers alive at once. Each request is short (a page round trip measured 154 µs warm
# in the exploration's Process record, an Info round trip 1.3 ms here, and a worker's
# start to its first answer 45 to 51 ms, by `devtools/bench_sqlite_access.py`) and one table view asks one request at a time, so
# two serve a page and a hover card together while bounding the memory of crafted
# files to two processes.
READER_POOL_SIZE: Final = 2
# Requests that may wait for a worker; one more answers `busy` at once, keeping the last
# good rows on screen rather than queueing behind a slow database.
READER_QUEUE_MAX: Final = 8
# The parent kills a worker this long past a request's deadline, when the worker's own
# watchdog interrupt did not end the read (a stuck file system call, a crafted value).
READER_KILL_GRACE_SECONDS: Final = 1.0
# How long a request may run, from when the route accepted it to the watchdog's
# interrupt: the server's slow-request threshold, as the table routes' budget is
# (`TABLE_REQUEST_DEADLINE_SECONDS`).
SQLITE_REQUEST_DEADLINE_SECONDS: Final = 2.0
# The address space a worker may map, where the platform enforces `RLIMIT_AS` (Linux;
# macOS does not). After 50 Info reads a worker had mapped 112 MiB, peaking at 176 MiB
# with its watchdog thread's stack, and held 18 MiB resident
# (`uv run python -m devtools.bench_sqlite_access`, 2026-11-20, 4 CPUs at a load of 4);
# a preview through `blobopen` stays near its baseline even for a 200 MiB value (the
# exploration's Values record). One GiB leaves a page's values, SQLite's cache, and
# Python's heap several times that, and stops a crafted file that would take the
# machine's memory.
READER_ADDRESS_SPACE_BYTES: Final = 1024 * 1024 * 1024
# The largest Git blob read as a database: written once to a private file, then read
# with `immutable=1`. The same bound as a private copy (`COPY_MAX_BYTES`), whose cost
# was measured; a blob is written once rather than per request.
BLOB_MAX_BYTES: Final = sqlite_access.COPY_MAX_BYTES
# The Git blobs one process keeps written, by their total size; past it the least
# recently used are removed. A removed blob comes back on its next request for the cost
# of reading it from Git and writing it again: a median 138 ms at `BLOB_MAX_BYTES`
# (`uv run python -m devtools.bench_sqlite_access`, 2026-11-20, 4 CPUs at a load of 6).
# Four blobs at that size let a reader move between a few revisions' databases without
# paying it, and bound what the folder holds, memory where the temporary directory is a
# tmpfs, to that much.
BLOBS_MAX_BYTES: Final = 4 * BLOB_MAX_BYTES
# A blob handed out this recently is never removed, nor one a request is reading: the
# path goes from `blob` to the request that opens it within one request's deadline.
BLOB_HOLD_SECONDS: Final = SQLITE_REQUEST_DEADLINE_SECONDS
# The private folders' prefix under the system's temporary directory.
PRIVATE_PREFIX: Final = "metabrowser-sqlite-"
# A folder is made under this name, which the sweep's pattern does not match, and
# renamed to its `PRIVATE_PREFIX` name only once its lock is held, so a sweep never sees
# a live pool's folder unlocked.
_STAGING_PREFIX: Final = "." + PRIVATE_PREFIX
# A staging folder older than this was left by a process that died while making it: a
# live one is renamed within microseconds.
STAGING_STALE_SECONDS: Final = 60.0
_OWNER_LOCK: Final = "owner.lock"
_MAKE_ATTEMPTS: Final = 8

# The worker's whole program: load `sqlite_access.py` as `metabrowser.sqlite_access` and
# run its loop, which loads the registered worker modules first (`serve`).
_BOOTSTRAP: Final = (
    "import importlib.util, sys, types\n"
    "package = types.ModuleType('metabrowser')\n"
    "package.__path__ = []\n"
    "sys.modules['metabrowser'] = package\n"
    "spec = importlib.util.spec_from_file_location('metabrowser.sqlite_access', sys.argv[1])\n"
    "module = importlib.util.module_from_spec(spec)\n"
    "sys.modules[spec.name] = module\n"
    "package.sqlite_access = module\n"
    "spec.loader.exec_module(module)\n"
    "module.serve()\n"
)

# The most modules that may be registered to run in workers: one per source plugin that
# reads SQLite, with room to spare. A registration past it is refused.
MAX_WORKER_MODULES: Final = 8

type WorkerModules = tuple[tuple[str, str], ...]

_worker_modules: dict[str, str] = {}
_worker_modules_lock = threading.Lock()


def register_worker_module(name: str, path: str | Path) -> None:
    """Run the module at *path*, under the import name *name*, in every reader process.

    The module must import only the standard library and ``metabrowser.sqlite_access``
    (``from metabrowser import sqlite_access``), which resolves to the worker's own copy;
    any other ``metabrowser`` import fails in the worker, whose ``metabrowser`` package
    holds only that module and the registered ones. It adds the requests it answers to
    ``sqlite_access.OPS`` when it is loaded. Workers started with another set of modules
    are retired and replaced as they come free. Registering the same name and path again
    changes nothing.
    """
    if not all(part.isidentifier() for part in name.split(".")):
        raise ValueError(f"worker module name {name!r} is not a dotted import name")
    resolved = Path(path).resolve()
    if resolved.suffix != ".py" or not resolved.is_file():
        raise ValueError(f"worker module {name!r} is not a Python file: {path}")
    with _worker_modules_lock:
        if name not in _worker_modules and len(_worker_modules) >= MAX_WORKER_MODULES:
            raise ValueError(f"more than {MAX_WORKER_MODULES} worker modules")
        _worker_modules[name] = str(resolved)


def worker_modules() -> WorkerModules:
    """The registered worker modules, in registration order."""
    with _worker_modules_lock:
        return tuple(_worker_modules.items())


class _Stopped(Exception):
    """The worker exited or answered nothing a reader can use."""


class _TimedOut(Exception):
    """The worker did not answer by the hard deadline."""


class _TooLarge(Exception):
    """The worker sent more than :data:`~metabrowser.sqlite_access.ANSWER_MAX_BYTES`
    without ending its answer."""


class _Worker:
    """One reader process and the subject it serves."""

    def __init__(self, subject: str, modules: WorkerModules) -> None:
        self.subject = subject
        self.modules = modules
        worker_env: dict[str, str] | None = None
        if (
            sys.platform == "linux"
            and sys.maxsize > 2**32
            and sysconfig.get_config_var("Py_GIL_DISABLED")
        ):
            # On 64-bit free-threaded CPython, mimalloc can reserve a 1 GiB arena
            # before the worker applies its address-space limit. Smaller arenas leave
            # room in that limit for the watchdog thread and SQLite allocations.
            worker_env = dict(os.environ, MIMALLOC_ARENA_RESERVE="64MiB")
        self.process = subprocess.Popen(
            [
                sys.executable,
                "-I",
                "-c",
                _BOOTSTRAP,
                sqlite_access.__file__,
                str(READER_ADDRESS_SPACE_BYTES),
                json.dumps(modules),
            ],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            cwd="/",
            env=worker_env,
            close_fds=True,
        )
        self._buffer = bytearray()

    @property
    def pid(self) -> int:
        return self.process.pid

    def alive(self) -> bool:
        return self.process.poll() is None

    def ask(self, request: dict[str, Any], hard_deadline: float) -> dict[str, Any]:
        stdin = self.process.stdin
        stdout = self.process.stdout
        if stdin is None or stdout is None:  # pragma: no cover - always piped
            raise _Stopped
        try:
            stdin.write(json.dumps(request).encode() + b"\n")
            stdin.flush()
        except (BrokenPipeError, OSError) as exc:
            raise _Stopped from exc
        fd = stdout.fileno()
        # One answer and its newline at most; each chunk is searched once, so reading an
        # answer is linear in its length.
        limit = sqlite_access.ANSWER_MAX_BYTES + 1
        end = self._buffer.find(b"\n")
        while end < 0:
            if len(self._buffer) >= limit:
                raise _TooLarge
            remaining = hard_deadline - time.monotonic()
            if remaining <= 0:
                raise _TimedOut
            ready, _, _ = select.select([fd], [], [], remaining)
            if not ready:
                raise _TimedOut
            chunk = os.read(fd, min(65536, limit - len(self._buffer)))
            if not chunk:
                raise _Stopped
            found = chunk.find(b"\n")
            if found >= 0:
                end = len(self._buffer) + found
            self._buffer += chunk
        line = bytes(self._buffer[:end])
        del self._buffer[: end + 1]
        try:
            response = json.loads(line)
        except ValueError as exc:
            raise _Stopped from exc
        if not isinstance(response, dict):
            raise _Stopped
        return response

    def stop(self) -> None:
        """Close the worker's stdin, which ends its loop, and reap it."""
        with contextlib.suppress(OSError):
            if self.process.stdin is not None:
                self.process.stdin.close()
        try:
            self.process.wait(timeout=READER_KILL_GRACE_SECONDS)
        except subprocess.TimeoutExpired:
            self.kill()
        with contextlib.suppress(OSError):
            if self.process.stdout is not None:
                self.process.stdout.close()

    def kill(self) -> None:
        with contextlib.suppress(OSError):
            self.process.kill()
        with contextlib.suppress(subprocess.TimeoutExpired):
            self.process.wait(timeout=READER_KILL_GRACE_SECONDS)


def _sweep(root: Path) -> None:
    """Remove private folders a process that has died left behind.

    A live pool holds an advisory lock on its folder's lock file from before the folder
    has its swept name, so a lock this process can take marks a folder nobody owns. A
    staging folder is swept only once it is :data:`STAGING_STALE_SECONDS` old. Only this
    user's folders are touched.
    """
    try:
        candidates = [(folder, False) for folder in root.glob(f"{PRIVATE_PREFIX}*")]
        candidates += [(folder, True) for folder in root.glob(f"{_STAGING_PREFIX}*")]
    except OSError:
        return
    for folder, staging in candidates:
        try:
            info = folder.lstat()
            if not stat.S_ISDIR(info.st_mode) or info.st_uid != os.getuid():
                continue
            if staging and time.time() - info.st_mtime < STAGING_STALE_SECONDS:
                continue
            fd = os.open(folder / _OWNER_LOCK, os.O_RDONLY | os.O_NOFOLLOW)
        except FileNotFoundError:
            if staging:
                # Died before it made its lock file.
                shutil.rmtree(folder, ignore_errors=True)
            continue
        except OSError:
            continue
        try:
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError:
            os.close(fd)
            continue
        shutil.rmtree(folder, ignore_errors=True)
        os.close(fd)


def _make_folder(root: Path) -> tuple[Path, int]:
    """A new private folder under *root* and the descriptor holding its lock.

    It is made and locked under a staging name, then renamed to the name the sweep looks
    at, so no sweep finds it unlocked.
    """
    for _ in range(_MAKE_ATTEMPTS):
        staging = Path(tempfile.mkdtemp(prefix=_STAGING_PREFIX, dir=root))
        fd = -1
        try:
            fd = os.open(
                staging / _OWNER_LOCK, os.O_RDWR | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600
            )
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
            final = root / staging.name.removeprefix(".")
            if not os.path.lexists(final):
                os.rename(staging, final)
                return final, fd
        except BaseException:
            if fd >= 0:
                os.close(fd)
            shutil.rmtree(staging, ignore_errors=True)
            raise
        os.close(fd)
        shutil.rmtree(staging, ignore_errors=True)
    raise OSError("no free name for a private folder")


def _held(folder: Path, lock: tuple[int, int]) -> bool:
    """Whether *folder* still holds the lock file whose identity is *lock*."""
    try:
        info = os.stat(folder / _OWNER_LOCK, follow_symlinks=False)
    except OSError:
        return False
    return (info.st_dev, info.st_ino) == lock


# The reader's sentence when the process reading a database stopped or could not start.
_TRY_AGAIN_MESSAGE: Final = "This database could not be read. Try again."


def _pool_closed() -> SqliteAccessError:
    """The refusal of a read once the pool has closed, as the server stops."""
    return SqliteAccessError(
        "busy", sqlite_access.BUSY_MESSAGE, detail="The reader processes have stopped."
    )


def _folder_error(exc: OSError) -> SqliteAccessError:
    return SqliteAccessError(
        "unreadable",
        sqlite_access.UNREADABLE_MESSAGE,
        detail="The private folder databases are read through could not be made: "
        f"{exc.strerror or exc}",
    )


@dataclass(slots=True)
class _BlobFile:
    """One written Git blob: its size, when it was last handed out, and the requests
    reading it now."""

    size: int
    handed_out: float
    reading: int = 0


class ReaderPool:
    """A bounded pool of reader processes and the private folders they read copies from."""

    def __init__(
        self,
        *,
        size: int = READER_POOL_SIZE,
        queue_max: int = READER_QUEUE_MAX,
        temporary_root: Path | None = None,
    ) -> None:
        self._size = size
        self._queue_max = queue_max
        self._root = temporary_root
        self._cond = threading.Condition()
        self._idle: list[_Worker] = []
        self._count = 0
        self._waiting = 0
        self._folder: Path | None = None
        self._lock_fd: int | None = None
        self._lock_key: tuple[int, int] = (0, 0)
        # Written blobs by path, least recently used first.
        self._blobs: OrderedDict[str, _BlobFile] = OrderedDict()
        self._requests = itertools.count()
        self._closed = False
        self.started = 0

    # ── Private folders ──

    def folder(self) -> Path:
        """This pool's private folder: made on first use after sweeping leftovers, and
        made again when something removed it (the system's cleaning of its temporary
        directory, which a long-running server can outlive).

        Raises :class:`~metabrowser.sqlite_access.SqliteAccessError` (``unreadable``)
        when it cannot be made, and ``busy`` once the pool is closed.
        """
        with self._cond:
            if self._closed:
                raise _pool_closed()
            if self._folder is not None and _held(self._folder, self._lock_key):
                return self._folder
            lost, fd = self._folder, self._lock_fd
            self._folder = self._lock_fd = None
            self._blobs.clear()
            if fd is not None:
                os.close(fd)
            if lost is not None and not os.path.lexists(lost / _OWNER_LOCK):
                # Whatever is left of it is this pool's own and no longer locked.
                shutil.rmtree(lost, ignore_errors=True)
            root = self._root or Path(tempfile.gettempdir())
            _sweep(root)
            try:
                folder, fd = _make_folder(root)
                held = os.fstat(fd)
            except OSError as exc:
                raise _folder_error(exc) from exc
            self._folder, self._lock_fd = folder, fd
            self._lock_key = (held.st_dev, held.st_ino)
            return folder

    def _in_folder[T](self, make: Callable[[Path], T]) -> T:
        """*make* run on the private folder, and once more on a new folder when the
        first was removed under it."""
        for attempt in range(2):
            base = self.folder()
            try:
                return make(base)
            except FileNotFoundError as exc:
                if attempt:
                    raise _folder_error(exc) from exc
            except OSError as exc:
                raise _folder_error(exc) from exc
        raise AssertionError("unreachable")

    @contextlib.contextmanager
    def scratch(self) -> Generator[Path]:
        """A fresh private folder for one request, removed when it ends."""

        def make(base: Path) -> Path:
            folder = base / f"request-{next(self._requests)}"
            folder.mkdir(mode=0o700)
            return folder

        folder = self._in_folder(make)
        try:
            yield folder
        finally:
            shutil.rmtree(folder, ignore_errors=True)

    def written_blob(self, oid: str) -> Path | None:
        """The private file already holding Git blob *oid*, or None.

        Ask before reading the blob, so a blob written once is not read from Git again.
        """
        _require_oid(oid)
        with self._cond:
            if self._folder is None or not _held(self._folder, self._lock_key):
                return None
            target = self._folder / "blobs" / f"{oid}.db"
            entry = self._blobs.get(str(target))
            if entry is None:
                return None
            if not target.is_file():
                del self._blobs[str(target)]
                return None
            entry.handed_out = time.monotonic()
            self._blobs.move_to_end(str(target))
            return target

    def blob(self, oid: str, load: Callable[[], bytes]) -> Path:
        """The private file holding Git blob *oid*, written once from *load*.

        *oid* names the content, so a file already written for it is reused, and *load*
        runs only when none is (:meth:`written_blob` asks without a *load*). It is written
        to a temporary name and renamed, and left read-only. Written blobs are kept to
        :data:`BLOBS_MAX_BYTES` in all, the least recently used removed first, never one
        handed out within :data:`BLOB_HOLD_SECONDS` or one a request is reading.
        """
        written = self.written_blob(oid)
        if written is not None:
            return written
        data = load()

        def write(base: Path) -> Path:
            blobs = base / "blobs"
            blobs.mkdir(mode=0o700, exist_ok=True)
            target = blobs / f"{oid}.db"
            temporary = blobs / f".{oid}.{os.getpid()}.{threading.get_ident()}.tmp"
            try:
                with open(temporary, "xb") as writer:
                    writer.write(data)
                temporary.chmod(0o400)
                os.replace(temporary, target)
            except BaseException:
                with contextlib.suppress(OSError):
                    temporary.unlink()
                raise
            return target

        target = self._in_folder(write)
        with self._cond:
            self._blobs[str(target)] = _BlobFile(len(data), time.monotonic())
            self._blobs.move_to_end(str(target))
            self._evict_blobs()
        return target

    def _evict_blobs(self) -> None:
        """Remove the least recently used blobs past :data:`BLOBS_MAX_BYTES`; called
        with the pool's lock held."""
        total = sum(entry.size for entry in self._blobs.values())
        now = time.monotonic()
        for path, entry in list(self._blobs.items()):
            if total <= BLOBS_MAX_BYTES:
                break
            if entry.reading or now - entry.handed_out < BLOB_HOLD_SECONDS:
                continue
            with contextlib.suppress(OSError):
                os.unlink(path)
            del self._blobs[path]
            total -= entry.size

    def _blob_in_use(self, path: object, change: int) -> str | None:
        """Count a request reading the written blob at *path* (a request's ``path``
        argument), or stop counting it; the path when it is a written blob."""
        if not isinstance(path, str):
            return None
        with self._cond:
            entry = self._blobs.get(path)
            if entry is None:
                return None
            entry.reading += change
            entry.handed_out = time.monotonic()
            return path

    # ── Requests ──

    def call(self, op: str, args: dict[str, Any], *, deadline: float, subject: str) -> Any:
        """Run *op* in a worker serving *subject*; its result, or the state it failed with.

        *deadline* is a ``time.monotonic()`` instant: the worker interrupts its read there
        and the pool kills it at :data:`READER_KILL_GRACE_SECONDS` later. Raises
        :class:`~metabrowser.sqlite_access.SqliteAccessError`.
        """
        worker = self._acquire(deadline, subject)
        seconds = max(0.0, deadline - time.monotonic())
        blob = self._blob_in_use(args.get("path"), +1)
        try:
            response = worker.ask(
                {"op": op, "args": args, "seconds": seconds},
                deadline + READER_KILL_GRACE_SECONDS,
            )
        except BaseException as exc:
            # Whatever ended the exchange, the worker may be mid-answer: it is never
            # reused, and its place in the pool is given back.
            worker.kill()
            self._discard(worker)
            if isinstance(exc, _TimedOut):
                raise SqliteAccessError(
                    "busy",
                    sqlite_access.TOO_SLOW_MESSAGE,
                    detail="The read did not finish in time, and its reader was stopped.",
                ) from None
            if isinstance(exc, _TooLarge):
                raise SqliteAccessError(
                    "too_large",
                    sqlite_access.TOO_LARGE_MESSAGE,
                    detail=f"The reader's answer passed {sqlite_access.ANSWER_MAX_BYTES:,} "
                    "bytes, and its reader was stopped.",
                ) from None
            if isinstance(exc, _Stopped):
                raise SqliteAccessError(
                    "reader_stopped",
                    _TRY_AGAIN_MESSAGE,
                    detail="The process reading this database stopped.",
                ) from None
            raise
        finally:
            self._blob_in_use(blob, -1)
        self._release(worker)
        if response.get("ok") is True:
            return response.get("result")
        raise SqliteAccessError(
            sqlite_access.error_state(response.get("state")),
            str(response.get("error") or sqlite_access.UNREADABLE_MESSAGE),
            detail=str(response.get("detail") or ""),
        )

    def _acquire(self, deadline: float, subject: str) -> _Worker:
        retired: list[_Worker] = []
        modules = worker_modules()
        try:
            with self._cond:
                if self._closed:
                    raise _pool_closed()
                if self._waiting >= self._queue_max:
                    raise SqliteAccessError(
                        "busy", sqlite_access.BUSY_MESSAGE, detail="Too many reads are waiting."
                    )
                self._waiting += 1
                try:
                    while True:
                        for worker in list(self._idle):
                            if not worker.alive():
                                self._idle.remove(worker)
                                self._count -= 1
                            elif worker.modules != modules:
                                # Started with another set of modules: replaced.
                                self._idle.remove(worker)
                                self._count -= 1
                                retired.append(worker)
                            elif worker.subject == subject:
                                self._idle.remove(worker)
                                return worker
                        if self._count < self._size:
                            self._count += 1
                            break
                        if self._idle:
                            # Another subject's idle worker gives up its place.
                            retired.append(self._idle.pop(0))
                            self._count -= 1
                            continue
                        remaining = deadline - time.monotonic()
                        if remaining <= 0:
                            raise SqliteAccessError(
                                "busy",
                                sqlite_access.BUSY_MESSAGE,
                                detail="Every reader stayed busy.",
                            )
                        self._cond.wait(remaining)
                finally:
                    self._waiting -= 1
        finally:
            for worker in retired:
                worker.stop()
        try:
            worker = _Worker(subject, modules)
        except OSError as exc:
            self._discard(None)
            raise SqliteAccessError(
                "reader_stopped",
                _TRY_AGAIN_MESSAGE,
                detail=f"A reader process could not start: {exc}",
            ) from exc
        self.started += 1
        return worker

    def _release(self, worker: _Worker) -> None:
        with self._cond:
            if self._closed:
                stop = True
            else:
                self._idle.append(worker)
                stop = False
            self._cond.notify()
        if stop:
            worker.stop()

    def _discard(self, _worker: _Worker | None) -> None:
        with self._cond:
            self._count -= 1
            self._cond.notify()

    def workers(self) -> list[int]:
        """The process ids of idle workers, for tests."""
        with self._cond:
            return [worker.pid for worker in self._idle]

    def close(self) -> None:
        """Stop every idle worker and remove the private folder."""
        with self._cond:
            self._closed = True
            idle, self._idle = self._idle, []
            self._count -= len(idle)
            folder, fd = self._folder, self._lock_fd
            self._folder = self._lock_fd = None
            self._blobs.clear()
        for worker in idle:
            worker.stop()
        if folder is not None:
            shutil.rmtree(folder, ignore_errors=True)
        if fd is not None:
            os.close(fd)


def _require_oid(oid: str) -> None:
    if not oid.isalnum():
        raise ValueError("a blob is named by its object id")


_pool: ReaderPool | None = None
_pool_lock = threading.Lock()


def reader_pool() -> ReaderPool:
    """The process's reader pool, started on first use and closed at exit."""
    global _pool
    with _pool_lock:
        if _pool is None:
            _pool = ReaderPool()
            atexit.register(_pool.close)
        return _pool


def request_deadline() -> float:
    """A request's deadline, counted from now."""
    return time.monotonic() + SQLITE_REQUEST_DEADLINE_SECONDS
