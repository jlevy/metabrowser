"""Wire shapes for the read-only ``/api/cache/`` routes.

The routes project logical ``f01`` state: the layout and config formats, source and store
identity, alias generations, publication state, and abandoned staging. Nothing here
names a cache path, a pack file, a Git internal, or a count that changes with ``gc``, and
nothing names the application home itself.

Conventions follow :mod:`metabrowser.git.wire`: required keys are required to the type
checker, conditional keys are ``NotRequired``, and a record that could not be read is
``None`` beside a ``problems`` entry that says why in a path-free sentence.

These are ``TypedDict`` rather than validating models on purpose. Every value is copied
from a cache record that its strict Pydantic model and SoftSchema contract already
validated on read, so a second model would only re-check it; the type checker holds each
producer in :mod:`metabrowser.cache.projection` to the required keys instead, and there
are no hand-synced gate sets to drift.
"""

from __future__ import annotations

from typing import Literal, NotRequired, TypedDict

type HomePresence = Literal["absent", "present"]

type LayoutState = Literal[
    # No directory at the resolved application home.
    "absent",
    # A home without cache/layout.yml and without cache entries a layout would describe.
    "uninitialized",
    # The layout and config are this release's format.
    "current",
    # The layout is current and config.yml is missing or lags it: an unfinished migration.
    "config_pending",
    # The layout is an older format this release migrates before reading entries.
    "migration_pending",
]

type SourcePublication = Literal[
    # The alias names a published store: the source is visible.
    "published",
    # The source is recorded but has no alias yet, so nothing opens it.
    "unattached",
    # The alias names a store that is not published.
    "dangling",
    # A record, or the directory holding it, is readable by other users, so Metabrowser
    # refused to read it rather than change permissions to answer a request. Reported
    # ahead of damage, because a record that was never read cannot be called corrupt, and
    # kept apart from it because the two need different things from the user: one a
    # chmod, the other an investigation.
    "not_private",
    # A record is missing, invalid, or inconsistent with its entry.
    "damaged",
]

type StorePublication = Literal["published", "not_private", "damaged"]

type ReferenceState = Literal[
    # At least one readable alias names the store.
    "referenced",
    # Every alias was read and none names the store, and there is no provider data.
    "unreferenced",
    # A reference could not be ruled out: an unreadable alias, an unrecognized source
    # entry, provider data, or a request whose record budget ran out before the alias
    # scan finished.
    "unknown",
]

type RecordName = Literal["source.yml", "state.yml", "store-alias.yml", "store.yml"]

type RecordProblemCode = Literal["missing", "invalid", "not_private", "unreadable", "mismatch"]
"""Why one record could not be reported. ``not_private`` is the one the user fixes with
``chmod``; the rest mean the record itself, or its absence, is the problem."""

type CacheErrorCode = Literal[
    "invalid_home_setting",
    "home_not_private",
    "future_format",
    "layout_unreadable",
    "config_unreadable",
    "layout_missing",
    "migration_pending",
    "invalid_parameter",
    "source_not_found",
    "cache_enumeration_limit",
    "cache_read_failed",
]


class CacheError(TypedDict):
    """A refusal. ``error`` is a sentence with no absolute path in it."""

    error: str
    code: CacheErrorCode
    # home_not_private: the logical location and the violation, never an absolute path.
    location: NotRequired[str]
    violation: NotRequired[str]
    # home_not_private: the fixed f01 location that failed, such as `cache/sources`, so
    # the user knows what to fix. Absent for anything else, and never a slug, a store
    # key, or a staging entry name.
    path: NotRequired[str]
    # future_format: the format found and the newest one this release reads.
    found: NotRequired[str]
    supported: NotRequired[str]


class RecordProblem(TypedDict):
    """Why one record of an entry could not be reported."""

    record: RecordName
    code: RecordProblemCode
    message: str


# ── /api/cache/layout ──────────────────────────────────────────────


class LayoutRecord(TypedDict):
    format: str
    created_by: str


class ConfigUpgrade(TypedDict):
    version: str
    at: str


class ConfigRecord(TypedDict):
    """The known fields of ``config.yml``; the user's own settings are not echoed."""

    format: str
    written_by: str
    upgrades: list[ConfigUpgrade]


class Reclamation(TypedDict):
    """What the next startup sweep may remove: abandoned staging entries."""

    staging_entries: int


class CacheLayoutResponse(TypedDict):
    home: HomePresence
    supported_format: str
    state: LayoutState
    layout: LayoutRecord | None
    config: ConfigRecord | None
    reclamation: Reclamation | None


# ── /api/cache/sources and /api/cache/source/{slug} ────────────────


class SourceIdentity(TypedDict):
    id: str
    display_url: str
    clone_url: str
    transport: str
    created_at: str


class SourceAlias(TypedDict):
    store_id: str
    generation: int
    updated_at: str


class SourceState(TypedDict):
    last_opened_at: str | None


class SourceRow(TypedDict):
    """One source's three records. ``publication`` is decided after all of them, so it
    never disagrees with ``problems`` or with the same entry on the other route."""

    slug: str
    publication: SourcePublication
    identity: SourceIdentity | None
    alias: SourceAlias | None
    state: SourceState | None
    problems: list[RecordProblem]


class CacheSourcesResponse(TypedDict):
    home: HomePresence
    layout_format: str | None
    sources: list[SourceRow]
    unrecognized_entries: int
    limit: int
    next_after: str | None


# ── /api/cache/stores ──────────────────────────────────────────────


class StoreAcquisition(TypedDict):
    git_version: str
    object_format: str


class StoreIdentity(TypedDict):
    created_at: str
    acquisition: StoreAcquisition


class StoreOperation(TypedDict):
    kind: str
    outcome: str
    at: str


class StoreState(TypedDict):
    default_remote_ref: str | None
    default_revision: str | None
    last_fetch_at: str | None
    last_operation: StoreOperation


class StoreRecords(TypedDict):
    id: str
    publication: StorePublication
    identity: StoreIdentity | None
    state: StoreState | None
    problems: list[RecordProblem]


class StoreReference(TypedDict):
    slug: str
    generation: int


class StoreRow(StoreRecords):
    referenced_by: list[StoreReference]
    reference_state: ReferenceState


class CacheStoresResponse(TypedDict):
    home: HomePresence
    layout_format: str | None
    stores: list[StoreRow]
    unrecognized_entries: int
    limit: int
    next_after: str | None


class SourceDetail(SourceRow):
    store: StoreRecords | None


class CacheSourceResponse(TypedDict):
    home: HomePresence
    layout_format: str
    source: SourceDetail


__all__ = [
    "CacheError",
    "CacheErrorCode",
    "CacheLayoutResponse",
    "CacheSourceResponse",
    "CacheSourcesResponse",
    "CacheStoresResponse",
    "ConfigRecord",
    "ConfigUpgrade",
    "HomePresence",
    "LayoutRecord",
    "LayoutState",
    "Reclamation",
    "RecordName",
    "RecordProblem",
    "RecordProblemCode",
    "ReferenceState",
    "SourceAlias",
    "SourceDetail",
    "SourceIdentity",
    "SourcePublication",
    "SourceRow",
    "SourceState",
    "StoreAcquisition",
    "StoreIdentity",
    "StoreOperation",
    "StorePublication",
    "StoreRecords",
    "StoreReference",
    "StoreRow",
]
