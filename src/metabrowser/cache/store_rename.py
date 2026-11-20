"""The ``f01`` and ``f02`` to ``f03`` migration: each store directory takes its current key.

An ``f01`` home names a store by all 64 hexadecimal digits of its identity, such as
``repository-stores/096a832ec2dfe765...``. An ``f02`` home names it for the repository it
holds and a prefix of that digest, joined by ``--``, such as
``repository-stores/github-com--jlevy--markform--096a832ec2dfe765``. ``f03`` names it by the
repository's words joined by single dashes and the first base-36 characters of the digest,
such as ``repository-stores/github-com-jlevy-markform-1bo2sp3ey2l``
(:func:`~metabrowser.cache.identity.store_key_candidates`).

The stores are renamed where they are. A store can hold a clone of gigabytes and nothing
in the cache deletes one, so leaving the old names would orphan every store: each
repository would be cloned again, and the old clones would stay with no command that
lists or removes them. A rename moves a store of any size in one step and fetches
nothing. A home that is ``f01`` is renamed once, straight to the ``f03`` names, and the
step from ``f02`` then finds nothing left to rename; the ``f02`` spelling is kept here
only to recognise it, not to write it again.

The repository a store holds is read from the source whose alias names it, or, for a
store no alias names, whose identity derives it (an acquisition interrupted between its
two renames leaves one): the source's recorded transport and address give the readable
part exactly as a lookup computes it, so the next acquisition of that source reuses the
store. A store no source names keeps the readable part its ``f02`` name had, and an
``f01`` one, which had none, takes :data:`UNATTACHED_READABLE`: it is listed as
unreferenced, which says what it is, and is kept, as such a store always was. A directory
whose ``store.yml`` does not record the identity its name spells is damaged already and is
left as it is, and an entry the migration cannot read is skipped and named in a warning,
so one cannot stop the rest.

The migration plans every rename first and then applies the plan with :func:`apply_renames`,
which takes paths relative to the home and moves each entry to the first target nothing
holds, so a later layout step that moves other directories, or moves a store between
directories, is another plan and not another mechanism.

Lock files named for a renamed store are left where they are: an older process may still
hold one, and an empty file costs nothing.

The caller holds the application-home lock, and each rename is atomic and refuses to
replace, so an interrupted migration is resumed by running it again: the stores it
renamed are not legacy names any more. Nothing is read or written outside the home.
This runs once for a home written by a release that spelled keys as ``f01`` or ``f02``
does, which is the released data it exists for.
"""

from __future__ import annotations

import logging
import re
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Final

from pydantic import BaseModel

from metabrowser.cache.atomic import RecordError, read_record, sync_directory
from metabrowser.cache.identity import (
    IDENTITY_PREFIX,
    GitTransport,
    ObjectFormat,
    StoreKeyCollisionError,
    identity_digest,
    is_slug,
    repository_store_id,
    store_key_candidates_for,
    store_readable_part,
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

# The readable part of the key of a store no source names and whose old name said nothing:
# nothing says which repository it holds, so the key says only that nothing is attached.
UNATTACHED_READABLE: Final = "unattached"
# The most entries of ``repository-stores`` or ``sources`` one migration lists, and refuses
# past: the bound the cache routes list under (``MAX_DIRECTORY_ENTRIES`` in
# ``cache/projection.py``, which a test holds this to), where a listing of 10,000 names
# measured 6-11 ms. A home past it is one those routes refused already.
MAX_MIGRATED_ENTRIES: Final = 10_000

_LEGACY_STORE_KEY_RE: Final = re.compile(r"^[0-9a-f]{64}$")
_F02_SEPARATOR: Final = "--"
# The hexadecimal digits an ``f02`` key ended in, shortest first: its 16-digit first choice,
# two longer ones, and the whole digest. Frozen here as released; ``f03`` does not write it.
F02_KEY_SUFFIX_HEX_DIGITS: Final = (16, 24, 32, 64)
_HEX_RE: Final = re.compile(r"^[0-9a-f]+$")
# The object formats a source's store can have (``OBJECT_FORMATS``, which a test holds this
# to), in the order they are tried.
DERIVED_OBJECT_FORMATS: Final[tuple[ObjectFormat, ...]] = ("sha1", "sha256")


@dataclass(frozen=True, slots=True)
class Rename:
    """One entry to move: *source* to the first of *targets* that nothing holds.

    Every path is relative to the application home, so a step may move an entry between
    directories as well as within one.
    """

    source: str
    targets: tuple[str, ...]


class NoFreeTargetError(FileExistsError):
    """Something already holds every target of a rename."""


def apply_renames(home: Path, renames: Sequence[Rename]) -> int:
    """Move each entry of *renames* where it stands, and return how many moved.

    Each is renamed to its first target that nothing holds, never over an existing entry
    (:func:`~metabrowser.home.rename_without_replacing`), and the directories it left and
    entered are flushed so the move survives a crash. Raises :class:`NoFreeTargetError` if
    something holds every target of one.
    """

    moved = 0
    for rename in renames:
        source = home / rename.source
        for target in rename.targets:
            try:
                rename_without_replacing(source, home / target)
            except FileExistsError:
                continue
            for directory in sorted({source.parent, (home / target).parent}):
                sync_directory(directory)
            moved += 1
            break
        else:
            raise NoFreeTargetError("every target of a rename is held by another entry")
    return moved


def is_legacy_store_key(name: str) -> bool:
    """Whether *name* is a store directory named as an ``f01`` home names it."""

    return _LEGACY_STORE_KEY_RE.fullmatch(name) is not None


def f02_key_parts(name: str) -> tuple[str, str] | None:
    """The readable part and hexadecimal suffix of a store directory named as ``f02`` does.

    ``None`` for any other name. The readable part is as ``f02`` spelled it, with its
    words joined by ``--``, and the suffix is one of :data:`F02_KEY_SUFFIX_HEX_DIGITS`
    hexadecimal digits. A name of ``f03`` has no ``--``, so the two never read alike.
    """

    if not is_slug(name):
        return None
    readable, separator, suffix = name.rpartition(_F02_SEPARATOR)
    if (
        not separator
        or not readable
        or len(suffix) not in F02_KEY_SUFFIX_HEX_DIGITS
        or _HEX_RE.fullmatch(suffix) is None
    ):
        return None
    return readable, suffix


def is_f02_store_key(name: str) -> bool:
    """Whether *name* is a store directory named as an ``f02`` home names it."""

    return f02_key_parts(name) is not None


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


def _spelled_identity_matches(name: str, recorded: str | None) -> bool:
    """Whether the identity recorded in a store names the directory it is in.

    An ``f01`` name is the whole digest, and an ``f02`` name ends in a prefix of it.
    """

    if recorded is None:
        return False
    if is_legacy_store_key(name):
        return recorded == f"{IDENTITY_PREFIX}{name}"
    parts = f02_key_parts(name)
    return parts is not None and identity_digest(recorded).startswith(parts[1])


def plan_store_renames(home: Path) -> list[Rename]:
    """The renames that give every store directory of *home* its current key.

    A store already named as ``f03`` names it is not in the plan, and a directory that is
    no store name of any format is left, as one whose record does not name it is.
    """

    try:
        names = list_private_directory(
            home, REPOSITORY_STORES, max_entries=MAX_MIGRATED_ENTRIES, shared="keep"
        )
    except FileNotFoundError:
        return []
    legacy = [name for name in names if is_legacy_store_key(name) or is_f02_store_key(name)]
    if not legacy:
        return []
    repositories = _repositories_by_store(home)
    renames: list[Rename] = []
    for name in legacy:
        recorded = _recorded_identity(home, name)
        if recorded is None or not _spelled_identity_matches(name, recorded):
            log.warning("Left a cache store whose record does not name its directory: %s", name)
            continue
        repository = repositories.get(recorded)
        parts = f02_key_parts(name)
        if repository is not None:
            readable = store_readable_part(*repository)
        elif parts is not None:
            # No source says which repository this is, but its name did: keep its words.
            readable = parts[0].replace(_F02_SEPARATOR, "-")
        else:
            readable = UNATTACHED_READABLE
        renames.append(
            Rename(
                f"{REPOSITORY_STORES}/{name}",
                tuple(
                    f"{REPOSITORY_STORES}/{key}"
                    for key in store_key_candidates_for(readable, recorded)
                ),
            )
        )
    return renames


def rename_legacy_stores(home: Path) -> None:
    """Rename every store directory of *home* named as ``f01`` or ``f02`` names one.

    Raises :class:`~metabrowser.cache.identity.StoreKeyCollisionError` if every key a
    store may have is held by another, which only a store's own digest can fill.
    """

    plan = plan_store_renames(home)
    try:
        renamed = apply_renames(home, plan)
    except NoFreeTargetError as error:
        raise StoreKeyCollisionError(
            "every store key suffix width is claimed by a different store"
        ) from error
    if renamed:
        log.info("Renamed %d cache store(s) to their current names", renamed)


__all__ = [
    "DERIVED_OBJECT_FORMATS",
    "F02_KEY_SUFFIX_HEX_DIGITS",
    "MAX_MIGRATED_ENTRIES",
    "UNATTACHED_READABLE",
    "NoFreeTargetError",
    "Rename",
    "apply_renames",
    "f02_key_parts",
    "is_f02_store_key",
    "is_legacy_store_key",
    "plan_store_renames",
    "rename_legacy_stores",
]
