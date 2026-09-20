"""Acquire a classified Git source into an isolated worktree-free store.

A ``file://`` URL is fetched through Git's pack transport into staging, then
published as an immutable store and a source alias. This module does not serve
content. The CLI acquires through ``--no-serve`` and ``--api /api/cache/…``;
https and ssh stay closed. A bare path never reaches here.
"""

from __future__ import annotations

import hashlib
import logging
import os
import secrets
import shutil
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Final, Literal, Self

from metabrowser.cache.atomic import publish_entry, read_record, write_record_atomic
from metabrowser.cache.identity import (
    ObjectFormat,
    cache_slug,
    repository_store_id,
    source_identity,
    store_key,
)
from metabrowser.cache.layout import open_cache, read_config, read_layout
from metabrowser.cache.locks import (
    CacheLock,
    LockBusyError,
    repository_store_lock,
    require_no_hierarchy_locks,
    source_alias_lock,
    staging_entry_lock,
    store_lease,
)
from metabrowser.cache.paths import (
    source_directory,
    source_record,
    staging_entry,
    store_directory,
    store_record,
)
from metabrowser.cache.records import (
    REPOSITORY_SOURCE_CONTRACT_ID,
    REPOSITORY_SOURCE_STATE_CONTRACT_ID,
    REPOSITORY_STORE_ALIAS_CONTRACT_ID,
    REPOSITORY_STORE_CONTRACT_ID,
    REPOSITORY_STORE_STATE_CONTRACT_ID,
    RepositorySource,
    RepositorySourceState,
    RepositoryStore,
    RepositoryStoreAlias,
    RepositoryStoreState,
    StoreAcquisition,
    StoreOperation,
)
from metabrowser.cache.urls import GitSource
from metabrowser.git.process import (
    ACQUISITION_POLICY,
    FETCH_POLICY,
    GitCommandError,
    GitOutputTooLargeError,
    GitProcessPolicy,
    repository_store_target,
    require_acquisition_git,
    run_git,
)
from metabrowser.git.wire import is_full_revision
from metabrowser.home import PrivateStorageError, SharedEntryPolicy, ensure_private_directory

log = logging.getLogger(__name__)

_PROTOCOL: Final[tuple[str, ...]] = (
    "-c",
    "protocol.allow=never",
    "-c",
    "protocol.file.allow=always",
)
_STORE_CONFIG: Final[tuple[tuple[str, str], ...]] = (
    ("maintenance.auto", "false"),
    ("gc.auto", "0"),
    ("fetch.recurseSubmodules", "false"),
    ("transfer.bundleURI", "false"),
    ("core.hooksPath", "/dev/null"),
)
_BLOB_MODES: Final[frozenset[bytes]] = frozenset({b"100644", b"100755", b"120000"})
_ENTRY_ATTEMPTS: Final = 8


class AcquisitionError(Exception):
    """Acquisition stopped before a validated staging store existed."""


class RemoteUnavailableError(AcquisitionError):
    """``ls-remote`` could not observe HEAD at the classified source."""


class FetchFailedError(AcquisitionError):
    """The blobless fetch into staging failed after HEAD was observed."""


class ValidationFailedError(AcquisitionError):
    """The fetched objects, HEAD, or object format did not validate."""


class AliasConflictError(AcquisitionError):
    """The source already names a different store; the existing alias was left in place."""


@dataclass(slots=True)
class StagingAcquisition:
    """A validated worktree-free Git database still under its staging lock."""

    home: Path
    entry: str
    git_dir: Path
    source: GitSource
    source_id: str
    object_format: ObjectFormat
    strategy: Literal["blobless", "full"]
    configuration_digest: str
    default_remote_ref: str | None
    default_revision: str
    git_version: str
    _lock: CacheLock | None = field(default=None, repr=False)

    def abandon(self) -> None:
        """Delete the staging entry and drop its liveness lock."""
        _delete_staging(self.home, self.entry)
        lock, self._lock = self._lock, None
        if lock is not None and lock.held:
            lock.remove_lock_file()

    def __enter__(self) -> Self:
        return self

    def __exit__(self, *_exc: object) -> None:
        self.abandon()


def _delete_staging(home: Path, entry: str) -> None:
    path = home / staging_entry(entry)
    if path.exists():
        shutil.rmtree(path)


def _claim_staging(home: Path) -> tuple[str, CacheLock]:
    for _attempt in range(_ENTRY_ATTEMPTS):
        entry = "acq-" + secrets.token_hex(6)
        try:
            lock = staging_entry_lock(home, entry)
        except LockBusyError:
            continue
        ensure_private_directory(home, staging_entry(entry))
        return entry, lock
    raise AcquisitionError("could not claim a staging entry")


async def _run(
    args: list[str],
    *,
    cwd: Path | None = None,
    git_dir: Path | None = None,
    policy: GitProcessPolicy = ACQUISITION_POLICY,
    stdin: bytes | None = None,
) -> bytes:
    require_no_hierarchy_locks("git")
    if git_dir is not None:
        return await run_git(
            args,
            target=repository_store_target(git_dir=git_dir),
            policy=policy,
            stdin=stdin,
        )
    if cwd is None:
        raise TypeError("cwd or git_dir is required")
    return await run_git(args, cwd=cwd, policy=policy, stdin=stdin)


def _parse_symref_head(stdout: bytes) -> tuple[str | None, str]:
    # The ``HEAD`` pattern also matches any ref whose last component is HEAD, such as
    # a clone's ``refs/remotes/origin/HEAD``. Only the ref named exactly HEAD counts.
    ref: str | None = None
    oid: str | None = None
    for line in stdout.decode("ascii", errors="replace").splitlines():
        payload, _, name = line.partition("\t")
        if name != "HEAD":
            continue
        if payload.startswith("ref:"):
            ref = payload.removeprefix("ref:").strip()
        else:
            oid = payload.strip()
    if oid is None or not is_full_revision(oid):
        raise RemoteUnavailableError("the source did not advertise HEAD")
    return ref, oid


def _remote_tracking_ref(head_ref: str | None) -> str | None:
    if head_ref is None or not head_ref.startswith("refs/heads/"):
        return None
    return "refs/remotes/origin/" + head_ref.removeprefix("refs/heads/")


async def _require_ref_at(git_dir: Path, ref: str, revision: str) -> None:
    """Refuse a record whose branch is not the pinned commit in the fetched store.

    The ref name came from an untrusted origin. ``show-ref --verify`` takes an exact
    ref path, so the name is never parsed as revision syntax. *revision* is already
    known to be a commit, so equal object IDs mean the ref resolves to that commit.
    """
    try:
        shown = await _run(["show-ref", "--verify", "--", ref], git_dir=git_dir)
    except GitCommandError as exc:
        raise ValidationFailedError("the default branch was not fetched") from exc
    if shown.split(b" ", 1)[0].decode("ascii", errors="replace") != revision:
        raise ValidationFailedError("the default branch does not resolve to the observed HEAD")


async def _configuration_digest(git_dir: Path) -> str:
    raw = await _run(["config", "--file", str(git_dir / "config"), "--list", "-z"], git_dir=git_dir)
    return "sha256:" + hashlib.sha256(raw).hexdigest()


async def _missing_objects(git_dir: Path, *scope: str) -> bool:
    # ``--quiet`` drops every object that is present, so the output is only the
    # ``?<oid>`` lines and its size does not grow with the objects that were fetched.
    listing = await _run(
        ["rev-list", "--quiet", "--objects", "--missing=print", *scope], git_dir=git_dir
    )
    return any(line.startswith(b"?") for line in listing.splitlines())


async def _filter_honored(git_dir: Path, revision: str) -> bool:
    """Return True when the fetch left objects out, so the store is blobless.

    ``blob:none`` on a first fetch omits every blob, so an origin that honored it
    shows a missing blob in the pinned commit's own tree. That answer costs one
    tree, whatever the history holds, and it is the usual one.

    A complete tip proves nothing about history: an origin can tag the tip's blobs,
    and a wanted object is sent despite the filter. Recording ``full`` claims every
    reachable object, so that claim alone pays for the walk over history, after a
    fetch that already transferred and indexed all of it. Either listing holds only
    missing objects, so overflowing the output cap means many are missing.
    """
    try:
        return await _missing_objects(git_dir, "--no-walk", revision) or await _missing_objects(
            git_dir, revision
        )
    except GitOutputTooLargeError:
        return True


async def _tree_blob_oids(git_dir: Path, revision: str) -> tuple[str, ...]:
    raw = await _run(["ls-tree", "-r", "-z", "--full-tree", revision], git_dir=git_dir)
    oids: list[str] = []
    seen: set[str] = set()
    for record in raw.split(b"\0"):
        if not record:
            continue
        meta, _, _path = record.partition(b"\t")
        parts = meta.split(b" ")
        if len(parts) != 3:
            continue
        mode, kind, oid_raw = parts
        if kind != b"blob" or mode not in _BLOB_MODES:
            continue
        oid = oid_raw.decode("ascii")
        if oid not in seen:
            seen.add(oid)
            oids.append(oid)
    return tuple(oids)


async def _prefetch_default_tree(git_dir: Path, revision: str) -> None:
    """Fetch HEAD tree blobs by object ID. A transport failure defers them."""

    oids = await _tree_blob_oids(git_dir, revision)
    if not oids:
        return
    try:
        await _run(
            [
                *_PROTOCOL,
                "-c",
                "fetch.negotiationAlgorithm=noop",
                "-c",
                "http.lowSpeedLimit=1000",
                "-c",
                "http.lowSpeedTime=30",
                "fetch",
                "--no-tags",
                "--no-write-fetch-head",
                "--recurse-submodules=no",
                "--filter=blob:none",
                "--stdin",
                "origin",
            ],
            git_dir=git_dir,
            policy=FETCH_POLICY,
            stdin=("\n".join(oids) + "\n").encode("ascii"),
        )
    except GitCommandError:
        return


async def acquire_into_staging(source: GitSource, *, home: Path) -> StagingAcquisition:
    """Fetch *source* into a new staging store and validate it.

    Only ``file://`` sources are acquired here. The returned object holds the
    staging liveness lock until :meth:`StagingAcquisition.abandon`.
    """
    if source.transport != "file":
        raise AcquisitionError(
            f"{source.transport} Git sources are not acquired yet ({source.normalized})"
        )
    version = require_acquisition_git()
    git_version = f"{version[0]}.{version[1]}.{version[2]}"
    cache = open_cache(home)
    home = cache.home
    entry, lock = _claim_staging(home)
    # Commands that run before the store exists start in the claimed staging entry, not
    # the home. Discovery stops at the working directory, and this one is private, new,
    # and never a repository, so neither the home nor anything enclosing it lends config.
    staging = home / staging_entry(entry)
    git_dir = staging / "repository.git"
    try:
        try:
            observed = await _run(
                [*_PROTOCOL, "ls-remote", "--symref", "--", source.normalized, "HEAD"],
                cwd=staging,
            )
        except GitCommandError as exc:
            raise RemoteUnavailableError("the source did not advertise HEAD") from exc
        head_ref, revision = _parse_symref_head(observed)
        advertised_format = "sha256" if len(revision) == 64 else "sha1"
        # No ``--ref-format=files``: the flag arrived in Git 2.45 and the admitted
        # floor is 2.43. The isolated environment drops GIT_DEFAULT_REF_FORMAT and
        # reads no user configuration, so nothing ambient selects reftable.
        await _run(
            [
                "init",
                "--bare",
                "--template=",
                f"--object-format={advertised_format}",
                "-q",
                str(git_dir),
            ],
            cwd=staging,
        )
        for key, value in _STORE_CONFIG:
            await _run(["config", key, value], git_dir=git_dir)
        await _run(["config", "remote.origin.url", source.normalized], git_dir=git_dir)
        try:
            await _run(
                [
                    *_PROTOCOL,
                    "fetch",
                    "--no-write-fetch-head",
                    "--filter=blob:none",
                    "origin",
                    "+refs/heads/*:refs/remotes/origin/*",
                    "+refs/tags/*:refs/tags/*",
                ],
                git_dir=git_dir,
            )
        except GitCommandError as exc:
            raise FetchFailedError("the blobless fetch into staging failed") from exc
        try:
            kind = (await _run(["cat-file", "-t", revision], git_dir=git_dir)).strip()
            object_format_raw = (
                await _run(["rev-parse", "--show-object-format"], git_dir=git_dir)
            ).strip()
        except GitCommandError as exc:
            raise ValidationFailedError("the observed HEAD did not validate") from exc
        if kind != b"commit":
            raise ValidationFailedError("the observed HEAD is not a commit")
        default_remote_ref = _remote_tracking_ref(head_ref)
        if default_remote_ref is not None:
            await _require_ref_at(git_dir, default_remote_ref, revision)
        object_format_name = object_format_raw.decode("ascii")
        if object_format_name not in {"sha1", "sha256"}:
            raise ValidationFailedError("unsupported object format")
        object_format: ObjectFormat = "sha1" if object_format_name == "sha1" else "sha256"
        strategy: Literal["blobless", "full"] = (
            "blobless" if await _filter_honored(git_dir, revision) else "full"
        )
        if strategy == "blobless":
            await _prefetch_default_tree(git_dir, revision)
        digest = await _configuration_digest(git_dir)
        return StagingAcquisition(
            home=home,
            entry=entry,
            git_dir=git_dir,
            source=source,
            source_id=source_identity(source.transport, source.normalized),
            object_format=object_format,
            strategy=strategy,
            configuration_digest=digest,
            default_remote_ref=default_remote_ref,
            default_revision=revision,
            git_version=git_version,
            _lock=lock,
        )
    except BaseException:
        _delete_staging(home, entry)
        if lock.held:
            lock.remove_lock_file()
        raise


@dataclass(frozen=True, slots=True)
class PublishedSource:
    """A published source alias naming one immutable repository store."""

    home: Path
    slug: str
    store_key: str
    git_dir: Path
    source: GitSource
    source_id: str
    store_id: str
    object_format: ObjectFormat
    strategy: Literal["blobless", "full"]
    default_remote_ref: str
    default_revision: str


def _canonical_now() -> str:
    return datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def _touch_last_opened(published: PublishedSource) -> None:
    """Best-effort recency. A failed write must not fail the open."""

    try:
        with source_alias_lock(published.home, published.slug, blocking=False):
            write_record_atomic(
                published.home,
                source_record(published.slug, "state.yml"),
                RepositorySourceState(last_opened_at=_canonical_now()),
                REPOSITORY_SOURCE_STATE_CONTRACT_ID,
            )
    except (LockBusyError, PrivateStorageError, OSError):
        log.debug("dropped last_opened_at; the cache hit still succeeded", exc_info=True)


def _source_id_for_slug(
    home: Path, slug: str, *, shared: SharedEntryPolicy = "repair"
) -> str | None:
    try:
        record = read_record(
            home, source_record(slug, "source.yml"), REPOSITORY_SOURCE_CONTRACT_ID, shared=shared
        )
    except FileNotFoundError:
        return None
    if not isinstance(record, RepositorySource):
        raise ValidationFailedError("source.yml did not validate")
    return record.id


def _claim_source_slug(home: Path, source: GitSource, source_id: str) -> tuple[str, CacheLock]:
    while True:
        slug = cache_slug(
            source.transport,
            source.normalized,
            source_id,
            slug_owner=lambda candidate: _source_id_for_slug(home, candidate),
        )
        lock = source_alias_lock(home, slug)
        owner = _source_id_for_slug(home, slug)
        if owner is None or owner == source_id:
            return slug, lock
        lock.release()


def _write_store_records(staged: StagingAcquisition, store_id: str, at: str) -> None:
    prefix = staging_entry(staged.entry)
    write_record_atomic(
        staged.home,
        f"{prefix}/store.yml",
        RepositoryStore(
            id=store_id,
            created_at=at,
            acquisition=StoreAcquisition(
                strategy=staged.strategy,
                git_version=staged.git_version,
                object_format=staged.object_format,
            ),
        ),
        REPOSITORY_STORE_CONTRACT_ID,
    )
    write_record_atomic(
        staged.home,
        f"{prefix}/state.yml",
        RepositoryStoreState(
            configuration_digest=staged.configuration_digest,
            default_remote_ref=staged.default_remote_ref,
            default_revision=staged.default_revision,
            object_state="complete" if staged.strategy == "full" else "converging",
            last_fetch_at=at,
            last_operation=StoreOperation(kind="acquire", outcome="succeeded", at=at),
        ),
        REPOSITORY_STORE_STATE_CONTRACT_ID,
    )


def _require_same_store(home: Path, key: str, store_id: str) -> RepositoryStore:
    record = read_record(home, store_record(key, "store.yml"), REPOSITORY_STORE_CONTRACT_ID)
    if not isinstance(record, RepositoryStore) or record.id != store_id:
        raise ValidationFailedError("the published store does not match this source")
    return record


def _publish_or_reuse_store(staged: StagingAcquisition, key: str, store_id: str) -> None:
    home = staged.home
    target = store_directory(key)
    with repository_store_lock(home, key) as store_lock:
        if os.path.lexists(home / target):
            _require_same_store(home, key, store_id)
            return
        try:
            publish_entry(home, staging_entry(staged.entry), target, owner=store_lock)
        except FileExistsError:
            _require_same_store(home, key, store_id)


def _publish_source_directory(
    home: Path,
    slug: str,
    source: GitSource,
    source_id: str,
    store_id: str,
    at: str,
    alias_lock: CacheLock,
) -> None:
    entry, liveness = _claim_staging(home)
    staged_rel = staging_entry(entry)
    try:
        write_record_atomic(
            home,
            f"{staged_rel}/source.yml",
            RepositorySource(
                id=source_id,
                slug=slug,
                display_url=source.normalized,
                clone_url=source.normalized,
                transport=source.transport,
                created_at=at,
            ),
            REPOSITORY_SOURCE_CONTRACT_ID,
        )
        write_record_atomic(
            home,
            f"{staged_rel}/store-alias.yml",
            RepositoryStoreAlias(
                source_id=source_id,
                store_id=store_id,
                generation=1,
                updated_at=at,
            ),
            REPOSITORY_STORE_ALIAS_CONTRACT_ID,
        )
        publish_entry(home, staged_rel, source_directory(slug), owner=alias_lock)
    except BaseException:
        _delete_staging(home, entry)
        raise
    finally:
        if liveness.held:
            liveness.remove_lock_file()


def _published(
    home: Path,
    slug: str,
    key: str,
    source: GitSource,
    source_id: str,
    store_id: str,
    object_format: ObjectFormat,
    strategy: Literal["blobless", "full"],
    default_remote_ref: str,
    default_revision: str,
) -> PublishedSource:
    return PublishedSource(
        home=home,
        slug=slug,
        store_key=key,
        git_dir=home / store_directory(key) / "repository.git",
        source=source,
        source_id=source_id,
        store_id=store_id,
        object_format=object_format,
        strategy=strategy,
        default_remote_ref=default_remote_ref,
        default_revision=default_revision,
    )


def _attach_or_conflict(
    home: Path,
    source: GitSource,
    source_id: str,
    store_id: str,
    key: str,
    at: str,
) -> PublishedSource:
    slug, alias_lock = _claim_source_slug(home, source, source_id)
    try:
        with alias_lock, repository_store_lock(home, key):
            if not os.path.lexists(home / store_directory(key)):
                raise ValidationFailedError("the store vanished before its alias was published")
            # A concurrent acquisition may have won publication with a different HEAD.
            # Report the selected store, never metadata from the discarded staging entry.
            store = _require_same_store(home, key, store_id)
            state = read_record(
                home, store_record(key, "state.yml"), REPOSITORY_STORE_STATE_CONTRACT_ID
            )
            if (
                not isinstance(state, RepositoryStoreState)
                or state.default_remote_ref is None
                or state.default_revision is None
            ):
                raise ValidationFailedError("the published store has no default revision")
            object_format = store.acquisition.object_format
            strategy = store.acquisition.strategy
            default_remote_ref = state.default_remote_ref
            default_revision = state.default_revision
            source_rel = source_directory(slug)
            if os.path.lexists(home / source_rel):
                try:
                    alias = read_record(
                        home,
                        source_record(slug, "store-alias.yml"),
                        REPOSITORY_STORE_ALIAS_CONTRACT_ID,
                    )
                except FileNotFoundError:
                    write_record_atomic(
                        home,
                        source_record(slug, "store-alias.yml"),
                        RepositoryStoreAlias(
                            source_id=source_id,
                            store_id=store_id,
                            generation=1,
                            updated_at=at,
                        ),
                        REPOSITORY_STORE_ALIAS_CONTRACT_ID,
                        replace=False,
                    )
                else:
                    if not isinstance(alias, RepositoryStoreAlias):
                        raise ValidationFailedError("store-alias.yml did not validate")
                    if alias.store_id != store_id:
                        raise AliasConflictError("this source already names a different store")
                return _published(
                    home,
                    slug,
                    key,
                    source,
                    source_id,
                    store_id,
                    object_format,
                    strategy,
                    default_remote_ref,
                    default_revision,
                )
            _publish_source_directory(home, slug, source, source_id, store_id, at, alias_lock)
            return _published(
                home,
                slug,
                key,
                source,
                source_id,
                store_id,
                object_format,
                strategy,
                default_remote_ref,
                default_revision,
            )
    finally:
        if alias_lock.held:
            alias_lock.release()


def _find_published(source: GitSource, home: Path) -> PublishedSource | None:
    source_id = source_identity(source.transport, source.normalized)
    slug = cache_slug(
        source.transport,
        source.normalized,
        source_id,
        slug_owner=lambda candidate: _source_id_for_slug(home, candidate, shared="keep"),
    )
    if _source_id_for_slug(home, slug, shared="keep") != source_id:
        return None
    try:
        alias = read_record(
            home,
            source_record(slug, "store-alias.yml"),
            REPOSITORY_STORE_ALIAS_CONTRACT_ID,
            shared="keep",
        )
    except FileNotFoundError:
        return None
    if not isinstance(alias, RepositoryStoreAlias):
        raise ValidationFailedError("store-alias.yml did not validate")
    expected = {
        repository_store_id(source_id, "sha1"),
        repository_store_id(source_id, "sha256"),
    }
    if alias.store_id not in expected:
        raise AliasConflictError("this source already names a different store")
    key = store_key(alias.store_id)
    try:
        store = read_record(
            home, store_record(key, "store.yml"), REPOSITORY_STORE_CONTRACT_ID, shared="keep"
        )
        state = read_record(
            home, store_record(key, "state.yml"), REPOSITORY_STORE_STATE_CONTRACT_ID, shared="keep"
        )
    except FileNotFoundError as exc:
        raise ValidationFailedError("the aliased store is missing") from exc
    if not isinstance(store, RepositoryStore) or not isinstance(state, RepositoryStoreState):
        raise ValidationFailedError("the published store did not validate")
    if state.default_remote_ref is None or state.default_revision is None:
        raise ValidationFailedError("the published store has no default revision")
    return _published(
        home,
        slug,
        key,
        source,
        source_id,
        alias.store_id,
        store.acquisition.object_format,
        store.acquisition.strategy,
        state.default_remote_ref,
        state.default_revision,
    )


def publish_from_staging(staged: StagingAcquisition) -> PublishedSource:
    """Publish *staged* as an immutable store and a source alias, then drop staging."""

    if staged.default_remote_ref is None:
        staged.abandon()
        raise ValidationFailedError("the source HEAD is not a branch")
    home = staged.home
    store_id = repository_store_id(staged.source_id, staged.object_format)
    key = store_key(store_id)
    at = _canonical_now()
    lease: CacheLock | None = None
    try:
        _write_store_records(staged, store_id, at)
        lease = store_lease(home, key)
        _publish_or_reuse_store(staged, key, store_id)
        staged.abandon()
        return _attach_or_conflict(
            home,
            staged.source,
            staged.source_id,
            store_id,
            key,
            at,
        )
    except BaseException:
        if staged._lock is not None and staged._lock.held:
            staged.abandon()
        raise
    finally:
        if lease is not None and lease.held:
            lease.release()


async def acquire_file_source(source: GitSource, *, home: Path) -> PublishedSource:
    """Return a published ``file://`` source, fetching only on a cache miss.

    A hit inspects an existing home without fetching or opening the cache, so it
    does not require the acquisition Git floor or owner-write on the home. It may
    try to record ``last_opened_at``; a failed write is dropped and the hit still
    returns. A miss checks the Git floor before ``open_cache``, so a below-floor
    refuse does not create the application home or complete an empty directory
    into an ``f01`` skeleton. A miss that is allowed to fetch then opens the
    cache (sweep, reclaim) and fetches. A future layout is refused before any
    write.
    """

    if source.transport != "file":
        raise AcquisitionError(
            f"{source.transport} Git sources are not acquired yet ({source.normalized})"
        )
    if home.exists():
        try:
            layout = read_layout(home, shared="keep")
            read_config(home, shared="keep")
        except PrivateStorageError:
            layout = None
        if layout is not None:
            found = _find_published(source, home)
            if found is not None:
                _touch_last_opened(found)
                return found
        require_acquisition_git()
        cache = open_cache(home)
        home = cache.home
        found = _find_published(source, home)
        if found is not None:
            _touch_last_opened(found)
            return found
    published = publish_from_staging(await acquire_into_staging(source, home=home))
    _touch_last_opened(published)
    return published


__all__ = [
    "AcquisitionError",
    "AliasConflictError",
    "FetchFailedError",
    "PublishedSource",
    "RemoteUnavailableError",
    "StagingAcquisition",
    "ValidationFailedError",
    "acquire_file_source",
    "acquire_into_staging",
    "publish_from_staging",
]
