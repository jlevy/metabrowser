"""The ``f01`` and ``f02`` to ``f03`` migration: older names become current ones.

Released ``f01`` homes name each store by all 64 digits of its identity, and ``f02`` homes
by its repository's words joined by ``--`` and 16 hexadecimal digits, in
``repository-stores``; both name a source by words joined by ``--`` and 12 digits. Every
home here is a current home rewritten as the release that wrote that format left it
(:func:`tests.cache_home_fixture.rewrite_as_f01` and ``rewrite_as_f02``), so the migration
is judged against the shapes the writers of those releases left.
"""

from __future__ import annotations

import asyncio
import fcntl
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
    is_slug,
    is_store_key,
    name_suffixes,
    slug_candidates,
    store_key_candidates,
    store_key_matches_identity,
)
from metabrowser.cache.layout import LayoutError, migrate_layout, open_cache, read_layout
from metabrowser.cache.lender import read_alternates
from metabrowser.cache.paths import (
    REPOSITORY_STORES,
    SOURCES,
    source_directory,
    source_record,
    store_directory,
    store_git_directory,
)
from metabrowser.cache.records import (
    REPOSITORY_SOURCE_CONTRACT_ID,
    REPOSITORY_STORE_CONTRACT_ID,
    CacheLayout,
    RepositorySource,
    RepositoryStore,
)
from metabrowser.cache.store_rename import (
    DERIVED_OBJECT_FORMATS,
    F02_KEY_SUFFIX_HEX_DIGITS,
    F02_SLUG_SUFFIX_HEX_DIGITS,
    LEGACY_REPOSITORY_STORES,
    LEGACY_SOURCE_CONTRACT_ID,
    MAX_MIGRATED_ENTRIES,
    UNATTACHED_READABLE,
    NoFreeTargetError,
    Rename,
    apply_renames,
    f02_key_parts,
    f02_slug_parts,
    is_f02_slug,
    is_f02_store_key,
    is_legacy_store_key,
    plan_store_renames,
    rename_legacy_names,
)
from metabrowser.git.process import OBJECT_FORMATS
from tests.cache_home_fixture import (
    CLICK,
    FLASK_HTTPS,
    FLASK_SSH,
    FLASK_STORE,
    ITSDANGEROUS,
    JINJA,
    MARKUPSAFE,
    ORPHAN_STORE,
    FixtureSource,
    build_overlay_home,
    build_populated_home,
    legacy_slug,
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
SOURCES_OF_THE_HOME = (FLASK_HTTPS, FLASK_SSH, CLICK)


@pytest.fixture(params=["f01", "f02"])
def old_format(request: pytest.FixtureRequest) -> str:
    return str(request.param)


def _names(home: Path) -> set[str]:
    """The entries of ``repos``, where every store belongs after the migration."""

    return {entry.name for entry in (home / REPOSITORY_STORES).iterdir()}


def _old_names(home: Path) -> set[str]:
    return {entry.name for entry in (home / LEGACY_REPOSITORY_STORES).iterdir()}


def _source_names(home: Path) -> set[str]:
    return {entry.name for entry in (home / SOURCES).iterdir()}


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
    assert F02_SLUG_SUFFIX_HEX_DIGITS == (12, 16, 24, 32, 64)
    assert f02_key_parts("github-com--pallets--flask--4c2d8559cb0179ba") == (
        "github-com--pallets--flask",
        "4c2d8559cb0179ba",
    )
    assert f02_key_parts("unattached--" + "0" * 64) == ("unattached", "0" * 64)
    assert f02_slug_parts("github-com--pallets--flask--e7b7fe0ffe8a") == (
        "github-com--pallets--flask",
        "e7b7fe0ffe8a",
    )
    # A store key never had 12 digits, and a slug never had 12 fewer than its widths.
    assert f02_key_parts("github-com--pallets--flask--e7b7fe0ffe8a") is None
    for name in (
        FLASK_STORE.key,
        FLASK_HTTPS.slug,
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
        assert not is_f02_slug(name), name


def test_no_name_is_a_current_one_and_an_older_one_at_once() -> None:
    for name in (FLASK_STORE.key, ORPHAN_STORE.key, FLASK_HTTPS.slug, CLICK.slug):
        assert is_store_key(name) and is_slug(name)
        assert not is_legacy_store_key(name)
        assert not is_f02_store_key(name) and not is_f02_slug(name)
    for name in (legacy_slug(FLASK_HTTPS), legacy_slug(CLICK)):
        assert is_f02_slug(name)
        assert not is_slug(name) and not is_store_key(name)
    assert not is_store_key("github-com--pallets--flask--4c2d8559cb0179ba")
    assert not is_store_key("a" * 64)


@posix_only
def test_an_old_home_has_its_stores_renamed_and_moved_where_they_stand(
    tmp_path: Path, old_format: str
) -> None:
    home, old = _old_home(tmp_path, old_format)
    inodes = {name: (home / LEGACY_REPOSITORY_STORES / name).stat().st_ino for name in old.values()}
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
    # The directory stores used to be in is gone with nothing in it.
    assert not (home / LEGACY_REPOSITORY_STORES).exists()
    # Its lock files are left: an older process may hold one, and an empty file costs nothing.
    assert (home / "locks/stores" / f"{old[FLASK_STORE.key]}.lock").exists()


@posix_only
def test_open_cache_moves_into_the_repos_directory_the_skeleton_made(
    tmp_path: Path, old_format: str
) -> None:
    """``ensure_home`` runs first, so ``repos`` exists and is empty, and the move is per store."""

    home, _old = _old_home(tmp_path, old_format)
    assert not (home / REPOSITORY_STORES).exists()

    open_cache(home, version="0.13.0")

    assert _names(home) == {FLASK_STORE.key, ORPHAN_STORE.key}
    assert not (home / LEGACY_REPOSITORY_STORES).exists()


@posix_only
def test_an_old_home_has_its_sources_renamed_and_their_records_rewritten(
    tmp_path: Path, old_format: str
) -> None:
    home, _old = _old_home(tmp_path, old_format)
    inodes = {
        source: (home / SOURCES / legacy_slug(source)).stat().st_ino
        for source in SOURCES_OF_THE_HOME
    }
    pulls = home / SOURCES / legacy_slug(FLASK_HTTPS) / "pulls"
    pulls.mkdir()
    (pulls / "1.json").write_text("{}")
    assert all(is_f02_slug(name) for name in _source_names(home))

    open_cache(home, version="0.13.0")

    assert _source_names(home) == {source.slug for source in SOURCES_OF_THE_HOME}
    for source in SOURCES_OF_THE_HOME:
        directory = home / source_directory(source.slug)
        # The same directory, so what a provider kept beside the source moved with it.
        assert directory.stat().st_ino == inodes[source]
        record = read_record(
            home, source_record(source.slug, "source.yml"), REPOSITORY_SOURCE_CONTRACT_ID
        )
        assert isinstance(record, RepositorySource)
        assert record.slug == source.slug and record.id == source.id
        assert record.created_at == "2026-09-17T12:00:00Z"
    assert (home / source_directory(FLASK_HTTPS.slug) / "pulls/1.json").read_text() == "{}"
    # The alias, which names the store by identity, is untouched and still resolves.
    assert (home / source_record(FLASK_HTTPS.slug, "store-alias.yml")).is_file()


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
    shutil.rmtree(home / SOURCES / legacy_slug(CLICK))

    open_cache(home, version="0.13.0")

    (orphan,) = _names(home) - {FLASK_STORE.key}
    assert orphan == f"{UNATTACHED_READABLE}-{name_suffixes(ORPHAN_STORE.id)[0]}"
    assert is_store_key(orphan) and store_key_matches_identity(orphan, ORPHAN_STORE.id)


@posix_only
def test_an_f02_store_no_source_names_keeps_the_words_its_name_had(tmp_path: Path) -> None:
    home, old = _old_home(tmp_path, "f02")
    shutil.rmtree(home / SOURCES / legacy_slug(CLICK))
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
    # A second name for a record is one a private read refuses; a file where a store's
    # directory belongs has no record to read.
    os.link(
        home / SOURCES / legacy_slug(CLICK) / "source.yml", tmp_path / "second-name-of-a-record"
    )
    os.link(
        home / SOURCES / legacy_slug(FLASK_HTTPS) / "store-alias.yml", tmp_path / "second-alias"
    )
    stray = "c" * 64 if old_format == "f01" else "github-com--stray--" + "c" * 16
    (home / LEGACY_REPOSITORY_STORES / stray).write_text("")

    with caplog.at_level(logging.WARNING, logger="metabrowser.cache.store_rename"):
        outcome = migrate_layout(home, version="0.13.0")

    assert outcome.layout.format == "f03"
    assert FLASK_STORE.key in _names(home)
    # The stray file is kept, under the name it had, with the entries nothing recognises.
    assert stray in _names(home) and (home / REPOSITORY_STORES / stray).is_file()
    assert f"could not read: {legacy_slug(CLICK)}" in caplog.text
    # flask's source was renamed first, so its alias is read, and refused, under the new name.
    assert f"could not read: {FLASK_HTTPS.slug}" in caplog.text
    assert f"could not read: {stray}" in caplog.text
    assert str(home) not in caplog.text
    # click's source cannot say what its store holds, and stays under its old name. An f01
    # store name said nothing, so that store is unattached, and an f02 name said click.
    assert legacy_slug(CLICK) in _source_names(home)
    assert old[ORPHAN_STORE.key] not in _names(home)
    if old_format == "f01":
        assert any(name.startswith(f"{UNATTACHED_READABLE}-") for name in _names(home))
    else:
        assert ORPHAN_STORE.key in _names(home)
    assert not (home / LEGACY_REPOSITORY_STORES).exists()


@posix_only
def test_two_opens_of_an_old_home_at_once_migrate_it_once(tmp_path: Path, old_format: str) -> None:
    home, old = _old_home(tmp_path, old_format)
    inode = (home / LEGACY_REPOSITORY_STORES / old[FLASK_STORE.key]).stat().st_ino
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
    before = (_names(home), _source_names(home))

    rename_legacy_names(home)

    assert (_names(home), _source_names(home)) == before
    assert plan_store_renames(home) == []


@posix_only
def test_an_interrupted_migration_resumes_with_what_is_left(
    tmp_path: Path, old_format: str
) -> None:
    home, old = _old_home(tmp_path, old_format)
    # One store was moved, and one source had its record rewritten, before the process died;
    # the layout still names the old format.
    (home / REPOSITORY_STORES).mkdir()
    (home / LEGACY_REPOSITORY_STORES / old[FLASK_STORE.key]).rename(
        home / REPOSITORY_STORES / FLASK_STORE.key
    )
    record = home / SOURCES / legacy_slug(FLASK_HTTPS) / "source.yml"
    record.write_text(
        record.read_text().replace(f"slug: {legacy_slug(FLASK_HTTPS)}", f"slug: {FLASK_HTTPS.slug}")
    )

    outcome = migrate_layout(home, version="0.13.0")

    assert outcome.layout.format == "f03"
    assert _names(home) == {FLASK_STORE.key, ORPHAN_STORE.key}
    assert _source_names(home) == {source.slug for source in SOURCES_OF_THE_HOME}
    assert not (home / LEGACY_REPOSITORY_STORES).exists()


@posix_only
def test_a_chain_interrupted_between_its_two_steps_resumes(tmp_path: Path) -> None:
    """An ``f01`` home is renamed once, so the step from ``f02`` that follows finds nothing."""

    home, _old = _old_home(tmp_path, "f01")

    def crash(_home: Path) -> None:
        raise RuntimeError("the process died between the two steps")

    with pytest.raises(RuntimeError, match="between the two steps"):
        migrate_layout(
            home, version="0.13.0", migrations={"f01": rename_legacy_names, "f02": crash}
        )
    layout = read_layout(home)
    assert layout is not None and layout.format == "f02"
    assert _names(home) == {FLASK_STORE.key, ORPHAN_STORE.key}

    outcome = migrate_layout(home, version="0.13.0")

    assert outcome.previous_format == "f02" and outcome.migrated_through == ("f03",)
    assert _names(home) == {FLASK_STORE.key, ORPHAN_STORE.key}
    assert _source_names(home) == {source.slug for source in SOURCES_OF_THE_HOME}


@posix_only
def test_a_store_whose_record_does_not_name_its_directory_is_left_alone(
    tmp_path: Path, old_format: str, caplog: pytest.LogCaptureFixture
) -> None:
    home, old = _old_home(tmp_path, old_format)
    damaged = old[ORPHAN_STORE.key]
    record = read_record(
        home, f"{LEGACY_REPOSITORY_STORES}/{damaged}/store.yml", REPOSITORY_STORE_CONTRACT_ID
    )
    assert isinstance(record, RepositoryStore)
    write_record_atomic(
        home,
        f"{LEGACY_REPOSITORY_STORES}/{damaged}/store.yml",
        record.model_copy(update={"id": "sha256:" + "e" * 64}),
        REPOSITORY_STORE_CONTRACT_ID,
    )

    with caplog.at_level(logging.WARNING, logger="metabrowser.cache.store_rename"):
        open_cache(home, version="0.13.0")

    # It is moved with the others, under the name it has, and nothing recognises it.
    assert damaged in _names(home) and not is_store_key(damaged)
    assert FLASK_STORE.key in _names(home)
    assert "does not name its directory" in caplog.text
    assert not (home / LEGACY_REPOSITORY_STORES).exists()


@posix_only
def test_a_source_whose_record_does_not_name_its_directory_is_left_alone(
    tmp_path: Path, old_format: str, caplog: pytest.LogCaptureFixture
) -> None:
    home, _old = _old_home(tmp_path, old_format)
    path = home / SOURCES / legacy_slug(CLICK) / "source.yml"
    path.write_text(path.read_text().replace("pallets/click", "pallets/other"))

    with caplog.at_level(logging.WARNING, logger="metabrowser.cache.store_rename"):
        open_cache(home, version="0.13.0")

    assert legacy_slug(CLICK) in _source_names(home)
    assert CLICK.slug not in _source_names(home)
    assert FLASK_HTTPS.slug in _source_names(home)
    assert "does not name its directory" in caplog.text


@posix_only
def test_a_source_directory_with_no_record_is_named_and_left(
    tmp_path: Path, old_format: str, caplog: pytest.LogCaptureFixture
) -> None:
    home, _old = _old_home(tmp_path, old_format)
    (home / SOURCES / legacy_slug(CLICK) / "source.yml").unlink()

    with caplog.at_level(logging.WARNING, logger="metabrowser.cache.store_rename"):
        open_cache(home, version="0.13.0")

    assert legacy_slug(CLICK) in _source_names(home)
    assert f"with no record: {legacy_slug(CLICK)}" in caplog.text
    assert FLASK_HTTPS.slug in _source_names(home)


@posix_only
def test_a_source_record_of_another_contract_is_not_read_as_an_old_one(
    tmp_path: Path, old_format: str, caplog: pytest.LogCaptureFixture
) -> None:
    home, _old = _old_home(tmp_path, old_format)
    path = home / SOURCES / legacy_slug(CLICK) / "source.yml"
    path.write_text(
        path.read_text().replace(LEGACY_SOURCE_CONTRACT_ID, "metabrowser.cache:RepositorySource/v9")
    )

    with caplog.at_level(logging.WARNING, logger="metabrowser.cache.store_rename"):
        open_cache(home, version="0.13.0")

    assert legacy_slug(CLICK) in _source_names(home)
    assert f"could not read: {legacy_slug(CLICK)}" in caplog.text


@posix_only
def test_the_records_the_migration_writes_name_the_current_contract(
    tmp_path: Path, old_format: str
) -> None:
    home, _old = _old_home(tmp_path, old_format)
    old = (home / SOURCES / legacy_slug(FLASK_HTTPS) / "source.yml").read_text()
    assert f"contract: {LEGACY_SOURCE_CONTRACT_ID}\n" in old

    open_cache(home, version="0.13.0")

    new = (home / source_record(FLASK_HTTPS.slug, "source.yml")).read_text()
    assert f"contract: {REPOSITORY_SOURCE_CONTRACT_ID}\n" in new
    assert LEGACY_SOURCE_CONTRACT_ID not in new
    assert REPOSITORY_SOURCE_CONTRACT_ID.endswith("/v2")


@posix_only
def test_a_migration_waits_while_an_earlier_release_fetches_into_a_store(
    tmp_path: Path, old_format: str
) -> None:
    """An older process holds absolute paths into the directory that is about to move."""

    home, old = _old_home(tmp_path, old_format)
    name = old[FLASK_STORE.key]
    fetching = os.open(home / "locks/stores" / f"{name}.fetch.lock", os.O_RDWR)
    fcntl.flock(fetching, fcntl.LOCK_EX | fcntl.LOCK_NB)
    try:
        with pytest.raises(LayoutError, match="earlier release of Metabrowser is fetching"):
            migrate_layout(home, version="0.13.0")
        # Nothing moved, and the layout still names the old format, so the next open retries.
        layout = read_layout(home)
        assert layout is not None and layout.format == old_format
        assert _old_names(home) == set(old.values())
        assert _source_names(home) == {legacy_slug(source) for source in SOURCES_OF_THE_HOME}
    finally:
        os.close(fetching)

    outcome = migrate_layout(home, version="0.13.0")

    assert outcome.layout.format == "f03"
    assert _names(home) == {FLASK_STORE.key, ORPHAN_STORE.key}


@posix_only
def test_an_old_lock_file_nobody_holds_does_not_stop_the_migration(
    tmp_path: Path, old_format: str
) -> None:
    home, _old = _old_home(tmp_path, old_format)

    outcome = migrate_layout(home, version="0.13.0")

    assert outcome.layout.format == "f03"


@posix_only
def test_a_store_that_never_fetched_has_no_lock_file_made_for_it(
    tmp_path: Path, old_format: str
) -> None:
    home, old = _old_home(tmp_path, old_format)
    name = old[ORPHAN_STORE.key]
    (home / "locks/stores" / f"{name}.fetch.lock").unlink()

    migrate_layout(home, version="0.13.0")

    assert not (home / "locks/stores" / f"{name}.fetch.lock").exists()


@posix_only
def test_an_overlay_store_keeps_its_borrowed_objects_through_the_move(
    tmp_path: Path, old_format: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A store that borrows from a checkout still borrows from it, in the same directory."""

    home = tmp_path / "home"
    build_overlay_home(home, tmp_path / "checkouts")
    stores = [JINJA.store(), MARKUPSAFE.store(), ITSDANGEROUS.store()]
    before = {
        store: (
            (home / store_git_directory(store.key)).stat().st_ino,
            read_alternates(home / store_git_directory(store.key)),
            (home / store_directory(store.key) / "store.yml").read_bytes(),
        )
        for store in stores
    }
    assert all(alternates for _inode, alternates, _record in before.values())
    if old_format == "f01":
        rewrite_as_f01(home)
    else:
        rewrite_as_f02(home, stores)

    open_cache(home, version="0.13.0")

    for store in stores:
        inode, alternates, record = before[store]
        git_dir = home / store_git_directory(store.key)
        assert git_dir.stat().st_ino == inode
        assert read_alternates(git_dir) == alternates
        assert (home / store_directory(store.key) / "store.yml").read_bytes() == record
    # The borrowed objects are where the record says, outside the cache, and are not touched.
    borrowed = read_alternates(home / store_git_directory(JINJA.store().key))
    assert borrowed is not None and Path(borrowed).is_dir()
    monkeypatch.setenv("METABROWSER_CACHE_DIR", str(home))
    status, body = projection.stores_response(limit=10, after=None)
    assert status == 200 and "stores" in body
    rows = {row["key"]: row for row in body["stores"]}
    assert rows[JINJA.store().key]["mode"] == "overlay"
    assert rows[JINJA.store().key]["lender"] == "present"
    assert rows[MARKUPSAFE.store().key]["lender"] == "lender_missing"
    assert {row["publication"] for row in rows.values()} <= {"published", "damaged"}
    assert not (home / LEGACY_REPOSITORY_STORES).exists()


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
    (home / REPOSITORY_STORES).mkdir()
    occupy(home, first, store_id="sha256:" + "f" * 64)

    open_cache(home, version="0.13.0")

    assert (home / store_directory(first) / "store.yml").is_file()
    assert not (home / store_directory(first) / "repository.git").exists()
    assert (home / store_directory(second) / "repository.git").is_dir()
    assert old[FLASK_STORE.key] not in _names(home)


@posix_only
def test_a_name_another_source_holds_is_skipped_and_never_shared(
    tmp_path: Path, old_format: str
) -> None:
    home, _old = _old_home(tmp_path, old_format)
    first, second, *_ = slug_candidates("https", FLASK_HTTPS.address, FLASK_HTTPS.id)
    assert first == FLASK_HTTPS.slug
    (home / SOURCES / first).mkdir()

    open_cache(home, version="0.13.0")

    # flask's source takes the next slug, its record says so, and the other entry is not touched.
    assert (home / SOURCES / first).is_dir() and not any((home / SOURCES / first).iterdir())
    record = read_record(home, source_record(second, "source.yml"), REPOSITORY_SOURCE_CONTRACT_ID)
    assert isinstance(record, RepositorySource) and record.slug == second


@posix_only
def test_a_source_every_name_of_which_another_holds_is_left_and_the_rest_migrate(
    tmp_path: Path, old_format: str, caplog: pytest.LogCaptureFixture
) -> None:
    home, _old = _old_home(tmp_path, old_format)
    for slug in slug_candidates("https", FLASK_HTTPS.address, FLASK_HTTPS.id):
        (home / SOURCES / slug).mkdir()

    with caplog.at_level(logging.WARNING, logger="metabrowser.cache.store_rename"):
        outcome = migrate_layout(home, version="0.13.0")

    assert outcome.layout.format == "f03"
    assert (home / SOURCES / legacy_slug(FLASK_HTTPS)).is_dir()
    assert f"every slug of which another source holds: {legacy_slug(FLASK_HTTPS)}" in caplog.text
    assert {FLASK_SSH.slug, CLICK.slug} <= _source_names(home)


@posix_only
def test_a_store_every_key_of_which_another_holds_is_left_and_the_rest_migrate(
    tmp_path: Path, old_format: str, caplog: pytest.LogCaptureFixture
) -> None:
    home = tmp_path / "home"
    build_populated_home(home)
    candidates = store_key_candidates("https", FLASK_HTTPS.address, FLASK_STORE.id)
    old = REWRITES[old_format](home)
    (home / REPOSITORY_STORES).mkdir()
    for key in candidates:
        occupy(home, key, store_id="sha256:" + "f" * 64)

    with caplog.at_level(logging.WARNING, logger="metabrowser.cache.store_rename"):
        rename_legacy_names(home)

    # flask's store stays where it was, so that it is not lost, and the other moves.
    assert (home / LEGACY_REPOSITORY_STORES / old[FLASK_STORE.key]).is_dir()
    assert ORPHAN_STORE.key in _names(home)
    assert f"every key of which another store holds: {old[FLASK_STORE.key]}" in caplog.text


@posix_only
def test_an_entry_the_filesystem_refuses_to_move_is_left_and_the_rest_migrate(
    tmp_path: Path,
    old_format: str,
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    from metabrowser.cache import store_rename
    from metabrowser.home import rename_without_replacing as real

    home, old = _old_home(tmp_path, old_format)
    refused = old[FLASK_STORE.key]

    def rename(source: Path, target: Path) -> bool:
        if source.name == refused:
            raise PermissionError(13, "Permission denied")
        return real(source, target)

    monkeypatch.setattr(store_rename, "rename_without_replacing", rename)

    with caplog.at_level(logging.WARNING, logger="metabrowser.cache.store_rename"):
        outcome = migrate_layout(home, version="0.13.0")

    assert outcome.layout.format == "f03"
    assert (home / LEGACY_REPOSITORY_STORES / refused).is_dir()
    assert ORPHAN_STORE.key in _names(home)
    assert f"could not move: {refused}" in caplog.text
    assert str(home) not in caplog.text


@posix_only
def test_an_entry_whose_name_another_entry_holds_stays_and_keeps_the_old_directory(
    tmp_path: Path, old_format: str, caplog: pytest.LogCaptureFixture
) -> None:
    home, _old = _old_home(tmp_path, old_format)
    stray = "notes.txt"
    (home / LEGACY_REPOSITORY_STORES / stray).write_text("old")
    (home / REPOSITORY_STORES).mkdir()
    (home / REPOSITORY_STORES / stray).write_text("new")

    with caplog.at_level(logging.WARNING, logger="metabrowser.cache.store_rename"):
        rename_legacy_names(home)

    assert (home / REPOSITORY_STORES / stray).read_text() == "new"
    assert (home / LEGACY_REPOSITORY_STORES / stray).read_text() == "old"
    assert _old_names(home) == {stray}
    assert "whose name another entry holds" in caplog.text
    assert _names(home) >= {FLASK_STORE.key, ORPHAN_STORE.key}


@posix_only
def test_a_cache_with_no_stores_directory_is_migrated_and_nothing_is_created(
    tmp_path: Path, old_format: str
) -> None:
    home, _old = _old_home(tmp_path, old_format)
    shutil.rmtree(home / LEGACY_REPOSITORY_STORES)

    rename_legacy_names(home)

    assert not (home / LEGACY_REPOSITORY_STORES).exists()
    assert not (home / REPOSITORY_STORES).exists()


@posix_only
def test_a_migration_run_alone_makes_the_repos_directory_it_moves_into(
    tmp_path: Path, old_format: str
) -> None:
    home, _old = _old_home(tmp_path, old_format)
    assert not (home / REPOSITORY_STORES).exists()

    rename_legacy_names(home)

    assert _names(home) == {FLASK_STORE.key, ORPHAN_STORE.key}


@posix_only
def test_a_home_already_at_f03_is_left_as_it_is(tmp_path: Path) -> None:
    home = tmp_path / "home"
    build_populated_home(home)
    before = (_names(home), _source_names(home))

    assert plan_store_renames(home) == []
    rename_legacy_names(home)

    assert (_names(home), _source_names(home)) == before


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

    async def no_provider_asked(_source: object, **_kwargs: object) -> None:
        raise AssertionError("a store that is cached must not be looked up at the provider")

    async def no_fetch(*_args: object, **_kwargs: object) -> object:
        raise AssertionError("a store that is cached must not be fetched")

    monkeypatch.setattr(acquire_module, "check_first_clone", no_provider_asked)
    monkeypatch.setattr(acquire_module, "acquire_into_staging", no_fetch)
    second = asyncio.run(acquire_source(source, home=home))

    assert second.store_key == first.store_key
    assert second.slug == first.slug
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

    taken = apply_renames(tmp_path, [Rename("from/a", ("to/first", "to/second", "to/third"))])

    assert taken == ["to/second"]
    assert (tmp_path / "to/first/other").read_text() == "not replaced"
    assert (tmp_path / "to/second/payload").read_text() == "kept"
    assert not (tmp_path / "from/a").exists()
    assert not (tmp_path / "to/third").exists()


def test_a_rename_can_move_an_entry_to_another_directory(tmp_path: Path) -> None:
    """What a later step that moves directories needs: a target outside the source's parent."""

    (tmp_path / "old-directory/entry").mkdir(parents=True)
    (tmp_path / "old-directory/entry/payload").write_text("kept")
    (tmp_path / "new-directory").mkdir()

    taken = apply_renames(tmp_path, [Rename("old-directory/entry", ("new-directory/entry",))])

    assert taken == ["new-directory/entry"]
    assert (tmp_path / "new-directory/entry/payload").read_text() == "kept"


def test_an_entry_every_target_of_which_is_held_is_a_typed_failure(tmp_path: Path) -> None:
    for name in ("a", "b", "c"):
        (tmp_path / name).mkdir()

    with pytest.raises(NoFreeTargetError):
        apply_renames(tmp_path, [Rename("a", ("b", "c"))])

    assert (tmp_path / "a").is_dir()


def test_a_plan_of_nothing_moves_nothing(tmp_path: Path) -> None:
    assert apply_renames(tmp_path, []) == []
