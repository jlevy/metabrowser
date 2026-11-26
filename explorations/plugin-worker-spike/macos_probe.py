"""Spike: the macOS half of Key Decision 11 (``mb-gmut``), run on a Mac.

Runs with the host Metabrowser's interpreter on macOS. It answers what the Linux probes
answered for Landlock and seccomp, for ``sandbox-exec`` with a profile from
``confine_macos.py``, and the questions only macOS has:

- ``backend``: the macOS version, and whether ``sandbox-exec`` applies a deny-default
  profile here.
- ``checks``: one program bare and under policies that vary network access, process
  creation, and the Mach services used by account lookup and name resolution.
- ``learn``: the kernel denials from the stand-in worker serving its hooks under the
  default profile, attributed to that worker alone.
- ``worker``: the stand-in's hooks and their access under each profile, and whether a
  confined worker exits when the request pipe closes during a synchronous hook.
- ``cost``: what the prefix adds to an interpreter's start and to a worker's.
- ``descriptors``: whether a descriptor the host hands over survives ``posix_spawn``'s
  same-number ``dup2`` and ``sandbox-exec``'s exec.
- ``nested``: whether ``sandbox-exec`` and the PDF preview's own probe work inside an
  outer sandbox, as a server an agent starts would be.
- ``privacy``, only with ``--privacy FILE``: a file in a folder macOS's privacy controls
  guard, such as ``~/Documents``, read bare and under a profile that does not grant it.
  Watch the desktop for a privacy prompt. This probe cannot determine TCC ordering.
- ``real``, only with ``--real PLUGIN_PYTHON ROOT SPEC FIXTURE_DIR``: the downstream
  plugins, which are not public, bare and confined, with kernel denials recorded by worker.
  The arguments are ``host_runtime.py``'s.

Usage: macos_probe.py SCRATCH_DIR [PROBE ...] [--privacy FILE] [--real PY ROOT SPEC FIX]

Prints JSON that names no path: paths in the kernel's reports are given relative to the
roots the probe knows (``<env>``, ``<python>``, ``~``, and so on).
"""

from __future__ import annotations

import fcntl
import hashlib
import json
import os
import re
import shutil
import socket
import statistics
import subprocess
import sys
import tempfile
import threading
import time
from collections.abc import Callable
from datetime import datetime
from pathlib import Path
from typing import Any
from urllib.parse import urlencode

HERE = Path(__file__).parent
sys.path.insert(0, str(HERE))  # run with -I, which leaves this folder off the path

import confine_backend
import confine_macos
import confine_probe
import host_runtime
import probes

Result = dict[str, Any]

# The Mach services a Python worker is expected to need beyond the default: the user
# database `getpwuid` and `os.path.expanduser` reach without HOME, and the resolver.
# The `checks` probe shows which of them matter; `learn` shows what else does.
LIBINFO_SERVICES = (
    "com.apple.system.opendirectoryd.libinfo",
    "com.apple.system.notification_center",
)
RESOLVER_SERVICES = ("com.apple.dnssd.service",)

# How long the unified log takes to hold a kernel report after the call it reports;
# a guess, which `learn` records alongside what it found.
LOG_SETTLE_SECONDS = 2.0

# The checking program. It answers by what happened, never by a path.
CHECKS = r"""
import asyncio, errno, json, multiprocessing.synchronize, os, pwd, socket, subprocess, sys, threading
granted, private, writable, port, udp_port, parent, unix_path = sys.argv[1:8]

def attempt(action):
    try:
        action()
        return "allowed"
    except socket.gaierror as exc:
        return f"refused (resolver error {exc.errno})"
    except OSError as exc:
        return f"refused ({errno.errorcode.get(exc.errno, exc.errno)})"
    except Exception as exc:
        return f"failed ({type(exc).__name__})"

def write_then_remove(folder):
    path = os.path.join(folder, "probe.txt")
    with open(path, "w") as handle:
        handle.write("x")
    os.remove(path)

def tcp():
    with socket.create_connection(("127.0.0.1", int(port)), timeout=2):
        pass

def udp():
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as made:
        made.sendto(b"probe", ("127.0.0.1", int(udp_port)))

def unix_socket():
    with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as made:
        made.connect(unix_path)

def fork():
    pid = os.fork()
    if pid == 0:
        os._exit(0)
    os.waitpid(pid, 0)

def thread():
    started = threading.Thread(target=lambda: None)
    started.start()
    started.join()

def resolve(name):
    socket.getaddrinfo(name, 80, type=socket.SOCK_STREAM)

print(json.dumps({
    "read a granted file": attempt(lambda: open(os.path.join(granted, "data.txt")).read()),
    "read a file outside the grants": attempt(lambda: open(os.path.join(private, "secret.txt")).read()),
    "list a folder outside the grants": attempt(lambda: os.listdir(private)),
    "list the home folder": attempt(lambda: os.listdir(os.path.expanduser("~"))),
    "write in the write grant": attempt(lambda: write_then_remove(writable)),
    "write in a read-only grant": attempt(lambda: write_then_remove(granted)),
    "write outside the grants": attempt(lambda: write_then_remove(private)),
    "connect over TCP": attempt(tcp),
    "send over UDP": attempt(udp),
    "open a UDP socket": attempt(lambda: socket.socket(socket.AF_INET, socket.SOCK_DGRAM).close()),
    "connect to a Unix socket outside the grants": attempt(unix_socket),
    "resolve localhost": attempt(lambda: resolve("localhost")),
    "resolve an internet name": attempt(lambda: resolve("example.com")),
    "look up the user (getpwuid)": attempt(lambda: pwd.getpwuid(os.getuid())),
    "start a system tool": attempt(lambda: subprocess.run(["/usr/bin/true"], check=True)),
    "fork": attempt(fork),
    "start a thread": attempt(thread),
    "make a POSIX semaphore (multiprocessing)": attempt(lambda: multiprocessing.synchronize.Lock(ctx=multiprocessing.get_context("spawn"))),
    "signal the parent": attempt(lambda: os.kill(int(parent), 0)),
    "make an asyncio event loop": attempt(lambda: asyncio.new_event_loop().close()),
    "write to an inherited descriptor": attempt(lambda: os.write(1, b"")),
}))
"""

# A kernel sandbox report, as `log show` prints it: process name, pid, the verdict, the
# operation, and what it was applied to.
REPORT = re.compile(
    r"Sandbox: (?P<process>.+?)\((?P<pid>\d+)\) (?P<verdict>allow|deny)(?:\(\d+\))? "
    r"(?P<operation>[\w*-]+)(?: (?P<argument>.*))?$"
)


class Redactor:
    """Paths as the roots they fall under, so a result names no personal path."""

    def __init__(self, roots: dict[str, str]) -> None:
        pairs = {os.path.realpath(path): label for label, path in roots.items() if path}
        pairs |= {path: label for label, path in roots.items() if path}
        self.pairs = sorted(pairs.items(), key=lambda pair: -len(pair[0]))

    def __call__(self, text: str) -> str:
        for path, label in self.pairs:
            text = text.replace(path, label)
        # Another account's home, by the folder that holds this one's.
        homes = re.escape(str(Path.home().parent))
        return re.sub(homes + r"/[^/\s]+", "~", text)


def since() -> str:
    """A start time `log show` reads."""
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def kernel_denials(start: str, pids: set[int], redact: Redactor) -> list[str]:
    """Report denials for this probe's processes, without replaying them as grants."""
    if not pids:
        return []
    time.sleep(LOG_SETTLE_SECONDS)
    command = [
        "/usr/bin/log", "show", "--start", start, "--style", "syslog",
        "--predicate", 'eventMessage CONTAINS "Sandbox: "',
    ]  # fmt: skip
    done = subprocess.run(command, capture_output=True, text=True, check=True)
    denied: set[str] = set()
    for line in done.stdout.splitlines():
        match = REPORT.search(line)
        if match and int(match["pid"]) in pids and match["verdict"] == "deny":
            denied.add(f"{match['operation']} {redact(match['argument'] or '')}".strip())
    return sorted(denied)


def communicate(process: subprocess.Popen[str]) -> tuple[str, str]:
    try:
        return process.communicate(timeout=15)
    except subprocess.TimeoutExpired:
        process.kill()
        process.communicate()
        raise


def run_checks(before: list[str], arguments: list[str]) -> tuple[dict[str, str], int]:
    command = [*before, sys.executable, "-I", "-S", "-c", CHECKS, *arguments]
    with subprocess.Popen(
        command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, cwd="/"
    ) as process:
        stdout, stderr = communicate(process)
        if process.returncode != 0:
            tail = stderr.strip().splitlines()[-1] if stderr.strip() else "no output"
            return {"did not run": tail}, process.pid
        return json.loads(stdout), process.pid


class Listeners:
    """A TCP listener and a Unix socket outside every grant, as an agent socket would be."""

    def __init__(self, socket_dir: Path) -> None:
        self.tcp = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.tcp.bind(("127.0.0.1", 0))
        self.tcp.listen(8)
        self.udp = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.udp.bind(("127.0.0.1", 0))
        # A Unix socket's path is at most 104 bytes on macOS: a short folder of its own.
        self.folder = Path(tempfile.mkdtemp(prefix="mb-probe-", dir=socket_dir))
        self.unix_path = self.folder / "agent.sock"
        self.unix = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        self.unix.bind(str(self.unix_path))
        self.unix.listen(8)
        for listener in (self.tcp, self.unix):
            threading.Thread(
                target=confine_probe.accept_forever, args=(listener,), daemon=True
            ).start()

    @property
    def port(self) -> int:
        return int(self.tcp.getsockname()[1])

    def close(self) -> None:
        self.tcp.close()
        self.udp.close()
        self.unix.close()
        shutil.rmtree(self.folder, ignore_errors=True)


def start_worker(
    python: str, root: Path, runtime: Path, log: Path, prefix: tuple[str, ...]
) -> tuple[host_runtime.Worker, float, Any]:
    """A worker that has listed its plugins, or an exception with nothing left running."""
    worker = host_runtime.Worker(python, root, runtime, log, prefix)
    try:
        worker.call("hello", root=str(root), timeout=30)
        listing, _ = worker.call("list", timeout=30)
    except Exception:
        worker.kill()
        raise
    return worker, (time.perf_counter() - worker.started) * 1000, listing


class Mac:
    """One scratch folder's stand-in bench, and the policies the probes share."""

    def __init__(self, scratch: Path, socket_dir: Path) -> None:
        self.scratch = scratch
        self.bench = probes.Bench(scratch)
        self.listeners = Listeners(socket_dir)
        self.outside = scratch / "outside"
        self.writable = scratch / "worker-scratch"
        for folder in (self.outside, self.writable):
            folder.mkdir(exist_ok=True)
        (self.outside / "secret.txt").write_text("secret")
        self.redact = Redactor(
            {
                "<unix-socket>": str(self.listeners.folder),
                "<scratch>": str(scratch),
                "<env>": str(scratch / "env"),
                "<runtime>": str(self.bench.runtime),
                "<root>": str(self.bench.root),
                "<spike>": str(HERE),
                "<python>": sys.base_prefix,
                "<host-env>": sys.prefix,
                "~": os.path.expanduser("~"),
            }
        )

    def worker_policy(self, **extra: Any) -> dict[str, Any]:
        """The plan's default grant for a repository's worker, on the stand-in."""
        policy: dict[str, Any] = {
            "read": [
                *confine_backend.interpreter_roots(),
                str(self.scratch / "env"),
                str(self.bench.runtime),
                str(self.bench.root),
                str(HERE),
            ],
            "write": [str(self.writable)],
            "network": "none",
        }
        return {**policy, **extra}

    def start(self, prefix: tuple[str, ...]) -> tuple[host_runtime.Worker, float]:
        bench = self.bench
        worker, ready_ms, _ = start_worker(
            bench.python, bench.root, bench.runtime, bench.log, prefix
        )
        return worker, ready_ms

    def reach_query(self) -> str:
        return (
            f"outside={self.outside / 'secret.txt'}&scratch={self.writable}"
            f"&port={self.listeners.port}"
        )

    def serve(self, prefix: tuple[str, ...], *, observe: set[int] | None = None) -> Result:
        """What one worker under *prefix* does with the stand-in's hooks."""
        try:
            worker, ready_ms = self.start(prefix)
        except Exception as exc:  # the worker never listed: the profile refused its start
            return {"did not start": type(exc).__name__, "stderr": self._log_tail()}
        if observe is not None:
            observe.add(worker.pid)
        try:
            before = len(worker.callbacks)
            result: Result = {
                "spawn_to_listed_ms": round(ready_ms, 1),
                "info": probes.call(worker, "info")[0]["status"],
                "viz-model bytes": len(
                    probes.call(worker, "viz_model", "process=specs/spec.md")[1]
                ),
                "charts on a pool log": probes.call(worker, "charts", "path=pool.jsonl")[0][
                    "status"
                ],
                "charts on an agent log": probes.call(worker, "charts", "path=agent.jsonl")[0][
                    "status"
                ],
            }
            result["host calls made"] = worker.callbacks[before:]
            if observe is None:
                result["reach"] = json.loads(probes.call(worker, "reach", self.reach_query())[1])
            result["resident MB"] = round(worker.rss_mb(), 1)
        except Exception as exc:
            result = {"failed while serving": type(exc).__name__, "stderr": self._log_tail()}
            worker.kill()
            return result
        result["exit"] = worker.close()["status"]
        return result

    def _log_tail(self) -> str:
        try:
            lines = self.bench.log.read_text().strip().splitlines()
        except OSError:
            return ""
        return self.redact(lines[-1]) if lines else ""


def backend(mac: Mac) -> Result:
    return confine_macos.probe()


def checks(mac: Mac) -> Result:
    granted, private = mac.scratch / "granted", mac.scratch / "private"
    for folder in (granted, private):
        folder.mkdir(exist_ok=True)
    (granted / "data.txt").write_text("data")
    (private / "secret.txt").write_text("secret")
    arguments = [str(granted), str(private), str(mac.writable), str(mac.listeners.port)]
    arguments += [
        str(mac.listeners.udp.getsockname()[1]),
        str(os.getpid()),
        str(mac.listeners.unix_path),
    ]
    base: dict[str, Any] = {
        "read": [*confine_backend.interpreter_roots(), str(granted)],
        "write": [str(mac.writable)],
    }
    policies: dict[str, dict[str, Any] | None] = {
        "bare": None,
        "confined": base,
        "confined, network internet": {**base, "network": "internet"},
        "confined, libinfo only": {**base, "mach": LIBINFO_SERVICES},
        "confined, network internet, libinfo and resolver services": {
            **base,
            "network": "internet",
            "mach": [*LIBINFO_SERVICES, *RESOLVER_SERVICES],
        },
        "confined, processes none": {**base, "processes": "none"},
    }
    result: Result = {}
    for label, policy in policies.items():
        before = [] if policy is None else confine_backend.prefix(policy, sys.executable)
        start = since()
        answers, pid = run_checks(before, arguments)
        result[label] = {key: mac.redact(value) for key, value in answers.items()}
        if policy is not None:
            result[label + ": the kernel's refusals"] = kernel_denials(start, {pid}, mac.redact)
    return result


def learn(mac: Mac) -> Result:
    """Observe denials while the worker runs its ordinary hooks."""
    start = since()
    pids: set[int] = set()
    served = mac.serve(tuple(confine_backend.prefix(mac.worker_policy())), observe=pids)
    return {
        "default worker": served,
        "worker denials": kernel_denials(start, pids, mac.redact),
        "log settle s": LOG_SETTLE_SECONDS,
    }


def worker(mac: Mac) -> Result:
    result: Result = {}
    runs: dict[str, tuple[str, ...]] = {
        "bare": (),
        "confined": tuple(confine_backend.prefix(mac.worker_policy())),
        "confined, network internet": tuple(
            confine_backend.prefix(mac.worker_policy(network="internet"))
        ),
    }
    for label, prefix in runs.items():
        result[label] = mac.serve(prefix)

    # The lifeline under confinement: a synchronous hook running, then the pipe closes.
    try:
        confined, _ = mac.start(runs["confined"])
        probes.ask(confined, "slow_sync", "seconds=8")
        time.sleep(0.3)
        hung_up = time.perf_counter()
        confined.hang_up()
        try:
            status = confined.wait(timeout=5)
            exit_result = {"ended": True, "exit": status}
        except subprocess.TimeoutExpired:
            confined.kill()
            exit_result = {"ended": False}
        result["a confined worker ends when its request pipe closes"] = {
            **exit_result,
            "after ms": round((time.perf_counter() - hung_up) * 1000, 1),
        }
    except Exception as exc:
        result["a confined worker ends when its request pipe closes"] = {
            "did not run": type(exc).__name__
        }
    return result


def cost(mac: Mac) -> Result:
    policy = {"read": confine_backend.interpreter_roots(), "processes": "none"}
    prefix = confine_backend.prefix(policy, sys.executable)
    worker_prefix = tuple(confine_backend.prefix(mac.worker_policy()))
    starts: dict[str, list[float]] = {"bare": [], "confined": []}
    for _ in range(9):
        for label, how in (("bare", ()), ("confined", worker_prefix)):
            try:
                started, ready_ms = mac.start(how)
            except Exception:
                continue
            started.close()
            starts[label].append(ready_ms)
    return {
        "interpreter start, bare": confine_probe.start_cost([]),
        "interpreter start, confined": confine_probe.start_cost(prefix),
        "worker spawn to listed, bare, median ms": _median(starts["bare"]),
        "worker spawn to listed, confined, median ms": _median(starts["confined"]),
    }


def _median(values: list[float]) -> float | None:
    return round(statistics.median(values), 1) if values else None


# Match the identity of the pipe. An interpreter may open a different file in that slot.
DESCRIPTOR_CHECK = """
import os, sys
fd, dev, ino = map(int, sys.argv[1:])
try:
    stat = os.fstat(fd)
except OSError:
    print("closed")
else:
    print("open" if (stat.st_dev, stat.st_ino) == (dev, ino) else "different file")
"""


def descriptors(mac: Mac) -> Result:
    """Whether the intended pipe survives exec, by each way of handing it over."""
    read, write = os.pipe()
    moved = fcntl.fcntl(read, fcntl.F_DUPFD_CLOEXEC, 10)
    identity = os.fstat(read)
    with tempfile.TemporaryFile(dir=mac.scratch) as output:

        def child_argv(prefix: list[str], fd: int) -> list[str]:
            return [
                *prefix, sys.executable, "-I", "-S", "-c", DESCRIPTOR_CHECK,
                str(fd), str(identity.st_dev), str(identity.st_ino),
            ]  # fmt: skip

        def child_sees(prefix: list[str], fd: int, actions: list[tuple[int, int, int]]) -> str:
            argv = child_argv(prefix, fd)
            output.seek(0)
            output.truncate()
            pid = os.posix_spawn(
                argv[0], argv, {"PATH": "/usr/bin:/bin"},
                file_actions=[*actions, (os.POSIX_SPAWN_DUP2, output.fileno(), 1)],
            )  # fmt: skip
            _, status = os.waitpid(pid, 0)
            if (exit_code := os.waitstatus_to_exitcode(status)) != 0:
                return f"no answer (exit {exit_code})"
            output.seek(0)
            return output.read().decode().strip()

        sandboxed = confine_backend.prefix(
            {"read": confine_backend.interpreter_roots(), "processes": "none"}, sys.executable
        )
        result: dict[str, dict[str, str]] = {}
        try:
            for label, prefix in (("bare", []), ("behind the prefix", sandboxed)):
                os.set_inheritable(read, False)
                answers = {
                    "dup2 to a different number": child_sees(
                        prefix, moved, [(os.POSIX_SPAWN_DUP2, read, moved)]
                    ),
                    "dup2 to the same number": child_sees(
                        prefix, read, [(os.POSIX_SPAWN_DUP2, read, read)]
                    ),
                    "no action, close-on-exec": child_sees(prefix, read, []),
                }
                os.set_inheritable(read, True)
                answers["no action, inheritable"] = child_sees(prefix, read, [])
                os.set_inheritable(read, False)
                done = subprocess.run(
                    child_argv(prefix, read),
                    pass_fds=(read,), capture_output=True, text=True, check=True,
                )  # fmt: skip
                answers["subprocess pass_fds"] = done.stdout.strip()
                result[label] = answers
        finally:
            for fd in (read, write, moved):
                os.close(fd)
    return result


# Runs inside an outer sandbox: can it start an inner one, and does the PDF preview's own
# probe find a backend there?
NESTED = r"""
import asyncio, json, subprocess, sys
inner = sys.argv[1]
done = subprocess.run(["/usr/bin/sandbox-exec", "-p", inner, "/usr/bin/true"], capture_output=True, text=True)
answer = {"inner sandbox-exec": "applied" if done.returncode == 0 else (done.stderr.strip().splitlines() or ["refused"])[-1]}
if sys.argv[2] == "pdf":
    from metabrowser.builtin_plugins.pdf import preview_isolation
    found = asyncio.run(preview_isolation.probe_sandbox())
    answer["the PDF preview's probe"] = "found sandbox-exec" if found else "found no backend"
print(json.dumps(answer))
"""


def nested(mac: Mac) -> Result:
    inner = confine_macos.profile({"exec": ["/usr/bin/true"], "processes": "none"})
    outers = {
        "inside an allow-default sandbox": ("(version 1)\n(allow default)", "pdf"),
        "inside the plan's worker profile": (confine_macos.profile(mac.worker_policy()), ""),
    }
    result: Result = {}
    for label, (outer, check_pdf) in outers.items():
        command = [
            "/usr/bin/sandbox-exec", "-p", outer, sys.executable, "-I", "-c", NESTED,
            inner, check_pdf,
        ]  # fmt: skip
        done = subprocess.run(command, capture_output=True, text=True, cwd="/", check=False)
        try:
            result[label] = json.loads(done.stdout)
        except json.JSONDecodeError:
            tail = done.stderr.strip().splitlines()[-1] if done.stderr.strip() else "no output"
            result[label] = {"did not run": mac.redact(tail)}
    return result


def privacy(mac: Mac, guarded: Path) -> Result:
    """A guarded file read bare, then under a profile that does not grant its folder."""
    code = "import sys\ntry:\n    open(sys.argv[1]).read(1)\n    print('allowed')\nexcept OSError as e:\n    print('refused', e.errno)"
    policy = {"read": confine_backend.interpreter_roots(), "processes": "none"}
    result: Result = {}
    for label, prefix in (
        ("bare", []),
        ("confined", confine_backend.prefix(policy, sys.executable)),
    ):
        start = since()
        command = [*prefix, sys.executable, "-I", "-S", "-c", code, str(guarded)]
        with subprocess.Popen(
            command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True
        ) as process:
            stdout, _ = communicate(process)
        result[label] = stdout.strip() or f"no answer (exit {process.returncode})"
        if prefix:
            result["confined: the kernel's refusals"] = kernel_denials(
                start, {process.pid}, mac.redact
            )
    result["note"] = "This records the sandbox denial; TCC ordering needs an app test."
    return result


def real(mac: Mac, python: str, root: str, spec: str, fixture: str) -> Result:
    """Measure the downstream hooks with the same inputs, bare and confined."""
    facts = json.loads(
        subprocess.run(
            [python, "-I", "-c", ENV_FACTS], capture_output=True, text=True, check=True
        ).stdout
    )
    redact = Redactor(
        {
            "<plugin-env>": facts["prefix"],
            "<plugin-python>": facts["base_prefix"],
            "<root>": root,
            "<fixture>": fixture,
            "<runtime>": str(mac.bench.runtime),
            "<scratch>": str(mac.scratch),
            "~": os.path.expanduser("~"),
        }
    )
    cache = mac.scratch / "real-cache"
    cache.mkdir(exist_ok=True)
    policy: dict[str, Any] = {
        "read": [
            facts["prefix"], facts["base_prefix"], *facts["editable_roots"],
            str(mac.bench.runtime), root, fixture, str(HERE),
        ],
        "write": [str(cache)],
        "network": "none",
    }  # fmt: skip
    log = mac.scratch / "run" / "real.stderr.log"
    runtime = mac.bench.runtime

    def serve(prefix: tuple[str, ...], pids: set[int]) -> Result:
        out: Result = {}
        try:
            worker, ready_ms, listing = start_worker(python, Path(root), runtime, log, prefix)
        except Exception as exc:
            return {"did not start": type(exc).__name__}
        pids.add(worker.pid)
        hooks: dict[str, str] = {}
        plugin = ""
        try:
            out["spawn_to_listed_ms"] = round(ready_ms, 1)
            out["plugins listed"] = len(listing["plugins"])
            out["errors"] = [redact(str(e)) for e in listing["errors"]]
            target = next(
                p for p in listing["plugins"] if "viz-model" in host_runtime.hooks_of(p["dir"])
            )
            hooks = host_runtime.hooks_of(target["dir"])
            plugin = target["entry_point"]

            def hook(route: str, query: str = "") -> tuple[Any, bytes]:
                return worker.call(
                    "call", sidekick=hooks[route], path=f"/api/plugin/{plugin}/{route}", query=query
                )

            info, _ = hook("info")
            viz, viz_body = hook("viz-model", urlencode({"process": spec}))
            out["info"] = info["status"]
            out["viz-model"] = {
                "status": viz["status"],
                "bytes": len(viz_body),
                "sha256": hashlib.sha256(viz_body).hexdigest(),
                "handler_ms": round(viz["handler_ms"], 1),
            }
            out["resident MB"] = round(worker.rss_mb(), 1)
            out["exit"] = worker.close()["status"]
        except Exception as exc:
            out["failed while serving"] = type(exc).__name__
            worker.kill()
        if "charts" not in hooks:
            return out
        fixture_worker = None
        try:
            fixture_worker, _, _ = start_worker(python, Path(fixture), runtime, log, prefix)
            pids.add(fixture_worker.pid)
            charts: Result = {}
            for name in ("pool.jsonl", "agent.jsonl"):
                header, body = fixture_worker.call(
                    "call",
                    sidekick=hooks["charts"],
                    path=f"/api/plugin/{plugin}/charts",
                    query=f"path={name}",
                )
                payload = json.loads(body)
                charts[name] = {
                    "status": header["status"],
                    "has summary": payload.get("summary") is not None,
                    "charts": len(payload.get("charts") or []),
                    "sha256": hashlib.sha256(body).hexdigest(),
                }
            out["charts"] = charts
            out["chart host calls"] = fixture_worker.callbacks
        except Exception as exc:
            out["charts"] = {"failed": type(exc).__name__}
        finally:
            if fixture_worker is not None:
                fixture_worker.close()
        return out

    result: Result = {"bare": serve((), set())}
    start = since()
    pids: set[int] = set()
    result["confined"] = serve(tuple(confine_backend.prefix(policy)), pids)
    result["confined: the kernel's refusals"] = kernel_denials(start, pids, redact)
    return result


# What the plugin environment's interpreter says about itself, and the source roots its
# `.pth` path lines name, which an editable install's code is read from.
ENV_FACTS = r"""
import json, os, site, sys
roots = []
for folder in site.getsitepackages():
    for name in sorted(os.listdir(folder)) if os.path.isdir(folder) else []:
        if name.endswith(".pth"):
            for line in open(os.path.join(folder, name)):
                line = line.strip()
                if line and not line.startswith(("#", "import ", "import\t")) and os.path.isdir(line):
                    roots.append(line)
print(json.dumps({"prefix": sys.prefix, "base_prefix": sys.base_prefix, "editable_roots": sorted(set(roots))}))
"""

PROBES: dict[str, Callable[[Mac], Result]] = {
    "backend": backend,
    "checks": checks,
    "learn": learn,
    "worker": worker,
    "cost": cost,
    "descriptors": descriptors,
    "nested": nested,
}


def main() -> None:
    arguments = sys.argv[1:]
    guarded: Path | None = None
    real_args: list[str] | None = None
    if "--privacy" in arguments:
        at = arguments.index("--privacy")
        guarded = Path(arguments[at + 1])
        del arguments[at : at + 2]
    if "--real" in arguments:
        at = arguments.index("--real")
        real_args = arguments[at + 1 : at + 5]
        del arguments[at : at + 5]
    if not arguments:
        raise SystemExit(__doc__)
    if sys.platform != "darwin":
        raise SystemExit(
            "macos_probe.py runs on macOS; probes.py and confine_probe.py run on Linux"
        )
    scratch = Path(arguments[0]).resolve()
    scratch.mkdir(parents=True, exist_ok=True)
    names = arguments[1:] or list(PROBES)
    socket_dir = Path(tempfile.gettempdir())
    mac = Mac(scratch, socket_dir)
    result: Result = {
        "platform": sys.platform,
        "python": sys.version.split()[0],
        "machine": os.uname().machine,
        "load_average": round(os.getloadavg()[0], 1),
    }
    try:
        for name in names:
            result[name] = PROBES[name](mac)
        if guarded is not None:
            result["privacy"] = privacy(mac, guarded)
        if real_args is not None:
            result["real"] = real(mac, *real_args)
    finally:
        mac.listeners.close()
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
