"""Which agent homes a folder holds.

A folder is a **Claude Code home** when it has a ``projects/`` directory and at least one
file or directory Claude Code writes beside it, and a **Codex home** when it has a
``state_<N>.sqlite`` store, or a ``sessions/`` directory with a Codex marker and no
``projects/``. A folder
also *holds* homes when it contains ``.claude`` or ``.codex`` directly and that directory
is itself a home: a project's own ``.claude/`` (settings and commands, no ``projects/``)
is not one. Serving ``~/.claude`` and serving ``~`` both reach the same home.

Everything here is a handful of ``stat`` calls and one directory listing at most, so a
view's ``offer`` predicate can call :func:`holds_homes` on every folder it renders.
"""

from __future__ import annotations

import os
import re
from pathlib import Path
from typing import Final

from .model import Home

# What Claude Code writes beside ``projects/`` in its home. One of these, plus
# ``projects/``, is what separates a home from a folder that merely has a ``projects``
# directory.
CLAUDE_MARKERS: Final = (
    "settings.json",
    "history.jsonl",
    "sessions",
    "plugins",
    "shell-snapshots",
    "session-env",
    "file-history",
    "todos",
    "statsig",
    "ide",
)

# What Codex writes beside ``sessions/`` in its home. ``sessions/`` alone is a common
# folder name, so it counts only with one of these.
CODEX_MARKERS: Final = ("config.toml", "history.jsonl", "session_index.jsonl", "archived_sessions")

# The store file a Codex home keeps its thread catalog in; ``N`` is its generation.
_CODEX_STORE: Final = re.compile(r"state_\d+\.sqlite")

# The most directory entries examined to find a Codex store. A Codex home holds a few
# dozen entries, so a folder with more than this is not one.
MAX_HOME_ENTRIES: Final = 2000

# The directories that hold a home, in the order their homes are reported.
NESTED: Final = ((".claude", "claude"), (".codex", "codex"))


def is_claude_home(folder: Path) -> bool:
    """True when *folder* has ``projects/`` and one Claude Code marker."""

    if not _is_dir(folder / "projects"):
        return False
    return any(os.path.lexists(folder / marker) for marker in CLAUDE_MARKERS)


def is_codex_home(folder: Path) -> bool:
    """True when *folder* has a ``state_<N>.sqlite`` store, or ``sessions/`` with a Codex
    marker and no ``projects/`` (Claude Code's layout, where ``sessions/`` holds pid files)."""

    if (
        _is_dir(folder / "sessions")
        and not _is_dir(folder / "projects")
        and any(os.path.lexists(folder / marker) for marker in CODEX_MARKERS)
    ):
        return True
    try:
        with os.scandir(folder) as entries:
            for count, entry in enumerate(entries):
                if count >= MAX_HOME_ENTRIES:
                    return False
                if _CODEX_STORE.fullmatch(entry.name) and entry.is_file():
                    return True
    except OSError:
        return False
    return False


def homes_in(folder: Path) -> tuple[Home, ...]:
    """The homes *folder* is or holds: itself first, then ``.claude`` and ``.codex``."""

    found: list[Home] = []
    if is_claude_home(folder):
        found.append(Home("claude", folder))
    if is_codex_home(folder) and not any(home.agent == "codex" for home in found):
        found.append(Home("codex", folder))
    for name, agent in NESTED:
        nested = folder / name
        if not _is_dir(nested):
            continue
        if agent == "claude" and is_claude_home(nested):
            found.append(Home("claude", nested))
        elif agent == "codex" and is_codex_home(nested):
            found.append(Home("codex", nested))
    return tuple(found)


def holds_homes(folder: Path) -> bool:
    """True when :func:`homes_in` would report a home; the cheap predicate for ``offer``."""

    return bool(homes_in(folder))


def _is_dir(path: Path) -> bool:
    try:
        return path.is_dir()
    except OSError:
        return False


# How many directories above a file `home_of` looks, so a deep path costs a bounded
# number of stats.
MAX_ASCENT: Final = 8


def home_of(path: Path, stop: Path) -> Home | None:
    """The home whose directory contains *path*, looking up to *stop* (the served root).

    Looks at most :data:`MAX_ASCENT` directories up, and never above *stop*.
    """

    folder = path.parent
    for _ in range(MAX_ASCENT):
        if is_claude_home(folder):
            return Home("claude", folder)
        if is_codex_home(folder):
            return Home("codex", folder)
        if folder == stop or folder.parent == folder:
            return None
        folder = folder.parent
    return None
