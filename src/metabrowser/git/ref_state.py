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
- every entry under ``refs/`` of the common directory, and of a linked worktree's own;
- ``packed-refs``, and ``reftable/`` for a repository that stores refs that way;
- ``config`` and ``config.worktree``, which name a branch's upstream;
- ``shallow`` and ``info/grafts``, which bound the walk. ``refs/replace/`` is under
  ``refs/``.

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

Reading is bounded. A repository with more than :data:`MAX_REF_ENTRIES` entries under its
ref directories gets no state, and its routes answer uncached as they did before; the walk
runs off the event loop either way.
"""

from __future__ import annotations

import asyncio
import hashlib
import logging
import os
from collections import OrderedDict
from dataclasses import dataclass
from pathlib import Path

from metabrowser.git.process import (
    GitError,
    GitLocation,
    RepositoryStoreTarget,
    failure_detail,
    run_git_at,
)
from metabrowser.paths_safe import register_root_callback

log = logging.getLogger(__name__)

# Entries walked under the ref directories before the state gives up. Measured 2026-11-11:
# this repository's common directory holds 50 entries under ``refs/`` beside a 41 KB
# ``packed-refs``, and a fresh clone packs its refs, so loose refs are what a reader
# created since. Sixteen thousand stats take a few milliseconds off the loop; past that
# the walk would cost what the Git processes it replaces cost.
MAX_REF_ENTRIES = 16_384

# Locations whose Git directories are remembered. A server serves one folder, or one pin
# at a time of one store, so this holds a handful; it is bounded because tests make
# repositories by the hundred.
_MAX_KNOWN_LOCATIONS = 64

# The files beside ``refs/`` that the history answers read.
_COMMON_FILES = ("packed-refs", "config", "shallow", "info/grafts")
_OWN_FILES = ("HEAD", "config.worktree")
_COMMON_TREES = ("refs", "reftable")


@dataclass(frozen=True, slots=True)
class _GitDirectories:
    """Where one location's refs live: its own Git directory and the common one."""

    own: Path
    common: Path


_DIRECTORIES: OrderedDict[str, _GitDirectories] = OrderedDict()


def clear_ref_state_cache() -> None:
    """Forget every location's Git directories, as a served-root change requires."""

    _DIRECTORIES.clear()


class _TooManyRefs(Exception):
    """The ref directories hold more entries than one state may stat."""


async def _directories(location: GitLocation) -> _GitDirectories | None:
    """The location's Git directories, asked of Git once and then remembered."""

    known = _DIRECTORIES.get(location.identity)
    if known is not None:
        _DIRECTORIES.move_to_end(location.identity)
        return known
    if isinstance(location.target, RepositoryStoreTarget):
        found = _GitDirectories(own=location.target.git_dir, common=location.target.git_dir)
    else:
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
        own = Path(lines[0])
        # ``--git-common-dir`` is relative to the working directory unless it is absolute;
        # joining keeps an absolute answer as it is.
        base = location.cwd if location.cwd is not None else own
        found = _GitDirectories(own=own, common=(base / lines[1]).resolve())
    _DIRECTORIES[location.identity] = found
    while len(_DIRECTORIES) > _MAX_KNOWN_LOCATIONS:
        _DIRECTORIES.popitem(last=False)
    return found


def _signature(path: Path) -> bytes:
    """One entry's contribution: what a ``stat`` says of it, or that it is absent."""

    try:
        found = os.stat(path, follow_symlinks=False)
    except OSError:
        return b"-"
    return (
        f"{found.st_ino}:{found.st_size}:{found.st_mtime_ns}:{found.st_ctime_ns}:{found.st_mode}"
    ).encode()


def _walk(root: Path, digest: hashlib.blake2b, budget: list[int]) -> None:
    """Fold every entry under *root* into *digest*, in a stable order."""

    stack = [root]
    while stack:
        directory = stack.pop()
        try:
            with os.scandir(directory) as listing:
                entries = sorted(listing, key=lambda entry: entry.name)
        except OSError:
            digest.update(b"\0dir-unreadable\0")
            digest.update(os.fsencode(directory))
            continue
        for entry in entries:
            budget[0] -= 1
            if budget[0] < 0:
                raise _TooManyRefs
            path = Path(entry.path)
            digest.update(b"\0")
            digest.update(os.fsencode(path.relative_to(root)))
            digest.update(b"\0")
            digest.update(_signature(path))
            if entry.is_dir(follow_symlinks=False):
                stack.append(path)


def _read_state(directories: _GitDirectories) -> str | None:
    """The digest of every file and ref entry the history answers read.

    None when the remembered Git directory has no ``HEAD``; :class:`_TooManyRefs` when the
    ref directories hold more than one state may stat.
    """

    digest = hashlib.blake2b(digest_size=16)
    head = directories.own / "HEAD"
    try:
        # HEAD's text is read as well as stated: it is a few bytes, and what it says is
        # the one input whose rewrite most often keeps its size.
        with head.open("rb") as handle:
            digest.update(handle.read(4096))
    except OSError:
        # The remembered directory is gone: the repository was moved or made again.
        return None
    budget = [MAX_REF_ENTRIES]
    directory_sets: list[tuple[Path, tuple[str, ...], tuple[str, ...]]] = [
        (directories.common, _COMMON_FILES, _COMMON_TREES)
    ]
    if directories.own != directories.common:
        directory_sets.append((directories.own, (), ("refs",)))
    for name in _OWN_FILES:
        digest.update(b"\0own\0")
        digest.update(name.encode())
        digest.update(_signature(directories.own / name))
    for base, files, trees in directory_sets:
        for name in files:
            digest.update(b"\0file\0")
            digest.update(name.encode())
            digest.update(_signature(base / name))
        for name in trees:
            digest.update(b"\0tree\0")
            digest.update(name.encode())
            tree = base / name
            digest.update(_signature(tree))
            if tree.is_dir():
                _walk(tree, digest, budget)
    return digest.hexdigest()


async def ref_state(location: GitLocation) -> str | None:
    """Name the current state of *location*'s refs, or None when it cannot be named.

    Two calls return the same string exactly when nothing this module covers changed
    between them. None means the routes must answer without keeping anything: the
    location has no readable Git directory, or more ref entries than one state may stat.
    """

    directories = await _directories(location)
    if directories is None:
        return None
    try:
        state = await asyncio.to_thread(_read_state, directories)
    except _TooManyRefs:
        return None
    if state is None:
        # Ask Git again next time, in case the repository was made again elsewhere.
        _DIRECTORIES.pop(location.identity, None)
    return state


register_root_callback(clear_ref_state_cache)


__all__ = [
    "MAX_REF_ENTRIES",
    "clear_ref_state_cache",
    "ref_state",
]
