"""Spike: confine a child process on Linux with Landlock and seccomp, then exec it.

The shape is a command prefix, as ``sandbox-exec -p PROFILE`` is on macOS: the host runs
``<host-python> -I -S confine_linux.py run POLICY_JSON -- ARGV...``. This program, still
unconfined, turns the policy into a Landlock ruleset and a seccomp filter, applies both to
itself, and replaces itself with ``ARGV``. Both survive ``execve`` and are inherited by
every process the child starts, and neither can be removed. Being a prefix matters: an
environment's ``.pth`` files run as its interpreter starts, before any worker script, so
the confinement has to be in place before that interpreter is.

- **Landlock** (kernel 5.13 and later, no privilege needed) denies every file access the
  ruleset handles outside the named roots: reads, writes, creation, removal, and exec.
  From ABI 4 (kernel 6.7) it also denies TCP bind and connect, and from ABI 6 (kernel
  6.12) it scopes signals and abstract Unix sockets to the confined processes. It does not
  judge UDP, or a connection to a Unix socket by its path.
- **seccomp** closes what Landlock leaves. ``socket(2)`` fails, or with ``network`` set to
  ``internet`` makes only the two internet families. ``io_uring_setup(2)`` fails, because
  ``IORING_OP_SOCKET`` makes a socket with no ``socket`` call (``confine_probe.py`` shows
  it reaching a Unix socket when left open). With ``processes`` set to ``none`` a new
  process fails while a new thread does not. Five calls that reach other domains with
  neither a file nor a socket (the kernel keyring, ``bpf``, ``perf_event_open``) fail.
  ``socketpair(2)`` stays, since an asyncio event loop makes one for itself.

Standard library only. ``probe`` prints what this kernel offers and changes nothing.

Usage:
    confine_linux.py probe
    confine_linux.py run POLICY_JSON -- ARGV...

``POLICY_JSON`` is ``{"read": [paths], "write": [paths], "network": "none" | "internet",
"processes": "confined" | "none"}``; the last two default to ``none`` and ``confined``. A
path that does not exist is skipped, as a profile's ``subpath`` of a missing directory
matches nothing. ``"io_uring": "open"`` leaves that call alone, which only the probe asks
for, to show the hole.
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
ALLOW = 0x7FFF0000
ERRNO = 0x00050000
KILL_PROCESS = 0x80000000
# Classic BPF: load a word of the call's record, compare, test bits, and answer.
LOAD, JUMP_EQUAL, JUMP_AT_LEAST, JUMP_ANY_BIT, ANSWER = 0x20, 0x15, 0x35, 0x45, 0x06
RECORD_NUMBER, RECORD_ARCHITECTURE, RECORD_FIRST_ARGUMENT = 0, 4, 16
EPERM, EACCES, ENOSYS = 1, 13, 38
AF_INET, AF_INET6 = 2, 10
CLONE_THREAD = 0x00010000
X32_SYSCALL_BIT = 0x40000000

Instruction = tuple[int, int, int, int]


class Machine:
    """One architecture's audit number and the numbers of the calls the filter names."""

    def __init__(self, audit: int, socket: int, clone: int, forks: tuple[int, ...]) -> None:
        self.audit = audit
        self.socket = socket
        self.clone = clone
        self.forks = forks


IO_URING_SETUP = 425
CLONE3 = 435
MACHINES: dict[str, Machine] = {
    "x86_64": Machine(0xC000003E, 41, 56, (57, 58)),
    "aarch64": Machine(0xC00000B7, 198, 220, ()),
}
# add_key, request_key, keyctl, bpf, perf_event_open.
OTHER_DOMAINS: dict[str, tuple[int, ...]] = {
    "x86_64": (248, 249, 250, 321, 298),
    "aarch64": (217, 218, 219, 280, 241),
}

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


def apply_landlock(read: list[str], write: list[str], *, network: str) -> int:
    """Confine this process to *read* and *write*; returns the ABI used, 0 for none."""
    abi = landlock_abi()
    if abi == 0:
        return 0
    handled_fs = _handled_fs(abi)
    handled_net = NET_BIND_TCP | NET_CONNECT_TCP if network == "none" and abi >= 4 else 0
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


def _refuse(error: int) -> list[Instruction]:
    return [(ANSWER, 0, 0, ERRNO | error)]


def filter_program(machine: str, *, network: str, processes: str, io_uring: str) -> bytes | None:
    """The seccomp program for *machine*: one block per call it names, then allow."""
    known = MACHINES.get(machine)
    if known is None:
        return None
    blocks: list[tuple[int, list[Instruction]]] = []
    if network == "internet":
        # Sockets of the two internet families only: no Unix, netlink, or packet socket.
        internet: list[Instruction] = [
            (LOAD, 0, 0, RECORD_FIRST_ARGUMENT),
            (JUMP_EQUAL, 2, 0, AF_INET),
            (JUMP_EQUAL, 1, 0, AF_INET6),
            (ANSWER, 0, 0, ERRNO | EACCES),
            (ANSWER, 0, 0, ALLOW),
        ]
        blocks.append((known.socket, internet))
    else:
        blocks.append((known.socket, _refuse(EPERM)))
    if io_uring != "open":
        blocks.append((IO_URING_SETUP, _refuse(ENOSYS)))
    if processes == "none":
        # A thread is a clone with CLONE_THREAD; any other clone is a new process. clone3
        # keeps its flags behind a pointer, so it is refused and libc falls back to clone.
        threads_only: list[Instruction] = [
            (LOAD, 0, 0, RECORD_FIRST_ARGUMENT),
            (JUMP_ANY_BIT, 1, 0, CLONE_THREAD),
            (ANSWER, 0, 0, ERRNO | EPERM),
            (ANSWER, 0, 0, ALLOW),
        ]
        blocks.append((known.clone, threads_only))
        blocks.append((CLONE3, _refuse(ENOSYS)))
        blocks.extend((number, _refuse(EPERM)) for number in known.forks)
    blocks.extend((number, _refuse(ENOSYS)) for number in OTHER_DOMAINS[machine])
    program: list[Instruction] = [
        (LOAD, 0, 0, RECORD_ARCHITECTURE),
        (JUMP_EQUAL, 1, 0, known.audit),
        (ANSWER, 0, 0, KILL_PROCESS),
        (LOAD, 0, 0, RECORD_NUMBER),
        (JUMP_AT_LEAST, 0, 1, X32_SYSCALL_BIT),
        (ANSWER, 0, 0, KILL_PROCESS),
    ]
    for number, block in blocks:
        program.append((JUMP_EQUAL, 0, len(block), number))
        program.extend(block)  # every path through a block answers, so none falls out
    program.append((ANSWER, 0, 0, ALLOW))
    return b"".join(struct.pack("=HBBI", *instruction) for instruction in program)


def apply_filter(*, network: str, processes: str, io_uring: str) -> bool:
    """Install the filter in this process and everything it starts."""
    program = filter_program(
        platform.machine(), network=network, processes=processes, io_uring=io_uring
    )
    if program is None:
        return False
    instructions = ctypes.create_string_buffer(program, len(program))
    # struct sock_fprog { unsigned short len; struct sock_filter *filter; }, natively aligned.
    filter_program_struct = struct.pack("HP", len(program) // 8, ctypes.addressof(instructions))
    holder = ctypes.create_string_buffer(filter_program_struct, len(filter_program_struct))
    result: int = _libc.prctl(
        ctypes.c_int(PR_SET_SECCOMP),
        ctypes.c_ulong(SECCOMP_MODE_FILTER),
        ctypes.c_void_p(ctypes.addressof(holder)),
        ctypes.c_ulong(0),
        ctypes.c_ulong(0),
    )
    return result == 0


def confine(policy: dict[str, Any]) -> dict[str, Any]:
    """Apply *policy* to this process; what was applied, for the caller to judge."""
    no_new_privileges: int = _libc.prctl(
        ctypes.c_int(PR_SET_NO_NEW_PRIVS),
        ctypes.c_ulong(1),
        ctypes.c_ulong(0),
        ctypes.c_ulong(0),
        ctypes.c_ulong(0),
    )
    if no_new_privileges != 0:
        return {"landlock_abi": 0, "filter": False}
    network = str(policy.get("network", "none"))
    read = [str(path) for path in policy.get("read", [])]
    write = [str(path) for path in policy.get("write", [])]
    abi = apply_landlock(read, write, network=network)
    filtered = apply_filter(
        network=network,
        processes=str(policy.get("processes", "confined")),
        io_uring=str(policy.get("io_uring", "refused")),
    )
    return {"landlock_abi": abi, "filter": filtered}


def main() -> None:
    if sys.argv[1:2] == ["probe"]:
        report = {"landlock_abi": landlock_abi(), "machine": platform.machine()}
        print(json.dumps({**report, "filter_known": platform.machine() in MACHINES}))
        return
    if sys.argv[1:2] != ["run"] or "--" not in sys.argv:
        raise SystemExit(__doc__)
    policy: dict[str, Any] = json.loads(sys.argv[2])
    command = sys.argv[sys.argv.index("--") + 1 :]
    applied = confine(policy)
    if applied["landlock_abi"] == 0 or not applied["filter"]:
        # Fail closed: a caller that asked for confinement never gets an unconfined child.
        raise SystemExit(f"confine_linux: confinement is not available here: {applied}")
    os.execv(command[0], command)


if __name__ == "__main__":
    main()
