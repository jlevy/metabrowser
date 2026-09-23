"""Publish a validated staging store and reuse a cache hit. No serving."""

from __future__ import annotations

import asyncio
import os
import shutil
from pathlib import Path

import pytest

from metabrowser.cache import acquire as acquire_module
from metabrowser.cache.acquire import (
    AliasConflictError,
    acquire_file_source,
    acquire_into_staging,
    publish_from_staging,
)
from metabrowser.cache.atomic import write_record_atomic
from metabrowser.cache.layout import open_cache
from metabrowser.cache.paths import SOURCES, STAGING, source_record, store_directory
from metabrowser.cache.records import REPOSITORY_STORE_ALIAS_CONTRACT_ID, RepositoryStoreAlias
from tests.test_cache_acquire import _allow_installed_git, _file_source, _origin

posix_only = pytest.mark.skipif(os.name != "posix", reason="owner-only cache is POSIX-only")


@posix_only
def test_publish_makes_the_source_visible_and_clears_staging(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _allow_installed_git(monkeypatch)
    origin = _origin(tmp_path)
    home = tmp_path / "home"
    source = _file_source(origin)
    staged = asyncio.run(acquire_into_staging(source, home=home))
    published = publish_from_staging(staged)
    assert published.git_dir.is_dir()
    assert published.git_dir == home / store_directory(published.store_key) / "repository.git"
    assert (home / source_record(published.slug, "source.yml")).is_file()
    assert (home / source_record(published.slug, "store-alias.yml")).is_file()
    assert (home / store_directory(published.store_key) / "store.yml").is_file()
    assert list((home / STAGING).iterdir()) == []
    assert published.default_revision


@posix_only
def test_a_second_acquire_reuses_the_store_without_fetching(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _allow_installed_git(monkeypatch)
    origin = _origin(tmp_path)
    home = tmp_path / "home"
    source = _file_source(origin)
    first = asyncio.run(acquire_file_source(source, home=home))
    fetches = 0
    real_run = acquire_module._run

    async def counting_run(
        args: list[str], *, cwd: Path | None = None, git_dir: Path | None = None
    ) -> bytes:
        nonlocal fetches
        if "fetch" in args:
            fetches += 1
        return await real_run(args, cwd=cwd, git_dir=git_dir)

    monkeypatch.setattr(acquire_module, "_run", counting_run)
    second = asyncio.run(acquire_file_source(source, home=home))
    assert fetches == 0
    assert second.store_key == first.store_key
    assert second.slug == first.slug
    assert second.git_dir == first.git_dir
    assert list((home / STAGING).iterdir()) == []


@posix_only
def test_an_alias_that_names_a_different_store_is_left_in_place(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _allow_installed_git(monkeypatch)
    origin = _origin(tmp_path)
    home = tmp_path / "home"
    source = _file_source(origin)
    published = asyncio.run(acquire_file_source(source, home=home))
    other_store = "sha256:" + "ab" * 32
    write_record_atomic(
        home,
        source_record(published.slug, "store-alias.yml"),
        RepositoryStoreAlias(
            source_id=published.source_id,
            store_id=other_store,
            generation=1,
            updated_at="2026-09-18T00:00:00Z",
        ),
        REPOSITORY_STORE_ALIAS_CONTRACT_ID,
        replace=True,
    )
    with pytest.raises(AliasConflictError):
        asyncio.run(acquire_file_source(source, home=home))
    alias = (home / source_record(published.slug, "store-alias.yml")).read_text(encoding="utf-8")
    assert other_store in alias
    assert (home / source_record(published.slug, "source.yml")).is_file()


@posix_only
def test_a_store_left_unreferenced_is_kept_and_reused_by_the_next_acquire(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _allow_installed_git(monkeypatch)
    origin = _origin(tmp_path)
    home = tmp_path / "home"
    source = _file_source(origin)
    staged = asyncio.run(acquire_into_staging(source, home=home))
    published = publish_from_staging(staged)
    for entry in (home / SOURCES).iterdir():
        if entry.is_dir():
            shutil.rmtree(entry)
    store_inode = published.git_dir.stat().st_ino

    open_cache(home)
    assert published.git_dir.stat().st_ino == store_inode

    again = asyncio.run(acquire_file_source(source, home=home))
    assert again == published
    assert published.git_dir.stat().st_ino == store_inode
    assert list((home / STAGING).iterdir()) == []
