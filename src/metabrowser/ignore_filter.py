"""Gitignore-aware path filtering.

Uses ``pathspec.GitIgnoreSpec`` to match paths against gitignore-format patterns.
Adapted from kash's ``ignore_files.py`` for use in the metabrowser and
any other context where directory walks need to skip ignored paths.
"""

from __future__ import annotations

import logging
import os
from enum import StrEnum
from pathlib import Path
from threading import Event, Lock
from typing import Protocol

from pathspec.gitignore import GitIgnoreSpec

log = logging.getLogger(__name__)


class IgnoreMode(StrEnum):
    """How the browser filters paths.

    - ``default``: Apply ``.gitignore`` rules but always show ``.logs/`` and
      ``.state/`` (operational directories).
    - ``gitignore``: Apply ``.gitignore`` rules strictly — no allowlist overrides.
    - ``show_all``: No filtering — show every file and directory.
    """

    default = "default"
    gitignore = "gitignore"
    show_all = "show_all"


# Directories that are shown even when gitignored, under IgnoreMode.default.
ALLOWLIST_DIRS = frozenset({".logs", ".state"})


class IgnoreFilter(Protocol):
    """Callable that returns True if a path should be ignored."""

    def __call__(self, path: str | Path, *, is_dir: bool = False) -> bool: ...


class IgnoreChecker:
    """Check paths against gitignore-format patterns via ``pathspec``."""

    def __init__(self, lines: list[str]) -> None:
        self.lines = lines
        self.spec = GitIgnoreSpec.from_lines(lines)

    @classmethod
    def from_file(cls, path: Path) -> IgnoreChecker:
        """Load patterns from a gitignore-format file."""
        with open(path) as f:
            lines = f.readlines()
        log.debug("Loaded ignore patterns (%s lines) from %s", len(lines), path)
        return cls(lines)

    def matches(self, path: str | Path, *, is_dir: bool = False) -> bool:
        """Return True if *path* matches the ignore spec."""
        path_str = str(path)
        if path_str == ".":
            return False
        # Directories need a trailing slash to match gitignore dir patterns.
        patterns = [path_str]
        if is_dir and not path_str.endswith("/"):
            patterns.append(path_str + "/")
        return any(self.spec.match_file(p) for p in patterns)

    def __call__(self, path: str | Path, *, is_dir: bool = False) -> bool:
        return self.matches(path, is_dir=is_dir)

    def __repr__(self) -> str:
        active = [
            line.strip() for line in self.lines if line.strip() and not line.strip().startswith("#")
        ]
        return f"IgnoreChecker({'; '.join(active)})"


ignore_none: IgnoreFilter = lambda path, *, is_dir=False: False
"""No-op filter that ignores nothing."""


class HierarchicalGitIgnore:
    """Decide paths under one repository root from its ``.gitignore`` files, lazily.

    Git decides a path from the ``.gitignore`` files in the directories above
    it: each file's patterns are relative to its own directory, a deeper file
    overrides a shallower one, and nothing inside an ignored directory can be
    re-included. So a verdict needs only the files on its ancestor chain, and
    this reads each directory's file the first time a path inside that
    directory is checked.

    That removes the eager alternative, a second traversal of the whole tree to
    collect every nested ``.gitignore`` before the indexing walk may start. On
    a real repository it visited 40,832 directories to find 25 files and
    held back the first directory rows for 9-34 s, while the breadth-first
    walk that needs the verdicts reaches every directory before anything inside
    it and so can supply each file just in time.

    The instance caches files and directory verdicts for its lifetime; its
    owner decides how long that is. Calls may come from the walker and from
    request handlers at once, so cache updates are serialized.
    """

    def __init__(self, root: Path) -> None:
        self._root = root
        self._lock = Lock()
        # Directory (relative to root, "" for root) -> its parsed .gitignore.
        self._specs: dict[str, GitIgnoreSpec | None] = {}
        # Directory -> the (directory, spec) chain governing paths inside it.
        self._chains: dict[str, tuple[tuple[str, GitIgnoreSpec], ...]] = {}
        # Directory -> whether the directory itself is ignored.
        self._directory_verdicts: dict[str, bool] = {}

    def __call__(self, path: str | Path, *, is_dir: bool = False) -> bool:
        rel = str(path).replace(os.sep, "/").strip("/")
        if rel in ("", "."):
            return False
        parent = rel.rpartition("/")[0]
        with self._lock:
            if parent and self._directory_ignored(parent):
                return True
            return self._matches(rel, parent, is_dir=is_dir)

    def _matches(self, rel: str, parent: str, *, is_dir: bool) -> bool:
        """Apply the chain above *rel*, deeper files overriding shallower ones."""

        verdict: bool | None = None
        suffix = "/" if is_dir else ""
        for directory, spec in self._chain(parent):
            relative = rel[len(directory) + 1 :] if directory else rel
            result = spec.check_file(relative + suffix)
            if result.include is not None:
                verdict = result.include
        return bool(verdict)

    def _directory_ignored(self, directory: str) -> bool:
        cached = self._directory_verdicts.get(directory)
        if cached is not None:
            return cached
        parts = directory.split("/")
        ignored = False
        for depth in range(1, len(parts) + 1):
            prefix = "/".join(parts[:depth])
            verdict = self._directory_verdicts.get(prefix)
            if verdict is None:
                # An ignored ancestor settles every descendant; git never reads
                # a .gitignore inside it, and neither does this.
                verdict = ignored or self._matches(
                    prefix, "/".join(parts[: depth - 1]), is_dir=True
                )
                self._directory_verdicts[prefix] = verdict
            ignored = verdict
        return ignored

    def _chain(self, directory: str) -> tuple[tuple[str, GitIgnoreSpec], ...]:
        cached = self._chains.get(directory)
        if cached is not None:
            return cached
        pending = [directory]
        chain: tuple[tuple[str, GitIgnoreSpec], ...] = ()
        current = directory
        while current:
            current = current.rpartition("/")[0]
            found = self._chains.get(current)
            if found is not None:
                chain = found
                break
            pending.append(current)
        for pending_directory in reversed(pending):
            spec = self._spec(pending_directory)
            if spec is not None:
                chain = (*chain, (pending_directory, spec))
            self._chains[pending_directory] = chain
        return chain

    def _spec(self, directory: str) -> GitIgnoreSpec | None:
        if directory in self._specs:
            return self._specs[directory]
        path = self._root / directory / ".gitignore" if directory else self._root / ".gitignore"
        spec: GitIgnoreSpec | None = None
        try:
            with open(path, encoding="utf-8", errors="surrogateescape") as f:
                lines = f.readlines()
        except OSError:
            lines = []
        if any(line.strip() and not line.lstrip().startswith("#") for line in lines):
            spec = GitIgnoreSpec.from_lines(lines)
            log.debug("Loaded gitignore patterns (%s lines) from %s", len(lines), path)
        self._specs[directory] = spec
        return spec


def make_ignore_filter(
    root: Path,
    mode: IgnoreMode,
    *,
    cancel_event: Event | None = None,
) -> IgnoreFilter:
    """Build an ``IgnoreFilter`` for the given mode.

    - ``show_all``: returns ``ignore_none``.
    - ``gitignore``: returns a strict gitignore filter.
    - ``default``: returns a gitignore filter that exempts ``ALLOWLIST_DIRS``.
    """
    if mode is IgnoreMode.show_all or (cancel_event is not None and cancel_event.is_set()):
        return ignore_none

    base: IgnoreFilter = HierarchicalGitIgnore(root)
    if mode is IgnoreMode.gitignore:
        return base

    # default mode: wrap the base filter to exempt allowlisted directories at any depth.
    def _default_filter(path: str | Path, *, is_dir: bool = False) -> bool:
        if any(part in ALLOWLIST_DIRS for part in Path(path).parts):
            return False
        return base(path, is_dir=is_dir)

    return _default_filter
