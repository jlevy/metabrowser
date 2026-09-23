"""Request-path reads of a published store: isolation, no lazy fetch, request deadline."""

from __future__ import annotations

import asyncio
import os
import shutil
from collections.abc import Sequence
from dataclasses import replace
from pathlib import Path
from typing import Any

import pytest

from metabrowser.git import process as process_module
from metabrowser.git import tree_source as tree_module
from metabrowser.git.process import (
    ACQUISITION_POLICY,
    READ_POLICY,
    GitLocation,
    GitProcessPolicy,
    git_environment,
    repository_store_target,
    run_git,
)
from metabrowser.git.tree_source import git_revision_subject
from metabrowser.settings import GIT_SUBPROCESS_TIMEOUT_S
from tests.git_pin_harness import fast_import_store

pytestmark = pytest.mark.skipif(
    shutil.which("git") is None,
    reason="git executable is required",
)


def test_store_read_policy_is_isolated_and_request_bounded() -> None:
    policy = process_module.STORE_READ_POLICY
    assert policy.timeout_s == GIT_SUBPROCESS_TIMEOUT_S
    assert policy.timeout_s < ACQUISITION_POLICY.timeout_s
    assert policy.stdin == "devnull"
    assert policy.isolate_user_config and policy.no_lazy_fetch
    env = git_environment(policy)
    assert env["GIT_NO_LAZY_FETCH"] == "1"
    assert env["GIT_CONFIG_GLOBAL"] == os.devnull
    assert env["GIT_CONFIG_NOSYSTEM"] == "1"


def test_store_read_policy_drops_every_ambient_git_variable(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Isolation is an allowlist, and the request path inherits it.

    ``isolate_user_config`` is what admits a policy to that allowlist, so a
    store read gets exactly the variables the policy asks for. Without it an
    ambient ``GIT_ALLOW_PROTOCOL`` would replace every ``protocol.*`` setting
    on a request-path read of a published store.
    """
    monkeypatch.setenv("GIT_ALLOW_PROTOCOL", "file:ext")
    monkeypatch.setenv("GIT_DEFAULT_REF_FORMAT", "reftable")
    monkeypatch.setenv("GIT_TRACE", "1")
    env = git_environment(process_module.STORE_READ_POLICY)
    assert {name: value for name, value in env.items() if name.startswith("GIT_")} == {
        "GIT_OPTIONAL_LOCKS": "0",
        "GIT_TERMINAL_PROMPT": "0",
        "GIT_ASKPASS": "",
        "GIT_CONFIG_GLOBAL": os.devnull,
        "GIT_CONFIG_NOSYSTEM": "1",
        "GIT_NO_LAZY_FETCH": "1",
        "GIT_SSH_COMMAND": "ssh -oBatchMode=yes",
    }


def test_a_pinned_location_reads_under_the_store_read_policy(tmp_path: Path) -> None:
    store = tmp_path / "store.git"
    store.mkdir()
    location = GitLocation.revision(repository_store_target(git_dir=store), "a" * 40)
    assert location.read_policy is process_module.STORE_READ_POLICY
    assert GitLocation.filesystem(tmp_path).read_policy is READ_POLICY


def test_tree_source_store_reads_use_the_store_read_policy(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    store, commit = fast_import_store(tmp_path, {b"docs/a.md": b"a\n", b"b.txt": b"b\n"})
    seen: list[tuple[str, GitProcessPolicy | None]] = []
    real_run_git = tree_module.run_git

    async def recording_run_git(args: Sequence[str], **kwargs: Any) -> bytes:
        verb = next(arg for arg in args if arg in {"ls-tree", "rev-parse"})
        seen.append((verb, kwargs.get("policy")))
        return await real_run_git(args, **kwargs)

    monkeypatch.setattr(tree_module, "run_git", recording_run_git)

    async def run() -> None:
        subject = await git_revision_subject(
            target=repository_store_target(git_dir=store),
            commit_oid=commit,
            store_identity="policy-fixture",
        )
        try:
            assert await subject.tree_source.blob_index() is not None
        finally:
            await subject.aclose()

    asyncio.run(run())
    assert {verb for verb, _policy in seen} == {"ls-tree", "rev-parse"}
    assert all(policy is process_module.STORE_READ_POLICY for _verb, policy in seen), seen


def test_a_store_target_without_a_policy_never_reads_under_the_ambient_policy(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    store, commit = fast_import_store(tmp_path, {b"a.txt": b"a\n"})
    chosen: list[GitProcessPolicy | None] = []
    real_environment = process_module.git_environment

    def recording_environment(policy: GitProcessPolicy | None = None) -> dict[str, str]:
        chosen.append(policy)
        return real_environment(policy)

    monkeypatch.setattr(process_module, "git_environment", recording_environment)

    async def run() -> bytes:
        return await run_git(
            ["cat-file", "-t", commit], target=repository_store_target(git_dir=store)
        )

    assert asyncio.run(run()).strip() == b"commit"
    assert chosen == [process_module.STORE_READ_POLICY]


def test_no_store_spawn_may_run_with_lazy_fetch_enabled(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The no-lazy-fetch decision holds at the one spawn seam.

    A caller that names a policy bypasses the store default, so the seam itself
    refuses any policy that leaves lazy fetch on. It refuses before Git runs.
    """

    store, commit = fast_import_store(tmp_path, {b"a.txt": b"a\n"})
    target = repository_store_target(git_dir=store)
    spawned: list[object] = []

    async def no_spawn(*args: object, **kwargs: object) -> None:
        spawned.append(args)
        raise AssertionError("a refused store read must not spawn Git")

    monkeypatch.setattr(process_module.asyncio, "create_subprocess_exec", no_spawn)
    monkeypatch.setattr(process_module.subprocess, "run", no_spawn)

    lazy = replace(process_module.STORE_READ_POLICY, name="lazy", no_lazy_fetch=False)
    for policy in (READ_POLICY, lazy):
        with pytest.raises(ValueError, match="lazy fetch"):
            asyncio.run(run_git(["cat-file", "-t", commit], target=target, policy=policy))
        with pytest.raises(ValueError, match="lazy fetch"):
            process_module.run_git_blocking(
                ["cat-file", "-t", commit], target=target, policy=policy
            )
    assert spawned == []
    policies = [
        value
        for value in vars(process_module).values()
        if isinstance(value, GitProcessPolicy) and value is not READ_POLICY
    ]
    assert policies, "the named policies moved"
    assert all(policy.no_lazy_fetch for policy in policies), policies


def test_info_many_applies_the_batch_deadline_per_chunk(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A whole-tree size read must not share one fixed deadline.

    Eight headers at 0.15 s each outlast a single 1 s deadline. In chunks of
    two, each chunk needs 0.3 s of its own 1 s.
    """

    files = {f"f{index}.txt".encode(): f"{index}\n".encode() for index in range(8)}
    store, commit = fast_import_store(tmp_path, files)
    real_read_header = tree_module._read_header

    async def slow_header(reader: asyncio.StreamReader) -> bytes:
        await asyncio.sleep(0.15)
        return await real_read_header(reader)

    async def run() -> None:
        subject = await git_revision_subject(
            target=repository_store_target(git_dir=store),
            commit_oid=commit,
            store_identity="policy-fixture",
        )
        try:
            entries = await subject.tree_source.list_tree()
            oids = tuple(entry.oid for entry in entries)
            assert len(set(oids)) == 8
            actor = tree_module._BatchObjectReader(subject.tree_source.target)
            try:
                with monkeypatch.context() as scoped:
                    scoped.setattr(tree_module, "_read_header", slow_header)
                    scoped.setattr(tree_module, "INFO_MANY_CHUNK_OBJECTS", 2, raising=False)
                    scoped.setattr(
                        tree_module,
                        "BATCH_OBJECT_POLICY",
                        replace(tree_module.BATCH_OBJECT_POLICY, timeout_s=1.0),
                    )
                    infos = await actor.info_many(oids)
                assert [info.size for info in infos.values() if info is not None] == [2] * 8
                assert list(infos) == list(oids)
            finally:
                await actor.aclose()
        finally:
            await subject.aclose()

    asyncio.run(run())
