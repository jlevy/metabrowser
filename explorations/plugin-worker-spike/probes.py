"""Spike: probes of the second shape's worker, on a stand-in plugin that needs no network.

Runs with the host Metabrowser's interpreter. It builds a plugin environment offline (a
standard-library venv, with the stand-in plugin's entry point written by hand), then
answers four questions the first two spikes left open:

- ``lifecycle``: does the lifeline hold when a hook blocks the worker's event loop, what
  a deadline kill takes with it, and whether a forked child reaches the protocol;
- ``transport``: what a response costs by its size, with no polling inside the timing;
- ``confined``: the same worker behind this platform's confinement prefix
  (``confine_backend.py``), and what a hook can then reach;
- ``identity``: whether a Git common directory's device and inode identify a clone, and
  the ways a folder can claim to be a trusted clone's worktree;
- ``watchdog``, ``locate``, ``pth``, and ``pdf``: a group leader that outlives nothing, a
  plugin directory found without importing, ``.pth`` code at interpreter start, and the
  repository's PDF render child behind the confinement prefix.

Usage: probes.py SCRATCH_DIR [PROBE ...]

Prints JSON that names no path. With no probe named, runs them all.
"""

from __future__ import annotations

import asyncio
import configparser
import csv
import importlib
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

import confine_backend
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
    (info / "RECORD").write_text("standin.pth,,\n")  # as an editable install records its .pth
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
        # No /proc, as on macOS: ask ps, which prints nothing for a reaped process.
        done = subprocess.run(["ps", "-o", "stat=", "-p", str(pid)], capture_output=True, text=True)
        state = done.stdout.strip()[:1] or "Z"
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
    worker.wait()
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
    worker.wait()
    result["request pipe closed while a synchronous hook runs"] = {
        "exited after ms": round((time.perf_counter() - hung_up) * 1000, 1)
    }

    # The same while a hook sits in native code that keeps the interpreter lock.
    worker, _ = bench.start()
    ask(worker, "native_sleep", "seconds=6")
    time.sleep(0.5)
    hung_up = time.perf_counter()
    worker.hang_up()
    time.sleep(2.0)
    still_running = alive(worker.pid)
    worker.wait()
    result["request pipe closed while a hook holds the interpreter lock in native code"] = {
        "worker running 2 s later": still_running,
        "exited after s": round(time.perf_counter() - hung_up, 1),
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
    except (TimeoutError, EOFError):  # EOFError: the host saw the worker go
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

    # A forked child writes to the reply descriptor, which an exec'd one cannot reach.
    worker, _ = bench.start()
    readers = threading.active_count()
    try:
        call(worker, "fork_writes_protocol", timeout=5)
        forked = "answered"
    except (TimeoutError, EOFError):  # EOFError: the host saw the worker go
        forked = "never answered"
    try:
        call(worker, "info", timeout=3)
        after = "answered"
    except (TimeoutError, EOFError):  # EOFError: the host saw the worker go
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
    backend = confine_backend.name()
    if backend is None:
        return {"skipped": "no confinement backend in this spike for this platform"}
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
            *confine_backend.interpreter_roots(),
            str(bench.scratch / "env"),
            str(bench.runtime),
            str(bench.root),
            str(HERE),
            "/dev/null",
            "/dev/urandom",
        ],
        "write": [str(writable)],
        "network": "none",
    }
    prefix = tuple(confine_backend.prefix(policy))
    result: Result = {"backend": backend}
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

    # Three folders that claim a trusted clone, with nothing written into the clone.
    _git("clone", "-q", "first", "trusted", cwd=work)
    git_dir = work / "trusted" / ".git"
    _git("worktree", "add", "-q", str(work / "linked"), "-b", "linked", cwd=work / "trusted")
    forged = {
        "a .git file naming the clone's Git directory": work / "names-the-clone",
        "a .git file naming one of the clone's worktrees": work / "names-a-worktree",
        "a .git directory holding only HEAD and commondir": work / "commondir-only",
    }
    names_clone, names_worktree, commondir_only = forged.values()
    for folder in forged.values():
        folder.mkdir()
    (names_clone / ".git").write_text(f"gitdir: {git_dir}\n")
    (names_worktree / ".git").write_text(f"gitdir: {git_dir / 'worktrees' / 'linked'}\n")
    (commondir_only / ".git").mkdir()
    (commondir_only / ".git" / "HEAD").write_text((git_dir / "HEAD").read_text())
    (commondir_only / ".git" / "commondir").write_text(f"{git_dir}\n")

    def back_pointers() -> list[Path]:
        return [
            Path(each.read_text().strip()).parent for each in git_dir.glob("worktrees/*/gitdir")
        ]

    trusted_common = _common_directory(work / "trusted")
    listed = _git("worktree", "list", "--porcelain", cwd=work / "trusted")
    claims: Result = {}
    for how, folder in forged.items():
        claims[how] = {
            "git reports the trusted clone's common directory": _common_directory(folder)
            == trusted_common,
            "the clone lists it or holds a back-pointer to it": str(folder) in listed
            or folder in back_pointers(),
        }
    real = work / "linked" in back_pointers()
    # A worktree moved by hand: the clone's back-pointer still names where it was.
    shutil.move(str(work / "linked"), str(work / "moved"))
    return {
        "file system": _file_system(work),
        "reclone of another repository kept the device and inode": f"{same} of {rounds}",
        "forged folders": claims,
        "the clone holds a back-pointer to its real linked worktree": real,
        "after that worktree is moved by hand, to its new path": work / "moved" in back_pointers(),
    }


def _file_system(path: Path) -> str:
    if sys.platform == "darwin":
        # BSD stat has no file system type; the mount table names it.
        mount_point = subprocess.run(["df", "-P", str(path)], capture_output=True, text=True)
        point = mount_point.stdout.strip().splitlines()[-1].split()[-1]
        for line in subprocess.run(["mount"], capture_output=True, text=True).stdout.splitlines():
            if f" on {point} (" in line:
                return line.rsplit("(", 1)[1].split(",")[0]
        return "unknown"
    done = subprocess.run(
        ["stat", "-f", "-c", "%T", str(path)], capture_output=True, text=True, check=False
    )
    return done.stdout.strip() or "unknown"


# A group leader that holds a lifeline from the server, starts the target, and kills its
# own process group when the lifeline ends or the target exits. It is /bin/sh here; the
# plan's is the confinement launcher. LIFELINE is replaced by the descriptor's number.
WATCHDOG = r"""
"$@" &
target=$!
( while read -r _ <&LIFELINE; do :; done; kill -KILL 0 ) &
wait "$target"
kill -KILL 0
"""
# Stands in for a worker stuck in native code: it ignores what can be ignored, reads
# nothing, and has started a program of its own. It prints that program's pid and its own.
STUCK = "trap '' TERM INT HUP; sleep 40 & echo $!; echo $$; sleep 41"
SERVER = r"""
import os, subprocess, sys, time
script, stuck = sys.argv[1:3]
lifeline_read, lifeline_write = os.pipe()
leader = subprocess.Popen(
    ["/bin/sh", "-c", script.replace("LIFELINE", str(lifeline_read)), "watchdog", "/bin/sh", "-c", stuck],
    pass_fds=(lifeline_read,), process_group=0, stdin=subprocess.DEVNULL,
    stdout=subprocess.PIPE, text=True, env={"PATH": "/usr/bin:/bin"},
)
os.close(lifeline_read)
print(leader.pid, int(leader.stdout.readline()), int(leader.stdout.readline()), flush=True)
time.sleep(60)
"""


def watchdog(bench: Bench) -> Result:
    """Whether a watchdog group leader ends a stuck target and its child when the server
    is killed outright, which a lifeline inside the target cannot promise."""
    command = [sys.executable, "-I", "-c", SERVER, WATCHDOG, STUCK]
    server = subprocess.Popen(command, stdout=subprocess.PIPE, text=True)
    if server.stdout is None:
        raise RuntimeError("the server has no output")
    leader, child, target = (int(part) for part in server.stdout.readline().split())
    before = {"leader": alive(leader), "target": alive(target), "its child": alive(child)}
    server.kill()
    server.wait()
    time.sleep(0.5)
    after = {"leader": alive(leader), "target": alive(target), "its child": alive(child)}
    return {"running before the server is killed": before, "running 0.5 s after": after}


def _entry_points(info: Path) -> dict[str, str]:
    entry = info / "entry_points.txt"
    if not entry.is_file():
        return {}
    parser = configparser.ConfigParser(delimiters=("=",))
    parser.optionxform = lambda optionstr: optionstr
    parser.read_string(entry.read_text())
    if not parser.has_section("metabrowser.plugins"):
        return {}
    return dict(parser.items("metabrowser.plugins"))


def locate_plugin(site: Path, info: Path, value: str) -> tuple[str, list[Path]]:
    """A provider's plugin directories, found from its metadata without importing it.

    A wheel's ``RECORD`` lists every file it owns, the manifest among them. An editable
    install's ``RECORD`` lists a ``.pth`` whose path line is the source root.
    """
    module = value.partition(":")[0].split(".")[0]
    record = info / "RECORD"
    owned = [row[0] for row in csv.reader(record.read_text().splitlines()) if row]
    manifests = [name for name in owned if name.endswith("/manifest.toml")]
    recorded = [(site / name).parent for name in manifests if name.split("/")[0] == module]
    if recorded:
        return "RECORD", [found for found in recorded if (found / "index.js").is_file()]
    for name in owned:
        if not name.endswith(".pth"):
            continue
        for line in (site / name).read_text().splitlines():
            package = Path(line) / module
            if line and not line.startswith(("import ", "import\t", "#")) and package.is_dir():
                found = sorted(package.rglob("manifest.toml"))[:64]
                return ".pth path line", [
                    m.parent for m in found if (m.parent / "index.js").is_file()
                ]
    return "not without importing", []


def locate(bench: Bench) -> Result:
    """Where the stand-in's plugin directory is, from metadata alone, and what that costs.

    The stand-in is installed in the editable shape. A second copy is laid down in the
    wheel shape, with a ``RECORD`` that lists its files, as uv writes one.
    """
    (site,) = (bench.scratch / "env" / "lib").glob("python*/site-packages")
    wheel = site / "wheelshaped"
    shutil.copytree(
        HERE / "standin" / "standin_plugin" / "plugin", wheel / "plugin", dirs_exist_ok=True
    )
    (wheel / "__init__.py").write_text("")
    info = site / "wheelshaped-0.0.0.dist-info"
    info.mkdir(exist_ok=True)
    (info / "METADATA").write_text("Metadata-Version: 2.1\nName: wheelshaped\nVersion: 0.0.0\n")
    (info / "entry_points.txt").write_text(
        "[metabrowser.plugins]\nwheel = wheelshaped:plugin_dir\n"
    )
    rows = [
        "wheelshaped/__init__.py,,",
        "wheelshaped/plugin/manifest.toml,,",
        "wheelshaped/plugin/index.js,,",
    ]
    (info / "RECORD").write_text("\n".join(rows) + "\n")
    started = time.perf_counter()
    found: Result = {}
    for each in sorted(site.glob("*.dist-info")):
        for name, value in _entry_points(each).items():
            how, folders = locate_plugin(site, each, value)
            found[name] = {"found by": how, "plugin directories": len(folders)}
    elapsed = (time.perf_counter() - started) * 1000
    modules = subprocess.run(
        [bench.python, "-I", "-c", "import sys; print('standin_plugin' in sys.modules)"],
        capture_output=True,
        text=True,
        check=True,
    )
    return {
        "providers": found,
        "scan and locate, ms": round(elapsed, 2),
        "a provider module was imported to do it": modules.stdout.strip() == "True",
    }


def pth(bench: Bench) -> Result:
    """Whether an environment's ``.pth`` code runs as its interpreter starts, isolated mode
    included, and whether confinement applied by a prefix is in place before it."""
    (site,) = (bench.scratch / "env" / "lib").glob("python*/site-packages")
    marks = bench.scratch / "pth-marks"
    shutil.rmtree(marks, ignore_errors=True)
    marks.mkdir()
    line = f"import pathlib; pathlib.Path({str(marks / 'ran')!r}).write_text('x')\n"
    (site / "zz_probe.pth").write_text(line)
    result: Result = {}
    try:
        subprocess.run([bench.python, "-I", "-c", "pass"], check=True)
        result["a .pth line ran in a bare interpreter started with -I"] = (marks / "ran").exists()
        (marks / "ran").unlink(missing_ok=True)
        if confine_backend.name() is not None:
            policy = {"read": [*confine_backend.interpreter_roots(), str(bench.scratch / "env")]}
            command = [*confine_backend.prefix(policy), bench.python, "-I", "-c", "pass"]
            subprocess.run(command, capture_output=True, check=False)
            result["the same line wrote its file behind the confinement prefix"] = (
                marks / "ran"
            ).exists()
    finally:
        (site / "zz_probe.pth").unlink(missing_ok=True)
    return result


def pdf(bench: Bench) -> Result:
    """The repository's own PDF render child, unmodified, behind the Linux prefix through
    the ``Sandbox`` seam it already has. macOS has its own profile for it already, which
    ``tests/test_pdf_preview_sandbox.py`` runs."""
    if not sys.platform.startswith("linux"):
        return {"skipped": "macOS confines this child already; see the PDF sandbox tests"}
    sys.path.insert(0, str(HERE.parents[1]))  # for the suite's sample document
    preview = importlib.import_module("metabrowser.builtin_plugins.pdf.preview")
    isolation = importlib.import_module("metabrowser.builtin_plugins.pdf.preview_isolation")
    sample: bytes = vars(importlib.import_module("tests.test_pdf_surfaces_session"))["_PDF"]
    reads = [*isolation.child_read_roots(), *confine_probe.interpreter_roots()]
    reads += ["/usr/share/fonts", "/dev/null", "/dev/urandom"]
    policy: dict[str, Any] = {"read": reads, "processes": "none"}
    backend = isolation.Sandbox(name="landlock+seccomp", prefix=tuple(confine_probe.prefix(policy)))

    def render(sandbox: Any) -> tuple[Any, bytes, float]:
        started = time.perf_counter()
        facts, png = asyncio.run(preview.render(sample, isolation.Isolation(sandbox=sandbox)))
        return facts, png, (time.perf_counter() - started) * 1000

    _, bare_png, _ = render(None)
    facts, confined_png, _ = render(backend)
    without = isolation.isolation_for(trusted=False, sandbox=None)
    return {
        "the rule for an untrusted source with no backend": str(without),
        "the rule for an untrusted source with this backend": type(
            isolation.isolation_for(trusted=False, sandbox=backend)
        ).__name__,
        "confined render equals the bare render": confined_png == bare_png,
        "the server's check accepts it": preview.png_facts(confined_png) == facts,
        "render ms, bare, median of 9": round(statistics.median(render(None)[2] for _ in range(9))),
        "render ms, confined, median of 9": round(
            statistics.median(render(backend)[2] for _ in range(9))
        ),
    }


PROBES: dict[str, Callable[[Bench], Result]] = {
    "lifecycle": lifecycle,
    "transport": transport,
    "confined": confined,
    "identity": identity,
    "watchdog": watchdog,
    "locate": locate,
    "pth": pth,
    "pdf": pdf,
}


def main() -> None:
    scratch = Path(sys.argv[1]).resolve()
    scratch.mkdir(parents=True, exist_ok=True)
    names = sys.argv[2:] or list(PROBES)
    bench = Bench(scratch)
    result: Result = {
        "platform": sys.platform,
        "kernel": os.uname().release.split("-")[0],
        "python": sys.version.split()[0],
        "load_average": round(os.getloadavg()[0], 1),
    }
    for name in names:
        result[name] = PROBES[name](bench)
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
