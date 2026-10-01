"""Golden CLI transcripts for file:// acquisition.

Successful ``metab file:// --no-serve`` cannot run as a tryscript subprocess
where the installed Git is below the acquisition floor, which has no environment
escape by design. These goldens invoke the production CLI in-process with only
``require_acquisition_git`` and the clock replaced -- the same boundary
``tests/test_cache_acquire.py`` uses to exercise fetch -- and pin logical
identity: publication, transport, object format, remote-tracking ref, the
deterministic revision, and every recorded time. The slug, the store and source
ids, and the file:// URL depend on the sandbox path, and the Git and package
versions on the host, so those are labels (``tests/golden_harness.py``). The
origin branch is ``topic`` so the remote-tracking ref is not the default-branch
spelling public hygiene rejects; ``--initial-branch`` still pins the name so it
does not vary by Git version.
"""

from __future__ import annotations

import os
import shutil
from pathlib import Path

import pytest

from metabrowser.cache.layout import migrate_layout
from metabrowser.cache.paths import staging_entry
from metabrowser.home import ensure_home, ensure_private_directory
from tests.cache_home_fixture import (
    FIXTURE_VERSION,
    LEFTOVER_STAGING_ENTRY,
    _stage_and_publish_store,
)
from tests.golden_harness import (
    Invocation,
    Labels,
    check_golden,
    file_url,
    isolate_cli,
    ok,
    pinned_git,
)
from tests.test_cache_acquire import _remove_owner_write, _restore_owner_write

# Pinned by the identity and dates of ``pinned_git_env`` and the origin recipe below.
# A commit hash is a function of tree, parents, author, committer, and message.
ORIGIN_REVISION = "8f05aafe23bbeade03ef581868a59e3c944ac5c4"
ORIGIN_REMOTE_REF = "refs/remotes/origin/topic"

posix_only = pytest.mark.skipif(os.name != "posix", reason="owner-only cache is POSIX-only")
skip_as_root = pytest.mark.skipif(
    os.geteuid() == 0, reason="root is never denied by modes, so a denial cannot be staged"
)

pytestmark = pytest.mark.skipif(shutil.which("git") is None, reason="git executable is required")


def deterministic_origin(tmp_path: Path) -> Path:
    """A bare origin whose HEAD is ``ORIGIN_REVISION`` on every machine."""

    work = tmp_path / "work"
    origin = tmp_path / "origin.git"
    work.mkdir()
    pinned_git(work, "init", "-q", "--initial-branch=topic")
    (work / "README").write_text("hello\n", encoding="utf-8")
    pinned_git(work, "add", "README")
    pinned_git(work, "-c", "commit.gpgsign=false", "commit", "-qm", "first")
    pinned_git(work, "clone", "--bare", "--template=", "--", str(work), str(origin))
    assert pinned_git(origin, "rev-parse", "HEAD") == ORIGIN_REVISION
    return origin


def _labels(url: str) -> Labels:
    labels = Labels()
    labels.origin(url, store="STORE_ID", source="SOURCE_ID")
    return labels


def _transcript(tmp_path: Path, labels: Labels, blocks: list[tuple[str, Invocation]]) -> str:
    rendered = labels.apply("".join(result.block(command) for command, result in blocks))
    assert str(tmp_path) not in rendered
    return rendered


NO_SERVE = "file://<ORIGIN> --no-serve"


def _api(root: Path, route: str) -> tuple[str, Invocation]:
    return f"<ROOT> --api {route}", ok([str(root), "--api", route])


def _empty_root(tmp_path: Path) -> Path:
    root = tmp_path / "root"
    root.mkdir()
    return root


@posix_only
def test_golden_file_url_acquire_and_reuse(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    home = isolate_cli(tmp_path, monkeypatch).home
    url = file_url(deterministic_origin(tmp_path))
    root = _empty_root(tmp_path)

    first = ok([url, "--no-serve"])
    second = ok([url, "--no-serve"])
    assert first.stdout == second.stdout
    assert ORIGIN_REVISION in first.stdout
    assert str(home) not in first.stdout
    assert "Serving" not in first.stdout

    layout = _api(root, "/api/cache/layout")
    sources = _api(root, "/api/cache/sources")
    stores = _api(root, "/api/cache/stores")
    assert ORIGIN_REVISION in stores[1].stdout
    assert ORIGIN_REMOTE_REF in stores[1].stdout
    assert '"object_format": "sha1"' in stores[1].stdout
    assert '"transport": "file"' in sources[1].stdout
    assert '"publication": "published"' in sources[1].stdout

    blocks = [(NO_SERVE, first), (NO_SERVE, second), layout, sources, stores]
    check_golden("cli-cache-acquire.txt", _transcript(tmp_path, _labels(url), blocks))


@posix_only
def test_golden_lock_free_staging_is_swept_on_acquire(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    home = isolate_cli(tmp_path, monkeypatch).home
    ensure_home(home)
    migrate_layout(home, version=FIXTURE_VERSION)
    ensure_private_directory(home, f"{staging_entry(LEFTOVER_STAGING_ENTRY)}/repository.git")
    root = _empty_root(tmp_path)

    before = _api(root, "/api/cache/layout")
    assert '"staging_entries": 1' in before[1].stdout

    url = file_url(deterministic_origin(tmp_path))
    acquired = ok([url, "--no-serve"])

    after = _api(root, "/api/cache/layout")
    assert '"staging_entries": 0' in after[1].stdout
    assert list((home / "cache" / "staging").iterdir()) == []

    blocks = [before, (NO_SERVE, acquired), after]
    check_golden("cli-cache-recover.txt", _transcript(tmp_path, _labels(url), blocks))


FIRST_ORPHAN_KEY = "0" * 64


@posix_only
def test_golden_unreferenced_store_is_kept_by_the_next_acquire(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    home = isolate_cli(tmp_path, monkeypatch).home
    # The acquired store's key hashes a URL under tmp_path, so /api/cache/stores lists
    # the two stores in a different order from run to run unless the orphan's key
    # sorts first whatever that hash is.
    ensure_home(home)
    migrate_layout(home, version=FIXTURE_VERSION)
    _stage_and_publish_store(home, FIRST_ORPHAN_KEY, with_revision=False)
    root = _empty_root(tmp_path)

    before = _api(root, "/api/cache/stores")
    assert '"reference_state": "unreferenced"' in before[1].stdout
    assert f"sha256:{FIRST_ORPHAN_KEY}" in before[1].stdout

    url = file_url(deterministic_origin(tmp_path))
    acquired = ok([url, "--no-serve"])

    after = _api(root, "/api/cache/stores")
    assert '"reference_state": "unreferenced"' in after[1].stdout
    assert '"reference_state": "referenced"' in after[1].stdout
    assert f"sha256:{FIRST_ORPHAN_KEY}" in after[1].stdout
    assert ORIGIN_REVISION in after[1].stdout
    assert list((home / "cache" / "repository-stores").iterdir()) != []

    blocks = [before, (NO_SERVE, acquired), after]
    check_golden("cli-cache-orphan-kept.txt", _transcript(tmp_path, _labels(url), blocks))


@posix_only
@skip_as_root
def test_golden_cache_hit_against_a_home_without_owner_write(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    home = isolate_cli(tmp_path, monkeypatch).home
    url = file_url(deterministic_origin(tmp_path))
    first = ok([url, "--no-serve"])
    _remove_owner_write(home)
    try:
        second = ok([url, "--no-serve"])
        assert first.stdout == second.stdout
        assert ORIGIN_REVISION in second.stdout
        blocks = [(NO_SERVE, first), (NO_SERVE, second)]
        check_golden("cli-cache-readonly-hit.txt", _transcript(tmp_path, _labels(url), blocks))
    finally:
        _restore_owner_write(home)
