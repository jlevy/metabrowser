"""Whether a Git location's configuration names a textconv driver, kept between requests.

The diff plugin's route lists a comparison and prints its patch in one run (H116), and that
run passes ``--no-textconv``: a driver is a program the configuration names, and the patch
of the whole comparison would run it on every file it applies to, on both sides, past the
page as well. ``--numstat`` never runs one, so such a file with binary content was listed as
binary and never hydrated, and one second a conversion made a page of nine of them time out
(review of #449, H1). Where no driver is named, the patch is the same with and without the
option, and the page is answered from the one run. Where one is, the page's files are diffed
in a run of their own, with their drivers, exactly as before: no attribute is read, so a
named driver costs that run whether or not any file selects it.

The answer is ``git config --list --show-origin -z``'s: any key ``diff.<driver>.textconv``.
It is kept per configuration, which is the directory Git runs in, the policy and arguments
it runs with, and the environment that names configuration files, with the state of every
file Git reads for it: the repository's own and its worktree's, the global files, and the
system file, ``git var GIT_CONFIG_SYSTEM``'s, whether or not each exists, and each file an
include names. A regular file's state is its modification time, size, and inode; a missing
file's is that it is missing; a character device, ``/dev/null`` as a store's reads name
it, is a fixed, empty configuration. The answer is believed while every state is unchanged,
which one ``stat`` each tells.

When it cannot be sure what Git would read, it keeps nothing, and every comparison asks
again (review of #449): a file whose state changed while it was read, one that is neither
regular nor a device, an include written ``%(prefix)/`` or ``~user/``, an
``includeIf.onbranch`` condition, which reads a file or not as the branch moves, a folder
whose Git directory it cannot find, and ``GIT_CONFIG`` in the environment, which points
``git config`` at another file than the one ``git diff`` reads; there it says nothing, so a
driver is taken to be named.
"""

from __future__ import annotations

import asyncio
import os
import stat
import time
from collections import OrderedDict
from dataclasses import dataclass
from pathlib import Path
from typing import Final

from metabrowser.git.process import (
    GitError,
    GitLocation,
    git_environment,
    git_executable,
    run_git_at,
)
from metabrowser.repository_context import read_bounded_text

# Configurations kept. A server reads a few folders and stores; past this the oldest goes.
MAX_KEPT_CONFIGURATIONS: Final = 64

# A file found by the read itself, an include's, is believed unchanged by the read only if
# it was last changed this long before the read began: a file system's times can be as
# coarse as two seconds.
_SETTLED_NS: Final = 2_000_000_000

# A `.git` file names the Git directory in a line; one far longer is not one.
_MAX_GITFILE_BYTES: Final = 4096

type _State = tuple[str, int, int, int] | tuple[str, int] | None
type _Stamp = tuple[tuple[str, _State], ...]
type _Key = tuple[str, ...]


class _Unsure(Exception):
    """What Git would read cannot be told, so nothing is kept."""


@dataclass(frozen=True, slots=True)
class _Kept:
    named: bool
    stamp: _Stamp


_KEPT: OrderedDict[_Key, _Kept] = OrderedDict()
# The system file each Git and environment reads: a path, or None for none.
_SYSTEM: dict[tuple[str, ...], Path | None] = {}


def _cwd(location: GitLocation) -> Path:
    if location.target is not None:
        return location.target.git_dir
    assert location.cwd is not None
    return location.cwd


def _environment(location: GitLocation) -> dict[str, str]:
    return git_environment(location.read_policy, target=location.target)


def _key(location: GitLocation, env: dict[str, str]) -> _Key:
    named = sorted(
        f"{name}={value}"
        for name, value in env.items()
        if name.startswith("GIT_CONFIG") or name in {"HOME", "XDG_CONFIG_HOME"}
    )
    return (str(_cwd(location)), location.read_policy.name, *location.config_args, "", *named)


def _state(path: Path) -> _State:
    try:
        status = os.stat(path)
    except (FileNotFoundError, NotADirectoryError):
        return None
    except OSError as exc:
        raise _Unsure(f"{path} cannot be read: {exc}") from exc
    if stat.S_ISREG(status.st_mode):
        return ("file", status.st_mtime_ns, status.st_size, status.st_ino)
    if stat.S_ISCHR(status.st_mode):
        return ("device", status.st_rdev)
    raise _Unsure(f"{path} is neither a file nor a device")


def _stamp(paths: set[Path]) -> _Stamp:
    return tuple((str(path), _state(path)) for path in sorted(paths))


def _git_dirs(location: GitLocation) -> tuple[Path, Path]:
    """The repository's own Git directory and its worktree's, which hold ``config`` and
    ``config.worktree``: one and the same for a store and for a main worktree."""
    if location.target is not None:
        return location.target.git_dir, location.target.git_dir
    dot = _cwd(location) / ".git"
    if dot.is_dir():
        worktree = dot
    else:
        text = read_bounded_text(dot, _MAX_GITFILE_BYTES)
        if text is None or not text.startswith("gitdir: "):
            raise _Unsure(f"{dot} names no Git directory")
        worktree = (dot.parent / text[len("gitdir: ") :].strip()).resolve()
    common = worktree
    named = worktree / "commondir"
    if named.exists():
        text = read_bounded_text(named, _MAX_GITFILE_BYTES)
        if text is None:
            raise _Unsure(f"{named} cannot be read")
        common = (worktree / text.strip()).resolve()
    return common, worktree


def _global_files(env: dict[str, str]) -> set[Path]:
    """The global files Git reads, whether or not they exist yet."""
    chosen = env.get("GIT_CONFIG_GLOBAL")
    if chosen is not None:
        return {Path(chosen)}
    home = env.get("HOME", "")
    xdg = env.get("XDG_CONFIG_HOME") or (f"{home}/.config" if home else "")
    files = {Path(home) / ".gitconfig"} if home else set()
    return files | {Path(xdg) / "git" / "config"} if xdg else files


async def _system_file(location: GitLocation, env: dict[str, str]) -> Path | None:
    """The system file this Git reads under *env*, or None when it reads none."""
    if env.get("GIT_CONFIG_NOSYSTEM", "").lower() in {"1", "true", "yes", "on"}:
        return None
    key = (
        str(git_executable()),
        env.get("GIT_CONFIG_SYSTEM", ""),
        env.get("GIT_CONFIG_NOSYSTEM", ""),
    )
    if key not in _SYSTEM:
        try:
            out = await run_git_at(["var", "GIT_CONFIG_SYSTEM"], location)
        except GitError as exc:
            # It names none, and says so by failing, when GIT_CONFIG_NOSYSTEM is set.
            if "GIT_CONFIG_NOSYSTEM" not in env:
                raise _Unsure("git var named no system file") from exc
            _SYSTEM[key] = None
        else:
            _SYSTEM[key] = Path(os.fsdecode(out.rstrip(b"\n"))) if out.strip() else None
    return _SYSTEM[key]


def _read(out: bytes, cwd: Path, env: dict[str, str]) -> tuple[bool, set[Path]]:
    """Whether the listing names a driver, and the files it was read from or includes.

    With ``-z`` each entry is its origin, a NUL, then its key, a newline, its value, and a
    NUL. Git lowercases a key's section and name; an include's path is relative to the file
    that holds it.
    """
    fields = out.split(b"\0")
    named = False
    files: set[Path] = set()
    home = env.get("HOME", "")
    for origin, entry in zip(fields[0::2], fields[1::2], strict=False):
        key, _, value = entry.partition(b"\n")
        name = key.decode("utf-8", "replace")
        holder: Path | None = None
        if origin.startswith(b"file:"):
            holder = cwd / os.fsdecode(origin[len(b"file:") :])
            files.add(holder)
        if name.startswith("diff.") and name.endswith(".textconv") and name.count(".") >= 2:
            named = True
        if name.startswith("includeif.onbranch:"):
            raise _Unsure("an include follows the branch")
        included = name == "include.path" or (
            name.startswith("includeif.") and name.endswith(".path")
        )
        if not included or not value:
            continue
        path = os.fsdecode(value)
        if path.startswith("%(") or (path.startswith("~") and not path.startswith("~/")):
            raise _Unsure(f"an include is named {path!r}")
        if path.startswith("~/"):
            if not home:
                raise _Unsure("an include names a home there is none of")
            path = home + path[1:]
        target = Path(path)
        if not target.is_absolute():
            if holder is None:
                raise _Unsure("a relative include held by no file")
            target = holder.parent / target
        files.add(target)
    return named, files


async def textconv_named(location: GitLocation) -> bool | None:
    """Whether the kept answer for *location* names a driver, or None when none is kept."""
    kept = _KEPT.get(_key(location, _environment(location)))
    if kept is None:
        return None
    paths = {Path(path) for path, _state in kept.stamp}
    try:
        current = await asyncio.to_thread(_stamp, paths)
    except _Unsure:
        return None
    return kept.named if current == kept.stamp else None


async def read_textconv_named(location: GitLocation) -> bool | None:
    """Ask Git whether *location*'s configuration names a driver, and keep a sure answer.

    None when Git could not say, which a caller takes as a driver that may be named.
    """
    env = _environment(location)
    if "GIT_CONFIG" in env:
        return None
    key = _key(location, env)
    try:
        common, worktree = await asyncio.to_thread(_git_dirs, location)
        system = await _system_file(location, env)
        known = {common / "config", worktree / "config.worktree", *_global_files(env)}
        if system is not None:
            known.add(system)
        before = await asyncio.to_thread(_stamp, known)
    except _Unsure:
        before = None
    started_ns = time.time_ns()
    try:
        out = await run_git_at(["config", "--list", "--show-origin", "-z"], location)
    except GitError:
        return None
    try:
        named, files = _read(out, _cwd(location), env)
    except _Unsure:
        return _read_named_only(out)
    if before is not None:
        try:
            after = await asyncio.to_thread(_stamp, {Path(path) for path, _ in before} | files)
        except _Unsure:
            return named
        if _unchanged(before, after, started_ns):
            _KEPT[key] = _Kept(named, after)
            _KEPT.move_to_end(key)
            while len(_KEPT) > MAX_KEPT_CONFIGURATIONS:
                _KEPT.popitem(last=False)
    return named


def _unchanged(before: _Stamp, after: _Stamp, started_ns: int) -> bool:
    """Whether nothing Git read changed while it read: every file known beforehand is as it
    was, and every file the read itself found was last changed well before it began."""
    known = dict(before)
    for path, state in after:
        if path in known:
            if known[path] != state:
                return False
        elif state is not None and state[0] == "file" and state[1] > started_ns - _SETTLED_NS:
            return False
    return True


def _read_named_only(out: bytes) -> bool:
    fields = out.split(b"\0")
    return any(
        name.startswith(b"diff.") and name.endswith(b".textconv")
        for name in (entry.partition(b"\n")[0] for entry in fields[1::2])
    )


def forget() -> None:
    """Drop every kept answer, for a test that counts the processes of a cold one."""
    _KEPT.clear()
    _SYSTEM.clear()


__all__ = ["MAX_KEPT_CONFIGURATIONS", "forget", "read_textconv_named", "textconv_named"]
