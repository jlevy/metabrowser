"""A disposable bank of PR manifests beside a repository store, one per pull request.

The record's immutable endpoints are prepared after fetch, before its record is
published. A fresh server reads the manifest instead of running the costly raw
listing. Resolution still verifies that this store can answer for both commits.
Each pull request keeps the manifest of the last comparison read for it, with no index,
enumeration or LRU lock: another comparison of the same pull request replaces it and can
only cause a later cache miss. So the bank holds one manifest for each pull request ever
prepared in the store; clearing the cache leaves it, as it leaves the store. Only a
cached record's comparison is read, so the count is the records', each read is bounded
by `MAX_MANIFEST_RECORD_BYTES`, and the measurement below sizes the whole.

Measured 2026-11-17 on a reader's cache: 90 manifests in 9 stores, a median of 10.7 KB,
90th percentile 44 KB, and largest 68 KB, about 500 bytes a changed file; beside them,
one source's 64 records had a median of 33 KB. So a pull request's manifest adds about a
third of what its record already keeps. Sixteen direct-mapped slots, before, held 11 of
19 open pull requests' manifests on average, and each of the rest was listed again
(about 77 ms) whenever it was opened (mb-g8oe).
"""

from __future__ import annotations

import asyncio
import contextlib
import hashlib
import logging
import secrets
from threading import Lock
from typing import TYPE_CHECKING, Any, Final, Literal
from weakref import WeakKeyDictionary

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from metabrowser.builtin_plugins.diff.comparison_cache import ResolvedManifest
from metabrowser.builtin_plugins.diff.sidekick import (
    comparison_cache_key,
    shared_comparison_manifest,
)
from metabrowser.builtin_plugins.github.pull_record import MAX_PULL_RECORD_BYTES, PullRecord
from metabrowser.cache.atomic import RecordError, read_bytes_bounded
from metabrowser.cache.paths import store_directory
from metabrowser.diff.adapters.base import DiffSourceError
from metabrowser.diff.adapters.git import MANIFEST_LISTING, MAX_MANIFEST_FILES, GitDiffSource
from metabrowser.diff.format import FILE_DIFF_SCHEMA, FILE_DIFF_SCHEMA_VERSION, ChangeSetDocument
from metabrowser.git.process import (
    GIT_COMMON_ARGS,
    STORE_READ_POLICY,
    GitError,
    GitLocation,
    RepositoryStoreTarget,
)
from metabrowser.home import (
    PrivateStorageError,
    ensure_private_directory,
    private_directory_is_writable,
    write_private_file_atomic,
)
from metabrowser.http_caching import store_tag
from metabrowser.loading_cache import LoadingCache

if TYPE_CHECKING:
    from metabrowser.cache.acquire import PublishedSource

log = logging.getLogger(__name__)

# Cache admission uses the existing PR-record read bound; a larger result is still served
# in full.
MAX_MANIFEST_RECORD_BYTES: Final = MAX_PULL_RECORD_BYTES
# Epochs, direct-mapped by comparison. An epoch advances only when a comparison is found
# corrupt, so a collision costs one more listing after that, and these few files at the
# store's root are the ones v0.12 kept, which hold only random values.
EPOCH_SLOTS: Final = 16
_FLIGHTS: WeakKeyDictionary[
    asyncio.AbstractEventLoop, LoadingCache[tuple[str, ...], ResolvedManifest]
] = WeakKeyDictionary()
_FLIGHTS_LOCK = Lock()


class _ManifestRecord(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: Literal[3] = 3
    epoch: str = Field(pattern=r"^[0-9a-f]{64}$")
    identity: tuple[str, ...] = Field(min_length=8, max_length=8)
    digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    document: ChangeSetDocument


# What of a store read's process shapes a listing's output: Git's common options, and the
# configuration and attributes the store's Git is kept from. A store's own attributes
# are in its token, in *key*. The bounds and the timeout are not here: they refuse a
# listing, never change one.
_STORE_READ: Final = repr(
    (
        GIT_COMMON_ARGS,
        STORE_READ_POLICY.isolate_user_config,
        sorted((STORE_READ_POLICY.extra_env or {}).items()),
        STORE_READ_POLICY.attributes_from_empty_tree,
    )
)


def _identity(key: tuple[str, ...]) -> tuple[str, ...]:
    """What a kept manifest answers for: the document's schema, the listing, how the store
    is read, and *key*.

    Not the build, so a manifest outlives an upgrade and an edit of the source (mb-g8oe);
    a change to the schema, to the listing's options, or to the store read's isolation
    moves it, and so does raising `MANIFEST_READING`.
    """
    schema = f"{FILE_DIFF_SCHEMA}.{FILE_DIFF_SCHEMA_VERSION}"
    return (schema, MANIFEST_LISTING, _STORE_READ, *key)


def _directory(published: PublishedSource) -> str:
    return f"{store_directory(published.store_key)}/github-pull-manifests"


def _epoch_slot(key: tuple[str, ...]) -> int:
    digest = hashlib.sha256("\0".join(_identity(key)).encode()).digest()
    return int.from_bytes(digest[:8]) % EPOCH_SLOTS


def _epoch_path(published: PublishedSource, key: tuple[str, ...]) -> str:
    """Beside the bank, not in it, so an epoch moves even when the bank cannot be written;
    and the comparison's, not the pull request's, so invalidating a comparison reaches
    every pull request that keeps it."""
    slot = _epoch_slot(key)
    return f"{store_directory(published.store_key)}/github-pull-manifest-{slot:02d}.epoch"


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


def _path(published: PublishedSource, number: int) -> str:
    # Named so that no file of the sixteen slots v0.12 kept, `00.json` to `15.json`, is one.
    return f"{_directory(published)}/pull-{number}.json"


def _digest(document: ChangeSetDocument) -> str:
    return hashlib.sha256(document.model_dump_json(by_alias=True).encode()).hexdigest()


def _read(
    published: PublishedSource,
    number: int,
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
            _path(published, number),
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
    published: PublishedSource,
    number: int,
    key: tuple[str, ...],
    answer: ResolvedManifest,
    epoch: str,
) -> None:
    document = ChangeSetDocument(
        schema=FILE_DIFF_SCHEMA,
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
    write_private_file_atomic(published.home, _path(published, number), data)


def invalidate_pull_manifest(
    published: PublishedSource, number: int, pair: tuple[str, str]
) -> None:
    """Invalidate the manifests of *pair*, a comparison detected corrupt that pull request
    *number* read.

    The private atomic writer publishes an invalid cache marker instead of deleting
    through an unchecked path. A later read recomputes it. Refusals are reported by the
    caller; a failed invalidation must not be presented as successful repair. The
    comparison's epoch beside the bank invalidates every pull request's manifest of it,
    and older in-flight computations, even when the bank itself cannot be written. Epoch
    publication must succeed.
    """
    location = GitLocation.revision(
        RepositoryStoreTarget(published.git_dir, published.object_format), pair[1]
    )
    intent = {"left": pair[0], "right": pair[1], "base_policy": "merge_base"}
    key = comparison_cache_key(location, intent, store_tag(published.git_dir))
    assert key is not None
    # Invalidation must not depend on whether the current reader can adopt or even
    # inspect the manifest, whichever comparison it holds: it is disposable.
    slot_error: OSError | PrivateStorageError | None = None
    try:
        write_private_file_atomic(published.home, _path(published, number), b"{}")
    except (OSError, PrivateStorageError) as error:
        slot_error = error
    try:
        # Advance even when the manifest was cleared: a computation already in flight can
        # publish afterward. Its captured old epoch must remain a miss. This also
        # invalidates an untouched manifest when only the bank is read-only.
        write_private_file_atomic(
            published.home, _epoch_path(published, key), secrets.token_hex(32).encode("ascii")
        )
    except (OSError, PrivateStorageError) as error:
        if slot_error is not None:
            raise error from slot_error
        raise


async def load_pull_manifest(
    published: PublishedSource,
    number: int,
    source: GitDiffSource,
    intent: dict[str, Any],
    key: tuple[str, ...],
) -> ResolvedManifest:
    """Reuse one matching manifest, or compute and heal it. Never fetch the network.

    Preparation and readers join the active disk load. Only the read path keeps a
    ready result in the comparison's memory cache.
    """
    try:
        epoch = await asyncio.to_thread(_current_epoch, published, key)
    except (OSError, RecordError, PrivateStorageError):
        epoch = None
    loop = asyncio.get_running_loop()
    with _FLIGHTS_LOCK:
        flights = _FLIGHTS.get(loop)
        if flights is None:
            flights = _FLIGHTS[loop] = LoadingCache(max_values=0)
    return await flights.get(
        (str(number), *key, epoch or ""),
        lambda: _load(published, number, source, intent, key, epoch),
    )


async def _load(
    published: PublishedSource,
    number: int,
    source: GitDiffSource,
    intent: dict[str, Any],
    key: tuple[str, ...],
    epoch: str | None,
) -> ResolvedManifest:
    # Check the store before using a persisted result.
    resolved = await source.resolve(intent)
    kept = (
        None
        if epoch is None
        else await asyncio.to_thread(_read, published, number, key, epoch=epoch)
    )
    if kept is not None and kept.resolved == resolved:
        return kept
    answer = ResolvedManifest(resolved, await source.manifest(resolved))
    try:
        if epoch is not None:
            # Capture before computing, never after: a concurrent invalidation must also
            # invalidate a manifest whose raw listing started before it.
            await asyncio.to_thread(_write, published, number, key, answer, epoch)
    except (OSError, PrivateStorageError):
        # Persistence is disposable. A read-only cache still serves the computed answer.
        log.debug("could not retain a pull-request manifest")
    return answer


async def shared_pull_manifest(
    published: PublishedSource, number: int, base: str, head: str, *, retain_memory: bool = True
) -> ResolvedManifest:
    location = GitLocation.revision(
        RepositoryStoreTarget(published.git_dir, published.object_format), head
    )
    intent = {"left": base, "right": head, "base_policy": "merge_base"}
    key = comparison_cache_key(location, intent, store_tag(published.git_dir))
    assert key is not None

    async def load() -> ResolvedManifest:
        return await load_pull_manifest(published, number, GitDiffSource(location), intent, key)

    return await shared_comparison_manifest(key, load) if retain_memory else await load()


async def prepare_pull_manifest(published: PublishedSource, record: PullRecord) -> None:
    """Prepare the record's manifest after fetch; a failure never loses its record."""
    comparison = record.comparison
    if comparison is None:
        return
    try:
        await shared_pull_manifest(
            published, record.number, comparison.base, comparison.head, retain_memory=False
        )
    except (DiffSourceError, GitError):
        log.debug("could not prepare pull-request %s's manifest", record.number)
