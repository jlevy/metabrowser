"""A checkout with several branches and tags and a dirty working tree, identical on every machine.

Run as a script, it builds below one directory:

- ``origin.git``: :func:`tests.source_mirror_fixture.build_origin`'s bare repository,
  written with ``git fast-import``, so each commit ID is the same everywhere. ``topic``
  (the default branch) is ``first`` then ``second``; ``feature`` branches from ``first``;
  ``v1`` is an annotated tag of ``first``.
- ``checkout``: a clone of it, on ``topic``, with what a reader's own checkout has and a
  mirror does not:

  - local branches ``topic`` and ``feature``, and ``local-work``, a commit made here on
    ``topic`` with a fixed identity and date that no remote has;
  - remote-tracking branches ``origin/topic`` and ``origin/feature``, and the symbolic
    ``origin/HEAD`` a clone writes;
  - the tag ``v1``, and a lightweight tag ``local-tag`` at ``feature``;
  - a working tree that differs from every commit: ``README.md`` edited and not staged,
    ``STAGED.md`` added to the index and not committed, and ``UNTRACKED.md`` on disk
    only. So the index is not ``HEAD``'s, and a command that refreshed, reset, or checked
    out anything would show.

- the JSON request bodies the transcript posts.

:func:`snapshot` reads every entry under the checkout, its ``.git`` included, so a test can
say that showing other revisions left the working tree, the index, ``HEAD``, and every ref
and object byte for byte as they were.

    source_checkout_fixture.py <directory>
"""

from __future__ import annotations

import hashlib
import json
import os
import stat
import subprocess
import sys
from pathlib import Path
from typing import Final

import pytest

from metabrowser.git.process import detect_git_version
from metabrowser.git.tree_source import GitPath
from tests.admitted_git import require_admitted_git, required_admitted_git
from tests.source_mirror_fixture import build_origin

# The fixed identity and date of the one commit made in the checkout, so its ID is literal.
_IDENTITY: Final = {
    "GIT_AUTHOR_NAME": "Checkout",
    "GIT_AUTHOR_EMAIL": "checkout@example.invalid",
    "GIT_COMMITTER_NAME": "Checkout",
    "GIT_COMMITTER_EMAIL": "checkout@example.invalid",
    "GIT_AUTHOR_DATE": "2026-02-01T00:00:00Z",
    "GIT_COMMITTER_DATE": "2026-02-01T00:00:00Z",
}
# What the working tree holds that no commit does.
EDITED_README: Final = "# Mirror\n\nEdited in the working tree, not committed.\n"
STAGED_TEXT: Final = "Staged, not committed.\n"
UNTRACKED_TEXT: Final = "On disk only.\n"


def git_env(directory: Path) -> dict[str, str]:
    """An environment with no ambient repository, configuration, or identity but the fixed one."""

    env = {name: value for name, value in os.environ.items() if not name.startswith("GIT_")}
    env.update(_IDENTITY)
    env["GIT_CONFIG_GLOBAL"] = os.devnull
    env["GIT_CONFIG_NOSYSTEM"] = "1"
    env["HOME"] = str(directory)
    return env


def git(checkout: Path, *args: str) -> str:
    """Run ``git -C checkout`` in the fixture's environment and return its trimmed output."""

    return subprocess.run(
        ["git", "-C", str(checkout), *args],
        check=True,
        capture_output=True,
        text=True,
        env=git_env(checkout.parent),
    ).stdout.strip()


def build_checkout(directory: Path) -> Path:
    """Build ``origin.git`` and ``checkout`` under *directory*; return the checkout."""

    origin = build_origin(directory)
    checkout = directory / "checkout"
    subprocess.run(
        ["git", "clone", "-q", "--template=", str(origin), str(checkout)],
        check=True,
        capture_output=True,
        env=git_env(directory),
    )
    git(checkout, "branch", "-q", "feature", "origin/feature")
    git(checkout, "tag", "local-tag", "feature")
    git(checkout, "checkout", "-q", "-b", "local-work")
    (checkout / "LOCAL.md").write_text("Committed here, pushed nowhere.\n", encoding="utf-8")
    git(checkout, "add", "LOCAL.md")
    git(checkout, "commit", "-q", "-m", "local work")
    git(checkout, "checkout", "-q", "topic")
    (checkout / "README.md").write_text(EDITED_README, encoding="utf-8")
    (checkout / "STAGED.md").write_text(STAGED_TEXT, encoding="utf-8")
    git(checkout, "add", "STAGED.md")
    (checkout / "UNTRACKED.md").write_text(UNTRACKED_TEXT, encoding="utf-8")
    return checkout


def signed_branch(checkout: Path, name: str = "signed") -> str:
    """Write ``refs/heads/<name>``: ``feature``'s commit with a signature header. Its ID.

    The header is what a signed commit carries, with no key behind it, so a Git asked to
    verify signatures runs its signature program for this commit and nothing else has to
    be installed. The working tree, the index, and ``HEAD`` are not touched.
    """

    env = git_env(checkout.parent)
    plain = subprocess.run(
        ["git", "-C", str(checkout), "cat-file", "commit", "refs/heads/feature"],
        check=True,
        capture_output=True,
        env=env,
    ).stdout
    headers, _, message = plain.partition(b"\n\n")
    signature = (
        b"gpgsig -----BEGIN PGP SIGNATURE-----\n \n iQEzBAABCAAdFiEE\n -----END PGP SIGNATURE-----"
    )
    signed = headers + b"\n" + signature + b"\n\n" + message
    oid = (
        subprocess.run(
            ["git", "-C", str(checkout), "hash-object", "-t", "commit", "-w", "--stdin"],
            check=True,
            capture_output=True,
            input=signed,
            env=env,
        )
        .stdout.decode()
        .strip()
    )
    git(checkout, "update-ref", f"refs/heads/{name}", oid)
    return oid


def build_partial_clone(directory: Path) -> Path:
    """A blobless clone of ``origin.git`` under *directory*, with nothing checked out.

    It names every blob of every commit and holds none, as a ``--filter=blob:none`` clone
    of a large repository does until a checkout fetches them.
    """

    origin = directory / "origin.git"
    if not origin.exists():
        build_origin(directory)
    env = git_env(directory)
    subprocess.run(
        ["git", "--git-dir", str(origin), "config", "uploadpack.allowfilter", "true"],
        check=True,
        env=env,
    )
    clone = directory / "partial"
    subprocess.run(
        [
            *("git", "clone", "-q", "--template=", "--filter=blob:none", "--no-checkout"),
            f"file://{origin}",
            str(clone),
        ],
        check=True,
        capture_output=True,
        env=env,
    )
    return clone


def admit_installed_git(monkeypatch: pytest.MonkeyPatch) -> None:
    """Let a checkout's revisions be read with the installed Git, whatever its version.

    Production reads them only with a Git the acquisition floor admits
    (``checkout_revisions.py``, "Which Git"), and the suite has to pass on whatever Git a
    machine has. As ``tests/test_cache_acquire.py`` does for acquisition: when the run
    names an admitted release, the CI ``admitted-git`` job, nothing is patched and the
    production floor itself must admit the Git on ``PATH``.
    """

    if required_admitted_git() is not None:
        require_admitted_git()
        return
    version, raw = detect_git_version()
    if version is None:
        pytest.fail(f"the installed Git's version is unparseable: {raw!r}")
    monkeypatch.setattr("metabrowser.checkout_revisions.require_acquisition_git", lambda: version)


def read_refs_at_every_ask(monkeypatch: pytest.MonkeyPatch) -> None:
    """Have a served checkout read its refs at every page ask, as asks an interval apart do.

    A test asks right after the Git command it is about, sooner than a page's timer
    would, and inside the floor the server keeps between two readings
    (``CHECKOUT_REFS_FLOOR_S`` in ``checkout_revisions.py``), which would answer it from
    memory. That floor has its own test in ``tests/test_checkout_revisions.py``.
    """

    monkeypatch.setattr("metabrowser.checkout_revisions.CHECKOUT_REFS_FLOOR_S", 0.0)


def snapshot(checkout: Path) -> dict[str, tuple[str, int, int, int, str]]:
    """Every entry under *checkout*, ``.git`` included, by its path relative to it.

    A file is its type, mode, inode, modification time in nanoseconds, and the SHA-256 of
    its bytes; a directory and a symbolic link the same with the link's target or nothing
    in place of the digest. A file rewritten to the same bytes has a new modification
    time, and one replaced by rename a new inode, so this sees a rewrite as well as a
    change: the index, which ``git status`` rewrites with the same entries, included.
    """

    entries: dict[str, tuple[str, int, int, int, str]] = {}
    for directory, subdirectories, files in os.walk(checkout):
        for name in sorted((*subdirectories, *files)):
            path = Path(directory) / name
            status = path.lstat()
            if stat.S_ISLNK(status.st_mode):
                kind, content = "link", os.readlink(path)
            elif stat.S_ISDIR(status.st_mode):
                kind, content = "directory", ""
            else:
                kind, content = "file", hashlib.sha256(path.read_bytes()).hexdigest()
            entries[str(path.relative_to(checkout))] = (
                kind,
                stat.S_IMODE(status.st_mode),
                status.st_ino,
                status.st_mtime_ns,
                content,
            )
    return entries


def view(display: str) -> str:
    """The ``/view/`` address of *display* on a revision, where a path is a ``GitPath`` wire."""

    return "/view/" + GitPath.from_display(display).to_wire()


def write_bodies(directory: Path) -> None:
    """The request bodies the transcript posts, by file name."""

    bodies: dict[str, dict[str, object]] = {
        "pin-feature.json": {"ref": "refs/heads/feature"},
        "pin-feature-view.json": {"ref": "feature", "view": "/view/README.md"},
        "pin-remote.json": {"ref": "refs/remotes/origin/feature"},
        "pin-tag.json": {"ref": "v1"},
        "pin-checked-out.json": {"ref": "topic", "view": "/view/STAGED.md"},
        "pin-gone.json": {"ref": "refs/heads/gone"},
        "pin-syntax.json": {"ref": "topic~1"},
        "pin-working-tree.json": {"working_tree": True},
        "pin-working-tree-and-ref.json": {"working_tree": True, "ref": "topic"},
        "page-ask.json": {"for": "page"},
        # What a watch on the checkout's HEAD compares (`HEAD_WATCH_PATH`, file_watches.py).
        "watch-head.json": {"path": ".git/HEAD"},
    }
    for name, body in bodies.items():
        (directory / name).write_text(json.dumps(body) + "\n", encoding="utf-8")


def main(argv: list[str]) -> int:
    if len(argv) != 2:
        sys.stderr.write(__doc__ or "")
        return 2
    directory = Path(argv[1]).resolve()
    directory.mkdir(parents=True, exist_ok=True)
    build_checkout(directory)
    write_bodies(directory)
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
