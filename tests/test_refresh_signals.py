"""A refresh's Git under real signals: Ctrl-C or a hangup kills it; a killed server's does not.

A refresh's ``git fetch`` runs in its own process group, so exiting the server does
not stop it by itself. These tests run the real ``metab`` command as a separate
process, serving a mirror stale enough that it refreshes when it starts, with an
origin that holds one large object so the fetch is still transferring when the signal
arrives:

- Ctrl-C (SIGINT) takes the immediate-exit path, which kills the fetch's process group
  before the interpreter exits, so no Git is left writing the store and its fetch lock
  is free. A terminal hangup (SIGHUP) takes the same path, exiting 129;
- SIGKILL cannot run any handler, so the fetch outlives the server. It inherited the
  fetch lock's descriptor, so the lock stays held until it exits and no other process
  can start a refresh, or clean up files, under a live writer.

They need a Git the acquisition floor admits and skip below it; the admitted-Git CI job
runs them unpatched.
"""

from __future__ import annotations

import asyncio
import os
import shutil
import signal
import socket
import subprocess
import sys
import time
from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path

import pytest

from metabrowser.cache.acquire import PublishedSource, acquire_source
from metabrowser.cache.atomic import write_record_atomic
from metabrowser.cache.locks import LockBusyError, repository_store_lock, store_fetch_lock
from metabrowser.cache.paths import store_record
from metabrowser.cache.records import (
    REPOSITORY_STORE_STATE_CONTRACT_ID,
    RepositoryStoreState,
    StoreOperation,
)
from metabrowser.cache.update import RefreshOutcome, update_store
from tests.admitted_git import require_admitted_git
from tests.test_cache_acquire import _file_source, _git

pytestmark = [
    pytest.mark.skipif(os.name != "posix", reason="process groups and flock are POSIX"),
    pytest.mark.skipif(shutil.which("git") is None, reason="git executable is required"),
]

_STALE_AT = "2020-01-01T00:00:00Z"
# Large enough that a file:// fetch of it is still running tens of milliseconds after it
# starts on a fast machine: the fetch hashes and writes every byte.
_LARGE_OBJECT_BYTES = 64 * 1024 * 1024
_METAB = Path(sys.executable).with_name("metab")


@dataclass(frozen=True, slots=True)
class _Stale:
    origin: Path
    published: PublishedSource


def _free_port() -> int:
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        return int(probe.getsockname()[1])


@pytest.fixture
def stale(tmp_path: Path) -> Iterator[_Stale]:
    """A published store, an origin one large commit ahead, and a fetch long ago."""

    require_admitted_git()
    work = tmp_path / "work"
    work.mkdir()
    _git(work, "init", "-q", "-b", "topic")
    (work / "README.md").write_text("small\n", encoding="utf-8")
    _git(work, "add", "README.md")
    _git(work, "commit", "-qm", "small")
    origin = tmp_path / "origin.git"
    _git(work, "clone", "-q", "--bare", "--template=", "--", str(work), str(origin))
    published = asyncio.run(acquire_source(_file_source(origin), home=tmp_path / "home"))
    (work / "large.bin").write_bytes(os.urandom(_LARGE_OBJECT_BYTES))
    _git(work, "add", "large.bin")
    _git(work, "commit", "-qm", "large")
    _git(work, "push", "-q", str(origin), "topic")
    with repository_store_lock(published.home, published.store_key):
        write_record_atomic(
            published.home,
            store_record(published.store_key, "state.yml"),
            RepositoryStoreState(
                default_remote_ref=published.default_remote_ref,
                default_revision=published.default_revision,
                last_fetch_at=_STALE_AT,
                last_operation=StoreOperation(kind="acquire", outcome="succeeded", at=_STALE_AT),
            ),
            REPOSITORY_STORE_STATE_CONTRACT_ID,
        )
    yield _Stale(origin=origin, published=published)


def _serve(stale: _Stale) -> subprocess.Popen[bytes]:
    env = {name: value for name, value in os.environ.items() if not name.startswith("GIT_")}
    env["METABROWSER_HOME"] = str(stale.published.home)
    env["METABROWSER_LOG_LEVEL"] = "WARNING"
    return subprocess.Popen(
        [str(_METAB), f"file://{stale.origin}", "--no-open", "--port", str(_free_port())],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        env=env,
    )


def _fetch_group(stale: _Stale, server: subprocess.Popen[bytes]) -> int:
    """The process group of the server's refresh fetch, once it is running."""

    git_dir = str(stale.published.git_dir)
    deadline = time.monotonic() + 60
    while time.monotonic() < deadline:
        assert server.poll() is None, "the server exited before its refresh started"
        listed = subprocess.run(
            ["ps", "-A", "-o", "pid=,pgid=,args="], capture_output=True, text=True, check=True
        ).stdout
        for line in listed.splitlines():
            pid, pgid, args = line.strip().split(None, 2)
            if git_dir in args and " fetch " in f" {args} " and pid == pgid:
                return int(pgid)
        time.sleep(0.005)
    raise AssertionError("the server never started its refresh fetch")


def _refresh(stale: _Stale) -> RefreshOutcome:
    published = stale.published
    update = update_store(
        published.home, published.store_key, remote_url=published.source.normalized
    )
    return asyncio.run(update).outcome


def _group_alive(pgid: int) -> bool:
    try:
        os.killpg(pgid, 0)
    except ProcessLookupError:
        return False
    return True


def _wait_for_group_to_end(pgid: int, *, timeout_s: float) -> None:
    deadline = time.monotonic() + timeout_s
    while _group_alive(pgid):
        assert time.monotonic() < deadline, "the fetch's process group is still running"
        time.sleep(0.02)


@pytest.mark.parametrize(
    ("stop", "status"),
    [(signal.SIGINT, 130), (signal.SIGHUP, 129)],
    ids=["ctrl-c", "hangup"],
)
def test_ctrl_c_or_a_hangup_kills_the_refresh_fetch_and_frees_its_lock(
    stale: _Stale, stop: signal.Signals, status: int
) -> None:
    """A hangup reaches only the server, since the fetch left the terminal's group."""

    server = _serve(stale)
    try:
        pgid = _fetch_group(stale, server)
        server.send_signal(stop)
        assert server.wait(timeout=30) == status
        # SIGKILL is delivered at once, but reaping the group can take a moment.
        _wait_for_group_to_end(pgid, timeout_s=5)
    finally:
        if server.poll() is None:
            server.kill()
            server.wait()
    home, key = stale.published.home, stale.published.store_key
    with store_fetch_lock(home, key):
        pass
    # What the killed fetch left is removed under the lock, and the next refresh works.
    assert _refresh(stale) is RefreshOutcome.succeeded


def test_a_killed_servers_fetch_keeps_the_lock_until_it_exits(stale: _Stale) -> None:
    server = _serve(stale)
    pgid = _fetch_group(stale, server)
    server.kill()
    server.wait()
    home, key = stale.published.home, stale.published.store_key
    assert _group_alive(pgid), "the fetch finished before the server was killed"
    # The orphaned fetch still writes the store, so it still holds the fetch lock: no
    # other process can refresh, or clean up, under it.
    with pytest.raises(LockBusyError):
        store_fetch_lock(home, key)
    assert _refresh(stale) is RefreshOutcome.refreshing_elsewhere
    _wait_for_group_to_end(pgid, timeout_s=120)
    with store_fetch_lock(home, key):
        pass
    assert _refresh(stale) is RefreshOutcome.succeeded
