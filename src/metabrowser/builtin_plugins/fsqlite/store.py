"""An fsqlite store, read as a guest: recognition, the `current` pointer, and its snapshot.

An fsqlite store (the specification is
https://github.com/jlevy/fsqlite/blob/main/docs/fsql-format-spec.md, format `f1.0`) is a directory holding ``fsqlite.json``, whose ``current`` file names the
published version, an immutable SQLite file ``snapshots/<version>.fsqlite.sqlite`` with
the version zero-padded to 12 digits. Everything here is a reader's part of the protocol
(the spec's section 13, "Reader"): parse the marker and the pointer strictly, open only
the snapshot the pointer names, read-only, and never modify any store file. A reader may
take a read lease, which writes a file under ``leases/``; this one takes none, and no
lock either, so it never touches the store: a viewer opening a store changes nothing in
it. A snapshot that disappears between the pointer read and the open was collected by
garbage collection after a stale read, not corruption, so the pointer is read again
once (:data:`SNAPSHOT_READ_ATTEMPTS`).

The server reads the marker, the pointer, and the pending envelopes' directory; the
snapshot is read by a reader process through :mod:`metabrowser.sqlite_access` with
``immutable_content``, since a published snapshot never changes (the spec's S6).
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import uuid
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Final, Literal

# ── The format ─────────────────────────────────────────────────

MARKER_NAME: Final = "fsqlite.json"
CURRENT_NAME: Final = "current"
SNAPSHOTS_DIR: Final = "snapshots"
PENDING_DIR: Final = "tx/pending"
# The snapshot's SQLite `application_id`, ASCII "FSQL"
# (https://github.com/jlevy/fsqlite/blob/main/docs/application-id.md).
FSQLITE_APPLICATION_ID: Final = 0x4653514C
# The two tables every snapshot carries for the format's own use (the spec's S3): the
# idempotency ledger and the identity stamp. A table view groups them as internal.
RESERVED_TABLES: Final = frozenset({"applied_tx", "fsqlite_meta"})
# Digits of a snapshot's zero-padded version in its file name (the spec's section 2).
SNAPSHOT_DIGITS: Final = 12
# The pointer's content may be at most this many bytes (the spec's section 4); one more is read
# so a longer file is detected without loading it.
CURRENT_MAX_BYTES: Final = 64
# The greatest version a pointer may name, 2^53 - 1 (the spec's section 4).
CURRENT_MAX_VERSION: Final = 2**53 - 1
# The marker is a few hundred bytes (the spec's section 2 example is 140); one past this
# is invalid rather than parsed, so a crafted marker costs one bounded read.
MARKER_MAX_BYTES: Final = 64 * 1024
# Format versions this reader understands. A valid marker naming another is unsupported,
# not corrupt (the spec's M2); `f1.0` is the only version the format defines.
SUPPORTED_FORMAT_VERSIONS: Final = frozenset({"f1.0"})
# `required_features` this reader understands: none, since `f1.0` defines none, so a
# marker requiring any is unsupported (the spec's M5).
SUPPORTED_FEATURES: Final = frozenset[str]()
# How many times a snapshot is looked for: the pointer is read again once when the
# snapshot it named is gone, which garbage collection does to a superseded version
# after a stale read (the spec's section 13). A pointer that names a missing snapshot
# twice is corruption.
SNAPSHOT_READ_ATTEMPTS: Final = 2
# Entries of `tx/pending/` examined to count envelopes. An envelope is one directory
# per captured write until the next reconcile folds it in; past this many entries the
# count says it stopped (`complete: false`) rather than holding a request on a listing.
PENDING_SCAN_MAX: Final = 10_000

_FORMAT_VERSION = re.compile(r"f(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)")
_DIGITS = re.compile(rb"[0-9]+")
# ASCII whitespace as the spec's section 4 lists it; a byte order mark or a no-break space is
# not whitespace here.
_ASCII_WHITESPACE: Final = b" \t\n\v\f\r"
# Diagnostics quote at most this much of a malformed pointer (the spec's section 4).
_QUOTE_CHARS: Final = 32

type StoreState = Literal["invalid", "unsupported", "corrupt"]


class StoreError(Exception):
    """A store that cannot be read, and the state it is shown as (the spec's section 11).

    ``invalid``: the marker is malformed or names another format. ``unsupported``: a
    valid marker this reader does not understand. ``corrupt``: the pointer is missing,
    torn, or names a missing snapshot, or the snapshot is not an fsqlite snapshot.
    """

    def __init__(self, state: StoreState, message: str) -> None:
        super().__init__(message)
        self.state: StoreState = state


@dataclass(frozen=True, slots=True)
class Marker:
    """A valid ``fsqlite.json``: the format version and the store's identity."""

    format_version: str
    store_id: str
    required_features: tuple[str, ...]


def _quote(raw: bytes) -> str:
    text = "".join(
        chr(byte) if 0x20 <= byte < 0x7F and byte != 0x5C else f"\\x{byte:02x}"
        for byte in raw[:_QUOTE_CHARS]
    )
    return f"“{text}”" + ("…" if len(raw) > _QUOTE_CHARS else "")


def _is_uuid(text: str) -> bool:
    """Whether *text* is a UUID in its canonical hyphenated spelling, in either case."""
    try:
        return str(uuid.UUID(text)) == text.lower()
    except ValueError:
        return False


def parse_marker(raw: bytes) -> Marker:
    """The marker *raw* holds, under the spec's M1, M2, and M5.

    Raises :class:`StoreError`: ``invalid`` for a marker that is malformed or names
    another format, ``unsupported`` for a valid one naming a version or a required
    feature this reader does not understand. Unknown fields are ignored.
    """
    if len(raw) > MARKER_MAX_BYTES:
        raise StoreError("invalid", f"fsqlite.json is larger than {MARKER_MAX_BYTES:,} bytes.")
    try:
        document = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, ValueError) as exc:
        raise StoreError("invalid", "fsqlite.json is not valid JSON.") from exc
    if not isinstance(document, dict):
        raise StoreError("invalid", "fsqlite.json is not a JSON object.")
    if document.get("format") != "fsqlite":
        raise StoreError("invalid", "fsqlite.json names another format.")
    version = document.get("format_version")
    if not isinstance(version, str) or _FORMAT_VERSION.fullmatch(version) is None:
        raise StoreError("invalid", "fsqlite.json has no valid format_version.")
    features = document.get("required_features")
    if (
        not isinstance(features, list)
        or not all(isinstance(item, str) for item in features)
        or len(set(features)) != len(features)
    ):
        raise StoreError("invalid", "fsqlite.json's required_features is not a list of names.")
    store_id = document.get("store_id")
    if not isinstance(store_id, str) or not _is_uuid(store_id):
        raise StoreError("invalid", "fsqlite.json's store_id is not a UUID.")
    marker = Marker(version, store_id, tuple(features))
    if version not in SUPPORTED_FORMAT_VERSIONS:
        raise StoreError(
            "unsupported", f"This store's format {version} is newer than this reader knows."
        )
    unknown = [item for item in features if item not in SUPPORTED_FEATURES]
    if unknown:
        raise StoreError(
            "unsupported", f"This store requires features this reader lacks: {', '.join(unknown)}."
        )
    return marker


def parse_current(raw: bytes) -> int:
    """The version a ``current`` file's bytes name, parsed strictly (the spec's section 4).

    At most :data:`CURRENT_MAX_BYTES` bytes; after trimming ASCII whitespace, ASCII
    digits only, naming at most :data:`CURRENT_MAX_VERSION`. Anything else, empty
    content included, is ``corrupt``, never version 0.
    """
    if len(raw) > CURRENT_MAX_BYTES:
        raise StoreError(
            "corrupt", f"The current pointer is longer than {CURRENT_MAX_BYTES} bytes."
        )
    text = raw.strip(_ASCII_WHITESPACE)
    if _DIGITS.fullmatch(text) is None:
        raise StoreError("corrupt", f"The current pointer does not name a version: {_quote(raw)}.")
    version = int(text)
    if version > CURRENT_MAX_VERSION:
        raise StoreError("corrupt", "The current pointer names a version past 2^53 - 1.")
    return version


def snapshot_name(version: int) -> str:
    """The file name of version *version*'s snapshot under ``snapshots/``."""
    return f"{version:0{SNAPSHOT_DIGITS}d}.fsqlite.sqlite"


# ── Reading the store's files ──────────────────────────────────


def _read_bounded(path: Path, limit: int) -> bytes:
    """At most ``limit + 1`` bytes of *path*, so a longer file shows as longer."""
    with path.open("rb") as handle:
        return handle.read(limit + 1)


def read_marker(path: Path) -> Marker:
    """Read and parse the marker at *path*. Raises :class:`StoreError` or ``OSError``."""
    return parse_marker(_read_bounded(path, MARKER_MAX_BYTES))


def read_current(path: Path | None) -> int:
    """Read and parse the pointer at *path*, None when it is missing.

    A missing or unreadable pointer is ``corrupt``: a marked store whose pointer is gone
    has lost its head (the spec's section 3).
    """
    if path is None:
        raise StoreError("corrupt", "This store has no current pointer.")
    try:
        raw = _read_bounded(path, CURRENT_MAX_BYTES)
    except FileNotFoundError as exc:
        raise StoreError("corrupt", "This store has no current pointer.") from exc
    except OSError as exc:
        raise StoreError("corrupt", f"The current pointer cannot be read: {exc.strerror}") from exc
    return parse_current(raw)


def _file_identity(path: Path) -> str:
    info = os.stat(path)
    return f"{info.st_dev}:{info.st_ino}:{info.st_size}:{info.st_mtime_ns}"


def store_generation(marker: Path, current: Path, version: int) -> str:
    """A token that changes whenever the store's head may have changed.

    The version ``current`` names, then a hash of the identity, size, and modification
    time of ``fsqlite.json`` and ``current``: a publish replaces ``current`` by a rename,
    so its identity changes even when a version repeats after a repair, and a format
    upgrade replaces the marker the same way. The snapshot itself never changes, and
    pending envelopes change no snapshot, so neither is stat'ed. Raises ``OSError`` when
    a file is gone.
    """
    material = f"{_file_identity(marker)}|{_file_identity(current)}|{version}"
    return f"{version}-{hashlib.sha256(material.encode()).hexdigest()[:12]}"


@dataclass(frozen=True, slots=True)
class PendingCount:
    """The transaction envelopes waiting under ``tx/pending/`` for the next reconcile.

    ``committed`` envelopes hold their ``COMMITTED`` marker and are the store's
    accepted, unpublished tail (a ``live`` store); ``uncommitted`` ones are captures in
    flight or torn (the spec's section 5). ``complete`` is false when the scan stopped
    at :data:`PENDING_SCAN_MAX` entries.
    """

    committed: int
    uncommitted: int
    complete: bool


def count_pending(pending: Path | None) -> PendingCount:
    """Count the envelopes under *pending* (``tx/pending/``), None or missing for none.

    An envelope is a directory named ``<txid>.txn``; transients beside them
    (``.work-*`` working copies, ``*.tmp``) are not envelopes. Reads directory entries
    and one stat per envelope, never an envelope's files.
    """
    committed = uncommitted = 0
    if pending is None:
        return PendingCount(0, 0, True)
    try:
        entries = os.scandir(pending)
    except (FileNotFoundError, NotADirectoryError):
        return PendingCount(0, 0, True)
    with entries:
        for examined, entry in enumerate(entries):
            if examined >= PENDING_SCAN_MAX:
                return PendingCount(committed, uncommitted, False)
            name = entry.name
            if name.startswith(".") or not name.endswith(".txn"):
                continue
            try:
                if not entry.is_dir(follow_symlinks=False):
                    continue
            except OSError:
                continue
            if os.path.lexists(os.path.join(entry.path, "COMMITTED")):
                committed += 1
            else:
                uncommitted += 1
    return PendingCount(committed, uncommitted, True)


# ── Resolving and reading the snapshot ─────────────────────────


@dataclass(frozen=True, slots=True)
class Snapshot:
    """The snapshot a read used: the version the pointer named and its file."""

    version: int
    name: str
    path: Path
    attempts: int


class SnapshotGone(Exception):
    """The snapshot a read was given disappeared before it was opened."""


type Locate = Callable[[str], Path | None]


def read_snapshot[T](
    current: Path | None, locate: Locate, read: Callable[[Snapshot], T]
) -> tuple[T, Snapshot]:
    """Read the pointer, find the snapshot it names, and run *read* on it.

    *locate* maps a snapshot's name to its path under ``snapshots/`` through the
    caller's safe-path gate, None when nothing is there. *read* raises
    :class:`SnapshotGone` when the file it was given disappeared before it opened it.
    A snapshot that is missing, at either point, sends the read back to the pointer
    once, since garbage collection may have collected a version a stale pointer named;
    a pointer that names a missing snapshot every time is ``corrupt``.
    """
    missing = ""
    for attempt in range(1, SNAPSHOT_READ_ATTEMPTS + 1):
        version = read_current(current)
        name = snapshot_name(version)
        path = locate(name)
        missing = f"The current pointer names version {version}, whose snapshot {name} is missing."
        if path is None or not path.is_file():
            continue
        snapshot = Snapshot(version, name, path, attempt)
        try:
            return read(snapshot), snapshot
        except SnapshotGone:
            continue
    raise StoreError("corrupt", missing)


def check_application_id(application_id: int) -> None:
    """Raise ``corrupt`` unless *application_id* is fsqlite's (the spec's S2)."""
    if application_id != FSQLITE_APPLICATION_ID:
        raise StoreError(
            "corrupt",
            f"The snapshot's application_id is {application_id:#010x}, not fsqlite's "
            f"{FSQLITE_APPLICATION_ID:#010x} (“FSQL”).",
        )
