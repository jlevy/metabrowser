"""The answers :mod:`metabrowser.git.file_ages` gives, kept per commit and read in the
background.

A page of a Git revision never waits for its files' ages. The tree route asks this service
for the revision's answer (:meth:`FileAgesService.request`), which returns at once with what
it has: the answer, or that the read is running, or why there is none. A first request
starts the read as a background job, and a later request finds the answer. A command that
prints the ages waits on ``/api/index/progress`` (``wait_for_index``); a page shows them on
its next load, since nothing on it asks again yet.

**Per commit.** An answer belongs to a commit ID, which names a tree for good, so it is
never stale: returning to a branch shown a moment ago is a lookup. A different branch or
tag is read for its own tip, and when the tip descends from a commit that is answered, only
the commits since it are read, when no merge lies between
(:func:`metabrowser.git.file_ages.nearest_ancestor`). The answers are in memory, in one table for the process, bounded by ``GIT_AGES_CACHE_REVISIONS``.
A restart reads again; the cost of that is ``GIT_AGES_TIMEOUT_S``'s measurement.

**Failure.** A read that fails, with the Git too old or the command failing or anything
else, is recorded for ``GIT_AGES_RETRY_AFTER_S`` so a poll is answered from the record and
does not start Git again; an answer cut by the read's budget is served and read again after
``GIT_AGES_CUT_RETRY_AFTER_S``, and is never the base of a derived read. Every step of a read
is inside one ``file_ages.read`` job span, which says why a read failed, with Git's stderr;
none of it goes to a response.
"""

from __future__ import annotations

import asyncio
import time
from collections import OrderedDict
from collections.abc import Awaitable, Callable, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Final, Literal

from metabrowser import event_log
from metabrowser.commit_ids import short_commit
from metabrowser.git.file_ages import (
    AgeLimits,
    FileAgesUnavailableError,
    RevisionAges,
    date_revision,
    file_ages_availability,
    nearest_ancestor,
)
from metabrowser.git.process import GitCommandError, RepositoryStoreTarget
from metabrowser.git.shallow import read_boundary
from metabrowser.settings import (
    GIT_AGES_CACHE_REVISIONS,
    GIT_AGES_CUT_RETRY_AFTER_S,
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
        cut_retry_after_s: float = GIT_AGES_CUT_RETRY_AFTER_S,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self._capacity = capacity
        self._limits = limits if limits is not None else AgeLimits(timeout_s=GIT_AGES_TIMEOUT_S)
        self._retry_after_s = retry_after_s
        self._cut_retry_after_s = cut_retry_after_s
        self._clock = clock
        self._answers: OrderedDict[_Key, RevisionAges] = OrderedDict()
        self._cut_at: dict[_Key, float] = {}
        self._jobs: dict[_Key, asyncio.Task[None]] = {}
        self._failures: OrderedDict[_Key, tuple[float, str]] = OrderedDict()

    @staticmethod
    def _key(target: RepositoryStoreTarget, commit: str) -> _Key:
        return (target.git_dir, commit)

    def request(self, target: RepositoryStoreTarget, commit: str, names: NamesSource) -> AgesStatus:
        """The answer for *commit*, or the state of getting it. Never waits on Git.

        The first request for a commit starts its read as a task on the running loop;
        *names* gives the sorted files of its tree, ``None`` when the index is truncated.
        An answer cut by the read's budget is served as it is, and read again by the first
        request after ``GIT_AGES_CUT_RETRY_AFTER_S``, as a failed read is after
        ``GIT_AGES_RETRY_AFTER_S``.
        """

        availability = file_ages_availability()
        if not availability.available:
            return AgesStatus("unavailable", reason=availability.reason, hint=availability.hint)
        key = self._key(target, commit)
        answer = self._answers.get(key)
        if answer is not None:
            cut_at = self._cut_at.get(key)
            if cut_at is None or self._clock() - cut_at < self._cut_retry_after_s:
                self._answers.move_to_end(key)
                return AgesStatus("ready" if answer.complete else "partial", ages=answer)
            self._forget(key)
        if key in self._jobs:
            return AgesStatus("dating")
        failure = self._failures.get(key)
        if failure is not None:
            if self._clock() - failure[0] < self._retry_after_s:
                return AgesStatus("failed", reason=failure[1])
            del self._failures[key]
        self._start(key, target, commit, names)
        return AgesStatus("dating")

    def _forget(self, key: _Key) -> None:
        self._answers.pop(key, None)
        self._cut_at.pop(key, None)

    def _start(
        self, key: _Key, target: RepositoryStoreTarget, commit: str, names: NamesSource
    ) -> None:
        task = asyncio.create_task(
            self._read(key, target, commit, names),
            name=f"metabrowser-file-ages-{short_commit(commit)}",
        )
        self._jobs[key] = task

        def finished(done: asyncio.Task[None]) -> None:
            # A read cancelled and asked for again is a newer task under the same key.
            if self._jobs.get(key) is done:
                del self._jobs[key]

        task.add_done_callback(finished)

    async def _read(
        self, key: _Key, target: RepositoryStoreTarget, commit: str, names_source: NamesSource
    ) -> None:
        """One read, every step of it inside one ``file_ages.read`` job span, so a failure at
        any step leaves a record and none is retried by the next poll."""

        with event_log.span(
            "job", "file_ages.read", attrs={"commit": commit}, announce=True
        ) as span:
            try:
                names = await names_source()
                if names is None:
                    span.end("failed", reason="too_many_files")
                    self._fail(key, "too_many_files")
                    return
                span.set(files=len(names))
                boundary = await asyncio.to_thread(read_boundary, target.git_dir)
                candidates = [
                    answer for (git_dir, _), answer in self._answers.items() if git_dir == key[0]
                ]
                base = await nearest_ancestor(target, commit, candidates)
                ages = await date_revision(
                    target=target,
                    commit=commit,
                    names=names,
                    boundary=boundary,
                    limits=self._limits,
                    base=base,
                )
            except FileAgesUnavailableError as exc:
                span.end("failed", reason=exc.reason)
                self._fail(key, exc.reason)
            except GitCommandError as exc:
                span.end(
                    "failed",
                    reason="git_failed",
                    stderr=exc.stderr_summary,
                    returncode=exc.returncode,
                )
                self._fail(key, "git_failed")
            except Exception as exc:
                # Anything else is the same to a page: no ages, asked again later. The record
                # says what it was.
                span.end("failed", reason="git_failed", error=event_log.describe_error(exc))
                self._fail(key, "git_failed")
            else:
                self._answers[key] = ages
                self._answers.move_to_end(key)
                if ages.stop == "budget":
                    self._cut_at[key] = self._clock()
                while len(self._answers) > self._capacity:
                    self._forget(next(iter(self._answers)))
                span.end(
                    "ok",
                    stop=ages.stop,
                    dated=ages.dated,
                    seconds=round(ages.seconds, 3),
                    from_commit=ages.from_commit,
                )

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


_service: FileAgesService | None = None


def file_ages_service() -> FileAgesService:
    """The process's service, made on first use."""

    global _service
    if _service is None:
        _service = FileAgesService()
    return _service


__all__ = [
    "AgesState",
    "AgesStatus",
    "FileAgesService",
    "NamesSource",
    "file_ages_service",
]
