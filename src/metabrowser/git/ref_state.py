"""The state of a repository's refs, named from the filesystem without running Git.

The history routes answer from refs: ``/api/git/refs`` lists them, ``/api/git/summary``
counts the commits they reach, and ``/api/git/log`` walks those commits with the refs as
decorations. Each answer used to spawn several Git processes per request, 14 to 23 ms
apiece from the server's interpreter, so the Commits panel waited 177 ms for its first log
page and 186 ms for a 67-byte summary (measured 2026-11-11 on this repository at load
15, ``docs/project/research/research-2026-11-11-ui-apparent-performance.md``). Between
two requests the refs almost never move, so :func:`ref_state` names their state with one
``stat`` per file instead, and the routes keep their answers under that name
(:mod:`metabrowser.git.route_memo`, and the scope and first-page reuse in
:mod:`metabrowser.git.history`).

What the state covers is everything those answers read beyond the object graph, which a
commit ID makes immutable:

- ``HEAD`` of the location's own Git directory, which a linked worktree has apart from
  the repository it belongs to;
- every entry under ``refs/`` and ``reftable/`` of the common directory, and of a linked
  worktree's own, where a reftable repository keeps that worktree's ``HEAD`` and its
  per-worktree refs;
- ``packed-refs``;
- ``config`` and ``config.worktree``, which name a branch's upstream;
- ``shallow`` and ``info/grafts``, which bound the walk. ``refs/replace/`` is under
  ``refs/``.

It does not cover other worktrees' ``HEAD`` files, so no answer may read them: the
summary counts the scope the log walks rather than ``rev-list --all``, which adds every
worktree's ``HEAD``. ``tests/test_git_route_memo.py`` moves each input above once, served
from a main and from a linked worktree, with the files backend and with reftable, and
writes the common files from the main worktree; ``packed-refs`` is moved with the files
backend only, the one that has it.

Git updates a ref by writing a lock file and renaming it over the ref, so the ref's inode
changes even when its time and size do not, and its directory's entry changes with it.
Each entry contributes its path, inode, size, and modification and change times, so an
in-place write that some other tool makes moves the state too.

A pinned revision names its store, whose refs a refresh moves. A pin's default history is
the pin alone and cannot move, but its ``scope=all`` history and its refs list do.

What the state does not cover, and the answers therefore do not notice until something it
does cover moves: Git configuration outside the repository (the reader's global and system
files) and an object that disappears from under a ref that still names it. Neither
changes which commits the refs name.

The Git directories are asked of Git once per location and remembered with the served
root's ``.git`` entry: its inode and type, and its text when it is a file. A ``.git``
replaced in place, as a folder deleted and cloned again is, is asked about again.

Reading is bounded. A repository with more than :data:`MAX_REF_ENTRIES` entries under its
ref directories gets no state, and its routes answer uncached as they did before; that
verdict is remembered for :data:`~metabrowser.settings.GIT_REPO_INFO_TTL_S`, so such a
repository is walked once in that time rather than on every request. The walk runs off
the event loop either way.
"""

from __future__ import annotations

import asyncio
import hashlib
import logging
import os
import stat
import time
from collections import OrderedDict
from dataclasses import dataclass, replace
from pathlib import Path

from metabrowser.git.process import (
    GitError,
    GitLocation,
    RepositoryStoreTarget,
    failure_detail,
    run_git_at,
)
from metabrowser.paths_safe import register_root_callback
from metabrowser.settings import GIT_REPO_INFO_TTL_S

log = logging.getLogger(__name__)

# Entries walked under the ref directories before the state gives up. Measured 2026-11-12
# on APFS with CPython 3.14.7 at a load average of 5.1 to 5.6: the median of 11 walks, and
# of 5 runs of `git for-each-ref`, on a repository holding N loose refs (packed refs cost
# nothing to walk):
#
#   N loose refs (entries)          0 (3)   1,000 (1,102)   4,000 (4,102)   16,000 (16,102)
#   walk, ms                          0.1             6.2            19.3              75.4
#   one git for-each-ref, ms         13.7            67.9           221.7             911.4
#
# About 4.7 microseconds an entry. At every size the walk costs a tenth or less of the
# one Git process the cheapest of these routes runs, so the bound is not where it stops
# paying; it caps how long a request holds the interpreter in its worker thread, at about
# 75 ms. A repository past it is walked once per identity-cache period, not per request.
MAX_REF_ENTRIES = 16_384

# Locations whose Git directories are remembered. A server serves one folder, or one pin
# at a time of one store, so this holds a handful; it is bounded because tests make
# repositories by the hundred.
_MAX_KNOWN_LOCATIONS = 64

# The files the history answers read, in the common directory and in the location's own.
_COMMON_FILES = ("packed-refs", "config", "shallow", "info/grafts")
_OWN_FILES = ("HEAD", "config.worktree")
# The ref trees, walked in the common directory and, for a linked worktree, in its own.
_TREES = ("refs", "reftable")


@dataclass(frozen=True, slots=True)
class _Known:
    """Where one location's refs live, and what was true when that was asked."""

    own: Path
    common: Path
    # The served root's `.git` entry when the directories were asked for; None for a store.
    marker: bytes | None
    # Until when (monotonic) the ref trees are known to hold more than one state may walk.
    unbounded_until: float = 0.0


_KNOWN: OrderedDict[str, _Known] = OrderedDict()


def clear_ref_state_cache() -> None:
    """Forget every location's Git directories, as a served-root change requires."""

    _KNOWN.clear()


class _TooManyRefs(Exception):
    """The ref directories hold more entries than one state may stat."""


def _git_marker(root: Path) -> bytes:
    """What identifies the served root's ``.git`` entry: its inode and type, and its text.

    A directory's times are left out, since Git writes inside it on most commands; its
    inode changes only when it is replaced. A file is a linked worktree's pointer, and its
    text says which Git directory it names.
    """

    path = root / ".git"
    try:
        found = os.stat(path, follow_symlinks=False)
    except OSError:
        return b"-"
    marker = f"{found.st_dev}:{found.st_ino}:{stat.S_IFMT(found.st_mode)}".encode()
    if stat.S_ISREG(found.st_mode):
        try:
            with path.open("rb") as handle:
                marker += b"\0" + handle.read(4096)
        except OSError:
            marker += b"\0unreadable"
    return marker


async def _known(location: GitLocation) -> _Known | None:
    """The location's Git directories, asked of Git once and then remembered."""

    marker = None if location.cwd is None else await asyncio.to_thread(_git_marker, location.cwd)
    known = _KNOWN.get(location.identity)
    if known is not None and known.marker == marker:
        _KNOWN.move_to_end(location.identity)
        return known
    if isinstance(location.target, RepositoryStoreTarget):
        found = _Known(own=location.target.git_dir, common=location.target.git_dir, marker=None)
    else:
        cwd = location.cwd
        if cwd is None:
            raise TypeError("a location without a working directory is a store")
        try:
            raw = await run_git_at(
                ["rev-parse", "--absolute-git-dir", "--git-common-dir"], location
            )
        except GitError as exc:
            log.debug("git ref state: no Git directory: %s", failure_detail(exc))
            return None
        lines = os.fsdecode(raw).splitlines()
        if len(lines) != 2 or not lines[0] or not lines[1]:
            return None
        # ``--git-common-dir`` is relative to the working directory unless it is absolute;
        # joining keeps an absolute answer as it is.
        found = _Known(own=Path(lines[0]), common=(cwd / lines[1]).resolve(), marker=marker)
    _KNOWN[location.identity] = found
    _KNOWN.move_to_end(location.identity)
    while len(_KNOWN) > _MAX_KNOWN_LOCATIONS:
        _KNOWN.popitem(last=False)
    return found


def _signature(path: str) -> bytes:
    """One file's contribution: what a ``stat`` says of it, or that it is absent."""

    try:
        found = os.stat(path, follow_symlinks=False)
    except OSError:
        return b"-"
    return (
        f"{found.st_ino}:{found.st_size}:{found.st_mtime_ns}:{found.st_ctime_ns}:{found.st_mode}"
    ).encode()


def _walk(root: str, digest: hashlib.blake2b, budget: list[int]) -> None:
    """Fold every entry under *root* into *digest*, in a stable order.

    Strings and ``DirEntry.stat`` throughout: per entry, a ``pathlib`` path and its
    ``relative_to`` cost three times the ``stat`` (review B of #368).
    """

    prefix = len(root) + 1
    stack = [root]
    while stack:
        directory = stack.pop()
        try:
            with os.scandir(directory) as listing:
                entries = sorted(listing, key=lambda entry: entry.name)
        except OSError:
            digest.update(b"\0dir-unreadable\0")
            digest.update(os.fsencode(directory[prefix:]))
            continue
        for entry in entries:
            budget[0] -= 1
            if budget[0] < 0:
                raise _TooManyRefs
            try:
                found = entry.stat(follow_symlinks=False)
            except OSError:
                signature = b"-"
                is_dir = False
            else:
                signature = (
                    f"{found.st_ino}:{found.st_size}:{found.st_mtime_ns}:"
                    f"{found.st_ctime_ns}:{found.st_mode}"
                ).encode()
                is_dir = stat.S_ISDIR(found.st_mode)
            digest.update(b"\0")
            digest.update(os.fsencode(entry.path[prefix:]))
            digest.update(b"\0")
            digest.update(signature)
            if is_dir:
                stack.append(entry.path)


def _read_state(known: _Known) -> str | None:
    """The digest of every file and ref entry the history answers read.

    None when the remembered Git directory has no ``HEAD``; :class:`_TooManyRefs` when the
    ref directories hold more than one state may stat.
    """

    digest = hashlib.blake2b(digest_size=16)
    own = os.fspath(known.own)
    common = os.fspath(known.common)
    try:
        # HEAD's text is read as well as stated: it is a few bytes, and what it says is
        # the one input whose rewrite most often keeps its size.
        with open(os.path.join(own, "HEAD"), "rb") as handle:
            digest.update(handle.read(4096))
    except OSError:
        # The remembered directory is gone: the repository was moved or made again.
        return None
    budget = [MAX_REF_ENTRIES]
    directory_sets: list[tuple[str, tuple[str, ...]]] = [(common, _COMMON_FILES)]
    if own != common:
        directory_sets.append((own, ()))
    for name in _OWN_FILES:
        digest.update(b"\0own\0")
        digest.update(name.encode())
        digest.update(_signature(os.path.join(own, name)))
    for base, files in directory_sets:
        digest.update(b"\0base\0")
        digest.update(b"own" if base == own else b"common")
        for name in files:
            digest.update(b"\0file\0")
            digest.update(name.encode())
            digest.update(_signature(os.path.join(base, name)))
        for name in _TREES:
            digest.update(b"\0tree\0")
            digest.update(name.encode())
            tree = os.path.join(base, name)
            signature = _signature(tree)
            digest.update(signature)
            if signature != b"-" and os.path.isdir(tree):
                _walk(tree, digest, budget)
    return digest.hexdigest()


async def ref_state(location: GitLocation) -> str | None:
    """Name the current state of *location*'s refs, or None when it cannot be named.

    Two calls return the same string exactly when nothing this module covers changed
    between them. None means the routes must answer without keeping anything: the
    location has no readable Git directory, or more ref entries than one state may stat.
    """

    known = await _known(location)
    if known is None:
        return None
    if known.unbounded_until > time.monotonic():
        return None
    try:
        state = await asyncio.to_thread(_read_state, known)
    except _TooManyRefs:
        _KNOWN[location.identity] = replace(
            known, unbounded_until=time.monotonic() + GIT_REPO_INFO_TTL_S
        )
        return None
    if state is None:
        # Ask Git again next time, in case the repository was made again elsewhere.
        _KNOWN.pop(location.identity, None)
    return state


register_root_callback(clear_ref_state_cache)


__all__ = [
    "MAX_REF_ENTRIES",
    "clear_ref_state_cache",
    "ref_state",
]
