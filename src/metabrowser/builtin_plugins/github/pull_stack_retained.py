"""A stack's earlier comparisons, kept admitted after the stack moves, across restarts.

A stack's page keeps the comparison it drew when a member moves, and offers the new one
(docs/project/architecture/arch-github-pull-requests.md, "The Stack Page"). The parts it
loads later, a deferred file, its Docs, a rendered document, an image, name the drawn
pair, so the server must keep answering it, as a pull request's earlier pairs keep
answering (:mod:`.pull_snapshot_cache`).

``sources/<slug>/pulls/stack-<n>.snapshots.json`` keeps each pair the ``stack`` route
answered for stack *n*, most recent last: its two commits, its members' digest, and the
members themselves, from which ``stack-comparison`` lists that comparison again once the
process no longer holds it in memory. Each pair names the store that computed it and the
reader whose records named it, and is admitted only for that store and, once a reader is
observed, that reader.

Admission reads it with :func:`retained_stack_pair`, and the ``stack`` route's ``since``,
which says what moved since a drawn pair, with :func:`retained_stack_digest`. Both fail
closed: a file they cannot read now admits nothing and says so, and a malformed one retains
nothing. The ``stack``
route writes it when it answers a pair the file does not end with, by atomic replacement
under the source's alias lock, as every writer of the ``pulls`` directory does, so two
writers lose no pair and a cache clear removes the file whole.
"""

from __future__ import annotations

import json
import logging
import os
import threading
from collections import OrderedDict
from collections.abc import Callable
from pathlib import Path
from typing import TYPE_CHECKING, Annotated, Final, Literal

from pydantic import StringConstraints, TypeAdapter, ValidationError

from metabrowser.builtin_plugins.github.pull_record import Reader, Sha, _Model
from metabrowser.cache.atomic import RecordError, read_bytes_bounded
from metabrowser.cache.locks import source_alias_lock
from metabrowser.cache.paths import source_stack_snapshots
from metabrowser.home import PrivateStorageError, SharedEntryPolicy, write_private_file_atomic

if TYPE_CHECKING:
    from metabrowser.builtin_plugins.github.pull_stack import StackPair
    from metabrowser.cache.acquire import PublishedSource

log = logging.getLogger(__name__)

# How many earlier comparisons of one stack stay admitted: one per move, a member's push or
# a change to the member list. A page holds the one it drew, so this outlives seven moves
# while a page stays open on it.
MAX_RETAINED_STACK_PAIRS: Final = 8
# The file's read bound. Eight pairs of a 64-member stack with the longest fields the model
# accepts (64-hex IDs, a 103-character reader, a `sha256:` store ID, five-digit numbers)
# serialize to 79,089 bytes, and validating them took 0.5 ms (measured 2026-11-25,
# `timeit` over 200 runs, load average 229); the largest stack cached on 2026-11-24 had 46
# members (`MAX_KEPT_ANCESTRIES` in pull_stack.py). A stack too large for the bound keeps
# fewer pairs, and one whose single pair exceeds it, none.
_MAX_BYTES: Final = 128 * 1024

type _Digest = Annotated[str, StringConstraints(pattern=r"^[0-9a-f]{32}$")]
type _Identity = tuple[int, int, int, int]


class RetainedStackPair(_Model):
    store: str
    reader: Reader
    base: Sha
    head: Sha
    digest: _Digest
    # (number, merge base, head), bottom first, and whether the top head contains each.
    members: tuple[tuple[int, Sha, Sha], ...]
    in_top: tuple[bool, ...]


_PAIRS = TypeAdapter(tuple[RetainedStackPair, ...])

# The file each stack's pairs were last seen in, by its identity (device, inode,
# modification time, and size), and the pair it ends with: a page's poll, which answers the
# same pair each time, then costs one lstat and writes nothing, and a file that cache-clear
# removed or another writer replaced is read and written again.
_LAST: OrderedDict[tuple[str, str, int], tuple[str, str, str, _Identity]] = OrderedDict()
_LAST_LOCK: Final = threading.Lock()
_MAX_LAST: Final = 64


def _read(home: Path, slug: str, number: int, *, shared: SharedEntryPolicy) -> bytes:
    return read_bytes_bounded(
        home, source_stack_snapshots(slug, number), max_bytes=_MAX_BYTES, shared=shared
    )


def _identity(home: Path, slug: str, number: int) -> _Identity | None:
    try:
        status = os.lstat(home / source_stack_snapshots(slug, number))
    except OSError:
        return None
    return (status.st_dev, status.st_ino, status.st_mtime_ns, status.st_size)


def retain_stack_pair(published: PublishedSource, pair: StackPair, reader: str) -> None:
    """Keep *pair*, which the ``stack`` route answers now, as stack's most recent. Blocking:
    run it with :func:`~metabrowser.cache.locks.run_lock_section`.

    It writes under the source's alias lock, which every writer of the ``pulls`` directory
    takes (:func:`.pull_record.clear_pulls`). A file that cannot be read now is left as it
    was; one no writer of this format could have written starts over. A write that fails is
    logged and leaves admission as it was.
    """

    from metabrowser.builtin_plugins.github.pull_stack import StackPair as _Pair

    assert isinstance(pair, _Pair)
    home, slug, number = published.home, published.slug, pair.number
    seen = (str(home), slug, number)
    last = (published.store_id, reader, pair.digest)
    with _LAST_LOCK:
        known = _LAST.get(seen)
    if known is not None and known[:3] == last and known[3] == _identity(home, slug, number):
        with _LAST_LOCK:
            if seen in _LAST:
                _LAST.move_to_end(seen)
        return
    try:
        entry = RetainedStackPair(
            store=published.store_id,
            reader=reader,
            base=pair.base,
            head=pair.head,
            digest=pair.digest,
            members=pair.members,
            in_top=pair.in_top,
        )
    except ValidationError as exc:
        log.debug("not retaining stack %s's comparison: %s", number, exc)
        return
    try:
        with source_alias_lock(home, slug):
            _write(home, slug, number, entry)
            identity = _identity(home, slug, number)
    except (OSError, PrivateStorageError) as exc:
        log.debug("not retaining stack %s's comparison: %s", number, exc)
        return
    if identity is None:
        return
    with _LAST_LOCK:
        _LAST[seen] = (*last, identity)
        _LAST.move_to_end(seen)
        while len(_LAST) > _MAX_LAST:
            _LAST.popitem(last=False)


def _write(home: Path, slug: str, number: int, entry: RetainedStackPair) -> None:
    """End stack *number*'s file with *entry*, keeping its reader's earlier pairs within the
    bounds. Under the source's alias lock."""

    previous = _history_for_write(home, slug, number)
    kept = [old for old in previous if old.reader == entry.reader and old.digest != entry.digest]
    kept.append(entry)
    kept = kept[-MAX_RETAINED_STACK_PAIRS:]
    body = b""
    while kept:
        body = json.dumps(
            [old.model_dump(mode="json") for old in kept], separators=(",", ":")
        ).encode()
        if len(body) <= _MAX_BYTES:
            break
        kept = kept[1:]
    if kept and tuple(kept) != previous:
        write_private_file_atomic(home, source_stack_snapshots(slug, number), body)


def _history_for_write(home: Path, slug: str, number: int) -> tuple[RetainedStackPair, ...]:
    try:
        body = _read(home, slug, number, shared="repair")
    except FileNotFoundError:
        return ()
    except RecordError as exc:
        log.debug("discarding stack %s's retained comparisons: %s", number, exc)
        return ()
    try:
        return _PAIRS.validate_json(body)[-MAX_RETAINED_STACK_PAIRS:]
    except ValidationError as exc:
        log.debug("discarding stack %s's retained comparisons: %s", number, exc)
        return ()


def retained_stack_pair(
    published: PublishedSource,
    number: int,
    reader: str | None,
    base: str,
    head: str,
    digest: str | None,
) -> StackPair | Literal["unknown"] | None:
    """The retained pair of stack *number* with these commits, and *digest* when given, for
    this store and, when *reader* is given, that reader; ``unknown`` when the file is there
    but cannot be read now. Blocking and bounded."""

    return _retained(
        published,
        number,
        reader,
        lambda entry: (
            (entry.base, entry.head) == (base, head) and (digest is None or entry.digest == digest)
        ),
    )


def retained_stack_digest(
    published: PublishedSource, number: int, reader: str, digest: str
) -> StackPair | Literal["unknown"] | None:
    """The retained pair of stack *number* whose members' digest is *digest*, for this store
    and reader: the comparison a page drew, which the ``stack`` route's ``since`` names to
    say what moved since. ``unknown`` when the file is there but cannot be read now.
    Blocking and bounded."""

    return _retained(published, number, reader, lambda entry: entry.digest == digest)


def _retained(
    published: PublishedSource,
    number: int,
    reader: str | None,
    matches: Callable[[RetainedStackPair], bool],
) -> StackPair | Literal["unknown"] | None:
    from metabrowser.builtin_plugins.github.pull_stack import StackPair

    try:
        found = _PAIRS.validate_json(_read(published.home, published.slug, number, shared="refuse"))
    except (FileNotFoundError, RecordError, ValidationError):
        return None
    except (OSError, PrivateStorageError):
        return "unknown"
    for entry in reversed(found[-MAX_RETAINED_STACK_PAIRS:]):
        if (
            entry.store == published.store_id
            and (reader is None or entry.reader == reader)
            and matches(entry)
            and len(entry.members) == len(entry.in_top)
            and entry.members
        ):
            return StackPair(
                number, entry.base, entry.head, entry.digest, entry.members, entry.in_top
            )
    return None


__all__ = [
    "MAX_RETAINED_STACK_PAIRS",
    "RetainedStackPair",
    "retain_stack_pair",
    "retained_stack_digest",
    "retained_stack_pair",
]
