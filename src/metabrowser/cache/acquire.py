"""Acquire a classified Git source into an isolated worktree-free store.

A ``file://`` or ``https://`` URL is fetched into staging, every object and not a
partial clone, then published as a complete store and a source alias. Nothing later
removes objects from a store. This module does not serve content. The CLI acquires
through ``--no-serve``, ``--api``, and ``--show``; ssh stays closed. A bare path never
reaches here. Every command against the origin gets :func:`remote_git_args`: the
protocol allowlist, the measured stall bound, and a provider's credential helper.
"""

from __future__ import annotations

import asyncio
import contextlib
import functools
import logging
import os
import secrets
import shutil
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Final, Self

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
    LockOrder,
    lock_order,
    repository_store_lock,
    require_no_hierarchy_locks,
    run_lock_section,
    source_alias_lock,
    staging_entry_lock,
)
from metabrowser.cache.paths import (
    source_directory,
    source_record,
    staging_entry,
    store_directory,
    store_record,
)
from metabrowser.cache.providers import check_first_clone
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
from metabrowser.cache.remote import (
    REMOTE_PROBE_TIMEOUT_S,
    RemoteFailureState,
    classify_remote_failure,
    describe_remote_failure,
    remote_git_args,
)
from metabrowser.cache.urls import GitSource
from metabrowser.git.process import (
    ACQUISITION_POLICY,
    GitCommandError,
    GitTimeoutError,
    repository_store_target,
    require_acquisition_git,
    run_git,
)
from metabrowser.git.wire import is_full_revision
from metabrowser.home import PrivateStorageError, SharedEntryPolicy, ensure_private_directory

log = logging.getLogger(__name__)

_ACQUIRED_TRANSPORTS: Final[frozenset[str]] = frozenset({"file", "https"})
_STORE_CONFIG: Final[tuple[tuple[str, str], ...]] = (
    ("maintenance.auto", "false"),
    ("gc.auto", "0"),
    ("fetch.recurseSubmodules", "false"),
    ("transfer.bundleURI", "false"),
    ("core.hooksPath", "/dev/null"),
)
_ENTRY_ATTEMPTS: Final = 8


class AcquisitionError(Exception):
    """Acquisition stopped before a validated staging store existed."""


class RemoteUnavailableError(AcquisitionError):
    """``ls-remote`` could not observe HEAD at the classified source."""


class FetchFailedError(AcquisitionError):
    """The fetch into staging failed after HEAD was observed."""


class ValidationFailedError(AcquisitionError):
    """The fetched objects, HEAD, or object format did not validate."""


class AliasConflictError(AcquisitionError):
    """The source already names a different store; the existing alias was left in place."""


class RemoteAccessError(AcquisitionError):
    """Git could not reach or read an https origin; ``state`` names why.

    The message names the source URL and the state, never Git's own error text.
    """

    def __init__(self, state: RemoteFailureState, source_url: str, *, detail: str = "") -> None:
        super().__init__(describe_remote_failure(state, source_url, detail=detail))
        self.state: RemoteFailureState = state


class RepositoryTooLargeError(RemoteAccessError):
    """A provider refused a first clone that could not finish within the deadline."""

    def __init__(self, source_url: str, *, detail: str) -> None:
        super().__init__("too_large", source_url, detail=detail)


type PhaseReporter = Callable[[str], None]


def remote_url_for(source: GitSource) -> str:
    """The URL Git fetches *source* from: its normalized URL.

    A seam, not a policy: tests stand a local ``file://`` origin in for a provider URL
    here, so the canonical source identity stays the provider's.
    """

    return source.normalized


def _classified(source: GitSource, exc: GitCommandError) -> RemoteAccessError | None:
    """A typed failure for an https origin whose error text Git classifies.

    Only https: a ``file://`` failure's text names local paths, which could match.
    """

    if source.transport != "https":
        return None
    state = classify_remote_failure(exc.stderr_summary)
    return None if state is None else RemoteAccessError(state, source.normalized)


def _report(on_phase: PhaseReporter | None, phase: str) -> None:
    if on_phase is not None:
        on_phase(phase)


@dataclass(slots=True)
class StagingAcquisition:
    """A validated worktree-free Git database still under its staging lock."""

    home: Path
    entry: str
    git_dir: Path
    source: GitSource
    source_id: str
    object_format: ObjectFormat
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


def _claim_staging(home: Path, *, order: LockOrder | None = None) -> tuple[str, CacheLock]:
    for _attempt in range(_ENTRY_ATTEMPTS):
        entry = "acq-" + secrets.token_hex(6)
        try:
            lock = staging_entry_lock(home, entry, order=order)
        except LockBusyError:
            continue
        ensure_private_directory(home, staging_entry(entry))
        return entry, lock
    raise AcquisitionError("could not claim a staging entry")


@dataclass(frozen=True, slots=True)
class _StagingClaim:
    """An opened home and a claimed, still empty staging entry."""

    home: Path
    entry: str
    lock: CacheLock
    git_version: str

    def abandon(self) -> None:
        _delete_staging(self.home, self.entry)
        if self.lock.held:
            self.lock.remove_lock_file()


def _open_and_claim_staging(home: Path, owner: LockOrder) -> _StagingClaim:
    """Check the Git floor, open the cache, and claim a staging entry, in a worker thread.

    ``open_cache`` takes the blocking home lock and sweeps the home, so none
    of this may run on the event loop. The staging entry's lock outlives this section, so
    it is recorded for *owner*, the thread that awaits the acquisition and keeps it.
    """

    version = require_acquisition_git()
    cache = open_cache(home)
    entry, lock = _claim_staging(cache.home, order=owner)
    return _StagingClaim(cache.home, entry, lock, f"{version[0]}.{version[1]}.{version[2]}")


async def _abandon_off_loop(claim: _StagingClaim) -> None:
    """Delete a failed staging entry in a worker thread, finishing even if cancelled again.

    The entry can hold a whole fetched store, so its ``rmtree`` stays off the event loop.
    """

    await asyncio.shield(asyncio.ensure_future(asyncio.to_thread(claim.abandon)))


async def _run(
    args: list[str],
    *,
    cwd: Path | None = None,
    git_dir: Path | None = None,
    timeout_s: float | None = None,
) -> bytes:
    require_no_hierarchy_locks("git")
    if git_dir is not None:
        return await run_git(
            args,
            target=repository_store_target(git_dir=git_dir),
            policy=ACQUISITION_POLICY,
            timeout_s=timeout_s,
        )
    if cwd is None:
        raise TypeError("cwd or git_dir is required")
    return await run_git(args, cwd=cwd, policy=ACQUISITION_POLICY, timeout_s=timeout_s)


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


async def acquire_into_staging(
    source: GitSource, *, home: Path, on_phase: PhaseReporter | None = None
) -> StagingAcquisition:
    """Fetch *source* into a new staging store and validate it.

    ``file://`` and ``https://`` sources are acquired here. The returned object holds
    the staging liveness lock until :meth:`StagingAcquisition.abandon`. *on_phase* is
    told each phase as it starts.
    """
    if source.transport not in _ACQUIRED_TRANSPORTS:
        raise AcquisitionError(
            f"{source.transport} Git sources are not acquired yet ({source.normalized})"
        )
    remote_url = remote_url_for(source)
    network = list(remote_git_args(remote_url))
    # Only https has a first-request deadline: curl's stall bound does not cover a TLS
    # handshake that never completes. A local origin keeps the acquisition deadline.
    probe_timeout_s = REMOTE_PROBE_TIMEOUT_S if source.transport == "https" else None
    claim = await run_lock_section(
        functools.partial(_open_and_claim_staging, home, lock_order()),
        release=_StagingClaim.abandon,
    )
    home, entry, lock, git_version = claim.home, claim.entry, claim.lock, claim.git_version
    # Commands that run before the store exists start in the claimed staging entry, not
    # the home. Discovery stops at the working directory, and this one is private, new,
    # and never a repository, so neither the home nor anything enclosing it lends config.
    staging = home / staging_entry(entry)
    git_dir = staging / "repository.git"
    try:
        _report(on_phase, "reading the default branch")
        try:
            observed = await _run(
                [*network, "ls-remote", "--symref", "--", remote_url, "HEAD"],
                cwd=staging,
                timeout_s=probe_timeout_s,
            )
        except GitTimeoutError as exc:
            if source.transport != "https":
                raise
            raise RemoteAccessError(
                "timed_out",
                source.normalized,
                detail=f"no answer within {REMOTE_PROBE_TIMEOUT_S:g} s",
            ) from exc
        except GitCommandError as exc:
            # ls-remote itself failed: the path is missing, is not a repository, or
            # cannot be read. A readable source without HEAD is refused below.
            raise _classified(source, exc) or RemoteUnavailableError(
                "the source could not be read as a Git repository; nothing was published"
            ) from exc
        head_ref, revision = _parse_symref_head(observed)
        default_remote_ref = _remote_tracking_ref(head_ref)
        if default_remote_ref is None:
            # Publication needs a branch. Refuse here, before the fetch is paid for.
            raise ValidationFailedError("the source HEAD is not a branch")
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
        await _run(["config", "remote.origin.url", remote_url], git_dir=git_dir)
        _report(on_phase, "fetching every object")
        try:
            # Every object: a published store is complete, so no read ever needs the
            # origin again, and an origin that would honor a filter is not asked to.
            await _run(
                [
                    *network,
                    "fetch",
                    "--no-write-fetch-head",
                    "origin",
                    "+refs/heads/*:refs/remotes/origin/*",
                    "+refs/tags/*:refs/tags/*",
                ],
                git_dir=git_dir,
            )
        except GitCommandError as exc:
            raise _classified(source, exc) or FetchFailedError(
                "the fetch into staging failed"
            ) from exc
        _report(on_phase, "validating")
        try:
            kind = (await _run(["cat-file", "-t", revision], git_dir=git_dir)).strip()
            object_format_raw = (
                await _run(["rev-parse", "--show-object-format"], git_dir=git_dir)
            ).strip()
        except GitCommandError as exc:
            raise ValidationFailedError("the observed HEAD did not validate") from exc
        if kind != b"commit":
            raise ValidationFailedError("the observed HEAD is not a commit")
        await _require_ref_at(git_dir, default_remote_ref, revision)
        object_format_name = object_format_raw.decode("ascii")
        if object_format_name not in {"sha1", "sha256"}:
            raise ValidationFailedError("unsupported object format")
        object_format: ObjectFormat = "sha1" if object_format_name == "sha1" else "sha256"
        return StagingAcquisition(
            home=home,
            entry=entry,
            git_dir=git_dir,
            source=source,
            source_id=source_identity(source.transport, source.normalized),
            object_format=object_format,
            default_remote_ref=default_remote_ref,
            default_revision=revision,
            git_version=git_version,
            _lock=lock,
        )
    except GeneratorExit:
        # A closed coroutine cannot await its cleanup.
        claim.abandon()
        raise
    except BaseException:
        await _abandon_off_loop(claim)
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
            default_remote_ref=staged.default_remote_ref,
            default_revision=staged.default_revision,
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


def _publish_store_if_absent(staged: StagingAcquisition, key: str, store_lock: CacheLock) -> None:
    home = staged.home
    target = store_directory(key)
    if os.path.lexists(home / target):
        return
    with contextlib.suppress(FileExistsError):
        publish_entry(home, staging_entry(staged.entry), target, owner=store_lock)


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
        default_remote_ref=default_remote_ref,
        default_revision=default_revision,
    )


def _attach_existing_source(home: Path, slug: str, source_id: str, store_id: str, at: str) -> None:
    """Write the alias of a source published without one, or check the alias it has."""

    try:
        alias = read_record(
            home, source_record(slug, "store-alias.yml"), REPOSITORY_STORE_ALIAS_CONTRACT_ID
        )
    except FileNotFoundError:
        write_record_atomic(
            home,
            source_record(slug, "store-alias.yml"),
            RepositoryStoreAlias(
                source_id=source_id, store_id=store_id, generation=1, updated_at=at
            ),
            REPOSITORY_STORE_ALIAS_CONTRACT_ID,
            replace=False,
        )
        return
    if not isinstance(alias, RepositoryStoreAlias):
        raise ValidationFailedError("store-alias.yml did not validate")
    if alias.store_id != store_id:
        raise AliasConflictError("this source already names a different store")


def _publish_store_and_alias(
    staged: StagingAcquisition, store_id: str, key: str, at: str
) -> PublishedSource:
    """Publish or reuse the store, then its alias, under both locks held throughout.

    The alias lock and then the store lock are held from the store's rename through the
    alias commit, so every alias that names a store is written under that store's lock,
    and a holder of the store lock never sees this store published without its alias.
    A crash between the two renames leaves an unreferenced store, which the next
    acquisition of the same source reuses.
    """

    home, source, source_id = staged.home, staged.source, staged.source_id
    slug, alias_lock = _claim_source_slug(home, source, source_id)
    try:
        with alias_lock, repository_store_lock(home, key) as store_lock:
            _publish_store_if_absent(staged, key, store_lock)
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
            if not os.path.lexists(home / source_directory(slug)):
                _publish_source_directory(home, slug, source, source_id, store_id, at, alias_lock)
            else:
                _attach_existing_source(home, slug, source_id, store_id, at)
            return _published(
                home,
                slug,
                key,
                source,
                source_id,
                store_id,
                store.acquisition.object_format,
                state.default_remote_ref,
                state.default_revision,
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
        state.default_remote_ref,
        state.default_revision,
    )


def publish_from_staging(staged: StagingAcquisition) -> PublishedSource:
    """Publish *staged* as an immutable store and a source alias, then drop staging.

    Synchronous and blocking: it takes the alias lock and the store lock, each of which
    may wait on another process. Async callers run it in a worker thread, as
    :func:`acquire_source` does.
    """

    if staged.default_remote_ref is None:
        staged.abandon()
        raise ValidationFailedError("the source HEAD is not a branch")
    store_id = repository_store_id(staged.source_id, staged.object_format)
    key = store_key(store_id)
    at = _canonical_now()
    try:
        _write_store_records(staged, store_id, at)
        return _publish_store_and_alias(staged, store_id, key, at)
    finally:
        # After the locks: when the store was reused, staging still holds a whole
        # fetched copy, and deleting it is no work to do under a lock.
        staged.abandon()


async def acquire_source(
    source: GitSource, *, home: Path, on_phase: PhaseReporter | None = None
) -> PublishedSource:
    """Return a published ``file://`` or ``https://`` source, fetching only on a miss.

    A hit inspects an existing home without fetching or opening the cache, so it
    does not require the acquisition Git floor or owner-write on the home, and it
    makes no network request. It may try to record ``last_opened_at``; a failed write
    is dropped and the hit still returns. A miss checks the Git floor and then lets
    each provider refuse the first clone (the GitHub provider's size check) before
    ``open_cache``, so neither refusal creates the application home or completes an
    empty directory into an ``f01`` skeleton. A miss that is allowed to fetch then
    opens the cache (and sweeps staging and trash) and fetches, telling *on_phase*
    each phase as it starts. A future layout is refused before any write.
    """

    if source.transport not in _ACQUIRED_TRANSPORTS:
        raise AcquisitionError(
            f"{source.transport} Git sources are not acquired yet ({source.normalized})"
        )
    # Every step that reads the home, takes a cache lock, or sweeps runs in a worker
    # thread; the event loop only awaits Git processes and those threads.
    found, home = await run_lock_section(
        functools.partial(_find_or_open_cache, source, home, open_on_miss=False)
    )
    if found is not None:
        return found
    await check_first_clone(source)
    found, home = await run_lock_section(functools.partial(_find_or_open_cache, source, home))
    if found is not None:
        return found
    staged = await acquire_into_staging(source, home=home, on_phase=on_phase)
    _report(on_phase, "publishing")
    published = await run_lock_section(functools.partial(_publish_and_touch, staged))
    _report(on_phase, "done")
    return published


def _find_or_open_cache(
    source: GitSource, home: Path, *, open_on_miss: bool = True
) -> tuple[PublishedSource | None, Path]:
    """Return a cache hit, or open the cache for a miss; synchronous and blocking.

    With *open_on_miss* false, a miss only checks the Git floor and opens nothing.
    """

    if not home.exists():
        return None, home
    try:
        layout = read_layout(home, shared="keep")
        read_config(home, shared="keep")
    except PrivateStorageError:
        layout = None
    if layout is not None:
        found = _find_published(source, home)
        if found is not None:
            _touch_last_opened(found)
            return found, home
    require_acquisition_git()
    if not open_on_miss:
        return None, home
    cache = open_cache(home)
    home = cache.home
    found = _find_published(source, home)
    if found is not None:
        _touch_last_opened(found)
    return found, home


def _publish_and_touch(staged: StagingAcquisition) -> PublishedSource:
    published = publish_from_staging(staged)
    _touch_last_opened(published)
    return published


__all__ = [
    "AcquisitionError",
    "AliasConflictError",
    "FetchFailedError",
    "PhaseReporter",
    "PublishedSource",
    "RemoteAccessError",
    "RemoteUnavailableError",
    "RepositoryTooLargeError",
    "StagingAcquisition",
    "ValidationFailedError",
    "acquire_into_staging",
    "acquire_source",
    "publish_from_staging",
    "remote_url_for",
]
