"""Bounded, owner-local admission of PR snapshot pairs across process restarts.

``sources/<slug>/pulls/<n>.snapshots.json`` keeps the comparison pairs a mirror's records
named before the current one, so a revision page opened at an earlier base and head
keeps opening after a refresh moves the record on. Only a store-backed record write
changes it, under the source alias lock, by atomic replacement. It holds one reader's
pairs: a write by another reader starts it over, whether or not that write has a
comparison of its own, and admission also requires the record's reader. Each pair names
the store that computed it, and is admitted only for that store.

Admission reads it with :func:`read_snapshot_bindings`, which fails closed: a file it
cannot read now admits nothing and says so, and a malformed one retains nothing. A writer
reads it with its own reader, which tells a missing file from one it cannot read now: a
transient failure leaves the file as it was, and only a file no writer of this format
could have written is started over, with a debug log.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Final

from pydantic import TypeAdapter, ValidationError

from metabrowser.builtin_plugins.github.pull_record import (
    PullRecord,
    Reader,
    RecordAbsence,
    Sha,
    _Model,
)
from metabrowser.cache.atomic import RecordError, read_bytes_bounded
from metabrowser.cache.paths import source_pull_snapshots
from metabrowser.home import PrivateStorageError, write_private_file_atomic

log = logging.getLogger(__name__)

# How many earlier comparisons a revision link outlives: one per head change of a pull
# request. Admission validates the whole file on each request it cannot answer from the
# current record, so the cost is the file's size. Sixteen pairs of the longest fields
# this model accepts (64-hex SHA-256 IDs, a 103-character reader, a `sha256:` store ID)
# serialize to 5,553 bytes, and validating that body took 0.021 ms (measured 2026-11-11,
# `timeit` over 2,000 runs, three adjacent runs, load average 2.3). The read bound is
# about three times the largest valid file.
_MAX_PAIRS: Final = 16
_MAX_BYTES: Final = 16 * 1024


class SnapshotBinding(_Model):
    store: str
    reader: Reader
    base: Sha
    head: Sha


_BINDINGS = TypeAdapter(tuple[SnapshotBinding, ...])


def read_snapshot_bindings(
    home: Path, slug: str, number: int
) -> tuple[SnapshotBinding, ...] | None:
    """The retained pairs; ``None`` when the file is there but cannot be read now. Read-only.

    A missing file, and one no writer of this format could have written, retain nothing.
    """
    try:
        body = read_bytes_bounded(
            home, source_pull_snapshots(slug, number), max_bytes=_MAX_BYTES, shared="refuse"
        )
        return _BINDINGS.validate_json(body)[-_MAX_PAIRS:]
    except (FileNotFoundError, RecordError, ValidationError):
        return ()
    except (OSError, PrivateStorageError):
        return None


def _history_for_write(home: Path, slug: str, number: int) -> tuple[SnapshotBinding, ...]:
    """The retained pairs a writer starts from.

    Raises ``OSError`` or ``PrivateStorageError`` when the file is there but cannot be read
    now, so the caller leaves it as it was. A file too large or outside the model is one
    this format never writes, and starts over, with a debug log.
    """
    try:
        body = read_bytes_bounded(home, source_pull_snapshots(slug, number), max_bytes=_MAX_BYTES)
    except FileNotFoundError:
        return ()
    except RecordError as exc:
        log.debug("discarding pull request %s's revision history: %s", number, exc)
        return ()
    try:
        return _BINDINGS.validate_json(body)[-_MAX_PAIRS:]
    except ValidationError as exc:
        log.debug("discarding pull request %s's revision history: %s", number, exc)
        return ()


def _save(
    home: Path,
    slug: str,
    number: int,
    previous: tuple[SnapshotBinding, ...],
    current: tuple[SnapshotBinding, ...],
) -> None:
    current = current[-_MAX_PAIRS:]
    if current != previous:
        write_private_file_atomic(
            home,
            source_pull_snapshots(slug, number),
            json.dumps([pair.model_dump() for pair in current], separators=(",", ":")).encode(),
        )


def retain_replaced_pair(
    home: Path, slug: str, store: str, current: PullRecord | RecordAbsence, record: PullRecord
) -> None:
    """Before *record* replaces *current*, keep *current*'s pair admitted for its reader.

    The history keeps only *record*'s reader's pairs. *current*'s pair is added only
    when no store has it yet: a pair already retained names the store that computed it,
    and *store* may be another. The caller holds the source alias publication lock.
    """
    previous = _history_for_write(home, slug, record.number)
    kept = tuple(pair for pair in previous if pair.reader == record.reader)
    comparison = current.comparison if isinstance(current, PullRecord) else None
    if (
        comparison is not None
        and isinstance(current, PullRecord)
        and current.reader == record.reader
        and not any((pair.base, pair.head) == (comparison.base, comparison.head) for pair in kept)
    ):
        kept = (
            *kept,
            SnapshotBinding(
                store=store, reader=current.reader, base=comparison.base, head=comparison.head
            ),
        )
    _save(home, slug, record.number, previous, kept)


def retain_snapshot_binding(home: Path, slug: str, store: str, record: PullRecord) -> None:
    """Retain *record*'s pair, computed in *store*, as the most recent.

    The caller holds the source alias publication lock.
    """
    comparison = record.comparison
    if comparison is None:
        return
    binding = SnapshotBinding(
        store=store, reader=record.reader, base=comparison.base, head=comparison.head
    )
    previous = _history_for_write(home, slug, record.number)
    current = (
        *(pair for pair in previous if pair.reader == binding.reader and pair != binding),
        binding,
    )
    _save(home, slug, record.number, previous, current)
