"""Whether a Git location's configuration names a textconv driver, kept between requests.

The diff plugin's route lists a comparison and prints its patch in one run (H116), and that
run passes ``--no-textconv``: a driver is a program the configuration names, and the patch
of the whole comparison would run it on every file it applies to, on both sides, past the
page as well. ``--numstat`` never runs one, so such a file with binary content was listed as
binary and never hydrated, and one second a conversion made a page of nine of them time out
in review (fixed in ``f0e9b5796``). Where no driver is named, the patch is the same with and
without the option, and the page is answered from the one run. Where one is, the page's
files are diffed in a run of their own, with their drivers, exactly as before: no attribute
is read, so a named driver costs that run whether or not any file selects it.
``diff.submodule=diff`` counts as a driver too: Git diffs each changed submodule's files in
a child ``git diff`` of the submodule's own, which honors the submodule's drivers whatever
the parent run passes. The last value listed is the one Git uses, so at a store target,
whose reads set ``diff.submodule=short`` on the command line (``GitLocation.config_args``),
it never counts.

The answer is ``git config --list --show-origin -z``'s: any key ``diff.<driver>.textconv``,
or ``diff.submodule`` set to ``diff``. It is kept per configuration, which is the directory
Git runs in, the policy and arguments it runs with, and the environment that names
configuration files, with the state of every file Git reads for it: the repository's own and
its worktree's, the global files, and the system file, whether or not each exists, and each
file an include names. A regular file's state is its modification time, size, and inode; a
missing file's is that it is missing; a character device, ``/dev/null`` as a store's reads
name it, is a fixed, empty configuration. The answer is believed while every state is
unchanged, which one ``stat`` each tells. A kept answer that is used moves to the back of
the queue of :data:`MAX_KEPT_CONFIGURATIONS`, so the oldest unused one goes first.

The system file is the one ``git var GIT_CONFIG_SYSTEM`` names, asked once per Git and
environment, unless ``GIT_CONFIG_NOSYSTEM`` is true as Git reads a boolean. Git before 2.42
has no such variable: it is asked instead to list its system file alone, which it names in
its refusal when the file is missing and in each entry's origin when the file has any. Such
a Git's first comparison of a server costs those two processes more, and its answers are
kept as a newer Git's are; a system file it reads but holds no entry cannot be placed, so
nothing such a Git reads is kept, and each comparison asks ``git config`` again, three
processes where a kept answer takes two.

When it cannot be sure what Git would read, it keeps nothing, and every comparison asks
again: a file whose state changed while it was read, one that is neither regular nor a
device, an include written ``%(prefix)/`` or ``~user/``, an ``includeIf.onbranch``
condition, which reads a file or not as the branch moves, a folder whose Git directory it
cannot find, a system file it cannot place, and ``GIT_CONFIG`` in the environment, which
points ``git config`` at another file than the one ``git diff`` reads; there it says
nothing, so a driver is taken to be named.
"""

from __future__ import annotations

import asyncio
import dataclasses
import os
import re
import stat
import time
from collections import OrderedDict
from dataclasses import dataclass
from pathlib import Path
from typing import Final

from metabrowser.git.process import (
    GitCommandError,
    GitError,
    GitLocation,
    git_environment,
    git_executable,
    run_git_at,
)
from metabrowser.repository_context import read_bounded_text

# Configurations kept. A server reads a few folders and stores; past this the one used least
# recently goes.
MAX_KEPT_CONFIGURATIONS: Final = 64

# How a Git before 2.42 names a system file it lists alone and cannot find, in the C locale.
_MISSING_FILE: Final = re.compile(r"unable to read config file '(.+)': No such file or directory")

# An integer as Git reads one in a boolean, `strtoimax` with base 0 and a unit after it.
_GIT_INTEGER: Final = re.compile(
    r"[ \t\n\v\f\r]*[-+]?(0[xX][0-9a-fA-F]+|0[0-7]*|[1-9][0-9]*)([kKmMgG]?)"
)
_UNITS: Final = {"": 1, "k": 1 << 10, "m": 1 << 20, "g": 1 << 30}
_INT_MAX: Final = (1 << 31) - 1

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


class _Unplaced(_Unsure):
    """This Git reads a system file it gives no name for, which stays so for its life."""


@dataclass(frozen=True, slots=True)
class _Kept:
    named: bool
    stamp: _Stamp


_KEPT: OrderedDict[_Key, _Kept] = OrderedDict()
# The system file each Git and environment reads: a path, or None for none.
_SYSTEM: dict[tuple[str, ...], Path | None] = {}
# The Gits and environments whose system file cannot be placed.
_UNPLACED: set[tuple[str, ...]] = set()


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


def _surely_true(value: str | None) -> bool:
    """Whether Git reads *value*, as it reads ``GIT_CONFIG_NOSYSTEM``, as true.

    Git's boolean is ``true``, ``yes`` or ``on`` in any case, or a nonzero integer in C's
    ``strtoimax`` with base 0 and an optional ``k``, ``m`` or ``g``; the empty string,
    ``false``, ``no``, ``off`` and zero are false, and Git refuses anything else. Only a
    true value is taken to mean no system file: any other leaves the file to be found, which
    a Git that refuses the value then fails to do, and nothing is kept.
    """
    if value is None:
        return False
    if value.lower() in {"true", "yes", "on"}:
        return True
    number = _GIT_INTEGER.fullmatch(value)
    if number is None:
        return False
    digits, unit = number.groups()
    if digits[:2] in {"0x", "0X"}:
        magnitude = int(digits[2:], 16)
    elif digits.startswith("0"):
        magnitude = int(digits, 8)
    else:
        magnitude = int(digits)
    return 0 < magnitude * _UNITS[unit.lower()] <= _INT_MAX


async def _system_file(location: GitLocation, env: dict[str, str]) -> Path | None:
    """The system file this Git reads under *env*, or None when it reads none."""
    if _surely_true(env.get("GIT_CONFIG_NOSYSTEM")):
        return None
    key = (
        str(git_executable()),
        env.get("GIT_CONFIG_SYSTEM", ""),
        env.get("GIT_CONFIG_NOSYSTEM", ""),
    )
    if key in _UNPLACED:
        raise _Unplaced("this Git reads a system file it gives no name for")
    if key not in _SYSTEM:
        try:
            out = await run_git_at(["var", "GIT_CONFIG_SYSTEM"], location)
        except GitCommandError:
            # Git before 2.42 has no such variable.
            try:
                _SYSTEM[key] = await _system_file_listed(location)
            except _Unplaced:
                _UNPLACED.add(key)
                raise
        except GitError as exc:
            raise _Unsure("git var did not answer") from exc
        else:
            _SYSTEM[key] = Path(os.fsdecode(out.rstrip(b"\n"))) if out.strip() else None
    return _SYSTEM[key]


async def _system_file_listed(location: GitLocation) -> Path:
    """The system file a Git before 2.42 reads, from a listing of that file alone.

    Missing, it is named in Git's refusal, which the C locale keeps in English. With entries,
    it is each entry's origin, includes not followed. With none, it cannot be placed.
    """
    policy = location.read_policy
    english = dataclasses.replace(policy, extra_env={**(policy.extra_env or {}), "LC_ALL": "C"})
    try:
        out = await run_git_at(
            ["config", "--system", "--list", "--show-origin", "-z"], location, policy=english
        )
    except GitCommandError as exc:
        missing = _MISSING_FILE.search(exc.stderr_summary)
        if missing is None or "�" in missing.group(1):
            raise _Unsure("git config --system named no system file") from exc
        return _cwd(location) / missing.group(1)
    except GitError as exc:
        raise _Unsure("git config --system failed") from exc
    origin = out.split(b"\0", 1)[0]
    if not origin.startswith(b"file:"):
        raise _Unplaced("the system file holds no entry that names it")
    return _cwd(location) / os.fsdecode(origin[len(b"file:") :])


def _read(out: bytes, cwd: Path, env: dict[str, str]) -> tuple[bool, set[Path]]:
    """Whether the listing names a driver, and the files it was read from or includes.

    With ``-z`` each entry is its origin, a NUL, then its key, a newline, its value, and a
    NUL. Git lowercases a key's section and name; an include's path is relative to the file
    that holds it.
    """
    fields = out.split(b"\0")
    named = False
    # The last listed value is the one Git uses: the command line's comes after the files'.
    submodule_diff = False
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
        if name == "diff.submodule":
            submodule_diff = value.strip().lower() == b"diff"
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
    return named or submodule_diff, files


def kept_textconv_named(location: GitLocation) -> bool | None:
    """The answer kept for *location*, unchecked, or None when none is kept.

    It costs no file system call, so a caller can decide what to start before it checks."""
    kept = _KEPT.get(_key(location, _environment(location)))
    return None if kept is None else kept.named


async def textconv_named(location: GitLocation) -> bool | None:
    """Whether the kept answer for *location* names a driver, or None when none is kept."""
    key = _key(location, _environment(location))
    kept = _KEPT.get(key)
    if kept is None:
        return None
    paths = {Path(path) for path, _state in kept.stamp}
    try:
        current = await asyncio.to_thread(_stamp, paths)
    except _Unsure:
        return None
    if current != kept.stamp:
        return None
    if key in _KEPT:
        _KEPT.move_to_end(key)
    return kept.named


async def textconv_answer(location: GitLocation) -> bool | None:
    """The kept answer for *location* while it holds, else Git's (:func:`read_textconv_named`)."""
    kept = await textconv_named(location)
    return kept if kept is not None else await read_textconv_named(location)


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
            _keep(key, _Kept(named, after))
    return named


def _keep(key: _Key, kept: _Kept) -> None:
    """Keep *kept* as the most recently used answer, and let the least recently used go."""
    _KEPT[key] = kept
    _KEPT.move_to_end(key)
    while len(_KEPT) > MAX_KEPT_CONFIGURATIONS:
        _KEPT.popitem(last=False)


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
    entries = [entry.partition(b"\n") for entry in fields[1::2]]
    submodule = [value for name, _, value in entries if name == b"diff.submodule"]
    return any(
        name.startswith(b"diff.") and name.endswith(b".textconv") for name, _, _ in entries
    ) or bool(submodule and submodule[-1].strip().lower() == b"diff")


def forget() -> None:
    """Drop every kept answer, for a test that counts the processes of a cold one."""
    _KEPT.clear()
    _SYSTEM.clear()
    _UNPLACED.clear()


__all__ = [
    "MAX_KEPT_CONFIGURATIONS",
    "forget",
    "kept_textconv_named",
    "read_textconv_named",
    "textconv_answer",
    "textconv_named",
]
