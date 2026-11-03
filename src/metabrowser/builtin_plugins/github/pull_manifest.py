"""A bounded, disposable bank of PR manifests beside a repository store.

The record's immutable endpoints are prepared after fetch, before its record is
published. A fresh server reads the manifest instead of running the costly raw
listing. Resolution still verifies that this store can answer for both commits.
Sixteen direct-mapped slots bound disk use without an index, enumeration or an
LRU lock: a collision replaces a slot and can only cause a later cache miss.
"""

from __future__ import annotations

import asyncio
import contextlib
import hashlib
import logging
import secrets
from typing import TYPE_CHECKING, Any, Final, Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from metabrowser.builtin_plugins.diff.comparison_cache import ResolvedManifest
from metabrowser.builtin_plugins.diff.sidekick import comparison_cache_key
from metabrowser.builtin_plugins.github.pull_record import MAX_PULL_RECORD_BYTES, PullRecord
from metabrowser.cache.atomic import RecordError, read_bytes_bounded
from metabrowser.cache.paths import store_directory
from metabrowser.diff.adapters.base import DiffSourceError
from metabrowser.diff.adapters.git import MAX_MANIFEST_FILES, GitDiffSource
from metabrowser.diff.format import FILE_DIFF_SCHEMA_VERSION, ChangeSetDocument
from metabrowser.git.process import GitError, GitLocation, RepositoryStoreTarget
from metabrowser.home import (
    PrivateStorageError,
    ensure_private_directory,
    private_directory_is_writable,
    write_private_file_atomic,
)
from metabrowser.http_caching import BUILD_TAG, store_tag

if TYPE_CHECKING:
    from metabrowser.cache.acquire import PublishedSource

log = logging.getLogger(__name__)

# The same retained-comparison count as the in-memory manifest cache. Cache admission
# uses the existing PR-record read bound; a larger result is still served in full.
MANIFEST_SLOTS: Final = 16
MAX_MANIFEST_RECORD_BYTES: Final = MAX_PULL_RECORD_BYTES


class _ManifestRecord(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: Literal[2] = 2
    epoch: str = Field(pattern=r"^[0-9a-f]{64}$")
    identity: tuple[str, ...] = Field(min_length=6, max_length=6)
    digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    document: ChangeSetDocument


def _identity(key: tuple[str, ...]) -> tuple[str, ...]:
    return (BUILD_TAG, *key)


def _directory(published: PublishedSource) -> str:
    return f"{store_directory(published.store_key)}/github-pull-manifests"


def _slot(key: tuple[str, ...]) -> int:
    digest = hashlib.sha256("\0".join(_identity(key)).encode()).digest()
    return int.from_bytes(digest[:8]) % MANIFEST_SLOTS


def _epoch_path(published: PublishedSource, key: tuple[str, ...]) -> str:
    return f"{store_directory(published.store_key)}/github-pull-manifest-{_slot(key):02d}.epoch"


def _epoch(published: PublishedSource, key: tuple[str, ...]) -> str:
    data = read_bytes_bounded(
        published.home, _epoch_path(published, key), max_bytes=64, shared="refuse"
    )
    if len(data) != 64 or any(byte not in b"0123456789abcdef" for byte in data):
        raise RecordError("the disposable manifest epoch is invalid", published.home)
    return data.decode("ascii")


def _current_epoch(published: PublishedSource, key: tuple[str, ...]) -> str:
    """Read or exclusively establish an epoch before any manifest computation."""
    try:
        return _epoch(published, key)
    except FileNotFoundError:
        with contextlib.suppress(FileExistsError):
            write_private_file_atomic(
                published.home,
                _epoch_path(published, key),
                secrets.token_hex(32).encode("ascii"),
                replace=False,
            )
        return _epoch(published, key)


def _path(published: PublishedSource, key: tuple[str, ...]) -> str:
    return f"{_directory(published)}/{_slot(key):02d}.json"


def _digest(document: ChangeSetDocument) -> str:
    return hashlib.sha256(document.model_dump_json(by_alias=True).encode()).hexdigest()


def _read(
    published: PublishedSource,
    key: tuple[str, ...],
    *,
    epoch: str | None = None,
) -> ResolvedManifest | None:
    try:
        if not private_directory_is_writable(published.home, _directory(published)):
            return None
        if epoch is None:
            epoch = _epoch(published, key)
        data = read_bytes_bounded(
            published.home,
            _path(published, key),
            max_bytes=MAX_MANIFEST_RECORD_BYTES,
            shared="refuse",
        )
        record = _ManifestRecord.model_validate_json(data)
    except (OSError, RecordError, PrivateStorageError, ValidationError):
        return None
    document = record.document
    manifest = document.manifest
    if (
        record.epoch != epoch
        or record.identity != _identity(key)
        or record.digest != _digest(document)
        or document.patches
        or len(manifest.files) > MAX_MANIFEST_FILES
        or manifest.totals.files != len(manifest.files)
    ):
        return None
    return ResolvedManifest(document.resolved, manifest)


def _write(
    published: PublishedSource, key: tuple[str, ...], answer: ResolvedManifest, epoch: str
) -> None:
    document = ChangeSetDocument(
        schema="file-diff-v1",
        schema_version=FILE_DIFF_SCHEMA_VERSION,
        resolved=answer.resolved,
        manifest=answer.manifest,
        patches={},
    )
    record = _ManifestRecord(
        epoch=epoch, identity=_identity(key), digest=_digest(document), document=document
    )
    data = record.model_dump_json(by_alias=True).encode()
    if len(data) > MAX_MANIFEST_RECORD_BYTES:
        return
    ensure_private_directory(published.home, _directory(published))
    write_private_file_atomic(published.home, _path(published, key), data)


def invalidate_pull_manifest(published: PublishedSource, pair: tuple[str, str]) -> None:
    """Invalidate disposable metadata derived from a detected corrupt comparison.

    The private atomic writer publishes an invalid cache marker instead of deleting
    through an unchecked path. A later read recomputes it. Refusals are reported by the
    caller; a failed invalidation must not be presented as successful repair. An epoch
    beside the bank invalidates this slot and its older in-flight computations,
    even when the bank itself cannot be written. Epoch publication must succeed.
    """
    location = GitLocation.revision(
        RepositoryStoreTarget(published.git_dir, published.object_format), pair[1]
    )
    intent = {"left": pair[0], "right": pair[1], "base_policy": "merge_base"}
    key = comparison_cache_key(location, intent, store_tag(published.git_dir))
    assert key is not None
    # Invalidation must not depend on whether the current reader can adopt or even
    # inspect the slot. Evicting a colliding disposable entry is harmless.
    slot_error: OSError | PrivateStorageError | None = None
    try:
        write_private_file_atomic(published.home, _path(published, key), b"{}")
    except (OSError, PrivateStorageError) as error:
        slot_error = error
    try:
        # Advance even when the slot was cleared: a computation already in flight can
        # publish afterward. Its captured old epoch must remain a miss. This also
        # invalidates an untouched slot when only the bank is read-only.
        write_private_file_atomic(
            published.home, _epoch_path(published, key), secrets.token_hex(32).encode("ascii")
        )
    except (OSError, PrivateStorageError) as error:
        if slot_error is not None:
            raise error from slot_error
        raise


async def load_pull_manifest(
    published: PublishedSource, source: GitDiffSource, intent: dict[str, Any], key: tuple[str, ...]
) -> ResolvedManifest:
    """Reuse one matching manifest, or compute and heal it. Never fetch the network.

    Called inside the comparison cache's shared task, so concurrent page and
    deferred-file requests share a miss or repair. The inexpensive resolution
    prevents a disk entry from answering for objects this store no longer has.
    """
    resolved = await source.resolve(intent)
    try:
        epoch = await asyncio.to_thread(_current_epoch, published, key)
    except (OSError, RecordError, PrivateStorageError):
        epoch = None
    kept = None if epoch is None else await asyncio.to_thread(_read, published, key, epoch=epoch)
    if kept is not None and kept.resolved == resolved:
        return kept
    answer = ResolvedManifest(resolved, await source.manifest(resolved))
    try:
        if epoch is not None:
            # Capture before computing, never after: a concurrent invalidation must also
            # invalidate a manifest whose raw listing started before it.
            await asyncio.to_thread(_write, published, key, answer, epoch)
    except (OSError, PrivateStorageError):
        # Persistence is disposable. A read-only cache still serves the computed answer.
        log.debug("could not retain a pull-request manifest")
    return answer


async def prepare_pull_manifest(published: PublishedSource, record: PullRecord) -> None:
    """Prepare the record's manifest after fetch; a failure never loses its record."""
    comparison = record.comparison
    if comparison is None:
        return
    location = GitLocation.revision(
        RepositoryStoreTarget(published.git_dir, published.object_format), comparison.head
    )
    intent = {"left": comparison.base, "right": comparison.head, "base_policy": "merge_base"}
    key = comparison_cache_key(location, intent, store_tag(published.git_dir))
    assert key is not None
    try:
        await load_pull_manifest(published, GitDiffSource(location), intent, key)
    except (DiffSourceError, GitError):
        log.debug("could not prepare pull-request %s's manifest", record.number)
