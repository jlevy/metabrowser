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
  error instead. Where it is logged, it is logged through :func:`loggable`:
  part of it is whatever an origin sent, and a log goes to a terminal.

Acquisition reuses this runner. Named policies add ``stdin=DEVNULL``,
umask ``077``, isolated Git configuration, and ``GIT_NO_LAZY_FETCH``;
``GitCommandTarget`` becomes ``--git-dir`` / ``--work-tree`` arguments
rather than environment overrides. Version detection lives here so the
acquisition floor has one parser.
"""

from __future__ import annotations

import asyncio
import contextlib
import errno
import hashlib
import logging
import os
import re
import shutil
import signal
import subprocess
import sys
import threading
import time
from collections.abc import Awaitable, Callable, Mapping, Sequence
from dataclasses import dataclass, field
from functools import cache
from pathlib import Path
from typing import TYPE_CHECKING, Final, Literal

from metabrowser.content_errors import ContentReadError
from metabrowser.git.children import child_pids, executable, prepare_child_listing
from metabrowser.settings import GIT_SUBPROCESS_MAX_BYTES, GIT_SUBPROCESS_TIMEOUT_S

if TYPE_CHECKING:
    from metabrowser.git.progress import GitProgress

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

# Store reads must not apply the operator's mailmap to acquired objects.
GIT_DISABLE_MAILMAP_ARGS: Final[tuple[str, ...]] = (
    "-c",
    "mailmap.blob=",
    "-c",
    "mailmap.file=",
)

# Acquisition has no measured low-speed stall bound yet.
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
    # Read a store's attributes from its empty tree, so no commit's ``.gitattributes``
    # reaches a read of it: Git 2.43 reads a bare repository's attributes from ``HEAD``,
    # which a fetch moves, and 2.50 reads no commit's; ``GIT_ATTR_SOURCE`` names the tree
    # on both. Applied to a spawn on a ``RepositoryStoreTarget``; a worktree keeps its own.
    attributes_from_empty_tree: bool = False
    # Start Git as the leader of its own process group so a timeout or a
    # cancellation kills the helpers it forks (``upload-pack``, ``index-pack``,
    # ``remote-https``), not only the ``git`` process itself. The terminal's
    # Ctrl-C then reaches Git through cancellation, which kills the group, rather
    # than directly, so this is only for families whose spawns fork helpers and
    # are always awaited by a caller that handles cancellation (mb-lp89).
    own_process_group: bool = False


READ_POLICY: Final[GitProcessPolicy] = GitProcessPolicy(
    name="read",
    timeout_s=GIT_SUBPROCESS_TIMEOUT_S,
    max_bytes=GIT_SUBPROCESS_MAX_BYTES,
    stdin="inherit",
    child_umask=None,
    isolate_user_config=False,
    no_lazy_fetch=False,
)
# Acquisition Git runs with HOME=/dev/null. User and XDG Git configuration are already
# isolated; what HOME still reached was curl's optional ``$HOME/.netrc``, which Git
# enables and cannot turn off, so a netrc entry would answer an origin's challenge
# before any credential helper Metabrowser chose. Measured 2026-09-23 against a local
# server answering 401: with a netrc in HOME, curl retried with its credentials; with
# HOME=/dev/null it sent none. A credential helper that needs the real home (``gh``)
# is given it in its own command.
ACQUISITION_POLICY: Final[GitProcessPolicy] = GitProcessPolicy(
    name="acquisition",
    timeout_s=GIT_ACQUISITION_TIMEOUT_S,
    max_bytes=GIT_SUBPROCESS_MAX_BYTES,
    stdin="devnull",
    child_umask=0o077,
    isolate_user_config=True,
    no_lazy_fetch=True,
    ssh_batch=True,
    extra_env={"GCM_INTERACTIVE": "never", "LC_ALL": "C", "HOME": os.devnull},
    own_process_group=True,
)
# Request-path reads of a published store: ``ls-tree``, ``rev-parse``, ``log``,
# ``rev-list``, ``show``, ``diff``. The store holds untrusted content, so the
# isolation is acquisition-grade and lazy fetch is off. The deadline is the
# request-path one, because a request is waiting on the answer.
#
# A store's answer must be the same for every reader, so its reads see no attributes of the
# reader's either: Git reads ``$XDG_CONFIG_HOME/git/attributes``, else
# ``$HOME/.config/git/attributes``, and the system file, whatever ``GIT_CONFIG_*`` say,
# and ``*.lock -diff`` there turned a comparison's text files binary (review of #284).
# ``HOME`` and ``XDG_CONFIG_HOME`` hold nothing, as acquisition's ``HOME`` does; nothing a
# store read runs needs either, and Git is quiet about a path under ``/dev/null``.
#
# Nor a commit's: the same answer on every Git the floor admits means the attributes come
# from the store's empty tree (``attributes_from_empty_tree``), since Git 2.43 reads a bare
# repository's from ``HEAD``, which a fetch moves, and 2.50 reads none. What a store read
# honors is the store's own ``info/attributes``, which Git reads whatever else is set.
_NO_USER_ATTRIBUTES: Final[dict[str, str]] = {"HOME": os.devnull, "XDG_CONFIG_HOME": os.devnull}
STORE_READ_POLICY: Final[GitProcessPolicy] = GitProcessPolicy(
    name="store-read",
    timeout_s=GIT_SUBPROCESS_TIMEOUT_S,
    max_bytes=GIT_SUBPROCESS_MAX_BYTES,
    stdin="devnull",
    child_umask=0o077,
    isolate_user_config=True,
    no_lazy_fetch=True,
    ssh_batch=True,
    extra_env={"GCM_INTERACTIVE": "never", "LC_ALL": "C", **_NO_USER_ATTRIBUTES},
    attributes_from_empty_tree=True,
)
BATCH_OBJECT_POLICY: Final[GitProcessPolicy] = GitProcessPolicy(
    name="batch-object",
    timeout_s=GIT_SUBPROCESS_TIMEOUT_S,
    max_bytes=GIT_SUBPROCESS_MAX_BYTES,
    stdin="pipe",
    child_umask=0o077,
    isolate_user_config=True,
    no_lazy_fetch=True,
    extra_env=_NO_USER_ATTRIBUTES,
    attributes_from_empty_tree=True,
)

# The object format a store was made with. ``cat-file`` and ``diff`` answer under either;
# what differs is the length of an object id, and the id of the empty tree.
type ObjectFormat = Literal["sha1", "sha256"]
OBJECT_FORMATS: Final[frozenset[str]] = frozenset({"sha1", "sha256"})

# How much of a store's ``config`` is read for its object format. Git writes a store's in a
# few lines, and ``extensions.objectFormat`` is in the store's own file, never an include.
_STORE_CONFIG_MAX_BYTES: Final[int] = 64 * 1024
_CONFIG_SECTION = re.compile(rb"^\s*\[\s*([^\s\]\"]+)")
_OBJECT_FORMAT_KEY = re.compile(rb"^\s*objectformat\s*=\s*\"?(sha1|sha256)\"?\s*$", re.IGNORECASE)


def empty_tree_oid(object_format: ObjectFormat) -> str:
    """The id of the empty tree under *object_format*: the hash of ``tree 0\\0``, which is
    what ``git hash-object -t tree /dev/null`` answers, with no Git run."""
    digest = hashlib.sha256 if object_format == "sha256" else hashlib.sha1
    return digest(b"tree 0\0").hexdigest()


def _store_object_format(git_dir: Path) -> ObjectFormat:
    """What ``extensions.objectFormat`` in the store's ``config`` says, else SHA-1.

    Git's own rule: the extension names the format, and a repository without it is SHA-1.
    Read here rather than asked of Git because a target is made on request paths, and a
    bounded read of a file of a few lines costs nothing a spawn does.
    """
    try:
        with (git_dir / "config").open("rb") as handle:
            text = handle.read(_STORE_CONFIG_MAX_BYTES)
    except OSError:
        return "sha1"
    in_extensions = False
    for line in text.splitlines():
        section = _CONFIG_SECTION.match(line)
        if section is not None:
            in_extensions = section.group(1).lower() == b"extensions"
            continue
        if in_extensions:
            found = _OBJECT_FORMAT_KEY.match(line)
            if found is not None:
                return "sha256" if found.group(1).lower() == b"sha256" else "sha1"
    return "sha1"


@dataclass(frozen=True, slots=True)
class AttachedWorktreeTarget:
    """A trusted worktree plus Git directory. Construct with the factory."""

    worktree: Path
    git_dir: Path


@dataclass(frozen=True, slots=True)
class RepositoryStoreTarget:
    """A trusted worktree-free Git directory. Construct with the factory.

    ``object_format`` is the store's, read from its ``config`` once when the target is made,
    so a spawn can name the store's empty tree without asking Git.
    """

    git_dir: Path
    object_format: ObjectFormat


type GitCommandTarget = AttachedWorktreeTarget | RepositoryStoreTarget


@dataclass(frozen=True, slots=True)
class GitLocation:
    """Where Git commands run: a worktree path or a trusted target, never both.

    ``identity`` is the discovery-cache and history-session key. It is never
    placed on the wire. A revision location always carries the pinned full
    object id so two pins over one store do not share HEAD or history.
    """

    cwd: Path | None
    target: GitCommandTarget | None
    identity: str
    pinned_revision: str | None

    def __post_init__(self) -> None:
        if (self.cwd is None) == (self.target is None):
            raise TypeError("GitLocation requires cwd XOR target")
        if self.target is not None and self.pinned_revision is None:
            raise TypeError("a command-target location requires a pinned revision")
        if self.cwd is not None and self.pinned_revision is not None:
            raise TypeError("a filesystem location cannot pin a revision")

    @classmethod
    def filesystem(cls, root: Path) -> GitLocation:
        resolved = root.expanduser().resolve()
        return cls(cwd=resolved, target=None, identity=str(resolved), pinned_revision=None)

    @classmethod
    def revision(cls, target: RepositoryStoreTarget, commit_oid: str) -> GitLocation:
        return cls(
            cwd=None,
            target=target,
            identity=f"git-revision:{target.git_dir}:{commit_oid}",
            pinned_revision=commit_oid,
        )

    @property
    def read_policy(self) -> GitProcessPolicy:
        return STORE_READ_POLICY if self.target is not None else READ_POLICY

    @property
    def config_args(self) -> tuple[str, ...]:
        return GIT_DISABLE_MAILMAP_ARGS if self.target is not None else ()


def as_location(value: Path | GitLocation) -> GitLocation:
    """Accept the historical ``Path`` overload or an explicit location."""

    if isinstance(value, GitLocation):
        return value
    return GitLocation.filesystem(value)


class GitError(ContentReadError):
    """Base for every failure this package reports.

    Route handlers catch this one type and convert it to a response.
    Subclasses exist so callers that can act on a specific failure
    (``GitUnavailableError`` in particular, which decides whether the Git
    tab appears at all) do not have to inspect messages.

    It is also part of the shared content-read vocabulary, so a plugin data
    hook reading a pinned blob catches one family for both source kinds.
    """

    code = "git_failed"
    http_status = 500


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
    """``git`` exceeded its policy deadline and was killed.

    The default message names no command and no path, so a caller that prints
    ``str(exc)`` for a batch-actor timeout still says what happened.
    """

    code = "git_timeout"
    http_status = 504

    def __init__(self, message: str = "git command timed out") -> None:
        super().__init__(message)


class GitOutputTooLargeError(GitError):
    """``git`` produced more than :data:`GIT_SUBPROCESS_MAX_BYTES` on stdout."""


class UnsupportedGitVersionError(GitError):
    """The acquisition security floor refuses this host's Git.

    *detected* is the first line ``git version`` printed, empty when it printed nothing
    usable, and ``None`` when no ``git`` is on ``PATH``: that has no version to blame,
    so it says what is missing and which release to install.
    """

    def __init__(self, detected: str | None, required: str) -> None:
        super().__init__(
            f"git was not found on PATH; acquisition requires Git {required}"
            if detected is None
            else f"unsupported Git version ({detected or 'unparseable'}); "
            f"acquisition requires {required}"
        )
        self.detected = detected
        self.required = required


def loggable(text: str) -> str:
    """*text* as a log may print it: nothing in it acts on a terminal.

    Git's stderr holds whatever the origin sent, and a log's handler writes to a
    terminal. Every character that is not printable becomes its visible escape
    (``\\x1b``, ``\\r``, ``\\u202e``), so an escape sequence, a carriage return, a
    backspace, or a bidirectional override is read and not obeyed. A line break stays,
    since the text is several lines.
    """

    if text.isascii() and text.isprintable():
        return text
    return "".join(
        ch if ch == "\n" or ch.isprintable() else ch.encode("unicode_escape").decode("ascii")
        for ch in text
    )


def failure_detail(exc: GitError) -> str:
    """Log text for a git failure, including git's own stderr.

    Separate from ``str(exc)`` so the stderr text — which routinely
    carries absolute local paths — reaches a log line and only a log
    line. A caller that puts an exception message into a response body
    still gets the path-free form. The stderr text is :func:`loggable`.
    """
    summary = getattr(exc, "stderr_summary", "")
    return f"{exc}: {loggable(summary)}" if summary else str(exc)


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


def _default_policy(target: GitCommandTarget | None) -> GitProcessPolicy:
    """The policy for a caller that named none.

    A worktree-free store is never read under the ambient-configuration policy:
    no-lazy-fetch and isolation must not depend on every caller remembering.
    """

    return STORE_READ_POLICY if isinstance(target, RepositoryStoreTarget) else READ_POLICY


def _require_no_lazy_fetch(target: GitCommandTarget | None, policy: GitProcessPolicy) -> None:
    """Refuse a store spawn whose policy would let Git fetch a missing object itself.

    Stores are full clones with no promisor remote, so this is defense in depth:
    every Git process on a worktree-free store runs with ``GIT_NO_LAZY_FETCH=1``,
    and objects enter a store only through an explicit fetch, never inside a
    request. Checking here, where every store spawn passes, keeps that true for
    callers that name a policy as well as for those that inherit the default.
    """

    if isinstance(target, RepositoryStoreTarget) and not policy.no_lazy_fetch:
        raise ValueError(f"Git policy {policy.name!r} would allow lazy fetch in a repository store")


# Git processes started as the leaders of their own process groups and not yet reaped.
# They outlive a Python process that exits without unwinding, because they are in
# another group, so a command that must stop at once kills them first; see
# :func:`stop_process_groups`.
# Kept by process ID with the ``Process`` itself, whose ``returncode`` is set once the
# child is reaped, by its owner or by asyncio: from then on its ID may be reused.
_LIVE_PROCESS_GROUPS: dict[int, asyncio.subprocess.Process] = {}


# How long a stop waits for a group's spawn under way on another thread to fork, so that
# the stop's last look finds the child. A Git spawn took 2.9 ms (median) and 3.9 ms (max)
# from its start to its registration over 50 runs on a loaded M-series Mac (2026-11-11),
# so the bound is reached only when that thread's event loop is stuck; the stop then
# kills what it finds and the caller exits anyway.
SPAWN_WAIT_S: Final[float] = 2.0
# How often a stop that waits looks again. It polls rather than waiting on an event,
# whose lock a signal handler on the same thread might already hold.
_SPAWN_POLL_S: Final[float] = 0.005


@dataclass(slots=True)
class _GroupStop:
    """What a stop shares with the spawns of process groups (:func:`start_process_group`).

    Once a stop begins, no group is spawned. A spawn already under way is counted by the
    thread it runs on, so a stop on another thread can wait, within a bound, for it to
    fork. Nothing here waits for a spawn to *return*: the stop finds its groups from the
    kernel's list of this process's children (:mod:`metabrowser.git.children`), which
    has a child from its fork on, so a group whose spawn never returns, or fails after
    the fork, is found all the same. *programs* holds the files group spawns run, every
    link resolved, which is how a child that leads its own group is known to be one.

    The lock is re-entrant because a stop may run in a signal handler, between two
    bytecodes of the main thread, while that thread holds it for a spawn's bookkeeping.
    """

    lock: threading.RLock = field(default_factory=threading.RLock)
    requested: bool = False
    in_flight: dict[int, int] = field(default_factory=lambda: {})
    programs: set[str] = field(default_factory=lambda: set())


_GROUP_STOP = _GroupStop()


class ProcessGroupsStoppedError(OSError):
    """A process group was not started, because this process is stopping.

    An ``OSError``, as a spawn that failed is, so callers that report a failed spawn
    report this one too.
    """

    def __init__(self) -> None:
        super().__init__(errno.ECANCELED, "this process is stopping")


def kill_live_process_groups() -> None:
    """Kill every Git process group this process registered and has not yet reaped.

    Safe to call from a signal handler just before ``os._exit``: it only signals.
    A group killed here leaves what an interrupted Git leaves, which the next fetch
    cleans up under the store's fetch lock. A reaped child is skipped, because its
    group ID may already belong to an unrelated process. A group whose spawn has not
    returned is not in the registry; :func:`stop_process_groups` finds those too.
    """

    for pid, proc in tuple(_LIVE_PROCESS_GROUPS.items()):
        if proc.returncode is not None or not _unreaped_child(pid):
            continue
        with contextlib.suppress(ProcessLookupError, PermissionError):
            os.killpg(pid, signal.SIGKILL)


def _unreaped_child(pid: int) -> bool:
    """Whether *pid* is, at this moment, a child of this process that is not yet reaped.

    Asked just before a signal: a child that has not been reaped keeps its ID, so the
    signal reaches its group and no one else's. ``WNOWAIT`` leaves an exited child for
    its owner to reap, as before. Python before 3.13 has no ``waitid`` on macOS: there
    the kernel's list of children is asked again, which holds a child until it is
    reaped. Where neither answers, the caller's own record (the registry's
    ``returncode``) is all there is.

    What is left is the interval from this check to the signal. Measured 2026-11-12 on
    a loaded M-series Mac, ``waitid``, ``getpgid``, and ``killpg`` in a row took 1.4 us
    (median of 2,000) and 1.6 us (99th percentile); longer only if this thread is
    descheduled between them. For the signal to reach anyone else, another thread
    would have to reap the child in that interval, and the system give its ID to a new
    process that has already made itself a group leader. macOS and Linux hand out IDs
    in rising order and reuse one only after wrapping around, macOS at 99,999 and Linux
    at its ``pid_max``; and a process forked from this one took 0.87 ms at the least
    (median 1.08 ms, of 200) to lead a session of its own.
    """

    if not hasattr(os, "waitid"):
        listed = child_pids()
        return listed is None or pid in listed
    try:
        os.waitid(os.P_PID, pid, os.WEXITED | os.WNOHANG | os.WNOWAIT)
    except ChildProcessError:
        return False
    return True


def stop_process_groups(*, wait_s: float = SPAWN_WAIT_S) -> None:
    """Refuse new process groups and kill every one this process started, then return.

    For a command that must stop at once and then exits without unwinding. It does not
    need the event loop to make progress:

    * From now on :func:`start_process_group` refuses.
    * Every group this process leads is killed: each child the kernel lists that the
      registry holds, or that leads its own group and runs a file a group spawn ran,
      whether or not its spawn ever returned (see :func:`_kill_owned_groups`).
    * A spawn under way on another thread may not have forked yet, or may fork and
      register while the stop first looks. The stop waits for those, up to *wait_s*,
      and always looks once more at the end.

    It returns after waiting at most *wait_s*, plus the two looks at this process's
    children. A look is a few system calls per child, but on a Linux kernel without
    per-thread child lists it reads every process's ``/proc`` entry.

    A spawn on the calling thread gets no such wait: that thread is here, and the caller
    exits next. If a signal handler interrupted that spawn between the fork and the
    child's ``exec``, the child is still a copy of this interpreter, runs no file a
    group spawn ran, and is not killed.

    Where the kernel cannot list children (:func:`metabrowser.git.children.child_pids`),
    the registry is all there is. Safe in a signal handler: it takes only a re-entrant
    lock that no holder keeps for long, signals, and sleeps between looks.
    """

    stop = _GROUP_STOP
    me = threading.get_ident()
    with stop.lock:
        stop.requested = True
    _kill_owned_groups(stop)
    deadline = time.monotonic() + wait_s
    while _spawns_elsewhere(stop, me) and time.monotonic() < deadline:
        time.sleep(_SPAWN_POLL_S)
    # Always: a spawn elsewhere may have forked and registered during the first look,
    # so that this check found nothing under way and nothing was waited for.
    _kill_owned_groups(stop)


def _spawns_elsewhere(stop: _GroupStop, me: int) -> bool:
    with stop.lock:
        return any(count for thread, count in stop.in_flight.items() if thread != me)


def _kill_owned_groups(stop: _GroupStop) -> None:
    """Kill each group this process leads, as the kernel lists its children.

    A candidate is a child the registry holds, which leads its own group by how it was
    started, unless its ``returncode`` says it was reaped; or a child that leads its own
    group and runs a file a group spawn ran, which leaves alone a child that is not ours
    to end, such as a browser the standard library starts in a session of its own.

    The listing is only numbers, and another thread may reap a listed child at any time,
    after which its ID is free. So each candidate is confirmed to be this process's
    unreaped child (:func:`_unreaped_child`) immediately before it is signalled. What is
    left is that interval, about a microsecond unless this thread is descheduled in it:
    a child reaped then, and its ID given to a new process that has already made itself
    a group leader, would take the signal; :func:`_unreaped_child` gives the numbers.
    """

    children = child_pids()
    if children is None:
        kill_live_process_groups()
        return
    with stop.lock:
        programs = frozenset(stop.programs)
    for pid in children:
        registered = _LIVE_PROCESS_GROUPS.get(pid)
        if registered is not None:
            if registered.returncode is not None:
                continue
        else:
            path = executable(pid)
            if path is None or path not in programs or not _leads_its_own_group(pid):
                continue
        if not _unreaped_child(pid):
            continue
        with contextlib.suppress(ProcessLookupError, PermissionError):
            os.killpg(pid, signal.SIGKILL)


async def start_process_group(
    start: Callable[[], Awaitable[asyncio.subprocess.Process]],
    *,
    program: str,
    cwd: Path | None = None,
    env: Mapping[str, str] | None = None,
) -> asyncio.subprocess.Process:
    """Spawn, with *start*, a process that leads its own group, and track that group.

    Every such spawn goes through here, Git's and another tool's run the same way, such
    as ``gh``, so a stop can account for it. *program*, *cwd*, and *env* are what *start*
    launches with; the file that resolves to is how a stop knows the group from the
    fork on (see :func:`stop_process_groups`). The group is also registered for
    :func:`kill_live_process_groups` once the spawn returns, and its owner calls
    :func:`forget_process_group` once it is reaped. Raises
    :class:`ProcessGroupsStoppedError`, and starts nothing, once a stop has begun.
    """

    prepare_child_listing()
    # Before admission and off the event loop: it reads the file system and may run
    # ``xcrun``, which a stop, possibly in a signal handler, never does.
    launched = await asyncio.to_thread(_launched_files, program, cwd=cwd, env=env)
    stop = _GROUP_STOP
    me = threading.get_ident()
    with stop.lock:
        if stop.requested:
            raise ProcessGroupsStoppedError
        stop.programs.update(launched)
        stop.in_flight[me] = stop.in_flight.get(me, 0) + 1
    try:
        proc = await start()
    except BaseException:
        # What a failed spawn forked, if anything, is still this process's child, which
        # a stop finds from the kernel; the spawn itself just ends.
        _end_group_spawn(stop, me, None)
        raise
    _end_group_spawn(stop, me, proc)
    return proc


def _launched_files(
    program: str, *, cwd: Path | None, env: Mapping[str, str] | None
) -> frozenset[str]:
    """The files a spawn of *program* runs, every link resolved, as the kernel names them.

    Resolved as ``subprocess`` resolves it: a path with a directory part against *cwd*,
    which the child enters before it executes; a bare name against each directory of
    ``PATH`` in *env* (or this process's) in turn, each of which may itself be relative
    to *cwd*. The first executable file wins. Empty when none is found, and the spawn is
    then known only to the registry. The current directory is asked for only when a
    relative candidate needs it and no *cwd* is given: it may have been removed, which
    stops neither an absolute launch nor this.

    On macOS a launch from ``/usr/bin`` may be an Apple developer-tool shim, as
    ``/usr/bin/git`` is: within milliseconds it executes the tool of the selected
    developer directory in the same process, which the kernel then names instead. That
    tool is added as ``xcrun`` finds it (:func:`_apple_shim_tool`).
    """

    base = os.fspath(cwd) if cwd is not None else None
    if os.path.dirname(program):
        candidates = [program]
    else:
        candidates = [os.path.join(directory, program) for directory in os.get_exec_path(env)]
    for candidate in candidates:
        if not os.path.isabs(candidate) and base is None:
            try:
                base = os.getcwd()
            except OSError:
                continue
        path = candidate if base is None else os.path.join(base, candidate)
        if os.path.isfile(path) and os.access(path, os.X_OK):
            launched = os.path.realpath(path)
            if sys.platform != "darwin" or os.path.dirname(launched) != _APPLE_SHIM_DIR:
                return frozenset({launched})
            developer_dir = (env if env is not None else os.environ).get("DEVELOPER_DIR")
            tool = _apple_shim_tool(os.path.basename(launched), developer_dir)
            return frozenset({launched} if tool is None else {launched, tool})
    return frozenset()


# Where Apple's developer-tool shims are, and how long ``xcrun`` gets to name the tool one
# runs. It answered in about 10 ms (2026-11-12), on a worker thread, once per spawn of a
# shim with no ``DEVELOPER_DIR``; the bound covers only one that hangs.
_APPLE_SHIM_DIR: Final[str] = "/usr/bin"
_XCRUN_TIMEOUT_S: Final[float] = 2.0


# Answers ``xcrun`` gave for an explicit developer directory, which do not change.
_SHIM_TOOLS: dict[tuple[str, str], str] = {}


def _apple_shim_tool(name: str, developer_dir: str | None) -> str | None:
    """The tool Apple's ``/usr/bin/<name>`` shim runs, as ``xcrun`` finds it, or ``None``.

    With no ``DEVELOPER_DIR`` the shim runs the system's selection, which
    ``xcode-select -s`` can change while the server runs, so that is asked each time.
    An explicit directory's answer is kept once found. A failure is never kept, so a
    later spawn can still learn the tool.
    """

    if developer_dir is not None and (name, developer_dir) in _SHIM_TOOLS:
        return _SHIM_TOOLS[name, developer_dir]
    tool = _xcrun_find(name, developer_dir)
    if tool is not None and developer_dir is not None:
        _SHIM_TOOLS[name, developer_dir] = tool
    return tool


def _xcrun_find(name: str, developer_dir: str | None) -> str | None:
    env = {key: value for key, value in os.environ.items() if key != "DEVELOPER_DIR"}
    if developer_dir is not None:
        env["DEVELOPER_DIR"] = developer_dir
    try:
        found = subprocess.run(
            ["/usr/bin/xcrun", "--find", name],
            capture_output=True,
            text=True,
            timeout=_XCRUN_TIMEOUT_S,
            env=env,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    path = found.stdout.strip()
    return os.path.realpath(path) if found.returncode == 0 and path else None


def _end_group_spawn(stop: _GroupStop, me: int, proc: asyncio.subprocess.Process | None) -> None:
    """Register what a spawn started, if it is still running, and stop counting it.

    A child already reaped, as one that ended while its spawn was held is, has given up
    its ID, which may by now lead an unrelated group: it is not kept, and nothing here
    signals it. A stop under way kills the groups itself.
    """

    with stop.lock:
        if proc is not None and proc.returncode is None:
            _register_group(proc)
        remaining = stop.in_flight.get(me, 0) - 1
        if remaining > 0:
            stop.in_flight[me] = remaining
        else:
            stop.in_flight.pop(me, None)


def _register_group(proc: asyncio.subprocess.Process) -> None:
    # A streaming owner may reap its child with ``wait()`` alone; forget those here so
    # the registry holds only children that may still be running.
    for pid, known in tuple(_LIVE_PROCESS_GROUPS.items()):
        if known.returncode is not None:
            del _LIVE_PROCESS_GROUPS[pid]
    _LIVE_PROCESS_GROUPS[proc.pid] = proc


def _reaped(proc: asyncio.subprocess.Process) -> None:
    if _LIVE_PROCESS_GROUPS.get(proc.pid) is proc:
        del _LIVE_PROCESS_GROUPS[proc.pid]


def forget_process_group(proc: asyncio.subprocess.Process) -> None:
    """Stop tracking a group :func:`start_process_group` registered."""

    _reaped(proc)


def git_environment(
    policy: GitProcessPolicy | None = None, *, target: GitCommandTarget | None = None
) -> dict[str, str]:
    """Environment for a git child process.

    Strips the repository-pinning variables above, then:

    ``GIT_OPTIONAL_LOCKS=0`` is the environment form of
    ``--no-optional-locks`` and covers any git subprocess spawned in turn.
    ``GIT_TERMINAL_PROMPT=0`` and the empty askpass settings guarantee a
    repository needing credentials fails fast instead of blocking the
    request on a prompt that has no terminal to appear on.

    An isolated policy (acquisition, store read, or batch object) also drops every
    inherited ``GIT_*`` variable, isolates user and system Git configuration and
    attributes, disables implicit lazy fetch, and can force SSH batch mode. Those extras
    are not applied to ordinary local reads, which keep honoring the caller's Git
    environment.

    A policy that reads attributes from the empty tree names the tree of *target*'s
    object format in ``GIT_ATTR_SOURCE`` when *target* is a store; a worktree's commands
    read its own attributes, and a spawn with no target has no tree to name.
    """
    env = dict(os.environ)
    for name in _REPO_PINNING_GIT_VARS:
        env.pop(name, None)
    if policy is not None and policy.isolate_user_config:
        # An allowlist, not a denylist. Git reads configuration, protocol policy
        # (GIT_ALLOW_PROTOCOL replaces every protocol.* setting), the default ref
        # format, tracing targets, and helper commands from GIT_* variables, and
        # each release adds more. An isolated spawn inherits none of them and
        # gets exactly the ones set below.
        for name in tuple(env):
            if name.startswith("GIT_"):
                del env[name]
    env["GIT_OPTIONAL_LOCKS"] = "0"
    env["GIT_TERMINAL_PROMPT"] = "0"
    env["GIT_ASKPASS"] = ""
    env["SSH_ASKPASS"] = ""
    if policy is not None:
        if policy.isolate_user_config:
            env["GIT_CONFIG_GLOBAL"] = os.devnull
            env["GIT_CONFIG_NOSYSTEM"] = "1"
            # Attributes are not configuration: the system attributes file has its own switch.
            env["GIT_ATTR_NOSYSTEM"] = "1"
        if policy.no_lazy_fetch:
            env["GIT_NO_LAZY_FETCH"] = "1"
        if policy.ssh_batch:
            env["GIT_SSH_COMMAND"] = "ssh -oBatchMode=yes"
        if policy.extra_env:
            env.update(policy.extra_env)
        if policy.attributes_from_empty_tree and isinstance(target, RepositoryStoreTarget):
            env["GIT_ATTR_SOURCE"] = empty_tree_oid(target.object_format)
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


async def _read_stderr(
    stream: asyncio.StreamReader | None,
    on_progress: Callable[[GitProgress], None] | None,
) -> tuple[bytes, bool]:
    """Drain stderr for the log, handing progress records to *on_progress* as numbers.

    Without *on_progress* this is the capped drain. With it, a record of the shape
    ``git fetch --progress`` prints is parsed into a :class:`GitProgress` and dropped,
    and only the rest counts toward the cap: a long fetch writes more progress than the
    cap holds, and the error that explains a failure comes after it. No text Git or the
    origin wrote reaches the caller; see :mod:`metabrowser.git.progress`.
    """
    if stream is None or on_progress is None:
        return await _read_capped(stream, _STDERR_MAX_BYTES)
    # Imported where progress is read: every Git read loads this module, a folder's
    # among them, and only a first clone reads progress.
    from metabrowser.git.progress import ProgressSplitter

    splitter = ProgressSplitter(on_progress, _STDERR_MAX_BYTES)
    while chunk := await stream.read(_READ_CHUNK_BYTES):
        splitter.feed(chunk)
    return splitter.finish(), False


async def run_git(
    args: Sequence[str],
    *,
    cwd: Path | None = None,
    target: GitCommandTarget | None = None,
    policy: GitProcessPolicy | None = None,
    timeout_s: float | None = None,
    max_bytes: int | None = None,
    pass_fds: Sequence[int] = (),
    stdin_bytes: bytes | None = None,
    on_progress: Callable[[GitProgress], None] | None = None,
) -> bytes:
    """Run ``git`` with *args* in *cwd* and return raw stdout.

    Bytes, not text: git emits path names as raw bytes in whatever
    encoding the filesystem uses, and the record separators the parsers
    rely on are byte-oriented. Decoding is the parsers' job, where they
    can choose the right granularity and error policy.

    Pass *target* for a core-constructed repository; *cwd* remains the
    path used by local-worktree readers. *timeout_s* and *max_bytes*
    override the selected policy when a caller already named a bound.
    *pass_fds* are descriptors Git inherits, such as a lock it must hold for
    as long as it runs, even if this process dies first. *stdin_bytes* is written
    to Git's stdin, which is then closed, as ``update-ref --stdin`` reads it.
    *on_progress* is called, on the event loop, with each progress record a command
    run with ``--progress`` writes to stderr. It changes nothing else: the deadline,
    the output cap, and what a cancellation kills are the same with or without it.

    Raises :class:`GitUnavailableError`, :class:`GitTimeoutError`,
    :class:`GitOutputTooLargeError`, or :class:`GitCommandError`.
    """
    chosen = policy if policy is not None else _default_policy(target)
    proc = await spawn_git_process(
        args,
        cwd=cwd,
        target=target,
        policy=chosen,
        pass_fds=pass_fds,
        pipe_stdin=stdin_bytes is not None,
    )
    timeout = chosen.timeout_s if timeout_s is None else timeout_s
    max_bytes = chosen.max_bytes if max_bytes is None else max_bytes

    # stdout and stderr are drained concurrently. Reading them in
    # sequence deadlocks as soon as git fills the pipe we are not
    # reading, which a repository with a lot of output will do.
    stdout_task = asyncio.ensure_future(_read_capped(proc.stdout, max_bytes))
    stderr_task = asyncio.ensure_future(_read_stderr(proc.stderr, on_progress))

    async def feed_stdin() -> None:
        if stdin_bytes is None or proc.stdin is None:
            return
        # A Git that exits early closes its end; its exit status says why.
        with contextlib.suppress(BrokenPipeError, ConnectionResetError):
            proc.stdin.write(stdin_bytes)
            await proc.stdin.drain()
        proc.stdin.close()

    try:
        _fed, (stdout, overflowed), (stderr, _), returncode = await asyncio.wait_for(
            asyncio.gather(feed_stdin(), stdout_task, stderr_task, proc.wait()),
            timeout=timeout,
        )
        _reaped(proc)
    except TimeoutError:
        stdout_task.cancel()
        stderr_task.cancel()
        await terminate_git_process(proc)
        raise GitTimeoutError(
            f"git {' '.join(args)} exceeded {timeout:g}s and was terminated"
        ) from None
    except BaseException:
        # A genuine cancellation — the client disconnected, or the server
        # is shutting down — or anything else that stopped the wait. Reap the
        # child so it cannot outlive the request, then let the exception
        # continue to propagate; converting a cancellation to a GitError
        # would swallow the shutdown signal.
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
        log.debug("git %s exited %s: %s", " ".join(args), returncode, loggable(stderr_summary))
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
    pass_fds: Sequence[int] = (),
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

    chosen = policy if policy is not None else _default_policy(target)
    _require_no_lazy_fetch(target, chosen)
    exe = git_executable()
    if exe is None:
        raise GitUnavailableError("git executable not found on PATH")

    prefix: tuple[str, ...] = ()
    work_cwd = cwd
    if target is not None:
        prefix, work_cwd = _target_prefix_and_cwd(target)
    assert work_cwd is not None

    argv = (exe, *GIT_COMMON_ARGS, *prefix, *args)
    child_umask = chosen.child_umask if chosen.child_umask is not None else -1
    env = git_environment(chosen, target=target)
    if chosen.isolate_user_config:
        # A command with no ``--git-dir`` (``ls-remote``, ``init``) still runs
        # repository discovery from its working directory, and a repository that
        # encloses it would lend its local configuration, ``url.*.insteadOf``
        # included. A ceiling is never the directory discovery starts in, so name
        # the parent: Git looks at the working directory and no higher. Resolved,
        # because Git compares the ceiling against its physical working directory.
        env["GIT_CEILING_DIRECTORIES"] = str(Path(work_cwd).resolve().parent)
    own_group = chosen.own_process_group and os.name == "posix"

    async def spawn() -> asyncio.subprocess.Process:
        return await asyncio.create_subprocess_exec(
            *argv,
            cwd=work_cwd,
            stdin=_stdin_for_policy(chosen, pipe_stdin=pipe_stdin),
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            env=env,
            umask=child_umask,
            start_new_session=own_group,
            pass_fds=tuple(pass_fds),
        )

    # A group is registered as soon as it exists, so a stop that cannot unwind kills it
    # too, and a stop that begins while it is starting waits for it.
    spawning = asyncio.ensure_future(
        start_process_group(spawn, program=exe, cwd=work_cwd, env=env) if own_group else spawn()
    )
    try:
        return await asyncio.shield(spawning)
    except asyncio.CancelledError:
        # Cancelled while the child was starting. The child may already have forked
        # helpers, and asyncio's own cleanup would kill only ``git``; finish the
        # spawn, then kill the whole group before the cancellation continues.
        await kill_when_spawned(spawning)
        raise
    except OSError as exc:
        # Spawn itself failed — a missing cwd, a permissions problem, or
        # process-table exhaustion. Nothing downstream can distinguish
        # these usefully, so they collapse into one typed failure.
        raise GitUnavailableError(f"could not run git: {exc}") from exc


async def kill_when_spawned(spawn: asyncio.Future[asyncio.subprocess.Process]) -> None:
    """Wait out a spawn that a cancellation interrupted, then kill what it started."""

    while not spawn.done():
        with contextlib.suppress(asyncio.CancelledError):
            await asyncio.wait({spawn})
    if spawn.cancelled() or spawn.exception() is not None:
        return
    await terminate_git_process(spawn.result())


async def run_git_at(
    args: Sequence[str],
    location: GitLocation,
    *,
    policy: GitProcessPolicy | None = None,
    timeout_s: float | None = None,
    max_bytes: int | None = None,
) -> bytes:
    """Run ``git`` at *location*, applying store isolation when it is a pin."""

    return await run_git(
        [*location.config_args, *args],
        cwd=location.cwd,
        target=location.target,
        policy=policy if policy is not None else location.read_policy,
        timeout_s=timeout_s,
        max_bytes=max_bytes,
    )


async def spawn_git_at(
    args: Sequence[str],
    location: GitLocation,
    *,
    policy: GitProcessPolicy | None = None,
    pipe_stdin: bool = False,
) -> asyncio.subprocess.Process:
    """Start a Git process at *location*, applying store isolation when pinned."""

    return await spawn_git_process(
        [*location.config_args, *args],
        cwd=location.cwd,
        target=location.target,
        policy=policy if policy is not None else location.read_policy,
        pipe_stdin=pipe_stdin,
    )


async def terminate_git_process(proc: asyncio.subprocess.Process) -> None:
    """Kill *proc* and reap it, so a timeout cannot leak a child.

    ``proc.wait()`` after ``kill()`` is what actually reaps; skipping it
    leaves a zombie for the lifetime of the server.
    """
    if proc.returncode is not None:
        _reaped(proc)
        return
    # The process may exit between the returncode check and the signal.
    with contextlib.suppress(ProcessLookupError):
        if _leads_its_own_group(proc.pid):
            os.killpg(proc.pid, signal.SIGKILL)
        else:
            proc.kill()
    # The request may be cancelled again while reaping. The child is
    # already signalled by then, and re-raising here would replace the
    # original failure with a cancellation from the cleanup path.
    with contextlib.suppress(asyncio.CancelledError):
        await proc.wait()
    _reaped(proc)


def _leads_its_own_group(pid: int) -> bool:
    """Whether *pid* was started with ``own_process_group``.

    Read from the process rather than remembered, so a caller holding only the
    ``Process`` can still kill the whole group. An unreaped child keeps its group
    id, so this is exact until :func:`terminate_git_process` reaps it.
    """
    if os.name != "posix":
        return False
    try:
        return os.getpgid(pid) == pid
    except ProcessLookupError:
        return False


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
    """Validate and freeze one worktree-free repository store, with its object format."""
    resolved = git_dir.expanduser().resolve()
    if not resolved.is_dir():
        raise GitUnavailableError(f"repository store is not a directory: {resolved}")
    return RepositoryStoreTarget(git_dir=resolved, object_format=_store_object_format(resolved))


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


def acquisition_gate_as_fixture(version_output: str) -> dict[str, bool]:
    """Project a version string into the git-version-gates fixture expected object."""
    return {"acquisition": acquisition_allowed(parse_git_version(version_output))}


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
    """Return the installed Git version, or raise if it is absent or below the floor."""
    version, raw = detect_git_version()
    if version is None or not acquisition_allowed(version):
        detected = None if git_executable() is None else raw
        raise UnsupportedGitVersionError(detected, required_acquisition_version_label())
    return version


__all__ = [
    "ACQUISITION_MINIMUM",
    "ACQUISITION_NEWEST_PATCHED",
    "ACQUISITION_PATCHED_TRACKS",
    "ACQUISITION_POLICY",
    "BATCH_OBJECT_POLICY",
    "GIT_ACQUISITION_TIMEOUT_S",
    "GIT_DISABLE_MAILMAP_ARGS",
    "GitCommandError",
    "GitError",
    "GitLocation",
    "GitOutputTooLargeError",
    "GitProcessPolicy",
    "GitTimeoutError",
    "GitUnavailableError",
    "OBJECT_FORMATS",
    "ProcessGroupsStoppedError",
    "ObjectFormat",
    "READ_POLICY",
    "SPAWN_WAIT_S",
    "STORE_READ_POLICY",
    "UnsupportedGitVersionError",
    "acquisition_allowed",
    "acquisition_gate_as_fixture",
    "as_location",
    "attached_worktree_target",
    "detect_git_version",
    "empty_tree_oid",
    "failure_detail",
    "git_environment",
    "git_executable",
    "forget_process_group",
    "kill_live_process_groups",
    "kill_when_spawned",
    "loggable",
    "parse_git_version",
    "parsed_git_version_as_fixture",
    "repository_store_target",
    "require_acquisition_git",
    "run_git",
    "run_git_at",
    "spawn_git_at",
    "spawn_git_process",
    "start_process_group",
    "stop_process_groups",
    "terminate_git_process",
]
