"""Acquire a classified Git source into an isolated worktree-free staging store.

This module stops at a validated staging directory. It does not rename into
``repository-stores``, create a source alias, or serve content. A ``file://``
URL is fetched through Git's pack transport; a bare path never reaches here.
"""

from __future__ import annotations

import hashlib
import secrets
import shutil
from dataclasses import dataclass, field
from pathlib import Path
from typing import Final, Literal, Self

from metabrowser.cache.identity import ObjectFormat, source_identity
from metabrowser.cache.layout import open_cache
from metabrowser.cache.locks import (
    CacheLock,
    LockBusyError,
    require_no_hierarchy_locks,
    staging_entry_lock,
)
from metabrowser.cache.paths import staging_entry
from metabrowser.cache.urls import GitSource
from metabrowser.git.process import (
    ACQUISITION_POLICY,
    GitCommandError,
    repository_store_target,
    require_acquisition_git,
    run_git,
)
from metabrowser.home import ensure_private_directory

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
_ENTRY_ATTEMPTS: Final = 8


class AcquisitionError(Exception):
    """Acquisition stopped before a validated staging store existed."""


class RemoteUnavailableError(AcquisitionError):
    """``ls-remote`` could not observe HEAD at the classified source."""


class FetchFailedError(AcquisitionError):
    """The blobless fetch into staging failed after HEAD was observed."""


class ValidationFailedError(AcquisitionError):
    """The fetched objects, HEAD, or object format did not validate."""


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
) -> bytes:
    require_no_hierarchy_locks("git")
    if git_dir is not None:
        return await run_git(
            args, target=repository_store_target(git_dir=git_dir), policy=ACQUISITION_POLICY
        )
    if cwd is None:
        raise TypeError("cwd or git_dir is required")
    return await run_git(args, cwd=cwd, policy=ACQUISITION_POLICY)


def _parse_symref_head(stdout: bytes) -> tuple[str | None, str]:
    ref: str | None = None
    oid: str | None = None
    for line in stdout.decode("ascii", errors="replace").splitlines():
        if line.startswith("ref:"):
            payload, _, _name = line.partition("\t")
            ref = payload.removeprefix("ref:").strip()
            continue
        if line.endswith("\tHEAD"):
            oid = line.split("\t", 1)[0].strip()
    if oid is None or not oid:
        raise RemoteUnavailableError("the source did not advertise HEAD")
    return ref, oid


def _remote_tracking_ref(head_ref: str | None) -> str | None:
    if head_ref is None or not head_ref.startswith("refs/heads/"):
        return None
    return "refs/remotes/origin/" + head_ref.removeprefix("refs/heads/")


async def _configuration_digest(git_dir: Path) -> str:
    raw = await _run(["config", "--file", str(git_dir / "config"), "--list", "-z"], git_dir=git_dir)
    return "sha256:" + hashlib.sha256(raw).hexdigest()


async def _filter_honored(git_dir: Path, revision: str) -> bool:
    listing = await _run(["rev-list", "--objects", "--missing=print", revision], git_dir=git_dir)
    return any(line.startswith(b"?") for line in listing.splitlines())


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
    git_dir = home / staging_entry(entry) / "repository.git"
    try:
        try:
            observed = await _run(
                [*_PROTOCOL, "ls-remote", "--symref", "--", source.normalized, "HEAD"],
                cwd=home,
            )
        except GitCommandError as exc:
            raise RemoteUnavailableError("the source did not advertise HEAD") from exc
        head_ref, revision = _parse_symref_head(observed)
        await _run(["init", "--bare", "--template=", "-q", str(git_dir)], cwd=home)
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
        object_format_name = object_format_raw.decode("ascii")
        if object_format_name not in {"sha1", "sha256"}:
            raise ValidationFailedError("unsupported object format")
        object_format: ObjectFormat = "sha1" if object_format_name == "sha1" else "sha256"
        strategy: Literal["blobless", "full"] = (
            "blobless" if await _filter_honored(git_dir, revision) else "full"
        )
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
            default_remote_ref=_remote_tracking_ref(head_ref),
            default_revision=revision,
            git_version=git_version,
            _lock=lock,
        )
    except BaseException:
        _delete_staging(home, entry)
        if lock.held:
            lock.remove_lock_file()
        raise


__all__ = [
    "AcquisitionError",
    "FetchFailedError",
    "RemoteUnavailableError",
    "StagingAcquisition",
    "ValidationFailedError",
    "acquire_into_staging",
]
