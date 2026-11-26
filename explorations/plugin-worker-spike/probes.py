"""Spike: probes of the second shape's worker, on a stand-in plugin that needs no network.

Runs with the host Metabrowser's interpreter. It builds a plugin environment offline (a
standard-library venv, with the stand-in plugin's entry point written by hand), then
answers four questions the first two spikes left open:

- ``lifecycle``: does the lifeline hold when a hook blocks the worker's event loop, what
  a deadline kill takes with it, and whether a forked child reaches the protocol;
- ``transport``: what a response costs by its size, with no polling inside the timing;
- ``confined`` (Linux): the same worker behind ``confine_linux.py``, and what a hook can
  then reach;
- ``identity``: whether a Git common directory's device and inode identify a clone, and
  whether a folder can claim to be a trusted clone's worktree.

Usage: probes.py SCRATCH_DIR [lifecycle] [transport] [confined] [identity]

Prints JSON that names no path. With no probe named, runs all four.
"""

from __future__ import annotations

import json
import os
import shutil
import signal
import socket
import statistics
import subprocess
import sys
import threading
import time
from collections.abc import Callable
from pathlib import Path
from typing import Any

HERE = Path(__file__).parent
sys.path.insert(0, str(HERE))  # run with -I, which leaves this folder off the path

import confine_probe
import host_runtime

Result = dict[str, Any]
SIDEKICK = "standin_plugin.sidekick"


def standin_environment(scratch: Path) -> str:
    """A venv holding the stand-in plugin as an editable install, made without a network."""
    env = scratch / "env"
    if not (env / "pyvenv.cfg").is_file():
        subprocess.run([sys.executable, "-m", "venv", "--without-pip", str(env)], check=True)
    (site,) = (env / "lib").glob("python*/site-packages")
    (site / "standin.pth").write_text(f"{HERE / 'standin'}\n")
    info = site / "standin_plugin-0.0.0.dist-info"
    info.mkdir(exist_ok=True)
    (info / "METADATA").write_text("Metadata-Version: 2.1\nName: standin-plugin\nVersion: 0.0.0\n")
    entry_point = "[metabrowser.plugins]\nstandin = standin_plugin:plugin_dir\n"
    (info / "entry_points.txt").write_text(entry_point)
    return str(env / "bin" / "python")


def served_root(scratch: Path) -> Path:
    root = scratch / "root"
    (root / "specs").mkdir(parents=True, exist_ok=True)
    (root / "specs" / "spec.md").write_text("# A process specification\n\nsteps: a, b\n")
    (root / "pool.jsonl").write_text('{"event":"pool_start"}\n{"event":"process_start"}\n')
    (root / "agent.jsonl").write_text('{"type":"system","subtype":"init","session_id":"s"}\n')
    return root


class Bench:
    """One scratch folder's environment, served root, and runtime, and workers on them."""

    def __init__(self, scratch: Path) -> None:
        self.scratch = scratch
        self.python = standin_environment(scratch)
        self.root = served_root(scratch)
        self.runtime = host_runtime.assemble_runtime(scratch / "run")
        self.log = scratch / "run" / "worker.stderr.log"

    def start(self, prefix: tuple[str, ...] = ()) -> tuple[host_runtime.Worker, float]:
        worker, ready = host_runtime.start(self.python, self.root, self.runtime, self.log, prefix)
        return worker, float(ready["spawn_to_listed_ms"])


def call(
    worker: host_runtime.Worker, hook: str, query: str = "", timeout: float = 10
) -> tuple[Result, bytes]:
    sidekick = f"{SIDEKICK}:{hook}"
    return worker.call("call", sidekick=sidekick, path="/x", query=query, timeout=timeout)


def ask(worker: host_runtime.Worker, hook: str, query: str = "") -> Any:
    return worker.request("call", sidekick=f"{SIDEKICK}:{hook}", path="/x", query=query)


def alive(pid: int) -> bool:
    """Whether *pid* is running: a zombie waiting to be reaped is not."""
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    try:
        state = Path(f"/proc/{pid}/stat").read_text().rsplit(")", 1)[1].split()[0]
    except OSError:
        return True
    return state != "Z"


def timed(action: Callable[[], object]) -> float:
    started = time.perf_counter()
    action()
    return (time.perf_counter() - started) * 1000


def lifecycle(bench: Bench) -> Result:
    result: Result = {}

    # The lifeline while an ``async def`` hook blocks the worker's event loop.
    worker, _ = bench.start()
    ask(worker, "blocking_async", "seconds=8")
    time.sleep(0.5)
    hung_up = time.perf_counter()
    worker.hang_up()
    time.sleep(3.0)
    still_running = alive(worker.pid)
    os.waitpid(worker.pid, 0)
    result["request pipe closed while an async hook blocks the loop"] = {
        "worker running 3 s later": still_running,
        "exited after s": round(time.perf_counter() - hung_up, 1),
    }

    # The same with a synchronous hook, which runs in a thread and leaves the loop free.
    worker, _ = bench.start()
    ask(worker, "slow_sync", "seconds=8")
    time.sleep(0.5)
    hung_up = time.perf_counter()
    worker.hang_up()
    os.waitpid(worker.pid, 0)
    result["request pipe closed while a synchronous hook runs"] = {
        "exited after ms": round((time.perf_counter() - hung_up) * 1000, 1)
    }

    # A blocking ``async def`` hook stalls every other call in its worker.
    worker, _ = bench.start()
    ask(worker, "blocking_async", "seconds=3")
    time.sleep(0.2)
    result["trivial hook beside a 3 s blocking async hook, ms"] = round(
        timed(lambda: call(worker, "info"))
    )

    # What a deadline kill takes with it, and what it leaves behind.
    child = int(json.loads(call(worker, "spawn_child")[1])["child_pid"])
    other = ask(worker, "slow_sync", "seconds=1.5")
    worker.request("sleep", seconds=60)
    time.sleep(0.5)
    worker.kill()
    try:
        other.result(timeout=4)
        other_call = "answered"
    except TimeoutError:
        other_call = "never answered"
    child_survived = alive(child)
    result["worker killed at a deadline"] = {
        "another call in flight": other_call,
        "the hook's subprocess still running": child_survived,
        "that subprocess in the host's process group": child_survived
        and os.getpgid(child) == os.getpgid(0),
    }
    if child_survived:
        os.kill(child, signal.SIGKILL)

    # A forked child writes to descriptor 4, which an exec'd one cannot reach.
    worker, _ = bench.start()
    readers = threading.active_count()
    try:
        call(worker, "fork_writes_protocol", timeout=5)
        forked = "answered"
    except TimeoutError:
        forked = "never answered"
    try:
        call(worker, "info", timeout=3)
        after = "answered"
    except TimeoutError:
        after = "never answered"
    result["a forked child writes to the reply pipe"] = {
        "that call": forked,
        "the next call": after,
        "host reader thread ended": threading.active_count() < readers,
    }
    worker.kill()
    return result


def transport(bench: Bench) -> Result:
    worker, _ = bench.start()
    result: Result = {}
    for size in (0, 429_248, 4 << 20, 64 << 20):
        overheads: list[float] = []
        for _ in range(3 if size > (32 << 20) else 9):
            started = time.perf_counter()
            header, body = call(worker, "blob", f"n={size}", timeout=60)
            total = (time.perf_counter() - started) * 1000
            if len(body) != size:
                raise RuntimeError("the body arrived short")
            overheads.append(total - float(header["handler_ms"]))
        result[f"{size} bytes"] = {
            "overhead_ms_median": round(statistics.median(overheads), 2),
            "overhead_ms_max": round(max(overheads), 2),
        }
    large = ask(worker, "blob", f"n={64 << 20}")
    result["trivial hook issued behind a 64 MiB reply, ms"] = round(
        timed(lambda: call(worker, "info")), 1
    )
    large.result(timeout=60)
    result["worker resident MB after the 64 MiB replies"] = round(worker.rss_mb(), 1)
    worker.close()
    return result


def confined(bench: Bench) -> Result:
    if not sys.platform.startswith("linux"):
        return {"skipped": "confine_linux.py is the Linux backend"}
    outside = bench.scratch / "outside"
    writable = bench.scratch / "worker-scratch"
    for folder in (outside, writable):
        folder.mkdir(exist_ok=True)
    (outside / "secret.txt").write_text("secret")
    listener = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    listener.bind(("127.0.0.1", 0))
    listener.listen(8)
    query = f"outside={outside / 'secret.txt'}&scratch={writable}&port={listener.getsockname()[1]}"
    policy = {
        "read": [
            *confine_probe.interpreter_roots(),
            str(bench.scratch / "env"),
            str(bench.runtime),
            str(bench.root),
            str(HERE),
            "/dev/null",
            "/dev/urandom",
        ],
        "write": [str(writable)],
        "network": False,
    }
    launcher = (sys.executable, "-I", "-S", str(HERE / "confine_linux.py"))
    prefix = (*launcher, "run", json.dumps(policy), "--")
    result: Result = {}
    for name, how in (("bare", ()), ("confined", prefix)):
        worker, ready_ms = bench.start(how)
        before = len(worker.callbacks)
        reached: dict[str, str] = json.loads(call(worker, "reach", query)[1])
        result[name] = {
            "spawn_to_listed_ms": round(ready_ms, 1),
            "info": call(worker, "info")[0]["status"],
            "viz-model bytes": len(call(worker, "viz_model", "process=specs/spec.md")[1]),
            "charts on a pool log": call(worker, "charts", "path=pool.jsonl")[0]["status"],
            "charts on an agent log": call(worker, "charts", "path=agent.jsonl")[0]["status"],
            "host calls made": worker.callbacks[before:],
            "reach": reached,
            "exit": worker.close()["status"],
        }
    listener.close()
    return result


def _git(*arguments: str, cwd: Path) -> str:
    identity = ["-c", "user.name=probe", "-c", "user.email=probe@example.invalid"]
    done = subprocess.run(
        ["git", *identity, *arguments], cwd=cwd, capture_output=True, text=True, check=True
    )
    return done.stdout.strip()


def _common_directory(folder: Path) -> tuple[int, int]:
    common = _git("rev-parse", "--path-format=absolute", "--git-common-dir", cwd=folder)
    status = os.stat(common)
    return status.st_dev, status.st_ino


def identity(bench: Bench) -> Result:
    work = bench.scratch / "identity"
    shutil.rmtree(work, ignore_errors=True)
    work.mkdir()
    for name in ("first", "second"):
        _git("init", "-q", name, cwd=work)
        _git("commit", "-q", "--allow-empty", "-m", name, cwd=work / name)

    # A different repository cloned at a path a trusted clone was deleted from.
    same = 0
    rounds = 5
    for _ in range(rounds):
        _git("clone", "-q", "first", "app", cwd=work)
        trusted = _common_directory(work / "app")
        shutil.rmtree(work / "app")
        _git("clone", "-q", "second", "app", cwd=work)
        same += trusted == _common_directory(work / "app")
        shutil.rmtree(work / "app")

    # A folder whose one hand-written file names a trusted clone's Git directory.
    _git("clone", "-q", "first", "trusted", cwd=work)
    forged = work / "forged"
    forged.mkdir()
    (forged / ".git").write_text(f"gitdir: {work / 'trusted' / '.git'}\n")
    _git("worktree", "add", "-q", str(work / "linked"), "-b", "linked", cwd=work / "trusted")
    listed = _git("worktree", "list", "--porcelain", cwd=work / "trusted")
    back_pointers = [
        Path(pointer.read_text().strip()).parent
        for pointer in (work / "trusted" / ".git" / "worktrees").glob("*/gitdir")
    ]
    return {
        "file system": _file_system(work),
        "reclone of another repository kept the device and inode": f"{same} of {rounds}",
        "forged folder reports the trusted clone's common directory": _common_directory(forged)
        == _common_directory(work / "trusted"),
        "the clone lists the forged folder as a worktree": str(forged) in listed,
        "the clone holds a back-pointer to the forged folder": forged in back_pointers,
        "the clone holds a back-pointer to its real linked worktree": work / "linked"
        in back_pointers,
    }


def _file_system(path: Path) -> str:
    done = subprocess.run(
        ["stat", "-f", "-c", "%T", str(path)], capture_output=True, text=True, check=False
    )
    return done.stdout.strip() or "unknown"


PROBES: dict[str, Callable[[Bench], Result]] = {
    "lifecycle": lifecycle,
    "transport": transport,
    "confined": confined,
    "identity": identity,
}


def main() -> None:
    scratch = Path(sys.argv[1]).resolve()
    scratch.mkdir(parents=True, exist_ok=True)
    names = sys.argv[2:] or list(PROBES)
    bench = Bench(scratch)
    result: Result = {
        "kernel": os.uname().release.split("-")[0],
        "python": sys.version.split()[0],
        "load_average": round(os.getloadavg()[0], 1),
    }
    for name in names:
        result[name] = PROBES[name](bench)
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
