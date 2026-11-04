"""Bounded observations of failed reads, for a reader's explicit recovery action.

No read here starts network work. Keys include the store and the exact commit selection;
failures from another comparison cannot authorize its repair. Only an observed full
object ID is retained, never Git diagnostics, paths, or content. Success clears an
observation only after the caller authenticates the recovered object.
"""

from __future__ import annotations

import re
import threading
import time
from collections import OrderedDict
from dataclasses import dataclass
from typing import Literal

from metabrowser.git.process import GitCommandError, GitError, RepositoryStoreTarget
from metabrowser.git.wire import is_full_revision

# Match the comparison cache's sixteen attended/recent selections. Eight observed
# failures per selection cover one initial PR viewport with at most 128 small records.
# Ten minutes allows a reader to reconnect and retry; expired failures authorize nothing.
MAX_FAILED_COMPARISONS = 16
MAX_FAILED_OBJECTS = 8
FAILURE_TTL_S = 600.0
_OID = r"([0-9a-f]{40}(?:[0-9a-f]{24})?)"
_MISSING = re.compile(
    rf"(?:^|\n)(?:fatal: unable to read |error: Could not read |fatal: bad object ){_OID}(?=\n|$)"
)


@dataclass(frozen=True, slots=True)
class FailedObject:
    oid: str
    state: Literal["object_unavailable", "object_corrupt"]
    observed_at: float


class ObjectFailures:
    """Thread-safe, bounded observations with no reference to a live server or source."""

    def __init__(self) -> None:
        self._guard = threading.Lock()
        self._entries: OrderedDict[tuple[str, tuple[str, ...]], OrderedDict[str, FailedObject]] = (
            OrderedDict()
        )

    def _expire(self) -> None:
        cutoff = time.monotonic() - FAILURE_TTL_S
        for key, entries in tuple(self._entries.items()):
            for oid, failure in tuple(entries.items()):
                if failure.observed_at < cutoff:
                    del entries[oid]
            if not entries:
                del self._entries[key]

    def remember(
        self, target: RepositoryStoreTarget, commits: tuple[str, ...], error: GitError
    ) -> FailedObject | None:
        from metabrowser.git.tree_source import GitObjectCorruptError, GitObjectUnavailableError

        if not commits or not all(is_full_revision(commit) for commit in commits):
            return None
        oid: str | None = None
        state: Literal["object_unavailable", "object_corrupt"] = "object_unavailable"
        if isinstance(error, (GitObjectUnavailableError, GitObjectCorruptError)):
            oid = error.oid
            if isinstance(error, GitObjectCorruptError):
                state = "object_corrupt"
        elif isinstance(error, GitCommandError):
            match = _MISSING.search(error.stderr_summary)
            if match is not None:
                oid = match.group(1)
        if oid is None or not is_full_revision(oid):
            return None
        failure = FailedObject(oid, state, time.monotonic())
        key = (str(target.git_dir), commits)
        with self._guard:
            self._expire()
            entries = self._entries.setdefault(key, OrderedDict())
            entries[oid] = failure
            entries.move_to_end(oid)
            while len(entries) > MAX_FAILED_OBJECTS:
                entries.popitem(last=False)
            self._entries.move_to_end(key)
            while len(self._entries) > MAX_FAILED_COMPARISONS:
                self._entries.popitem(last=False)
        return failure

    def pending(
        self, target: RepositoryStoreTarget, commits: tuple[str, ...]
    ) -> tuple[FailedObject, ...]:
        with self._guard:
            self._expire()
            return tuple(self._entries.get((str(target.git_dir), commits), {}).values())

    def verified(
        self, target: RepositoryStoreTarget, commits: tuple[str, ...], failure: FailedObject
    ) -> None:
        """Clear only the observation verified, preserving a concurrent newer failure."""
        key = (str(target.git_dir), commits)
        with self._guard:
            entries = self._entries.get(key)
            if entries is not None and entries.get(failure.oid) is failure:
                del entries[failure.oid]
                if not entries:
                    del self._entries[key]

    def forget_store(self, target: RepositoryStoreTarget) -> None:
        with self._guard:
            for key in tuple(self._entries):
                if key[0] == str(target.git_dir):
                    del self._entries[key]


observed_object_failures = ObjectFailures()
