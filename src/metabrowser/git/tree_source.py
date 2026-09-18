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
display names. Blob listings
carry ``cat-file`` info sizes so ``min_size`` can filter; trees and gitlinks
have no blob size. Recursive ``ls-tree -r`` plus ``cat-file`` info fills
directory ``total_files`` / ``total_size``; a truncated listing or a missing
blob size omits the incomplete dimension. Omitted mtime still leaves age
chrome empty rather than pending.
Markdown and wiki destinations encode authored segments
as GitPath wires. An LFS pointer is the stored pointer bytes;
a blob the tree names but the store lacks is ``object_unavailable`` with
lazy fetch disabled. Serving acquired Git stays on a later bead.
"""

from __future__ import annotations

import asyncio
import base64
import threading
from collections.abc import AsyncGenerator, Mapping
from contextlib import asynccontextmanager, suppress
from dataclasses import dataclass, replace
from pathlib import Path
from types import MappingProxyType
from typing import Final, Literal

from metabrowser.git.process import (
    ACQUISITION_POLICY,
    BATCH_OBJECT_POLICY,
    GIT_DISABLE_MAILMAP_ARGS,
    GitCommandTarget,
    GitError,
    GitOutputTooLargeError,
    RepositoryStoreTarget,
    run_git,
    spawn_git_process,
    terminate_git_process,
)
from metabrowser.git.wire import is_full_revision
from metabrowser.settings import INVENTORY_MAX_FILES, TEXT_PREVIEW_REQUEST_MAX_BYTES
from metabrowser.source import (
    ContentHandle,
    ContentSource,
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
_STDERR_MAX_BYTES: Final[int] = 64 * 1024
_POOLS_GUARD = threading.Lock()
_POOLS: dict[Path, _StoreReaderPool] = {}


class GitPathError(ValueError):
    """A GitPath wire token or segment is not a lossless byte identity."""


class GitObjectUnavailableError(GitError):
    """The store does not have this object with lazy fetch disabled."""

    code = "object_unavailable"

    def __init__(self, oid: str) -> None:
        self.oid = oid
        super().__init__(f"object_unavailable: {oid}")


class GitBlobTooLargeError(GitError):
    """``info`` declared a blob larger than the preview/raw bound."""

    code = "blob_too_large"

    def __init__(self, *, oid: str, size: int, max_bytes: int) -> None:
        self.oid = oid
        self.size = size
        self.max_bytes = max_bytes
        super().__init__(f"blob {oid} is {size} bytes; limit is {max_bytes}")


class GitBatchProtocolError(GitError):
    """The cat-file actor returned a truncated or unexpected frame."""


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

    def display(self) -> str:
        return "/".join(segment.decode("utf-8", "replace") for segment in self.segments)


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


@dataclass(frozen=True, slots=True)
class GitTreeTally:
    """Descendant blob count and size under one tree.

    ``total_size`` is ``None`` when any counted blob is missing from the store.
    """

    total_files: int
    total_size: int | None


@dataclass(frozen=True, slots=True)
class GitBlobIndex:
    """Recursive blob names under one tree, with ``cat-file`` sizes when known."""

    blobs: tuple[tuple[bytes, str], ...]
    sizes: Mapping[str, int]

    def tally(self, prefix: bytes = b"") -> GitTreeTally:
        files = 0
        size = 0
        size_known = True
        needle = prefix + b"/" if prefix else b""
        for name, oid in self.blobs:
            if prefix and name != prefix and not name.startswith(needle):
                continue
            files += 1
            blob_size = self.sizes.get(oid)
            if blob_size is None:
                size_known = False
            else:
                size += blob_size
        return GitTreeTally(files, size if size_known else None)


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
        self._stderr_task: asyncio.Task[tuple[bytes, bool]] | None = None

    async def info(self, oid: str) -> _ObjectInfo:
        result = await self._transact(oid, contents=False)
        if not isinstance(result, _ObjectInfo):
            raise GitBatchProtocolError("info transaction returned a body")
        return result

    async def info_many(self, oids: tuple[str, ...]) -> dict[str, _ObjectInfo | None]:
        """One flush for many ``info`` commands. A missing object is ``None``."""

        unique: list[str] = []
        seen: set[str] = set()
        for oid in oids:
            require_full_oid(oid)
            if oid not in seen:
                seen.add(oid)
                unique.append(oid)
        if not unique:
            return {}
        try:
            return await self._info_many_inner(tuple(unique))
        except asyncio.CancelledError:
            await self._poison()
            raise
        except (BrokenPipeError, ConnectionResetError, asyncio.IncompleteReadError) as exc:
            await self._poison()
            raise GitBatchProtocolError("cat-file actor framing failed") from exc
        except GitBatchProtocolError:
            await self._poison()
            raise
        except Exception:
            await self._poison()
            raise

    async def _info_many_inner(self, oids: tuple[str, ...]) -> dict[str, _ObjectInfo | None]:
        await self._ensure()
        proc = self._proc
        writer = None if proc is None else proc.stdin
        reader = None if proc is None else proc.stdout
        if proc is None or writer is None or reader is None:
            raise GitBatchProtocolError("cat-file actor has no pipes")
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

    async def aclose(self) -> None:
        await self._poison()

    async def _transact(
        self,
        oid: str,
        *,
        contents: bool,
        expected: _ObjectInfo | None = None,
    ) -> _ObjectInfo | bytes:
        require_full_oid(oid)
        try:
            return await self._transact_inner(oid, contents=contents, expected=expected)
        except asyncio.CancelledError:
            await self._poison()
            raise
        except GitObjectUnavailableError:
            raise
        except (BrokenPipeError, ConnectionResetError, asyncio.IncompleteReadError) as exc:
            await self._poison()
            raise GitBatchProtocolError("cat-file actor framing failed") from exc
        except GitBatchProtocolError:
            await self._poison()
            raise
        except Exception:
            await self._poison()
            raise

    async def _transact_inner(
        self,
        oid: str,
        *,
        contents: bool,
        expected: _ObjectInfo | None,
    ) -> _ObjectInfo | bytes:
        await self._ensure()
        proc = self._proc
        writer = None if proc is None else proc.stdin
        reader = None if proc is None else proc.stdout
        if proc is None or writer is None or reader is None:
            raise GitBatchProtocolError("cat-file actor has no pipes")
        command = "contents" if contents else "info"
        writer.write(f"{command} {oid}\nflush\n".encode("ascii"))
        await writer.drain()
        header = await _read_header(reader)
        info = _parse_info_header(oid, header)
        if not contents:
            return info
        if expected is not None and (info.oid != expected.oid or info.size != expected.size):
            raise GitBatchProtocolError("contents header does not match info")
        body = await reader.readexactly(info.size)
        trailer = await reader.readexactly(1)
        if trailer != b"\n":
            raise GitBatchProtocolError("contents frame is missing the trailing newline")
        return body

    async def _ensure(self) -> None:
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


async def _drain_stderr(proc: asyncio.subprocess.Process) -> tuple[bytes, bool]:
    stream = proc.stderr
    if stream is None:
        return b"", False
    chunks: list[bytes] = []
    total = 0
    overflowed = False
    while True:
        chunk = await stream.read(65536)
        if not chunk:
            break
        if total < _STDERR_MAX_BYTES:
            remain = _STDERR_MAX_BYTES - total
            chunks.append(chunk[:remain])
        else:
            overflowed = True
        total += len(chunk)
    return b"".join(chunks), overflowed


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


def _parse_ls_tree(payload: bytes, *, parent: GitPath) -> tuple[GitTreeEntry, ...]:
    entries = [
        GitTreeEntry(path=parent.child(name), mode=mode, kind=kind, oid=oid)
        for mode, kind, oid, name in _iter_ls_tree_records(payload)
    ]
    entries.sort(key=lambda entry: entry.path.segments[-1])
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
        self._trees: dict[str, tuple[GitTreeEntry, ...]] = {}
        self._indexes: dict[str, GitBlobIndex | None] = {}

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
            entry = next((item for item in cached if item.path.segments[-1] == segment), None)
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
        parent = await self._tree_oid_for(path.parent())
        if parent is None:
            return None
        children = await self._list_tree_oid(parent, parent_path=path.parent())
        return next((item for item in children if item.path == path), None)

    async def list_tree(self, path: GitPath | None = None) -> tuple[GitTreeEntry, ...]:
        located = GitPath.root() if path is None else path
        tree_oid = await self._tree_oid_for(located)
        if tree_oid is None:
            raise GitObjectUnavailableError(located.to_wire() or self._root_tree_oid)
        return await self._list_tree_oid(tree_oid, parent_path=located)

    async def read_blob(self, path: GitPath) -> bytes:
        entry = await self.resolve_path(path)
        if entry is None or not entry.is_blob:
            raise GitObjectUnavailableError(path.to_wire())
        async with self._pool.checkout() as reader:
            return await reader.read_blob(entry.oid, max_blob_bytes=self._max_blob_bytes)

    async def read_blob_oid(self, oid: str) -> bytes:
        async with self._pool.checkout() as reader:
            return await reader.read_blob(
                require_full_oid(oid), max_blob_bytes=self._max_blob_bytes
            )

    async def object_info(self, oid: str) -> _ObjectInfo:
        async with self._pool.checkout() as reader:
            return await reader.info(require_full_oid(oid))

    async def aclose(self) -> None:
        self._trees.clear()
        self._indexes.clear()
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
        cached = self._trees.get(tree_oid)
        if cached is not None:
            return cached
        payload = await run_git(
            [*_MAILMAP_ARGS, "ls-tree", "-z", "--full-tree", tree_oid],
            target=self._target,
            policy=ACQUISITION_POLICY,
        )
        entries = _parse_ls_tree(payload, parent=parent_path)
        entries = await self._attach_blob_sizes(entries)
        self._trees[tree_oid] = entries
        return entries

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
                policy=ACQUISITION_POLICY,
            )
        except GitOutputTooLargeError:
            self._indexes[tree_oid] = None
            return None
        blobs: list[tuple[bytes, str]] = []
        for _mode, kind, oid, name in _iter_ls_tree_records(payload):
            if kind != "blob":
                continue
            blobs.append((name, oid))
            if len(blobs) > INVENTORY_MAX_FILES:
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
        index = GitBlobIndex(blobs=tuple(blobs), sizes=MappingProxyType(sizes))
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


class GitRevisionSubject:
    """A pinned full-OID tree over a worktree-free store."""

    kind = RepositorySubjectKind.git_revision.value

    def __init__(
        self,
        *,
        commit_oid: str,
        tree_oid: str,
        content: GitTreeSource,
        store_identity: str,
    ) -> None:
        self._identity = f"{store_identity}:{commit_oid}"
        self._commit_oid = commit_oid
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


async def git_revision_subject(
    *,
    target: GitCommandTarget,
    commit_oid: str,
    store_identity: str = "store",
    max_blob_bytes: int = TEXT_PREVIEW_REQUEST_MAX_BYTES,
) -> GitRevisionSubject:
    """Pin a commit's tree after proving the tree object is present."""

    if not isinstance(target, RepositoryStoreTarget):
        raise GitPathError("GitRevisionSubject requires a RepositoryStoreTarget")
    oid = require_full_oid(commit_oid)
    raw = await run_git(
        [*_MAILMAP_ARGS, "rev-parse", "--verify", "--end-of-options", f"{oid}^{{tree}}"],
        target=target,
        policy=ACQUISITION_POLICY,
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
    )


__all__ = [
    "GIT_REVISION_CAPABILITIES",
    "MAX_BATCH_READERS_PER_STORE",
    "GitBatchProtocolError",
    "GitBlobIndex",
    "GitBlobTooLargeError",
    "GitObjectUnavailableError",
    "GitPath",
    "GitPathError",
    "GitRevisionSubject",
    "GitTreeEntry",
    "GitTreeSource",
    "GitTreeTally",
    "git_revision_subject",
    "read_store_blob",
    "require_full_oid",
    "store_batch_reader_count",
]
