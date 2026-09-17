"""Logical projections of the ``f01`` cache for the read-only ``/api/cache/`` routes.

Each projection resolves the application home per request and never creates it: a
missing home is the ``absent`` state, not an error. Reads take no lock, because a lock is
a file write and a cache hit must be readable from a home the process cannot write; a
concurrent publication, quarantine, or reclamation can therefore show an entry mid-move,
and an entry that disappears between listing and reading is left out rather than
reported damaged. Records are read only through :func:`~metabrowser.cache.atomic.read_record`,
:func:`~metabrowser.cache.layout.read_layout`, and :func:`~metabrowser.cache.layout.read_config`,
and directories only through :func:`~metabrowser.cache.listing.list_private_directory`,
so everything reported was verified owner-only on the way in.

Entries are read under the layout this release writes, and every other state is refused
exactly as :func:`~metabrowser.cache.layout.migrate_layout` would refuse it: a newer
format, an unknown one, an older one awaiting migration, or entries with no layout at
all. A home-wide refusal is a typed, path-free :class:`~metabrowser.cache.wire.CacheError`;
a damaged entry is reported beside the readable ones with the reason in ``problems``.

Enumeration is bounded. Names in one directory are cheap next to records, so a listing
reads up to :data:`MAX_DIRECTORY_ENTRIES` names and refuses past that; record reads are
bounded by the page size and, for store references, by :data:`MAX_REFERENCE_SCAN`.
"""

from __future__ import annotations

import logging
import os
from collections.abc import Callable
from pathlib import Path
from typing import Final

from pydantic import BaseModel

from metabrowser import home as home_module
from metabrowser.cache.atomic import RecordError, read_record
from metabrowser.cache.identity import IDENTITY_PREFIX, is_identity, is_slug, is_store_key
from metabrowser.cache.layout import (
    FORMAT_HISTORY,
    FutureLayoutFormatError,
    LayoutError,
    read_config,
    read_layout,
)
from metabrowser.cache.listing import ListingLimitError, list_private_directory
from metabrowser.cache.locks import is_entry_name
from metabrowser.cache.paths import (
    CACHE_ROOT,
    PROVIDER_BINDINGS,
    PROVIDER_REPOSITORIES,
    QUARANTINE,
    REPOSITORY_STORES,
    SOURCES,
    STAGING,
    TRASH,
    quarantine_entry,
    source_directory,
    source_record,
    store_directory,
    store_record,
)
from metabrowser.cache.records import (
    REPOSITORY_SOURCE_CONTRACT_ID,
    REPOSITORY_SOURCE_STATE_CONTRACT_ID,
    REPOSITORY_STORE_ALIAS_CONTRACT_ID,
    REPOSITORY_STORE_CONTRACT_ID,
    REPOSITORY_STORE_STATE_CONTRACT_ID,
    ApplicationConfig,
    CacheLayout,
    RepositorySource,
    RepositorySourceState,
    RepositoryStore,
    RepositoryStoreAlias,
    RepositoryStoreState,
)
from metabrowser.cache.wire import (
    CacheError,
    CacheLayoutResponse,
    CacheSourceResponse,
    CacheSourcesResponse,
    CacheStoresResponse,
    ConfigRecord,
    LayoutState,
    QuarantineEntry,
    Reclamation,
    RecordName,
    RecordProblem,
    ReferenceState,
    SourceAlias,
    SourceDetail,
    SourceIdentity,
    SourcePublication,
    SourceRow,
    StoreIdentity,
    StoreRecords,
    StoreReference,
    StoreRow,
    StoreState,
)
from metabrowser.home import ApplicationHomeError, PrivateStorageError

log = logging.getLogger(__name__)

# Bounds, measured on 2026-09-17 against homes of real f01 records on macOS APFS, three
# rounds each, with load averages of 25-38 from unrelated work, so an idle machine is
# faster; the ratios are what the bounds rest on:
#
# - One verified record read: 1.3-1.7 ms median and 1.7-4.8 ms mean over 500 records.
#   Portable YAML parsing is most of it; path verification is about 0.5 ms.
# - A verified listing: 0.5-1.1 ms for 500 names and 6-11 ms for 10,000.
# - A sources page of 100 rows (two reads per row): 0.93-1.19 s.
# - A stores page whose references read 500 aliases: 1.4-2.2 s.
# - The layout of an empty cache: 3-7 ms.
#
# Record reads dominate by three orders of magnitude, so pages bound reads and listings
# bound only names.
DEFAULT_PAGE_LIMIT: Final = 50
MAX_PAGE_LIMIT: Final = 100
# Store references read one alias per source. Past this many sources they are reported
# unknown rather than read.
MAX_REFERENCE_SCAN: Final = 500
# Past this a listing is refused rather than truncated, because a partial listing cannot
# produce a correctly ordered page.
MAX_DIRECTORY_ENTRIES: Final = 10_000
# Each reported quarantine entry costs up to three verified listings.
MAX_QUARANTINE_ENTRIES: Final = 100

type CacheAnswer[T] = tuple[int, T | CacheError]

_MISSING_MESSAGE: Final = "The record is missing."
_UNREADABLE_MESSAGE: Final = "The record could not be read."
_DURABLE_DIRECTORIES: Final = (
    SOURCES,
    REPOSITORY_STORES,
    QUARANTINE,
    PROVIDER_BINDINGS,
    PROVIDER_REPOSITORIES,
)


class _Refusal(Exception):
    """A home-wide answer other than 200, with its typed body."""

    def __init__(self, status: int, body: CacheError) -> None:
        super().__init__(body["error"])
        self.status: int = status
        self.body: CacheError = body


# ── Public projections ─────────────────────────────────────────────


def page_limit(raw: str | None) -> int:
    """Parse and clamp a ``limit`` query parameter, as the Git routes do."""

    try:
        limit = int(raw) if raw else DEFAULT_PAGE_LIMIT
    except ValueError:
        return DEFAULT_PAGE_LIMIT
    return max(1, min(limit, MAX_PAGE_LIMIT))


def layout_response() -> CacheAnswer[CacheLayoutResponse]:
    """``/api/cache/layout``: format state, config, and reclamation outcomes."""

    return _answer(_layout)


def sources_response(*, limit: int, after: str | None) -> CacheAnswer[CacheSourcesResponse]:
    """``/api/cache/sources``: one page of sources in slug order."""

    return _answer(lambda: _sources(limit, after))


def source_response(slug: str) -> CacheAnswer[CacheSourceResponse]:
    """``/api/cache/source/{slug}``: one source with its recency and its store's records."""

    return _answer(lambda: _source(slug))


def stores_response(*, limit: int, after: str | None) -> CacheAnswer[CacheStoresResponse]:
    """``/api/cache/stores``: one page of stores in identity order, with references."""

    return _answer(lambda: _stores(limit, after))


def _answer[T](build: Callable[[], T]) -> CacheAnswer[T]:
    try:
        return 200, build()
    except _Refusal as refusal:
        return refusal.status, refusal.body
    except PrivateStorageError as error:
        return 409, {
            "error": str(error),
            "code": "home_not_private",
            "location": error.location.value,
            "violation": error.violation.value,
        }
    except ListingLimitError as error:
        return 503, {
            "error": (
                f"A cache directory holds more than {error.max_entries} entries, more than "
                "one request lists."
            ),
            "code": "cache_enumeration_limit",
        }
    except OSError:
        # home.py strips file names from these, so the log names no private repository.
        log.warning("Could not read the repository cache", exc_info=True)
        return 500, {
            "error": "The repository cache could not be read.",
            "code": "cache_read_failed",
        }


# ── Home, layout, and config ───────────────────────────────────────


def _resolve_home() -> Path | None:
    """Resolve and verify the home for this request; ``None`` when it does not exist."""

    try:
        home = home_module.application_home()
    except ApplicationHomeError as error:
        raise _Refusal(409, {"error": str(error), "code": "invalid_home_setting"}) from error
    try:
        home_module.validate_private_home(home)
    except FileNotFoundError:
        return None
    return home


def _future(error: FutureLayoutFormatError) -> _Refusal:
    return _Refusal(
        409,
        {
            "error": str(error),
            "code": "future_format",
            "found": error.found,
            "supported": error.supported,
        },
    )


def _read_layout(home: Path) -> CacheLayout | None:
    try:
        layout = read_layout(home)
    except FutureLayoutFormatError as error:
        raise _future(error) from error
    except LayoutError as error:
        raise _Refusal(409, {"error": str(error), "code": "layout_unreadable"}) from error
    if layout is not None and layout.format not in FORMAT_HISTORY:
        raise _Refusal(
            409,
            {
                "error": (
                    f"cache/layout.yml names format {layout.format}, which no Metabrowser "
                    "release wrote."
                ),
                "code": "layout_unreadable",
            },
        )
    return layout


def _read_config(home: Path) -> ApplicationConfig | None:
    try:
        return read_config(home)
    except FutureLayoutFormatError as error:
        raise _future(error) from error
    except LayoutError as error:
        raise _Refusal(409, {"error": str(error), "code": "config_unreadable"}) from error


def _names(home: Path, relative_path: str) -> tuple[str, ...]:
    try:
        return list_private_directory(home, relative_path, max_entries=MAX_DIRECTORY_ENTRIES)
    except FileNotFoundError:
        return ()


def _has_entries(home: Path, relative_path: str) -> bool:
    try:
        return bool(list_private_directory(home, relative_path, max_entries=0))
    except FileNotFoundError:
        return False
    except ListingLimitError:
        return True


def _refuse_entries_without_layout(home: Path) -> None:
    if any(_has_entries(home, directory) for directory in _DURABLE_DIRECTORIES):
        raise _Refusal(
            409,
            {
                "error": (
                    "The cache has entries but no cache/layout.yml, so their format is "
                    "unknown. Move the cache directory aside, or set METABROWSER_HOME to a "
                    "different directory."
                ),
                "code": "layout_missing",
            },
        )


def _entries_layout(home: Path) -> CacheLayout | None:
    """The layout entries are read under; ``None`` when the home has neither."""

    layout = _read_layout(home)
    if layout is None:
        _refuse_entries_without_layout(home)
        return None
    if layout.format != FORMAT_HISTORY[-1]:
        raise _Refusal(
            409,
            {
                "error": (
                    f"This application home uses format {layout.format}, which this release "
                    f"migrates to {FORMAT_HISTORY[-1]} before it reads cache entries."
                ),
                "code": "migration_pending",
            },
        )
    return layout


def _layout() -> CacheLayoutResponse:
    supported = FORMAT_HISTORY[-1]
    home = _resolve_home()
    if home is None:
        return {
            "home": "absent",
            "supported_format": supported,
            "state": "absent",
            "layout": None,
            "config": None,
            "reclamation": None,
        }
    layout = _read_layout(home)
    config = _read_config(home)
    state: LayoutState
    if layout is None:
        _refuse_entries_without_layout(home)
        state = "uninitialized"
    elif layout.format != supported:
        state = "migration_pending"
    elif config is None or config.format != layout.format:
        state = "config_pending"
    else:
        state = "current"
    return {
        "home": "present",
        "supported_format": supported,
        "state": state,
        "layout": None
        if layout is None
        else {"format": layout.format, "created_by": layout.created_by},
        "config": None if config is None else _config(config),
        "reclamation": _reclamation(home),
    }


def _config(config: ApplicationConfig) -> ConfigRecord:
    return {
        "format": config.format,
        "written_by": config.written_by,
        "upgrades": [{"version": upgrade.version, "at": upgrade.at} for upgrade in config.upgrades],
    }


# ── Reclamation ────────────────────────────────────────────────────


def _retained_name(relative_path: str) -> str:
    """The name a cache directory keeps inside a trash or quarantine entry."""

    return relative_path.removeprefix(f"{CACHE_ROOT}/")


def _reclamation(home: Path) -> Reclamation:
    quarantined = [name for name in _names(home, QUARANTINE) if is_entry_name(name)]
    entries: list[QuarantineEntry] = []
    for name in quarantined[:MAX_QUARANTINE_ENTRIES]:
        entry = _quarantine_entry(home, name)
        if entry is not None:
            entries.append(entry)
    return {
        "staging_entries": sum(is_entry_name(name) for name in _names(home, STAGING)),
        "trash_entries": sum(is_entry_name(name) for name in _names(home, TRASH)),
        "quarantine_entries": len(quarantined),
        "quarantine": entries,
        "quarantine_truncated": len(quarantined) > MAX_QUARANTINE_ENTRIES,
    }


def _quarantine_entry(home: Path, name: str) -> QuarantineEntry | None:
    """The logical entries one quarantine retains; ``None`` if it was purged meanwhile."""

    base = quarantine_entry(name)
    try:
        contents = list_private_directory(home, base, max_entries=MAX_DIRECTORY_ENTRIES)
    except FileNotFoundError:
        return None
    sources_name = _retained_name(SOURCES)
    stores_name = _retained_name(REPOSITORY_STORES)
    sources = _names(home, f"{base}/{sources_name}") if sources_name in contents else ()
    stores = _names(home, f"{base}/{stores_name}") if stores_name in contents else ()
    return {
        "entry": name,
        "sources": [slug for slug in sources if is_slug(slug)],
        "stores": [f"{IDENTITY_PREFIX}{key}" for key in stores if is_store_key(key)],
    }


# ── Records ────────────────────────────────────────────────────────


def _exists(home: Path, relative_path: str) -> bool:
    """Whether an entry is still there; only decides whether to report it at all."""

    return os.path.lexists(home / relative_path)


def _read[M: BaseModel](
    home: Path,
    relative_path: str,
    contract_id: str,
    model: type[M],
    record: RecordName,
    problems: list[RecordProblem],
    *,
    required: bool,
) -> M | None:
    """Read one record, noting why it cannot be reported instead of failing the page."""

    try:
        value = read_record(home, relative_path, contract_id)
    except FileNotFoundError:
        if required:
            problems.append({"record": record, "code": "missing", "message": _MISSING_MESSAGE})
        return None
    except RecordError as error:
        problems.append({"record": record, "code": "invalid", "message": str(error)})
        return None
    except PrivateStorageError as error:
        problems.append({"record": record, "code": "not_private", "message": str(error)})
        return None
    except OSError:
        log.warning("Could not read a cache record", exc_info=True)
        problems.append({"record": record, "code": "unreadable", "message": _UNREADABLE_MESSAGE})
        return None
    if not isinstance(value, model):
        problems.append(
            {
                "record": record,
                "code": "invalid",
                "message": f"The record is not a {model.__name__}.",
            }
        )
        return None
    return value


# ── Sources ────────────────────────────────────────────────────────


def _source_identity(source: RepositorySource) -> SourceIdentity:
    return {
        "id": source.id,
        "display_url": source.display_url,
        "clone_url": source.clone_url,
        "transport": source.transport,
        "created_at": source.created_at,
    }


def _source_alias(alias: RepositoryStoreAlias) -> SourceAlias:
    return {
        "store_id": alias.store_id,
        "generation": alias.generation,
        "updated_at": alias.updated_at,
    }


def _source_row(
    home: Path, slug: str, store_keys: frozenset[str]
) -> tuple[SourceRow, RepositoryStoreAlias | None] | None:
    problems: list[RecordProblem] = []
    source = _read(
        home,
        source_record(slug, "source.yml"),
        REPOSITORY_SOURCE_CONTRACT_ID,
        RepositorySource,
        "source.yml",
        problems,
        required=True,
    )
    if source is None and not _exists(home, source_directory(slug)):
        return None
    alias = _read(
        home,
        source_record(slug, "store-alias.yml"),
        REPOSITORY_STORE_ALIAS_CONTRACT_ID,
        RepositoryStoreAlias,
        "store-alias.yml",
        problems,
        required=False,
    )
    if source is not None and source.slug != slug:
        problems.append(
            {
                "record": "source.yml",
                "code": "mismatch",
                "message": "source.yml records a different slug than the entry it is in.",
            }
        )
    if source is not None and alias is not None and alias.source_id != source.id:
        problems.append(
            {
                "record": "store-alias.yml",
                "code": "mismatch",
                "message": "store-alias.yml names a different source than source.yml.",
            }
        )
    publication: SourcePublication
    if problems:
        publication = "damaged"
    elif alias is None:
        publication = "unattached"
    elif alias.store_id.removeprefix(IDENTITY_PREFIX) not in store_keys:
        publication = "dangling"
    else:
        publication = "published"
    row: SourceRow = {
        "slug": slug,
        "publication": publication,
        "identity": None if source is None else _source_identity(source),
        "alias": None if alias is None else _source_alias(alias),
        "problems": problems,
    }
    return row, alias


def _store_keys(home: Path) -> frozenset[str]:
    return frozenset(key for key in _names(home, REPOSITORY_STORES) if is_store_key(key))


def _invalid_parameter(message: str) -> _Refusal:
    return _Refusal(400, {"error": message, "code": "invalid_parameter"})


def _sources(limit: int, after: str | None) -> CacheSourcesResponse:
    if after is not None and not is_slug(after):
        raise _invalid_parameter("after must be a source slug.")
    home = _resolve_home()
    layout = None if home is None else _entries_layout(home)
    if home is None or layout is None:
        return {
            "home": "absent" if home is None else "present",
            "layout_format": None,
            "sources": [],
            "unrecognized_entries": 0,
            "limit": limit,
            "next_after": None,
        }
    names = _names(home, SOURCES)
    slugs = [name for name in names if is_slug(name)]
    store_keys = _store_keys(home)
    candidates = [slug for slug in slugs if after is None or slug > after]
    rows: list[SourceRow] = []
    for slug in candidates[:limit]:
        read = _source_row(home, slug, store_keys)
        if read is not None:
            rows.append(read[0])
    return {
        "home": "present",
        "layout_format": layout.format,
        "sources": rows,
        "unrecognized_entries": len(names) - len(slugs),
        "limit": limit,
        "next_after": candidates[limit - 1] if len(candidates) > limit else None,
    }


def _source(slug: str) -> CacheSourceResponse:
    if not is_slug(slug):
        raise _invalid_parameter("The source slug is malformed.")
    not_found = _Refusal(404, {"error": "No source has this slug.", "code": "source_not_found"})
    home = _resolve_home()
    layout = None if home is None else _entries_layout(home)
    if home is None or layout is None or slug not in _names(home, SOURCES):
        raise not_found
    store_keys = _store_keys(home)
    read = _source_row(home, slug, store_keys)
    if read is None:
        raise not_found
    row, alias = read
    problems = row["problems"]
    state = _read(
        home,
        source_record(slug, "state.yml"),
        REPOSITORY_SOURCE_STATE_CONTRACT_ID,
        RepositorySourceState,
        "state.yml",
        problems,
        required=False,
    )
    store = None
    if alias is not None and row["publication"] != "damaged":
        key = alias.store_id.removeprefix(IDENTITY_PREFIX)
        if key in store_keys:
            store = _store_records(home, key)
    detail: SourceDetail = {
        "slug": row["slug"],
        "publication": row["publication"],
        "identity": row["identity"],
        "alias": row["alias"],
        "problems": problems,
        "state": None if state is None else {"last_opened_at": state.last_opened_at},
        "store": store,
    }
    return {"home": "present", "layout_format": layout.format, "source": detail}


# ── Stores ─────────────────────────────────────────────────────────


def _store_identity(store: RepositoryStore) -> StoreIdentity:
    acquisition = store.acquisition
    return {
        "created_at": store.created_at,
        "acquisition": {
            "strategy": acquisition.strategy,
            "git_version": acquisition.git_version,
            "object_format": acquisition.object_format,
        },
    }


def _store_state(state: RepositoryStoreState) -> StoreState:
    operation = state.last_operation
    return {
        "object_state": state.object_state,
        "default_remote_ref": state.default_remote_ref,
        "default_revision": state.default_revision,
        "last_fetch_at": state.last_fetch_at,
        "last_operation": {
            "kind": operation.kind,
            "outcome": operation.outcome,
            "at": operation.at,
        },
    }


def _store_records(home: Path, key: str) -> StoreRecords | None:
    problems: list[RecordProblem] = []
    store = _read(
        home,
        store_record(key, "store.yml"),
        REPOSITORY_STORE_CONTRACT_ID,
        RepositoryStore,
        "store.yml",
        problems,
        required=True,
    )
    if store is None and not _exists(home, store_directory(key)):
        return None
    state = _read(
        home,
        store_record(key, "state.yml"),
        REPOSITORY_STORE_STATE_CONTRACT_ID,
        RepositoryStoreState,
        "state.yml",
        problems,
        required=True,
    )
    store_id = f"{IDENTITY_PREFIX}{key}"
    if store is not None and store.id != store_id:
        problems.append(
            {
                "record": "store.yml",
                "code": "mismatch",
                "message": "store.yml records a different identity than the entry it is in.",
            }
        )
    return {
        "id": store_id,
        "publication": "damaged" if problems else "published",
        "identity": None if store is None else _store_identity(store),
        "state": None if state is None else _store_state(state),
        "problems": problems,
    }


def _references(home: Path) -> tuple[dict[str, list[StoreReference]], bool]:
    """Every readable alias by the store it names, and whether nothing else could refer.

    This mirrors :func:`~metabrowser.cache.reclaim.store_is_referenced`: provider data, an
    unrecognized source entry, and an unreadable alias all keep reclamation from treating
    a store as unreferenced, so they make the answer incomplete.
    """

    complete = not any(
        _has_entries(home, directory) for directory in (PROVIDER_BINDINGS, PROVIDER_REPOSITORIES)
    )
    names = _names(home, SOURCES)
    slugs = [name for name in names if is_slug(name)]
    if len(slugs) != len(names):
        complete = False
    if len(slugs) > MAX_REFERENCE_SCAN:
        return {}, False
    references: dict[str, list[StoreReference]] = {}
    for slug in slugs:
        try:
            alias = read_record(
                home, source_record(slug, "store-alias.yml"), REPOSITORY_STORE_ALIAS_CONTRACT_ID
            )
        except FileNotFoundError:
            continue
        except (RecordError, PrivateStorageError, OSError):
            complete = False
            continue
        if not isinstance(alias, RepositoryStoreAlias):
            complete = False
            continue
        references.setdefault(alias.store_id, []).append(
            {"slug": slug, "generation": alias.generation}
        )
    return references, complete


def _stores(limit: int, after: str | None) -> CacheStoresResponse:
    if after is not None and not is_identity(after):
        raise _invalid_parameter("after must be a repository store identity.")
    home = _resolve_home()
    layout = None if home is None else _entries_layout(home)
    if home is None or layout is None:
        return {
            "home": "absent" if home is None else "present",
            "layout_format": None,
            "stores": [],
            "unrecognized_entries": 0,
            "limit": limit,
            "next_after": None,
        }
    names = _names(home, REPOSITORY_STORES)
    keys = [name for name in names if is_store_key(name)]
    after_key = None if after is None else after.removeprefix(IDENTITY_PREFIX)
    candidates = [key for key in keys if after_key is None or key > after_key]
    references, complete = _references(home)
    rows: list[StoreRow] = []
    for key in candidates[:limit]:
        records = _store_records(home, key)
        if records is None:
            continue
        referenced_by = references.get(records["id"], [])
        reference_state: ReferenceState
        if referenced_by:
            reference_state = "referenced"
        elif complete:
            reference_state = "unreferenced"
        else:
            reference_state = "unknown"
        rows.append(
            {
                "id": records["id"],
                "publication": records["publication"],
                "identity": records["identity"],
                "state": records["state"],
                "problems": records["problems"],
                "referenced_by": referenced_by,
                "reference_state": reference_state,
            }
        )
    return {
        "home": "present",
        "layout_format": layout.format,
        "stores": rows,
        "unrecognized_entries": len(names) - len(keys),
        "limit": limit,
        "next_after": (
            f"{IDENTITY_PREFIX}{candidates[limit - 1]}" if len(candidates) > limit else None
        ),
    }


__all__ = [
    "DEFAULT_PAGE_LIMIT",
    "MAX_DIRECTORY_ENTRIES",
    "MAX_PAGE_LIMIT",
    "MAX_QUARANTINE_ENTRIES",
    "MAX_REFERENCE_SCAN",
    "CacheAnswer",
    "layout_response",
    "page_limit",
    "source_response",
    "sources_response",
    "stores_response",
]
