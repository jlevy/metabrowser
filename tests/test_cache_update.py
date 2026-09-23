"""Refreshing a published store from a ``file://`` origin, and resolving what to pin.

Every test acquires a real store from a real bare origin, changes the origin with
ordinary Git commands, and refreshes through :func:`update_store`. Nothing is mocked but
the acquisition floor, which ``_allow_installed_git`` patches exactly as the acquisition
tests do and leaves alone in the admitted-Git CI job.
"""

from __future__ import annotations

import asyncio
import contextlib
import os
import shutil
import subprocess
import sys
import textwrap
from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pytest

from metabrowser.cache.acquire import PublishedSource, acquire_file_source
from metabrowser.cache.atomic import read_record
from metabrowser.cache.locks import held_locks, store_fetch_lock
from metabrowser.cache.paths import store_record
from metabrowser.cache.records import REPOSITORY_STORE_STATE_CONTRACT_ID, RepositoryStoreState
from metabrowser.cache.repository_store import (
    is_valid_ref_name,
    mirror_ref_candidates,
    open_revision,
    ref_tip,
    resolve_pin,
)
from metabrowser.cache.update import (
    RefreshOutcome,
    remove_interrupted_fetch_leftovers,
    update_store,
)
from metabrowser.git.process import (
    RepositoryStoreTarget,
    UnsupportedGitVersionError,
    repository_store_target,
)
from metabrowser.mirror_refresh import (
    AmbiguousSelectionError,
    InvalidSelectionError,
    SelectionNotFoundError,
)
from tests.test_cache_acquire import _allow_installed_git, _file_source, _git, _git_env

posix_only = pytest.mark.skipif(os.name != "posix", reason="owner-only cache is POSIX-only")

pytestmark = [
    posix_only,
    pytest.mark.skipif(shutil.which("git") is None, reason="git executable is required"),
]


@dataclass(frozen=True, slots=True)
class _Mirror:
    """A work repository, the bare origin it pushes to, and the store acquired from it."""

    work: Path
    origin: Path
    published: PublishedSource

    @property
    def target(self) -> RepositoryStoreTarget:
        return repository_store_target(git_dir=self.published.git_dir)

    def commit(self, name: str, body: str, message: str) -> str:
        (self.work / name).write_text(body, encoding="utf-8")
        _git(self.work, "add", name)
        _git(self.work, "commit", "-qm", message)
        return _rev_parse(self.work, "HEAD")

    def push(self, *refspecs: str) -> None:
        _git(self.work, "push", "-q", str(self.origin), *refspecs)

    def state(self) -> RepositoryStoreState:
        record = read_record(
            self.published.home,
            store_record(self.published.store_key, "state.yml"),
            REPOSITORY_STORE_STATE_CONTRACT_ID,
        )
        assert isinstance(record, RepositoryStoreState)
        return record


def _rev_parse(work: Path, revision: str) -> str:
    return subprocess.run(
        ["git", "-C", str(work), "rev-parse", "--verify", revision],
        check=True,
        capture_output=True,
        text=True,
        env=_git_env(work),
    ).stdout.strip()


def _refs(git_dir: Path) -> dict[str, str]:
    listed = subprocess.run(
        ["git", "--git-dir", str(git_dir), "for-each-ref", "--format=%(refname) %(objectname)"],
        check=True,
        capture_output=True,
        text=True,
    ).stdout
    refs: dict[str, str] = {}
    for line in listed.splitlines():
        name, oid = line.split(" ")
        refs[name] = oid
    return refs


@pytest.fixture
def mirror(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[_Mirror]:
    """A ``topic`` origin with one commit, a ``doomed`` branch, and an annotated tag."""

    _allow_installed_git(monkeypatch)
    work = tmp_path / "work"
    work.mkdir()
    _git(work, "init", "-q", "-b", "topic")
    (work / "README.md").write_text("first\n", encoding="utf-8")
    _git(work, "add", "README.md")
    _git(work, "commit", "-qm", "first")
    _git(work, "branch", "doomed")
    _git(work, "tag", "-a", "v1", "-m", "release one")
    origin = tmp_path / "origin.git"
    _git(work, "clone", "-q", "--bare", "--template=", "--", str(work), str(origin))
    published = asyncio.run(acquire_file_source(_file_source(origin), home=tmp_path / "home"))
    yield _Mirror(work=work, origin=origin, published=published)


def _update(mirror: _Mirror) -> RefreshOutcome:
    return asyncio.run(update_store(mirror.published.home, mirror.published.store_key)).outcome


# ── The update operation ─────────────────────────────────────────────


def test_a_refresh_brings_new_commits_and_records_them(mirror: _Mirror) -> None:
    before = mirror.state()
    newer = mirror.commit("b.txt", "second\n", "second")
    mirror.push("topic")

    update = asyncio.run(update_store(mirror.published.home, mirror.published.store_key))

    assert update.outcome is RefreshOutcome.succeeded
    assert update.default_remote_ref == "refs/remotes/origin/topic"
    assert update.default_revision == newer
    state = mirror.state()
    assert state.default_revision == newer
    assert state.default_remote_ref == "refs/remotes/origin/topic"
    assert state.last_operation.kind == "refresh"
    assert state.last_operation.outcome == "succeeded"
    assert state.last_fetch_at == update.at
    assert before.last_fetch_at is not None
    assert update.at >= before.last_fetch_at
    assert asyncio.run(ref_tip(mirror.target, "refs/remotes/origin/topic")) == newer
    # The refresh held no hierarchy lock afterwards, and released its side lock.
    assert held_locks() == ()


def test_a_force_push_moves_the_branch_and_keeps_the_old_commit_readable(
    mirror: _Mirror,
) -> None:
    old = mirror.commit("b.txt", "to be rewritten\n", "rewritten away")
    mirror.push("topic")
    assert _update(mirror) is RefreshOutcome.succeeded
    _git(mirror.work, "reset", "-q", "--hard", "HEAD~1")
    replacement = mirror.commit("c.txt", "replacement\n", "replacement")
    mirror.push("--force", "topic")

    assert _update(mirror) is RefreshOutcome.succeeded

    assert asyncio.run(ref_tip(mirror.target, "refs/remotes/origin/topic")) == replacement

    async def read_old() -> str:
        subject = await open_revision(
            home=mirror.published.home,
            store_key=mirror.published.store_key,
            commit_oid=old,
            store_identity=mirror.published.store_id,
        )
        try:
            return subject.commit_oid
        finally:
            await subject.aclose()

    assert asyncio.run(read_old()) == old


def test_a_branch_deleted_upstream_is_pruned_and_its_commits_stay_readable(
    mirror: _Mirror,
) -> None:
    _git(mirror.work, "switch", "-q", "doomed")
    doomed = mirror.commit("d.txt", "only on doomed\n", "doomed work")
    mirror.push("doomed")
    assert _update(mirror) is RefreshOutcome.succeeded
    assert _refs(mirror.published.git_dir)["refs/remotes/origin/doomed"] == doomed
    mirror.push("--delete", "doomed")

    assert _update(mirror) is RefreshOutcome.succeeded

    refs = _refs(mirror.published.git_dir)
    assert "refs/remotes/origin/doomed" not in refs
    assert "refs/tags/v1" in refs
    assert asyncio.run(ref_tip(mirror.target, "refs/remotes/origin/doomed")) is None
    resolved = asyncio.run(resolve_pin(mirror.target, oid=doomed))
    assert resolved.commit_oid == doomed and resolved.ref is None
    with pytest.raises(SelectionNotFoundError):
        asyncio.run(resolve_pin(mirror.target, ref="doomed"))


def test_an_unchanged_origin_refreshes_to_the_same_revision(mirror: _Mirror) -> None:
    revision = mirror.published.default_revision
    assert _update(mirror) is RefreshOutcome.succeeded
    assert mirror.state().default_revision == revision


def test_a_removed_origin_is_a_typed_failure_that_keeps_the_last_fetch(
    mirror: _Mirror,
) -> None:
    before = mirror.state()
    refs = _refs(mirror.published.git_dir)
    shutil.rmtree(mirror.origin)

    update = asyncio.run(update_store(mirror.published.home, mirror.published.store_key))

    assert update.outcome is RefreshOutcome.origin_unavailable
    state = mirror.state()
    assert state.last_operation.kind == "refresh"
    assert state.last_operation.outcome == "failed"
    assert state.last_fetch_at == before.last_fetch_at
    assert state.default_revision == before.default_revision
    assert _refs(mirror.published.git_dir) == refs
    assert held_locks() == ()


def test_a_git_below_the_floor_fetches_nothing(
    mirror: _Mirror, monkeypatch: pytest.MonkeyPatch
) -> None:
    def refuse() -> tuple[int, int, int]:
        raise UnsupportedGitVersionError("git version 2.43.0", "2.43.7")

    monkeypatch.setattr("metabrowser.cache.update.require_acquisition_git", refuse)
    before = mirror.state()
    assert _update(mirror) is RefreshOutcome.unsupported_git
    assert mirror.state() == before


def test_a_fetch_lock_held_by_another_process_is_refreshing_elsewhere(
    mirror: _Mirror,
) -> None:
    """The side lock is a real flock another process holds, never waited on."""

    home, key = mirror.published.home, mirror.published.store_key
    with store_fetch_lock(home, key) as held:
        lock_path = held.path
    holder = subprocess.Popen(
        [
            sys.executable,
            "-c",
            textwrap.dedent(
                """
                import fcntl, os, sys
                fd = os.open(sys.argv[1], os.O_RDWR)
                fcntl.flock(fd, fcntl.LOCK_EX)
                print("held", flush=True)
                sys.stdin.read()
                """
            ),
            str(lock_path),
        ],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        text=True,
    )
    try:
        assert holder.stdout is not None
        assert holder.stdout.readline().strip() == "held"
        before = mirror.state()
        assert _update(mirror) is RefreshOutcome.refreshing_elsewhere
        assert mirror.state() == before
    finally:
        assert holder.stdin is not None
        holder.stdin.close()
        holder.wait(timeout=10)
    assert _update(mirror) is RefreshOutcome.succeeded


def test_a_second_refresh_in_this_process_finds_the_lock_busy(mirror: _Mirror) -> None:
    home, key = mirror.published.home, mirror.published.store_key
    with store_fetch_lock(home, key):
        assert _update(mirror) is RefreshOutcome.refreshing_elsewhere


def test_stale_lock_files_and_temporary_packs_are_removed_before_fetching(
    mirror: _Mirror,
) -> None:
    """Exactly what a killed fetch leaves; a leftover ref lock would fail the next fetch."""

    git_dir = mirror.published.git_dir
    (git_dir / "packed-refs.lock").write_text("", encoding="utf-8")
    (git_dir / "refs" / "remotes" / "origin").mkdir(parents=True, exist_ok=True)
    (git_dir / "refs" / "remotes" / "origin" / "topic.lock").write_text("", encoding="utf-8")
    (git_dir / "refs" / "tags").mkdir(parents=True, exist_ok=True)
    (git_dir / "refs" / "tags" / "v1.lock").write_text("", encoding="utf-8")
    (git_dir / "objects" / "pack" / "tmp_pack_abc123").write_bytes(b"partial")
    newer = mirror.commit("b.txt", "second\n", "second")
    mirror.push("topic")

    assert _update(mirror) is RefreshOutcome.succeeded

    assert not (git_dir / "packed-refs.lock").exists()
    assert not (git_dir / "refs" / "remotes" / "origin" / "topic.lock").exists()
    assert not (git_dir / "refs" / "tags" / "v1.lock").exists()
    assert not (git_dir / "objects" / "pack" / "tmp_pack_abc123").exists()
    assert mirror.state().default_revision == newer


def test_leftover_removal_touches_only_leftovers(tmp_path: Path) -> None:
    git_dir = tmp_path / "repository.git"
    (git_dir / "refs" / "heads").mkdir(parents=True)
    (git_dir / "objects" / "pack").mkdir(parents=True)
    (git_dir / "refs" / "heads" / "keep").write_text("x", encoding="utf-8")
    (git_dir / "refs" / "heads" / "stale.lock").write_text("", encoding="utf-8")
    (git_dir / "objects" / "pack" / "pack-1.pack").write_bytes(b"P")
    (git_dir / "objects" / "pack" / "tmp_idx_1").write_bytes(b"I")
    (git_dir / "config.lock").write_text("", encoding="utf-8")

    removed = remove_interrupted_fetch_leftovers(git_dir)

    assert removed == ("objects/pack/tmp_idx_1", "refs/heads/stale.lock")
    assert (git_dir / "refs" / "heads" / "keep").exists()
    assert (git_dir / "objects" / "pack" / "pack-1.pack").exists()
    assert (git_dir / "config.lock").exists()


def test_a_cancelled_fetch_leaves_the_mirror_consistent(
    mirror: _Mirror, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Cancel a real fetch mid-transfer: refs are all old or all new, and the next refresh works.

    The fetch runs unmodified; the wrapper only reports when Git has been started, so the
    cancellation lands while its process group is transferring a large object.
    """

    import metabrowser.cache.update as update_module

    before = mirror.state()
    old_refs = _refs(mirror.published.git_dir)
    (mirror.work / "large.bin").write_bytes(os.urandom(48 * 1024 * 1024))
    _git(mirror.work, "add", "large.bin")
    _git(mirror.work, "commit", "-qm", "large")
    large = _rev_parse(mirror.work, "HEAD")
    _git(mirror.work, "tag", "v2")
    mirror.push("topic", "v2")
    real_run_git = update_module.run_git

    async def cancel_mid_fetch() -> bool:
        fetching = asyncio.Event()

        async def observed(args: list[str], **kwargs: Any) -> bytes:
            if "fetch" in args:
                fetching.set()
            return await real_run_git(args, **kwargs)

        monkeypatch.setattr(update_module, "run_git", observed)
        job = asyncio.ensure_future(update_store(mirror.published.home, mirror.published.store_key))
        await asyncio.wait_for(fetching.wait(), timeout=30)
        # Long enough for Git to be transferring, far shorter than the transfer.
        await asyncio.sleep(0.02)
        cancelled = not job.done()
        job.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await job
        monkeypatch.setattr(update_module, "run_git", real_run_git)
        return cancelled

    cancelled = asyncio.run(cancel_mid_fetch())

    assert cancelled, "the fetch finished before it could be cancelled; enlarge the object"
    assert held_locks() == ()
    # Cancellation writes no record; the atomic fetch moved the refs together or not at all.
    assert mirror.state() == before
    refs = _refs(mirror.published.git_dir)
    assert refs == old_refs or (
        refs["refs/remotes/origin/topic"] == large and refs["refs/tags/v2"] == large
    )
    fsck = subprocess.run(
        ["git", "--git-dir", str(mirror.published.git_dir), "fsck", "--connectivity-only"],
        capture_output=True,
        text=True,
        check=False,
    )
    assert fsck.returncode == 0, fsck.stderr
    assert _update(mirror) is RefreshOutcome.succeeded
    assert mirror.state().default_revision == large
    pack_directory = mirror.published.git_dir / "objects" / "pack"
    assert not any(entry.name.startswith("tmp_") for entry in os.scandir(pack_directory))


# ── Resolving a selection ────────────────────────────────────────────


@pytest.mark.parametrize(
    ("name", "valid"),
    [
        ("refs/remotes/origin/topic", True),
        ("refs/remotes/origin/feature/x-1", True),
        ("refs/tags/v1.0", True),
        ("refs/tags/café", True),
        ("refs/remotes/origin/a..b", False),
        ("refs/remotes/origin/a b", False),
        ("refs/remotes/origin/a~1", False),
        ("refs/remotes/origin/a^", False),
        ("refs/remotes/origin/a:b", False),
        ("refs/remotes/origin/a?", False),
        ("refs/remotes/origin/a*", False),
        ("refs/remotes/origin/a[", False),
        ("refs/remotes/origin/a\\b", False),
        ("refs/remotes/origin/@{-1}", False),
        ("refs/remotes/origin/x.lock", False),
        ("refs/remotes/origin/.hidden", False),
        ("refs/remotes/origin/trailing.", False),
        ("refs/remotes/origin/trailing/", False),
        ("refs/remotes/origin//double", False),
        ("refs/remotes/origin/ctrl\x01", False),
        ("refs/remotes/origin/del\x7f", False),
        ("refs/remotes/origin/\ud800", False),
        ("refs/remotes/origin/" + "x" * 1100, False),
        ("HEAD", False),
    ],
)
def test_ref_names_follow_the_git_ref_name_rules(name: str, valid: bool) -> None:
    assert is_valid_ref_name(name) is valid


def test_ref_candidates_are_a_branch_then_a_tag_and_only_mirror_namespaces() -> None:
    assert mirror_ref_candidates("topic") == ("refs/remotes/origin/topic", "refs/tags/topic")
    assert mirror_ref_candidates("refs/tags/v1") == ("refs/tags/v1",)
    with pytest.raises(InvalidSelectionError):
        mirror_ref_candidates("refs/heads/topic")
    with pytest.raises(InvalidSelectionError):
        mirror_ref_candidates(":/text")
    with pytest.raises(InvalidSelectionError):
        mirror_ref_candidates("HEAD@{1}")


def test_a_branch_wins_over_a_tag_of_the_same_name_and_tags_peel(mirror: _Mirror) -> None:
    first = mirror.published.default_revision
    newer = mirror.commit("b.txt", "second\n", "second")
    _git(mirror.work, "tag", "topic", first)
    mirror.push("refs/heads/topic:refs/heads/topic", "refs/tags/topic:refs/tags/topic")
    assert _update(mirror) is RefreshOutcome.succeeded
    target = mirror.target

    branch = asyncio.run(resolve_pin(target, ref="topic"))
    assert branch.commit_oid == newer and branch.ref == "refs/remotes/origin/topic"
    tag = asyncio.run(resolve_pin(target, ref="refs/tags/topic"))
    assert tag.commit_oid == first and tag.ref == "refs/tags/topic"
    # v1 is an annotated tag: the pin is the commit it peels to, not the tag object.
    annotated = asyncio.run(resolve_pin(target, ref="v1"))
    assert annotated.commit_oid == first and annotated.ref == "refs/tags/v1"


def test_a_commit_id_resolves_full_abbreviated_and_through_ref_text(mirror: _Mirror) -> None:
    target = mirror.target
    commit = mirror.published.default_revision
    assert asyncio.run(resolve_pin(target, oid=commit)).commit_oid == commit
    assert asyncio.run(resolve_pin(target, oid=commit[:9])).commit_oid == commit
    assert asyncio.run(resolve_pin(target, oid=commit[:9].upper())).commit_oid == commit
    # No branch or tag has the name, so the hexadecimal text is a commit ID last.
    through_ref = asyncio.run(resolve_pin(target, ref=commit[:10]))
    assert through_ref.commit_oid == commit and through_ref.ref is None


@pytest.mark.parametrize(
    ("ref", "oid", "error"),
    [
        (None, None, InvalidSelectionError),
        ("topic", "0" * 40, InvalidSelectionError),
        ("", None, InvalidSelectionError),
        (":/first", None, InvalidSelectionError),
        ("topic@{1}", None, InvalidSelectionError),
        ("topic^{/first}", None, InvalidSelectionError),
        ("nope", None, SelectionNotFoundError),
        (None, "abc", InvalidSelectionError),
        (None, "not-hex-at-all", InvalidSelectionError),
        (None, "0" * 40, SelectionNotFoundError),
        (None, "0000000", SelectionNotFoundError),
    ],
)
def test_selections_that_cannot_be_pinned_are_typed(
    mirror: _Mirror, ref: str | None, oid: str | None, error: type[Exception]
) -> None:
    with pytest.raises(error):
        asyncio.run(resolve_pin(mirror.target, ref=ref, oid=oid))


def test_a_commit_id_naming_a_tree_is_not_a_commit(mirror: _Mirror) -> None:
    tree = _rev_parse(mirror.work, "HEAD^{tree}")
    with pytest.raises(SelectionNotFoundError):
        asyncio.run(resolve_pin(mirror.target, oid=tree))


def test_an_abbreviation_matching_several_commits_is_ambiguous(
    mirror: _Mirror, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Two real commits never share a seven-digit prefix on demand, so Git's list is fixed."""

    commit = mirror.published.default_revision
    newer = mirror.commit("b.txt", "second\n", "second")
    mirror.push("topic")
    assert _update(mirror) is RefreshOutcome.succeeded
    import metabrowser.cache.repository_store as repository_store

    real_run_git = repository_store.run_git

    async def listing(args: list[str], **kwargs: object) -> bytes:
        if any(arg.startswith("--disambiguate=") for arg in args):
            return f"{commit}\n{newer}\n".encode()
        return await real_run_git(args, **kwargs)  # type: ignore[arg-type]

    monkeypatch.setattr(repository_store, "run_git", listing)
    with pytest.raises(AmbiguousSelectionError):
        asyncio.run(resolve_pin(mirror.target, oid=commit[:7]))
