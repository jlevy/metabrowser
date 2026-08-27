"""Bounded ``git`` subprocess execution.

The single place in the package that spawns a process. Every
``/api/git/`` handler runs on a request path, so each invocation is
bounded on both axes that can hurt the server: wall clock, and how much
output we are willing to buffer.

Three properties are deliberate:

* **Fixed argument vectors, never a shell.** Callers pass a list; nothing
  is interpolated into a command string. Combined with the revision
  validation in :mod:`metabrowser.git.wire`, a caller-supplied value can
  never become an option or a second command.
* **Incremental capped reads.** ``communicate()`` would buffer the whole
  stream before any size check could run, so a pathological repository
  would already have cost the memory by the time we noticed. Reading in
  chunks lets the cap fire while the output is still small.
* **stderr never reaches the client.** Git writes absolute local paths
  into its error text. It is logged and dropped; the caller gets a typed
  error instead.
"""

from __future__ import annotations

import asyncio
import contextlib
import logging
import os
import shutil
from collections.abc import Sequence
from functools import cache
from pathlib import Path

from metabrowser.settings import GIT_SUBPROCESS_MAX_BYTES, GIT_SUBPROCESS_TIMEOUT_S

log = logging.getLogger(__name__)

# Read granularity for the capped stdout drain. Large enough that a big
# log page is a handful of reads, small enough that the cap check fires
# well before the process can hand us an unbounded buffer.
_READ_CHUNK_BYTES = 64 * 1024

# stderr is only ever logged, so it needs far less headroom than stdout.
# Git diagnostics are a few lines; anything beyond this is truncated.
_STDERR_MAX_BYTES = 64 * 1024

# Options applied to every invocation, before the subcommand:
#
# ``--no-optional-locks`` keeps a read from taking the index lock, so
# browsing history cannot contend with a git command the user is running
# in a terminal on the same repository.
#
# ``core.quotepath=false`` makes git emit UTF-8 paths directly instead of
# octal-escaping every non-ASCII byte, which would otherwise have to be
# unescaped in each parser.
GIT_COMMON_ARGS: tuple[str, ...] = ("--no-optional-locks", "-c", "core.quotepath=false")


class GitError(Exception):
    """Base for every failure this package reports.

    Route handlers catch this one type and convert it to a response.
    Subclasses exist so callers that can act on a specific failure
    (``GitUnavailableError`` in particular, which decides whether the Git
    tab appears at all) do not have to inspect messages.
    """


class GitUnavailableError(GitError):
    """No usable ``git`` executable on ``PATH``.

    Not an error condition for the user: the Git tab is simply hidden,
    exactly as it is outside a repository.
    """


class GitCommandError(GitError):
    """``git`` exited non-zero.

    ``stderr_summary`` is retained for logging only. It is never placed in
    a response body: git error text routinely contains absolute local
    paths.
    """

    def __init__(self, args: Sequence[str], returncode: int, stderr_summary: str) -> None:
        super().__init__(f"git {' '.join(args)} exited {returncode}")
        self.args_used: tuple[str, ...] = tuple(args)
        self.returncode: int = returncode
        self.stderr_summary: str = stderr_summary


class GitTimeoutError(GitError):
    """``git`` exceeded :data:`GIT_SUBPROCESS_TIMEOUT_S` and was killed."""


class GitOutputTooLargeError(GitError):
    """``git`` produced more than :data:`GIT_SUBPROCESS_MAX_BYTES` on stdout."""


def failure_detail(exc: GitError) -> str:
    """Log text for a git failure, including git's own stderr.

    Separate from ``str(exc)`` so the stderr text — which routinely
    carries absolute local paths — reaches a log line and only a log
    line. A caller that puts an exception message into a response body
    still gets the path-free form.
    """
    summary = getattr(exc, "stderr_summary", "")
    return f"{exc}: {summary}" if summary else str(exc)


@cache
def git_executable() -> str | None:
    """Absolute path to ``git``, or ``None`` when it is not installed.

    Cached for the process lifetime. A ``git`` that appears on ``PATH``
    after startup will not be picked up until restart, which is the right
    trade for a lookup on every history request.
    """
    return shutil.which("git")


# Environment variables that pin git to a specific repository, index, or
# object store. Git exports several of these to hook processes (GIT_DIR
# in particular), and they take precedence over ``cwd``. Inherited into
# our children they would silently redirect every command at whatever
# repository the parent hook was running in — observed concretely as a
# fixture ``git init`` re-initializing the *served* repository as bare
# from inside a pre-push hook. Every spawn scrubs them so the repository
# is always the one resolved from ``cwd``.
_REPO_PINNING_GIT_VARS: tuple[str, ...] = (
    "GIT_DIR",
    "GIT_WORK_TREE",
    "GIT_INDEX_FILE",
    "GIT_COMMON_DIR",
    "GIT_OBJECT_DIRECTORY",
    "GIT_ALTERNATE_OBJECT_DIRECTORIES",
    "GIT_PREFIX",
    "GIT_NAMESPACE",
    "GIT_CEILING_DIRECTORIES",
)


def git_environment() -> dict[str, str]:
    """Environment for a git child process.

    Strips the repository-pinning variables above, then:

    ``GIT_OPTIONAL_LOCKS=0`` is the environment form of
    ``--no-optional-locks`` and covers any git subprocess spawned in turn.
    ``GIT_TERMINAL_PROMPT=0`` and the empty askpass settings guarantee a
    repository needing credentials fails fast instead of blocking the
    request on a prompt that has no terminal to appear on.
    """
    env = dict(os.environ)
    for name in _REPO_PINNING_GIT_VARS:
        env.pop(name, None)
    env["GIT_OPTIONAL_LOCKS"] = "0"
    env["GIT_TERMINAL_PROMPT"] = "0"
    env["GIT_ASKPASS"] = ""
    env["SSH_ASKPASS"] = ""
    return env


async def _read_capped(stream: asyncio.StreamReader | None, max_bytes: int) -> tuple[bytes, bool]:
    """Drain *stream*, stopping once *max_bytes* have been read.

    Returns ``(data, overflowed)``. Draining continues past the cap
    without retaining the excess: a producer blocked on a full pipe would
    never exit, and the caller needs the process to finish so it can be
    reaped.
    """
    if stream is None:
        return b"", False

    chunks: list[bytes] = []
    total = 0
    overflowed = False
    while True:
        chunk = await stream.read(_READ_CHUNK_BYTES)
        if not chunk:
            break
        total += len(chunk)
        if total > max_bytes:
            overflowed = True
            continue
        chunks.append(chunk)
    return b"".join(chunks), overflowed


async def run_git(
    args: Sequence[str],
    *,
    cwd: Path,
    timeout_s: float = GIT_SUBPROCESS_TIMEOUT_S,
    max_bytes: int = GIT_SUBPROCESS_MAX_BYTES,
) -> bytes:
    """Run ``git`` with *args* in *cwd* and return raw stdout.

    Bytes, not text: git emits path names as raw bytes in whatever
    encoding the filesystem uses, and the record separators the parsers
    rely on are byte-oriented. Decoding is the parsers' job, where they
    can choose the right granularity and error policy.

    Raises :class:`GitUnavailableError`, :class:`GitTimeoutError`,
    :class:`GitOutputTooLargeError`, or :class:`GitCommandError`.
    """
    proc = await spawn_git_process(args, cwd=cwd)

    # stdout and stderr are drained concurrently. Reading them in
    # sequence deadlocks as soon as git fills the pipe we are not
    # reading, which a repository with a lot of output will do.
    stdout_task = asyncio.ensure_future(_read_capped(proc.stdout, max_bytes))
    stderr_task = asyncio.ensure_future(_read_capped(proc.stderr, _STDERR_MAX_BYTES))
    try:
        (stdout, overflowed), (stderr, _), returncode = await asyncio.wait_for(
            asyncio.gather(stdout_task, stderr_task, proc.wait()),
            timeout=timeout_s,
        )
    except TimeoutError:
        stdout_task.cancel()
        stderr_task.cancel()
        await terminate_git_process(proc)
        raise GitTimeoutError(
            f"git {' '.join(args)} exceeded {timeout_s:g}s and was terminated"
        ) from None
    except asyncio.CancelledError:
        # A genuine cancellation — the client disconnected, or the server
        # is shutting down. Reap the child so it cannot outlive the
        # request, then let the cancellation continue to propagate;
        # converting it to a GitError would swallow the shutdown signal.
        stdout_task.cancel()
        stderr_task.cancel()
        await terminate_git_process(proc)
        raise

    if overflowed:
        raise GitOutputTooLargeError(
            f"git {' '.join(args)} produced more than {max_bytes} bytes on stdout"
        )

    if returncode != 0:
        stderr_summary = stderr.decode("utf-8", errors="replace").strip()
        # DEBUG, because a non-zero exit is a result this layer hands back,
        # not an event it can rank. Most of them are deliberate probes:
        # discovery asks whether the served root is a repository at all,
        # HEAD resolution distinguishes detached from unborn by exit code,
        # and the history scope tries every candidate ref and keeps the ones
        # that resolve. Ranking each of those as INFO put a line in the
        # terminal every few seconds for anyone browsing a directory that is
        # not a repository. Callers that treat a failure as a failure log it
        # themselves, with :func:`failure_detail` for this same text.
        log.debug("git %s exited %s: %s", " ".join(args), returncode, stderr_summary)
        raise GitCommandError(args, returncode, stderr_summary)

    return stdout


async def spawn_git_process(
    args: Sequence[str],
    *,
    cwd: Path,
    pipe_stdin: bool = False,
) -> asyncio.subprocess.Process:
    """Start a sanitized Git process whose streams the caller owns.

    Long-lived streaming consumers cannot use :func:`run_git`, which
    drains and buffers a complete command. They still use this seam so
    executable lookup, environment isolation, fixed arguments, and
    spawn-failure translation remain identical to ordinary requests.
    ``pipe_stdin`` is reserved for bounded, validated input such as a
    resolved history scope.
    """
    exe = git_executable()
    if exe is None:
        raise GitUnavailableError("git executable not found on PATH")

    argv = (exe, *GIT_COMMON_ARGS, *args)
    try:
        return await asyncio.create_subprocess_exec(
            *argv,
            cwd=cwd,
            stdin=asyncio.subprocess.PIPE if pipe_stdin else None,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            env=git_environment(),
        )
    except OSError as exc:
        # Spawn itself failed — a missing cwd, a permissions problem, or
        # process-table exhaustion. Nothing downstream can distinguish
        # these usefully, so they collapse into one typed failure.
        raise GitUnavailableError(f"could not run git: {exc}") from exc


async def terminate_git_process(proc: asyncio.subprocess.Process) -> None:
    """Kill *proc* and reap it, so a timeout cannot leak a child.

    ``proc.wait()`` after ``kill()`` is what actually reaps; skipping it
    leaves a zombie for the lifetime of the server.
    """
    if proc.returncode is not None:
        return
    # The process may exit between the returncode check and the signal.
    with contextlib.suppress(ProcessLookupError):
        proc.kill()
    # The request may be cancelled again while reaping. The child is
    # already signalled by then, and re-raising here would replace the
    # original failure with a cancellation from the cleanup path.
    with contextlib.suppress(asyncio.CancelledError):
        await proc.wait()


__all__ = [
    "GitCommandError",
    "GitError",
    "GitOutputTooLargeError",
    "GitTimeoutError",
    "GitUnavailableError",
    "failure_detail",
    "git_executable",
    "spawn_git_process",
    "terminate_git_process",
    "run_git",
]
