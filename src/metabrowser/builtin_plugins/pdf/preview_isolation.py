"""Where a preview may be rendered: the isolation rule of threat model T7, and its sandbox.

PDFium parses bytes a content author wrote, so a preview of an untrusted source's PDF is
rendered only in a child process the operating system confines (no network, no writes,
no new processes), and where no such confinement is available that source's card has no
image. ``docs/project/architecture/arch-threat-model.md`` (T7) states the rule and why.

- :func:`isolation_for` is the rule, as a pure function of whether the source is trusted
  and which sandbox the platform offers. Tests and goldens call it with a sandbox of
  their choosing, so its answer is the same on every platform.
- :func:`sandbox` answers which sandbox this process can use, from a probe run once:
  :func:`probe_sandbox` by default, replaced with :func:`set_sandbox_probe` by a test or a
  golden's recorder.
- :func:`macos_profile` is the confinement on macOS, a ``sandbox-exec`` profile that
  denies everything it does not allow. The probe starts the real render child under it
  and checks that it loads PDFium; ``tests/test_pdf_preview_sandbox.py`` renders under it
  and shows a write, a connection, a fork, an exec, and a read of the reader's files fail.

Linux has no sandbox here: an untrusted source's PDF gets no image there, which the
preview route answers as ``no_sandbox``.
"""

from __future__ import annotations

import asyncio
import importlib.util
import os
import sys
from collections.abc import Callable, Coroutine, Iterable
from dataclasses import dataclass
from pathlib import Path
from typing import Final, Literal

from metabrowser.builtin_plugins.pdf import render_child

# macOS's sandbox front end. Deprecated by Apple since 10.8 and still how its own tools
# confine a process; the probe finds out whether it works on this machine and version.
SANDBOX_EXEC: Final = "/usr/bin/sandbox-exec"

# How long the probe may take: the render child starting under the profile and loading
# PDFium. Measured at 0.10 to 0.16 s (12 runs, 2026-11-24, load average 87 to 105); ten
# seconds is a machine too busy to answer, which a later probe in another process asks
# again.
PROBE_DEADLINE_SECONDS: Final = 10.0

# The system's read-only locations the child reads: its libraries, the dyld shared
# cache, and the system fonts PDFium substitutes for a font a PDF names and does not
# embed. Nothing under a user's home is among them; the interpreter's own directories are
# added by `child_read_roots`.
_SYSTEM_READ_ROOTS: Final = (
    "/System",
    "/usr/lib",
    "/Library/Fonts",
    "/private/var/db/dyld",
)
# Single files the interpreter opens as it starts: the root directory it lists, and the
# devices it reads randomness from and discards output to.
_SYSTEM_READ_FILES: Final = ("/", "/dev/null", "/dev/random", "/dev/urandom")


@dataclass(frozen=True, slots=True)
class Sandbox:
    """A confinement the render child can be started under.

    *prefix* is the command that confines what follows it, such as
    ``("/usr/bin/sandbox-exec", "-p", <profile>)``; *name* says which, for logs.
    """

    name: str
    prefix: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class Isolation:
    """How one render runs: under *sandbox*, or, for a trusted source without one, bare."""

    sandbox: Sandbox | None


type Refusal = Literal["no_sandbox"]


def isolation_for(*, trusted: bool, sandbox: Sandbox | None) -> Isolation | Refusal:
    """The isolation rule of threat model T7.

    Every render runs under the sandbox when the platform has one: a trusted folder's
    PDFs lose nothing by it. Without one, a trusted folder's PDF still renders, since its
    PDFs are the reader's own, and an untrusted source's is refused.
    """

    if sandbox is not None:
        return Isolation(sandbox=sandbox)
    if trusted:
        return Isolation(sandbox=None)
    return "no_sandbox"


def _sbpl_string(text: str) -> str:
    """*text* as a sandbox profile string literal."""

    return '"' + text.replace("\\", "\\\\").replace('"', '\\"') + '"'


def child_read_roots() -> tuple[str, ...]:
    """The directories the render child reads: its interpreter's, PDFium's, and its own.

    Each is given as Python names it and as its real path, since the profile matches the
    path the kernel resolves and a virtual environment's directory links to its base
    interpreter's.
    """

    found: set[str] = {sys.prefix, sys.base_prefix, sys.exec_prefix}
    found.add(str(Path(render_child.__file__).parent))
    spec = importlib.util.find_spec("pypdfium2_raw")
    if spec is not None and spec.submodule_search_locations:
        found.update(spec.submodule_search_locations)
    return tuple(sorted(found | {os.path.realpath(root) for root in found}))


def child_executables() -> tuple[str, ...]:
    """The interpreter, as Python names it and as its real path; the profile execs only it."""

    return tuple(sorted({sys.executable, os.path.realpath(sys.executable)}))


def macos_profile(read_roots: Iterable[str], executables: Iterable[str]) -> str:
    """A ``sandbox-exec`` profile that lets the render child do its work and nothing else.

    Everything is denied but: exec of the interpreter alone (``sandbox-exec`` execs it
    after applying the profile, and no other program); metadata of any path, which the
    interpreter's path searches need and which says only whether a name exists; reading
    and mapping code from *read_roots* and the system's libraries; and reading the
    machine's settings through ``sysctl``. So no socket can be opened, no file written or
    created, no process forked, and no file read outside those directories, which keeps a
    taken-over PDFium from the reader's files. The child's pipes were opened before the
    profile applied, and stay usable.
    """

    roots = sorted(set(read_roots))
    reads = " ".join(f"(subpath {_sbpl_string(root)})" for root in [*roots, *_SYSTEM_READ_ROOTS])
    files = " ".join(f"(literal {_sbpl_string(path)})" for path in _SYSTEM_READ_FILES)
    code = " ".join(f"(subpath {_sbpl_string(root)})" for root in [*roots, "/System", "/usr/lib"])
    execs = " ".join(f"(literal {_sbpl_string(path)})" for path in sorted(set(executables)))
    return "\n".join(
        [
            "(version 1)",
            "(deny default)",
            f"(allow process-exec {execs})",
            "(allow file-read-metadata)",
            f"(allow file-read* {reads} {files})",
            f"(allow file-map-executable {code})",
            "(allow sysctl-read)",
        ]
    )


def macos_sandbox() -> Sandbox:
    """The ``sandbox-exec`` confinement for this interpreter, untested."""

    profile = macos_profile(child_read_roots(), child_executables())
    return Sandbox(name="sandbox-exec", prefix=(SANDBOX_EXEC, "-p", profile))


def child_command(isolation: Isolation, arguments: Iterable[str]) -> list[str]:
    """The render child's command line under *isolation*."""

    prefix = isolation.sandbox.prefix if isolation.sandbox is not None else ()
    return [
        *prefix,
        sys.executable,
        "-I",
        "-B",
        str(Path(render_child.__file__)),
        *arguments,
    ]


def child_environment() -> dict[str, str]:
    """A minimal environment: no inherited variable reaches the child.

    ``PYTHONDONTWRITEBYTECODE`` is set as well as ``-B``, which is what ``-I`` heeds. On
    64-bit free-threaded CPython on Linux, mimalloc can reserve a 1 GiB arena before the
    child limits its address space, so its arenas are made smaller, as the SQLite readers
    make theirs (`sqlite_readers.py`).
    """

    import sysconfig

    env = {"PATH": "/usr/bin:/bin", "LC_ALL": "C", "PYTHONDONTWRITEBYTECODE": "1"}
    if (
        sys.platform.startswith("linux")
        and sys.maxsize > 2**32
        and sysconfig.get_config_var("Py_GIL_DISABLED")
    ):
        env["MIMALLOC_ARENA_RESERVE"] = "64MiB"
    return env


async def probe_sandbox() -> Sandbox | None:
    """The sandbox this process can start the render child under, or None.

    On macOS, the render child is started under :func:`macos_profile` in its probe mode,
    which loads PDFium and answers ``ok``. Anything else (another platform, no
    ``sandbox-exec``, a profile this macOS refuses, a process that is itself sandboxed and
    may not nest another) is no sandbox.
    """

    if sys.platform != "darwin" or not os.access(SANDBOX_EXEC, os.X_OK):
        return None
    candidate = macos_sandbox()
    command = child_command(Isolation(sandbox=candidate), [render_child.PROBE_ARGUMENT])
    try:
        process = await asyncio.create_subprocess_exec(
            *command,
            stdin=asyncio.subprocess.DEVNULL,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.DEVNULL,
            cwd="/",
            env=child_environment(),
            start_new_session=True,
        )
    except OSError:
        return None
    try:
        async with asyncio.timeout(PROBE_DEADLINE_SECONDS):
            out = await process.stdout.read(64) if process.stdout is not None else b""
            code = await process.wait()
    except TimeoutError:
        return None
    finally:
        if process.returncode is None:
            kill_group(process.pid)
            await process.wait()
    return candidate if code == 0 and out == render_child.PROBE_ANSWER else None


def kill_group(pid: int) -> None:
    """Kill the session *pid* leads, so nothing it started outlives it."""

    import signal

    try:
        os.killpg(pid, signal.SIGKILL)
    except (ProcessLookupError, PermissionError):
        return


type SandboxProbe = Callable[[], Coroutine[object, object, Sandbox | None]]

_probe: SandboxProbe = probe_sandbox
_probed: asyncio.Future[Sandbox | None] | None = None
_probed_loop: asyncio.AbstractEventLoop | None = None


def set_sandbox_probe(probe: SandboxProbe | None) -> None:
    """Replace the probe, or restore the default with None, and forget its answer.

    A golden's recorder passes one that answers no sandbox, so its transcript is the same
    on macOS and Linux.
    """

    global _probe, _probed, _probed_loop
    _probe = probe if probe is not None else probe_sandbox
    _probed = None
    _probed_loop = None


async def sandbox() -> Sandbox | None:
    """The probe's answer, asked once per event loop and shared by concurrent callers."""

    global _probed, _probed_loop
    loop = asyncio.get_running_loop()
    if _probed is None or _probed_loop is not loop:
        _probed_loop = loop
        _probed = loop.create_task(_probe())
    return await asyncio.shield(_probed)


__all__ = [
    "Isolation",
    "Refusal",
    "Sandbox",
    "SandboxProbe",
    "child_command",
    "child_environment",
    "isolation_for",
    "kill_group",
    "macos_profile",
    "probe_sandbox",
    "sandbox",
    "set_sandbox_probe",
]
