"""A disposable bank of PR manifests beside a repository store, one per pull request.

The record's immutable endpoints are prepared after fetch, before its record is
published. A fresh server reads the manifest instead of running the costly raw
listing. Resolution still verifies that this store can answer for both commits.
Each pull request keeps the manifest of the last comparison read for it, with no index,
enumeration or LRU lock: another comparison of the same pull request replaces it and can
only cause a later cache miss. So the bank holds one manifest for each pull request ever
prepared in the store; clearing the cache leaves it, as it leaves the store. Only a
cached record's comparison is kept, so the count is the records', each read is bounded
by `MAX_MANIFEST_RECORD_BYTES`, and the measurement below sizes the whole.

A native stack keeps one too, beside its members', by the same rules
(:func:`load_stack_manifest`): its combined comparison restricted to the files its layers
change (:mod:`.pull_stack`), named ``stack-<n>.json`` so it never shares a file with a
pull request of the same number, and with the stack's digest of its members in its key, so
it never answers for the unrestricted comparison of the same two commits. A stack's also
says whether its size has been asked to an answer (``size_settled``), so that a process
that finds it kept runs no Git to ask again.

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
from collections.abc import Awaitable, Callable
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
from metabrowser.diff.format import (
    FILE_DIFF_SCHEMA,
    FILE_DIFF_SCHEMA_VERSION,
    ChangeSetDocument,
    ChangeSetManifest,
    ResolvedComparison,
)
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

# What a kept manifest is of: a pull request's comparison, or a native stack's combined one.
type KeptKind = Literal["pull", "stack"]

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
    # A pull request's comparison is named by eight items; a stack's has a ninth, its
    # restriction and members' digest (`stack_scope` in pull_stack.py).
    identity: tuple[str, ...] = Field(min_length=8, max_length=9)
    digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    document: ChangeSetDocument
    # A stack's alone: whether its comparison's size has been asked to an answer, a size,
    # a reason there is none, or that it is not one that is measured, so that no later
    # process asks again (`settle_stack_size`; :mod:`.pull_stack` says what asks). False on
    # a manifest kept before the mark existed, which is asked once.
    size_settled: bool = False


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


def _path(published: PublishedSource, number: int, kind: KeptKind = "pull") -> str:
    # Named so that no file of the sixteen slots v0.12 kept, `00.json` to `15.json`, is one,
    # and so that a stack's is never a pull request's of the same number.
    return f"{_directory(published)}/{kind}-{number}.json"


def _digest(document: ChangeSetDocument) -> str:
    return hashlib.sha256(document.model_dump_json(by_alias=True).encode()).hexdigest()


def _read(
    published: PublishedSource,
    number: int,
    key: tuple[str, ...],
    *,
    epoch: str | None = None,
    kind: KeptKind = "pull",
) -> ResolvedManifest | None:
    record = _read_record(published, number, key, epoch=epoch, kind=kind)
    if record is None:
        return None
    return ResolvedManifest(record.document.resolved, record.document.manifest)


def _read_record(
    published: PublishedSource,
    number: int,
    key: tuple[str, ...],
    *,
    epoch: str | None = None,
    kind: KeptKind = "pull",
) -> _ManifestRecord | None:
    try:
        if not private_directory_is_writable(published.home, _directory(published)):
            return None
        if epoch is None:
            epoch = _epoch(published, key)
        data = read_bytes_bounded(
            published.home,
            _path(published, number, kind),
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
    return record


def _write(
    published: PublishedSource,
    number: int,
    key: tuple[str, ...],
    answer: ResolvedManifest,
    epoch: str,
    kind: KeptKind = "pull",
    *,
    size_settled: bool = False,
) -> None:
    document = ChangeSetDocument(
        schema=FILE_DIFF_SCHEMA,
        schema_version=FILE_DIFF_SCHEMA_VERSION,
        resolved=answer.resolved,
        manifest=answer.manifest,
        patches={},
    )
    record = _ManifestRecord(
        epoch=epoch,
        identity=_identity(key),
        digest=_digest(document),
        document=document,
        size_settled=size_settled,
    )
    data = record.model_dump_json(by_alias=True).encode()
    if len(data) > MAX_MANIFEST_RECORD_BYTES:
        return
    ensure_private_directory(published.home, _directory(published))
    write_private_file_atomic(published.home, _path(published, number, kind), data)


def stack_size_settled(published: PublishedSource, number: int, key: tuple[str, ...]) -> bool:
    """Whether stack *number*'s kept manifest of the comparison *key* names says its size has
    been asked to an answer (:func:`settle_stack_size`). Blocking and bounded; False where
    no such manifest is kept."""

    record = _read_record(published, number, key, kind="stack")
    return record is not None and record.size_settled


def settle_stack_size(published: PublishedSource, number: int, key: tuple[str, ...]) -> None:
    """Mark stack *number*'s kept manifest of the comparison *key* names as one whose size
    has been asked to an answer, so a later process runs no Git for it. Blocking.

    The manifest kept is written again as it is, under the epoch it was read at, so one
    invalidated meanwhile stays a miss. Disposable: where none is kept, or the bank cannot
    be written, nothing is marked and the size is asked again.
    """

    record = _read_record(published, number, key, kind="stack")
    if record is None or record.size_settled:
        return
    answer = ResolvedManifest(record.document.resolved, record.document.manifest)
    try:
        _write(published, number, key, answer, record.epoch, "stack", size_settled=True)
    except (OSError, PrivateStorageError):
        log.debug("could not mark a stack manifest's size as settled")


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
    _invalidate(published, number, key, "pull")


def invalidate_stack_manifest(
    published: PublishedSource, number: int, key: tuple[str, ...]
) -> None:
    """Invalidate stack *number*'s kept manifest of the comparison *key* names, a comparison
    detected corrupt, as :func:`invalidate_pull_manifest` does a pull request's."""

    _invalidate(published, number, key, "stack")


def _invalidate(
    published: PublishedSource, number: int, key: tuple[str, ...], kind: KeptKind
) -> None:
    # Invalidation must not depend on whether the current reader can adopt or even
    # inspect the manifest, whichever comparison it holds: it is disposable.
    slot_error: OSError | PrivateStorageError | None = None
    try:
        write_private_file_atomic(published.home, _path(published, number, kind), b"{}")
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
    return await _kept_load(published, number, "pull", source, intent, key, source.manifest)


async def load_stack_manifest(
    published: PublishedSource,
    number: int,
    source: GitDiffSource,
    intent: dict[str, Any],
    key: tuple[str, ...],
    compute: Callable[[ResolvedComparison], Awaitable[ChangeSetManifest]],
) -> ResolvedManifest:
    """Stack *number*'s kept manifest of the comparison *key* names, or *compute* it and
    keep it. *key* names the stack's digest of its members, so a stack's manifest is never
    another comparison's. Never fetches."""

    return await _kept_load(published, number, "stack", source, intent, key, compute)


async def _kept_load(
    published: PublishedSource,
    number: int,
    kind: KeptKind,
    source: GitDiffSource,
    intent: dict[str, Any],
    key: tuple[str, ...],
    compute: Callable[[ResolvedComparison], Awaitable[ChangeSetManifest]],
) -> ResolvedManifest:
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
        (f"{kind}-{number}", *key, epoch or ""),
        lambda: _load(published, number, kind, source, intent, key, epoch, compute),
    )


async def _load(
    published: PublishedSource,
    number: int,
    kind: KeptKind,
    source: GitDiffSource,
    intent: dict[str, Any],
    key: tuple[str, ...],
    epoch: str | None,
    compute: Callable[[ResolvedComparison], Awaitable[ChangeSetManifest]],
) -> ResolvedManifest:
    # Check the store before using a persisted result.
    resolved = await source.resolve(intent)
    kept = (
        None
        if epoch is None
        else await asyncio.to_thread(_read, published, number, key, epoch=epoch, kind=kind)
    )
    if kept is not None and kept.resolved == resolved:
        return kept
    answer = ResolvedManifest(resolved, await compute(resolved))
    try:
        if epoch is not None:
            # Capture before computing, never after: a concurrent invalidation must also
            # invalidate a manifest whose raw listing started before it.
            await asyncio.to_thread(_write, published, number, key, answer, epoch, kind)
    except (OSError, PrivateStorageError):
        # Persistence is disposable. A read-only cache still serves the computed answer.
        log.debug("could not retain a %s manifest", kind)
    return answer


def kept_pull_manifest(
    published: PublishedSource, number: int, base: str, head: str
) -> ResolvedManifest | None:
    """Pull request *number*'s kept manifest of *base*..*head*, read with no Git, or ``None``
    when none is kept for that comparison. Blocking and bounded.

    The kept file names the comparison it answers (its identity holds the store, both
    commits, and the base policy), so a stack reads its members' changed paths from it
    without resolving them again: a store that cannot answer for a member's commits still
    names the paths its comparison listed when it could.
    """

    location = GitLocation.revision(
        RepositoryStoreTarget(published.git_dir, published.object_format), head
    )
    intent = {"left": base, "right": head, "base_policy": "merge_base"}
    key = comparison_cache_key(location, intent, store_tag(published.git_dir))
    assert key is not None
    return _read(published, number, key)


async def shared_pull_manifest(
    published: PublishedSource,
    number: int,
    base: str,
    head: str,
    *,
    retain_memory: bool = True,
) -> ResolvedManifest:
    """The comparison *base*..*head*'s manifest, shared in memory with every reader of it.

    The pull request's kept manifest answers it and is replaced by it, so it is for the
    record's own comparison alone.
    """
    location = GitLocation.revision(
        RepositoryStoreTarget(published.git_dir, published.object_format), head
    )
    intent = {"left": base, "right": head, "base_policy": "merge_base"}
    key = comparison_cache_key(location, intent, store_tag(published.git_dir))
    assert key is not None

    async def load() -> ResolvedManifest:
        source = GitDiffSource(location)
        return await load_pull_manifest(published, number, source, intent, key)

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
