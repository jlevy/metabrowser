"""Bounded, owner-local admission of PR snapshot pairs across process restarts."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Final

from pydantic import TypeAdapter, ValidationError

from metabrowser.builtin_plugins.github.pull_record import PullRecord, Reader, Sha, _Model
from metabrowser.cache.atomic import RecordError, read_bytes_bounded
from metabrowser.cache.paths import source_pull_record
from metabrowser.home import PrivateStorageError, write_private_file_atomic

_MAX_PAIRS: Final = 16


class SnapshotBinding(_Model):
    store: str
    reader: Reader
    base: Sha
    head: Sha


_BINDINGS = TypeAdapter(tuple[SnapshotBinding, ...])


def _path(slug: str, number: int) -> str:
    return source_pull_record(slug, number).removesuffix(".json") + ".snapshots.json"


def read_snapshot_bindings(home: Path, slug: str, number: int) -> tuple[SnapshotBinding, ...]:
    try:
        body = read_bytes_bounded(home, _path(slug, number), max_bytes=16 * 1024, shared="refuse")
        return _BINDINGS.validate_json(body)[-_MAX_PAIRS:]
    except (RecordError, OSError, PrivateStorageError, ValidationError):
        return ()


def retain_snapshot_binding(home: Path, slug: str, store: str, record: PullRecord) -> None:
    """Retain an admitted pair. The caller holds the source alias publication lock."""
    comparison = record.comparison
    if comparison is None:
        return
    binding = SnapshotBinding(
        store=store, reader=record.reader, base=comparison.base, head=comparison.head
    )
    previous = read_snapshot_bindings(home, slug, record.number)
    current = (
        *(pair for pair in previous if pair.reader == binding.reader and pair != binding),
        binding,
    )[-_MAX_PAIRS:]
    if current != previous:
        write_private_file_atomic(
            home,
            _path(slug, record.number),
            json.dumps([pair.model_dump() for pair in current], separators=(",", ":")).encode(),
        )
