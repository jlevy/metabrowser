"""Spike: what a child can do bare and under ``confine_linux.py``, and what the prefix costs.

Runs with the host Metabrowser's interpreter on Linux. It makes a scratch tree, starts a
TCP listener and a Unix socket outside every grant, and runs one checking program under
five policies: bare; confined with the defaults (no network, programs allowed); the same
with ``io_uring_setup`` left open, which is the hole a filter on ``socket`` alone leaves;
with ``network`` set to ``internet``; and with ``processes`` set to ``none``. Each run
answers the same questions, so the columns are the finding.

Usage: confine_probe.py SCRATCH_DIR

Prints JSON that names no path.
"""

from __future__ import annotations

import json
import os
import shutil
import socket
import statistics
import subprocess
import sys
import sysconfig
import tempfile
import threading
import time
from pathlib import Path
from typing import Any

HERE = Path(__file__).parent

# The program each run executes. It answers by what happened, never by a path.
CHECKS = r"""
import asyncio, ctypes, errno, json, mmap, os, socket, struct, subprocess, sys, threading
granted, private, writable, port, parent, unix_path = sys.argv[1:7]
libc = ctypes.CDLL(None, use_errno=True)
libc.syscall.restype = ctypes.c_long

def attempt(action):
    try:
        action()
        return "allowed"
    except OSError as exc:
        return f"refused ({errno.errorcode.get(exc.errno, exc.errno)})"

def call(number, *arguments):
    result = libc.syscall(number, *arguments)
    if result < 0:
        raise OSError(ctypes.get_errno(), "syscall")
    return result

def write_then_remove(folder):
    path = os.path.join(folder, "probe.txt")
    with open(path, "w") as handle:
        handle.write("x")
    os.remove(path)

def tcp():
    with socket.create_connection(("127.0.0.1", int(port)), timeout=2):
        pass

def unix_socket():
    with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as made:
        made.connect(unix_path)

def io_uring_unix_socket():
    # IORING_OP_SOCKET makes a socket with no socket(2) call; then connect it by path.
    params = ctypes.create_string_buffer(120)
    ring = call(425, 4, params)
    sq_entries, cq_entries = struct.unpack("2I", params.raw[:8])
    sq_tail, sq_array = struct.unpack("I", params.raw[44:48])[0], struct.unpack("I", params.raw[64:68])[0]
    cqes = struct.unpack("I", params.raw[100:104])[0]
    shared = dict(flags=mmap.MAP_SHARED, prot=mmap.PROT_READ | mmap.PROT_WRITE)
    sq_ring = mmap.mmap(ring, sq_array + sq_entries * 4, offset=0, **shared)
    cq_ring = mmap.mmap(ring, cqes + cq_entries * 16, offset=0x8000000, **shared)
    sqes = mmap.mmap(ring, sq_entries * 64, offset=0x10000000, **shared)
    sqes[0:64] = struct.pack("=BBHiQQIIQ", 45, 0, 0, socket.AF_UNIX, socket.SOCK_STREAM, 0, 0, 0, 1).ljust(64, b"\0")
    sq_ring[sq_array : sq_array + 4] = struct.pack("I", 0)
    sq_ring[sq_tail : sq_tail + 4] = struct.pack("I", 1)
    call(426, ring, 1, 1, 1, None, 0)
    _user, made, _flags = struct.unpack("=QiI", cq_ring[cqes : cqes + 16])
    if made < 0:
        raise OSError(-made, "IORING_OP_SOCKET")
    with socket.socket(fileno=made) as connected:
        connected.connect(unix_path)

def fork():
    pid = os.fork()
    if pid == 0:
        os._exit(0)
    os.waitpid(pid, 0)

def thread():
    started = threading.Thread(target=lambda: None)
    started.start()
    started.join()

keyctl = {"x86_64": 250, "aarch64": 219}[os.uname().machine]
print(json.dumps({
    "read a granted file": attempt(lambda: open(os.path.join(granted, "data.txt")).read()),
    "read a file outside the grants": attempt(lambda: open(os.path.join(private, "secret.txt")).read()),
    "list a folder outside the grants": attempt(lambda: os.listdir(private)),
    "write in the write grant": attempt(lambda: write_then_remove(writable)),
    "write in a read-only grant": attempt(lambda: write_then_remove(granted)),
    "write outside the grants": attempt(lambda: write_then_remove(private)),
    "connect over TCP": attempt(tcp),
    "open a UDP socket": attempt(lambda: socket.socket(socket.AF_INET, socket.SOCK_DGRAM).close()),
    "connect to a Unix socket outside the grants": attempt(unix_socket),
    "the same, with a socket from io_uring": attempt(io_uring_unix_socket),
    "start a system tool": attempt(lambda: subprocess.run(["/bin/true"], check=True)),
    "fork": attempt(fork),
    "start a thread": attempt(thread),
    "signal the parent": attempt(lambda: os.kill(int(parent), 0)),
    "ask the kernel keyring": attempt(lambda: call(keyctl, 0, -1, 0)),
    "make an asyncio event loop": attempt(lambda: asyncio.new_event_loop().close()),
    "write to an inherited descriptor": attempt(lambda: os.write(1, b"")),
}))
"""


def interpreter_roots() -> list[str]:
    """What the interpreter itself reads: its prefixes and the system's libraries."""
    found = {sys.prefix, sys.base_prefix, sys.exec_prefix, sysconfig.get_path("stdlib")}
    found |= {os.path.realpath(path) for path in found}
    system = ["/usr/lib", "/usr/lib64", "/lib", "/lib64", "/usr/bin", "/bin", "/etc/ld.so.cache"]
    return sorted(found | set(system))


def launcher() -> list[str]:
    return [sys.executable, "-I", "-S", str(HERE / "confine_linux.py")]


def prefix(policy: dict[str, Any]) -> list[str]:
    return [*launcher(), "run", json.dumps(policy), "--"]


def run_checks(before: list[str], arguments: list[str]) -> dict[str, str]:
    command = [*before, sys.executable, "-I", "-S", "-c", CHECKS, *arguments]
    done = subprocess.run(command, capture_output=True, text=True, cwd="/", check=False)
    if done.returncode != 0:
        return {"did not run": done.stderr.strip().splitlines()[-1] if done.stderr else "no output"}
    answers: dict[str, str] = json.loads(done.stdout)
    return answers


def start_cost(before: list[str], runs: int = 25) -> dict[str, float]:
    command = [*before, sys.executable, "-I", "-S", "-c", "pass"]
    subprocess.run(command, cwd="/", check=True)  # one warm-up, discarded
    times: list[float] = []
    for _ in range(runs):
        started = time.perf_counter()
        subprocess.run(command, cwd="/", check=True)
        times.append((time.perf_counter() - started) * 1000)
    return {"median_ms": round(statistics.median(times), 1), "max_ms": round(max(times), 1)}


def accept_forever(listener: socket.socket) -> None:
    while True:
        try:
            connection, _ = listener.accept()
        except OSError:
            return
        connection.close()


def main() -> None:
    scratch = Path(sys.argv[1]).resolve()
    granted, private, writable = scratch / "granted", scratch / "private", scratch / "writable"
    for folder in (granted, private, writable):
        folder.mkdir(parents=True, exist_ok=True)
    (granted / "data.txt").write_text("data")
    (private / "secret.txt").write_text("secret")

    tcp = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    tcp.bind(("127.0.0.1", 0))
    tcp.listen(8)
    # Stands in for an agent socket or a session bus: a Unix socket outside every grant.
    # A Unix socket's path is at most 108 bytes, so it gets a short folder of its own.
    unix_folder = Path(tempfile.mkdtemp(prefix="mb-probe-"))
    unix_path = unix_folder / "agent.sock"
    unix = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    unix.bind(str(unix_path))
    unix.listen(8)
    for listener in (tcp, unix):
        threading.Thread(target=accept_forever, args=(listener,), daemon=True).start()

    probe = subprocess.run([*launcher(), "probe"], capture_output=True, text=True, check=True)
    base: dict[str, Any] = {
        "read": [*interpreter_roots(), str(granted), "/dev/urandom", "/dev/null"],
        "write": [str(writable)],
    }
    arguments = [str(granted), str(private), str(writable), str(tcp.getsockname()[1])]
    arguments += [str(os.getpid()), str(unix_path)]
    result: dict[str, Any] = {
        "kernel": os.uname().release.split("-")[0],
        "python": sys.version.split()[0],
        "probe": json.loads(probe.stdout),
        "bare": run_checks([], arguments),
        "confined": run_checks(prefix(base), arguments),
        "confined, io_uring left open": run_checks(prefix({**base, "io_uring": "open"}), arguments),
        "confined, network internet": run_checks(
            prefix({**base, "network": "internet"}), arguments
        ),
        "confined, processes none": run_checks(prefix({**base, "processes": "none"}), arguments),
        "start_bare": start_cost([]),
        "start_confined": start_cost(prefix(base)),
    }
    tcp.close()
    unix.close()
    shutil.rmtree(unix_folder, ignore_errors=True)
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
