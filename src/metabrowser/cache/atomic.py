"""Bounded record reads, atomic record writes, and lock-verified publication.

A record is read through :func:`metabrowser.home.open_private_file` with a size bound,
parsed with SoftSchema's portable YAML rules, and validated against the contract the
caller selects from the record's place in the layout. It is written only by
:func:`metabrowser.home.write_private_file_atomic`: an exclusive temporary file, flushed
and renamed into place, so an interrupted write leaves the previous record.

Publication renames a staged directory or file to a path that must not exist. The
guarantee is the check under the owning lock: the caller holds the lock every writer of
that path takes, the target is verified absent, and the rename uses the platform
no-replace rename where there is one, so a violated lock discipline fails instead of
silently replacing an entry.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Final

from pydantic import BaseModel

from metabrowser.cache.contracts import cache_contract_registry
from metabrowser.cache.locks import CacheLock, LockOrderError
from metabrowser.home import (
    ensure_private_directory,
    open_private_file,
    rename_without_replacing,
    write_private_file_atomic,
)
from metabrowser.plugin_loader.artifact_contracts import serialize_artifact, validate_artifact

# The largest f01 record in the conformance corpus is under 1 KiB; the bound only stops a
# corrupted or substituted file from being parsed at any size.
MAX_RECORD_BYTES: Final = 64 * 1024


class RecordError(Exception):
    """A record exists but is too large, malformed, or outside its contract.

    ``str()`` names no path; ``path`` is for local logs.
    """

    def __init__(self, message: str, path: Path) -> None:
        super().__init__(message)
        self.path: Path = path


def read_bytes_bounded(
    home: Path, relative_path: str, *, max_bytes: int = MAX_RECORD_BYTES
) -> bytes:
    """Read a private file of at most *max_bytes*; a missing file raises ``FileNotFoundError``."""

    fd = open_private_file(home, relative_path, os.O_RDONLY | os.O_NONBLOCK)
    try:
        if os.fstat(fd).st_size > max_bytes:
            raise RecordError("the record is larger than any valid record", home / relative_path)
        chunks: list[bytes] = []
        remaining = max_bytes + 1
        while remaining > 0:
            chunk = os.read(fd, remaining)
            if not chunk:
                break
            chunks.append(chunk)
            remaining -= len(chunk)
    finally:
        os.close(fd)
    data = b"".join(chunks)
    if len(data) > max_bytes:
        raise RecordError("the record is larger than any valid record", home / relative_path)
    return data


def parse_record(payload: bytes, contract_id: str, path: Path) -> BaseModel:
    """Validate *payload* against the installed contract the caller chose."""

    try:
        artifact = validate_artifact(
            payload, expected_contract_id=contract_id, contracts=cache_contract_registry()
        )
    except ValueError as error:
        raise RecordError(f"the record does not satisfy {contract_id}: {error}", path) from error
    record = artifact.record
    if not isinstance(record, BaseModel):
        raise RecordError(f"the record does not satisfy {contract_id}", path)
    return record


def read_record(home: Path, relative_path: str, contract_id: str) -> BaseModel:
    """Read and validate one enforced record."""

    return parse_record(read_bytes_bounded(home, relative_path), contract_id, home / relative_path)


def serialize_record(record: BaseModel, contract_id: str) -> bytes:
    """Serialize a record with its contract, envelope, and status, and no schema path."""

    return serialize_artifact(record, contract_id=contract_id, contracts=cache_contract_registry())


def write_record_atomic(
    home: Path,
    relative_path: str,
    record: BaseModel,
    contract_id: str,
    *,
    replace: bool = True,
) -> None:
    """Validate and publish one enforced record by atomic rename.

    With *replace* false an existing record raises :class:`FileExistsError`.
    """

    write_private_file_atomic(
        home, relative_path, serialize_record(record, contract_id), replace=replace
    )


def publish_entry(
    home: Path, staged_relative: str, target_relative: str, *, owner: CacheLock
) -> bool:
    """Rename a staged entry to a target that must not exist, under its owning lock.

    *owner* must be held; it is the lock every writer of *target_relative* takes. The
    target's parent directory is created or verified owner-only. Raises
    :class:`FileExistsError` if the target exists. Returns whether the platform's atomic
    no-replace rename performed the move.
    """

    if not owner.held:
        raise LockOrderError("publication requires its owning lock to be held")
    target_parent, _, _ = target_relative.rpartition("/")
    staged_parent, _, _ = staged_relative.rpartition("/")
    ensure_private_directory(home, staged_parent)
    parent = ensure_private_directory(home, target_parent)
    os.lstat(home / staged_relative)
    atomic = rename_without_replacing(home / staged_relative, home / target_relative)
    _sync(parent)
    if staged_parent != target_parent:
        _sync(home / staged_parent)
    return atomic


def _sync(directory: Path) -> None:
    fd = os.open(directory, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


__all__ = [
    "MAX_RECORD_BYTES",
    "RecordError",
    "parse_record",
    "publish_entry",
    "read_bytes_bounded",
    "read_record",
    "serialize_record",
    "write_record_atomic",
]
