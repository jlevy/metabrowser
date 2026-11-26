"""Spike: what a child can do bare and under ``confine_linux.py``, and what the prefix costs.

Runs with the host Metabrowser's interpreter on Linux. It makes a scratch tree, starts a
TCP listener, and runs one checking program twice: bare, and behind the confinement
prefix with a policy that grants reading the interpreter and one folder and writing one
other folder. Each run answers the same questions, so the two columns are the finding.

Usage: confine_probe.py SCRATCH_DIR

Prints JSON that names no path.
"""

from __future__ import annotations

import json
import os
import socket
import statistics
import subprocess
import sys
import sysconfig
import time
from pathlib import Path
from typing import Any

HERE = Path(__file__).parent

# The program each run executes. It answers by what happened, never by a path.
CHECKS = r"""
import asyncio, json, os, signal, socket, subprocess, sys
granted, private, writable, port, parent = sys.argv[1:6]

def attempt(action):
    try:
        action()
        return "allowed"
    except PermissionError:
        return "denied"
    except OSError as exc:
        return f"failed: {type(exc).__name__}"

def write_then_remove(folder):
    path = os.path.join(folder, "probe.txt")
    with open(path, "w") as handle:
        handle.write("x")
    os.remove(path)

def tcp():
    with socket.create_connection(("127.0.0.1", int(port)), timeout=2):
        pass

def unix_socket():
    socket.socket(socket.AF_UNIX, socket.SOCK_STREAM).close()

def udp():
    socket.socket(socket.AF_INET, socket.SOCK_DGRAM).close()

def run_tool():
    subprocess.run(["/bin/true"], check=True)

def event_loop():
    asyncio.new_event_loop().close()

print(json.dumps({
    "read a granted file": attempt(lambda: open(os.path.join(granted, "data.txt")).read()),
    "read a file outside the grants": attempt(lambda: open(os.path.join(private, "secret.txt")).read()),
    "list a folder outside the grants": attempt(lambda: os.listdir(private)),
    "write in the write grant": attempt(lambda: write_then_remove(writable)),
    "write in a read-only grant": attempt(lambda: write_then_remove(granted)),
    "write outside the grants": attempt(lambda: write_then_remove(private)),
    "connect over TCP": attempt(tcp),
    "open a UDP socket": attempt(udp),
    "open a Unix socket": attempt(unix_socket),
    "start a system tool": attempt(run_tool),
    "signal the parent": attempt(lambda: os.kill(int(parent), 0)),
    "make an asyncio event loop": attempt(event_loop),
    "write to an inherited descriptor": attempt(lambda: os.write(1, b"")),
}))
"""


def interpreter_roots() -> list[str]:
    """What the interpreter itself reads: its prefixes and the system's libraries."""
    found = {sys.prefix, sys.base_prefix, sys.exec_prefix, sysconfig.get_path("stdlib")}
    found |= {os.path.realpath(path) for path in found}
    system = ["/usr/lib", "/usr/lib64", "/lib", "/lib64", "/usr/bin", "/bin", "/etc/ld.so.cache"]
    return sorted(found | set(system))


def run_checks(prefix: list[str], arguments: list[str]) -> dict[str, str]:
    command = [*prefix, sys.executable, "-I", "-S", "-c", CHECKS, *arguments]
    done = subprocess.run(command, capture_output=True, text=True, cwd="/", check=False)
    if done.returncode != 0:
        return {"did not run": done.stderr.strip().splitlines()[-1] if done.stderr else "no output"}
    answers: dict[str, str] = json.loads(done.stdout)
    return answers


def start_cost(prefix: list[str], runs: int = 25) -> dict[str, float]:
    command = [*prefix, sys.executable, "-I", "-S", "-c", "pass"]
    subprocess.run(command, cwd="/", check=True)  # one warm-up, discarded
    times: list[float] = []
    for _ in range(runs):
        started = time.perf_counter()
        subprocess.run(command, cwd="/", check=True)
        times.append((time.perf_counter() - started) * 1000)
    return {"median_ms": round(statistics.median(times), 1), "max_ms": round(max(times), 1)}


def main() -> None:
    scratch = Path(sys.argv[1]).resolve()
    granted, private, writable = scratch / "granted", scratch / "private", scratch / "writable"
    for folder in (granted, private, writable):
        folder.mkdir(parents=True, exist_ok=True)
    (granted / "data.txt").write_text("data")
    (private / "secret.txt").write_text("secret")

    listener = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    listener.bind(("127.0.0.1", 0))
    listener.listen(8)
    port = listener.getsockname()[1]

    launcher = [sys.executable, "-I", "-S", str(HERE / "confine_linux.py")]
    probe = subprocess.run([*launcher, "probe"], capture_output=True, text=True, check=True)
    policy = {
        "read": [*interpreter_roots(), str(granted), "/dev/urandom", "/dev/null"],
        "write": [str(writable)],
        "network": False,
    }
    prefix = [*launcher, "run", json.dumps(policy), "--"]
    arguments = [str(granted), str(private), str(writable), str(port), str(os.getpid())]
    result: dict[str, Any] = {
        "kernel": os.uname().release.split("-")[0],
        "python": sys.version.split()[0],
        "probe": json.loads(probe.stdout),
        "bare": run_checks([], arguments),
        "confined": run_checks(prefix, arguments),
        "start_bare": start_cost([]),
        "start_confined": start_cost(prefix),
    }
    listener.close()
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
