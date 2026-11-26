"""Spike: confine a child process on Linux with Landlock and seccomp, then exec it.

The shape is a command prefix, as ``sandbox-exec -p PROFILE`` is on macOS: the host runs
``<host-python> -I -S confine_linux.py run POLICY_JSON -- ARGV...``. This program, still
unconfined, turns the policy into a Landlock ruleset and a seccomp filter, applies both to
itself, and replaces itself with ``ARGV``. Both survive ``execve`` and are inherited by
every process the child starts, and neither can be removed.

- **Landlock** (kernel 5.13 and later, no privilege needed) denies every file access the
  ruleset handles outside the named roots: reads, writes, creation, removal, and exec.
  From ABI 4 (kernel 6.7) it also denies TCP bind and connect, and from ABI 6 (kernel
  6.12) it scopes signals and abstract Unix sockets to the confined processes.
- **seccomp** denies ``socket(2)`` with ``EPERM``, which covers what Landlock does not:
  UDP, raw sockets, and connecting to a Unix socket by its path. ``socketpair(2)`` stays,
  since an asyncio event loop makes one for itself.

Standard library only. ``probe`` prints what this kernel offers and changes nothing.

Usage:
    confine_linux.py probe
    confine_linux.py run POLICY_JSON -- ARGV...

``POLICY_JSON`` is ``{"read": [paths], "write": [paths], "network": bool}``. A path that
does not exist is skipped, as a profile's ``subpath`` of a missing directory matches
nothing.
"""

from __future__ import annotations

import ctypes
import json
import os
import platform
import struct
import sys
from typing import Any

SYS_LANDLOCK_CREATE_RULESET = 444
SYS_LANDLOCK_ADD_RULE = 445
SYS_LANDLOCK_RESTRICT_SELF = 446
LANDLOCK_CREATE_RULESET_VERSION = 1
LANDLOCK_RULE_PATH_BENEATH = 1

FS_EXECUTE = 1 << 0
FS_WRITE_FILE = 1 << 1
FS_READ_FILE = 1 << 2
FS_READ_DIR = 1 << 3
# Bits 4 to 12: removing and making directories, files, devices, sockets, and links.
FS_CHANGE_TREE = sum(1 << bit for bit in range(4, 13))
FS_REFER = 1 << 13  # ABI 2
FS_TRUNCATE = 1 << 14  # ABI 3
FS_IOCTL_DEV = 1 << 15  # ABI 5
NET_BIND_TCP = 1 << 0  # ABI 4
NET_CONNECT_TCP = 1 << 1
SCOPE_ABSTRACT_UNIX_SOCKET = 1 << 0  # ABI 6
SCOPE_SIGNAL = 1 << 1

PR_SET_NO_NEW_PRIVS = 38
PR_SET_SECCOMP = 22
SECCOMP_MODE_FILTER = 2
SECCOMP_RET_ALLOW = 0x7FFF0000
SECCOMP_RET_ERRNO_EPERM = 0x00050000 | 1
SECCOMP_RET_KILL_PROCESS = 0x80000000
# The audit architecture and ``socket`` syscall number of each machine this spike knows.
ARCHITECTURES: dict[str, tuple[int, int]] = {
    "x86_64": (0xC000003E, 41),
    "aarch64": (0xC00000B7, 198),
}
X32_SYSCALL_BIT = 0x40000000

_libc = ctypes.CDLL(None, use_errno=True)


def _syscall(number: int, *arguments: Any) -> int:
    result: int = _libc.syscall(ctypes.c_long(number), *arguments)
    if result < 0:
        error = ctypes.get_errno()
        raise OSError(error, os.strerror(error))
    return result


def landlock_abi() -> int:
    """The Landlock ABI this kernel offers, or 0 when it has none or it is turned off."""
    try:
        return _syscall(
            SYS_LANDLOCK_CREATE_RULESET,
            None,
            ctypes.c_size_t(0),
            ctypes.c_uint32(LANDLOCK_CREATE_RULESET_VERSION),
        )
    except OSError:
        return 0


def _handled_fs(abi: int) -> int:
    handled = FS_EXECUTE | FS_WRITE_FILE | FS_READ_FILE | FS_READ_DIR | FS_CHANGE_TREE
    if abi >= 2:
        handled |= FS_REFER
    if abi >= 3:
        handled |= FS_TRUNCATE
    if abi >= 5:
        handled |= FS_IOCTL_DEV
    return handled


def _allow(ruleset: int, path: str, access: int) -> None:
    try:
        fd = os.open(path, os.O_PATH | os.O_CLOEXEC)
    except OSError:
        return
    try:
        if not os.path.isdir(path):
            # A rule on a file may name only the rights that apply to a file.
            access &= FS_EXECUTE | FS_WRITE_FILE | FS_READ_FILE | FS_TRUNCATE | FS_IOCTL_DEV
        rule = struct.pack("=Qi", access, fd)
        _syscall(
            SYS_LANDLOCK_ADD_RULE,
            ctypes.c_int(ruleset),
            ctypes.c_int(LANDLOCK_RULE_PATH_BENEATH),
            ctypes.c_char_p(rule),
            ctypes.c_uint32(0),
        )
    finally:
        os.close(fd)


def apply_landlock(read: list[str], write: list[str], *, network: bool) -> int:
    """Confine this process to *read* and *write*; returns the ABI used, 0 for none."""
    abi = landlock_abi()
    if abi == 0:
        return 0
    handled_fs = _handled_fs(abi)
    handled_net = 0 if network or abi < 4 else NET_BIND_TCP | NET_CONNECT_TCP
    scoped = SCOPE_ABSTRACT_UNIX_SOCKET | SCOPE_SIGNAL if abi >= 6 else 0
    # The attribute grew a field at ABI 4 and another at ABI 6; a kernel takes its own size.
    size = 24 if abi >= 6 else 16 if abi >= 4 else 8
    attribute = struct.pack("=QQQ", handled_fs, handled_net, scoped)[:size]
    ruleset = _syscall(
        SYS_LANDLOCK_CREATE_RULESET,
        ctypes.c_char_p(attribute),
        ctypes.c_size_t(size),
        ctypes.c_uint32(0),
    )
    reading = handled_fs & (FS_EXECUTE | FS_READ_FILE | FS_READ_DIR)
    for path in read:
        _allow(ruleset, path, reading)
    for path in write:
        _allow(ruleset, path, handled_fs & ~FS_EXECUTE)
    _syscall(SYS_LANDLOCK_RESTRICT_SELF, ctypes.c_int(ruleset), ctypes.c_uint32(0))
    os.close(ruleset)
    return abi


def _instruction(code: int, jump_true: int, jump_false: int, value: int) -> bytes:
    return struct.pack("=HBBI", code, jump_true, jump_false, value)


def apply_socket_filter() -> bool:
    """Make ``socket(2)`` fail with ``EPERM`` in this process and everything it starts."""
    known = ARCHITECTURES.get(platform.machine())
    if known is None:
        return False
    architecture, socket_number = known
    load, jump_equal, jump_at_least, answer = 0x20, 0x15, 0x35, 0x06
    program = b"".join(
        [
            _instruction(load, 0, 0, 4),  # the call's architecture
            _instruction(jump_equal, 1, 0, architecture),
            _instruction(answer, 0, 0, SECCOMP_RET_KILL_PROCESS),
            _instruction(load, 0, 0, 0),  # the call's number
            _instruction(jump_at_least, 0, 1, X32_SYSCALL_BIT),
            _instruction(answer, 0, 0, SECCOMP_RET_KILL_PROCESS),
            _instruction(jump_equal, 0, 1, socket_number),
            _instruction(answer, 0, 0, SECCOMP_RET_ERRNO_EPERM),
            _instruction(answer, 0, 0, SECCOMP_RET_ALLOW),
        ]
    )
    instructions = ctypes.create_string_buffer(program, len(program))
    # struct sock_fprog { unsigned short len; struct sock_filter *filter; }, natively aligned.
    filter_program = struct.pack("HP", len(program) // 8, ctypes.addressof(instructions))
    holder = ctypes.create_string_buffer(filter_program, len(filter_program))
    result: int = _libc.prctl(
        ctypes.c_int(PR_SET_SECCOMP),
        ctypes.c_ulong(SECCOMP_MODE_FILTER),
        ctypes.c_void_p(ctypes.addressof(holder)),
        ctypes.c_ulong(0),
        ctypes.c_ulong(0),
    )
    return result == 0


def confine(read: list[str], write: list[str], *, network: bool) -> dict[str, Any]:
    """Apply the policy to this process; what was applied, for the caller to judge."""
    no_new_privileges: int = _libc.prctl(
        ctypes.c_int(PR_SET_NO_NEW_PRIVS),
        ctypes.c_ulong(1),
        ctypes.c_ulong(0),
        ctypes.c_ulong(0),
        ctypes.c_ulong(0),
    )
    if no_new_privileges != 0:
        return {"landlock_abi": 0, "socket_filter": False}
    abi = apply_landlock(read, write, network=network)
    filtered = False if network else apply_socket_filter()
    return {"landlock_abi": abi, "socket_filter": filtered}


def main() -> None:
    if sys.argv[1:2] == ["probe"]:
        report = {"landlock_abi": landlock_abi(), "machine": platform.machine()}
        print(json.dumps({**report, "socket_filter_known": platform.machine() in ARCHITECTURES}))
        return
    if sys.argv[1:2] != ["run"] or "--" not in sys.argv:
        raise SystemExit(__doc__)
    policy: dict[str, Any] = json.loads(sys.argv[2])
    command = sys.argv[sys.argv.index("--") + 1 :]
    read = [str(path) for path in policy.get("read", [])]
    write = [str(path) for path in policy.get("write", [])]
    applied = confine(read, write, network=bool(policy.get("network", False)))
    if applied["landlock_abi"] == 0 or not (applied["socket_filter"] or policy.get("network")):
        # Fail closed: a caller that asked for confinement never gets an unconfined child.
        raise SystemExit(f"confine_linux: confinement is not available here: {applied}")
    os.execv(command[0], command)


if __name__ == "__main__":
    main()
