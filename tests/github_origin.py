"""A deterministic multi-ref ``file://`` origin that stands in for a GitHub repository.

``git fast-import`` writes every commit with a fixed committer, date, and message, so
each commit ID is the same on every machine and the builder asserts it. The refs cover
what a GitHub URL's ref-and-path split has to decide:

- ``topic`` (the default branch, since public hygiene rejects the usual spelling) and
  ``release/v1``, a branch whose name contains ``/``;
- ``same``, a branch and a tag at different commits, where the branch wins;
- ``v1.0``, an annotated tag, and ``light``, a lightweight one;
- ``523f``, a branch at the second commit whose name is also the abbreviated ID of the
  first, where the branch wins;
- ``tree-tag``, a tag that names a tree rather than a commit.

Tests that fetch from it through production acquisition monkeypatch
``metabrowser.cache.acquire.remote_url_for`` so the store's identity is the canonical
GitHub URL while every object comes from this local origin.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

from tests.git_pin_harness import git_env

DEFAULT_BRANCH = "topic"
FIRST_COMMIT = "523f476bbcbde731f18dec9d6875df8fe8db13f3"
SECOND_COMMIT = "89e0fadf1d6368c47b9363ff7df0cd26b48d67df"
ROOT_TREE = "5a2a414fc94449bec7a7822a119e166bd1bf90c5"
V1_TAG_OBJECT = "5e1183f0be42ce0e9556e90a1fd0ddbdfc7ba418"


def _commit(
    ref: str, message: str, files: dict[bytes, bytes], *, parent: str | None, when: int
) -> bytes:
    stream = bytearray(f"commit {ref}\n".encode())
    stream += f"committer Origin <origin@example.invalid> {when} +0000\n".encode()
    stream += f"data {len(message)}\n{message}\n".encode()
    if parent is not None:
        stream += f"from {parent}\n".encode()
    for name, body in files.items():
        stream += b"M 100644 inline " + name + b"\ndata " + str(len(body)).encode() + b"\n"
        stream += body + b"\n"
    return bytes(stream + b"\n")


def _git(origin: Path, env: dict[str, str], *args: str, stdin: bytes | None = None) -> str:
    return (
        subprocess.run(
            ["git", "--git-dir", str(origin), *args],
            check=True,
            capture_output=True,
            input=stdin,
            env=env,
        )
        .stdout.decode()
        .strip()
    )


def github_origin(tmp_path: Path) -> Path:
    """Build the origin and prove every object ID is the pinned one."""

    origin = tmp_path / "github-origin.git"
    env = git_env(tmp_path)
    subprocess.run(
        ["git", "init", "-q", "--bare", "--template=", "-b", DEFAULT_BRANCH, str(origin)],
        check=True,
        capture_output=True,
        env=env,
    )
    first_files = {
        b"README.md": b"# Demo\n\nLine three.\nLine four.\n",
        b"docs/guide.md": b"# Guide\n",
        b"docs/My Notes.md": b"spaces in a name\n",
    }
    stream = _commit(
        f"refs/heads/{DEFAULT_BRANCH}", "first", first_files, parent=None, when=1767225600
    )
    stream += _commit(
        "refs/heads/release/v1",
        "second",
        {b"docs/v1.md": b"# Version one\n"},
        parent=f"refs/heads/{DEFAULT_BRANCH}",
        when=1767229200,
    )
    _git(origin, env, "fast-import", "--quiet", stdin=stream + b"done\n")
    first = _git(origin, env, "rev-parse", f"refs/heads/{DEFAULT_BRANCH}")
    second = _git(origin, env, "rev-parse", "refs/heads/release/v1")
    tree = _git(origin, env, "rev-parse", f"{first}^{{tree}}")
    _git(origin, env, "update-ref", "refs/heads/same", first)
    _git(origin, env, "update-ref", "refs/tags/same", second)
    _git(origin, env, "update-ref", "refs/heads/523f", second)
    _git(origin, env, "update-ref", "refs/tags/light", first)
    _git(origin, env, "update-ref", "refs/tags/tree-tag", tree)
    _git(
        origin,
        {
            **env,
            "GIT_COMMITTER_NAME": "Origin",
            "GIT_COMMITTER_EMAIL": "origin@example.invalid",
            "GIT_COMMITTER_DATE": "1767232800 +0000",
        },
        "tag",
        "-a",
        "-m",
        "one",
        "v1.0",
        second,
    )
    assert (first, second, tree) == (FIRST_COMMIT, SECOND_COMMIT, ROOT_TREE)
    assert _git(origin, env, "rev-parse", "refs/tags/v1.0") == V1_TAG_OBJECT
    return origin


__all__ = [
    "DEFAULT_BRANCH",
    "FIRST_COMMIT",
    "ROOT_TREE",
    "SECOND_COMMIT",
    "V1_TAG_OBJECT",
    "github_origin",
]
