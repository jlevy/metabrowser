"""A cached mirror whose history changes files every way a diff shows, identical everywhere.

Run as a module, it builds below one directory:

- ``origin.git``: a bare repository written with ``git fast-import``, which takes every
  identity and date from the stream, so each commit ID is the same on every machine.
  ``trunk`` (the default branch) is ``first`` then ``second``, and ``second`` modifies
  ``README.md``, adds ``added.txt``, deletes ``gone.txt``, renames ``src/old_name.py`` to
  ``src/new_name.py``, and modifies a file whose name is not UTF-8. ``base`` branches
  from ``first`` and adds ``BASE.md``, so the merge base of ``base`` and ``trunk`` is
  ``first``, as it is for a pull request whose base branch moved on after the fork.
  ``changes.patch`` is a patch file in the tree, whose diff names no commit.
- ``home``: an application home that acquired ``file://<directory>/origin.git``, with
  its last fetch recorded at ``tests/source_mirror_fixture.py``'s fixed time.
- ``pin-parent.json``: the body View file posts to open the renamed file's old path at
  ``first``.

The acquisition floor is patched for that one call, as ``tests/source_mirror_fixture.py``
explains; the transcript's commands only open the cached store.

    PYTHONPATH=<repository> python -m tests.diff_view_file_fixture <directory>
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from typing import Final

from metabrowser.git.tree_source import GitPath
from tests.source_mirror_fixture import _EPOCH, _commit, _file, _git_env, _rev, build_home

# A name Git stores as these bytes, the Latin-1 spelling of "latin1-é.txt". The byte
# 0xE9 alone is not UTF-8, so the name shows a replacement character.
LATIN1_NAME: Final = b"latin1-\xe9.txt"
OLD_NAME: Final = "src/old_name.py"
NEW_NAME: Final = "src/new_name.py"

_PYTHON: Final = b"def old():\n    return 1\n\n\ndef keep():\n    return 2\n"
_PATCH: Final = (
    b"diff --git a/kept.txt b/kept.txt\n"
    b"--- a/kept.txt\n"
    b"+++ b/kept.txt\n"
    b"@@ -1 +1 @@\n"
    b"-unchanged\n"
    b"+changed by the patch\n"
)


def _stream() -> bytes:
    stream = _commit(b"refs/heads/trunk", 1, _EPOCH, b"first\n", None)
    stream += _file(b"README.md", b"# Changes\n\nFirst line.\n")
    stream += _file(b"docs/guide.md", b"# Guide\n\nOne.\nTwo.\nThree.\n")
    stream += _file(OLD_NAME.encode(), _PYTHON)
    stream += _file(b"gone.txt", b"gone soon\n")
    stream += _file(b"kept.txt", b"unchanged\n")
    stream += _file(LATIN1_NAME, b"a Latin-1 name\n")
    stream += _file(b"changes.patch", _PATCH)
    stream += _commit(b"refs/heads/trunk", 2, _EPOCH + 3600, b"second\n", 1)
    stream += _file(b"README.md", b"# Changes\n\nFirst line, changed.\nSecond line.\n")
    stream += _file(b"added.txt", b"new file\n")
    stream += b"D gone.txt\n"
    stream += b"R " + OLD_NAME.encode() + b" " + NEW_NAME.encode() + b"\n"
    stream += _file(LATIN1_NAME, b"a Latin-1 name, edited\n")
    stream += _commit(b"refs/heads/base", 3, _EPOCH + 7200, b"base moved on\n", 1)
    stream += _file(b"BASE.md", b"Only on base.\n")
    return stream + b"done\n"


def build_origin(directory: Path) -> Path:
    origin = directory / "origin.git"
    env = _git_env(directory)
    subprocess.run(
        ["git", "init", "-q", "--bare", "--template=", "-b", "trunk", str(origin)],
        check=True,
        env=env,
    )
    subprocess.run(
        ["git", "--git-dir", str(origin), "fast-import", "--quiet", "--done"],
        check=True,
        input=_stream(),
        env=env,
    )
    return origin


def commits(origin: Path) -> dict[str, str]:
    """The fixture's commits by what they are to the story."""

    return {
        "first": _rev(origin, "refs/heads/trunk~1"),
        "second": _rev(origin, "refs/heads/trunk"),
        "base": _rev(origin, "refs/heads/base"),
    }


def view(display: str | bytes) -> str:
    """The ``/view/`` address of a path on a pin."""

    path = (
        GitPath.from_display(display)
        if isinstance(display, str)
        else GitPath(tuple(display.split(b"/")))
    )
    return "/view/" + path.to_wire()


def write_bodies(directory: Path, origin: Path) -> None:
    body = {"oid": commits(origin)["first"], "view": view(OLD_NAME)}
    (directory / "pin-parent.json").write_text(json.dumps(body) + "\n", encoding="utf-8")


def build_all(directory: Path) -> None:
    origin = build_origin(directory)
    build_home(directory, origin)
    write_bodies(directory, origin)


if __name__ == "__main__":
    arguments = sys.argv[1:]
    if len(arguments) != 1:
        raise SystemExit("usage: python -m tests.diff_view_file_fixture <directory>")
    build_all(Path(arguments[0]).resolve())


__all__ = [
    "LATIN1_NAME",
    "NEW_NAME",
    "OLD_NAME",
    "build_all",
    "build_origin",
    "commits",
    "view",
    "write_bodies",
]
