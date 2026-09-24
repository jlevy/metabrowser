"""A cached mirror for the source-route golden transcript, identical on every machine.

Run as a script, it builds below one directory:

- ``origin.git``: a bare repository written with ``git fast-import``, which takes every
  identity and date from the stream, so each commit ID below is the same everywhere.
  ``topic`` (the default branch) is ``first`` then ``second``; ``feature`` branches from
  ``first``; ``v1`` is an annotated tag of ``first``.
- ``home``: an application home that acquired ``file://<directory>/origin.git``. Its
  store's recorded fetch is then set to a fixed time with the production writer under
  the store lock, so the status envelope is literal.
- the JSON request bodies the transcript posts;
- with ``--hold-fetch-lock``, a detached process that holds the store's fetch lock, as
  another server's refresh would, and writes its process ID to ``holder.pid``. It lets
  go when the transcript's ``after`` step stops it, when ``origin.git`` is gone, or
  after five minutes, whichever is first.

Acquisition checks the installed Git against the security floor, and CI's Git is below
it. The transcript's commands only open the cached store, which a cache hit does without
the floor, so this fixture stands in for an acquisition an admitted Git performed and
patches the floor for that one call, as the in-process acquisition tests do. A refresh
the transcript requests checks the floor itself, after the fetch lock: the held lock makes
that refresh report another process refreshing whatever Git the machine has, which a
transcript run on CI's Git and on an admitted one must agree on.

    source_mirror_fixture.py <directory> [--hold-fetch-lock]
"""

from __future__ import annotations

import asyncio
import json
import os
import subprocess
import sys
import time
from pathlib import Path
from typing import Final

from metabrowser.cache import acquire
from metabrowser.cache.atomic import write_record_atomic
from metabrowser.cache.locks import repository_store_lock, store_fetch_lock
from metabrowser.cache.paths import store_record
from metabrowser.cache.records import (
    REPOSITORY_STORE_STATE_CONTRACT_ID,
    RepositoryStoreState,
    StoreOperation,
)
from metabrowser.cache.urls import GitSource, classify_root_argument
from metabrowser.git.tree_source import GitPath

FETCHED_AT: Final = "2026-09-17T12:00:05Z"
_IDENTITY: Final = b"Mirror <mirror@example.invalid>"
# 2026-01-01T00:00:00Z, then an hour apart.
_EPOCH: Final = 1767225600


def _data(payload: bytes) -> bytes:
    return b"data " + str(len(payload)).encode() + b"\n" + payload + b"\n"


def _commit(ref: bytes, mark: int, at: int, message: bytes, parent: int | None) -> bytes:
    stream = b"commit " + ref + b"\nmark :" + str(mark).encode() + b"\n"
    stream += b"committer " + _IDENTITY + b" " + str(at).encode() + b" +0000\n"
    stream += _data(message)
    if parent is not None:
        stream += b"from :" + str(parent).encode() + b"\n"
    return stream


def _file(name: bytes, body: bytes) -> bytes:
    return b"M 100644 inline " + name + b"\n" + _data(body)


def _stream() -> bytes:
    stream = _commit(b"refs/heads/topic", 1, _EPOCH, b"first\n", None)
    stream += _file(b"README.md", b"# Mirror\n")
    stream += _commit(b"refs/heads/topic", 2, _EPOCH + 3600, b"second\n", 1)
    stream += _file(b"NOTES.md", b"Second commit on topic.\n")
    stream += _commit(b"refs/heads/feature", 3, _EPOCH + 7200, b"feature\n", 1)
    stream += _file(b"FEATURE.md", b"Only on feature.\n")
    stream += b"tag v1\nfrom :1\n"
    stream += b"tagger " + _IDENTITY + b" " + str(_EPOCH).encode() + b" +0000\n"
    stream += _data(b"release v1\n")
    return stream + b"done\n"


def _git_env(directory: Path) -> dict[str, str]:
    env = {name: value for name, value in os.environ.items() if not name.startswith("GIT_")}
    env["GIT_CONFIG_GLOBAL"] = os.devnull
    env["GIT_CONFIG_NOSYSTEM"] = "1"
    env["HOME"] = str(directory)
    return env


def build_origin(directory: Path) -> Path:
    origin = directory / "origin.git"
    env = _git_env(directory)
    subprocess.run(
        ["git", "init", "-q", "--bare", "--template=", "-b", "topic", str(origin)],
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


def _rev(origin: Path, ref: str) -> str:
    return subprocess.run(
        ["git", "--git-dir", str(origin), "rev-parse", "--verify", f"{ref}^{{commit}}"],
        check=True,
        capture_output=True,
        text=True,
        env=_git_env(origin.parent),
    ).stdout.strip()


def build_home(directory: Path, origin: Path) -> None:
    classified = classify_root_argument(f"file://{origin}")
    if not isinstance(classified, GitSource):
        raise SystemExit("the origin did not classify as a Git source")
    # The floor this stands in for; see the module docstring.
    acquire.require_acquisition_git = lambda: (2, 50, 1)
    published = asyncio.run(acquire.acquire_source(classified, home=directory / "home"))
    with repository_store_lock(published.home, published.store_key):
        write_record_atomic(
            published.home,
            store_record(published.store_key, "state.yml"),
            RepositoryStoreState(
                default_remote_ref=published.default_remote_ref,
                default_revision=published.default_revision,
                last_fetch_at=FETCHED_AT,
                last_operation=StoreOperation(kind="acquire", outcome="succeeded", at=FETCHED_AT),
            ),
            REPOSITORY_STORE_STATE_CONTRACT_ID,
        )


def write_bodies(directory: Path, origin: Path) -> None:
    first = _rev(origin, "refs/heads/topic~1")
    bodies = {
        "refresh.json": {},
        "pin-feature.json": {"ref": "feature"},
        "pin-tag.json": {"ref": "v1"},
        "pin-oid.json": {"oid": first[:9]},
        "pin-same.json": {"ref": "topic"},
        "pin-missing.json": {"ref": "gone"},
        "pin-syntax.json": {"ref": ":/first"},
        # What the ref selector posts: the full ref it listed and the page's address.
        # README.md is on every branch; NOTES.md only on topic.
        "pin-feature-view.json": {
            "ref": "refs/remotes/origin/feature",
            "view": "/view/" + GitPath.from_display("README.md").to_wire(),
        },
        "pin-feature-away.json": {
            "ref": "refs/remotes/origin/feature",
            "view": "/view/" + GitPath.from_display("NOTES.md").to_wire(),
        },
    }
    for name, body in bodies.items():
        (directory / name).write_text(json.dumps(body) + "\n", encoding="utf-8")


_HOLDER: Final = """
import fcntl, os, sys, time
fd = os.open(sys.argv[1], os.O_RDWR)
fcntl.flock(fd, fcntl.LOCK_EX)
with open(sys.argv[3], "w") as marker:
    marker.write(str(os.getpid()))
deadline = time.monotonic() + 300
while os.path.exists(sys.argv[2]) and time.monotonic() < deadline:
    time.sleep(0.5)
"""


def hold_fetch_lock(directory: Path) -> None:
    """Hold the store's fetch lock from a detached process, as another refresh would."""

    home = directory / "home"
    (key,) = [entry.name for entry in (home / "cache" / "repository-stores").iterdir()]
    # Created and released through the production path, so the file is the lock file.
    with store_fetch_lock(home, key) as lock:
        lock_path = lock.path
    marker = directory / "holder.pid"
    subprocess.Popen(
        [sys.executable, "-c", _HOLDER, str(lock_path), str(directory / "origin.git"), str(marker)],
        stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        start_new_session=True,
    )
    deadline = time.monotonic() + 30
    while not marker.exists() or not marker.read_text(encoding="utf-8"):
        if time.monotonic() > deadline:
            raise SystemExit("the fetch-lock holder did not start")
        time.sleep(0.05)


def build_all(directory: Path, *, hold_lock: bool = False) -> None:
    origin = build_origin(directory)
    build_home(directory, origin)
    write_bodies(directory, origin)
    if hold_lock:
        hold_fetch_lock(directory)


if __name__ == "__main__":
    arguments = sys.argv[1:]
    hold = "--hold-fetch-lock" in arguments
    positional = [argument for argument in arguments if argument != "--hold-fetch-lock"]
    if len(positional) != 1:
        raise SystemExit("usage: source_mirror_fixture.py <directory> [--hold-fetch-lock]")
    build_all(Path(positional[0]).resolve(), hold_lock=hold)
