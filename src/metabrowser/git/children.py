"""This process's child processes, as the kernel lists them.

A stop that must not leave a process group behind cannot rely on what the event loop has
had time to record: a group's ID reaches the registry in :mod:`metabrowser.git.process`
only when its spawn returns, several loop turns after the fork, and a stuck loop never
gets there. The kernel knows the child from the fork on, and a child that has not been
reaped keeps its ID, which no other process can be given meanwhile. So a stop asks the
kernel which children this process has, and what each one runs.

Listing is available on macOS, through ``libproc``, and on Linux, through ``/proc``.
Elsewhere :func:`child_pids` returns ``None`` and a stop has only the registry.
"""

from __future__ import annotations

import ctypes
import os
import sys
from typing import Final

# More children than a server has: a stop that finds this many lists no more, and kills
# what it found.
_MAX_CHILDREN: Final[int] = 4096
# ``PROC_PIDPATHINFO_MAXSIZE``: four times ``MAXPATHLEN``.
_PATH_BYTES: Final[int] = 4096
# A ``/proc`` file this reads holds a few numbers; the cap only bounds a surprise.
_PROC_FILE_BYTES: Final[int] = 64 * 1024
_DELETED_SUFFIX: Final[str] = " (deleted)"

# ``libproc``, loaded by :func:`prepare_child_listing` before a stop may need it, so a stop
# in a signal handler does not load a library.
_LIBPROC: dict[str, object] = {}


def prepare_child_listing() -> None:
    """Load what listing children needs, ahead of a stop that may run in a signal handler."""

    if sys.platform != "darwin" or "lib" in _LIBPROC:
        return
    try:
        lib = ctypes.CDLL("/usr/lib/libproc.dylib", use_errno=True)
    except OSError:
        return
    lib.proc_listchildpids.argtypes = (ctypes.c_int, ctypes.c_void_p, ctypes.c_int)
    lib.proc_listchildpids.restype = ctypes.c_int
    lib.proc_pidpath.argtypes = (ctypes.c_int, ctypes.c_void_p, ctypes.c_uint32)
    lib.proc_pidpath.restype = ctypes.c_int
    _LIBPROC["lib"] = lib


def child_pids() -> list[int] | None:
    """The IDs of this process's children not yet reaped, or ``None`` if unknowable here.

    A child that has exited but not been reaped is listed too.
    """

    if sys.platform == "darwin":
        return _darwin_child_pids()
    if sys.platform.startswith("linux"):
        return _linux_child_pids()
    return None


def executable(pid: int) -> str | None:
    """The path of the program child *pid* runs, or ``None`` when it cannot be read.

    ``None`` for a child that has exited, and for one that is gone.
    """

    if sys.platform == "darwin":
        return _darwin_executable(pid)
    if sys.platform.startswith("linux"):
        try:
            path = os.readlink(f"/proc/{pid}/exe")
        except OSError:
            return None
        return path.removesuffix(_DELETED_SUFFIX)
    return None


def _darwin_child_pids() -> list[int] | None:
    if sys.platform != "darwin":
        return None
    lib = _LIBPROC.get("lib")
    if not isinstance(lib, ctypes.CDLL):
        return None
    buffer = (ctypes.c_int * _MAX_CHILDREN)()
    count = int(lib.proc_listchildpids(os.getpid(), buffer, ctypes.sizeof(buffer)))
    if count < 0:
        return None
    return [int(pid) for pid in buffer[: min(count, _MAX_CHILDREN)]]


def _darwin_executable(pid: int) -> str | None:
    if sys.platform != "darwin":
        return None
    lib = _LIBPROC.get("lib")
    if not isinstance(lib, ctypes.CDLL):
        return None
    buffer = ctypes.create_string_buffer(_PATH_BYTES)
    length = int(lib.proc_pidpath(pid, buffer, _PATH_BYTES))
    if length <= 0:
        return None
    return os.fsdecode(buffer.raw[:length])


def _linux_child_pids() -> list[int] | None:
    me = os.getpid()
    children = _linux_task_children(me)
    if children is not None:
        return children
    # A kernel built without ``CONFIG_PROC_CHILDREN``: every process's parent, instead.
    found: list[int] = []
    try:
        entries = os.listdir("/proc")
    except OSError:
        return None
    for entry in entries:
        if not entry.isdigit():
            continue
        stat = _read_proc_file(f"/proc/{entry}/stat")
        # ``pid (comm) state ppid ...``; a name may hold spaces and parentheses.
        fields = stat.rpartition(b")")[2].split() if stat else []
        if len(fields) > 1 and fields[1] == str(me).encode():
            found.append(int(entry))
    return found


def _linux_task_children(me: int) -> list[int] | None:
    # Each thread's children are listed under it; a thread gone since the listing has none.
    if not os.path.exists(f"/proc/{me}/task/{me}/children"):
        return None
    try:
        tasks = os.listdir(f"/proc/{me}/task")
    except OSError:
        return None
    children: list[int] = []
    for task in tasks:
        children.extend(
            int(pid) for pid in _read_proc_file(f"/proc/{me}/task/{task}/children").split()
        )
    return children


def _read_proc_file(path: str) -> bytes:
    try:
        fd = os.open(path, os.O_RDONLY)
    except OSError:
        return b""
    try:
        return os.read(fd, _PROC_FILE_BYTES)
    except OSError:
        return b""
    finally:
        os.close(fd)


__all__ = ["child_pids", "executable", "prepare_child_listing"]
