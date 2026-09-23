"""Immutable Git-tree source: GitPath, revision subject, and batch blob reads.

Reads go through a worktree-free ``RepositoryStoreTarget``. This module
does not check out, index, branch, or invent filesystem facts. Batch
``cat-file`` actors are pooled per store (at most
:data:`MAX_BATCH_READERS_PER_STORE` in one process). Git discovery,
history, refs, commit detail, file, raw, tree, diffs, KPress, patch-file
containers, binary byte chunks, plugin kinds from identity and bounded
JSON/YAML/frontmatter bytes, structured parsed, agent-log JSONL, and
``GitDiffSource.content`` honor a pinned revision. ``/view/`` accepts a
``GitPath`` wire on that pin. ``/api/tree`` also projects a SPA ``tree``
array of GitPath nav nodes. A Git tree ``/api/file`` envelope is SPA
``folder`` chrome. A direct-child README blob mounts Overview. A complete
blob-size tally also mounts treemap; ``/api/rollup`` answers from the same
recursive index and omits mtime. ``/api/catalog`` lists those blob names
as Quick File rows. ``/api/index/progress``, ``/api/index/meta``, and
``/api/capabilities`` report that complete-at-once index without a watcher
or invented mtime. ``/api/tree`` also carries whole-tree ``extensions``,
``canonical_extensions``, ``type_families``, and ``type_presets`` rows plus
``tally_cache_status`` and, when blob sizes are complete, a ``summary`` from
that index. ``types`` and ``min_size`` keep ancestor trees of matching blobs
and emit subtree ``filtered`` totals. Type matching uses the same bounded
compound-tail logical extension as filesystem inventory. ``include_ignored=0`` is a
no-op because ignore is absent. SPA file nodes and blob ``/api/file``
envelopes emit that tail as ``ext``; ``logical_ext`` is only the inner
extension of a compressed name on tree nodes. Blob file envelopes omit
compressed identity because blobs are stored bytes with no gzip smudge.
Markdown blob envelopes include parsed YAML ``frontmatter`` and
``frontmatter_error``. Text blobs use the same first-window and highlight
bound as filesystem listings. A Git image blob is SPA ``image`` chrome;
``/raw`` serves the stored bytes. ``/api/file``, ``/raw``, KPress, and plugin
sidekicks follow in-tree relative symlink blobs. ``depth`` nests SPA children the way filesystem
listings do (default 2) and emits a lazy sentinel past the cap. SPA path chrome decodes GitPath wires to
display names; C0 and invalid UTF-8 become U+FFFD. Blob listings
carry ``cat-file`` info sizes so ``min_size`` can filter; trees and gitlinks
have no blob size. Recursive ``ls-tree -r`` plus ``cat-file`` info fills
directory ``total_files`` / ``total_size``; a truncated listing or a missing
blob size omits the incomplete dimension. Omitted mtime still leaves age
chrome empty rather than pending.
Markdown and wiki destinations encode authored segments
as GitPath wires. An LFS pointer is the stored pointer bytes;
a blob the tree names but the store lacks is ``object_unavailable``.
The CLI can attach a ``file://`` pin for ``--show`` and ``--api``.
Serving acquired Git over a listening port stays on a later bead.
"""

from __future__ import annotations

import asyncio
import base64
import re
import threading
from array import array
from bisect import bisect_left
from collections import OrderedDict
from collections.abc import AsyncGenerator, Callable, Coroutine, Hashable, Mapping, Sequence
from contextlib import asynccontextmanager, suppress
from dataclasses import dataclass, field, replace
from pathlib import Path
from types import MappingProxyType
from typing import Any, Final, Literal, cast

from metabrowser.content_errors import ContentUnavailableError
from metabrowser.git.process import (
    BATCH_OBJECT_POLICY,
    GIT_DISABLE_MAILMAP_ARGS,
    STORE_READ_POLICY,
    GitCommandError,
    GitCommandTarget,
    GitError,
    GitOutputTooLargeError,
    GitTimeoutError,
    RepositoryStoreTarget,
    run_git,
    spawn_git_process,
    terminate_git_process,
)
from metabrowser.git.wire import is_full_revision
from metabrowser.settings import INVENTORY_MAX_FILES, TEXT_PREVIEW_REQUEST_MAX_BYTES
from metabrowser.source import (
    MAX_CONTAINER_INNER_DEPTH,
    ContentHandle,
    ContentRef,
    ContentSource,
    ContentStat,
    ContentWindow,
    RepositorySubjectKind,
    SourceCapabilities,
)

_B64_ALPHABET = frozenset("ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-_")
_MAILMAP_ARGS = GIT_DISABLE_MAILMAP_ARGS
_BATCH_ARGS: Final[tuple[str, ...]] = (
    *_MAILMAP_ARGS,
    "cat-file",
    "--batch-command",
    "--buffer",
)
# Whole-tree reads peaked at four actors and fell with eight. See
# docs/project/architecture/arch-repository-sources-and-provider-mirrors.md.
MAX_BATCH_READERS_PER_STORE: Final[int] = 4
# ``info`` commands per flush. Each chunk gets the batch deadline to itself, so
# the deadline bounds a stalled actor rather than the size of the tree. Measured
# over 100,000 packed blobs: 4 to 8 us per object, and chunking at this size
# adds about 0.2 s to the whole read. The slowest rate measured in review, a
# cold loose-object store at 160 us per object, puts one chunk at 1.6 s, a
# ninth of the 15 s deadline. A chunk also caps the commands buffered before a
# flush at under 0.5 MiB.
INFO_MANY_CHUNK_OBJECTS: Final[int] = 10_000
# A windowed blob read streams the object from its start, since ``cat-file`` has no
# byte ranges. Past the window it either drains the rest, which keeps the actor, or
# terminates the actor, which costs the next read a respawn. Measured on a packed
# store on macOS at load average 8 to 23: a respawn cost 4.0 ms and a terminate 0.5 ms,
# while draining ran near 1.1 GiB/s (a 64 MiB blob in about 55 ms), so abandoning pays
# off past about 4.5 MiB. Terminating is what makes a first window cheap: 2 MiB of a
# 256 MiB blob took 39 to 45 ms, against 1.1 s drained and 1.0 s read whole.
BLOB_WINDOW_DRAIN_MAX_BYTES: Final[int] = 4 * 1024 * 1024
_STREAM_CHUNK_BYTES: Final[int] = 1024 * 1024
_FULL_OID: Final = re.compile(r"\b(?:[0-9a-f]{64}|[0-9a-f]{40})\b")
# Facts memoized per pinned source: index chrome, index facts, extensions, the
# catalog body, and one entry per recently used filter or rollup shape. Each is
# at most linear in INVENTORY_MAX_FILES; the largest measured, the rendered
# catalog body of a 100,000-blob tree, is 9.0 MB; a filter's running totals are
# three 8-byte sums per blob. The bound keeps a client that cycles through
# filters and rollup shapes from growing the process.
MAX_DERIVED_FACTS: Final[int] = 32
_POOLS_GUARD = threading.Lock()
_POOLS: dict[Path, _StoreReaderPool] = {}


class GitPathError(ValueError):
    """A GitPath wire token or segment is not a lossless byte identity."""


class GitObjectUnavailableError(GitError, ContentUnavailableError):
    """The store does not have this object."""

    code = "object_unavailable"
    http_status = 404

    def __init__(self, oid: str) -> None:
        self.oid = oid
        super().__init__(f"object_unavailable: {oid}")


class GitBlobTooLargeError(GitError):
    """``info`` declared a blob larger than the preview/raw bound."""

    code = "blob_too_large"
    http_status = 413

    def __init__(self, *, oid: str, size: int, max_bytes: int) -> None:
        self.oid = oid
        self.size = size
        self.max_bytes = max_bytes
        super().__init__(f"blob {oid} is {size} bytes; limit is {max_bytes}")


class GitBatchProtocolError(GitError):
    """The cat-file actor returned a truncated or unexpected frame."""


def display_segment(segment: bytes) -> str:
    """Replacement-safe UTF-8. C0 and DEL become U+FFFD so chrome cannot wrap."""

    text = segment.decode("utf-8", "replace")
    return "".join("\ufffd" if ord(ch) < 32 or ch == "\x7f" else ch for ch in text)


def _b64encode(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).decode("ascii").rstrip("=")


def _b64decode(text: str) -> bytes:
    if not text or any(char not in _B64_ALPHABET for char in text):
        raise GitPathError("GitPath atom is not canonical unpadded base64url")
    padding = "=" * (-len(text) % 4)
    try:
        raw = base64.urlsafe_b64decode(text + padding)
    except Exception as exc:
        raise GitPathError("GitPath atom is not canonical unpadded base64url") from exc
    if _b64encode(raw) != text:
        raise GitPathError("GitPath atom is not canonical unpadded base64url")
    return raw


def require_full_oid(value: str) -> str:
    if not is_full_revision(value):
        raise GitPathError("Git object id must be a full lowercase SHA-1 or SHA-256")
    return value


@dataclass(frozen=True, slots=True, order=True)
class GitPath:
    """Raw non-NUL Git tree segments. Never a host ``Path``."""

    segments: tuple[bytes, ...]

    def __post_init__(self) -> None:
        for segment in self.segments:
            if not segment or b"\x00" in segment or b"/" in segment:
                raise GitPathError("GitPath segments must be non-empty and free of NUL and '/'")

    @classmethod
    def root(cls) -> GitPath:
        return cls(())

    @classmethod
    def from_segments(cls, *names: bytes) -> GitPath:
        return cls(names)

    def child(self, name: bytes) -> GitPath:
        return GitPath((*self.segments, name))

    def parent(self) -> GitPath:
        if not self.segments:
            return self
        return GitPath(self.segments[:-1])

    def to_wire(self) -> str:
        return "/".join(f"g1-{_b64encode(segment)}" for segment in self.segments)

    @classmethod
    def from_wire(cls, wire: str) -> GitPath:
        if wire == "":
            return cls.root()
        parts = wire.split("/")
        segments: list[bytes] = []
        for part in parts:
            if not part.startswith("g1-"):
                raise GitPathError("GitPath wire tokens must use the g1- role prefix")
            segments.append(_b64decode(part[3:]))
        return cls(tuple(segments))

    @classmethod
    def from_display(cls, selection: str) -> GitPath:
        """Slash-separated display names, or an already-encoded GitPath wire.

        ``.`` and the empty string are the tree root. ``..`` is refused so a
        CLI spelling cannot look like a host path escape. POSIX undecodable
        bytes stay surrogate-escaped at the CLI boundary.
        """

        text = selection
        if text in {"", ".", "/"}:
            return cls.root()
        parts = text.split("/")
        if parts and all(part.startswith("g1-") for part in parts):
            return cls.from_wire(text)
        segments: list[bytes] = []
        for part in parts:
            if part in {"", ".", ".."}:
                raise GitPathError("GitPath display segments cannot be empty, '.', or '..'")
            if "\\" in part or "\0" in part:
                raise GitPathError("GitPath display segments cannot contain NUL or '\\\\'")
            segments.append(part.encode("utf-8", "surrogateescape"))
        return cls(tuple(segments))

    def display(self) -> str:
        return "/".join(display_segment(segment) for segment in self.segments)


# Relative in-tree symlink hops per resolution on file/raw/KPress/sidekicks, counting
# links met partway through a target. Listings still show the link.
_MAX_GIT_SYMLINK_FOLLOW = 8
# Linux ``PATH_MAX``. ``symlink(2)`` refuses a longer target with ``ENAMETOOLONG``, so
# a checkout could not hold such a link either. It also bounds resolution work, which
# is one lookup per component in the directory already in hand. Measured on macOS
# under load: a 4091-byte ``a/..`` body at depth 200 took 0.14 s, and eight such links
# chained took 0.88 s, with no loop stall over 15 ms. Walking from the root per
# component had taken 12 s and 97 s for the same two cases.
_MAX_GIT_SYMLINK_BODY_BYTES = 4096


def split_git_container_wire(wire: str) -> tuple[GitPath, str]:
    """Split a request identity into a GitPath prefix and a container inner path.

    ``g1-`` tokens are the Git tree address. Anything after the last
    contiguous ``g1-`` prefix is a virtual inner path owned by a container
    blob, not another tree segment.
    """

    if wire == "":
        return GitPath.root(), ""
    parts = wire.split("/")
    cut = 0
    while cut < len(parts) and parts[cut].startswith("g1-"):
        cut += 1
    if cut == 0:
        raise GitPathError("GitPath wire tokens must use the g1- role prefix")
    return GitPath.from_wire("/".join(parts[:cut])), "/".join(parts[cut:])


GitEntryKind = Literal["blob", "tree", "commit"]


@dataclass(frozen=True, slots=True)
class GitTreeEntry:
    path: GitPath
    mode: str
    kind: GitEntryKind
    oid: str
    size: int | None = None

    @property
    def is_tree(self) -> bool:
        return self.kind == "tree"

    @property
    def is_blob(self) -> bool:
        return self.kind == "blob"

    @property
    def is_gitlink(self) -> bool:
        return self.kind == "commit"

    @property
    def is_symlink(self) -> bool:
        return self.mode == "120000"


def _tree_entry_name(entry: GitTreeEntry) -> bytes:
    return entry.path.segments[-1]


def _reparent_tree_entries(
    entries: tuple[GitTreeEntry, ...], parent: GitPath
) -> tuple[GitTreeEntry, ...]:
    """Rebuild cached names under *parent*. Tree OIDs are path-independent."""

    return tuple(replace(entry, path=parent.child(_tree_entry_name(entry))) for entry in entries)


@dataclass(frozen=True, slots=True)
class _CachedTree:
    """One tree object's children, recorded under the first path that listed it.

    A tree OID is path-independent, so two paths can share one record. A lookup
    by name reparents only its hit. A listing under another path rebuilds the
    names, which is linear in the listing it returns.
    """

    parent: GitPath
    entries: tuple[GitTreeEntry, ...]
    by_name: Mapping[bytes, GitTreeEntry]

    def listed_under(self, parent: GitPath) -> tuple[GitTreeEntry, ...]:
        if parent == self.parent:
            return self.entries
        return _reparent_tree_entries(self.entries, parent)

    def child(self, path: GitPath) -> GitTreeEntry | None:
        entry = self.by_name.get(path.segments[-1])
        if entry is None or entry.path == path:
            return entry
        return replace(entry, path=path)


@dataclass(frozen=True, slots=True)
class GitTreeTally:
    """Descendant blob count and size under one tree.

    ``total_size`` is ``None`` when any counted blob is missing from the store.
    """

    total_files: int
    total_size: int | None


class GitBlobTallies:
    """Running file and byte counts over an index's sorted blobs.

    A pin is immutable, so the sums are built once. A subtree is a contiguous
    span of the sorted names, which makes its tally two subtractions instead of
    a walk over its blobs. *matches* keeps only the selected blobs, for a filter.
    """

    __slots__ = ("_files", "_sizes", "_unsized")

    def __init__(
        self,
        blobs: Sequence[tuple[bytes, str]],
        sizes: Mapping[str, int],
        matches: Sequence[int] | None = None,
    ) -> None:
        files = array("q", [0])
        total = array("q", [0])
        unsized = array("q", [0])
        file_count = byte_count = unsized_count = 0
        for position, (_name, oid) in enumerate(blobs):
            if matches is None or matches[position]:
                file_count += 1
                size = sizes.get(oid)
                if size is None:
                    unsized_count += 1
                else:
                    byte_count += size
            files.append(file_count)
            total.append(byte_count)
            unsized.append(unsized_count)
        self._files = files
        self._sizes = total
        self._unsized = unsized

    def tally(self, spans: Sequence[tuple[int, int]]) -> GitTreeTally:
        files = size = unsized = 0
        for start, stop in spans:
            files += self._files[stop] - self._files[start]
            size += self._sizes[stop] - self._sizes[start]
            unsized += self._unsized[stop] - self._unsized[start]
        return GitTreeTally(files, None if unsized else size)


@dataclass(frozen=True, slots=True)
class GitBlobIndex:
    """Recursive blob names under one tree, with ``cat-file`` sizes when known."""

    blobs: tuple[tuple[bytes, str], ...]
    sizes: Mapping[str, int]
    tallies: GitBlobTallies = field(init=False, repr=False, compare=False)

    def __post_init__(self) -> None:
        ordered = tuple(sorted(self.blobs, key=lambda item: item[0]))
        if ordered != self.blobs:
            object.__setattr__(self, "blobs", ordered)
        object.__setattr__(self, "tallies", GitBlobTallies(self.blobs, self.sizes))

    def iter_blobs(self, prefix: bytes = b"") -> tuple[tuple[bytes, str], ...]:
        """Blobs named ``prefix`` or under ``prefix/``. Shared string prefixes are excluded."""

        if not prefix:
            return self.blobs
        ranges: list[tuple[bytes, str]] = []
        for start, stop in self.prefix_spans(prefix):
            ranges.extend(self.blobs[start:stop])
        return tuple(ranges)

    def tally(self, prefix: bytes = b"") -> GitTreeTally:
        return self.tallies.tally(self.prefix_spans(prefix))

    def prefix_spans(self, prefix: bytes) -> tuple[tuple[int, int], ...]:
        """Sorted half-open spans for an exact blob and its ``prefix/`` children.

        ``docs`` matches ``docs`` and ``docs/a`` and does not match ``docs!`` or
        ``documentation``. The spans are adjacent slices of the sorted name list.
        """

        if not prefix:
            return ((0, len(self.blobs)),)
        exact = bisect_left(self.blobs, (prefix, ""))
        spans: list[tuple[int, int]] = []
        if exact < len(self.blobs) and self.blobs[exact][0] == prefix:
            spans.append((exact, exact + 1))
        child_lo = bisect_left(self.blobs, (prefix + b"/", ""))
        # '/' is 0x2F and '0' is the next byte, so this is the first name after
        # every ``prefix/`` child.
        child_hi = bisect_left(self.blobs, (prefix + b"0", ""))
        if child_lo < child_hi:
            spans.append((child_lo, child_hi))
        return tuple(spans)


GIT_REVISION_CAPABILITIES = SourceCapabilities(
    navigation=True,
    index=True,
    recency=False,
    ignore=False,
    watcher=False,
    activity=False,
    mutation=False,
)


@dataclass(frozen=True, slots=True)
class _ObjectInfo:
    oid: str
    kind: str
    size: int


class _BatchObjectReader:
    """One exclusive ``cat-file --batch-command --buffer`` actor."""

    def __init__(self, target: RepositoryStoreTarget) -> None:
        self._target = target
        self._proc: asyncio.subprocess.Process | None = None
        self._stderr_task: asyncio.Task[None] | None = None
        self._closed = False

    async def info(self, oid: str) -> _ObjectInfo:
        result = await self._transact(oid, contents=False)
        if not isinstance(result, _ObjectInfo):
            raise GitBatchProtocolError("info transaction returned a body")
        return result

    async def info_many(self, oids: tuple[str, ...]) -> dict[str, _ObjectInfo | None]:
        """``info`` for many objects, one flush per chunk. A missing object is ``None``."""

        unique: list[str] = []
        seen: set[str] = set()
        for oid in oids:
            require_full_oid(oid)
            if oid not in seen:
                seen.add(oid)
                unique.append(oid)
        found: dict[str, _ObjectInfo | None] = {}
        for start in range(0, len(unique), INFO_MANY_CHUNK_OBJECTS):
            chunk = tuple(unique[start : start + INFO_MANY_CHUNK_OBJECTS])
            found.update(await self._info_chunk(chunk))
        return found

    async def _info_chunk(self, oids: tuple[str, ...]) -> dict[str, _ObjectInfo | None]:
        """One flush under one deadline, so a whole tree never shares a fixed budget."""

        return await self._within_deadline(self._info_many_inner(oids))

    async def _info_many_inner(self, oids: tuple[str, ...]) -> dict[str, _ObjectInfo | None]:
        reader, writer = await self._pipes()
        for oid in oids:
            writer.write(f"info {oid}\n".encode("ascii"))
        writer.write(b"flush\n")
        await writer.drain()
        found: dict[str, _ObjectInfo | None] = {}
        for oid in oids:
            header = await _read_header(reader)
            parts = header.split(b" ")
            if len(parts) == 2 and parts[1] == b"missing":
                found[oid] = None
                continue
            found[oid] = _parse_info_header(oid, header)
        return found

    async def read_blob(self, oid: str, *, max_blob_bytes: int) -> bytes:
        info = await self.info(oid)
        if info.kind != "blob":
            raise GitBatchProtocolError(f"{oid} is {info.kind}, not a blob")
        if info.size > max_blob_bytes:
            raise GitBlobTooLargeError(oid=oid, size=info.size, max_bytes=max_blob_bytes)
        body = await self._transact(oid, contents=True, expected=info)
        if isinstance(body, _ObjectInfo):
            raise GitBatchProtocolError("contents transaction returned info")
        return body

    async def read_blob_window(self, oid: str, *, offset: int, max_bytes: int) -> tuple[bytes, int]:
        """At most *max_bytes* of blob *oid* from *offset*, and the blob's size.

        ``cat-file`` addresses objects, not byte ranges, so the blob streams from its
        start like a compressed artifact: the bytes before *offset* are read and
        dropped, the window is kept, and nothing past it is held. A remainder up to
        :data:`BLOB_WINDOW_DRAIN_MAX_BYTES` is drained so the actor stays usable; past
        that the actor is terminated and the next transaction starts a new one.
        """

        require_full_oid(oid)
        if offset < 0 or max_bytes < 0:
            raise ValueError("blob window offset and size cannot be negative")
        return await self._within_deadline(self._read_blob_window_inner(oid, offset, max_bytes))

    async def _read_blob_window_inner(
        self, oid: str, offset: int, max_bytes: int
    ) -> tuple[bytes, int]:
        reader, writer = await self._pipes()
        writer.write(f"contents {oid}\nflush\n".encode("ascii"))
        await writer.drain()
        info = _parse_info_header(oid, await _read_header(reader))
        if info.kind != "blob":
            # Its body is still in the pipe, so the actor is discarded.
            raise GitBatchProtocolError(f"{oid} is {info.kind}, not a blob")
        start = min(offset, info.size)
        stop = min(start + max_bytes, info.size)
        await _discard_exactly(reader, start)
        window = await reader.readexactly(stop - start)
        remainder = info.size - stop
        if remainder > BLOB_WINDOW_DRAIN_MAX_BYTES:
            await self._poison()
            return window, info.size
        await _discard_exactly(reader, remainder)
        if await reader.readexactly(1) != b"\n":
            raise GitBatchProtocolError("contents frame is missing the trailing newline")
        return window, info.size

    async def read_tree(self, oid: str) -> bytes:
        """Raw tree object bytes: one actor round trip, not an ``ls-tree`` spawn.

        The header is checked before the body is read. A refused frame leaves
        its body in the pipe, so the actor is discarded like any framing error.
        """

        body = await self._transact(oid, contents=True, tree=True)
        if isinstance(body, _ObjectInfo):
            raise GitBatchProtocolError("contents transaction returned info")
        return body

    async def aclose(self) -> None:
        """Terminate the actor for good. A later transaction fails instead of respawning."""

        self._closed = True
        await self._poison()

    async def _within_deadline[T](self, transaction: Coroutine[Any, Any, T]) -> T:
        """Run one transaction under the batch deadline; discard the actor if it fails.

        A missing object is a complete frame, so the actor survives it. Anything else
        can leave part of a frame in the pipe.
        """

        try:
            return await asyncio.wait_for(transaction, timeout=BATCH_OBJECT_POLICY.timeout_s)
        except TimeoutError as exc:
            await self._poison()
            raise GitTimeoutError() from exc
        except asyncio.CancelledError:
            await self._poison()
            raise
        except GitObjectUnavailableError:
            raise
        except (BrokenPipeError, ConnectionResetError, asyncio.IncompleteReadError) as exc:
            await self._poison()
            raise GitBatchProtocolError("cat-file actor framing failed") from exc
        except Exception:
            await self._poison()
            raise

    async def _pipes(self) -> tuple[asyncio.StreamReader, asyncio.StreamWriter]:
        await self._ensure()
        proc = self._proc
        writer = None if proc is None else proc.stdin
        reader = None if proc is None else proc.stdout
        if proc is None or writer is None or reader is None:
            raise GitBatchProtocolError("cat-file actor has no pipes")
        return reader, writer

    async def _transact(
        self,
        oid: str,
        *,
        contents: bool,
        expected: _ObjectInfo | None = None,
        tree: bool = False,
    ) -> _ObjectInfo | bytes:
        require_full_oid(oid)
        return await self._within_deadline(
            self._transact_inner(oid, contents=contents, expected=expected, tree=tree)
        )

    async def _transact_inner(
        self,
        oid: str,
        *,
        contents: bool,
        expected: _ObjectInfo | None,
        tree: bool,
    ) -> _ObjectInfo | bytes:
        reader, writer = await self._pipes()
        command = "contents" if contents else "info"
        writer.write(f"{command} {oid}\nflush\n".encode("ascii"))
        await writer.drain()
        info = _parse_info_header(oid, await _read_header(reader))
        if not contents:
            return info
        if expected is not None and (info.oid != expected.oid or info.size != expected.size):
            raise GitBatchProtocolError("contents header does not match info")
        if tree:
            if info.kind != "tree":
                raise GitBatchProtocolError(f"{oid} is {info.kind}, not a tree")
            if info.size > BATCH_OBJECT_POLICY.max_bytes:
                raise GitOutputTooLargeError(
                    f"tree {oid} is {info.size} bytes; limit is {BATCH_OBJECT_POLICY.max_bytes}"
                )
        body = await reader.readexactly(info.size)
        trailer = await reader.readexactly(1)
        if trailer != b"\n":
            raise GitBatchProtocolError("contents frame is missing the trailing newline")
        return body

    async def _ensure(self) -> None:
        if self._closed:
            # A request can still hold this actor when its pool closes. Spawning
            # here would start a process that no pool owns or terminates.
            raise GitBatchProtocolError("batch reader is closed")
        proc = self._proc
        if proc is not None and proc.returncode is None:
            return
        await self._poison()
        self._proc = await spawn_git_process(
            _BATCH_ARGS,
            target=self._target,
            policy=BATCH_OBJECT_POLICY,
            pipe_stdin=True,
        )
        self._stderr_task = asyncio.create_task(_drain_stderr(self._proc))

    async def _poison(self) -> None:
        proc = self._proc
        self._proc = None
        task = self._stderr_task
        self._stderr_task = None
        if proc is not None:
            await terminate_git_process(proc)
        if task is not None:
            task.cancel()
            with suppress(asyncio.CancelledError, Exception):
                await task


class _StoreReaderPool:
    """At most ``MAX_BATCH_READERS_PER_STORE`` actors, shared by every source on a store."""

    def __init__(self, target: RepositoryStoreTarget) -> None:
        self._target = target
        self._available: asyncio.Queue[_BatchObjectReader] = asyncio.Queue()
        self._readers: list[_BatchObjectReader] = []
        self._create_lock = asyncio.Lock()
        self._closed = False
        self._holders = 0

    @asynccontextmanager
    async def checkout(self) -> AsyncGenerator[_BatchObjectReader]:
        reader = await self._acquire()
        try:
            yield reader
        finally:
            await self._release(reader)

    async def aclose(self) -> None:
        self._closed = True
        for reader in self._readers:
            await reader.aclose()
        self._readers.clear()
        while True:
            try:
                self._available.get_nowait()
            except asyncio.QueueEmpty:
                break

    async def _acquire(self) -> _BatchObjectReader:
        if self._closed:
            raise GitBatchProtocolError("batch reader pool is closed")
        try:
            return self._available.get_nowait()
        except asyncio.QueueEmpty:
            pass
        async with self._create_lock:
            if len(self._readers) < MAX_BATCH_READERS_PER_STORE:
                reader = _BatchObjectReader(self._target)
                self._readers.append(reader)
                return reader
        return await self._available.get()

    async def _release(self, reader: _BatchObjectReader) -> None:
        if self._closed:
            await reader.aclose()
            return
        await self._available.put(reader)


def _pool_key(target: RepositoryStoreTarget) -> Path:
    return target.git_dir.resolve()


def _retain_pool(target: RepositoryStoreTarget) -> _StoreReaderPool:
    key = _pool_key(target)
    with _POOLS_GUARD:
        pool = _POOLS.get(key)
        if pool is None:
            pool = _StoreReaderPool(target)
            _POOLS[key] = pool
        pool._holders += 1
        return pool


async def _release_pool(pool: _StoreReaderPool) -> None:
    close = False
    with _POOLS_GUARD:
        pool._holders -= 1
        if pool._holders <= 0:
            pool._holders = 0
            key = _pool_key(pool._target)
            if _POOLS.get(key) is pool:
                del _POOLS[key]
            close = True
    if close:
        await pool.aclose()


def store_batch_reader_count(target: RepositoryStoreTarget) -> int:
    """Live cat-file actors for *target*'s store in this process."""

    with _POOLS_GUARD:
        pool = _POOLS.get(_pool_key(target))
        return 0 if pool is None else len(pool._readers)


async def read_store_blob(
    target: RepositoryStoreTarget,
    oid: str,
    *,
    max_blob_bytes: int = TEXT_PREVIEW_REQUEST_MAX_BYTES,
) -> bytes:
    """Read one blob through the shared per-store cat-file pool.

    Callers that are not a live ``GitTreeSource`` still share the pool and
    the size gate. The retain/release pair closes the pool when nothing
    else holds it.
    """

    pool = _retain_pool(target)
    try:
        async with pool.checkout() as reader:
            return await reader.read_blob(require_full_oid(oid), max_blob_bytes=max_blob_bytes)
    finally:
        await _release_pool(pool)


async def _drain_stderr(proc: asyncio.subprocess.Process) -> None:
    """Read and drop an actor's stderr, so a chatty Git never blocks on a full pipe."""

    stream = proc.stderr
    if stream is None:
        return
    while await stream.read(65536):
        pass


async def _discard_exactly(reader: asyncio.StreamReader, count: int) -> None:
    """Read and drop *count* bytes without holding more than one chunk of them."""

    while count > 0:
        count -= len(await reader.readexactly(min(count, _STREAM_CHUNK_BYTES)))


async def _read_header(reader: asyncio.StreamReader) -> bytes:
    line = await reader.readline()
    if not line.endswith(b"\n"):
        raise GitBatchProtocolError("truncated cat-file header")
    return line[:-1]


def _parse_info_header(oid: str, header: bytes) -> _ObjectInfo:
    parts = header.split(b" ")
    if len(parts) == 2 and parts[1] == b"missing":
        raise GitObjectUnavailableError(oid)
    if len(parts) != 3:
        raise GitBatchProtocolError("unexpected cat-file info header")
    reported, kind_b, size_b = parts
    reported_oid = reported.decode("ascii", errors="replace")
    kind = kind_b.decode("ascii", errors="replace")
    if reported_oid != oid:
        raise GitBatchProtocolError("cat-file info oid mismatch")
    try:
        size = int(size_b)
    except ValueError as exc:
        raise GitBatchProtocolError("cat-file info size is not an integer") from exc
    if size < 0:
        raise GitBatchProtocolError("cat-file info size is negative")
    return _ObjectInfo(oid=oid, kind=kind, size=size)


def _iter_ls_tree_records(payload: bytes) -> tuple[tuple[str, GitEntryKind, str, bytes], ...]:
    records: list[tuple[str, GitEntryKind, str, bytes]] = []
    offset = 0
    length = len(payload)
    while offset < length:
        nul = payload.find(b"\x00", offset)
        if nul < 0:
            raise GitBatchProtocolError("ls-tree frame is not NUL-terminated")
        record = payload[offset:nul]
        offset = nul + 1
        tab = record.find(b"\t")
        if tab < 0:
            raise GitBatchProtocolError("ls-tree record is missing a name")
        meta = record[:tab]
        name = record[tab + 1 :]
        try:
            mode_b, kind_b, oid_b = meta.split(b" ", 2)
        except ValueError as exc:
            raise GitBatchProtocolError("ls-tree record is missing mode, type, or oid") from exc
        mode = mode_b.decode("ascii", errors="replace")
        kind = kind_b.decode("ascii", errors="replace")
        oid = oid_b.decode("ascii", errors="replace")
        if kind not in ("blob", "tree", "commit") or not is_full_revision(oid):
            raise GitBatchProtocolError("ls-tree record has an invalid type or oid")
        records.append((mode, kind, oid, name))
    return tuple(records)


def _index_blob_records(payload: bytes) -> list[tuple[bytes, str]] | None:
    """Blob names and OIDs of one ``ls-tree -r`` frame. ``None`` past the index bound."""

    blobs: list[tuple[bytes, str]] = []
    for _mode, kind, oid, name in _iter_ls_tree_records(payload):
        if kind != "blob":
            continue
        blobs.append((name, oid))
        if len(blobs) > INVENTORY_MAX_FILES:
            return None
    return blobs


def _parse_tree_object(payload: bytes, *, parent: GitPath, oid: str) -> tuple[GitTreeEntry, ...]:
    """Children of one raw tree object: ``<mode> <name>NUL<binary oid>`` records.

    The object format fixes the binary width, so it comes from the tree's own
    hex OID. Modes are zero-padded to the six digits ``ls-tree`` prints.
    """

    oid_bytes = len(oid) // 2
    entries: list[GitTreeEntry] = []
    offset = 0
    length = len(payload)
    while offset < length:
        space = payload.find(b" ", offset)
        nul = -1 if space < 0 else payload.find(b"\x00", space + 1)
        end = nul + 1 + oid_bytes
        if space < 0 or nul < 0 or end > length:
            raise GitBatchProtocolError("tree object record is truncated")
        mode = payload[offset:space].decode("ascii", errors="replace").zfill(6)
        if len(mode) != 6 or not mode.isdigit():
            raise GitBatchProtocolError("tree object record has an invalid mode")
        kind: GitEntryKind = (
            "tree" if mode == "040000" else "commit" if mode == "160000" else "blob"
        )
        try:
            path = parent.child(payload[space + 1 : nul])
        except GitPathError as exc:
            raise GitBatchProtocolError("tree object record has an invalid name") from exc
        entries.append(
            GitTreeEntry(path=path, mode=mode, kind=kind, oid=payload[nul + 1 : end].hex())
        )
        offset = end
    entries.sort(key=_tree_entry_name)
    return tuple(entries)


class GitTreeSource:
    """Byte-safe tree walk and size-gated blob reads over one revision."""

    def __init__(
        self,
        *,
        target: RepositoryStoreTarget,
        root_tree_oid: str,
        max_blob_bytes: int = TEXT_PREVIEW_REQUEST_MAX_BYTES,
    ) -> None:
        self._target = target
        self._root_tree_oid = require_full_oid(root_tree_oid)
        self._max_blob_bytes = max_blob_bytes
        self._pool = _retain_pool(target)
        self._pool_released = False
        self._trees: dict[str, _CachedTree] = {}
        self._indexes: dict[str, GitBlobIndex | None] = {}
        self._derived: OrderedDict[Hashable, object] = OrderedDict()
        self._deriving: dict[Hashable, asyncio.Future[Any]] = {}

    @property
    def target(self) -> RepositoryStoreTarget:
        return self._target

    def resolve(self, identity: str) -> ContentHandle | None:
        """Sync cache lookup. Walks use :meth:`resolve_path`."""

        try:
            path = GitPath.from_wire(identity)
        except GitPathError:
            return None
        if not path.segments:
            return ContentHandle(
                identity=identity,
                path=None,
                exists=True,
                is_dir=True,
                is_file=False,
            )
        parent_oid = self._root_tree_oid
        entry: GitTreeEntry | None = None
        walked = GitPath.root()
        for segment in path.segments:
            cached = self._trees.get(parent_oid)
            if cached is None:
                return None
            walked = walked.child(segment)
            entry = cached.by_name.get(segment)
            if entry is None:
                return ContentHandle(
                    identity=identity,
                    path=None,
                    exists=False,
                    is_dir=False,
                    is_file=False,
                )
            parent_oid = entry.oid if entry.is_tree else ""
        if entry is None:
            return None
        return ContentHandle(
            identity=identity,
            path=None,
            exists=True,
            is_dir=entry.is_tree,
            is_file=entry.is_blob,
        )

    async def resolve_path(self, path: GitPath) -> GitTreeEntry | None:
        if not path.segments:
            return GitTreeEntry(
                path=GitPath.root(),
                mode="040000",
                kind="tree",
                oid=self._root_tree_oid,
            )
        parent_path = path.parent()
        parent = await self._tree_oid_for(parent_path)
        if parent is None:
            return None
        return (await self._load_tree(parent, parent_path=parent_path)).child(path)

    async def resolve_child(self, directory: GitTreeEntry, name: bytes) -> GitTreeEntry | None:
        """*name* inside a tree entry already in hand, without re-walking its path."""

        if not directory.is_tree:
            return None
        cached = await self._load_tree(directory.oid, parent_path=directory.path)
        entry = cached.by_name.get(name)
        if entry is None:
            return None
        return cached.child(directory.path.child(name))

    async def list_tree(self, path: GitPath | None = None) -> tuple[GitTreeEntry, ...]:
        located = GitPath.root() if path is None else path
        tree_oid = await self._tree_oid_for(located)
        if tree_oid is None:
            raise GitObjectUnavailableError(located.to_wire() or self._root_tree_oid)
        return await self._list_tree_oid(tree_oid, parent_path=located)

    async def list_tree_entry(self, entry: GitTreeEntry) -> tuple[GitTreeEntry, ...]:
        """List a tree a parent listing already resolved, without re-walking its path."""

        if not entry.is_tree:
            raise GitObjectUnavailableError(entry.path.to_wire() or entry.oid)
        return await self._list_tree_oid(entry.oid, parent_path=entry.path)

    async def read_blob(self, path: GitPath) -> bytes:
        entry = await self.resolve_path(path)
        if entry is None or not entry.is_blob:
            raise GitObjectUnavailableError(path.to_wire())
        async with self._pool.checkout() as reader:
            return await reader.read_blob(entry.oid, max_blob_bytes=self._max_blob_bytes)

    async def open_ref(self, identity: str) -> ContentRef | None:
        """Resolve a GitPath wire to readable blob bytes. See `ContentSource`."""

        try:
            path = GitPath.from_wire(identity)
        except GitPathError:
            return None
        return await self._open_ref_path(path)

    async def open_container(
        self, identity: str, *, suffixes: tuple[str, ...]
    ) -> tuple[ContentRef, str] | None:
        """Split a GitPath prefix from a container inner. See `ContentSource`."""

        try:
            path, inner = split_git_container_wire(identity)
        except GitPathError:
            return None
        if inner and inner.count("/") + 1 > MAX_CONTAINER_INNER_DEPTH:
            return None
        ref = await self._open_ref_path(path)
        if ref is None or ref.logical_ext not in suffixes:
            return None
        return ref, inner

    async def _open_ref_path(self, path: GitPath) -> ContentRef | None:
        entry = await resolve_git_blob_entry(self, path)
        if entry is None:
            return None
        # The requested path stays the route identity even when a symlink was
        # followed, matching what ``/api/file`` and ``/raw`` echo back. The
        # extension comes from the resolved leaf, which is what a kind check
        # has to see.
        return ContentRef(
            identity=path.to_wire(),
            logical_ext=blob_logical_ext(entry.path),
            fingerprint=entry.oid,
            reader=_GitBlobReader(source=self, entry=entry),
        )

    @property
    def max_blob_bytes(self) -> int:
        """The largest blob this pin reads whole; a larger one is read in windows."""

        return self._max_blob_bytes

    async def read_blob_oid(self, oid: str) -> bytes:
        async with self._pool.checkout() as reader:
            return await reader.read_blob(
                require_full_oid(oid), max_blob_bytes=self._max_blob_bytes
            )

    async def read_blob_window(self, oid: str, *, offset: int, max_bytes: int) -> tuple[bytes, int]:
        """A bounded window of one blob and the blob's size, at any blob size.

        See :meth:`_BatchObjectReader.read_blob_window`: reaching *offset* costs
        streaming up to it, and nothing past the window is held.
        """

        async with self._pool.checkout() as reader:
            return await reader.read_blob_window(
                require_full_oid(oid), offset=offset, max_bytes=max_bytes
            )

    async def object_info(self, oid: str) -> _ObjectInfo:
        async with self._pool.checkout() as reader:
            return await reader.info(require_full_oid(oid))

    async def derived[T](self, key: Hashable, build: Callable[[], T]) -> T:
        """Memoize a fact derived from this pin's immutable objects.

        *key* names the fact and every input that varies it: a tree OID, a path,
        a filter. *build* is pure and runs off the event loop, once per key even
        when requests race. The least recently used facts are dropped past
        :data:`MAX_DERIVED_FACTS`. A failed build is not remembered.
        """

        if key in self._derived:
            self._derived.move_to_end(key)
            return cast("T", self._derived[key])
        pending = self._deriving.get(key)
        if pending is None:
            pending = asyncio.ensure_future(asyncio.to_thread(build))
            self._deriving[key] = pending
            pending.add_done_callback(lambda _done: self._deriving.pop(key, None))
        value = await asyncio.shield(pending)
        if not self._pool_released:
            self._derived[key] = value
            self._derived.move_to_end(key)
            while len(self._derived) > MAX_DERIVED_FACTS:
                self._derived.popitem(last=False)
        return cast("T", value)

    async def aclose(self) -> None:
        self._trees.clear()
        self._indexes.clear()
        self._derived.clear()
        if self._pool_released:
            return
        self._pool_released = True
        await _release_pool(self._pool)

    async def _tree_oid_for(self, path: GitPath) -> str | None:
        if not path.segments:
            return self._root_tree_oid
        entry = await self.resolve_path(path)
        if entry is None or not entry.is_tree:
            return None
        return entry.oid

    async def _list_tree_oid(
        self, tree_oid: str, *, parent_path: GitPath
    ) -> tuple[GitTreeEntry, ...]:
        return (await self._load_tree(tree_oid, parent_path=parent_path)).listed_under(parent_path)

    async def _load_tree(self, tree_oid: str, *, parent_path: GitPath) -> _CachedTree:
        cached = self._trees.get(tree_oid)
        if cached is not None:
            return cached
        async with self._pool.checkout() as reader:
            payload = await reader.read_tree(tree_oid)
        entries = _parse_tree_object(payload, parent=parent_path, oid=tree_oid)
        entries = await self._attach_blob_sizes(entries)
        cached = _CachedTree(
            parent=parent_path,
            entries=entries,
            by_name=MappingProxyType({_tree_entry_name(entry): entry for entry in entries}),
        )
        self._trees[tree_oid] = cached
        return cached

    async def blob_index(self, path: GitPath | None = None) -> GitBlobIndex | None:
        """Recursive blob names and sizes under *path*. ``None`` if truncated."""

        located = GitPath.root() if path is None else path
        tree_oid = await self._tree_oid_for(located)
        if tree_oid is None:
            return None
        return await self._blob_index_oid(tree_oid)

    async def tree_tally(self, path: GitPath | None = None) -> GitTreeTally | None:
        index = await self.blob_index(path)
        if index is None:
            return None
        return index.tally()

    async def _blob_index_oid(self, tree_oid: str) -> GitBlobIndex | None:
        if tree_oid in self._indexes:
            return self._indexes[tree_oid]
        try:
            payload = await run_git(
                [*_MAILMAP_ARGS, "ls-tree", "-r", "-z", "--full-tree", tree_oid],
                target=self._target,
                policy=STORE_READ_POLICY,
            )
        except GitOutputTooLargeError:
            self._indexes[tree_oid] = None
            return None
        except GitCommandError as exc:
            # The walk names a nested object it could not read. Only that
            # validated OID leaves the stderr text, which can carry paths. An
            # absent walk root is reported without one, so ask the store.
            missing = _FULL_OID.search(exc.stderr_summary)
            if missing is not None:
                raise GitObjectUnavailableError(missing.group()) from exc
            try:
                await self.object_info(tree_oid)
            except GitObjectUnavailableError as unavailable:
                raise unavailable from exc
            raise
        # Parsing and sorting a whole tree is synchronous work, so it leaves the loop.
        blobs = await asyncio.to_thread(_index_blob_records, payload)
        if blobs is None:
            self._indexes[tree_oid] = None
            return None
        blob_oids = tuple(oid for _name, oid in blobs)
        sizes: dict[str, int] = {}
        if blob_oids:
            async with self._pool.checkout() as reader:
                infos = await reader.info_many(blob_oids)
            for oid, info in infos.items():
                if info is not None and info.kind == "blob":
                    sizes[oid] = info.size
        index = await asyncio.to_thread(
            GitBlobIndex, blobs=tuple(blobs), sizes=MappingProxyType(sizes)
        )
        self._indexes[tree_oid] = index
        return index

    async def _attach_blob_sizes(
        self, entries: tuple[GitTreeEntry, ...]
    ) -> tuple[GitTreeEntry, ...]:
        """Fill blob sizes from ``cat-file`` info. Trees and gitlinks stay unsized."""

        blob_oids = tuple(entry.oid for entry in entries if entry.is_blob)
        if not blob_oids:
            return entries
        async with self._pool.checkout() as reader:
            infos = await reader.info_many(blob_oids)
        sized: list[GitTreeEntry] = []
        for entry in entries:
            if not entry.is_blob:
                sized.append(entry)
                continue
            info = infos.get(entry.oid)
            if info is None or info.kind != "blob":
                sized.append(entry)
                continue
            sized.append(replace(entry, size=info.size))
        return tuple(sized)


@dataclass(slots=True)
class _SymlinkBudget:
    """Hops left for one resolution, shared by every link it meets."""

    hops: int = _MAX_GIT_SYMLINK_FOLLOW

    def spend(self) -> bool:
        self.hops -= 1
        return self.hops >= 0


async def follow_git_symlinks(source: GitTreeSource, entry: GitTreeEntry) -> GitTreeEntry | None:
    """Follow in-tree relative symlink blobs the way the operating system would.

    A link body resolves one component at a time from the link's own directory. A
    link met partway through is followed before the walk goes on, so a ``..`` after
    it climbs from where that link led, and a component that is missing or is not a
    directory stops the walk, as it would for a checkout on disk. Normalizing the
    body as text first would answer ``dir-link/..`` with the link's own directory and
    turn ``file/..`` or ``missing/..`` into a hit. None when the target is absolute,
    climbs out of the tree, cannot be resolved, or takes more than
    ``_MAX_GIT_SYMLINK_FOLLOW`` hops in all.
    """

    budget = _SymlinkBudget()
    current: GitTreeEntry | None = entry
    while current is not None and current.is_symlink:
        current = await _resolve_git_symlink(source, current, budget)
    return current


async def _resolve_git_symlink(
    source: GitTreeSource, link: GitTreeEntry, budget: _SymlinkBudget
) -> GitTreeEntry | None:
    """The entry one link names, itself possibly a link; see :func:`follow_git_symlinks`.

    Each component is looked up in the directory entry already in hand, and ``..``
    pops back to the one before, so a body costs one lookup per component rather than
    a walk from the root per component. Only following a link partway through
    rebuilds the stack, from the directory that link led to.
    """

    if not budget.spend():
        return None
    if link.size is not None and link.size > _MAX_GIT_SYMLINK_BODY_BYTES:
        return None
    raw = await source.read_blob(link.path)
    if len(raw) > _MAX_GIT_SYMLINK_BODY_BYTES:
        return None
    if not raw or b"\x00" in raw or raw.startswith(b"/"):
        return None
    parts = [part for part in raw.split(b"/") if part not in {b"", b"."}]
    stack = await _directory_stack(source, link.path.parent())
    if stack is None:
        return None
    for index, part in enumerate(parts):
        # A cached tree answers without suspending, so yield once per component.
        await asyncio.sleep(0)
        if part == b"..":
            if len(stack) == 1:
                return None
            stack.pop()
            continue
        try:
            entry = await source.resolve_child(stack[-1], part)
        except GitPathError:
            return None
        if entry is None:
            return None
        if index == len(parts) - 1:
            return entry
        if entry.is_symlink:
            while entry is not None and entry.is_symlink:
                entry = await _resolve_git_symlink(source, entry, budget)
            if entry is None or not entry.is_tree:
                return None
            # ``..`` after a link climbs from where the link led.
            stack = await _directory_stack(source, entry.path)
            if stack is None:
                return None
            continue
        if not entry.is_tree:
            return None
        stack.append(entry)
    # The body ended on ``..`` or named the link's own directory.
    return stack[-1]


async def _directory_stack(source: GitTreeSource, path: GitPath) -> list[GitTreeEntry] | None:
    """The tree entries from the root down to *path*, or None if one is not a tree."""

    root = await source.resolve_path(GitPath.root())
    if root is None:
        return None
    stack = [root]
    for segment in path.segments:
        entry = await source.resolve_child(stack[-1], segment)
        if entry is None or not entry.is_tree:
            return None
        stack.append(entry)
    return stack


async def resolve_git_blob_entry(source: GitTreeSource, path: GitPath) -> GitTreeEntry | None:
    """Resolve a GitPath to a blob, following in-tree relative symlink blobs.

    None when missing, a tree, a gitlink, or an unusable symlink target.
    """

    entry = await source.resolve_path(path)
    if entry is None:
        return None
    if entry.is_symlink:
        entry = await follow_git_symlinks(source, entry)
        if entry is None:
            return None
    if not entry.is_blob or entry.is_symlink or entry.is_gitlink:
        return None
    return entry


def blob_logical_ext(path: GitPath) -> str:
    """Lowercase suffix of a blob's display name.

    A stored blob has no gzip smudge, so there is no compression suffix to
    strip the way an on-disk artifact needs.
    """

    if not path.segments:
        return ""
    return Path(display_segment(path.segments[-1])).suffix.lower()


@dataclass(frozen=True, slots=True)
class _GitBlobReader:
    """Bounded reads of one resolved blob, through the pooled cat-file actors."""

    source: GitTreeSource
    entry: GitTreeEntry

    async def stat(self) -> ContentStat:
        size = self.entry.size
        if size is None:
            # A listing that could not attach sizes, or a blob reached by
            # following a symlink out of a listing that did.
            size = (await self.source.object_info(self.entry.oid)).size
        return ContentStat(size=size)

    async def read_window(self, *, offset: int, max_bytes: int) -> ContentWindow:
        # The blob streams from its start to the end of the window, like a compressed
        # artifact, and only the window is held, so no blob size is refused here. It is
        # not memoized between windows. Paging the byte view to its 32 MiB ceiling, seven
        # requests, took 0.27 s in all for a 32 MiB blob and 0.38 s for 64 MiB, at worst
        # 56 and 70 ms a request; reading the blob once and slicing took 0.04 and 0.11 s,
        # but only by holding the whole blob in server memory while the view might page.
        # See docs/large-content-rendering.md.
        window, size = await self.source.read_blob_window(
            self.entry.oid, offset=offset, max_bytes=max_bytes
        )
        return ContentWindow(data=window, offset=offset, has_more=offset + len(window) < size)


class GitRevisionSubject:
    """A pinned full-OID tree over a worktree-free store.

    ``ref`` is the label the pin was resolved from, such as
    ``refs/remotes/origin/topic``, when one is known. It records what was asked for
    and is never read back to find the commit: every read uses ``commit_oid``.
    """

    kind = RepositorySubjectKind.git_revision.value

    def __init__(
        self,
        *,
        commit_oid: str,
        tree_oid: str,
        content: GitTreeSource,
        store_identity: str,
        ref: str | None = None,
    ) -> None:
        self._identity = f"{store_identity}:{commit_oid}"
        self._commit_oid = commit_oid
        self._ref = ref
        self._tree_oid = tree_oid
        self._content = content
        self._capabilities = GIT_REVISION_CAPABILITIES

    @property
    def identity(self) -> str:
        return self._identity

    @property
    def commit_oid(self) -> str:
        return self._commit_oid

    @property
    def tree_oid(self) -> str:
        return self._tree_oid

    @property
    def ref(self) -> str | None:
        return self._ref

    @property
    def capabilities(self) -> SourceCapabilities:
        return self._capabilities

    @property
    def content(self) -> ContentSource:
        return self._content

    @property
    def filesystem_root(self) -> Path | None:
        return None

    @property
    def tree_source(self) -> GitTreeSource:
        return self._content

    @property
    def command_target(self) -> RepositoryStoreTarget:
        return self._content.target

    async def aclose(self) -> None:
        await self._content.aclose()


def ref_short_name(ref: str | None) -> str | None:
    """The name a reader knows a mirror ref by: ``topic`` for ``refs/remotes/origin/topic``.

    A store mirrors its origin's branches under ``refs/remotes/origin/`` and its tags
    under ``refs/tags/``; stripping that prefix gives the name the origin uses. Any
    other ref keeps its full spelling rather than being guessed at.
    """

    if ref is None:
        return None
    for prefix in ("refs/remotes/origin/", "refs/tags/", "refs/heads/"):
        if ref.startswith(prefix) and len(ref) > len(prefix):
            return ref.removeprefix(prefix)
    return ref


async def git_revision_subject(
    *,
    target: GitCommandTarget,
    commit_oid: str,
    store_identity: str,
    max_blob_bytes: int = TEXT_PREVIEW_REQUEST_MAX_BYTES,
    ref: str | None = None,
) -> GitRevisionSubject:
    """Pin a commit's tree after proving the tree object is present.

    *ref* labels the pin (see :class:`GitRevisionSubject`); it is not resolved.
    """

    if not isinstance(target, RepositoryStoreTarget):
        raise GitPathError("GitRevisionSubject requires a RepositoryStoreTarget")
    oid = require_full_oid(commit_oid)
    raw = await run_git(
        [*_MAILMAP_ARGS, "rev-parse", "--verify", "--end-of-options", f"{oid}^{{tree}}"],
        target=target,
        policy=STORE_READ_POLICY,
    )
    tree_oid = require_full_oid(raw.decode("ascii", errors="replace").strip())
    source = GitTreeSource(target=target, root_tree_oid=tree_oid, max_blob_bytes=max_blob_bytes)
    try:
        await source.object_info(tree_oid)
    except BaseException:
        await source.aclose()
        raise
    return GitRevisionSubject(
        commit_oid=oid,
        tree_oid=tree_oid,
        content=source,
        store_identity=store_identity,
        ref=ref,
    )


__all__ = [
    "BLOB_WINDOW_DRAIN_MAX_BYTES",
    "GIT_REVISION_CAPABILITIES",
    "MAX_BATCH_READERS_PER_STORE",
    "GitBatchProtocolError",
    "GitBlobIndex",
    "GitBlobTallies",
    "GitBlobTooLargeError",
    "GitObjectUnavailableError",
    "GitPath",
    "GitPathError",
    "GitRevisionSubject",
    "GitTreeEntry",
    "GitTreeSource",
    "GitTreeTally",
    "blob_logical_ext",
    "display_segment",
    "follow_git_symlinks",
    "git_revision_subject",
    "read_store_blob",
    "ref_short_name",
    "require_full_oid",
    "resolve_git_blob_entry",
    "split_git_container_wire",
    "store_batch_reader_count",
]
