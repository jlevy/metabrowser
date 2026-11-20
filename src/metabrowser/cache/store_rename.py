"""The ``f01`` to ``f02`` migration: each store directory takes a readable key.

An ``f01`` home names a store by all 64 hexadecimal digits of its identity, such as
``repository-stores/589d51b16fd8f1a2...``. ``f02`` names it for the repository it holds and
a prefix of that digest, such as ``repository-stores/github-com--jlevy--markform--589d51b16fd8f1a2``
(:func:`~metabrowser.cache.identity.store_key_candidates`).

The stores are renamed where they are. A store can hold a clone of gigabytes and nothing
in the cache deletes one, so leaving the old names would orphan every store: each
repository would be cloned again, and the old clones would stay with no command that
lists or removes them. A rename moves a store of any size in one step and fetches
nothing.

The repository a store holds is read from the source whose alias names it, or, for a
store no alias names, whose identity derives it (an acquisition interrupted between its
two renames leaves one): the source's recorded transport and address give the readable
part exactly as a lookup computes it, so the next acquisition of that source reuses the
store. A store no source names takes :data:`UNATTACHED_READABLE`: it is listed as
unreferenced, which says what it is, and is kept, as such a store always was. A directory
whose ``store.yml`` does not record the identity its name spells is damaged already and is
left as it is, and an entry the migration cannot read is skipped and named in a warning,
so one cannot stop the rest.

Lock files named for a renamed store are left where they are: an older process may still
hold one, and an empty file costs nothing.

The caller holds the application-home lock, and each rename is atomic and refuses to
replace, so an interrupted migration is resumed by running it again: the stores it
renamed are not legacy names any more. Nothing is read or written outside the home.
This runs once for a home written by a release that spelled keys as ``f01`` does, which
is the released data it exists for.
"""

from __future__ import annotations

import logging
import re
from pathlib import Path
from typing import Final

from pydantic import BaseModel

from metabrowser.cache.atomic import RecordError, read_record, sync_directory
from metabrowser.cache.identity import (
    IDENTITY_PREFIX,
    GitTransport,
    ObjectFormat,
    StoreKeyCollisionError,
    is_slug,
    repository_store_id,
    slug_readable_part,
    store_key_candidates_for,
)
from metabrowser.cache.listing import list_private_directory
from metabrowser.cache.paths import REPOSITORY_STORES, SOURCES, source_record
from metabrowser.cache.records import (
    REPOSITORY_SOURCE_CONTRACT_ID,
    REPOSITORY_STORE_ALIAS_CONTRACT_ID,
    REPOSITORY_STORE_CONTRACT_ID,
    RepositorySource,
    RepositoryStore,
    RepositoryStoreAlias,
)
from metabrowser.home import PrivateStorageError, rename_without_replacing

log = logging.getLogger(__name__)

# The readable part of the key of a store no source names: nothing says which repository
# it holds, so the key says only that nothing is attached to it.
UNATTACHED_READABLE: Final = "unattached"
# The most entries of ``repository-stores`` or ``sources`` one migration lists, and refuses
# past: the bound the cache routes list under (``MAX_DIRECTORY_ENTRIES`` in
# ``cache/projection.py``, which a test holds this to), where a listing of 10,000 names
# measured 6-11 ms. A home past it is one those routes refused already.
MAX_MIGRATED_ENTRIES: Final = 10_000

_LEGACY_STORE_KEY_RE: Final = re.compile(r"^[0-9a-f]{64}$")
# The object formats a source's store can have (``OBJECT_FORMATS``, which a test holds this
# to), in the order they are tried.
DERIVED_OBJECT_FORMATS: Final[tuple[ObjectFormat, ...]] = ("sha1", "sha256")


def is_legacy_store_key(name: str) -> bool:
    """Whether *name* is a store directory named as an ``f01`` home names it."""

    return _LEGACY_STORE_KEY_RE.fullmatch(name) is not None


def _read_entry(home: Path, relative_path: str, contract_id: str, entry: str) -> BaseModel | None:
    """One record of the entry named *entry*, or ``None`` when it has none or cannot be read.

    An entry the migration cannot read is skipped and named, never a reason to refuse every
    open of the cache: a hard-linked alias, a link, or a file where a directory belongs
    would otherwise stop the migration of every other store. The name is a slug or a store
    directory's own, and the message names no path.
    """

    try:
        return read_record(home, relative_path, contract_id, shared="keep")
    except FileNotFoundError:
        return None
    except (OSError, PrivateStorageError, RecordError, ValueError):
        log.warning("Skipped a cache entry the migration could not read: %s", entry)
        return None


def _repositories_by_store(home: Path) -> dict[str, tuple[GitTransport, str]]:
    """The transport and address of the repository each store belongs to.

    A store an alias names belongs to the source that alias is in. A store no alias names
    still belongs to the source whose identity derives it, in either object format, which
    is how an acquisition interrupted between its two renames, or a source published with
    no store, keeps its repository's name. An alias wins over a derivation, and an entry
    that cannot be read names nothing.
    """

    names = list_private_directory(home, SOURCES, max_entries=MAX_MIGRATED_ENTRIES, shared="keep")
    aliased: dict[str, tuple[GitTransport, str]] = {}
    derived: dict[str, tuple[GitTransport, str]] = {}
    for slug in names:
        if not is_slug(slug):
            continue
        source = _read_entry(
            home, source_record(slug, "source.yml"), REPOSITORY_SOURCE_CONTRACT_ID, slug
        )
        if not isinstance(source, RepositorySource):
            continue
        repository = (source.transport, source.clone_url)
        for object_format in DERIVED_OBJECT_FORMATS:
            derived.setdefault(repository_store_id(source.id, object_format), repository)
        alias = _read_entry(
            home, source_record(slug, "store-alias.yml"), REPOSITORY_STORE_ALIAS_CONTRACT_ID, slug
        )
        if isinstance(alias, RepositoryStoreAlias):
            aliased.setdefault(alias.store_id, repository)
    return {**derived, **aliased}


def _recorded_identity(home: Path, name: str) -> str | None:
    record = _read_entry(
        home, f"{REPOSITORY_STORES}/{name}/store.yml", REPOSITORY_STORE_CONTRACT_ID, name
    )
    return record.id if isinstance(record, RepositoryStore) else None


def rename_legacy_stores(home: Path) -> None:
    """Rename every store directory of *home* named by a whole digest to its readable key.

    Raises :class:`~metabrowser.cache.identity.StoreKeyCollisionError` if every key a
    store may have is held by another, which only a store's own digest can fill.
    """

    try:
        names = list_private_directory(
            home, REPOSITORY_STORES, max_entries=MAX_MIGRATED_ENTRIES, shared="keep"
        )
    except FileNotFoundError:
        return
    legacy = [name for name in names if is_legacy_store_key(name)]
    if not legacy:
        return
    repositories = _repositories_by_store(home)
    stores = home / REPOSITORY_STORES
    renamed = 0
    for name in legacy:
        store_id = f"{IDENTITY_PREFIX}{name}"
        if _recorded_identity(home, name) != store_id:
            log.warning("Left a cache store whose record does not name its directory: %s", name)
            continue
        repository = repositories.get(store_id)
        readable = UNATTACHED_READABLE if repository is None else slug_readable_part(*repository)
        for key in store_key_candidates_for(readable, store_id):
            try:
                rename_without_replacing(stores / name, stores / key)
            except FileExistsError:
                continue
            sync_directory(stores)
            renamed += 1
            break
        else:
            raise StoreKeyCollisionError(
                "every store key suffix width is claimed by a different store"
            )
    if renamed:
        log.info("Renamed %d cache store(s) to readable names", renamed)


__all__ = [
    "DERIVED_OBJECT_FORMATS",
    "MAX_MIGRATED_ENTRIES",
    "UNATTACHED_READABLE",
    "is_legacy_store_key",
    "rename_legacy_stores",
]
