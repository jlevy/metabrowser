"""Durable, disposable PR cores bound to the repository catalog's private identity.

A core is useful after its freshness window or a process restart. The catalog member's
fingerprint determines whether preparation must revalidate it; display may use a stale
core from the same source, repository, reader, and catalog epoch. No read fetches.
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict

from metabrowser.builtin_plugins.github.pull_catalog import (
    CatalogMember,
    CatalogState,
    catalog_members,
)
from metabrowser.builtin_plugins.github.pull_list import parse_stamp
from metabrowser.builtin_plugins.github.pull_record import (
    MAX_PULL_RECORD_BYTES,
    PullRefreshStamp,
    PullRequest,
    ensure_pulls_directory,
)
from metabrowser.builtin_plugins.github.served_pull import PullCorePreview, make_core_preview
from metabrowser.cache.atomic import RecordError, read_bytes_bounded
from metabrowser.cache.locks import source_alias_lock
from metabrowser.cache.paths import source_pull_core, source_pull_cores_refresh
from metabrowser.home import PrivateStorageError, write_private_file_atomic


class CachedCore(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: Literal[1] = 1
    source: str
    repository_id: str
    reader: str
    epoch: str
    fingerprint: str
    observed_at: str
    pull: PullRequest


def _identity(catalog: CatalogState) -> tuple[str, str, str, str]:
    return catalog.source, catalog.repository_id, catalog.reader, catalog.epoch


def read_cached_core(
    home: Path,
    slug: str,
    number: int,
    *,
    fresh_only: bool = False,
    reader: str | None = None,
    reader_identity: tuple[str, str, str, str] | None = None,
) -> PullCorePreview | None:
    """Read one bounded core and validate it against one current catalog snapshot."""

    try:
        data = read_bytes_bounded(
            home, source_pull_core(slug, number), max_bytes=MAX_PULL_RECORD_BYTES, shared="refuse"
        )
        entry = CachedCore.model_validate_json(data)
        observed = parse_stamp(entry.observed_at)
        catalog, members = catalog_members(home, slug, "all", (number,))
        if (
            catalog is None
            or number not in members
            or entry.pull.number != number
            or (
                reader is not None
                and entry.reader != reader
                and (reader_identity is None or reader_identity == _identity(catalog))
            )
            or (entry.source, entry.repository_id, entry.reader, entry.epoch) != _identity(catalog)
            or (fresh_only and entry.fingerprint != members[number].fingerprint.hex())
        ):
            return None
        return make_core_preview(entry.source, entry.reader, entry.pull, observed, "not_started")
    except (FileNotFoundError, RecordError, PrivateStorageError, OSError, ValueError):
        return None


def write_cached_cores(
    home: Path,
    slug: str,
    catalog: CatalogState,
    members: dict[int, CatalogMember],
    cores: dict[int, PullRequest],
    observed_at: datetime,
) -> dict[int, PullCorePreview]:
    """Publish a batch only while the same catalog identity and members still hold.

    Caller runs this through run_lock_section, so cancelling a queued lock wait
    cannot publish later. The provider has already authenticated the actual viewer.
    """

    if not cores:
        return {}
    with source_alias_lock(home, slug):
        current, now = catalog_members(home, slug, "all", tuple(cores))
        if current is None or _identity(current) != _identity(catalog):
            return {}
        ensure_pulls_directory(home, slug)
        published: dict[int, PullCorePreview] = {}
        for number, core in cores.items():
            if now.get(number) != members.get(number):
                continue
            preview = make_core_preview(
                catalog.source, catalog.reader, core, observed_at, "not_started"
            )
            entry = CachedCore(
                source=catalog.source,
                repository_id=catalog.repository_id,
                reader=catalog.reader,
                epoch=catalog.epoch,
                fingerprint=members[number].fingerprint.hex(),
                observed_at=preview["observed_at"],
                pull=core,
            )
            data = entry.model_dump_json().encode()
            if len(data) > MAX_PULL_RECORD_BYTES:
                raise ValueError("the core exceeds the existing PR record read budget")
            write_private_file_atomic(home, source_pull_core(slug, number), data)
            published[number] = preview
        return published


class CachedCoreFailure(BaseModel):
    """A source-wide provider hold, with the same private identity as the core cache."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: Literal[1] = 1
    source: str
    repository_id: str
    reader: str
    epoch: str
    failure: PullRefreshStamp


def read_core_failure(home: Path, slug: str) -> PullRefreshStamp | None:
    """Read the latest preparation failure without probing GitHub or creating files."""
    from metabrowser.builtin_plugins.github.pull_catalog import read_catalog

    try:
        entry = CachedCoreFailure.model_validate_json(
            read_bytes_bounded(
                home,
                source_pull_cores_refresh(slug),
                max_bytes=MAX_PULL_RECORD_BYTES,
                shared="refuse",
            )
        )
        catalog = read_catalog(home, slug)
        if catalog is None or (
            entry.source,
            entry.repository_id,
            entry.reader,
            entry.epoch,
        ) != _identity(catalog):
            return None
        return entry.failure
    except (FileNotFoundError, RecordError, PrivateStorageError, OSError, ValueError):
        return None


def write_core_failure(
    home: Path, slug: str, catalog: CatalogState, failure: PullRefreshStamp
) -> None:
    """Persist the latest preparation outcome without replacing useful cores."""
    from metabrowser.builtin_plugins.github.pull_catalog import read_catalog

    with source_alias_lock(home, slug):
        current = read_catalog(home, slug)
        if current is None or _identity(current) != _identity(catalog):
            return
        previous = read_core_failure(home, slug)
        if previous is not None and (
            parse_stamp(previous.at) > parse_stamp(failure.at)
            or (
                previous.at == failure.at
                and previous.outcome != "succeeded"
                and failure.outcome == "succeeded"
            )
        ):
            return
        ensure_pulls_directory(home, slug)
        data = (
            CachedCoreFailure(
                source=catalog.source,
                repository_id=catalog.repository_id,
                reader=catalog.reader,
                epoch=catalog.epoch,
                failure=failure,
            )
            .model_dump_json()
            .encode()
        )
        write_private_file_atomic(home, source_pull_cores_refresh(slug), data)
