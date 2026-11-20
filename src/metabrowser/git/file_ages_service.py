"""The answers :mod:`metabrowser.git.file_ages` gives, kept per commit and read in the
background.

A page of a Git revision never waits for its files' ages. The tree route asks this service
for the revision's answer (:meth:`FileAgesService.request`), which returns at once with what
it has: the answer, or that the read is running, or why there is none. A first request
starts the read as a background job; the page polls ``/api/index/progress`` and loads the
tree again when the answer lands.

**Per commit.** An answer belongs to a commit ID, which names a tree for good, so it is
never stale: returning to a branch shown a moment ago is a lookup. A different branch or
tag is read for its own tip, and when the tip descends from a commit that is answered, only
the commits since it are read (:func:`metabrowser.git.file_ages.nearest_ancestor`). The
answers are in memory, in one table for the process, bounded by ``GIT_AGES_CACHE_REVISIONS``.
A restart reads again; the cost of that is ``GIT_AGES_TIMEOUT_S``'s measurement.

**Failure.** A read that fails, with the Git too old or the command failing, is recorded
for ``GIT_AGES_RETRY_AFTER_S`` so a poll is answered from the record and does not start
Git again. Its reason and Git's stderr go to the event log, never to a response.
"""

from __future__ import annotations

import asyncio
import contextlib
import time
from collections import OrderedDict
from collections.abc import Awaitable, Callable, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Final, Literal

from metabrowser.git.file_ages import (
    AgeLimits,
    FileAgesError,
    FileAgesUnavailableError,
    RevisionAges,
    date_revision,
    file_ages_availability,
    nearest_ancestor,
    run_dating,
)
from metabrowser.git.process import GitError, RepositoryStoreTarget
from metabrowser.git.shallow import read_boundary
from metabrowser.settings import (
    GIT_AGES_CACHE_REVISIONS,
    GIT_AGES_RETRY_AFTER_S,
    GIT_AGES_TIMEOUT_S,
)

type AgesState = Literal["unavailable", "dating", "ready", "partial", "failed"]
type NamesSource = Callable[[], Awaitable[Sequence[bytes] | None]]
type _Key = tuple[Path, str]

_FAILURES_KEPT: Final = 16


@dataclass(frozen=True, slots=True)
class AgesStatus:
    """What is known about a revision's file ages now.

    ``unavailable`` is a Git too old to read them; ``failed`` is a read that did not finish,
    named by ``reason``; ``dating`` is a read in progress; ``ready`` is every file dated and
    ``partial`` an answer with files undated (``ages.older_than`` and ``ages.stop`` say why).
    """

    state: AgesState
    ages: RevisionAges | None = None
    reason: str | None = None
    hint: str | None = None

    def wire(self, *, files: int | None = None) -> dict[str, Any]:
        """The status as ``/api/tree`` and ``/api/index/progress`` carry it."""

        payload: dict[str, Any] = {"state": self.state}
        ages = self.ages
        if ages is not None:
            payload.update(
                {
                    "files": len(ages.names),
                    "dated": ages.dated,
                    "older_than": ages.older_than,
                    "stop": ages.stop,
                    "commits": ages.commits,
                    "derived": ages.from_commit is not None,
                }
            )
        elif files is not None:
            payload["files"] = files
        if self.hint is not None:
            payload["hint"] = self.hint
        if self.reason is not None:
            payload["reason"] = self.reason
        return payload


class FileAgesService:
    """The process's answers and running reads, keyed by store and commit."""

    def __init__(
        self,
        *,
        capacity: int = GIT_AGES_CACHE_REVISIONS,
        limits: AgeLimits | None = None,
        retry_after_s: float = GIT_AGES_RETRY_AFTER_S,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self._capacity = capacity
        self._limits = limits if limits is not None else AgeLimits(timeout_s=GIT_AGES_TIMEOUT_S)
        self._retry_after_s = retry_after_s
        self._clock = clock
        self._answers: OrderedDict[_Key, RevisionAges] = OrderedDict()
        self._jobs: dict[_Key, asyncio.Task[None]] = {}
        self._failures: OrderedDict[_Key, tuple[float, str]] = OrderedDict()

    @staticmethod
    def _key(target: RepositoryStoreTarget, commit: str) -> _Key:
        return (target.git_dir, commit)

    def is_idle(self) -> bool:
        """Whether no answer, read, or failure is kept."""

        return not (self._answers or self._jobs or self._failures)

    def peek(self, target: RepositoryStoreTarget, commit: str) -> RevisionAges | None:
        """The kept answer for *commit*, starting nothing."""

        return self._answers.get(self._key(target, commit))

    def request(self, target: RepositoryStoreTarget, commit: str, names: NamesSource) -> AgesStatus:
        """The answer for *commit*, or the state of getting it. Never waits on Git.

        The first request for a commit starts its read as a task on the running loop;
        *names* gives the sorted files of its tree, ``None`` when the index is truncated.
        """

        availability = file_ages_availability()
        if not availability.available:
            return AgesStatus("unavailable", reason=availability.reason, hint=availability.hint)
        key = self._key(target, commit)
        answer = self._answers.get(key)
        if answer is not None:
            self._answers.move_to_end(key)
            return AgesStatus("ready" if answer.complete else "partial", ages=answer)
        if key in self._jobs:
            return AgesStatus("dating")
        failure = self._failures.get(key)
        if failure is not None:
            if self._clock() - failure[0] < self._retry_after_s:
                return AgesStatus("failed", reason=failure[1])
            del self._failures[key]
        self._start(key, target, commit, names)
        return AgesStatus("dating")

    def _start(
        self, key: _Key, target: RepositoryStoreTarget, commit: str, names: NamesSource
    ) -> None:
        task = asyncio.create_task(
            self._read(key, target, commit, names), name=f"metabrowser-file-ages-{commit[:12]}"
        )
        self._jobs[key] = task
        task.add_done_callback(lambda _done: self._jobs.pop(key, None))

    async def _read(
        self, key: _Key, target: RepositoryStoreTarget, commit: str, names_source: NamesSource
    ) -> None:
        try:
            names = await names_source()
            if names is None:
                self._fail(key, "too_many_files")
                return
            boundary = await asyncio.to_thread(read_boundary, target.git_dir)
            candidates = [
                answer for (git_dir, _), answer in self._answers.items() if git_dir == key[0]
            ]
            base = await nearest_ancestor(target, commit, candidates)
            ages = await run_dating(
                lambda: date_revision(
                    target=target,
                    commit=commit,
                    names=names,
                    boundary=boundary,
                    limits=self._limits,
                    base=base,
                ),
                commit=commit,
                files=len(names),
            )
        except FileAgesUnavailableError as exc:
            self._fail(key, exc.reason)
        except (GitError, FileAgesError, OSError):
            # The reason, and Git's stderr, are in the job's event-log record.
            self._fail(key, "git_failed")
        else:
            self._answers[key] = ages
            self._answers.move_to_end(key)
            while len(self._answers) > self._capacity:
                self._answers.popitem(last=False)

    def _fail(self, key: _Key, reason: str) -> None:
        self._failures[key] = (self._clock(), reason)
        self._failures.move_to_end(key)
        while len(self._failures) > _FAILURES_KEPT:
            self._failures.popitem(last=False)

    def cancel(self, target: RepositoryStoreTarget, commit: str) -> None:
        """Stop *commit*'s read when it is running, as its page goes."""

        task = self._jobs.pop(self._key(target, commit), None)
        if task is not None:
            task.cancel()

    async def settled(self, target: RepositoryStoreTarget, commit: str) -> None:
        """Wait for *commit*'s running read, for a caller that has no page to poll: a test,
        or ``metab --api``."""

        task = self._jobs.get(self._key(target, commit))
        if task is not None:
            with contextlib.suppress(asyncio.CancelledError):
                await task


_service: FileAgesService | None = None


def file_ages_service() -> FileAgesService:
    """The process's service, made on first use."""

    global _service
    if _service is None:
        _service = FileAgesService()
    return _service


def reset_file_ages_service() -> None:
    """Forget every answer and cancel every read, as a test or a new process starts."""

    global _service
    service, _service = _service, None
    if service is not None:
        for task in service._jobs.values():
            task.cancel()


__all__ = [
    "AgesState",
    "AgesStatus",
    "FileAgesService",
    "NamesSource",
    "file_ages_service",
    "reset_file_ages_service",
]
