"""Reproducible fixture repository for the diff adapter and CLI goldens.

Two commits whose delta exercises the change taxonomy: modify, add,
delete, rename-with-edit, chmod, file-to-symlink type change, and a
binary rewrite. Author, committer, and dates are pinned, so commit ids
are identical on every machine — which is what lets the tryscript
goldens assert real output.
"""

from __future__ import annotations

import os
import subprocess
from pathlib import Path

from metabrowser.diff.apply import TreeEntry, TreeSnapshot
from metabrowser.diff.format import EntryType
from metabrowser.git.process import _REPO_PINNING_GIT_VARS

_EPOCH_ONE = "2026-01-01T00:00:00 +0000"
_EPOCH_TWO = "2026-01-02T00:00:00 +0000"


def _env(root: Path, date: str) -> dict[str, str]:
    env = {key: value for key, value in os.environ.items() if key not in _REPO_PINNING_GIT_VARS}
    env.update(
        {
            "GIT_AUTHOR_NAME": "Fixture Author",
            "GIT_AUTHOR_EMAIL": "author@example.invalid",
            "GIT_COMMITTER_NAME": "Fixture Author",
            "GIT_COMMITTER_EMAIL": "author@example.invalid",
            "GIT_AUTHOR_DATE": date,
            "GIT_COMMITTER_DATE": date,
            "GIT_CONFIG_GLOBAL": str(root / ".gitconfig-absent"),
            "GIT_CONFIG_SYSTEM": str(root / ".gitconfig-absent"),
        }
    )
    return env


def git(root: Path, *args: str, date: str = _EPOCH_ONE) -> bytes:
    result = subprocess.run(
        ["git", "-C", str(root), *args],
        check=True,
        capture_output=True,
        env=_env(root, date),
    )
    return result.stdout


def build_diff_fixture(root: Path) -> tuple[str, str]:
    """Build the repo; returns (base_commit, target_commit)."""
    git(root, "init", "-q", "-b", "main")
    (root / "src").mkdir()
    (root / "a.py").write_text("def f():\n    return 1\n")
    (root / "gone.txt").write_text("bye\n")
    (root / "src/util.py").write_text("x = 1\n")
    (root / "run.sh").write_text("#!/bin/sh\necho run\n")
    (root / "cfg").write_text("real contents\n")
    (root / "logo.bin").write_bytes(b"\x00\x01\x02BINARY-ONE\x00")
    git(root, "add", "-A")
    git(root, "commit", "-q", "-m", "base")
    base = git(root, "rev-parse", "HEAD").decode().strip()

    (root / "a.py").write_text("def f():\n    return 2\n")
    (root / "gone.txt").unlink()
    (root / "new.md").write_text("# New\nbody\n")
    (root / "src/helpers").mkdir()
    (root / "src/util.py").rename(root / "src/helpers/util.py")
    (root / "src/helpers/util.py").write_text("x = 1\ny = 2\n")
    (root / "run.sh").chmod(0o755)
    (root / "cfg").unlink()
    (root / "cfg").symlink_to("target/cfg")
    (root / "logo.bin").write_bytes(b"\x00\x01\x02BINARY-TWO-LONGER\x00")
    git(root, "add", "-A", date=_EPOCH_TWO)
    git(root, "commit", "-q", "-m", "target", date=_EPOCH_TWO)
    target = git(root, "rev-parse", "HEAD").decode().strip()
    return base, target


def materialize_tree(root: Path, revision: str) -> TreeSnapshot:
    """Read one committed tree into the corpus tree shape, byte-exactly."""
    listing = git(root, "ls-tree", "-r", "-z", "--full-tree", revision)
    entries: dict[str, TreeEntry] = {}
    for record in listing.split(b"\0"):
        if not record:
            continue
        meta, path_raw = record.split(b"\t", 1)
        mode_raw, obj_type, oid = meta.decode("ascii").split(" ")
        path = path_raw.decode("utf-8", "surrogateescape")
        if obj_type == "commit":
            entries[path] = TreeEntry(EntryType.submodule, mode_raw, oid.encode("ascii"))
            continue
        content = git(root, "cat-file", "blob", oid)
        entry_type = EntryType.symlink if mode_raw == "120000" else EntryType.file
        entries[path] = TreeEntry(entry_type, mode_raw, content)
    return TreeSnapshot(entries=entries)
