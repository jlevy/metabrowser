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
import tempfile
import threading
import time
from collections.abc import Callable, Generator
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
# The private folders' prefix under the system's temporary directory.
PRIVATE_PREFIX: Final = "metabrowser-sqlite-"
_OWNER_LOCK: Final = "owner.lock"

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


class _Worker:
    """One reader process and the subject it serves."""

    def __init__(self, subject: str, modules: WorkerModules) -> None:
        self.subject = subject
        self.modules = modules
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
        while b"\n" not in self._buffer:
            remaining = hard_deadline - time.monotonic()
            if remaining <= 0:
                raise _TimedOut
            ready, _, _ = select.select([fd], [], [], remaining)
            if not ready:
                raise _TimedOut
            chunk = os.read(fd, 65536)
            if not chunk:
                raise _Stopped
            self._buffer += chunk
        line, _, rest = bytes(self._buffer).partition(b"\n")
        self._buffer = bytearray(rest)
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

    A live pool holds an advisory lock on its folder's lock file, so a lock this process
    can take marks a folder nobody owns. Only this user's folders are touched.
    """
    try:
        candidates = list(root.glob(f"{PRIVATE_PREFIX}*"))
    except OSError:
        return
    for folder in candidates:
        try:
            info = folder.lstat()
            if not stat.S_ISDIR(info.st_mode) or info.st_uid != os.getuid():
                continue
            fd = os.open(folder / _OWNER_LOCK, os.O_RDONLY | os.O_NOFOLLOW)
        except OSError:
            continue
        try:
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError:
            os.close(fd)
            continue
        shutil.rmtree(folder, ignore_errors=True)
        os.close(fd)


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
        self._requests = itertools.count()
        self._closed = False
        self.started = 0

    # ── Private folders ──

    def folder(self) -> Path:
        """This pool's private folder, created on first use after sweeping leftovers."""
        with self._cond:
            if self._folder is None:
                root = self._root or Path(tempfile.gettempdir())
                _sweep(root)
                folder = Path(tempfile.mkdtemp(prefix=PRIVATE_PREFIX, dir=root))
                fd = os.open(folder / _OWNER_LOCK, os.O_RDWR | os.O_CREAT | os.O_EXCL, 0o600)
                fcntl.flock(fd, fcntl.LOCK_EX)
                self._folder, self._lock_fd = folder, fd
            return self._folder

    @contextlib.contextmanager
    def scratch(self) -> Generator[Path]:
        """A fresh private folder for one request, removed when it ends."""
        folder = self.folder() / f"request-{next(self._requests)}"
        folder.mkdir(mode=0o700)
        try:
            yield folder
        finally:
            shutil.rmtree(folder, ignore_errors=True)

    def blob(self, oid: str, load: Callable[[], bytes]) -> Path:
        """The private file holding Git blob *oid*, written once from *load*.

        *oid* names the content, so a file already written for it is reused; it is
        written to a temporary name and renamed, and left read-only.
        """
        if not oid.isalnum():
            raise ValueError("a blob is named by its object id")
        blobs = self.folder() / "blobs"
        blobs.mkdir(mode=0o700, exist_ok=True)
        target = blobs / f"{oid}.db"
        if target.exists():
            return target
        data = load()
        temporary = blobs / f".{oid}.{os.getpid()}.{threading.get_ident()}.tmp"
        with open(temporary, "xb") as writer:
            writer.write(data)
        temporary.chmod(0o400)
        os.replace(temporary, target)
        return target

    # ── Requests ──

    def call(self, op: str, args: dict[str, Any], *, deadline: float, subject: str) -> Any:
        """Run *op* in a worker serving *subject*; its result, or the state it failed with.

        *deadline* is a ``time.monotonic()`` instant: the worker interrupts its read there
        and the pool kills it at :data:`READER_KILL_GRACE_SECONDS` later. Raises
        :class:`~metabrowser.sqlite_access.SqliteAccessError`.
        """
        worker = self._acquire(deadline, subject)
        seconds = max(0.0, deadline - time.monotonic())
        try:
            response = worker.ask(
                {"op": op, "args": args, "seconds": seconds},
                deadline + READER_KILL_GRACE_SECONDS,
            )
        except _TimedOut:
            worker.kill()
            self._discard(worker)
            raise SqliteAccessError(
                "busy", "The read did not finish in time, and its reader was stopped."
            ) from None
        except _Stopped:
            worker.kill()
            self._discard(worker)
            raise SqliteAccessError(
                "reader_stopped", "The process reading this database stopped."
            ) from None
        self._release(worker)
        if response.get("ok") is True:
            return response.get("result")
        raise SqliteAccessError(
            sqlite_access.error_state(response.get("state")),
            str(response.get("error") or "The read failed."),
        )

    def _acquire(self, deadline: float, subject: str) -> _Worker:
        retired: list[_Worker] = []
        modules = worker_modules()
        try:
            with self._cond:
                if self._closed:
                    raise SqliteAccessError("busy", "The reader processes have stopped.")
                if self._waiting >= self._queue_max:
                    raise SqliteAccessError("busy", "Too many reads are waiting.")
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
                            raise SqliteAccessError("busy", "Every reader stayed busy.")
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
                "reader_stopped", f"A reader process could not start: {exc}"
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
        for worker in idle:
            worker.stop()
        if folder is not None:
            shutil.rmtree(folder, ignore_errors=True)
        if fd is not None:
            os.close(fd)


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
