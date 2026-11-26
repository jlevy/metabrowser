"""Spike: the macOS half of Key Decision 11 (``mb-gmut``), run on a Mac.

Runs with the host Metabrowser's interpreter on macOS. It answers what the Linux probes
answered for Landlock and seccomp, for ``sandbox-exec`` with a profile from
``confine_macos.py``, and the questions only macOS has:

- ``backend``: the macOS version, and whether ``sandbox-exec`` applies a deny-default
  profile here.
- ``checks``: one checking program bare and under four policies (the default; the
  internet granted; programs refused; the default plus the Mach services ``getpwuid``
  and the resolver use), as ``confine_probe.py`` does on Linux.
- ``learn``: the stand-in plugin's worker under the default profile, with the kernel's
  report of every refusal read from the unified log, then again with those refusals
  granted, until the worker serves its hooks or nothing new is refused. The grants it
  had to add are the finding: whether a full Python environment's worker still reads as
  confined.
- ``worker``: the stand-in's worker bare, confined with the default grants and what
  ``learn`` added, and confined with the internet granted, and what a hook can reach in
  each; whether a confined worker ends when its request pipe closes.
- ``cost``: what the prefix adds to an interpreter's start and to a worker's.
- ``descriptors``: whether a descriptor the host hands over survives ``posix_spawn``'s
  same-number ``dup2`` and ``sandbox-exec``'s exec.
- ``nested``: whether ``sandbox-exec`` and the PDF preview's own probe work inside an
  outer sandbox, as a server an agent starts would be.
- ``privacy``, only with ``--privacy FILE``: a file in a folder macOS's privacy controls
  guard, such as ``~/Documents``, read bare and under a profile that does not grant it.
  The profile should refuse it before any privacy prompt; watch for one.
- ``real``, only with ``--real PLUGIN_PYTHON ROOT SPEC FIXTURE_DIR``: the downstream
  plugins, which are not public, bare and confined, with the grants learned for them.
  The arguments are ``host_runtime.py``'s.

Usage: macos_probe.py SCRATCH_DIR [PROBE ...] [--privacy FILE] [--real PY ROOT SPEC FIX]

Prints JSON that names no path: paths in the kernel's reports are given relative to the
roots the probe knows (``<env>``, ``<python>``, ``~``, and so on).
"""

from __future__ import annotations

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
LEARN_ROUNDS = 5

# The checking program. It answers by what happened, never by a path.
CHECKS = r"""
import asyncio, errno, json, multiprocessing.synchronize, os, pwd, socket, subprocess, sys, threading
granted, private, writable, port, parent, unix_path = sys.argv[1:7]

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


def kernel_reports(start: str, pids: set[int] | None = None) -> list[dict[str, str]]:
    """The sandbox reports since *start*, for *pids* or any Python process."""
    time.sleep(LOG_SETTLE_SECONDS)
    command = [
        "log", "show", "--start", start, "--style", "syslog",
        "--predicate", 'eventMessage CONTAINS "Sandbox: "',
    ]  # fmt: skip
    done = subprocess.run(command, capture_output=True, text=True, check=False)
    found: list[dict[str, str]] = []
    for line in done.stdout.splitlines():
        match = REPORT.search(line)
        if match is None:
            continue
        pid = int(match["pid"])
        if pids is not None and pid not in pids and not match["process"].startswith("python"):
            continue
        found.append({key: value or "" for key, value in match.groupdict().items()})
    return found


def grant_for(report: dict[str, str]) -> str | None:
    """The rule that would allow what *report* records, as narrowly as it can be said."""
    operation, argument = report["operation"], report["argument"].strip()
    if operation == "mach-lookup" and argument:
        return f"(allow mach-lookup (global-name {confine_macos.sbpl_string(argument)}))"
    if operation.startswith(("file-", "process-exec")) and argument.startswith("/"):
        return f"(allow {operation} (literal {confine_macos.sbpl_string(argument)}))"
    if operation.startswith(("sysctl", "ipc-", "iokit-", "user-preference", "system-")):
        return f"(allow {operation})"
    if operation.startswith("network") and argument.startswith("/"):
        return f"(allow {operation} (literal {confine_macos.sbpl_string(argument)}))"
    return None


def run_checks(before: list[str], arguments: list[str]) -> dict[str, str]:
    command = [*before, sys.executable, "-I", "-S", "-c", CHECKS, *arguments]
    done = subprocess.run(command, capture_output=True, text=True, cwd="/", check=False)
    if done.returncode != 0:
        tail = done.stderr.strip().splitlines()[-1] if done.stderr.strip() else "no output"
        return {"did not run": tail}
    answers: dict[str, str] = json.loads(done.stdout)
    return answers


class Listeners:
    """A TCP listener and a Unix socket outside every grant, as an agent socket would be."""

    def __init__(self) -> None:
        self.tcp = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.tcp.bind(("127.0.0.1", 0))
        self.tcp.listen(8)
        # A Unix socket's path is at most 104 bytes on macOS: a short folder of its own.
        self.folder = Path(tempfile.mkdtemp(prefix="mb-probe-", dir="/tmp"))
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

    def __init__(self, scratch: Path) -> None:
        self.scratch = scratch
        self.bench = probes.Bench(scratch)
        self.listeners = Listeners()
        self.outside = scratch / "outside"
        self.writable = scratch / "worker-scratch"
        for folder in (self.outside, self.writable):
            folder.mkdir(exist_ok=True)
        (self.outside / "secret.txt").write_text("secret")
        self.learned: list[str] = []
        self.redact = Redactor(
            {
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
            "sbpl": list(self.learned),
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

    def serve(self, prefix: tuple[str, ...]) -> Result:
        """What one worker under *prefix* does with the stand-in's hooks."""
        try:
            worker, ready_ms = self.start(prefix)
        except Exception as exc:  # the worker never listed: the profile refused its start
            return {"did not start": type(exc).__name__, "stderr": self._log_tail()}
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
    arguments += [str(os.getpid()), str(mac.listeners.unix_path)]
    base: dict[str, Any] = {
        "read": [*confine_backend.interpreter_roots(), str(granted)],
        "write": [str(mac.writable)],
    }
    services = [*LIBINFO_SERVICES, *RESOLVER_SERVICES]
    policies: dict[str, dict[str, Any] | None] = {
        "bare": None,
        "confined": base,
        "confined, network internet": {**base, "network": "internet"},
        "confined, network internet, libinfo and resolver services": {
            **base,
            "network": "internet",
            "mach": services,
        },
        "confined, processes none": {**base, "processes": "none"},
    }
    result: Result = {}
    for label, policy in policies.items():
        before = [] if policy is None else confine_backend.prefix(policy, sys.executable)
        start = since()
        result[label] = run_checks(before, arguments)
        if policy is not None:
            refused = {
                f"{report['operation']} {mac.redact(report['argument'])}".strip()
                for report in kernel_reports(start)
                if report["verdict"] == "deny"
            }
            result[label + ": the kernel's refusals"] = sorted(refused)
    return result


def learn(mac: Mac) -> Result:
    """Grant what the kernel reports refusing, round by round, until the worker serves."""
    rounds: list[Result] = []
    for _ in range(LEARN_ROUNDS):
        start = since()
        served = mac.serve(tuple(confine_backend.prefix(mac.worker_policy())))
        reports = [r for r in kernel_reports(start) if r["verdict"] == "deny"]
        new = sorted({g for r in reports if (g := grant_for(r)) and g not in mac.learned})
        unexpressed = sorted(
            {
                f"{r['operation']} {mac.redact(r['argument'])}".strip()
                for r in reports
                if not grant_for(r)
            }
        )
        working = "info" in served and served.get("charts on an agent log") == 200
        rounds.append(
            {
                "worker served its hooks": working,
                "refusals": len(reports),
                "grants added": [mac.redact(grant) for grant in new],
                "refusals no grant was made for": unexpressed,
            }
        )
        # A refusal the stand-in's reach hook asks for on purpose is not a need.
        new = [g for g in new if not _is_probe_target(g, mac)]
        if working or not new:
            break
        mac.learned.extend(new)

    # The same run traced: every refusal becomes a reported allowance, so this lists
    # what the default grants left out even where a refusal was handled quietly.
    start = since()
    mac.serve(tuple(confine_backend.prefix(mac.worker_policy(trace=True))))
    traced = {
        f"{r['operation']} {mac.redact(r['argument'])}".strip()
        for r in kernel_reports(start)
        if r["verdict"] == "allow"
    }
    return {
        "rounds": rounds,
        "learned grants in all": [mac.redact(grant) for grant in mac.learned],
        "traced allowances beyond the grants": sorted(traced),
        "log settle s": LOG_SETTLE_SECONDS,
    }


def _is_probe_target(grant: str, mac: Mac) -> bool:
    return any(str(path) in grant for path in (mac.outside, mac.listeners.folder))


def worker(mac: Mac) -> Result:
    result: Result = {"learned grants used": len(mac.learned)}
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
        deadline = hung_up + 5
        while probes.alive(confined.pid) and time.perf_counter() < deadline:
            time.sleep(0.01)
        ended = not probes.alive(confined.pid)
        result["a confined worker ends when its request pipe closes"] = {
            "ended": ended,
            "after ms": round((time.perf_counter() - hung_up) * 1000, 1),
        }
        if not ended:
            confined.kill()
        os.waitpid(confined.pid, 0)
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


# The child reports whether each descriptor it was told about is open.
DESCRIPTOR_CHECK = "import os, sys; print(','.join(str(int(_open(int(n)))) for n in sys.argv[1:]))"
DESCRIPTOR_PRELUDE = "def _open(n):\n    try:\n        os.fstat(n)\n        return True\n    except OSError:\n        return False\n"


def descriptors(mac: Mac) -> Result:
    """Whether a pipe the host hands over is open in the child, by each way of handing it."""
    code = "import os, sys\n" + DESCRIPTOR_PRELUDE + DESCRIPTOR_CHECK.split("; ", 1)[1]

    def child_sees(prefix: list[str], fd: int, actions: list[tuple[Any, ...]]) -> str:
        argv = [*prefix, sys.executable, "-I", "-S", "-c", code, str(fd)]
        out_read, out_write = os.pipe()
        pid = os.posix_spawn(
            argv[0], argv, {"PATH": "/usr/bin:/bin"},
            file_actions=[*actions, (os.POSIX_SPAWN_DUP2, out_write, 1)],
        )  # fmt: skip
        os.close(out_write)
        with os.fdopen(out_read) as handle:
            answer = handle.read().strip()
        os.waitpid(pid, 0)
        return {"1": "open", "0": "closed"}.get(answer, f"no answer ({answer!r})")

    sandboxed = confine_backend.prefix(
        {"read": confine_backend.interpreter_roots(), "processes": "none"}, sys.executable
    )
    result: Result = {}
    for label, prefix in (("bare", []), ("behind the prefix", sandboxed)):
        read, write = os.pipe()  # both close-on-exec, as os.pipe makes them
        moved = 9
        result[label] = {
            "dup2 to a different number": child_sees(
                prefix, moved, [(os.POSIX_SPAWN_DUP2, read, moved)]
            ),
            "dup2 to the same number": child_sees(
                prefix, read, [(os.POSIX_SPAWN_DUP2, read, read)]
            ),
            "no action, close-on-exec": child_sees(prefix, read, []),
        }
        os.set_inheritable(read, True)
        result[label]["no action, inheritable"] = child_sees(prefix, read, [])
        os.close(read)
        os.close(write)
    read, write = os.pipe()
    done = subprocess.run(
        [*sandboxed, sys.executable, "-I", "-S", "-c", code, str(read)],
        pass_fds=(read,), capture_output=True, text=True, check=False,
    )  # fmt: skip
    result["subprocess pass_fds, behind the prefix"] = {"1": "open", "0": "closed"}.get(
        done.stdout.strip(), "no answer"
    )
    os.close(read)
    os.close(write)
    return result


# Runs inside an outer sandbox: can it start an inner one, and does the PDF preview's own
# probe find a backend there?
NESTED = r"""
import asyncio, json, subprocess, sys
inner = sys.argv[1]
done = subprocess.run(["/usr/bin/sandbox-exec", "-p", inner, "/usr/bin/true"], capture_output=True, text=True)
answer = {"inner sandbox-exec": "applied" if done.returncode == 0 else (done.stderr.strip().splitlines() or ["refused"])[-1]}
try:
    from metabrowser.builtin_plugins.pdf import preview_isolation
    found = asyncio.run(preview_isolation.probe_sandbox())
    answer["the PDF preview's probe"] = "found sandbox-exec" if found else "found no backend"
except Exception as exc:
    answer["the PDF preview's probe"] = f"did not run ({type(exc).__name__})"
print(json.dumps(answer))
"""


def nested(mac: Mac) -> Result:
    inner = confine_macos.profile({"exec": ["/usr/bin/true"], "processes": "none"})
    outers = {
        "inside an allow-default sandbox": "(version 1)\n(allow default)",
        "inside the plan's worker profile": confine_macos.profile(
            {**mac.worker_policy(), "read": [*mac.worker_policy()["read"], sys.prefix]}
        ),
    }
    result: Result = {}
    for label, outer in outers.items():
        command = ["/usr/bin/sandbox-exec", "-p", outer, sys.executable, "-I", "-c", NESTED, inner]
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
        done = subprocess.run(
            [*prefix, sys.executable, "-I", "-S", "-c", code, str(guarded)],
            capture_output=True, text=True, check=False,
        )  # fmt: skip
        result[label] = done.stdout.strip() or "no answer"
        if prefix:
            result["confined: the kernel's refusals"] = sorted(
                {f"{r['operation']} {mac.redact(r['argument'])}" for r in kernel_reports(start)}
            )
    result["note"] = "A privacy prompt during the confined read would mean the check came first."
    return result


def real(mac: Mac, python: str, root: str, spec: str, fixture: str) -> Result:
    """The downstream plugins in a worker, bare and confined, with grants learned for them."""
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
        "sbpl": [],
    }  # fmt: skip
    log = mac.scratch / "run" / "real.stderr.log"
    runtime = mac.bench.runtime

    def serve(prefix: tuple[str, ...]) -> Result:
        out: Result = {}
        try:
            worker, ready_ms, listing = start_worker(python, Path(root), runtime, log, prefix)
        except Exception as exc:
            return {"did not start": type(exc).__name__}
        hooks: dict[str, str] = {}
        plugin = ""
        try:
            out["spawn_to_listed_ms"] = round(ready_ms, 1)
            out["plugins"] = [p["entry_point"] for p in listing["plugins"]]
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
            viz, viz_body = hook("viz-model", f"process={spec}")
            out["info"] = info["status"]
            out["viz-model"] = {
                "status": viz["status"],
                "bytes": len(viz_body),
                "handler_ms": viz.get("handler_ms"),
            }
            out["resident MB"] = round(worker.rss_mb(), 1)
            out["exit"] = worker.close()["status"]
        except Exception as exc:
            out["failed while serving"] = type(exc).__name__
            worker.kill()
        if "charts" not in hooks:
            return out
        try:
            fixture_worker, _, _ = start_worker(python, Path(fixture), runtime, log, prefix)
            charts: Result = {}
            for name in ("pool.jsonl", "agent.jsonl"):
                header, body = fixture_worker.call(
                    "call",
                    sidekick=hooks["charts"],
                    path=f"/api/plugin/{plugin}/charts",
                    query=f"path={name}",
                )
                charts[name] = {
                    "status": header["status"],
                    "charts": len(json.loads(body).get("charts") or []),
                }
            out["charts"] = charts
            fixture_worker.close()
        except Exception as exc:
            out["charts"] = {"failed": type(exc).__name__}
        return out

    result: Result = {"bare": serve(())}
    rounds: list[Result] = []
    for _ in range(LEARN_ROUNDS):
        start = since()
        served = serve(tuple(confine_backend.prefix(policy)))
        reports = [r for r in kernel_reports(start) if r["verdict"] == "deny"]
        new = sorted({g for r in reports if (g := grant_for(r)) and g not in policy["sbpl"]})
        rounds.append({"served": served, "grants added": [redact(g) for g in new]})
        if served.get("info") == 200 or not new:
            break
        policy["sbpl"].extend(new)
    start = since()
    serve(tuple(confine_backend.prefix({**policy, "trace": True})))
    result["confined rounds"] = rounds
    result["learned grants in all"] = [redact(g) for g in policy["sbpl"]]
    result["traced allowances beyond the grants"] = sorted(
        {
            f"{r['operation']} {redact(r['argument'])}".strip()
            for r in kernel_reports(start)
            if r["verdict"] == "allow"
        }
    )
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
    mac = Mac(scratch)
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
