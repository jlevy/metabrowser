"""The ``f01`` to ``f03`` migration: sources and stores take their current names.

``f03`` names a source directory by a slug and a store directory by a key, and both are
the repository's words joined by single dashes and the first base-36 characters of an
identity's digest, such as ``sources/github-com-jlevy-markform-jqlzm24hgct`` and
``repos/github-com-jlevy-markform-1bo2sp3ey2l``
(:func:`~metabrowser.cache.identity.slug_candidates` and
:func:`~metabrowser.cache.identity.store_key_candidates`).

In ``f01``, a store was named by all 64 hexadecimal digits of its identity, in
``repository-stores/``, such as ``repository-stores/096a832ec2dfe765...``. A source used
words joined by ``--`` and 12 digits of its identity, such as
``sources/github-com--jlevy--markform--8c5e18ed6f7f``.

The entries are renamed where they are, and the stores are moved into ``repos/``. A store
can hold a clone of gigabytes and nothing in the cache deletes one, so leaving the old
names would orphan every store: each repository would be cloned again, and the old clones
would stay with no command that lists or removes them. A rename moves a store of any size
in one step and fetches nothing.

Sources go first, so that the stores can name the repository they hold. A source's
``source.yml`` records its slug and is validated against its identity, and ``f03`` spells
that slug in a way a ``RepositorySource/v1`` record cannot hold, so it is a new contract,
``/v2``. The migration reads the old record as the YAML mapping it is
(:data:`LEGACY_SOURCE_CONTRACT_ID` is the only place the old contract is named, and nothing
else reads it), writes the ``/v2`` record with the new slug in the old directory, and then
renames the directory: a migration interrupted between the two leaves an entry under its
old name that the next run finishes, and never a directory whose record disagrees with its
name.

The repository a store holds is read from the source whose alias names it, or, for a
store no alias names, whose identity derives it (an acquisition interrupted between its
two renames leaves one): the source's recorded transport and address give the readable
part exactly as a lookup computes it, so the next acquisition of that source reuses the
store. An ``f01`` store that no source names takes :data:`UNATTACHED_READABLE` and is
listed as unreferenced. A directory whose ``store.yml`` or ``source.yml`` does not record the identity its name spells is
damaged already and is left as it is. An entry whose record cannot be read, or that cannot
be moved (a name every width of which another entry holds, a parent that refuses the
rename), is skipped and named in a warning, so one cannot stop the rest. Past
:data:`MAX_MIGRATED_ENTRIES` entries in one directory the migration refuses, as the cache
routes do (mb-kire).

An older release that is fetching into a store holds absolute paths into the directory the
migration is about to move, which its Git would fail to finalize, so the migration first
tries each old store's ``.fetch.lock`` and refuses, with the layout left as it was, while
one is held (:class:`OlderReleaseBusyError`). An older process that is merely running is
not stopped by this, and reads nothing once the stores have moved; the changelog says to
stop such processes first.

``f03`` also moves the stores' parent from ``repository-stores`` to ``repos``. ``open_cache``
makes the skeleton before it migrates, so ``repos/`` exists and is empty, which rules out
renaming the parent in one step: each store is moved into it by the same atomic,
no-replace rename that respells its key. An entry the migration skips is moved there under
its old name, which leaves it with the other entries no route recognises, and the old
parent is removed once it is empty. The renames are planned and then applied by
:func:`apply_renames`, which takes paths relative to the home and moves each entry to the
first target nothing holds.

Lock files named for a renamed entry are left where they are: an older process may still
hold one, and an empty file costs nothing.

The caller holds the application-home lock, and each rename is atomic and refuses to
replace, so an interrupted migration is resumed by running it again: the entries it
renamed are not legacy names any more. Nothing is read or written outside the home.

``f01`` is released data. Metabrowser v0.12.0 wrote its whole-digest store names,
``repository-stores`` directory, ``--`` source slugs, and ``RepositorySource/v1`` records.
"""

from __future__ import annotations

import logging
import os
import re
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Final

from pydantic import BaseModel, ValidationError
from softschema.validate import parse_yaml_text

from metabrowser.cache.atomic import (
    RecordError,
    read_bytes_bounded,
    read_record,
    sync_directory,
    write_record_atomic,
)
from metabrowser.cache.identity import (
    IDENTITY_PREFIX,
    TRANSPORTS,
    GitTransport,
    ObjectFormat,
    identity_digest,
    is_identity,
    is_slug,
    readable_part,
    repository_store_id,
    slug_candidates,
    source_identity,
    store_key_candidates_for,
)
from metabrowser.cache.listing import list_private_directory
from metabrowser.cache.locks import legacy_store_fetch_busy
from metabrowser.cache.paths import REPOSITORY_STORES, SOURCES, source_record
from metabrowser.cache.records import (
    REPOSITORY_SOURCE_CONTRACT_ID,
    REPOSITORY_STORE_ALIAS_CONTRACT_ID,
    REPOSITORY_STORE_CONTRACT_ID,
    RepositorySource,
    RepositoryStore,
    RepositoryStoreAlias,
)
from metabrowser.home import (
    PrivateStorageError,
    ensure_private_directory,
    rename_without_replacing,
)

log = logging.getLogger(__name__)

# What ``f01`` called the directory of the stores, which ``f03`` calls
# :data:`~metabrowser.cache.paths.REPOSITORY_STORES`.
LEGACY_REPOSITORY_STORES: Final = "repository-stores"
# The contract of the ``source.yml`` that ``f01`` wrote, whose slug was words
# joined by ``--`` and hexadecimal digits. It is read here and nowhere else.
LEGACY_SOURCE_CONTRACT_ID: Final = "metabrowser.cache:RepositorySource/v1"
# The readable part of the key of a store no source names and whose old name said nothing:
# nothing says which repository it holds, so the key says only that nothing is attached.
UNATTACHED_READABLE: Final = "unattached"
# The most entries of ``repos``, ``repository-stores`` or ``sources`` one migration lists,
# and refuses past: the bound the cache routes list under (``MAX_DIRECTORY_ENTRIES`` in
# ``cache/projection.py``, which a test holds this to), where a listing of 10,000 names
# measured 6-11 ms. A home past it is one those routes refused already.
MAX_MIGRATED_ENTRIES: Final = 10_000

_LEGACY_STORE_KEY_RE: Final = re.compile(r"^[0-9a-f]{64}$")
# An ``f01`` source slug has words joined by ``--`` followed by an identity digest prefix.
_LEGACY_SOURCE_SLUG_RE: Final = re.compile(
    r"^[a-z0-9]+(?:-[a-z0-9]+)*(?:--[a-z0-9]+(?:-[a-z0-9]+)*)*$"
)
_LEGACY_SOURCE_SEPARATOR: Final = "--"
_LEGACY_SOURCE_MAX_BYTES: Final = 96 + len(_LEGACY_SOURCE_SEPARATOR) + 64
LEGACY_SOURCE_SUFFIX_HEX_DIGITS: Final = (12, 16, 24, 32, 64)
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


class OlderReleaseBusyError(Exception):
    """A process of an earlier release holds the fetch lock of a store about to move."""


def apply_renames(home: Path, renames: Sequence[Rename]) -> list[str]:
    """Move each entry of *renames* where it stands, and return the target each took.

    Each is renamed to its first target that nothing holds, never over an existing entry
    (:func:`~metabrowser.home.rename_without_replacing`), and the directories it left and
    entered are flushed so the move survives a crash. Raises :class:`NoFreeTargetError` if
    something holds every target of one.
    """

    taken: list[str] = []
    for rename in renames:
        source = home / rename.source
        for target in rename.targets:
            try:
                rename_without_replacing(source, home / target)
            except FileExistsError:
                continue
            for directory in sorted({source.parent, (home / target).parent}):
                sync_directory(directory)
            taken.append(target)
            break
        else:
            raise NoFreeTargetError("every target of a rename is held by another entry")
    return taken


def is_legacy_store_key(name: str) -> bool:
    """Whether *name* is a store directory named as an ``f01`` home names it."""

    return _LEGACY_STORE_KEY_RE.fullmatch(name) is not None


def _legacy_source_suffix(name: str) -> str | None:
    """Return the hexadecimal suffix of an ``f01`` source slug."""
    if len(name) > _LEGACY_SOURCE_MAX_BYTES or _LEGACY_SOURCE_SLUG_RE.fullmatch(name) is None:
        return None
    readable, separator, suffix = name.rpartition(_LEGACY_SOURCE_SEPARATOR)
    if (
        not separator
        or not readable
        or len(suffix) not in LEGACY_SOURCE_SUFFIX_HEX_DIGITS
        or _HEX_RE.fullmatch(suffix) is None
    ):
        return None
    return suffix


def is_legacy_source_slug(name: str) -> bool:
    """Whether *name* has the shape of an ``f01`` source slug."""
    return _legacy_source_suffix(name) is not None


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


def _skipped(entry: str) -> None:
    log.warning("Skipped a cache entry the migration could not read: %s", entry)


def _legacy_source_values(home: Path, name: str) -> dict[str, Any] | None:
    """The values of the ``source.yml`` in the directory *name*, read without its contract.

    Under ``f03`` a record whose slug is spelled as ``f01`` spells it no longer validates,
    so an old record is read as the YAML mapping it is and checked by hand
    (:func:`_source_slugs`). Its header must name the old contract, or the current one, which
    an interrupted migration leaves. ``None`` when there is none or it cannot be read, which
    is named.
    """

    try:
        payload = read_bytes_bounded(home, f"{SOURCES}/{name}/source.yml", shared="keep")
    except FileNotFoundError:
        log.warning("Left a cache source with no record: %s", name)
        return None
    except (OSError, PrivateStorageError, RecordError, ValueError):
        _skipped(name)
        return None
    try:
        document = parse_yaml_text(payload.decode("utf-8").removeprefix("\ufeff"))
    except (UnicodeDecodeError, ValueError):
        _skipped(name)
        return None
    values = document.get("source") if isinstance(document, dict) else None
    header = document.get("softschema") if isinstance(document, dict) else None
    contract = header.get("contract") if isinstance(header, dict) else None
    if not isinstance(values, dict) or contract not in (
        LEGACY_SOURCE_CONTRACT_ID,
        REPOSITORY_SOURCE_CONTRACT_ID,
    ):
        _skipped(name)
        return None
    return values


def _source_slugs(name: str, values: dict[str, Any]) -> tuple[str, ...] | None:
    """The ``f03`` slugs the source in the directory *name* may take, or ``None``.

    The record must name its directory: its slug is the directory's, or is already an
    ``f03`` slug of its identity, as a migration interrupted after rewriting it leaves it.
    Its identity must derive from its transport and address, and a legacy slug must end in
    digits of that identity. Anything else is damaged already.
    """

    source_id = values.get("id")
    transport = values.get("transport")
    address = values.get("clone_url")
    recorded = values.get("slug")
    suffix = _legacy_source_suffix(name)
    if (
        suffix is not None
        and isinstance(source_id, str)
        and is_identity(source_id)
        and transport in TRANSPORTS
        and isinstance(address, str)
        and isinstance(recorded, str)
        and source_identity(transport, address) == source_id
        and identity_digest(source_id).startswith(suffix)
    ):
        candidates = slug_candidates(transport, address, source_id)
        if recorded == name or recorded in candidates:
            return candidates
    log.warning("Left a cache source whose record does not name its directory: %s", name)
    return None


def _rename_legacy_sources(home: Path) -> int:
    """Give every source directory of ``f01`` its ``f03`` slug; return how many."""

    try:
        names = list_private_directory(
            home, SOURCES, max_entries=MAX_MIGRATED_ENTRIES, shared="keep"
        )
    except FileNotFoundError:
        return 0
    renamed = 0
    for name in names:
        if not is_legacy_source_slug(name):
            continue
        values = _legacy_source_values(home, name)
        if values is None:
            continue
        candidates = _source_slugs(name, values)
        if candidates is None:
            continue
        # The slug a source recorded before it was interrupted is kept if it is still free.
        recorded = values["slug"]
        ordered = (recorded, *candidates) if recorded in candidates else candidates
        free = next((slug for slug in ordered if not os.path.lexists(home / SOURCES / slug)), None)
        if free is None:
            log.warning("Left a cache source every slug of which another source holds: %s", name)
            continue
        try:
            record = RepositorySource.model_validate({**values, "slug": free})
        except ValidationError:
            _skipped(name)
            continue
        try:
            write_record_atomic(
                home, f"{SOURCES}/{name}/source.yml", record, REPOSITORY_SOURCE_CONTRACT_ID
            )
            apply_renames(home, [Rename(f"{SOURCES}/{name}", (f"{SOURCES}/{free}",))])
        except (OSError, PrivateStorageError):
            log.warning("Left a cache source the migration could not move: %s", name)
            continue
        renamed += 1
    return renamed


def _repositories_by_store(home: Path) -> dict[str, tuple[GitTransport, str]]:
    """The transport and address of the repository each store belongs to.

    A store an alias names belongs to the source that alias is in. A store no alias names
    still belongs to the source whose identity derives it, in either object format, which
    is how an acquisition interrupted between its two renames, or a source published with
    no store, keeps its repository's name. An alias wins over a derivation, and an entry
    that cannot be read names nothing. Sources are read under their ``f03`` names, so a
    source the migration left under an old one names nothing either.
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
        home,
        f"{LEGACY_REPOSITORY_STORES}/{name}/store.yml",
        REPOSITORY_STORE_CONTRACT_ID,
        name,
    )
    return record.id if isinstance(record, RepositoryStore) else None


def plan_store_renames(home: Path) -> list[Rename]:
    """The renames that move every store of ``repository-stores`` into ``repos`` as its key.

    A store with an ``f01`` name takes its ``f03`` key. Entries with unrecognized names
    or mismatched records move afterwards under their existing names, so they cannot
    take a store's first key choice. A home with no
    ``repository-stores`` has nothing to plan.
    """

    try:
        names = list_private_directory(
            home, LEGACY_REPOSITORY_STORES, max_entries=MAX_MIGRATED_ENTRIES, shared="keep"
        )
    except FileNotFoundError:
        return []
    legacy = {name for name in names if is_legacy_store_key(name)}
    repositories = _repositories_by_store(home) if legacy else {}
    stores: list[Rename] = []
    kept: list[Rename] = []
    for name in names:
        source = f"{LEGACY_REPOSITORY_STORES}/{name}"
        if name not in legacy:
            kept.append(Rename(source, (f"{REPOSITORY_STORES}/{name}",)))
            continue
        recorded = _recorded_identity(home, name)
        if recorded is None or recorded != f"{IDENTITY_PREFIX}{name}":
            log.warning("Left a cache store whose record does not name its directory: %s", name)
            kept.append(Rename(source, (f"{REPOSITORY_STORES}/{name}",)))
            continue
        repository = repositories.get(recorded)
        readable = readable_part(*repository) if repository is not None else UNATTACHED_READABLE
        stores.append(
            Rename(
                source,
                tuple(
                    f"{REPOSITORY_STORES}/{key}"
                    for key in store_key_candidates_for(readable, recorded)
                ),
            )
        )
    return [*stores, *kept]


def _move_stores(home: Path) -> int:
    """Move every store into ``repos``; return how many; remove the old parent if empty."""

    plan = plan_store_renames(home)
    if plan:
        # `open_cache` has made `repos/` already; a migration run alone has not.
        ensure_private_directory(home, REPOSITORY_STORES)
    taken = _apply_store_renames(home, plan)
    try:
        os.rmdir(home / LEGACY_REPOSITORY_STORES)
    except FileNotFoundError:
        pass
    except OSError:
        log.warning("Left the old cache directory for stores, which still holds entries")
    else:
        sync_directory(home)
    return len(taken)


def _apply_store_renames(home: Path, plan: list[Rename]) -> list[str]:
    """Apply *plan*, leaving in the old directory any entry that cannot be moved.

    An entry that cannot move is not worth refusing every open for: a store whose every key
    another store holds, an entry whose old name something in ``repos`` already holds, or a
    directory that refuses the rename is named in a warning and left where it is, and keeps
    the old directory from being removed.
    """

    taken: list[str] = []
    for rename in plan:
        name = rename.source.rpartition("/")[2]
        if len(rename.targets) == 1 and os.path.lexists(home / rename.targets[0]):
            log.warning("Left a cache entry whose name another entry holds: %s", name)
            continue
        try:
            taken.extend(apply_renames(home, [rename]))
        except NoFreeTargetError:
            log.warning("Left a cache store every key of which another store holds: %s", name)
        except OSError:
            log.warning("Left a cache entry the migration could not move: %s", name)
    return taken


def _refuse_while_an_older_release_fetches(home: Path) -> None:
    """Raise :class:`OlderReleaseBusyError` if a process holds an old store's fetch lock.

    An ``f01`` store's fetch lock used its directory name. An older process holds that
    lock across its network work. The lock is only tried, never kept, and
    a lock file that is missing means no fetch, so none is created.
    """

    try:
        names = list_private_directory(
            home, LEGACY_REPOSITORY_STORES, max_entries=MAX_MIGRATED_ENTRIES, shared="keep"
        )
    except FileNotFoundError:
        return
    for name in names:
        if not is_legacy_store_key(name):
            continue
        try:
            busy = legacy_store_fetch_busy(home, name)
        except (OSError, PrivateStorageError):
            log.warning("Could not tell whether an earlier release is fetching into: %s", name)
            continue
        if busy:
            raise OlderReleaseBusyError(
                "An earlier release of Metabrowser is fetching into this cache, so it cannot be "
                "upgraded yet. Stop that metab or wait for it to finish, then open the "
                "repository again."
            )


def rename_legacy_names(home: Path) -> None:
    """Give every source and store of *home* its ``f03`` name, and move the stores to ``repos``.

    Raises :class:`OlderReleaseBusyError`, before anything is renamed, while an earlier
    release is fetching into a store. An entry that cannot be renamed or moved is left as it
    is and named in a warning.
    """

    _refuse_while_an_older_release_fetches(home)
    sources = _rename_legacy_sources(home)
    stores = _move_stores(home)
    if sources or stores:
        log.info("Renamed %d cache source(s) and %d cache store(s)", sources, stores)


__all__ = [
    "DERIVED_OBJECT_FORMATS",
    "LEGACY_REPOSITORY_STORES",
    "MAX_MIGRATED_ENTRIES",
    "UNATTACHED_READABLE",
    "LEGACY_SOURCE_CONTRACT_ID",
    "LEGACY_SOURCE_SUFFIX_HEX_DIGITS",
    "NoFreeTargetError",
    "OlderReleaseBusyError",
    "Rename",
    "apply_renames",
    "is_legacy_source_slug",
    "is_legacy_store_key",
    "plan_store_renames",
    "rename_legacy_names",
]
