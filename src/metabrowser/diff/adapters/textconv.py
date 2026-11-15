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
it runs with, and the environment that names configuration files, with the state of each
file the listing came from, of each file an include names, and of the global files Git
would read if they appeared. It is believed while none of those has changed, which one
``stat`` each tells. Not watched: a system file holding no entry, which needs a new install
of Git to appear, and an ``includeIf.onbranch`` condition, whose file is read or not as the
branch moves; a configuration holding one is never kept, so it is asked every time.
"""

from __future__ import annotations

import asyncio
import os
from collections import OrderedDict
from dataclasses import dataclass
from pathlib import Path
from typing import Final

from metabrowser.git.process import GitError, GitLocation, git_environment, run_git_at

# Configurations kept. A server reads a few folders and stores; past this the oldest goes.
MAX_KEPT_CONFIGURATIONS: Final = 64

type _Stamp = tuple[tuple[str, tuple[int, int, int] | None], ...]
type _Key = tuple[str, ...]


@dataclass(frozen=True, slots=True)
class _Kept:
    named: bool
    stamp: _Stamp


_KEPT: OrderedDict[_Key, _Kept] = OrderedDict()


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


def _global_files(env: dict[str, str]) -> list[Path]:
    """The global files Git reads, whether or not they exist yet."""
    chosen = env.get("GIT_CONFIG_GLOBAL")
    if chosen is not None:
        return [Path(chosen)]
    home = env.get("HOME", "")
    xdg = env.get("XDG_CONFIG_HOME") or (f"{home}/.config" if home else "")
    files = [Path(home) / ".gitconfig"] if home else []
    return [*files, Path(xdg) / "git" / "config"] if xdg else files


def _stamp(paths: list[Path]) -> _Stamp:
    states: list[tuple[str, tuple[int, int, int] | None]] = []
    for path in sorted(set(paths)):
        try:
            status = os.stat(path)
        except OSError:
            states.append((str(path), None))
        else:
            states.append((str(path), (status.st_mtime_ns, status.st_size, status.st_ino)))
    return tuple(states)


def _read(out: bytes, cwd: Path, env: dict[str, str]) -> tuple[bool, list[Path], bool]:
    """Whether the listing names a driver, the files it depends on, and whether it may be kept.

    With ``-z`` each entry is its origin, a NUL, then its key, a newline, its value, and a
    NUL. Git lowercases a key's section and name; an include's path is relative to the file
    that holds it.
    """
    fields = out.split(b"\0")
    named = False
    keepable = True
    files: list[Path] = []
    home = env.get("HOME", "")
    for origin, entry in zip(fields[0::2], fields[1::2], strict=False):
        key, _, value = entry.partition(b"\n")
        name = key.decode("utf-8", "replace")
        holder: Path | None = None
        if origin.startswith(b"file:"):
            holder = cwd / os.fsdecode(origin[len(b"file:") :])
            files.append(holder)
        if name.startswith("diff.") and name.endswith(".textconv") and name.count(".") >= 2:
            named = True
        included = name == "include.path" or (
            name.startswith("includeif.") and name.endswith(".path")
        )
        if name.startswith("includeif.onbranch:"):
            keepable = False
        if included and value:
            path = os.fsdecode(value)
            if path.startswith("~/") and home:
                path = home + path[1:]
            target = Path(path)
            if not target.is_absolute() and holder is not None:
                target = holder.parent / target
            files.append(target)
    return named, files, keepable


async def textconv_named(location: GitLocation) -> bool | None:
    """Whether the kept answer for *location* names a driver, or None when none is kept."""
    env = _environment(location)
    kept = _KEPT.get(_key(location, env))
    if kept is None:
        return None
    paths = [Path(path) for path, _state in kept.stamp]
    if await asyncio.to_thread(_stamp, paths) != kept.stamp:
        return None
    return kept.named


async def read_textconv_named(location: GitLocation) -> bool | None:
    """Ask Git whether *location*'s configuration names a driver, and keep the answer.

    None when Git could not say, which a caller takes as a driver that may be named.
    """
    env = _environment(location)
    key = _key(location, env)
    try:
        out = await run_git_at(["config", "--list", "--show-origin", "-z"], location)
    except GitError:
        return None
    named, files, keepable = _read(out, _cwd(location), env)
    if keepable:
        stamp = await asyncio.to_thread(_stamp, [*files, *_global_files(env)])
        _KEPT[key] = _Kept(named, stamp)
        _KEPT.move_to_end(key)
        while len(_KEPT) > MAX_KEPT_CONFIGURATIONS:
            _KEPT.popitem(last=False)
    return named


def forget() -> None:
    """Drop every kept answer, for a test that counts the processes of a cold one."""
    _KEPT.clear()


__all__ = ["MAX_KEPT_CONFIGURATIONS", "forget", "read_textconv_named", "textconv_named"]
