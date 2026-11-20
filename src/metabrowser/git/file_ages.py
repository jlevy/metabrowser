"""When each file of a Git revision last changed, from ``git last-modified``.

A Git revision has no modification times, so a file's age is the committer time of the last
commit that changed it, which is what a hosting site's file list shows. Git answers that
itself: ``git last-modified -r -z <commit>`` names, for every file of the commit's tree, the
commit that last changed it, with the meaning of ``git log -1 -- <path>`` (history
simplification follows a merge to the first parent a path is unchanged against, so a change
a merge discarded is not "the last change"). This module runs it, reads the commit times,
and keeps the answer; it walks no history of its own. A directory's age is the newest of its
files, which :meth:`RevisionAges.newest_under` derives.

**What it needs.** ``git last-modified`` is Git 2.52's, and experimental there. This module
requires :data:`FILE_AGES_GIT_MINIMUM`, the release that carries the fixes of its early
defects (a ``--`` pathspec bug and an uninitialized read), and uses neither a pathspec nor a
subdirectory, which the crash reported against 2.52 needs. With an older Git, or when the
command fails, file ages are absent and nothing replaces them: a revision shows no times, as
it did before, and :func:`file_ages_availability` says why for ``metab --doctor`` and the
page. No other implementation stands in.

**What the output is.** One record per file, ``<commit-id> TAB <path> NUL`` with ``-z``, in
the order Git finds them. Given a range with an excluded commit (``C ^A``), a file last
changed at or before ``A`` is reported as ``^<id>`` of the excluded commit its chain reached,
which is ``A`` itself for almost every file. The output carries no time, so the commit times
come from one ``git log --no-walk`` over the distinct commits.

**From an ancestor.** An answer for a commit *C* whose ancestor *A* is answered reads
``C ^A``, so Git walks only the commits since *A*, and a file marked ``^A`` keeps *A*'s time.
A file marked with any other excluded commit would need that commit's own answer, so the
whole answer is read again without *A*. ``tests/test_git_file_ages.py`` checks the derived
answer against a cold one on histories with merges.

What the answer does not know is stated, never guessed:

- **A shallow boundary.** Git treats the commit at a shallow boundary as a root, which adds
  every file, so a file last changed there is reported as that commit. It is *undated*,
  last changed at or before the boundary, and ``older_than`` says so.
- **The budget.** A read is bounded in time (``GIT_AGES_TIMEOUT_S`` in ``settings.py``).
  Git prints a file's record as soon as it knows it, so a read cut by the budget keeps what
  it printed and leaves the rest undated, last changed at or before ``older_than``: the
  time of the oldest commit among those printed.
"""

from __future__ import annotations

import asyncio
import contextlib
import time
from array import array
from bisect import bisect_left
from collections.abc import Awaitable, Callable, Sequence
from dataclasses import dataclass
from typing import Final, Literal

from metabrowser import event_log
from metabrowser.git.process import (
    GitCommandError,
    GitError,
    GitLocation,
    RepositoryStoreTarget,
    detect_git_version,
    git_executable,
    git_upgrade_remedy,
    run_git_at,
    spawn_git_at,
    terminate_git_process,
)
from metabrowser.git.wire import is_full_revision
from metabrowser.tool_install import Remedy

FILE_AGES_GIT_MINIMUM: Final[tuple[int, int, int]] = (2, 53, 0)
"""The oldest Git whose ``last-modified`` this module reads. The command appeared in 2.52
as experimental, and its early defects (a ``--`` pathspec bug and an uninitialized read)
are fixed from 2.53. Verified with the Git the admitted-git CI job builds
(``.github/workflows/ci.yml``) and the one a developer machine has; a release between the
two is not tested."""

UNDATED: Final = -1
"""A time slot with no time: the file is not dated."""

_READ_CHUNK_BYTES: Final = 256 * 1024
# A record is an object ID, a tab, and a path; a record past this is not Git's output.
_MAX_RECORD_BYTES: Final = 1024 * 1024
_STDERR_KEPT_BYTES: Final = 4096
# How long Git has to exit once it has closed its output.
_REAP_WAIT_S: Final = 5.0
# Commits whose time one ``git log --no-walk`` is asked for: 1,000 object IDs of 64 hex
# digits are 65 KB of arguments, far under the smallest ``ARG_MAX`` a supported platform has.
_TIME_CHUNK_COMMITS: Final = 1000

type StopReason = Literal["complete", "boundary", "budget"]
type UnavailableReason = Literal["no_git", "unreadable", "too_old"]


def file_ages_version_label() -> str:
    """The minimum Git as a person reads it: ``2.53``."""

    major, minor, patch = FILE_AGES_GIT_MINIMUM
    return f"{major}.{minor}" if patch == 0 else f"{major}.{minor}.{patch}"


@dataclass(frozen=True, slots=True)
class FileAgesAvailability:
    """Whether the Git Metabrowser runs can date a revision's files, and what to say if not."""

    available: bool
    reason: UnavailableReason | None
    executable: str | None
    version_line: str | None
    """The first line of ``git version``, as Git printed it."""

    @property
    def hint(self) -> str | None:
        """The sentence that says what is missing, ``None`` when nothing is."""

        if self.available:
            return None
        needed = f"Git {file_ages_version_label()} or newer"
        if self.reason == "no_git":
            return f"File ages on Git revisions need {needed}; no git was found on PATH"
        found = self.version_line or "an unreadable version"
        return f"File ages on Git revisions need {needed} (found {_short_version(found)})"

    @property
    def remedy(self) -> Remedy | None:
        """The step that brings the Git up to the minimum, ``None`` when none is needed."""

        return None if self.available else git_upgrade_remedy(self.executable)


def _short_version(line: str) -> str:
    """``2.50.1`` from ``git version 2.50.1 (Apple Git-155)``; a line this does not
    recognize is returned as it is."""

    words = line.split()
    return words[2] if len(words) >= 3 and words[:2] == ["git", "version"] else line


def file_ages_availability() -> FileAgesAvailability:
    """The Git on ``PATH`` against :data:`FILE_AGES_GIT_MINIMUM`. Cached per process, as the
    Git it reads is."""

    executable = git_executable()
    if executable is None:
        return FileAgesAvailability(False, "no_git", None, None)
    version, line = detect_git_version()
    if version is None:
        return FileAgesAvailability(False, "unreadable", executable, line or None)
    if version < FILE_AGES_GIT_MINIMUM:
        return FileAgesAvailability(False, "too_old", executable, line)
    return FileAgesAvailability(True, None, executable, line)


class FileAgesError(GitError):
    """Git's output was not the shape this module reads."""


class FileAgesUnavailableError(GitError):
    """File ages cannot be read here: the Git is too old, or the command failed."""

    code = "file_ages_unavailable"

    def __init__(self, message: str, *, reason: str) -> None:
        super().__init__(message)
        self.reason = reason


@dataclass(frozen=True, slots=True)
class AgeLimits:
    """The bound one read runs under: wall time."""

    timeout_s: float


@dataclass(frozen=True, slots=True)
class RevisionAges:
    """When each file at one commit last changed, as far as Git could tell.

    ``names`` are the files the answer dates, sorted bytes as the blob index lists them, and
    ``times[i]`` is the committer time, in seconds, of ``names[i]``'s last change, or
    :data:`UNDATED`. ``older_than`` is set when any name is undated: each is last changed at
    or before it. ``stop`` says why those are undated (``boundary`` for a shallow history,
    ``budget`` for a cut read) or is ``complete`` when none is.
    """

    commit: str
    commit_time: int
    names: tuple[bytes, ...]
    times: array[int]
    older_than: int | None
    stop: StopReason
    commits: int
    """How many distinct commits last changed a file."""
    seconds: float
    from_commit: str | None = None
    """The ancestor whose answer this one was derived from, when it was."""

    @property
    def dated(self) -> int:
        return sum(1 for value in self.times if value != UNDATED)

    @property
    def complete(self) -> bool:
        return self.stop == "complete"

    def time_of(self, name: bytes) -> int | None:
        """*name*'s time, or ``None`` when it is not a name here or is undated."""

        at = bisect_left(self.names, name)
        if at == len(self.names) or self.names[at] != name:
            return None
        value = self.times[at]
        return None if value == UNDATED else value

    def newest_under(self, prefix: bytes) -> int | None:
        """The newest time of a dated file at or under *prefix*, ``None`` when none is."""

        if not prefix:
            start, stop = 0, len(self.names)
        else:
            start = bisect_left(self.names, prefix + b"/")
            stop = bisect_left(self.names, prefix + b"0")
            at = bisect_left(self.names, prefix)
            if at < len(self.names) and self.names[at] == prefix:
                value = self.times[at]
                return None if value == UNDATED else value
        if start >= stop:
            return None
        newest = max(self.times[start:stop])
        return None if newest == UNDATED else newest

    def mapping(self) -> dict[bytes, int]:
        """Every dated name's time, for a caller that looks many up."""

        return {
            name: value
            for name, value in zip(self.names, self.times, strict=True)
            if value != UNDATED
        }


@dataclass(slots=True)
class _Read:
    """What one ``git last-modified`` read printed."""

    found: dict[bytes, bytes]
    """Wanted path to the object ID printed for it, ``^``-prefixed for an excluded commit."""
    cut: bool


async def _drain_stderr(stream: asyncio.StreamReader | None) -> str:
    kept = bytearray()
    if stream is None:
        return ""
    while True:
        chunk = await stream.read(_READ_CHUNK_BYTES)
        if not chunk:
            return bytes(kept).decode("utf-8", errors="replace")
        if len(kept) < _STDERR_KEPT_BYTES:
            kept.extend(chunk[: _STDERR_KEPT_BYTES - len(kept)])


async def _read_last_modified(
    location: GitLocation,
    *,
    commit: str,
    exclude: str | None,
    wanted: frozenset[bytes],
    deadline: float,
) -> _Read:
    """``git last-modified -r -z <commit> [^<exclude>]``, its records kept for *wanted*."""

    revisions = [commit] if exclude is None else [commit, f"^{exclude}"]
    for revision in (commit, exclude):
        if revision is not None and not is_full_revision(revision):
            raise FileAgesError("a revision is not a full commit ID")
    process = await spawn_git_at(["last-modified", "-r", "-z", *revisions], location)
    stderr_task = asyncio.create_task(_drain_stderr(process.stderr))
    found: dict[bytes, bytes] = {}
    cut = False
    natural_end = False
    try:
        try:
            async with asyncio.timeout(max(deadline - time.monotonic(), 0.0)):
                await _consume(process, wanted, found)
            natural_end = True
        except TimeoutError:
            cut = True
        if natural_end:
            with contextlib.suppress(TimeoutError):
                await asyncio.wait_for(process.wait(), timeout=_REAP_WAIT_S)
    finally:
        await terminate_git_process(process)
        stderr = await stderr_task
    if natural_end and process.returncode not in (0, None):
        raise GitCommandError(("last-modified",), process.returncode or 1, stderr)
    return _Read(found=found, cut=cut)


async def _consume(
    process: asyncio.subprocess.Process, wanted: frozenset[bytes], found: dict[bytes, bytes]
) -> None:
    stdout = process.stdout
    if stdout is None:
        raise FileAgesError("git last-modified has no stdout")
    carry = b""
    while True:
        chunk = await stdout.read(_READ_CHUNK_BYTES)
        if not chunk:
            if carry:
                raise FileAgesError("git last-modified ended in the middle of a record")
            return
        data = carry + chunk if carry else chunk
        records = data.split(b"\0")
        carry = records.pop()
        if len(carry) > _MAX_RECORD_BYTES:
            raise FileAgesError("git last-modified printed a record past the bound")
        for record in records:
            oid, tab, path = record.partition(b"\t")
            if not tab:
                raise FileAgesError("a record has no path")
            if path in wanted:
                found[path] = oid


async def _commit_times(location: GitLocation, commits: Sequence[str]) -> dict[str, int]:
    """The committer time of each of *commits*, in seconds."""

    times: dict[str, int] = {}
    for start in range(0, len(commits), _TIME_CHUNK_COMMITS):
        chunk = commits[start : start + _TIME_CHUNK_COMMITS]
        for oid in chunk:
            if not is_full_revision(oid):
                raise FileAgesError("a commit is not a full commit ID")
        output = await run_git_at(
            [
                "log",
                *location.diff_driver_args,
                "--no-walk=unsorted",
                "--format=%H %ct",
                *chunk,
            ],
            location,
        )
        for line in output.decode("ascii", errors="replace").splitlines():
            oid, _, seconds = line.partition(" ")
            try:
                times[oid] = int(seconds)
            except ValueError as exc:
                raise FileAgesError("a commit time is not a number") from exc
    missing = [oid for oid in commits if oid not in times]
    if missing:
        raise FileAgesError("a commit that last changed a file is not in the store")
    return times


async def date_revision(
    *,
    target: RepositoryStoreTarget,
    commit: str,
    names: Sequence[bytes],
    boundary: frozenset[str] | None,
    limits: AgeLimits,
    base: RevisionAges | None = None,
) -> RevisionAges:
    """When each of *names*, the sorted files of *commit*'s tree, last changed.

    *boundary* is the store's shallow boundary, empty for a complete history, and ``None``
    when it could not be read, which no answer is given for. With *base*, an answer for an
    ancestor of *commit*, only the commits since it are read.
    """

    availability = file_ages_availability()
    if not availability.available:
        raise FileAgesUnavailableError(
            availability.hint or "file ages are unavailable", reason="git"
        )
    if boundary is None:
        raise FileAgesUnavailableError("the shallow boundary cannot be read", reason="boundary")
    if not is_full_revision(commit):
        raise FileAgesError("the revision is not a full commit ID")
    location = GitLocation.revision(target, commit)
    started = time.monotonic()
    deadline = started + limits.timeout_s
    wanted = frozenset(names)
    read: _Read | None = None
    used_base: RevisionAges | None = None
    if base is not None:
        derived = await _read_last_modified(
            location, commit=commit, exclude=base.commit, wanted=wanted, deadline=deadline
        )
        excluded = {oid for oid in derived.found.values() if oid.startswith(b"^")}
        if derived.cut or excluded <= {b"^" + base.commit.encode("ascii")}:
            read, used_base = derived, base
    if read is None:
        read = await _read_last_modified(
            location, commit=commit, exclude=None, wanted=wanted, deadline=deadline
        )
    commits = sorted({oid.lstrip(b"^").decode("ascii") for oid in read.found.values()})
    times = await _commit_times(location, [commit, *commits])
    base_map = used_base.mapping() if used_base is not None else {}
    values = array("q", [UNDATED]) * len(names)
    boundary_time = 0
    bounds: list[int] = []
    for at, name in enumerate(names):
        oid_b = read.found.get(name)
        if oid_b is None:
            continue
        if oid_b.startswith(b"^"):
            carried = base_map.get(name)
            if carried is not None:
                values[at] = carried
            elif used_base is not None and used_base.older_than is not None:
                bounds.append(used_base.older_than)
            continue
        oid = oid_b.decode("ascii")
        if oid in boundary:
            boundary_time = max(boundary_time, times[oid])
            continue
        values[at] = times[oid]
    stop: StopReason = "complete"
    older_than: int | None = None
    if any(value == UNDATED for value in values):
        if boundary_time:
            bounds.append(boundary_time)
        if read.cut:
            printed = [times[oid] for oid in commits if oid not in boundary]
            bounds.append(min(printed) if printed else times[commit])
        older_than = max(bounds) if bounds else None
        stop = (
            "budget"
            if read.cut or (used_base is not None and used_base.stop == "budget")
            else "boundary"
        )
    return RevisionAges(
        commit=commit,
        commit_time=times[commit],
        names=tuple(names),
        times=values,
        older_than=older_than,
        stop=stop,
        commits=len(commits),
        seconds=time.monotonic() - started,
        from_commit=used_base.commit if used_base is not None else None,
    )


async def is_ancestor(target: RepositoryStoreTarget, ancestor: str, commit: str) -> bool:
    """Whether *ancestor* is reachable from *commit*, by ``merge-base --is-ancestor``."""

    if not (is_full_revision(ancestor) and is_full_revision(commit)):
        raise FileAgesError("an ancestor query needs full commit IDs")
    location = GitLocation.revision(target, commit)
    try:
        await run_git_at(["merge-base", "--is-ancestor", ancestor, commit], location)
    except GitCommandError as exc:
        if exc.returncode == 1:
            return False
        raise
    return True


async def nearest_ancestor(
    target: RepositoryStoreTarget, commit: str, candidates: Sequence[RevisionAges]
) -> RevisionAges | None:
    """The answered ancestor of *commit* among *candidates* that was committed last, so the
    fewest commits lie between. Another answer would read more, never differently."""

    for candidate in sorted(candidates, key=lambda ages: ages.commit_time, reverse=True):
        if candidate.commit == commit:
            continue
        if await is_ancestor(target, candidate.commit, commit):
            return candidate
    return None


async def run_dating(
    work: Callable[[], Awaitable[RevisionAges]], *, commit: str, files: int
) -> RevisionAges:
    """*work* as a logged job named for the read, ended with what it measured."""

    with event_log.span(
        "job", "file_ages.read", attrs={"commit": commit, "files": files}, announce=True
    ) as span:
        try:
            ages = await work()
        except FileAgesUnavailableError as exc:
            span.end("failed", reason=exc.reason)
            raise
        except GitCommandError as exc:
            span.end("failed", stderr=exc.stderr_summary, returncode=exc.returncode)
            raise
        span.end(
            "ok",
            stop=ages.stop,
            dated=ages.dated,
            commits=ages.commits,
            seconds=round(ages.seconds, 3),
            from_commit=ages.from_commit,
        )
        return ages


__all__ = [
    "FILE_AGES_GIT_MINIMUM",
    "UNDATED",
    "AgeLimits",
    "FileAgesAvailability",
    "FileAgesError",
    "FileAgesUnavailableError",
    "RevisionAges",
    "StopReason",
    "date_revision",
    "file_ages_availability",
    "file_ages_version_label",
    "is_ancestor",
    "nearest_ancestor",
    "run_dating",
]
