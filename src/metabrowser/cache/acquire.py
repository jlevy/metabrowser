"""Acquire a classified Git source into an isolated worktree-free store.

A ``file://`` or ``https://`` URL is fetched into staging, every object and not a
partial clone, then published as a complete store and a source alias. Nothing later
removes objects from a store. This module does not serve content. The CLI acquires
through ``--no-serve``, ``--api``, and ``--show``; ssh stays closed. A bare path never
reaches here. Both commands against the origin are built by
:mod:`metabrowser.cache.origin`: the protocol allowlist, the measured stall bound, and a
provider's credential helper.

A caller that wants to show a first clone running passes two reporters: one is told each
phase as it starts, and the other each progress record of the fetch, as numbers
(:mod:`metabrowser.git.progress`). Neither is given a path, and a cache hit calls
neither.

With ``--checkout`` the store is an overlay instead: the same staging, validation, and
publication, with an ``objects/info/alternates`` naming the checkout's objects, so the fetch
brings only what the checkout lacks (:mod:`metabrowser.cache.lender`). A published store
wins whatever its mode, so a URL never silently changes storage. An overlay whose checkout
has gone is refused at open, and naming the checkout's new place repairs it.
"""

from __future__ import annotations

import asyncio
import contextlib
import dataclasses
import functools
import logging
import os
import re
import secrets
import shutil
from collections.abc import Callable
from dataclasses import dataclass, field
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
from metabrowser.cache.lender import (
    CheckoutRefusedError,
    Lender,
    LenderRefusal,
    attach_lender,
    check_lender,
    checkout_command,
    lender_present,
    negotiation_tip_args,
    object_format_refusal,
    read_alternates,
    rebind_lender,
    show_path,
    suggested_checkout,
)
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
from metabrowser.cache.origin import (
    BRANCH_MIRROR_PREFIX,
    REMOTE_PROBE_TIMEOUT_S,
    OriginHeadError,
    RemoteFailureState,
    classify_remote_failure,
    describe_remote_failure,
    fetched_ref_names,
    ls_remote_head_args,
    mirror_fetch_args,
    parse_symref_head,
    remote_tracking_ref,
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
    StoreLender,
    StoreOperation,
    canonical_now,
)
from metabrowser.cache.resolve import (
    case_colliding_refs,
    describe_case_collision,
    store_ignores_case,
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
from metabrowser.git.progress import GitProgress
from metabrowser.home import (
    PrivateStorageError,
    SharedEntryPolicy,
    configuration_directory,
    ensure_private_directory,
    validate_storage_separation,
)

log = logging.getLogger(__name__)

_ACQUIRED_TRANSPORTS: Final[frozenset[str]] = frozenset({"file", "https"})
_STORE_CONFIG: Final[tuple[tuple[str, str], ...]] = (
    ("maintenance.auto", "false"),
    ("gc.auto", "0"),
    ("fetch.recurseSubmodules", "false"),
    ("transfer.bundleURI", "false"),
    ("core.hooksPath", "/dev/null"),
)
# What borrowing from a checkout adds. The store would otherwise read the checkout's
# ``objects/info/commit-graph``, which can name commits whose objects are gone: measured
# 2026-11-02, ``rev-list --count`` answered a history 743 commits longer than ``log`` could
# walk. And Git would run ``for-each-ref`` inside the checkout twice per fetch, under the
# checkout's configuration; ``true`` makes that read a no-op.
_OVERLAY_CONFIG: Final[tuple[tuple[str, str], ...]] = (
    ("core.commitGraph", "false"),
    ("core.alternateRefsCommand", "true"),
)
_ENTRY_ATTEMPTS: Final = 8
# How a source that is itself a partial clone refuses to send an object it lacks. The
# fetch's upload-pack inherits GIT_NO_LAZY_FETCH, and acquisition runs Git under
# LC_ALL=C, so this is Git's own untranslated text (promisor-remote.c).
_PARTIAL_CLONE_SOURCE: Final = re.compile(r"could not fetch [0-9a-f]+ from promisor remote")


class AcquisitionError(Exception):
    """Acquisition stopped before a validated staging store existed."""


class RemoteUnavailableError(AcquisitionError):
    """``ls-remote`` could not observe HEAD at the classified source."""


class FetchFailedError(AcquisitionError):
    """The fetch into staging failed after HEAD was observed."""


class PartialCloneSourceError(FetchFailedError):
    """The source is a partial clone missing objects the fetch needs."""


class ValidationFailedError(AcquisitionError):
    """The fetched objects, HEAD, or object format did not validate."""


class AliasConflictError(AcquisitionError):
    """The source already names a different store; the existing alias was left in place."""


class StoreDamagedError(ValidationFailedError):
    """A store's record of what it borrows disagrees with its alternates file."""

    state: Final = "damaged"


class LenderMissingError(AcquisitionError):
    """The checkout an overlay store borrows from is gone, so nothing in it can be read."""

    state: Final = "lender_missing"

    def __init__(self, source_url: str, lender: StoreLender) -> None:
        super().__init__(
            f"the checkout this mirror of {source_url} borrows objects from is gone: "
            f"{show_path(lender.checkout)} (lender_missing). If it moved, name where it is "
            f"now: metab {source_url} --checkout <new path>"
        )


class _ObjectFormatRefusedError(AcquisitionError):
    """The origin's object format is not the named checkout's. It is cloned instead."""


class RemoteAccessError(AcquisitionError):
    """Git could not reach or read an https origin; ``state`` names why.

    The message names the source URL and the state, never Git's own error text.
    """

    def __init__(self, state: RemoteFailureState, source_url: str, *, detail: str = "") -> None:
        super().__init__(describe_remote_failure(state, source_url, detail=detail))
        self.state: RemoteFailureState = state


class RepositoryTooLargeError(RemoteAccessError):
    """A provider refused a first clone over its size limit, which *detail* states."""

    def __init__(self, source_url: str, *, detail: str) -> None:
        super().__init__("too_large", source_url, detail=detail)


type PhaseReporter = Callable[[str], None]
type ProgressReporter = Callable[[GitProgress], None]
type NoteReporter = Callable[[str], None]


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


class RefCaseCollisionError(ValidationFailedError):
    """The origin has refs a case-insensitive store cannot hold apart."""

    state: Final = "ref_case_collision"


async def _refuse_case_collisions(git_dir: Path, names: tuple[str, ...]) -> None:
    """Refuse a store whose refs a case-insensitive filesystem folded together.

    On such a filesystem ``refs/remotes/origin/Feature`` and ``…/feature`` are one loose
    file: a non-atomic fetch keeps whichever it wrote last under the first name, and the
    other name resolves to it too, so a URL could pin the wrong commit. Nothing is
    published; a refresh reports the same state for its own fetch.
    """

    colliding = case_colliding_refs(names)
    if colliding and await store_ignores_case(repository_store_target(git_dir=git_dir)):
        raise RefCaseCollisionError(
            f"the source {describe_case_collision(colliding)}; nothing was published"
        )


def _report(on_phase: PhaseReporter | None, phase: str) -> None:
    if on_phase is not None:
        on_phase(phase)


def _note(on_note: NoteReporter | None, text: str) -> None:
    if on_note is not None:
        on_note(text)


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
    lender: StoreLender | None = None
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
    on_progress: ProgressReporter | None = None,
) -> bytes:
    require_no_hierarchy_locks("git")
    if git_dir is not None:
        return await run_git(
            args,
            target=repository_store_target(git_dir=git_dir),
            policy=ACQUISITION_POLICY,
            timeout_s=timeout_s,
            on_progress=on_progress,
        )
    if cwd is None:
        raise TypeError("cwd or git_dir is required")
    return await run_git(args, cwd=cwd, policy=ACQUISITION_POLICY, timeout_s=timeout_s)


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
    source: GitSource,
    *,
    home: Path,
    on_phase: PhaseReporter | None = None,
    on_progress: ProgressReporter | None = None,
    lender: Lender | None = None,
    on_note: NoteReporter | None = None,
) -> StagingAcquisition:
    """Fetch *source* into a new staging store and validate it.

    ``file://`` and ``https://`` sources are acquired here. The returned object holds
    the staging liveness lock until :meth:`StagingAcquisition.abandon`. *on_phase* is
    told each phase as it starts. With *on_progress* the fetch runs with ``--progress``
    and each record Git writes is passed on as numbers; without it Git reports none.

    With *lender*, the store borrows that checkout's objects and fetches what it lacks.
    No ref comes from the checkout: its tips are only what the fetch tells the origin it
    has, so the store's refs are what the origin sent, as a full store's are. *on_note* is
    told that it borrows, once the origin's object format has shown that it can.
    """
    if source.transport not in _ACQUIRED_TRANSPORTS:
        raise AcquisitionError(
            f"{source.transport} Git sources are not acquired yet ({source.normalized})"
        )
    remote_url = remote_url_for(source)
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
                ls_remote_head_args(remote_url),
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
        try:
            head_ref, revision = parse_symref_head(observed)
        except OriginHeadError as exc:
            raise RemoteUnavailableError(str(exc)) from exc
        default_remote_ref = remote_tracking_ref(head_ref)
        if default_remote_ref is None:
            # Publication needs a branch. Refuse here, before the fetch is paid for.
            raise ValidationFailedError("the source HEAD is not a branch")
        advertised_format: ObjectFormat = "sha256" if len(revision) == 64 else "sha1"
        if lender is not None:
            mismatch = object_format_refusal(lender, advertised_format)
            if mismatch is not None:
                raise _ObjectFormatRefusedError(mismatch.message)
            _note(on_note, f"borrowing objects from {show_path(lender.root)}")
            if await asyncio.to_thread(os.path.exists, lender.common_dir / "shallow"):
                _note(on_note, "history is shallow, as the checkout's is")
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
        negotiation: tuple[str, ...] = ()
        borrowed = lender.record if lender is not None else None
        if borrowed is not None:
            for key, value in _OVERLAY_CONFIG:
                await _run(["config", key, value], git_dir=git_dir)
            await asyncio.to_thread(attach_lender, git_dir, borrowed)
            require_no_hierarchy_locks("git")
            negotiation = await negotiation_tip_args(
                repository_store_target(git_dir=git_dir),
                borrowed,
                preferred=default_remote_ref.removeprefix(BRANCH_MIRROR_PREFIX),
            )
        _report(on_phase, "fetching every object" if lender is None else "fetching what it lacks")
        try:
            # Every object, or for an overlay every object the checkout lacks: nothing is
            # filtered, so no read ever needs the origin again, and an origin that would
            # honor a filter is not asked to.
            updated = await _run(
                mirror_fetch_args(
                    remote_url,
                    prune=False,
                    progress=on_progress is not None,
                    negotiation=negotiation,
                ),
                git_dir=git_dir,
                on_progress=on_progress,
            )
        except GitCommandError as exc:
            if _PARTIAL_CLONE_SOURCE.search(exc.stderr_summary):
                raise PartialCloneSourceError(
                    "the source is a partial clone missing objects; clone it fully first"
                ) from exc
            raise _classified(source, exc) or FetchFailedError(
                "the fetch into staging failed"
            ) from exc
        _report(on_phase, "validating")
        await _refuse_case_collisions(git_dir, fetched_ref_names(updated))
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
            lender=borrowed,
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
    """A published source alias naming one immutable repository store.

    ``fetched`` is true when the call that returned it fetched the store from the origin
    just now, so a ref the mirror lacks is not one a second fetch would bring.
    ``last_fetch_at`` is when the store was last fetched, as its record says. ``lender``
    is what an overlay store borrows from, and ``None`` for a full store.
    """

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
    fetched: bool = field(default=False, compare=False)
    last_fetch_at: str | None = field(default=None, compare=False)
    lender: StoreLender | None = field(default=None, compare=False)


def _touch_last_opened(published: PublishedSource) -> None:
    """Best-effort recency. A failed write must not fail the open."""

    try:
        with source_alias_lock(published.home, published.slug, blocking=False):
            write_record_atomic(
                published.home,
                source_record(published.slug, "state.yml"),
                RepositorySourceState(last_opened_at=canonical_now()),
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
            lender=staged.lender,
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
    last_fetch_at: str | None,
    lender: StoreLender | None,
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
        last_fetch_at=last_fetch_at,
        lender=lender,
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
                state.last_fetch_at,
                store.lender,
            )
    finally:
        if alias_lock.held:
            alias_lock.release()


def _require_consistent_borrowing(git_dir: Path, lender: StoreLender | None) -> None:
    """Refuse a store whose alternates file is not what its record says it borrows.

    A cache that was tampered with cannot point reads at another directory this way, and
    a store with no alternates file whose record says it has one would answer ``missing``
    for every borrowed object.
    """

    named = read_alternates(git_dir)
    if named != (lender.objects if lender is not None else None):
        raise StoreDamagedError(
            "this cached store's record of what it borrows disagrees with its objects/info/"
            "alternates file (damaged), so it was not opened. Move the cache directory aside, "
            "or set METABROWSER_CACHE_DIR to a different directory"
        )


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
    _require_consistent_borrowing(home / store_directory(key) / "repository.git", store.lender)
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
        state.last_fetch_at,
        store.lender,
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
    at = canonical_now()
    try:
        _write_store_records(staged, store_id, at)
        return _publish_store_and_alias(staged, store_id, key, at)
    finally:
        # After the locks: when the store was reused, staging still holds a whole
        # fetched copy, and deleting it is no work to do under a lock.
        staged.abandon()


async def acquire_source(
    source: GitSource,
    *,
    home: Path,
    on_phase: PhaseReporter | None = None,
    on_progress: ProgressReporter | None = None,
    checkout: Path | None = None,
    on_note: NoteReporter | None = None,
    inspecting: bool = False,
) -> PublishedSource:
    """Return a published ``file://`` or ``https://`` source, fetching only on a miss.

    A hit inspects an existing home without fetching or opening the cache, so it
    does not require the acquisition Git floor or owner-write on the home, and it
    makes no network request. It may try to record ``last_opened_at``; a failed write
    is dropped and the hit still returns. A miss checks the Git floor and then lets
    each provider refuse the first clone (the GitHub provider's size check) before
    ``open_cache``, so neither refusal creates the application home or completes an
    empty directory into an ``f01`` skeleton. A miss that is allowed to fetch then
    opens the cache (and sweeps staging) and fetches, telling *on_phase* each phase
    as it starts and *on_progress* how far the fetch has got. A future layout is refused
    before any write.

    *checkout* is what the reader named with ``--checkout``: on a miss it lends its objects
    if it can, and needs no size check, since only what it lacks is fetched; a checkout of
    another repository is refused. *on_note* is told what a reader should know about
    storage, one line each. Without *checkout*, a command that asks for notes is told when
    its working directory is a checkout of the source, which is never borrowed from
    unnamed. An overlay whose checkout has gone is refused unless *inspecting*, which is
    the cache routes: they read records and no object.
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
        return await _settled_hit(found, checkout, on_note, inspecting=inspecting)
    lender = await _lender_for_miss(source, checkout, on_note)
    if lender is None:
        await check_first_clone(source)
    found, home = await run_lock_section(functools.partial(_find_or_open_cache, source, home))
    if found is not None:
        return await _settled_hit(found, checkout, on_note, inspecting=inspecting)
    try:
        staged = await acquire_into_staging(
            source,
            home=home,
            on_phase=on_phase,
            on_progress=on_progress,
            lender=lender,
            on_note=on_note,
        )
    except _ObjectFormatRefusedError as exc:
        _note(on_note, f"{exc}; cloning")
        await check_first_clone(source)
        staged = await acquire_into_staging(
            source, home=home, on_phase=on_phase, on_progress=on_progress
        )
    _report(on_phase, "publishing")
    published = await run_lock_section(functools.partial(_publish_and_touch, staged))
    _report(on_phase, "done")
    return dataclasses.replace(published, fetched=True)


async def _lender_for_miss(
    source: GitSource, checkout: Path | None, on_note: NoteReporter | None
) -> Lender | None:
    """The checkout to borrow from when *source* has no store yet, saying what is decided."""

    if checkout is None:
        if on_note is not None:
            await asyncio.to_thread(_suggest_checkout, source, on_note)
        return None
    checked = await asyncio.to_thread(check_lender, checkout, source)
    if isinstance(checked, LenderRefusal):
        _note(on_note, f"{checked.message}; cloning")
        return None
    return checked


def _suggest_checkout(source: GitSource, on_note: NoteReporter) -> None:
    try:
        working_directory = Path.cwd()
    except OSError:
        return
    suggested = suggested_checkout(source, working_directory)
    if suggested is not None:
        on_note(
            f"this directory is a checkout of {source.normalized}; to borrow its objects "
            f"instead of cloning: {checkout_command(source.normalized, suggested)}"
        )


async def _settled_hit(
    found: PublishedSource,
    checkout: Path | None,
    on_note: NoteReporter | None,
    *,
    inspecting: bool,
) -> PublishedSource:
    """A published store as this command may use it; a published store always wins.

    A named checkout changes nothing about a full store or a healthy overlay. It repairs
    an overlay whose checkout has gone, once it has passed the checks a new overlay's
    checkout does. Nothing else changes a store's mode or what it borrows.
    """

    recorded = found.lender
    if checkout is None:
        if (
            recorded is not None
            and not inspecting
            and not await asyncio.to_thread(lender_present, recorded)
        ):
            raise LenderMissingError(found.source.normalized, recorded)
        return found
    if recorded is None:
        _note(
            on_note,
            f"a full mirror of {found.source.normalized} is already in the cache, and it is "
            "kept: --checkout borrowed nothing. This release has no command that converts it",
        )
        return found
    checked = await asyncio.to_thread(check_lender, checkout, found.source)
    if isinstance(checked, Lender) and checked.record.objects == recorded.objects:
        return found
    if await asyncio.to_thread(lender_present, recorded):
        _note(
            on_note,
            f"this mirror already borrows objects from {show_path(recorded.checkout)}, and it "
            "keeps doing so: --checkout changed nothing",
        )
        return found
    if isinstance(checked, Lender):
        mismatch = object_format_refusal(checked, found.object_format)
        checked = mismatch if mismatch is not None else checked
    if isinstance(checked, LenderRefusal):
        raise CheckoutRefusedError(f"--checkout cannot repair this mirror: {checked.message}")
    _note(on_note, f"borrowing objects from {show_path(checked.root)}")
    return await run_lock_section(functools.partial(_rebind, found, checked.record))


def _rebind(found: PublishedSource, lender: StoreLender) -> PublishedSource:
    """Point an overlay whose checkout has gone at *lender*, under the store's lock."""

    relative = store_record(found.store_key, "store.yml")
    with repository_store_lock(found.home, found.store_key):
        store = _require_same_store(found.home, found.store_key, found.store_id)
        rebind_lender(found.git_dir, lender)
        write_record_atomic(
            found.home,
            relative,
            store.model_copy(update={"lender": lender}),
            REPOSITORY_STORE_CONTRACT_ID,
        )
    return dataclasses.replace(found, lender=lender)


def _find_or_open_cache(
    source: GitSource, home: Path, *, open_on_miss: bool = True
) -> tuple[PublishedSource | None, Path]:
    """Return a cache hit, or open the cache for a miss; synchronous and blocking.

    With *open_on_miss* false, a miss only checks the Git floor and opens nothing, so a
    below-floor Git is refused before any provider check reaches the network.
    """

    validate_storage_separation(home)
    if not home.exists():
        if not open_on_miss:
            require_acquisition_git()
        return None, home
    try:
        layout = read_layout(home, shared="keep")
        read_config(configuration_directory(), shared="keep")
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
    "LenderMissingError",
    "NoteReporter",
    "PartialCloneSourceError",
    "PhaseReporter",
    "ProgressReporter",
    "PublishedSource",
    "RefCaseCollisionError",
    "RemoteAccessError",
    "RemoteUnavailableError",
    "RepositoryTooLargeError",
    "StagingAcquisition",
    "StoreDamagedError",
    "ValidationFailedError",
    "acquire_into_staging",
    "acquire_source",
    "publish_from_staging",
    "remote_url_for",
]
