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

Acquisition reuses this runner. Named policies add ``stdin=DEVNULL``,
umask ``077``, isolated Git configuration, and ``GIT_NO_LAZY_FETCH``;
``GitCommandTarget`` becomes ``--git-dir`` / ``--work-tree`` arguments
rather than environment overrides. Version detection lives here so the
acquisition floor has one parser.
"""

from __future__ import annotations

import asyncio
import contextlib
import logging
import os
import re
import shutil
import subprocess
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from functools import cache
from pathlib import Path
from typing import Final, Literal

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

# Acquisition has no measured low-speed stall bound yet (plan Phase 1B-a).
# This wall-clock cap is only so a forgotten child cannot live forever; user
# cancellation is the product guard. The 900s value is the measurement-harness
# timeout in explorations/repository-cache/measure.py.
GIT_ACQUISITION_TIMEOUT_S: Final[float] = 900.0

# Acquisition security floor, frozen in git-version-gates.json. A version on a
# listed track must meet that track's patched release; a newer track must be at
# least newest_patched. Unparseable output is below every floor.
ACQUISITION_MINIMUM: Final[tuple[int, int, int]] = (2, 43, 7)
ACQUISITION_PATCHED_TRACKS: Final[dict[str, tuple[int, int, int]]] = {
    "2.43": (2, 43, 7),
    "2.44": (2, 44, 4),
    "2.45": (2, 45, 4),
    "2.46": (2, 46, 4),
    "2.47": (2, 47, 3),
    "2.48": (2, 48, 2),
    "2.49": (2, 49, 1),
    "2.50": (2, 50, 1),
}
ACQUISITION_NEWEST_PATCHED: Final[tuple[int, int, int]] = (2, 50, 1)
_GIT_VERSION = re.compile(r"^git version (\d+)\.(\d+)(?:\.(\d+))?")


@dataclass(frozen=True, slots=True)
class GitProcessPolicy:
    """Named bounds and isolation for one family of Git spawns."""

    name: str
    timeout_s: float
    max_bytes: int
    stdin: Literal["inherit", "devnull", "pipe"]
    child_umask: int | None
    isolate_user_config: bool
    no_lazy_fetch: bool
    ssh_batch: bool = False
    extra_env: Mapping[str, str] | None = None


READ_POLICY: Final[GitProcessPolicy] = GitProcessPolicy(
    name="read",
    timeout_s=GIT_SUBPROCESS_TIMEOUT_S,
    max_bytes=GIT_SUBPROCESS_MAX_BYTES,
    stdin="inherit",
    child_umask=None,
    isolate_user_config=False,
    no_lazy_fetch=False,
)
ACQUISITION_POLICY: Final[GitProcessPolicy] = GitProcessPolicy(
    name="acquisition",
    timeout_s=GIT_ACQUISITION_TIMEOUT_S,
    max_bytes=GIT_SUBPROCESS_MAX_BYTES,
    stdin="devnull",
    child_umask=0o077,
    isolate_user_config=True,
    no_lazy_fetch=True,
    ssh_batch=True,
    extra_env={"GCM_INTERACTIVE": "never", "LC_ALL": "C"},
)
FETCH_POLICY: Final[GitProcessPolicy] = GitProcessPolicy(
    name="fetch",
    timeout_s=GIT_ACQUISITION_TIMEOUT_S,
    max_bytes=GIT_SUBPROCESS_MAX_BYTES,
    stdin="devnull",
    child_umask=0o077,
    isolate_user_config=True,
    no_lazy_fetch=True,
    ssh_batch=True,
    extra_env={"GCM_INTERACTIVE": "never", "LC_ALL": "C"},
)
BATCH_OBJECT_POLICY: Final[GitProcessPolicy] = GitProcessPolicy(
    name="batch-object",
    timeout_s=GIT_SUBPROCESS_TIMEOUT_S,
    max_bytes=GIT_SUBPROCESS_MAX_BYTES,
    stdin="pipe",
    child_umask=0o077,
    isolate_user_config=True,
    no_lazy_fetch=True,
)


@dataclass(frozen=True, slots=True)
class AttachedWorktreeTarget:
    """A trusted worktree plus Git directory. Construct with the factory."""

    worktree: Path
    git_dir: Path


@dataclass(frozen=True, slots=True)
class RepositoryStoreTarget:
    """A trusted worktree-free Git directory. Construct with the factory."""

    git_dir: Path


type GitCommandTarget = AttachedWorktreeTarget | RepositoryStoreTarget


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


class UnsupportedGitVersionError(GitError):
    """The installed Git is below the acquisition security floor."""

    def __init__(self, detected: str, required: str) -> None:
        super().__init__(
            f"unsupported Git version ({detected or 'unparseable'}); "
            f"acquisition requires {required}"
        )
        self.detected = detected
        self.required = required


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


def git_environment(policy: GitProcessPolicy | None = None) -> dict[str, str]:
    """Environment for a git child process.

    Strips the repository-pinning variables above, then:

    ``GIT_OPTIONAL_LOCKS=0`` is the environment form of
    ``--no-optional-locks`` and covers any git subprocess spawned in turn.
    ``GIT_TERMINAL_PROMPT=0`` and the empty askpass settings guarantee a
    repository needing credentials fails fast instead of blocking the
    request on a prompt that has no terminal to appear on.

    An acquisition, fetch, or batch-object policy also isolates user and
    system Git configuration, disables implicit lazy fetch, and can force
    SSH batch mode. Those extras are not applied to ordinary local reads.
    """
    env = dict(os.environ)
    for name in _REPO_PINNING_GIT_VARS:
        env.pop(name, None)
    env["GIT_OPTIONAL_LOCKS"] = "0"
    env["GIT_TERMINAL_PROMPT"] = "0"
    env["GIT_ASKPASS"] = ""
    env["SSH_ASKPASS"] = ""
    if policy is not None:
        if policy.isolate_user_config:
            env["GIT_CONFIG_GLOBAL"] = os.devnull
            env["GIT_CONFIG_NOSYSTEM"] = "1"
        if policy.no_lazy_fetch:
            env["GIT_NO_LAZY_FETCH"] = "1"
        if policy.ssh_batch:
            env["GIT_SSH_COMMAND"] = "ssh -oBatchMode=yes"
        if policy.extra_env:
            env.update(policy.extra_env)
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
    cwd: Path | None = None,
    target: GitCommandTarget | None = None,
    policy: GitProcessPolicy | None = None,
    timeout_s: float | None = None,
    max_bytes: int | None = None,
) -> bytes:
    """Run ``git`` with *args* in *cwd* and return raw stdout.

    Bytes, not text: git emits path names as raw bytes in whatever
    encoding the filesystem uses, and the record separators the parsers
    rely on are byte-oriented. Decoding is the parsers' job, where they
    can choose the right granularity and error policy.

    Pass *target* for a core-constructed repository; *cwd* remains the
    path used by local-worktree readers. *timeout_s* and *max_bytes*
    override the selected policy when a caller already named a bound.

    Raises :class:`GitUnavailableError`, :class:`GitTimeoutError`,
    :class:`GitOutputTooLargeError`, or :class:`GitCommandError`.
    """
    chosen = policy if policy is not None else READ_POLICY
    proc = await spawn_git_process(args, cwd=cwd, target=target, policy=chosen)
    timeout = chosen.timeout_s if timeout_s is None else timeout_s
    max_bytes = chosen.max_bytes if max_bytes is None else max_bytes

    # stdout and stderr are drained concurrently. Reading them in
    # sequence deadlocks as soon as git fills the pipe we are not
    # reading, which a repository with a lot of output will do.
    stdout_task = asyncio.ensure_future(_read_capped(proc.stdout, max_bytes))
    stderr_task = asyncio.ensure_future(_read_capped(proc.stderr, _STDERR_MAX_BYTES))
    try:
        (stdout, overflowed), (stderr, _), returncode = await asyncio.wait_for(
            asyncio.gather(stdout_task, stderr_task, proc.wait()),
            timeout=timeout,
        )
    except TimeoutError:
        stdout_task.cancel()
        stderr_task.cancel()
        await terminate_git_process(proc)
        raise GitTimeoutError(
            f"git {' '.join(args)} exceeded {timeout:g}s and was terminated"
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


def _target_prefix_and_cwd(target: GitCommandTarget) -> tuple[tuple[str, ...], Path]:
    match target:
        case AttachedWorktreeTarget(worktree=worktree, git_dir=git_dir):
            return ("--git-dir", str(git_dir), "--work-tree", str(worktree)), worktree
        case RepositoryStoreTarget(git_dir=git_dir):
            return ("--git-dir", str(git_dir)), git_dir


def _stdin_for_policy(policy: GitProcessPolicy, *, pipe_stdin: bool) -> int | None:
    if pipe_stdin or policy.stdin == "pipe":
        return asyncio.subprocess.PIPE
    if policy.stdin == "devnull":
        return subprocess.DEVNULL
    return None


async def spawn_git_process(
    args: Sequence[str],
    *,
    cwd: Path | None = None,
    target: GitCommandTarget | None = None,
    policy: GitProcessPolicy | None = None,
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
    if target is not None and cwd is not None:
        raise TypeError("pass target or cwd, not both")
    if target is None and cwd is None:
        raise TypeError("run_git requires cwd or target")

    exe = git_executable()
    if exe is None:
        raise GitUnavailableError("git executable not found on PATH")

    chosen = policy if policy is not None else READ_POLICY
    prefix: tuple[str, ...] = ()
    work_cwd = cwd
    if target is not None:
        prefix, work_cwd = _target_prefix_and_cwd(target)
    assert work_cwd is not None

    argv = (exe, *GIT_COMMON_ARGS, *prefix, *args)
    child_umask = chosen.child_umask if chosen.child_umask is not None else -1
    try:
        return await asyncio.create_subprocess_exec(
            *argv,
            cwd=work_cwd,
            stdin=_stdin_for_policy(chosen, pipe_stdin=pipe_stdin),
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            env=git_environment(chosen),
            umask=child_umask,
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


def attached_worktree_target(*, worktree: Path, git_dir: Path) -> AttachedWorktreeTarget:
    """Validate and freeze one attached worktree plus its Git directory."""
    resolved_worktree = worktree.expanduser().resolve()
    resolved_git_dir = git_dir.expanduser().resolve()
    if not resolved_worktree.is_dir():
        raise GitUnavailableError(f"worktree is not a directory: {resolved_worktree}")
    if not resolved_git_dir.exists():
        raise GitUnavailableError(f"git directory does not exist: {resolved_git_dir}")
    return AttachedWorktreeTarget(worktree=resolved_worktree, git_dir=resolved_git_dir)


def repository_store_target(*, git_dir: Path) -> RepositoryStoreTarget:
    """Validate and freeze one worktree-free repository store."""
    resolved = git_dir.expanduser().resolve()
    if not resolved.is_dir():
        raise GitUnavailableError(f"repository store is not a directory: {resolved}")
    return RepositoryStoreTarget(git_dir=resolved)


def parse_git_version(text: str) -> tuple[int, int, int] | None:
    """Parse the first line of ``git version`` output.

    A missing patch component is 0. Apple, Windows, and untagged suffixes
    after the matched numbers are ignored. Anything that does not match is
    below every floor.
    """
    first = text.splitlines()[0] if text else ""
    match = _GIT_VERSION.match(first)
    if match is None:
        return None
    return (int(match.group(1)), int(match.group(2)), int(match.group(3) or 0))


def acquisition_allowed(version: tuple[int, int, int] | None) -> bool:
    """Return True when *version* meets the acquisition security floor."""
    if version is None:
        return False
    if version < ACQUISITION_MINIMUM:
        return False
    track = f"{version[0]}.{version[1]}"
    if track in ACQUISITION_PATCHED_TRACKS:
        return version >= ACQUISITION_PATCHED_TRACKS[track]
    return version >= ACQUISITION_NEWEST_PATCHED


def initial_https_strategy(version: tuple[int, int, int] | None) -> Literal["blobless", "refused"]:
    """Blobless is the initial HTTPS strategy above the acquisition floor."""
    return "blobless" if acquisition_allowed(version) else "refused"


def acquisition_gate_as_fixture(version_output: str) -> dict[str, bool | str]:
    """Project a version string into the git-version-gates fixture expected object."""
    version = parse_git_version(version_output)
    return {
        "acquisition": acquisition_allowed(version),
        "initial_strategy_for_https": initial_https_strategy(version),
    }


def parsed_git_version_as_fixture(version_output: str) -> list[int] | None:
    """Project a version string into the fixture's ``parsed`` list."""
    version = parse_git_version(version_output)
    return list(version) if version is not None else None


def required_acquisition_version_label() -> str:
    major, minor, patch = ACQUISITION_MINIMUM
    newest = ".".join(str(part) for part in ACQUISITION_NEWEST_PATCHED)
    return f"{major}.{minor}.{patch} or a patched release at least {newest} on a newer track"


@cache
def detect_git_version() -> tuple[tuple[int, int, int] | None, str]:
    """Return ``(parsed, first line)`` from the installed ``git version``."""
    exe = git_executable()
    if exe is None:
        return None, ""
    try:
        completed = subprocess.run(
            [exe, "version"],
            check=False,
            capture_output=True,
            text=True,
            env=git_environment(ACQUISITION_POLICY),
            timeout=5,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None, ""
    raw = completed.stdout.splitlines()[0] if completed.stdout else ""
    return parse_git_version(raw), raw


def require_acquisition_git() -> tuple[int, int, int]:
    """Return the installed Git version, or raise if it is below the floor."""
    version, raw = detect_git_version()
    if version is None or not acquisition_allowed(version):
        raise UnsupportedGitVersionError(raw, required_acquisition_version_label())
    return version


__all__ = [
    "ACQUISITION_MINIMUM",
    "ACQUISITION_NEWEST_PATCHED",
    "ACQUISITION_PATCHED_TRACKS",
    "ACQUISITION_POLICY",
    "BATCH_OBJECT_POLICY",
    "FETCH_POLICY",
    "GIT_ACQUISITION_TIMEOUT_S",
    "GitCommandError",
    "GitError",
    "GitOutputTooLargeError",
    "GitProcessPolicy",
    "GitTimeoutError",
    "GitUnavailableError",
    "READ_POLICY",
    "UnsupportedGitVersionError",
    "acquisition_allowed",
    "acquisition_gate_as_fixture",
    "attached_worktree_target",
    "detect_git_version",
    "failure_detail",
    "git_environment",
    "git_executable",
    "initial_https_strategy",
    "parse_git_version",
    "parsed_git_version_as_fixture",
    "repository_store_target",
    "require_acquisition_git",
    "run_git",
    "spawn_git_process",
    "terminate_git_process",
]
