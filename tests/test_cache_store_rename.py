"""The ``f01`` and ``f02`` to ``f03`` migration: older store names become current keys.

Released ``f01`` homes name each store by all 64 digits of its identity, and ``f02`` homes
by its repository's words joined by ``--`` and 16 hexadecimal digits. Every home here is a
current home rewritten as the release that wrote that format left it
(:func:`tests.cache_home_fixture.rewrite_as_f01` and ``rewrite_as_f02``), so the migration
is judged against the shapes the writers of those releases left.
"""

from __future__ import annotations

import asyncio
import logging
import os
import shutil
import threading
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pytest

from metabrowser.cache import acquire as acquire_module
from metabrowser.cache import projection
from metabrowser.cache.acquire import acquire_source, cached_source
from metabrowser.cache.atomic import read_record, write_record_atomic
from metabrowser.cache.identity import (
    StoreKeyCollisionError,
    is_store_key,
    store_key_candidates,
    store_key_matches_identity,
    store_key_suffixes,
)
from metabrowser.cache.layout import migrate_layout, open_cache, read_layout
from metabrowser.cache.paths import (
    REPOSITORY_STORES,
    source_directory,
    source_record,
    store_directory,
)
from metabrowser.cache.records import (
    REPOSITORY_STORE_CONTRACT_ID,
    CacheLayout,
    RepositoryStore,
)
from metabrowser.cache.store_rename import (
    DERIVED_OBJECT_FORMATS,
    F02_KEY_SUFFIX_HEX_DIGITS,
    MAX_MIGRATED_ENTRIES,
    UNATTACHED_READABLE,
    NoFreeTargetError,
    Rename,
    apply_renames,
    f02_key_parts,
    is_f02_store_key,
    is_legacy_store_key,
    plan_store_renames,
    rename_legacy_stores,
)
from metabrowser.git.process import OBJECT_FORMATS
from tests.cache_home_fixture import (
    CLICK,
    FLASK_HTTPS,
    FLASK_STORE,
    ORPHAN_STORE,
    FixtureSource,
    build_populated_home,
    rewrite_as_f01,
    rewrite_as_f02,
)
from tests.test_cache_acquire import _allow_installed_git, _file_source, _origin
from tests.test_cache_acquire import _git as git
from tests.test_cache_acquire import _occupy_store_key as occupy

posix_only = pytest.mark.skipif(os.name != "posix", reason="owner-only cache is POSIX-only")

type Rewrite = Callable[[Path], dict[str, str]]
REWRITES: dict[str, Rewrite] = {"f01": rewrite_as_f01, "f02": rewrite_as_f02}
OLD_NAMES: dict[str, Callable[[str], bool]] = {
    "f01": is_legacy_store_key,
    "f02": is_f02_store_key,
}
# What a home of each format migrates through to reach the current one.
CHAINS: dict[str, tuple[str, ...]] = {"f01": ("f02", "f03"), "f02": ("f03",)}


@pytest.fixture(params=["f01", "f02"])
def old_format(request: pytest.FixtureRequest) -> str:
    return str(request.param)


def _names(home: Path) -> set[str]:
    return {entry.name for entry in (home / REPOSITORY_STORES).iterdir()}


def _old_home(tmp_path: Path, old_format: str) -> tuple[Path, dict[str, str]]:
    """A populated home rewritten as *old_format* left it, and each store's old name."""

    home = tmp_path / "home"
    build_populated_home(home)
    return home, REWRITES[old_format](home)


def test_a_whole_digest_is_a_legacy_name_and_a_key_is_not() -> None:
    assert is_legacy_store_key("a" * 64)
    assert not is_legacy_store_key("a" * 63)
    assert not is_legacy_store_key("A" * 64)
    assert not is_legacy_store_key(FLASK_STORE.key)
    assert not is_legacy_store_key("github-com--pallets--flask--4c2d8559cb0179ba")


def test_an_f02_name_is_words_joined_by_double_dashes_and_hexadecimal_digits() -> None:
    assert F02_KEY_SUFFIX_HEX_DIGITS == (16, 24, 32, 64)
    assert f02_key_parts("github-com--pallets--flask--4c2d8559cb0179ba") == (
        "github-com--pallets--flask",
        "4c2d8559cb0179ba",
    )
    assert f02_key_parts("unattached--" + "0" * 64) == ("unattached", "0" * 64)
    for name in (
        FLASK_STORE.key,
        "a" * 64,
        "github-com--pallets--flask",
        "github-com--pallets--flask--4c2d8559cb0179b",
        "github-com--pallets--flask--4c2d8559cb0179bA",
        "github-com--pallets--flask--4c2d8559cb0179bg",
        "--4c2d8559cb0179ba",
        "github-com--pallets--flask--4c2d8559cb0179ba/..",
        "",
    ):
        assert f02_key_parts(name) is None, name
        assert not is_f02_store_key(name), name


def test_no_name_is_a_key_and_an_older_name_at_once() -> None:
    for name in (FLASK_STORE.key, ORPHAN_STORE.key):
        assert is_store_key(name)
        assert not is_legacy_store_key(name) and not is_f02_store_key(name)
    assert not is_store_key("github-com--pallets--flask--4c2d8559cb0179ba")
    assert not is_store_key("a" * 64)


@posix_only
def test_an_old_home_has_its_stores_renamed_where_they_stand(
    tmp_path: Path, old_format: str
) -> None:
    home, old = _old_home(tmp_path, old_format)
    inodes = {name: (home / REPOSITORY_STORES / name).stat().st_ino for name in old.values()}
    pack = f"repository.git/objects/pack/pack-{FLASK_STORE.id.removeprefix('sha256:')[:40]}.pack"
    assert OLD_NAMES[old_format](old[FLASK_STORE.key])

    outcome = migrate_layout(home, version="0.13.0")

    assert outcome.previous_format == old_format
    assert outcome.migrated_through == CHAINS[old_format]
    layout = read_layout(home)
    assert layout is not None and layout.format == "f03"
    flask = home / store_directory(FLASK_STORE.key)
    assert flask.is_dir()
    assert (flask / pack).read_bytes() == b"PACK"
    # A rename and not a copy: the same directory, so nothing was fetched or duplicated.
    assert flask.stat().st_ino == inodes[old[FLASK_STORE.key]]
    assert not any(OLD_NAMES[old_format](name) for name in _names(home))
    assert all(is_store_key(name) for name in _names(home))
    # Its lock files are left: an older process may hold one, and an empty file costs nothing.
    assert (home / "locks/stores" / f"{old[FLASK_STORE.key]}.lock").exists()


@posix_only
def test_the_key_a_store_is_renamed_to_is_the_one_a_lookup_computes(
    tmp_path: Path, old_format: str
) -> None:
    home, _old = _old_home(tmp_path, old_format)

    open_cache(home, version="0.13.0")

    (flask,) = [name for name in _names(home) if name.startswith("github-com-pallets-flask-")]
    assert flask == store_key_candidates("https", FLASK_HTTPS.address, FLASK_STORE.id)[0]
    assert store_key_matches_identity(flask, FLASK_STORE.id)


@posix_only
def test_a_store_keeps_the_name_of_the_repository_of_a_source_that_names_or_derives_it(
    tmp_path: Path, old_format: str
) -> None:
    home, _old = _old_home(tmp_path, old_format)

    open_cache(home, version="0.13.0")

    # flask's alias names its store, so the key says flask. click's source was published
    # with no alias, which is the crash a store is left unreferenced by, and its identity
    # derives the store: it keeps click's name, so click's next acquisition reuses it.
    assert _names(home) == {FLASK_STORE.key, ORPHAN_STORE.key}
    assert ORPHAN_STORE.key.startswith("github-com-pallets-click-")


@posix_only
def test_an_f01_store_no_source_names_is_unattached(tmp_path: Path) -> None:
    home, _old = _old_home(tmp_path, "f01")
    shutil.rmtree(home / source_directory(CLICK.slug))

    open_cache(home, version="0.13.0")

    (orphan,) = _names(home) - {FLASK_STORE.key}
    assert orphan == f"{UNATTACHED_READABLE}-{store_key_suffixes(ORPHAN_STORE.id)[0]}"
    assert is_store_key(orphan) and store_key_matches_identity(orphan, ORPHAN_STORE.id)


@posix_only
def test_an_f02_store_no_source_names_keeps_the_words_its_name_had(tmp_path: Path) -> None:
    home, old = _old_home(tmp_path, "f02")
    shutil.rmtree(home / source_directory(CLICK.slug))
    assert old[ORPHAN_STORE.key].startswith("github-com--pallets--click--")

    open_cache(home, version="0.13.0")

    # Nothing names the repository now, but its old name did, and `--` becomes `-`.
    assert _names(home) == {FLASK_STORE.key, ORPHAN_STORE.key}


@posix_only
def test_an_entry_the_migration_cannot_read_is_named_and_skipped(
    tmp_path: Path, old_format: str, caplog: pytest.LogCaptureFixture
) -> None:
    """One entry that cannot be read must not stop the rest, or every open with it."""

    home, old = _old_home(tmp_path, old_format)
    # A second name for an alias is one a private read refuses; a file where a store's
    # directory belongs has no record to read.
    os.link(home / source_record(CLICK.slug, "source.yml"), tmp_path / "second-name-of-a-record")
    os.link(home / source_record(FLASK_HTTPS.slug, "store-alias.yml"), tmp_path / "second-alias")
    stray = "c" * 64 if old_format == "f01" else "github-com--stray--" + "c" * 16
    (home / REPOSITORY_STORES / stray).write_text("")

    with caplog.at_level(logging.WARNING, logger="metabrowser.cache.store_rename"):
        outcome = migrate_layout(home, version="0.13.0")

    assert outcome.layout.format == "f03"
    assert FLASK_STORE.key in _names(home)
    assert stray in _names(home) and (home / REPOSITORY_STORES / stray).is_file()
    assert f"could not read: {CLICK.slug}" in caplog.text
    assert f"could not read: {FLASK_HTTPS.slug}" in caplog.text
    assert f"could not read: {stray}" in caplog.text
    assert str(home) not in caplog.text
    # click's source cannot say what its store holds: an f01 name said nothing, so that
    # store is unattached, and an f02 name said click, which it keeps.
    assert old[ORPHAN_STORE.key] not in _names(home)
    if old_format == "f01":
        assert any(name.startswith(f"{UNATTACHED_READABLE}-") for name in _names(home))
    else:
        assert ORPHAN_STORE.key in _names(home)


@posix_only
def test_two_opens_of_an_old_home_at_once_migrate_it_once(tmp_path: Path, old_format: str) -> None:
    home, old = _old_home(tmp_path, old_format)
    inode = (home / REPOSITORY_STORES / old[FLASK_STORE.key]).stat().st_ino
    barrier = threading.Barrier(2)

    def open_together(_index: int) -> str:
        barrier.wait()
        return open_cache(home, version="0.13.0").layout.format

    with ThreadPoolExecutor(2) as pool:
        formats = list(pool.map(open_together, range(2)))

    assert formats == ["f03", "f03"]
    assert _names(home) == {FLASK_STORE.key, ORPHAN_STORE.key}
    assert (home / store_directory(FLASK_STORE.key)).stat().st_ino == inode


def test_the_migration_derives_a_store_in_every_object_format() -> None:
    assert set(DERIVED_OBJECT_FORMATS) == OBJECT_FORMATS


def test_the_migration_lists_no_more_entries_than_the_cache_routes_do() -> None:
    assert MAX_MIGRATED_ENTRIES == projection.MAX_DIRECTORY_ENTRIES


@posix_only
def test_running_the_migration_again_changes_nothing(tmp_path: Path, old_format: str) -> None:
    home, _old = _old_home(tmp_path, old_format)
    open_cache(home, version="0.13.0")
    before = _names(home)

    rename_legacy_stores(home)

    assert _names(home) == before
    assert plan_store_renames(home) == []


@posix_only
def test_an_interrupted_migration_resumes_with_what_is_left(
    tmp_path: Path, old_format: str
) -> None:
    home, old = _old_home(tmp_path, old_format)
    # One store was renamed before the process died; the layout still names the old format.
    (home / REPOSITORY_STORES / old[FLASK_STORE.key]).rename(
        home / REPOSITORY_STORES / FLASK_STORE.key
    )

    outcome = migrate_layout(home, version="0.13.0")

    assert outcome.layout.format == "f03"
    assert _names(home) == {FLASK_STORE.key, ORPHAN_STORE.key}


@posix_only
def test_a_chain_interrupted_between_its_two_steps_resumes(tmp_path: Path) -> None:
    """An ``f01`` home is renamed once, so the step from ``f02`` that follows finds nothing."""

    home, _old = _old_home(tmp_path, "f01")

    def crash(_home: Path) -> None:
        raise RuntimeError("the process died between the two steps")

    with pytest.raises(RuntimeError, match="between the two steps"):
        migrate_layout(
            home, version="0.13.0", migrations={"f01": rename_legacy_stores, "f02": crash}
        )
    layout = read_layout(home)
    assert layout is not None and layout.format == "f02"
    assert _names(home) == {FLASK_STORE.key, ORPHAN_STORE.key}

    outcome = migrate_layout(home, version="0.13.0")

    assert outcome.previous_format == "f02" and outcome.migrated_through == ("f03",)
    assert _names(home) == {FLASK_STORE.key, ORPHAN_STORE.key}


@posix_only
def test_a_store_whose_record_does_not_name_its_directory_is_left_alone(
    tmp_path: Path, old_format: str, caplog: pytest.LogCaptureFixture
) -> None:
    home, old = _old_home(tmp_path, old_format)
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
def test_a_name_another_store_holds_is_skipped_and_never_shared(
    tmp_path: Path, old_format: str
) -> None:
    home = tmp_path / "home"
    build_populated_home(home)
    # The first key flask's store may have is held by a different store.
    first, second, *_ = store_key_candidates("https", FLASK_HTTPS.address, FLASK_STORE.id)
    assert first == FLASK_STORE.key
    old = REWRITES[old_format](home)
    occupy(home, first, store_id="sha256:" + "f" * 64)

    open_cache(home, version="0.13.0")

    assert (home / store_directory(first) / "store.yml").is_file()
    assert not (home / store_directory(first) / "repository.git").exists()
    assert (home / store_directory(second) / "repository.git").is_dir()
    assert old[FLASK_STORE.key] not in _names(home)


@posix_only
def test_a_store_holding_every_name_of_another_is_a_typed_collision(
    tmp_path: Path, old_format: str
) -> None:
    home = tmp_path / "home"
    build_populated_home(home)
    candidates = store_key_candidates("https", FLASK_HTTPS.address, FLASK_STORE.id)
    old = REWRITES[old_format](home)
    for key in candidates:
        occupy(home, key, store_id="sha256:" + "f" * 64)

    with pytest.raises(StoreKeyCollisionError):
        rename_legacy_stores(home)

    assert (home / REPOSITORY_STORES / old[FLASK_STORE.key]).is_dir()


@posix_only
def test_a_cache_with_no_stores_directory_is_migrated_and_nothing_is_created(
    tmp_path: Path, old_format: str
) -> None:
    home, _old = _old_home(tmp_path, old_format)
    shutil.rmtree(home / REPOSITORY_STORES)

    rename_legacy_stores(home)

    assert not (home / REPOSITORY_STORES).exists()


@posix_only
def test_a_home_already_at_f03_is_left_as_it_is(tmp_path: Path) -> None:
    home = tmp_path / "home"
    build_populated_home(home)
    before = _names(home)

    assert plan_store_renames(home) == []
    rename_legacy_stores(home)

    assert _names(home) == before


@posix_only
def test_a_released_home_is_a_cache_hit_after_the_migration_and_never_a_new_clone(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, old_format: str
) -> None:
    """The reason the stores are renamed: a store can be gigabytes, and re-cloning is waste.

    A real store is acquired, rewritten as the release that wrote the old format left it,
    and opened again. The open migrates the home, finds the store where it was, and neither
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
    fixture = FixtureSource(source.transport, source.normalized).store()
    assert fixture.id == first.store_id
    old = rewrite_as_f01(home) if old_format == "f01" else rewrite_as_f02(home, [fixture])
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
    assert read_layout(home) == CacheLayout(format="f03", created_by="0.12.0")
    assert old[first.store_key] not in _names(home)
    git(second.git_dir, "rev-parse", "HEAD")
    found = cached_source(source, home)
    assert found is not None and found.store_key == first.store_key


# The mechanism a step takes, apart from the stores: paths relative to a home.


def test_a_rename_takes_its_first_free_target_and_never_replaces(tmp_path: Path) -> None:
    (tmp_path / "from").mkdir()
    (tmp_path / "from/a").mkdir()
    (tmp_path / "from/a/payload").write_text("kept")
    (tmp_path / "to").mkdir()
    (tmp_path / "to/first").mkdir()
    (tmp_path / "to/first/other").write_text("not replaced")

    moved = apply_renames(tmp_path, [Rename("from/a", ("to/first", "to/second", "to/third"))])

    assert moved == 1
    assert (tmp_path / "to/first/other").read_text() == "not replaced"
    assert (tmp_path / "to/second/payload").read_text() == "kept"
    assert not (tmp_path / "from/a").exists()
    assert not (tmp_path / "to/third").exists()


def test_a_rename_can_move_an_entry_to_another_directory(tmp_path: Path) -> None:
    """What a later step that moves directories needs: a target outside the source's parent."""

    (tmp_path / "old-directory/entry").mkdir(parents=True)
    (tmp_path / "old-directory/entry/payload").write_text("kept")
    (tmp_path / "new-directory").mkdir()

    moved = apply_renames(tmp_path, [Rename("old-directory/entry", ("new-directory/entry",))])

    assert moved == 1
    assert (tmp_path / "new-directory/entry/payload").read_text() == "kept"


def test_an_entry_every_target_of_which_is_held_is_a_typed_failure(tmp_path: Path) -> None:
    for name in ("a", "b", "c"):
        (tmp_path / name).mkdir()

    with pytest.raises(NoFreeTargetError):
        apply_renames(tmp_path, [Rename("a", ("b", "c"))])

    assert (tmp_path / "a").is_dir()


def test_a_plan_of_nothing_moves_nothing(tmp_path: Path) -> None:
    assert apply_renames(tmp_path, []) == 0
