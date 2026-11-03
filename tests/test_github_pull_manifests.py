"""Prepared PR manifests survive a fresh server, heal, and stay store-scoped."""

from __future__ import annotations

import asyncio
import json
import zlib
from dataclasses import replace
from pathlib import Path
from typing import Any

import pytest
from starlette.testclient import TestClient

from metabrowser.builtin_plugins.diff import sidekick as diff
from metabrowser.builtin_plugins.diff.comparison_cache import ComparisonCache
from metabrowser.builtin_plugins.github import pull_manifest
from metabrowser.builtin_plugins.github.pull_record import Comparison, PullRecord
from metabrowser.diff.adapters.git import GitDiffSource
from metabrowser.diff.format import ResolvedComparison
from metabrowser.git.process import GitLocation, RepositoryStoreTarget
from metabrowser.http_caching import store_tag
from tests.diff_fixture_repo import git
from tests.test_github_pulls import _Stand
from tests.test_github_pulls import pinned_pull as pinned_pull
from tests.test_github_pulls import stand as stand


def _fresh(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(diff, "_COMPARISONS", ComparisonCache())


def test_fetch_prepares_a_manifest_that_a_fresh_server_reuses(
    pinned_pull: tuple[_Stand, TestClient], monkeypatch: pytest.MonkeyPatch
) -> None:
    stand, client = pinned_pull
    paths = tuple((stand.published.home / pull_manifest._directory(stand.published)).glob("*.json"))
    assert len(paths) == 1
    assert json.loads(paths[0].read_bytes())["document"]["patches"] == {}
    _fresh(monkeypatch)

    async def forbidden(_source: GitDiffSource, _resolved: ResolvedComparison) -> Any:
        raise AssertionError("a prepared manifest was recomputed")

    monkeypatch.setattr(GitDiffSource, "manifest", forbidden)
    route = client.get("/api/plugin/github/pull").json()["comparison_route"]
    stand.calls()
    first = client.get(route)
    assert first.status_code == 200
    assert "immutable" in first.headers["cache-control"]
    assert client.get(route).json() == first.json()
    assert client.get(route, headers={"if-none-match": first.headers["etag"]}).status_code == 304
    assert stand.calls() == [], "a comparison GET fetched the network"
    assert client.get(route.replace("number=7", "number=8")).status_code == 404
    assert (
        client.get(route.replace("base_policy=merge_base", "base_policy=direct")).status_code == 400
    )
    assert client.get(route.replace("left=", "revision=HEAD&left=")).status_code == 400


@pytest.mark.parametrize("damage", ["json", "digest", "identity", "schema", "oversize"])
def test_a_damaged_manifest_is_recomputed_once_and_healed(
    pinned_pull: tuple[_Stand, TestClient], monkeypatch: pytest.MonkeyPatch, damage: str
) -> None:
    stand, client = pinned_pull
    path = next((stand.published.home / pull_manifest._directory(stand.published)).glob("*.json"))
    original = path.read_bytes()
    payload = json.loads(original)
    if damage == "json":
        damaged = b"{broken"
    elif damage == "oversize":
        damaged = b"x" * (pull_manifest.MAX_MANIFEST_RECORD_BYTES + 1)
    else:
        if damage == "digest":
            payload["document"]["manifest"]["files"][0]["id"] = "wrong"
        elif damage == "identity":
            payload["identity"][-1] = "direct"
        else:
            payload["schema_version"] = 999
        damaged = json.dumps(payload).encode()
    path.write_bytes(damaged)
    calls = 0
    real = GitDiffSource.manifest

    async def counted(source: GitDiffSource, resolved: ResolvedComparison) -> Any:
        nonlocal calls
        calls += 1
        return await real(source, resolved)

    monkeypatch.setattr(GitDiffSource, "manifest", counted)
    _fresh(monkeypatch)
    route = client.get("/api/plugin/github/pull").json()["comparison_route"]
    first = client.get(route)
    assert first.status_code == 200
    assert client.get(route).json() == first.json()
    assert calls == 1
    assert path.read_bytes() == original


def test_attributes_builds_and_slot_collisions_are_cache_misses(
    pinned_pull: tuple[_Stand, TestClient], monkeypatch: pytest.MonkeyPatch
) -> None:
    stand, client = pinned_pull
    record = stand.record(7)
    assert isinstance(record, PullRecord) and record.comparison is not None
    calls = 0
    real = GitDiffSource.manifest

    async def counted(source: GitDiffSource, resolved: ResolvedComparison) -> Any:
        nonlocal calls
        calls += 1
        return await real(source, resolved)

    monkeypatch.setattr(GitDiffSource, "manifest", counted)
    _fresh(monkeypatch)
    monkeypatch.setattr(pull_manifest, "BUILD_TAG", "another-build")
    route = client.get("/api/plugin/github/pull").json()["comparison_route"]
    assert client.get(route).status_code == 200
    assert calls == 1
    (stand.published.git_dir / "info").mkdir(exist_ok=True)
    (stand.published.git_dir / "info" / "attributes").write_text("* binary\n")
    _fresh(monkeypatch)
    new_route = client.get("/api/plugin/github/pull").json()["comparison_route"]
    changed = client.get(new_route)
    assert changed.status_code == 200 and new_route != route
    assert calls == 2
    assert all(change["binary"] for change in changed.json()["manifest"]["files"])
    # One fixed slot forces a collision, which is only an eviction, never a wrong hit.
    monkeypatch.setattr(pull_manifest, "MANIFEST_SLOTS", 1)
    for build in ("one", "two", "one"):
        monkeypatch.setattr(pull_manifest, "BUILD_TAG", build)
        _fresh(monkeypatch)
        assert client.get(new_route).status_code == 200
    assert calls == 5


def test_persistence_failure_does_not_fail_the_pr_record(
    stand: _Stand, monkeypatch: pytest.MonkeyPatch
) -> None:
    def denied(*_args: Any, **_kwargs: Any) -> None:
        raise OSError("read-only cache")

    monkeypatch.setattr(pull_manifest, "write_private_file_atomic", denied)
    assert isinstance(stand.refresh(7), PullRecord)
    assert isinstance(stand.record(7), PullRecord)


def test_a_disk_hit_cannot_answer_for_a_missing_commit(
    pinned_pull: tuple[_Stand, TestClient], monkeypatch: pytest.MonkeyPatch
) -> None:
    _stand, client = pinned_pull
    _fresh(monkeypatch)
    envelope = client.get("/api/plugin/github/pull").json()
    base = envelope["record"]["comparison"]["base"]
    refused = client.get(envelope["comparison_route"].replace(f"left={base}", f"left={'0' * 40}"))
    assert refused.status_code == 404
    assert "unknown revision" in refused.json()["message"]
    assert "etag" not in refused.headers


def test_admission_is_a_cache_bound_and_never_a_serving_bound(
    pinned_pull: tuple[_Stand, TestClient], monkeypatch: pytest.MonkeyPatch
) -> None:
    _stand, client = pinned_pull
    _fresh(monkeypatch)
    route = client.get("/api/plugin/github/pull").json()["comparison_route"]
    expected = client.get(route).json()
    _fresh(monkeypatch)
    monkeypatch.setattr(pull_manifest, "MAX_MANIFEST_RECORD_BYTES", 1)
    assert client.get(route).json() == expected


def test_sha256_endpoints_round_trip_through_the_manifest_bank(
    stand: _Stand, tmp_path: Path
) -> None:
    work = tmp_path / "sha256"
    work.mkdir()
    git(work, "init", "-q", "--object-format=sha256", "-b", "main")
    (work / "a.py").write_text("one\n")
    git(work, "add", "a.py")
    git(work, "commit", "-qm", "one")
    base = git(work, "rev-parse", "HEAD").decode().strip()
    (work / "a.py").write_text("two\n")
    git(work, "commit", "-qam", "two")
    head = git(work, "rev-parse", "HEAD").decode().strip()
    assert len(base) == len(head) == 64
    published = replace(stand.published, git_dir=work / ".git", object_format="sha256")
    record = stand.refresh(7)
    record = record.model_copy(
        update={
            "comparison": Comparison(base=base, head=head, base_commit=base, base_from="base_sha")
        }
    )
    location = GitLocation.revision(RepositoryStoreTarget(published.git_dir, "sha256"), head)
    intent = {"left": base, "right": head, "base_policy": "merge_base"}
    key = diff.comparison_cache_key(location, intent, store_tag(published.git_dir))
    assert key is not None

    async def run() -> None:
        await pull_manifest.prepare_pull_manifest(published, record)
        kept = pull_manifest._read(published, key)
        assert kept is not None
        adopted = await pull_manifest.load_pull_manifest(
            published, GitDiffSource(location), intent, key
        )
        assert adopted == kept
        assert (adopted.resolved.left.id, adopted.resolved.right.id) == (base, head)

    asyncio.run(run())


@pytest.mark.parametrize(
    ("bank_mode", "deny_parent"), [(0o700, False), (0o500, False), (0o400, False), (0o500, True)]
)
def test_corrupt_manifest_is_discarded_before_backing_repair_and_restart(
    pinned_pull: tuple[_Stand, TestClient],
    monkeypatch: pytest.MonkeyPatch,
    bank_mode: int,
    deny_parent: bool,
) -> None:
    from metabrowser.git.object_failures import observed_object_failures
    from metabrowser.git.process import repository_store_target

    stand, client = pinned_pull
    route = client.get("/api/plugin/github/pull?number=7").json()["comparison_route"]
    expected = client.get(route).json()
    record = stand.record(7)
    assert isinstance(record, PullRecord) and record.comparison is not None
    store = stand.published.git_dir
    oid = git(store, "rev-parse", f"{record.comparison.head}:src/app.txt").decode().strip()
    genuine = git(store, "cat-file", "blob", oid)
    loose = store / "objects" / oid[:2] / oid[2:]
    loose.parent.mkdir(exist_ok=True)
    saved = loose.read_bytes() if loose.exists() else None
    # This private fixture's own object shadows an empty alternate; no checkout is changed.
    borrowed = stand.tmp_path / "empty-borrowed-objects"
    borrowed.mkdir()
    (store / "objects/info/alternates").write_text(str(borrowed) + "\n")
    forged = b"forged line\n" * 23
    assert forged != genuine
    loose.unlink(missing_ok=True)
    loose.write_bytes(zlib.compress(b"blob " + str(len(forged)).encode() + b"\0" + forged))
    directory = stand.published.home / pull_manifest._directory(stand.published)
    for path in directory.glob("*.json"):
        path.unlink()
    asyncio.run(pull_manifest.prepare_pull_manifest(stand.published, record))
    slot = next(directory.glob("*.json"))
    damaged = slot.read_bytes()
    directory.chmod(bank_mode)
    if deny_parent:
        directory.parent.chmod(0o500)
    try:
        if bank_mode == 0o500:
            with pytest.raises(PermissionError):
                (directory / "write-witness").write_bytes(b"must fail")
        stand.calls()
        _fresh(monkeypatch)
        refused = client.get(route)
        assert refused.status_code == 409
        assert refused.json()["error"] == "object_corrupt"
        if deny_parent:
            assert "could not be discarded" in refused.json()["message"]
            assert "Clear the affected repository cache" in refused.json()["message"]
            assert str(stand.tmp_path) not in refused.text
        else:
            assert "could not be discarded" not in refused.json()["message"]
        if bank_mode != 0o700 and not deny_parent:
            epoch = directory.parent / f"github-pull-manifest-{slot.stem}.epoch"
            assert len(epoch.read_bytes()) == 64
        # Restore genuine backing data, then discard process-local failure/cache state.
        if saved is None:
            loose.unlink()
        else:
            loose.write_bytes(saved)
        assert git(store, "cat-file", "blob", oid) == genuine
        observed_object_failures.forget_store(repository_store_target(git_dir=store))
        _fresh(monkeypatch)
        replayed = client.get(route)
        assert replayed.status_code == 200
        assert replayed.json() == expected, "a repaired object must not replay forged statistics"
        if bank_mode == 0o500:
            assert slot.read_bytes() == damaged, "the read-only bank was not modified"
        directory.parent.chmod(0o700)
        directory.chmod(0o700)
        if deny_parent:
            # Neither invalidation could persist; the refusal requires explicit clearing.
            assert slot.read_bytes() == damaged
            pull_manifest.write_private_file_atomic(
                stand.published.home, str(slot.relative_to(stand.published.home)), b"{}"
            )
        # A retained epoch survives restored permissions and process restart, without
        # manual clearing. Only the all-writes-failed case above requires that action.
        _fresh(monkeypatch)
        assert client.get(route).json() == expected
        assert slot.read_bytes() != damaged
        _fresh(monkeypatch)

        async def forbidden(_source: GitDiffSource, _resolved: ResolvedComparison) -> Any:
            raise AssertionError("the healed writable bank must resume ordinary cache hits")

        monkeypatch.setattr(GitDiffSource, "manifest", forbidden)
        assert client.get(route).json() == expected
        assert stand.calls() == [], "neither read-only serving nor repair reads may fetch"
    finally:
        directory.parent.chmod(0o700)
        directory.chmod(0o700)


@pytest.mark.parametrize("bank_mode", [0o700, 0o500])
def test_manifest_computation_cannot_relabel_itself_after_invalidation(
    pinned_pull: tuple[_Stand, TestClient], monkeypatch: pytest.MonkeyPatch, bank_mode: int
) -> None:
    stand, client = pinned_pull
    record = stand.record(7)
    assert isinstance(record, PullRecord) and record.comparison is not None
    pair = (record.comparison.base, record.comparison.head)
    route = client.get("/api/plugin/github/pull").json()["comparison_route"]
    directory = stand.published.home / pull_manifest._directory(stand.published)
    slot = next(directory.glob("*.json"))
    original_epoch = json.loads(slot.read_bytes())["epoch"]
    slot.write_bytes(b"{}")
    real = GitDiffSource.manifest
    calls = 0

    async def invalidated(source: GitDiffSource, resolved: ResolvedComparison) -> Any:
        nonlocal calls
        calls += 1
        answer = await real(source, resolved)
        if calls == 1:
            directory.chmod(bank_mode)
            try:
                pull_manifest.invalidate_pull_manifest(stand.published, pair)
            finally:
                directory.chmod(0o700)
        return answer

    monkeypatch.setattr(GitDiffSource, "manifest", invalidated)
    _fresh(monkeypatch)
    expected = client.get(route).json()
    assert calls == 1
    # The completed old computation wrote its original epoch, not the new quarantine.
    assert json.loads(slot.read_bytes())["epoch"] == original_epoch
    _fresh(monkeypatch)
    assert client.get(route).json() == expected
    assert calls == 2
    assert len(json.loads(slot.read_bytes())["epoch"]) == 64
    _fresh(monkeypatch)
    assert client.get(route).json() == expected
    assert calls == 2


@pytest.mark.parametrize("damage", ["missing", "invalid", "symlink"])
def test_unusable_epoch_bypasses_persistence_without_changing_private_paths(
    pinned_pull: tuple[_Stand, TestClient], monkeypatch: pytest.MonkeyPatch, damage: str
) -> None:
    stand, client = pinned_pull
    route = client.get("/api/plugin/github/pull").json()["comparison_route"]
    expected = client.get(route).json()
    directory = stand.published.home / pull_manifest._directory(stand.published)
    slot = next(directory.glob("*.json"))
    path = directory.parent / f"github-pull-manifest-{slot.stem}.epoch"
    victim = stand.tmp_path / "untouched"
    victim.write_bytes(b"private witness")
    path.unlink()
    if damage == "invalid":
        path.write_bytes(b"invalid epoch")
        path.chmod(0o600)
    elif damage == "symlink":
        path.symlink_to(victim)
    real = GitDiffSource.manifest
    calls = 0

    async def counted(source: GitDiffSource, resolved: ResolvedComparison) -> Any:
        nonlocal calls
        calls += 1
        return await real(source, resolved)

    monkeypatch.setattr(GitDiffSource, "manifest", counted)
    _fresh(monkeypatch)
    assert client.get(route).json() == expected
    assert calls == 1
    assert victim.read_bytes() == b"private witness"
    if damage == "symlink":
        assert path.is_symlink()
    elif damage == "invalid":
        assert path.read_bytes() == b"invalid epoch"
    else:
        assert len(path.read_bytes()) == 64


def test_invalidation_preserves_other_slots_and_their_disk_hits(
    pinned_pull: tuple[_Stand, TestClient], monkeypatch: pytest.MonkeyPatch
) -> None:
    stand, client = pinned_pull
    first = stand.record(7)
    other = stand.refresh(8)
    assert isinstance(first, PullRecord) and first.comparison is not None
    assert isinstance(other, PullRecord) and other.comparison is not None

    def key_for(comparison: Comparison) -> tuple[str, ...]:
        location = GitLocation.revision(
            RepositoryStoreTarget(stand.published.git_dir, stand.published.object_format),
            comparison.head,
        )
        intent = {"left": comparison.base, "right": comparison.head, "base_policy": "merge_base"}
        key = diff.comparison_cache_key(location, intent, store_tag(stand.published.git_dir))
        assert key is not None
        return key

    first_key, other_key = key_for(first.comparison), key_for(other.comparison)
    # Slot collisions are legitimate evictions. Choose a namespace in which these two
    # actual comparisons do not collide, so this test exercises isolation instead.
    for namespace in range(32):
        monkeypatch.setattr(pull_manifest, "BUILD_TAG", f"slot-isolation-{namespace}")
        if pull_manifest._slot(first_key) != pull_manifest._slot(other_key):
            break
    else:
        raise AssertionError("could not separate the fixture comparison slots")
    route = client.get("/api/plugin/github/pull").json()["comparison_route"]
    _fresh(monkeypatch)
    expected = client.get(route).json()
    asyncio.run(pull_manifest.prepare_pull_manifest(stand.published, other))
    epoch = stand.published.home / pull_manifest._epoch_path(stand.published, first_key)
    old = epoch.read_bytes()
    pull_manifest.invalidate_pull_manifest(
        stand.published, (other.comparison.base, other.comparison.head)
    )
    assert epoch.read_bytes() == old
    _fresh(monkeypatch)

    async def forbidden(_source: GitDiffSource, _resolved: ResolvedComparison) -> Any:
        raise AssertionError("another slot's invalidation discarded this healthy disk hit")

    monkeypatch.setattr(GitDiffSource, "manifest", forbidden)
    assert client.get(route).json() == expected
