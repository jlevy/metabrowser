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
from threading import Event
from typing import Protocol

from pathspec.gitignore import GitIgnoreSpec

from metabrowser.fs_paths import is_visible

# Rebuild the pruning spec once the pattern set has grown by this factor. A
# rebuild costs O(patterns); doing one per `.gitignore` found makes the total
# quadratic in a tree that has many -- which is exactly the tree where pruning
# is worth most.
PRUNE_SPEC_REBUILD_GROWTH = 1.25


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


def load_gitignore(root: Path, *, cancel_event: Event | None = None) -> IgnoreFilter:
    """Load ``.gitignore`` files from *root* and its subdirectories.

    Collects patterns from the root ``.gitignore`` and any nested ``.gitignore``
    files, prefixing nested patterns with their relative directory so that
    ``pathspec`` matches them correctly. Returns ``ignore_none`` if no
    ``.gitignore`` files exist.
    """
    all_lines: list[str] = []

    root_gitignore = root / ".gitignore"
    if root_gitignore.is_file():
        with open(root_gitignore) as f:
            for line in f:
                if cancel_event is not None and cancel_event.is_set():
                    return ignore_none
                all_lines.append(line)

    # Walk for nested .gitignore files, pruning as we go.
    #
    # This is a second full traversal of the tree, before the one that actually
    # indexes it, and unpruned it was the larger of the two: on a real
    # 241,000-file working tree it cost 19-23 s against a 21 s index walk,
    # because it descended into every vendored, built, and hidden directory
    # looking for files that cannot matter. Two prunes remove that, and both
    # are semantics rather than shortcuts.
    #
    # A directory an accumulated pattern already ignores is pruned because git
    # does not read ``.gitignore`` files inside an ignored directory either --
    # its contents are excluded wholesale, so a nested pattern there could not
    # change any answer. Patterns are hierarchical and ``os.walk`` is top-down,
    # so everything governing a directory has been collected before it is
    # reached.
    #
    # A directory this shell will never show is pruned because a pattern found
    # inside it could only govern paths that are themselves never shown. See
    # ``fs_paths.is_visible``: the indexing walk skips these, so collecting
    # ignore rules for them is work spent on rows nobody can see.
    # The spec used for pruning is allowed to lag the patterns collected so far,
    # and that is what keeps it cheap. Rebuilding it on every ``.gitignore``
    # found costs O(patterns) each time -- on a tree with a few hundred of them
    # that dominated the traversal it was meant to save.
    #
    # Lagging is safe in one direction only, which is the direction it lags: a
    # spec with fewer patterns matches fewer paths, so a stale one prunes less
    # than it could and never prunes something a current one would have kept.
    # Pruning less costs a little traversal; pruning wrongly would drop a
    # pattern and change an answer.
    accumulated: GitIgnoreSpec | None = GitIgnoreSpec.from_lines(all_lines) if all_lines else None
    patterns_at_last_rebuild = max(len(all_lines), 1)
    for dirpath, dirnames, filenames in os.walk(root):
        if cancel_event is not None and cancel_event.is_set():
            return ignore_none
        here = Path(dirpath)
        kept: list[str] = []
        for name in dirnames:
            if name == ".git" or not is_visible(name):
                continue
            if accumulated is not None:
                rel = os.path.relpath(str(here / name), str(root))
                if accumulated.match_file(f"{rel}/"):
                    continue
            kept.append(name)
        dirnames[:] = kept
        if dirpath == str(root):
            continue  # already handled above
        if ".gitignore" in filenames:
            rel_dir = os.path.relpath(dirpath, root)
            nested_path = Path(dirpath) / ".gitignore"
            added = 0
            with open(nested_path) as f:
                for line in f:
                    if cancel_event is not None and cancel_event.is_set():
                        return ignore_none
                    stripped = line.strip()
                    # Skip blank lines and comments.
                    if not stripped or stripped.startswith("#"):
                        all_lines.append(line)
                        added += 1
                    else:
                        # Prefix pattern with relative directory for correct matching.
                        all_lines.append(f"{rel_dir}/{stripped}\n")
                        added += 1
            # Rebuild only here, which is once per ``.gitignore`` found --
            # hundreds of times on a large tree, not once per directory.
            # A negation would break the lag's whole safety argument: it makes
            # a larger pattern set match *fewer* paths, so a stale spec could
            # prune a directory the current one would have kept -- and that
            # loses a subtree's rules rather than one file's verdict.
            #
            # None can reach here today, because a nested pattern is prefixed
            # as f"{rel_dir}/{stripped}" and that turns "!keep.log" into the
            # literal "pkg/!keep.log". That prefixing is wrong and predates
            # this code; when it is fixed, this branch is what keeps the prune
            # sound instead of silently becoming unsafe. It costs nothing until
            # then, which is the point of writing it now.
            negated = any(line.lstrip().startswith("!") for line in all_lines[-added:])
            grown = len(all_lines) >= patterns_at_last_rebuild * PRUNE_SPEC_REBUILD_GROWTH
            if negated or grown:
                accumulated = GitIgnoreSpec.from_lines(all_lines)
                patterns_at_last_rebuild = len(all_lines)

    if not all_lines:
        return ignore_none

    log.debug("Loaded gitignore patterns (%s lines) from %s", len(all_lines), root)
    return IgnoreChecker(all_lines)


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
    if mode is IgnoreMode.show_all:
        return ignore_none

    base = load_gitignore(root, cancel_event=cancel_event)
    if base is ignore_none or mode is IgnoreMode.gitignore:
        return base

    # default mode: wrap the base filter to exempt allowlisted directories at any depth.
    def _default_filter(path: str | Path, *, is_dir: bool = False) -> bool:
        if any(part in ALLOWLIST_DIRS for part in Path(path).parts):
            return False
        return base(path, is_dir=is_dir)

    return _default_filter
