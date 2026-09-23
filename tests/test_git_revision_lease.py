"""Revision leases: shared store lock, durable subject refs, two-process coexistence."""

from __future__ import annotations

import asyncio
import os
import shutil
import signal
import subprocess
import sys
import textwrap
from collections.abc import Sequence
from pathlib import Path

import pytest

from metabrowser.cache.acquire import acquire_file_source
from metabrowser.cache.locks import (
    LockBusyError,
    LockOrderError,
    held_locks,
    store_maintenance_lock,
)
from metabrowser.cache.paths import store_directory
from metabrowser.cache.repository_store import (
    RevisionLease,
    lease_revision,
    subject_revision_ref,
)
from metabrowser.git.process import (
    ACQUISITION_POLICY,
    GitCommandTarget,
    GitUnavailableError,
    repository_store_target,
    run_git,
)
from metabrowser.git.tree_source import (
    GitObjectUnavailableError,
    GitPathError,
    git_revision_subject,
)
from tests.test_cache_acquire import _allow_installed_git, _file_source, _git, _git_env

pytestmark = [
    pytest.mark.skipif(shutil.which("git") is None, reason="git executable is required"),
    pytest.mark.skipif(os.name != "posix", reason="cache locks are BSD flock locks"),
]

CHILD_TIMEOUT = 30.0


def _git_out(root: Path, *args: str) -> str:
    result = subprocess.run(
        ["git", "-C", str(root), *args],
        check=True,
        capture_output=True,
        env=_git_env(root),
    )
    return result.stdout.decode().strip()


def _two_commit_origin(tmp_path: Path) -> tuple[Path, str, str]:
    work = tmp_path / "work"
    origin = tmp_path / "origin.git"
    work.mkdir()
    _git(work, "init", "-q", "-b", "topic")
    (work / "README").write_text("first\n", encoding="utf-8")
    _git(work, "add", "README")
    _git(work, "commit", "-qm", "first")
    first = _git_out(work, "rev-parse", "HEAD")
    (work / "README").write_text("second\n", encoding="utf-8")
    _git(work, "add", "README")
    _git(work, "commit", "-qm", "second")
    second = _git_out(work, "rev-parse", "HEAD")
    _git(work, "clone", "--bare", "--template=", "--", str(work), str(origin))
    return origin, first, second


def _publish(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> tuple[Path, str, Path, str, str]:
    _allow_installed_git(monkeypatch)
    origin, first, second = _two_commit_origin(tmp_path)
    home = tmp_path / "home"
    published = asyncio.run(acquire_file_source(_file_source(origin), home=home))
    assert published.default_revision == second
    return published.home, published.store_key, published.git_dir, first, second


async def _store_git(target: GitCommandTarget, *args: str) -> str:
    return (await run_git([*args], target=target, policy=ACQUISITION_POLICY)).decode().strip()


class _LeaseHolder:
    """Child process that holds ``lease_revision`` until released or killed."""

    def __init__(self, home: Path, store_key: str, commit_oid: str) -> None:
        script = textwrap.dedent(
            """
            import asyncio
            import sys
            from pathlib import Path
            from metabrowser.cache.repository_store import lease_revision
            home = Path(sys.argv[1])
            lease = asyncio.run(
                lease_revision(home=home, store_key=sys.argv[2], commit_oid=sys.argv[3])
            )
            print("held", flush=True)
            sys.stdin.readline()
            lease.release()
            print("released", flush=True)
            """
        )
        self.process = subprocess.Popen(
            [sys.executable, "-c", script, str(home), store_key, commit_oid],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        assert self.process.stdout is not None
        line = self.process.stdout.readline().strip()
        if line != "held":
            _, errors = self.process.communicate(timeout=CHILD_TIMEOUT)
            pytest.fail(f"lease holder did not start: {line!r} {errors}")

    def release(self) -> None:
        assert self.process.stdin is not None and self.process.stdout is not None
        self.process.stdin.write("\n")
        self.process.stdin.flush()
        assert self.process.stdout.readline().strip() == "released"
        self.process.communicate(timeout=CHILD_TIMEOUT)

    def kill(self) -> None:
        self.process.send_signal(signal.SIGKILL)
        self.process.communicate(timeout=CHILD_TIMEOUT)


def test_lease_pins_a_durable_ref_and_defers_exclusive_maintenance(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    home, store_key, git_dir, _first, second = _publish(tmp_path, monkeypatch)
    lease = asyncio.run(lease_revision(home=home, store_key=store_key, commit_oid=second))
    try:
        assert lease.ref_name == subject_revision_ref(second)
        assert (
            asyncio.run(_store_git(lease.target, "rev-parse", "--verify", lease.ref_name)) == second
        )
        with pytest.raises(LockOrderError, match="other mode"):
            store_maintenance_lock(home, store_key)
        assert not (git_dir / "index").exists()
        assert not (git_dir / "worktrees").exists()
    finally:
        lease.release()
    assert held_locks() == ()
    with store_maintenance_lock(home, store_key):
        pass
    target = repository_store_target(git_dir=git_dir)
    assert (
        asyncio.run(_store_git(target, "rev-parse", "--verify", subject_revision_ref(second)))
        == second
    )


def test_two_processes_lease_two_oids_in_one_store_without_a_checkout(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    home, store_key, git_dir, first, second = _publish(tmp_path, monkeypatch)
    other = _LeaseHolder(home, store_key, first)
    try:
        with pytest.raises(LockBusyError):
            store_maintenance_lock(home, store_key)
        lease = asyncio.run(lease_revision(home=home, store_key=store_key, commit_oid=second))
        try:

            async def _read() -> bytes:
                subject = await git_revision_subject(
                    target=lease.target, commit_oid=second, store_identity=store_key
                )
                try:
                    entries = await subject.tree_source.list_tree()
                    readme = next(entry for entry in entries if entry.path.display() == "README")
                    return await subject.tree_source.read_blob(readme.path)
                finally:
                    await subject.aclose()

            assert asyncio.run(_read()) == b"second\n"
            assert not (git_dir / "index").exists()
            assert (
                asyncio.run(
                    _store_git(lease.target, "rev-parse", "--verify", subject_revision_ref(first))
                )
                == first
            )
        finally:
            lease.release()
        with pytest.raises(LockBusyError):
            store_maintenance_lock(home, store_key)
    finally:
        other.release()
    with store_maintenance_lock(home, store_key):
        pass


def test_killing_a_lease_holder_releases_the_flock_and_keeps_the_ref(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    home, store_key, git_dir, _first, second = _publish(tmp_path, monkeypatch)
    holder = _LeaseHolder(home, store_key, second)
    try:
        with pytest.raises(LockBusyError):
            store_maintenance_lock(home, store_key)
        holder.kill()
        with store_maintenance_lock(home, store_key):
            pass
    finally:
        if holder.process.poll() is None:
            holder.kill()
    target = repository_store_target(git_dir=git_dir)
    assert (
        asyncio.run(_store_git(target, "rev-parse", "--verify", subject_revision_ref(second)))
        == second
    )


def test_durable_ref_keeps_a_commit_that_origin_refs_no_longer_name(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    home, store_key, git_dir, first, _second = _publish(tmp_path, monkeypatch)
    lease = asyncio.run(lease_revision(home=home, store_key=store_key, commit_oid=first))
    target = lease.target
    lease.release()
    asyncio.run(_store_git(target, "symbolic-ref", "HEAD", "refs/heads/unused"))
    refs = asyncio.run(_store_git(target, "for-each-ref", "--format=%(refname)")).splitlines()
    for ref in refs:
        if ref and ref != subject_revision_ref(first):
            asyncio.run(_store_git(target, "update-ref", "-d", ref))
    reachable = asyncio.run(_store_git(target, "rev-list", "--all"))
    assert first in reachable.split()
    assert asyncio.run(_store_git(target, "cat-file", "-t", first)) == "commit"
    asyncio.run(_store_git(target, "update-ref", "-d", subject_revision_ref(first)))
    reachable = asyncio.run(_store_git(target, "rev-list", "--all"))
    assert first not in reachable.split()
    assert not (git_dir / "index").exists()
    with store_maintenance_lock(home, store_key):
        pass


def _second_published_store(tmp_path: Path, home: Path) -> tuple[str, str]:
    """Publish a second source into *home*; return its store key and default revision."""

    other = tmp_path / "origin-2.git"
    _git(
        tmp_path,
        "clone",
        "-q",
        "--bare",
        "--template=",
        "--",
        str(tmp_path / "origin.git"),
        str(other),
    )
    published = asyncio.run(acquire_file_source(_file_source(other), home=home))
    assert published.home == home
    return published.store_key, published.default_revision


async def _gather_leases(
    home: Path, requests: Sequence[tuple[str, str]]
) -> list[RevisionLease | BaseException]:
    """Start every lease as its own task on one loop and let them interleave."""

    return list(
        await asyncio.gather(
            *(lease_revision(home=home, store_key=key, commit_oid=oid) for key, oid in requests),
            return_exceptions=True,
        )
    )


def _release_leases(results: Sequence[RevisionLease | BaseException]) -> None:
    for result in results:
        if isinstance(result, RevisionLease):
            result.release()


def _failures(results: Sequence[RevisionLease | BaseException]) -> list[str]:
    return [f"{type(r).__name__}: {r}" for r in results if isinstance(r, BaseException)]


def test_two_concurrent_leases_of_one_store_pin_both_refs(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Two leases of one store on one loop end where a serial pair would."""

    home, store_key, git_dir, first, second = _publish(tmp_path, monkeypatch)
    results = asyncio.run(_gather_leases(home, [(store_key, second), (store_key, first)]))
    try:
        assert _failures(results) == []
        with pytest.raises(LockOrderError, match="other mode"):
            store_maintenance_lock(home, store_key)
    finally:
        _release_leases(results)
    assert held_locks() == ()
    target = repository_store_target(git_dir=git_dir)
    for oid in (first, second):
        ref = subject_revision_ref(oid)
        assert asyncio.run(_store_git(target, "rev-parse", "--verify", ref)) == oid
    assert not (git_dir / "index").exists()
    with store_maintenance_lock(home, store_key):
        pass


def test_two_concurrent_leases_of_two_stores_pin_both_refs(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Leases of two stores neither queue behind each other nor break the lock order.

    The tasks are ordered so the one that reaches the store lock second holds the lower
    key: a holder identified by its thread reads that as one holder descending the rank.
    """

    home, store_key, git_dir, _first, second = _publish(tmp_path, monkeypatch)
    other_key, other_revision = _second_published_store(tmp_path, home)
    assert other_key != store_key
    requests = sorted(
        [(store_key, second), (other_key, other_revision)], key=lambda request: request[0]
    )
    results = asyncio.run(_gather_leases(home, list(reversed(requests))))
    try:
        assert _failures(results) == []
        for key in (store_key, other_key):
            with pytest.raises(LockOrderError, match="other mode"):
                store_maintenance_lock(home, key)
    finally:
        _release_leases(results)
    assert held_locks() == ()
    for key, oid in requests:
        target = repository_store_target(git_dir=home / store_directory(key) / "repository.git")
        ref = subject_revision_ref(oid)
        assert asyncio.run(_store_git(target, "rev-parse", "--verify", ref)) == oid
        with store_maintenance_lock(home, key):
            pass
    assert not (git_dir / "index").exists()


def test_lease_refuses_abbreviated_missing_and_absent_stores(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    home, store_key, _git_dir, _first, second = _publish(tmp_path, monkeypatch)
    with pytest.raises(GitPathError):
        asyncio.run(lease_revision(home=home, store_key=store_key, commit_oid=second[:12]))
    missing = "a" * 40
    with pytest.raises(GitObjectUnavailableError):
        asyncio.run(lease_revision(home=home, store_key=store_key, commit_oid=missing))
    with pytest.raises(GitUnavailableError):
        asyncio.run(lease_revision(home=home, store_key="b" * 64, commit_oid=second))
    assert held_locks() == ()


@pytest.mark.parametrize("ref_exists", [False, True], ids=["first-pin", "repeat-pin"])
def test_a_stale_subject_ref_lock_does_not_block_later_pins(
    ref_exists: bool, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A Git killed mid-``update-ref`` leaves ``<ref>.lock``; the next lease recovers (mb-2k9c)."""
    home, store_key, git_dir, _first, second = _publish(tmp_path, monkeypatch)
    if ref_exists:
        asyncio.run(lease_revision(home=home, store_key=store_key, commit_oid=second)).release()
    stale = git_dir / f"{subject_revision_ref(second)}.lock"
    stale.parent.mkdir(parents=True, exist_ok=True)
    stale.write_text("0" * 40 + "\n")
    lease = asyncio.run(lease_revision(home=home, store_key=store_key, commit_oid=second))
    try:
        assert not stale.exists()
        assert (
            asyncio.run(_store_git(lease.target, "rev-parse", "--verify", lease.ref_name)) == second
        )
    finally:
        lease.release()
