"""The ``f01`` to ``f02`` migration: whole-digest store names become readable keys.

Released ``f01`` homes name each store by all 64 digits of its identity. Every home here
is a current home rewritten as that release wrote it
(:func:`tests.cache_home_fixture.rewrite_as_f01`), so the migration is judged against the
shapes the writers of that release left.
"""

from __future__ import annotations

import asyncio
import logging
import os
import shutil
from pathlib import Path

import pytest

from metabrowser.cache import acquire as acquire_module
from metabrowser.cache.acquire import acquire_source, cached_source
from metabrowser.cache.atomic import read_record, write_record_atomic
from metabrowser.cache.identity import (
    identity_digest,
    is_store_key,
    store_key_candidates,
    store_key_matches_identity,
)
from metabrowser.cache.layout import migrate_layout, open_cache, read_layout
from metabrowser.cache.paths import REPOSITORY_STORES, store_directory
from metabrowser.cache.records import (
    REPOSITORY_STORE_CONTRACT_ID,
    CacheLayout,
    RepositoryStore,
)
from metabrowser.cache.store_rename import (
    UNATTACHED_READABLE,
    is_legacy_store_key,
    rename_legacy_stores,
)
from tests.cache_home_fixture import (
    FLASK_HTTPS,
    FLASK_STORE,
    ORPHAN_STORE,
    build_populated_home,
    rewrite_as_f01,
)
from tests.test_cache_acquire import _allow_installed_git, _file_source, _origin
from tests.test_cache_acquire import _git as git
from tests.test_cache_acquire import _occupy_store_key as occupy

posix_only = pytest.mark.skipif(os.name != "posix", reason="owner-only cache is POSIX-only")


def _names(home: Path) -> set[str]:
    return {entry.name for entry in (home / REPOSITORY_STORES).iterdir()}


def test_a_whole_digest_is_a_legacy_name_and_a_key_is_not() -> None:
    assert is_legacy_store_key("a" * 64)
    assert not is_legacy_store_key("a" * 63)
    assert not is_legacy_store_key("A" * 64)
    assert not is_legacy_store_key(FLASK_STORE.key)


@posix_only
def test_an_f01_home_has_its_stores_renamed_where_they_stand(tmp_path: Path) -> None:
    home = tmp_path / "home"
    build_populated_home(home)
    old = rewrite_as_f01(home)
    inodes = {digest: (home / REPOSITORY_STORES / digest).stat().st_ino for digest in old.values()}
    pack = f"repository.git/objects/pack/pack-{FLASK_STORE.id.removeprefix('sha256:')[:40]}.pack"
    assert is_legacy_store_key(old[FLASK_STORE.key])

    outcome = migrate_layout(home, version="0.13.0")

    assert outcome.previous_format == "f01" and outcome.migrated_through == ("f02",)
    layout = read_layout(home)
    assert layout is not None and layout.format == "f02"
    flask = home / store_directory(FLASK_STORE.key)
    assert flask.is_dir()
    assert (flask / pack).read_bytes() == b"PACK"
    # A rename and not a copy: the same directory, so nothing was fetched or duplicated.
    assert flask.stat().st_ino == inodes[old[FLASK_STORE.key]]
    assert not any(is_legacy_store_key(name) for name in _names(home))
    assert all(is_store_key(name) for name in _names(home))
    assert not (home / "locks/stores" / f"{old[FLASK_STORE.key]}.lock").exists()
    assert not (home / "locks/stores" / f"{old[FLASK_STORE.key]}.fetch.lock").exists()


@posix_only
def test_a_store_a_readable_alias_names_takes_that_repository_and_the_rest_are_unattached(
    tmp_path: Path,
) -> None:
    home = tmp_path / "home"
    build_populated_home(home)
    rewrite_as_f01(home)

    open_cache(home, version="0.13.0")

    # flask's alias names its store, so the key says flask. click's source was published
    # without one, which is the crash a store is left unreferenced by.
    assert FLASK_STORE.key in _names(home)
    (orphan,) = _names(home) - {FLASK_STORE.key}
    assert orphan == f"{UNATTACHED_READABLE}--{identity_digest(ORPHAN_STORE.id)[:16]}"
    assert is_store_key(orphan) and store_key_matches_identity(orphan, ORPHAN_STORE.id)


@posix_only
def test_running_the_migration_again_changes_nothing(tmp_path: Path) -> None:
    home = tmp_path / "home"
    build_populated_home(home)
    rewrite_as_f01(home)
    open_cache(home, version="0.13.0")
    before = _names(home)

    rename_legacy_stores(home)

    assert _names(home) == before


@posix_only
def test_an_interrupted_migration_resumes_with_what_is_left(tmp_path: Path) -> None:
    home = tmp_path / "home"
    build_populated_home(home)
    old = rewrite_as_f01(home)
    # One store was renamed before the process died; the layout still says f01.
    (home / REPOSITORY_STORES / old[FLASK_STORE.key]).rename(
        home / REPOSITORY_STORES / FLASK_STORE.key
    )

    outcome = migrate_layout(home, version="0.13.0")

    assert outcome.layout.format == "f02"
    assert FLASK_STORE.key in _names(home)
    assert not any(is_legacy_store_key(name) for name in _names(home))


@posix_only
def test_a_store_whose_record_does_not_name_its_directory_is_left_alone(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    home = tmp_path / "home"
    build_populated_home(home)
    old = rewrite_as_f01(home)
    damaged = old[ORPHAN_STORE.key]
    record = read_record(
        home, f"{REPOSITORY_STORES}/{damaged}/store.yml", REPOSITORY_STORE_CONTRACT_ID
    )
    assert isinstance(record, RepositoryStore)
    write_record_atomic(
        home,
        f"{REPOSITORY_STORES}/{damaged}/store.yml",
        record.model_copy(update={"id": "sha256:" + "e" * 64}),
        REPOSITORY_STORE_CONTRACT_ID,
    )

    with caplog.at_level(logging.WARNING, logger="metabrowser.cache.store_rename"):
        open_cache(home, version="0.13.0")

    assert damaged in _names(home)
    assert FLASK_STORE.key in _names(home)
    assert "does not name its directory" in caplog.text


@posix_only
def test_a_name_another_store_holds_is_skipped_and_never_shared(tmp_path: Path) -> None:
    home = tmp_path / "home"
    build_populated_home(home)
    # The first key flask's store may have is held by a different store.
    first, second, *_ = store_key_candidates("https", FLASK_HTTPS.address, FLASK_STORE.id)
    assert first == FLASK_STORE.key
    old = rewrite_as_f01(home)
    occupy(home, first, store_id="sha256:" + "f" * 64)

    open_cache(home, version="0.13.0")

    assert (home / store_directory(first) / "store.yml").is_file()
    assert not (home / store_directory(first) / "repository.git").exists()
    assert (home / store_directory(second) / "repository.git").is_dir()
    assert old[FLASK_STORE.key] not in _names(home)


@posix_only
def test_a_cache_with_no_stores_directory_is_migrated_and_nothing_is_created(
    tmp_path: Path,
) -> None:
    home = tmp_path / "home"
    build_populated_home(home)
    rewrite_as_f01(home)
    shutil.rmtree(home / REPOSITORY_STORES)

    rename_legacy_stores(home)

    assert not (home / REPOSITORY_STORES).exists()


@posix_only
def test_a_released_home_is_a_cache_hit_after_the_migration_and_never_a_new_clone(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The reason the stores are renamed: a store can be gigabytes, and re-cloning is waste.

    A real store is acquired, rewritten as the release that wrote ``f01`` left it, and
    opened again. The open migrates the home, finds the store where it was, and neither
    asks a provider about the repository nor fetches it: offline reading survives the
    upgrade.
    """

    _allow_installed_git(monkeypatch)
    origin = _origin(tmp_path)
    home = tmp_path / "home"
    source = _file_source(origin)
    first = asyncio.run(acquire_source(source, home=home))
    inode = first.git_dir.stat().st_ino
    git(first.git_dir, "rev-parse", "HEAD")
    old = rewrite_as_f01(home)
    assert not first.git_dir.exists()
    assert cached_source(source, home) is None, "a read that cannot migrate is a miss"

    async def no_provider_asked(_source: object) -> None:
        raise AssertionError("a store that is cached must not be looked up at the provider")

    async def no_fetch(*_args: object, **_kwargs: object) -> object:
        raise AssertionError("a store that is cached must not be fetched")

    monkeypatch.setattr(acquire_module, "check_first_clone", no_provider_asked)
    monkeypatch.setattr(acquire_module, "acquire_into_staging", no_fetch)
    second = asyncio.run(acquire_source(source, home=home))

    assert second.store_key == first.store_key
    assert second.git_dir == first.git_dir and second.git_dir.is_dir()
    assert second.git_dir.stat().st_ino == inode
    assert not second.fetched
    assert read_layout(home) == CacheLayout(format="f02", created_by="0.12.0")
    assert old[first.store_key] not in _names(home)
    git(second.git_dir, "rev-parse", "HEAD")
    found = cached_source(source, home)
    assert found is not None and found.store_key == first.store_key
