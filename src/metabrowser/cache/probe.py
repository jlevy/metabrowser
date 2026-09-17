"""The runtime probe that decides whether an application home can hold the cache.

The lock and publication rules were measured on one macOS APFS home, and CI runs only
Linux. A network file system can emulate ``flock`` with record locks, which vanish when
a process closes any descriptor for the file, and a file system can ignore a no-replace
rename flag. So before the cache uses a home, this probe checks on that home that:

- a second process cannot take an exclusive or shared lock this process holds
  exclusively, can share a shared lock but not take it exclusively, and gets the lock
  once it is released;
- closing an unrelated descriptor for the lock file does not release the lock;
- an exclusive attempt through a separate ``open()`` in this process contends with a
  shared lock this process holds, instead of coexisting with it; and
- the platform no-replace rename refuses an existing directory and file, and
  publication under a held lock refuses an existing target while moving a staged entry
  to an absent one.

A home that fails any check is refused as unverifiable. The probe costs one short-lived
interpreter started with ``-I -S`` plus a few file operations, and its result is kept
for the life of the process, keyed by the device and inode of ``cache/locks``; a home
that moves to another file system is a different directory and is probed again.
"""

from __future__ import annotations

import contextlib
import os
import secrets
import select
import shutil
import subprocess
import sys
import threading
from dataclasses import dataclass
from pathlib import Path
from typing import IO, Final

from metabrowser.cache.atomic import publish_entry
from metabrowser.cache.locks import CacheLock, staging_entry_lock
from metabrowser.home import (
    PrivateStorageError,
    PrivateStorageLocation,
    PrivateStorageViolation,
    ensure_private_directory,
    open_private_file,
    rename_without_replacing,
    write_private_file_atomic,
)

try:
    import fcntl
except ImportError:  # Windows: ensure_private_directory refuses first as unverifiable.
    fcntl = None

_REPLY_TIMEOUT_SECONDS: Final = 10.0
_CHILD_SCRIPT: Final = """
import fcntl, os, sys
fd = os.open(sys.argv[1], os.O_RDONLY | os.O_NOFOLLOW | os.O_CLOEXEC)
modes = {"ex": fcntl.LOCK_EX, "sh": fcntl.LOCK_SH}
def attempt(name):
    try:
        fcntl.flock(fd, modes[name] | fcntl.LOCK_NB)
    except BlockingIOError:
        return "busy"
    fcntl.flock(fd, fcntl.LOCK_UN)
    return "acquired"
for line in sys.stdin:
    sys.stdout.write(" ".join(attempt(name) for name in line.split()) + "\\n")
    sys.stdout.flush()
"""

_REMEDY: Final = "Set METABROWSER_HOME to a directory on a local file system"


@dataclass(frozen=True, slots=True)
class ProbeReport:
    """What the probe established about one application home."""

    no_replace_rename: bool


class _ProbeFailed(Exception):
    """One probe check did not behave as the cache requires."""


_RESULTS: dict[tuple[int, int], ProbeReport] = {}
_RESULTS_MUTEX = threading.Lock()


def probe_application_home(home: Path, *, force: bool = False) -> ProbeReport:
    """Verify *home*'s locks and publication once per process, or refuse the home.

    The ``f01`` skeleton must exist. Raises :class:`PrivateStorageError` with violation
    ``unverifiable`` when a check fails.
    """

    locks = ensure_private_directory(home, "cache/locks")
    status = os.stat(locks)
    key = (status.st_dev, status.st_ino)
    with _RESULTS_MUTEX:
        if not force and key in _RESULTS:
            return _RESULTS[key]
        try:
            report = _probe(home)
        except _ProbeFailed as failure:
            raise PrivateStorageError(
                PrivateStorageViolation.UNVERIFIABLE,
                PrivateStorageLocation.HOME,
                home,
                detail=f"{failure}. {_REMEDY}",
            ) from failure
        _RESULTS[key] = report
        return report


def _probe(home: Path) -> ProbeReport:
    entry = f"probe-{secrets.token_hex(8)}"
    staging = f"cache/staging/{entry}"
    with staging_entry_lock(home, entry) as owner:
        try:
            _probe_locks(home, f"cache/locks/staging/{entry}-flock.lock")
            return _probe_publication(home, staging, owner)
        finally:
            shutil.rmtree(home / staging, ignore_errors=True)
            owner.remove_lock_file()


def _probe_locks(home: Path, relative_path: str) -> None:
    if fcntl is None or not sys.executable:
        raise _ProbeFailed("a second process could not be started to verify its file locks")
    path = home / relative_path
    exclusive = open_private_file(home, relative_path, os.O_RDWR | os.O_CREAT)
    shared = open_private_file(home, relative_path, os.O_RDWR)
    try:
        try:
            fcntl.flock(exclusive, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError as error:
            raise _ProbeFailed("its file system refused a file lock") from error
        unrelated = open_private_file(home, relative_path, os.O_RDONLY)
        os.close(unrelated)
        with _Child(path) as child:
            if child.ask("ex sh") != "busy busy":
                raise _ProbeFailed(
                    "a second process took a lock this process held, or the lock did not "
                    "survive closing an unrelated descriptor for its file"
                )
            fcntl.flock(exclusive, fcntl.LOCK_UN)
            fcntl.flock(shared, fcntl.LOCK_SH | fcntl.LOCK_NB)
            _probe_separate_open(home, relative_path)
            if child.ask("sh ex") != "acquired busy":
                raise _ProbeFailed("its file locks did not keep shared and exclusive holders apart")
            fcntl.flock(shared, fcntl.LOCK_UN)
            if child.ask("ex") != "acquired":
                raise _ProbeFailed("a released file lock stayed held")
    finally:
        os.close(exclusive)
        os.close(shared)
        with contextlib.suppress(OSError):
            os.unlink(path)


def _probe_separate_open(home: Path, relative_path: str) -> None:
    """An exclusive attempt through its own ``open()`` must contend with a held lease.

    The caller holds a shared lock on the file through another descriptor. Were the new
    attempt to succeed, one process's lease and maintenance lock could coexist, as they
    do through a ``dup()`` or under record locks.
    """

    assert fcntl is not None
    other = open_private_file(home, relative_path, os.O_RDWR)
    try:
        try:
            fcntl.flock(other, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            return
        raise _ProbeFailed(
            "an exclusive lock through a separate descriptor in this process did not "
            "contend with a shared lock this process held"
        )
    finally:
        os.close(other)


def _probe_publication(home: Path, staging: str, owner: CacheLock) -> ProbeReport:
    ensure_private_directory(home, f"{staging}/source")
    ensure_private_directory(home, f"{staging}/occupied")
    write_private_file_atomic(home, f"{staging}/occupied-file", b"")
    source = home / staging / "source"
    for target in ("occupied", "occupied-file"):
        try:
            rename_without_replacing(source, home / staging / target)
        except FileExistsError:
            pass
        else:
            raise _ProbeFailed("a no-replace rename replaced an existing entry")
        if not source.is_dir():
            raise _ProbeFailed("a refused no-replace rename moved its source")
    if (
        not (home / staging / "occupied").is_dir()
        or not (home / staging / "occupied-file").is_file()
    ):
        raise _ProbeFailed("a refused no-replace rename changed its target")
    atomic = publish_entry(home, f"{staging}/source", f"{staging}/published", owner=owner)
    if source.exists() or not (home / staging / "published").is_dir():
        raise _ProbeFailed("publication did not move a staged entry to an absent target")
    try:
        publish_entry(home, f"{staging}/published", f"{staging}/occupied", owner=owner)
    except FileExistsError:
        pass
    else:
        raise _ProbeFailed("publication replaced an existing entry")
    return ProbeReport(no_replace_rename=atomic)


class _Child:
    """A short-lived interpreter that tries locks on request and reports the outcome."""

    def __init__(self, path: Path) -> None:
        self._path = path
        self._process: subprocess.Popen[bytes] | None = None

    def __enter__(self) -> _Child:
        try:
            self._process = subprocess.Popen(
                [sys.executable, "-I", "-S", "-c", _CHILD_SCRIPT, os.fspath(self._path)],
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.DEVNULL,
                close_fds=True,
            )
        except OSError as error:
            raise _ProbeFailed(
                "a second process could not be started to verify its file locks"
            ) from error
        return self

    def ask(self, request: str) -> str:
        process = self._process
        assert process is not None
        stdin: IO[bytes] | None = process.stdin
        stdout: IO[bytes] | None = process.stdout
        assert stdin is not None and stdout is not None
        try:
            stdin.write(request.encode() + b"\n")
            stdin.flush()
        except OSError as error:
            raise _ProbeFailed("the process verifying its file locks exited early") from error
        ready, _, _ = select.select([stdout], [], [], _REPLY_TIMEOUT_SECONDS)
        if not ready:
            raise _ProbeFailed("the process verifying its file locks did not answer")
        return stdout.readline().decode(errors="replace").strip()

    def __exit__(self, *_exc: object) -> None:
        process = self._process
        if process is None:
            return
        with contextlib.suppress(OSError):
            if process.stdin is not None:
                process.stdin.close()
        try:
            process.wait(timeout=_REPLY_TIMEOUT_SECONDS)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait()
        if process.stdout is not None:
            process.stdout.close()


__all__ = ["ProbeReport", "probe_application_home"]
