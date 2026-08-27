"""Bounded, replayable server sessions for continuous Git history.

Each session owns one ordered ``git log`` walk. Requests advance it one
page at a time, while completed pages are framed in a private spool and
replayed by indexed seek. The process, parser, session registry, idle
lifetime, and storage all have independent measured bounds.
"""

from __future__ import annotations

import asyncio
import base64
import binascii
import contextlib
import hashlib
import json
import logging
import re
import secrets
import struct
import tempfile
import time
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from metabrowser.git.log import LOG_FORMAT, parse_log_output, trunk_refs
from metabrowser.git.process import (
    GitCommandError,
    GitError,
    GitTimeoutError,
    run_git,
    spawn_git_process,
    terminate_git_process,
)
from metabrowser.git.wire import (
    GitCommit,
    GitGraphCheckpoint,
    GitGraphLane,
    GitLogPage,
    is_full_revision,
)
from metabrowser.settings import (
    GIT_HISTORY_SESSION_IDLE_TTL_S,
    GIT_HISTORY_SESSION_MAX_ENTRIES,
    GIT_HISTORY_SESSION_MAX_STORAGE_BYTES,
    GIT_HISTORY_SESSION_MAX_WALKS,
    GIT_HISTORY_SESSION_PARSER_MAX_BYTES,
    GIT_LOG_DEFAULT_LIMIT,
    GIT_SUBPROCESS_TIMEOUT_S,
)

log = logging.getLogger(__name__)

HistoryScopeName = Literal["default", "all"]
HistoryCursorDirection = Literal["current", "next", "previous"]

_CURSOR_VERSION = 1
_CURSOR_MAX_CHARS = 512
_CURSOR_SESSION_RE = re.compile(r"\A[A-Za-z0-9_-]{16,64}\Z")
_CURSOR_FINGERPRINT_RE = re.compile(r"\A[0-9a-f]{64}\Z")
_CURSOR_MAX_PAGE = 2**31 - 1
_FRAME_HEADER = struct.Struct(">Q")
_READ_CHUNK_BYTES = 64 * 1024
_STDERR_RETAIN_BYTES = 64 * 1024
_REAPER_MAX_INTERVAL_S = 30.0
_HEAD_LANE_COLOR = "var(--git-ref-local)"
_LANE_COLORS = tuple(f"var(--git-lane-{index})" for index in range(1, 6))


class HistorySessionError(Exception):
    """Base for history-session failures that routes translate explicitly."""


class InvalidHistoryCursorError(HistorySessionError):
    """A cursor is malformed or does not identify a valid page operation."""


class ExpiredHistorySessionError(HistorySessionError):
    """The cursor's bounded server session no longer exists."""


class StaleHistorySessionError(HistorySessionError):
    """The repository or requested ref scope changed after session creation."""


class HistoryStorageError(HistorySessionError):
    """A session exhausted its measured private replay-storage budget."""


class HistoryParserError(GitError):
    """Git produced a record larger than the measured parser budget."""


@dataclass(frozen=True)
class HistoryCursor:
    """Validated contents of an opaque server-issued history cursor."""

    session_id: str
    page: int
    direction: HistoryCursorDirection
    scope_fingerprint: str
    page_size: int


@dataclass(frozen=True)
class HistoryScope:
    """One resolved ref scope and the snapshot that makes it stale-detectable."""

    name: HistoryScopeName
    arguments: tuple[str, ...]
    display_refs: tuple[str, ...]
    fingerprint: str
    head_revision: str | None = None
    head_ref: str | None = None


@dataclass(frozen=True)
class _GraphLane:
    id: str
    color: str


@dataclass(frozen=True)
class _GraphCheckpoint:
    prior_swimlanes: tuple[_GraphLane, ...]
    color_index: int


@dataclass(frozen=True)
class _Frame:
    offset: int
    length: int
    commit_count: int
    has_more: bool
    graph_checkpoint: _GraphCheckpoint


def encode_history_cursor(cursor: HistoryCursor) -> str:
    """Encode a validated history cursor as compact URL-safe text."""
    payload = json.dumps(
        {
            "d": cursor.direction,
            "f": cursor.scope_fingerprint,
            "n": cursor.page,
            "s": cursor.session_id,
            "v": _CURSOR_VERSION,
            "z": cursor.page_size,
        },
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")
    return base64.urlsafe_b64encode(payload).decode("ascii").rstrip("=")


def decode_history_cursor(raw: str) -> HistoryCursor | None:
    """Decode an opaque cursor, returning ``None`` for every invalid shape."""
    if not raw or len(raw) > _CURSOR_MAX_CHARS:
        return None
    try:
        padding = b"=" * (-len(raw) % 4)
        payload = base64.b64decode(
            raw.encode("ascii") + padding,
            altchars=b"-_",
            validate=True,
        )
        parsed = json.loads(payload)
    except (binascii.Error, UnicodeDecodeError, UnicodeEncodeError, ValueError, TypeError):
        return None
    if not isinstance(parsed, dict) or set(parsed) != {"d", "f", "n", "s", "v", "z"}:
        return None
    if parsed["v"] != _CURSOR_VERSION:
        return None
    session_id = parsed["s"]
    fingerprint = parsed["f"]
    direction = parsed["d"]
    page = parsed["n"]
    page_size = parsed["z"]
    if not isinstance(session_id, str) or _CURSOR_SESSION_RE.fullmatch(session_id) is None:
        return None
    if not isinstance(fingerprint, str) or _CURSOR_FINGERPRINT_RE.fullmatch(fingerprint) is None:
        return None
    if direction not in ("current", "next", "previous"):
        return None
    if not isinstance(page, int) or isinstance(page, bool) or not 0 <= page <= _CURSOR_MAX_PAGE:
        return None
    if not isinstance(page_size, int) or isinstance(page_size, bool) or page_size < 1:
        return None
    return HistoryCursor(
        session_id=session_id,
        page=page,
        direction=direction,
        scope_fingerprint=fingerprint,
        page_size=page_size,
    )


async def _resolved_revision(root: Path, revision: str) -> str | None:
    try:
        raw = await run_git(
            ["rev-parse", "--verify", "--quiet", f"{revision}^{{commit}}"],
            cwd=root,
        )
    except GitCommandError:
        return None
    candidate = raw.decode("ascii", errors="ignore").strip()
    return candidate if is_full_revision(candidate) else None


async def _symbolic_head(root: Path) -> str | None:
    try:
        raw = await run_git(["symbolic-ref", "--quiet", "HEAD"], cwd=root)
    except GitCommandError:
        return None
    candidate = raw.decode("utf-8", errors="replace").strip()
    return candidate if candidate.startswith("refs/") else None


async def resolve_history_scope(root: Path, *, wants_all: bool) -> HistoryScope:
    """Resolve a stable scope and fingerprint its externally mutable ref state."""
    root = root.resolve()
    object_format = (
        (await run_git(["rev-parse", "--show-object-format"], cwd=root))
        .decode("ascii", errors="replace")
        .strip()
    )
    material = bytearray(f"history-scope-v1\0{object_format}\0".encode())
    head_revision = await _resolved_revision(root, "HEAD")
    head_ref = await _symbolic_head(root)
    material.extend(b"HEAD-REF\0")
    material.extend((head_ref or "").encode("utf-8"))
    material.extend(b"\0")

    if wants_all:
        refs = await run_git(
            [
                "for-each-ref",
                "--format=%(refname)%00%(objecttype)%00%(objectname)%00"
                "%(*objecttype)%00%(*objectname)",
                "refs",
            ],
            cwd=root,
        )
        material.extend(refs)
        material.extend(b"\0HEAD\0")
        material.extend((head_revision or "").encode("ascii"))
        targets: list[str] = []
        seen_targets: set[str] = set()
        for record in refs.splitlines():
            fields = record.split(b"\0")
            if len(fields) != 5:
                continue
            _ref, object_type, object_name, peeled_type, peeled_name = fields
            target = object_name if object_type == b"commit" else peeled_name
            target_type = object_type if object_type == b"commit" else peeled_type
            decoded = target.decode("ascii", errors="ignore")
            if (
                target_type == b"commit"
                and is_full_revision(decoded)
                and decoded not in seen_targets
            ):
                targets.append(decoded)
                seen_targets.add(decoded)
        if head_revision is not None and head_revision not in seen_targets:
            targets.append(head_revision)
        arguments = tuple(targets)
        display_refs: tuple[str, ...] = ()
        name: HistoryScopeName = "all"
    else:
        # HEAD, its upstream, and whichever trunk refs exist — "where I
        # am, and what I merge into", the comparison a history view is
        # for. Each candidate is resolved exactly once: scope resolution
        # runs on every paged request, so a second rev-parse per
        # candidate doubles the subprocess cost of continuous scrolling.
        # A candidate that does not resolve is dropped rather than passed
        # to git, which would fail the whole walk; HEAD reuses the
        # revision resolved for the fingerprint above. An empty result
        # means an unborn branch, which the caller renders as an empty
        # history rather than an error.
        resolved: list[tuple[str, str]] = []
        for candidate in ("HEAD", "@{upstream}", *trunk_refs()):
            revision = (
                head_revision if candidate == "HEAD" else await _resolved_revision(root, candidate)
            )
            if revision is not None:
                resolved.append((candidate, revision))
                material.extend(candidate.encode("utf-8"))
                material.extend(b"\0")
                material.extend(revision.encode("ascii"))
                material.extend(b"\0")
        arguments = tuple(dict.fromkeys(revision for _candidate, revision in resolved))
        display_refs = tuple(candidate for candidate, _revision in resolved)
        name = "default"

    # The two digests are computed across an externally mutable ref snapshot at
    # different request times. Equality proves that the session still names the
    # same Git walk without putting an unbounded ref list in every cursor.
    fingerprint = hashlib.sha256(material).hexdigest()
    return HistoryScope(
        name=name,
        arguments=arguments,
        display_refs=display_refs,
        fingerprint=fingerprint,
        head_revision=head_revision,
        head_ref=head_ref,
    )


def _label_color(commit: GitCommit, head_ref: str | None) -> str | None:
    if head_ref is None:
        return None
    for ref in commit.get("refs", []):
        if ref["id"] == head_ref:
            return _HEAD_LANE_COLOR
    return None


def _advance_graph_checkpoint(
    checkpoint: _GraphCheckpoint,
    commits: Sequence[GitCommit],
    *,
    head_ref: str | None,
) -> _GraphCheckpoint:
    """Advance the browser's lane algorithm without retaining row models."""
    previous_output = list(checkpoint.prior_swimlanes)
    color_index = checkpoint.color_index
    by_revision = {commit["id"]: commit for commit in commits}

    for commit in commits:
        output: list[_GraphLane] = []
        first_parent_added = False
        for lane in previous_output:
            if lane.id == commit["id"]:
                if commit["parent_ids"] and not first_parent_added:
                    output.append(
                        _GraphLane(
                            id=commit["parent_ids"][0],
                            color=_label_color(commit, head_ref) or lane.color,
                        )
                    )
                    first_parent_added = True
                continue
            output.append(lane)

        start = 1 if first_parent_added else 0
        for index in range(start, len(commit["parent_ids"])):
            color: str | None = None
            if index == 0:
                color = _label_color(commit, head_ref)
            else:
                parent = by_revision.get(commit["parent_ids"][index])
                if parent is not None:
                    color = _label_color(parent, head_ref)
            if color is None:
                color_index = (color_index + 1) % len(_LANE_COLORS)
                color = _LANE_COLORS[color_index]
            output.append(_GraphLane(id=commit["parent_ids"][index], color=color))
        previous_output = output

    return _GraphCheckpoint(tuple(previous_output), color_index)


def _wire_graph_checkpoint(
    checkpoint: _GraphCheckpoint,
    *,
    scope: HistoryScope,
) -> GitGraphCheckpoint:
    lanes: list[GitGraphLane] = [
        GitGraphLane(id=lane.id, color=lane.color) for lane in checkpoint.prior_swimlanes
    ]
    return GitGraphCheckpoint(
        version=1,
        prior_swimlanes=lanes,
        color_index=checkpoint.color_index,
        head_revision=scope.head_revision,
        scope_fingerprint=scope.fingerprint,
    )


async def _drain_stderr(stream: asyncio.StreamReader | None) -> bytes:
    retained = bytearray()
    if stream is None:
        return b""
    while True:
        chunk = await stream.read(_READ_CHUNK_BYTES)
        if not chunk:
            return bytes(retained)
        remaining = _STDERR_RETAIN_BYTES - len(retained)
        if remaining > 0:
            retained.extend(chunk[:remaining])


async def _discard_stream(stream: asyncio.StreamReader | None) -> None:
    """Drain a killed producer so ``Process.wait`` cannot block on its pipe."""
    if stream is None:
        return
    while await stream.read(_READ_CHUNK_BYTES):
        pass


class HistorySession:
    """One demand-driven Git walk plus its bounded indexed replay spool."""

    def __init__(
        self,
        *,
        root: Path,
        scope: HistoryScope,
        page_size: int,
        parser_max_bytes: int,
        storage_max_bytes: int,
        clock: Callable[[], float],
    ) -> None:
        self.id = secrets.token_urlsafe(18)
        self.root = root.resolve()
        self.scope = scope
        self.page_size = page_size
        # The budget passed in was measured for one GIT_LOG_DEFAULT_LIMIT
        # page (explorations/git-history/README.md), but a route-legal
        # ``limit`` reaches GIT_LOG_MAX_LIMIT. The accumulated-page budget
        # must scale with the page this session builds, or a legal
        # ``limit=1000`` overruns the default-page budget on an ordinary
        # repository and surfaces as a 500.
        default_pages = -(-page_size // GIT_LOG_DEFAULT_LIMIT)
        self.parser_max_bytes = parser_max_bytes * max(1, default_pages)
        self.storage_max_bytes = storage_max_bytes
        self._clock = clock
        self.last_access = clock()
        self._temporary_directory: tempfile.TemporaryDirectory[str] | None = None
        self._spool_path: Path | None = None
        self._process: asyncio.subprocess.Process | None = None
        self._stderr_task: asyncio.Task[bytes] | None = None
        self._stderr = b""
        self._buffer = bytearray()
        self._lookahead: tuple[bytes, GitCommit] | None = None
        self._frames: list[_Frame] = []
        self._graph_checkpoint = _GraphCheckpoint((), -1)
        self._storage_bytes = 0
        self._closed = False
        self._lock = asyncio.Lock()
        self.command_args: tuple[str, ...] = ()

    @classmethod
    async def start(
        cls,
        *,
        root: Path,
        scope: HistoryScope,
        page_size: int,
        parser_max_bytes: int,
        storage_max_bytes: int,
        clock: Callable[[], float],
    ) -> HistorySession:
        session = cls(
            root=root,
            scope=scope,
            page_size=page_size,
            parser_max_bytes=parser_max_bytes,
            storage_max_bytes=storage_max_bytes,
            clock=clock,
        )
        session._temporary_directory = await asyncio.to_thread(
            tempfile.TemporaryDirectory,
            prefix="metabrowser-git-history-",
        )
        session._spool_path = Path(session._temporary_directory.name) / "pages.bin"
        args = (
            "log",
            "-z",
            f"--format={LOG_FORMAT}",
            "--decorate=full",
            "--date-order",
            "--stdin",
        )
        session.command_args = args
        try:
            session._process = await spawn_git_process(
                args,
                cwd=session.root,
                pipe_stdin=True,
            )
        except BaseException:
            await asyncio.to_thread(session._temporary_directory.cleanup)
            session._temporary_directory = None
            raise
        session._stderr_task = asyncio.create_task(
            _drain_stderr(session._process.stderr),
            name=f"metabrowser-git-history-stderr-{session.id}",
        )
        try:
            async with asyncio.timeout(GIT_SUBPROCESS_TIMEOUT_S):
                await session._write_scope(scope.arguments)
        except TimeoutError:
            await session._close_locked()
            raise GitTimeoutError("git history scope timed out and was terminated") from None
        except BaseException:
            await session._close_locked()
            raise
        return session

    async def _write_scope(self, revisions: Sequence[str]) -> None:
        process = self._process
        if process is None or process.stdin is None:
            raise GitError("git history process has no scope input")
        process.stdin.write(("\n".join(revisions) + "\n").encode("ascii"))
        try:
            await process.stdin.drain()
        finally:
            process.stdin.close()
            with contextlib.suppress(BrokenPipeError, ConnectionResetError):
                await process.stdin.wait_closed()

    @property
    def walk_active(self) -> bool:
        return not self._closed and self._process is not None and self._process.returncode is None

    @property
    def closed(self) -> bool:
        return self._closed

    @property
    def spool_path(self) -> Path | None:
        return self._spool_path

    async def page(self, cursor: HistoryCursor) -> GitLogPage:
        """Build or replay the exact page named by *cursor*."""
        async with self._lock:
            if self._closed:
                raise ExpiredHistorySessionError("history session is closed")
            self.last_access = self._clock()
            if cursor.page > len(self._frames):
                raise InvalidHistoryCursorError("cursor skips an unvisited history page")
            if cursor.page == len(self._frames):
                if cursor.direction != "next" and cursor.page != 0:
                    raise InvalidHistoryCursorError("cursor cannot build this history page")
                try:
                    async with asyncio.timeout(GIT_SUBPROCESS_TIMEOUT_S):
                        frame, commits = await self._build_next_page()
                except TimeoutError:
                    await self._close_locked()
                    raise GitTimeoutError("git history page timed out and was terminated") from None
                except asyncio.CancelledError:
                    await self._close_locked()
                    raise
                self._frames.append(frame)
            else:
                frame = self._frames[cursor.page]
                commits = await self._replay_frame(frame)
            self.last_access = self._clock()
            return self._wire_page(cursor.page, frame, commits)

    async def _build_next_page(self) -> tuple[_Frame, list[GitCommit]]:
        records = bytearray()
        commits: list[GitCommit] = []
        if self._lookahead is not None:
            raw, commit = self._lookahead
            self._lookahead = None
            records.extend(raw)
            records.append(0)
            commits.append(commit)

        while len(commits) < self.page_size:
            item = await self._read_next_commit(len(records))
            if item is None:
                break
            raw, commit = item
            records.extend(raw)
            records.append(0)
            commits.append(commit)

        if len(commits) == self.page_size:
            self._lookahead = await self._read_next_commit(len(records))
        has_more = self._lookahead is not None
        if not commits and self._frames:
            raise InvalidHistoryCursorError("cursor points past the end of history")
        checkpoint = self._graph_checkpoint
        frame = await self._append_frame(
            bytes(records),
            len(commits),
            has_more,
            graph_checkpoint=checkpoint,
        )
        self._graph_checkpoint = _advance_graph_checkpoint(
            checkpoint,
            commits,
            head_ref=self.scope.head_ref,
        )
        return frame, commits

    async def _read_next_commit(self, page_bytes: int) -> tuple[bytes, GitCommit] | None:
        process = self._process
        if process is None or process.stdout is None:
            return None
        while True:
            boundary = self._buffer.find(0)
            if boundary >= 0:
                raw = bytes(self._buffer[:boundary])
                del self._buffer[: boundary + 1]
                parsed = parse_log_output(raw + b"\0")
                if parsed:
                    return raw, parsed[0]
                continue
            remaining = self.parser_max_bytes - page_bytes - len(self._buffer)
            if remaining <= 0:
                raise HistoryParserError("git history parser exceeded its measured buffer budget")
            chunk = await process.stdout.read(min(_READ_CHUNK_BYTES, remaining))
            if not chunk:
                if self._buffer:
                    raise HistoryParserError("git history stream ended inside a commit record")
                await self._finish_process()
                return None
            self._buffer.extend(chunk)

    async def _finish_process(self) -> None:
        process = self._process
        if process is None:
            return
        returncode = await process.wait()
        if self._stderr_task is not None:
            self._stderr = await self._stderr_task
            self._stderr_task = None
        self._process = None
        if returncode != 0:
            detail = self._stderr.decode("utf-8", errors="replace").strip()
            raise GitCommandError(self.command_args, returncode, detail)

    async def _append_frame(
        self,
        payload: bytes,
        commit_count: int,
        has_more: bool,
        *,
        graph_checkpoint: _GraphCheckpoint,
    ) -> _Frame:
        frame_bytes = _FRAME_HEADER.size + len(payload)
        if self._storage_bytes + frame_bytes > self.storage_max_bytes:
            await self._close_locked()
            raise HistoryStorageError("git history session storage budget exhausted")
        spool_path = self._spool_path
        if spool_path is None:
            raise ExpiredHistorySessionError("history spool no longer exists")

        def append() -> tuple[int, int]:
            with spool_path.open("ab") as destination:
                offset = destination.tell()
                destination.write(_FRAME_HEADER.pack(len(payload)))
                destination.write(payload)
                destination.flush()
            return offset, frame_bytes

        try:
            offset, written = await asyncio.to_thread(append)
        except OSError as exc:
            await self._close_locked()
            raise HistoryStorageError("git history replay spool write failed") from exc
        self._storage_bytes += written
        return _Frame(
            offset=offset,
            length=len(payload),
            commit_count=commit_count,
            has_more=has_more,
            graph_checkpoint=graph_checkpoint,
        )

    async def _replay_frame(self, frame: _Frame) -> list[GitCommit]:
        spool_path = self._spool_path
        if spool_path is None:
            raise ExpiredHistorySessionError("history spool no longer exists")

        def read() -> bytes:
            with spool_path.open("rb") as source:
                source.seek(frame.offset)
                header = source.read(_FRAME_HEADER.size)
                if len(header) != _FRAME_HEADER.size:
                    raise HistoryParserError("git history frame header is truncated")
                length = _FRAME_HEADER.unpack(header)[0]
                if length != frame.length:
                    raise HistoryParserError("git history frame index is inconsistent")
                payload = source.read(length)
                if len(payload) != length:
                    raise HistoryParserError("git history frame payload is truncated")
                return payload

        try:
            payload = await asyncio.to_thread(read)
        except OSError as exc:
            raise HistoryStorageError("git history replay spool read failed") from exc
        commits = parse_log_output(payload)
        if len(commits) != frame.commit_count:
            raise HistoryParserError("git history replay changed its commit count")
        return commits

    def _cursor(self, page: int, direction: HistoryCursorDirection) -> str:
        return encode_history_cursor(
            HistoryCursor(
                session_id=self.id,
                page=page,
                direction=direction,
                scope_fingerprint=self.scope.fingerprint,
                page_size=self.page_size,
            )
        )

    def _wire_page(self, page: int, frame: _Frame, commits: list[GitCommit]) -> GitLogPage:
        return GitLogPage(
            is_repo=True,
            commits=commits,
            cursor=self._cursor(page + 1, "next") if frame.has_more else None,
            has_more=frame.has_more,
            page=page,
            page_cursor=self._cursor(page, "current"),
            previous_cursor=self._cursor(page - 1, "previous") if page > 0 else None,
            scope=self.scope.name,
            scope_refs=list(self.scope.display_refs),
            scope_fingerprint=self.scope.fingerprint,
            graph_checkpoint=_wire_graph_checkpoint(
                frame.graph_checkpoint,
                scope=self.scope,
            ),
        )

    async def close(self) -> None:
        """Terminate the walk and delete every private session resource."""
        async with self._lock:
            await self._close_locked()

    async def _close_locked(self) -> None:
        if self._closed:
            return
        self._closed = True
        process = self._process
        self._process = None
        if process is not None:
            # A demand-driven walk normally leaves unread history in stdout.
            # On platforms where the asyncio transport waits for pipe EOF,
            # reaping a killed child before draining that buffered output can
            # deadlock session eviction. Start the discard first so it runs
            # concurrently with ``Process.wait`` inside the shared terminator.
            stdout_task = asyncio.create_task(
                _discard_stream(process.stdout),
                name=f"metabrowser-git-history-stdout-{self.id}",
            )
            try:
                await terminate_git_process(process)
            finally:
                with contextlib.suppress(asyncio.CancelledError):
                    await stdout_task
        if self._stderr_task is not None:
            with contextlib.suppress(asyncio.CancelledError):
                self._stderr = await self._stderr_task
            self._stderr_task = None
        temporary_directory = self._temporary_directory
        self._temporary_directory = None
        self._spool_path = None
        self._frames.clear()
        self._buffer.clear()
        self._lookahead = None
        if temporary_directory is not None:
            await asyncio.to_thread(temporary_directory.cleanup)


class HistorySessionRegistry:
    """Process-wide LRU owner for bounded history sessions and Git walks."""

    def __init__(
        self,
        *,
        max_entries: int = GIT_HISTORY_SESSION_MAX_ENTRIES,
        max_walks: int = GIT_HISTORY_SESSION_MAX_WALKS,
        idle_ttl_s: float = GIT_HISTORY_SESSION_IDLE_TTL_S,
        parser_max_bytes: int = GIT_HISTORY_SESSION_PARSER_MAX_BYTES,
        storage_max_bytes: int = GIT_HISTORY_SESSION_MAX_STORAGE_BYTES,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        if min(max_entries, max_walks, parser_max_bytes, storage_max_bytes) < 1:
            raise ValueError("history session budgets must be positive")
        if idle_ttl_s <= 0:
            raise ValueError("history session idle lifetime must be positive")
        self.max_entries = max_entries
        self.max_walks = max_walks
        self.idle_ttl_s = idle_ttl_s
        self.parser_max_bytes = parser_max_bytes
        self.storage_max_bytes = storage_max_bytes
        self._clock = clock
        self._sessions: dict[str, HistorySession] = {}
        self._lock = asyncio.Lock()
        self._create_lock = asyncio.Lock()
        self._reaper_task: asyncio.Task[None] | None = None

    @property
    def session_count(self) -> int:
        return len(self._sessions)

    async def read_page(
        self,
        root: Path,
        *,
        wants_all: bool | None,
        limit: int,
        cursor: str | None,
    ) -> GitLogPage:
        """Start, advance, or replay one page of a bounded history session."""
        self._ensure_reaper()
        if cursor is None:
            scope = await resolve_history_scope(root, wants_all=bool(wants_all))
            session = await self._create_session(root, scope=scope, page_size=limit)
            first = HistoryCursor(
                session_id=session.id,
                page=0,
                direction="next",
                scope_fingerprint=scope.fingerprint,
                page_size=limit,
            )
            try:
                return await session.page(first)
            except BaseException:
                await self._discard(session.id)
                raise

        decoded = decode_history_cursor(cursor)
        if decoded is None:
            raise InvalidHistoryCursorError("invalid history cursor")
        async with self._lock:
            session = self._sessions.get(decoded.session_id)
        if session is None or session.closed:
            raise ExpiredHistorySessionError("history session expired or was evicted")
        if decoded.page_size != limit:
            raise InvalidHistoryCursorError("history cursor page size changed")
        if decoded.scope_fingerprint != session.scope.fingerprint:
            raise InvalidHistoryCursorError("history cursor scope fingerprint is invalid")
        if session.root != root.resolve():
            await self._discard(session.id)
            raise StaleHistorySessionError("history cursor repository changed")
        if wants_all is not None:
            requested_scope: HistoryScopeName = "all" if wants_all else "default"
            if requested_scope != session.scope.name:
                await self._discard(session.id)
                raise StaleHistorySessionError("history cursor scope changed")
        current_scope = await resolve_history_scope(
            root,
            wants_all=session.scope.name == "all",
        )
        if current_scope.fingerprint != session.scope.fingerprint:
            await self._discard(session.id)
            raise StaleHistorySessionError("history refs changed during paging")
        try:
            return await session.page(decoded)
        except (GitError, HistoryStorageError):
            await self._discard(session.id)
            raise

    async def _create_session(
        self,
        root: Path,
        *,
        scope: HistoryScope,
        page_size: int,
    ) -> HistorySession:
        async with self._create_lock:
            await self.reap_expired()
            evicted: list[HistorySession] = []
            async with self._lock:
                while (
                    sum(session.walk_active for session in self._sessions.values())
                    >= self.max_walks
                ):
                    victim = min(
                        (session for session in self._sessions.values() if session.walk_active),
                        key=lambda session: session.last_access,
                    )
                    self._sessions.pop(victim.id, None)
                    evicted.append(victim)
                while len(self._sessions) >= self.max_entries:
                    victim = min(self._sessions.values(), key=lambda session: session.last_access)
                    self._sessions.pop(victim.id, None)
                    evicted.append(victim)
            for victim in evicted:
                await victim.close()

            session = await HistorySession.start(
                root=root,
                scope=scope,
                page_size=page_size,
                parser_max_bytes=self.parser_max_bytes,
                storage_max_bytes=self.storage_max_bytes,
                clock=self._clock,
            )
            async with self._lock:
                self._sessions[session.id] = session
            return session

    def _ensure_reaper(self) -> None:
        if self._reaper_task is None or self._reaper_task.done():
            self._reaper_task = asyncio.create_task(
                self._reap_loop(),
                name="metabrowser-git-history-reaper",
            )

    async def _reap_loop(self) -> None:
        interval = min(self.idle_ttl_s / 2, _REAPER_MAX_INTERVAL_S)
        while True:
            await asyncio.sleep(interval)
            try:
                await self.reap_expired()
            except Exception:
                # If a failing pass ended the loop, every remaining idle
                # session would keep its git process and spool directory
                # until process exit — the leak the idle TTL exists to
                # prevent. Cancellation still propagates and stops the
                # task.
                log.exception("git history reaper pass failed")

    async def reap_expired(self) -> None:
        """Close sessions whose last access is outside the idle budget."""
        cutoff = self._clock() - self.idle_ttl_s
        async with self._lock:
            expired = [
                session for session in self._sessions.values() if session.last_access <= cutoff
            ]
            for session in expired:
                self._sessions.pop(session.id, None)
        for session in expired:
            # A spool held open or a read-only temp filesystem fails one
            # session's cleanup; the other expired sessions still close.
            try:
                await session.close()
            except Exception:
                log.exception("git history session %s cleanup failed", session.id)

    async def _discard(self, session_id: str) -> None:
        async with self._lock:
            session = self._sessions.pop(session_id, None)
        if session is not None:
            await session.close()

    async def close_all(self) -> None:
        """Stop the reaper, terminate all walks, and remove every spool."""
        reaper = self._reaper_task
        self._reaper_task = None
        if reaper is not None and reaper is not asyncio.current_task():
            reaper.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await reaper
        async with self._lock:
            sessions = list(self._sessions.values())
            self._sessions.clear()
        for session in sessions:
            await session.close()


HISTORY_SESSIONS = HistorySessionRegistry()


async def close_history_sessions() -> None:
    """Release process-wide Git history resources during server shutdown."""
    await HISTORY_SESSIONS.close_all()


__all__ = [
    "ExpiredHistorySessionError",
    "HISTORY_SESSIONS",
    "HistoryCursor",
    "HistoryParserError",
    "HistorySessionRegistry",
    "HistoryStorageError",
    "InvalidHistoryCursorError",
    "StaleHistorySessionError",
    "close_history_sessions",
    "decode_history_cursor",
    "encode_history_cursor",
    "resolve_history_scope",
]
