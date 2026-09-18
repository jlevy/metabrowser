"""Exclusive-lock ``gc`` and ``repack`` over a published worktree-free store."""

from __future__ import annotations

import asyncio
import os
import shutil
from pathlib import Path

import pytest

from metabrowser.cache.locks import (
    LockBusyError,
    LockOrderError,
    held_locks,
    repository_store_lock,
)
from metabrowser.cache.repository_store import (
    lease_revision,
    maintain_store,
    subject_revision_ref,
)
from metabrowser.git.process import GitUnavailableError, repository_store_target
from tests.test_git_revision_lease import (
    _LeaseHolder,
    _publish,
    _store_git,
)

pytestmark = [
    pytest.mark.skipif(shutil.which("git") is None, reason="git executable is required"),
    pytest.mark.skipif(os.name != "posix", reason="cache locks are BSD flock locks"),
]


def test_maintain_store_runs_gc_without_a_checkout_or_store_lock(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    home, store_key, git_dir, first, second = _publish(tmp_path, monkeypatch)
    lease = asyncio.run(lease_revision(home=home, store_key=store_key, commit_oid=first))
    lease.release()
    asyncio.run(maintain_store(home=home, store_key=store_key))
    assert held_locks() == ()
    assert not (git_dir / "index").exists()
    assert not (git_dir / "worktrees").exists()
    target = repository_store_target(git_dir=git_dir)
    reachable = asyncio.run(_store_git(target, "rev-list", "--all"))
    assert first in reachable.split()
    assert second in reachable.split()
    assert (
        asyncio.run(_store_git(target, "rev-parse", "--verify", subject_revision_ref(first)))
        == first
    )


def test_maintain_store_refuses_a_live_lease_and_a_store_lock(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    home, store_key, git_dir, _first, second = _publish(tmp_path, monkeypatch)
    lease = asyncio.run(lease_revision(home=home, store_key=store_key, commit_oid=second))
    try:
        with pytest.raises(LockOrderError, match="other mode"):
            asyncio.run(maintain_store(home=home, store_key=store_key))
    finally:
        lease.release()
    with repository_store_lock(home, store_key), pytest.raises(LockOrderError, match="gc"):
        asyncio.run(maintain_store(home=home, store_key=store_key))
    other = _LeaseHolder(home, store_key, second)
    try:
        with pytest.raises(LockBusyError):
            asyncio.run(maintain_store(home=home, store_key=store_key))
    finally:
        other.release()
    asyncio.run(maintain_store(home=home, store_key=store_key))
    assert not (git_dir / "index").exists()
    target = repository_store_target(git_dir=git_dir)
    assert (
        asyncio.run(_store_git(target, "rev-parse", "--verify", subject_revision_ref(second)))
        == second
    )


def test_maintain_store_keeps_a_subject_ref_after_origin_refs_are_gone(
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
    asyncio.run(maintain_store(home=home, store_key=store_key))
    reachable = asyncio.run(_store_git(target, "rev-list", "--all"))
    assert first in reachable.split()
    assert asyncio.run(_store_git(target, "cat-file", "-t", first)) == "commit"
    assert not (git_dir / "index").exists()


def test_maintain_store_refuses_an_absent_store(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    home, store_key, _git_dir, _first, _second = _publish(tmp_path, monkeypatch)
    with pytest.raises(GitUnavailableError):
        asyncio.run(maintain_store(home=home, store_key="b" * 64))
    asyncio.run(maintain_store(home=home, store_key=store_key))
    assert held_locks() == ()
