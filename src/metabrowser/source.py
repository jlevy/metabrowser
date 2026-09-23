"""One active repository subject and its content-source ports.

Filesystem browsing keeps its current Path helpers. Git revision subjects
attach here; GitPath and blob batch readers stay in ``git.tree_source``.
Git discovery, history, refs, commit detail, file, raw, tree, diffs, and KPress honor
a pinned revision. ``InventoryCoordinator.open_subject`` accepts a Git pin without
opening a filesystem walker. The CLI can ``--show`` / ``--api`` a ``file://``
pin in-process, and serve mode hands the server an opener through
:func:`serve_subject_opener` so the application lifespan opens the pin in its own
event loop and closes it at shutdown. Opening https/ssh stays later.
"""

from __future__ import annotations

import asyncio
from collections.abc import AsyncGenerator, Awaitable, Callable, Generator
from contextlib import asynccontextmanager, contextmanager
from dataclasses import dataclass, field
from enum import StrEnum
from pathlib import Path
from typing import IO, Protocol, runtime_checkable

from strif import file_mtime_hash

import metabrowser.paths_safe as paths_safe
from metabrowser.content_errors import ContentReadError, ContentUnavailableError
from metabrowser.gz_io import ArtifactCompressionError, ArtifactPath
from metabrowser.inventory_engine.contract import canonical_inventory_path, native_inventory_path
from metabrowser.paths_safe import _is_within, _relativize, register_root_callback


class RepositorySubjectKind(StrEnum):
    attached_filesystem = "attached_filesystem"
    git_revision = "git_revision"


@dataclass(frozen=True, slots=True)
class SourceCapabilities:
    """What the active subject can actually do.

    These are source-kind facts, not the process content-trust flags.
    A local folder supports mutation even when writes stay off.
    """

    navigation: bool
    index: bool
    recency: bool
    ignore: bool
    watcher: bool
    activity: bool
    mutation: bool

    def as_wire(self) -> dict[str, bool]:
        return {
            "navigation": self.navigation,
            "index": self.index,
            "recency": self.recency,
            "ignore": self.ignore,
            "watcher": self.watcher,
            "activity": self.activity,
            "mutation": self.mutation,
        }

    def require(self, capability: str) -> None:
        try:
            allowed = getattr(self, capability)
        except AttributeError:
            raise UnsupportedSourceCapabilityError(capability) from None
        if not allowed:
            raise UnsupportedSourceCapabilityError(capability)


FILESYSTEM_CAPABILITIES = SourceCapabilities(
    navigation=True,
    index=True,
    recency=True,
    ignore=True,
    watcher=True,
    activity=True,
    mutation=True,
)


class UnsupportedSourceCapabilityError(ContentReadError):
    """The active subject does not implement the named capability."""

    code = "unsupported_for_subject"
    http_status = 409

    def __init__(self, capability: str) -> None:
        self.capability = capability
        super().__init__(f"source does not support {capability}")


def unsupported_source_payload(exc: UnsupportedSourceCapabilityError) -> dict[str, str]:
    return {
        "error": str(exc),
        "code": "unsupported_for_subject",
        "capability": exc.capability,
    }


@dataclass(frozen=True, slots=True)
class ContentHandle:
    """One resolved identity on the active subject.

    `path` is set only for an attached filesystem. Git blob reads go
    through ``GitTreeSource``, not this path.
    """

    identity: str
    path: Path | None
    exists: bool
    is_dir: bool
    is_file: bool

    @classmethod
    def from_path(cls, identity: str, target: Path) -> ContentHandle:
        try:
            exists = target.exists()
            is_dir = exists and target.is_dir()
            is_file = exists and target.is_file()
        except OSError:
            exists = False
            is_dir = False
            is_file = False
        return cls(
            identity=identity,
            path=target,
            exists=exists,
            is_dir=is_dir,
            is_file=is_file,
        )


# The deepest inner path a container may expose beneath its own file, counted
# from the container, not from the served root. One value for the server's
# ancestor walk, the pin's wire split, and every plugin's container hook, so the
# three implementations of this security-relevant rule cannot drift apart.
MAX_CONTAINER_INNER_DEPTH = 16


@dataclass(frozen=True, slots=True)
class ContentStat:
    """The validated logical size of one content object.

    Logical: the decompressed length of a compressed artifact, the stored
    length of a Git blob. Establishing it can cost a full decode and can fail,
    which is why it is a call of its own rather than a field on the reference.

    A caller that only needs to know whether content fits a bound should ask
    for that many bytes instead. A compressed artifact declares its length in a
    trailer nothing verifies until the stream is decoded, so a bounded read is
    the answer that cannot be forged.
    """

    size: int


@dataclass(frozen=True, slots=True)
class ContentWindow:
    """Exactly the bytes one bounded read returned.

    ``has_more`` says whether content continues past ``offset + len(data)``.
    It is answered by the read itself, so a caller never needs a second open
    to find out whether it has reached the end.
    """

    data: bytes
    offset: int
    has_more: bool


@runtime_checkable
class ContentReader(Protocol):
    """The bounded port one resolved content object hands out.

    Both methods run their blocking work off the event loop: an attached
    filesystem in the thread pool, a pin through its pooled ``cat-file``
    actors, which are already async.
    """

    async def stat(self) -> ContentStat: ...

    async def read_window(self, *, offset: int, max_bytes: int) -> ContentWindow: ...


@dataclass(frozen=True, slots=True)
class ContentRef:
    """An opaque reference to one readable content object.

    It carries the three facts resolution already established and a hook needs
    before it reads anything: the identity to echo back to the client, the
    logical extension to dispatch on, and a fingerprint that changes exactly
    when the bytes can have, so a hook keys its own cache on it without knowing
    whether that is an mtime hash or a blob object id. It is not a path, a
    cache location, or a handle on the source.
    """

    identity: str
    logical_ext: str
    fingerprint: str
    reader: ContentReader = field(repr=False, compare=False)


class ContentSource(Protocol):
    def resolve(self, identity: str) -> ContentHandle | None:
        """Resolve a canonical inventory identity, or None when it escapes."""

    async def open_ref(self, identity: str) -> ContentRef | None:
        """Resolve an identity to readable content, or None when it is not.

        None covers every way an identity names nothing readable: traversal out
        of the served root, a missing name, a directory or tree, an unusable
        symlink. A failure while reading to resolve raises a
        :class:`~metabrowser.content_errors.ContentReadError` instead.
        """

    async def open_container(
        self, identity: str, *, suffixes: tuple[str, ...]
    ) -> tuple[ContentRef, str] | None:
        """Split ``<content>/<inner>`` into readable content and its inner path.

        ``suffixes`` are the logical extensions the calling container claims;
        anything else resolves to None so one plugin cannot open another's
        files. The inner path is empty when the identity names the content
        itself.
        """


class RepositorySubject(Protocol):
    @property
    def kind(self) -> str: ...

    @property
    def identity(self) -> str: ...

    @property
    def capabilities(self) -> SourceCapabilities: ...

    @property
    def content(self) -> ContentSource: ...

    @property
    def filesystem_root(self) -> Path | None: ...


class ClosableRepositorySubject(RepositorySubject, Protocol):
    """A subject that owns resources, such as Git processes, until it is closed."""

    async def aclose(self) -> None: ...


SubjectOpener = Callable[[], Awaitable[ClosableRepositorySubject]]
"""Opens the subject a server serves, in the event loop that will serve it."""


# Copying a decompressed stream forward to reach an offset. A compressed
# artifact's stream is not seekable, so reaching offset N costs decompressing N
# bytes; see the binary plugin's sidekick for the measurements that make that
# acceptable at these bounds.
_SKIP_CHUNK_BYTES = 64 * 1024


def _skip_forward(stream: IO[bytes], offset: int) -> None:
    """Advance a non-seekable decompressed stream to ``offset``."""

    remaining = offset
    while remaining > 0:
        skipped = stream.read(min(_SKIP_CHUNK_BYTES, remaining))
        if not skipped:
            return
        remaining -= len(skipped)


def read_artifact_window(artifact: ArtifactPath, offset: int, max_bytes: int) -> ContentWindow:
    """Read ``max_bytes`` logical bytes at ``offset``, plus whether more remain.

    Reads one byte past the window to answer "is there more?" without a second
    open, and clips it back off before returning. The output bound is the
    window itself, so a compressed artifact cannot expand past what the caller
    asked for. Blocking: callers reach it through the thread pool.
    """

    with artifact.open_binary(max_output_bytes=offset + max_bytes + 1) as stream:
        if artifact.is_compressed:
            _skip_forward(stream, offset)
        else:
            stream.seek(offset)
        raw = stream.read(max_bytes + 1)
    return ContentWindow(data=raw[:max_bytes], offset=offset, has_more=len(raw) > max_bytes)


@dataclass(frozen=True, slots=True)
class _FilesystemContentReader:
    """Bounded reads of one file under the served root, off the event loop."""

    artifact: ArtifactPath

    async def stat(self) -> ContentStat:
        return await asyncio.to_thread(self._stat)

    async def read_window(self, *, offset: int, max_bytes: int) -> ContentWindow:
        return await asyncio.to_thread(self._read_window, offset, max_bytes)

    def _stat(self) -> ContentStat:
        with _filesystem_failures(self.artifact):
            return ContentStat(size=self.artifact.logical_size)

    def _read_window(self, offset: int, max_bytes: int) -> ContentWindow:
        with _filesystem_failures(self.artifact):
            return read_artifact_window(self.artifact, offset, max_bytes)


@contextmanager
def _filesystem_failures(artifact: ArtifactPath) -> Generator[None]:
    """Map a filesystem read failure into the shared content vocabulary.

    A compression failure is already in it and keeps its own code. Everything
    else an ``OSError`` reports here -- the file was replaced, unlinked, or is
    no longer readable -- is content that resolved and then went away, which is
    what a pinned store reports as a missing object.
    """

    try:
        yield
    except ArtifactCompressionError:
        raise
    except OSError as exc:
        raise ContentUnavailableError(artifact.disk_path.name) from exc


class FilesystemContentSource:
    """Identity and document resolution against one exact filesystem root."""

    def __init__(self, root: Path) -> None:
        self._root = root.resolve()

    def resolve(self, identity: str) -> ContentHandle | None:
        native = native_inventory_path(identity)
        if native is None:
            return None
        return self._resolve_native(identity, native)

    def resolve_document(self, requested: str) -> ContentHandle | None:
        return self._resolve_native(requested, requested)

    async def open_ref(self, identity: str) -> ContentRef | None:
        return await asyncio.to_thread(self._open_ref, identity)

    async def open_container(
        self, identity: str, *, suffixes: tuple[str, ...]
    ) -> tuple[ContentRef, str] | None:
        return await asyncio.to_thread(self._open_container, identity, suffixes)

    def _open_ref(self, identity: str) -> ContentRef | None:
        handle = self.resolve(identity)
        if handle is None or handle.path is None or not handle.is_file:
            return None
        artifact = ArtifactPath(handle.path)
        try:
            fingerprint = file_mtime_hash(handle.path)
        except OSError:
            # Unlinked or replaced between the resolve and the hash. There is
            # nothing readable at this identity after all.
            return None
        return ContentRef(
            identity=_identity_for(handle.path) or identity,
            logical_ext=artifact.logical_ext,
            fingerprint=fingerprint,
            reader=_FilesystemContentReader(artifact),
        )

    def _open_container(
        self, identity: str, suffixes: tuple[str, ...]
    ) -> tuple[ContentRef, str] | None:
        """Nearest-file-ancestor resolution, scoped to the caller's suffixes.

        The walk is bounded, every prefix passes the same served-root gate, and
        a real directory ancestor means the request was an ordinary missing
        file rather than a container child.
        """

        direct = self._open_ref(identity)
        if direct is not None:
            return (direct, "") if direct.logical_ext in suffixes else None
        parts = identity.split("/")
        if len(parts) < 2:
            return None
        for cut in range(len(parts) - 1, 0, -1):
            prefix = "/".join(parts[:cut])
            handle = self.resolve(prefix)
            if handle is None:
                continue
            if handle.is_dir:
                return None
            if not handle.is_file:
                # Nothing at this depth; keep walking toward the root.
                continue
            if len(parts) - cut > MAX_CONTAINER_INNER_DEPTH:
                # The bound is on the inner path, measured from the claiming
                # file -- a deeply nested container keeps its full reach.
                return None
            inner = native_inventory_path("/".join(parts[cut:]))
            if inner is None:
                return None
            ref = self._open_ref(prefix)
            if ref is None or ref.logical_ext not in suffixes:
                return None
            return ref, inner
        return None

    def _resolve_native(self, identity: str, native: str) -> ContentHandle | None:
        if not native:
            return ContentHandle.from_path(identity, self._root)
        try:
            target = (self._root / native).resolve()
        except ValueError:
            # A name the platform cannot express at all -- an embedded NUL,
            # which `/raw/a%00b` decodes to -- makes `resolve` raise before
            # any syscall. That is the same answer as traversal: there is no
            # such file under this root, so it is a refusal, not a crash.
            return None
        if not _is_within(target, self._root):
            return None
        return ContentHandle.from_path(identity, target)


class AttachedFilesystemSubject:
    """The current served folder, expressed as a repository subject."""

    kind = RepositorySubjectKind.attached_filesystem.value

    def __init__(self, root: Path) -> None:
        resolved = root.resolve()
        self._identity = str(resolved)
        self._capabilities = FILESYSTEM_CAPABILITIES
        self._content = FilesystemContentSource(resolved)
        self._filesystem_root = resolved

    @property
    def identity(self) -> str:
        return self._identity

    @property
    def capabilities(self) -> SourceCapabilities:
        return self._capabilities

    @property
    def content(self) -> ContentSource:
        return self._content

    @property
    def filesystem_root(self) -> Path | None:
        return self._filesystem_root


@dataclass(slots=True)
class SourceLease:
    generation: int
    _held: bool = True

    @property
    def held(self) -> bool:
        return self._held

    def release(self) -> None:
        self._held = False


@dataclass(slots=True)
class SourceSession:
    """The one active subject for this server/browser process."""

    subject: RepositorySubject
    generation: int
    lease: SourceLease

    @property
    def content(self) -> ContentSource:
        return self.subject.content

    @property
    def capabilities(self) -> SourceCapabilities:
        return self.subject.capabilities

    def close(self) -> None:
        self.lease.release()

    def as_wire(self) -> dict[str, object]:
        return {
            "kind": self.subject.kind,
            "generation": self.generation,
            "capabilities": self.capabilities.as_wire(),
            "lease": "held" if self.lease.held else "released",
        }


class SubjectOpenError(Exception):
    """The served subject did not open. The message names no path and is fit to print."""


class SubjectNotOpenError(RuntimeError):
    """A subject is configured to be served, and none is open to answer this request.

    Only a request made outside the application lifespan meets it: before startup,
    after shutdown, or from a client that never ran the lifespan. Falling back to
    the filesystem root there would serve the working directory in place of the pin.
    """

    def __init__(self) -> None:
        super().__init__("the served subject is not open")


_session: SourceSession | None = None
_generation = 0
_subject_opener: SubjectOpener | None = None
_open_failure: SubjectOpenError | None = None


def attach_subject(subject: RepositorySubject) -> SourceSession:
    """Install `subject` as the sole active session, releasing any previous lease."""

    global _session, _generation
    if _session is not None:
        _session.close()
    _generation += 1
    _session = SourceSession(
        subject=subject,
        generation=_generation,
        lease=SourceLease(generation=_generation),
    )
    return _session


def detach_session(session: SourceSession) -> None:
    """Release *session* if it is still the active one; a newer attach is left alone.

    The generation counter keeps counting, so a later attach in the same process
    never reuses a generation a client may still hold.
    """

    global _session
    if _session is session:
        session.close()
        _session = None


def get_source_session() -> SourceSession:
    """Return the active session, wrapping `ROOT_DIR` if nothing is attached yet.

    While an opener is configured, only the lifespan attaches the subject, so a
    request with none attached raises :class:`SubjectNotOpenError` instead.
    """

    global _session
    if _session is None:
        if _subject_opener is not None:
            raise SubjectNotOpenError
        return attach_subject(AttachedFilesystemSubject(paths_safe.ROOT_DIR))
    return _session


def reset_source_session() -> None:
    """Drop the process session and any served opener. Tests restore a root afterwards."""

    global _session, _generation, _subject_opener, _open_failure
    if _session is not None:
        _session.close()
    _session = None
    _generation = 0
    _subject_opener = None
    _open_failure = None


def serve_subject_opener(opener: SubjectOpener | None) -> None:
    """Serve the subject *opener* returns instead of the filesystem root, or stop.

    A pinned revision's batch readers are processes bound to the event loop that
    started them, so a server cannot be handed a subject opened in another loop.
    The application lifespan calls the opener in the serving loop at startup,
    attaches what it returns, and closes it at shutdown; see :func:`lifespan_subject`.
    Setting a filesystem root clears the opener.
    """

    global _subject_opener, _open_failure
    _subject_opener = opener
    _open_failure = None


def subject_open_failure() -> SubjectOpenError | None:
    """Why the configured subject failed to open at the last startup, if it did."""

    return _open_failure


@asynccontextmanager
async def lifespan_subject() -> AsyncGenerator[SourceSession | None]:
    """Open, attach, and at exit close the served subject, when one is configured.

    Without an opener this does nothing, and the filesystem root attaches lazily as
    before. Each entry opens a fresh subject, so a server that starts again after a
    shutdown reads through new processes and a new session generation. An opener
    that fails raises :class:`SubjectOpenError`, which is recorded for
    :func:`subject_open_failure` so a server can report it without a traceback.
    """

    global _open_failure
    opener = _subject_opener
    if opener is None:
        yield None
        return
    _open_failure = None
    try:
        subject = await opener()
    except SubjectOpenError as exc:
        _open_failure = exc
        raise
    session = attach_subject(subject)
    try:
        yield session
    finally:
        detach_session(session)
        await subject.aclose()


def session_filesystem_root() -> Path:
    root = get_source_session().subject.filesystem_root
    if root is None:
        raise UnsupportedSourceCapabilityError("filesystem")
    return root


def require_source_capability(capability: str) -> None:
    get_source_session().capabilities.require(capability)


def require_filesystem_hooks() -> None:
    if get_source_session().subject.filesystem_root is None:
        raise UnsupportedSourceCapabilityError("filesystem")


def require_filter_capabilities(*, recency: bool, include_ignored: bool) -> None:
    capabilities = get_source_session().capabilities
    if recency:
        capabilities.require("recency")
    if not include_ignored:
        capabilities.require("ignore")


def resolve_session_identity(identity: str) -> Path | None:
    handle = get_source_session().content.resolve(identity)
    if handle is None:
        return None
    if handle.path is None:
        raise UnsupportedSourceCapabilityError("filesystem")
    return handle.path


def source_capabilities() -> SourceCapabilities:
    return get_source_session().capabilities


def open_content(identity: str) -> ArtifactPath:
    """Gzip-aware reader for an identity on the active subject.

    Filesystem-only, because an :class:`ArtifactPath` is a path. A hook that
    only needs bytes uses :func:`resolve_content` and
    :func:`read_content_window`, which answer on every source kind.
    """

    require_filesystem_hooks()
    handle = get_source_session().content.resolve(identity)
    if handle is None or handle.path is None:
        raise FileNotFoundError(identity)
    return ArtifactPath(handle.path)


def _identity_for(target: Path) -> str | None:
    relative = _relativize(str(target))
    return canonical_inventory_path(relative) if relative else relative


def _readable_content_source() -> ContentSource:
    """The active source, or a typed refusal when it cannot read content."""

    source = get_source_session().content
    if not hasattr(source, "open_ref"):
        raise UnsupportedSourceCapabilityError("content")
    return source


async def resolve_content(identity: str) -> ContentRef | None:
    """Resolve a request identity to readable content on the active subject.

    The identity is whatever the client was given: an inventory path on an
    attached folder, a ``GitPath`` wire on a pinned revision. A hook passes it
    through unchanged and never builds one itself.

    None means the identity names nothing readable here. A failure part-way
    through -- an unreadable object, a deadline -- raises a
    :class:`~metabrowser.content_errors.ContentReadError`.
    """

    return await _readable_content_source().open_ref(identity)


async def resolve_content_container(
    identity: str, *, suffixes: tuple[str, ...]
) -> tuple[ContentRef, str] | None:
    """Resolve ``<content>/<inner>`` for a container kind. See `ContentSource`."""

    return await _readable_content_source().open_container(identity, suffixes=suffixes)


async def stat_content(ref: ContentRef) -> ContentStat:
    """Logical size, change fingerprint, and logical extension for *ref*."""

    return await ref.reader.stat()


async def read_content_window(ref: ContentRef, *, offset: int = 0, max_bytes: int) -> ContentWindow:
    """Read at most ``max_bytes`` bytes of *ref* starting at ``offset``.

    ``max_bytes`` is required: there is no unbounded read, and the bound is on
    bytes, not on a decoded string, so a caller that decodes afterwards still
    knows what it asked the server to hold. Both arguments are byte counts and
    must not be negative.

    On a pin a blob streams from its start, like a compressed artifact: reaching
    ``offset`` costs reading up to it, and only the window is held, so no blob is
    refused for its size.
    """

    if offset < 0:
        raise ValueError("content offset cannot be negative")
    if max_bytes < 0:
        raise ValueError("content read bound cannot be negative")
    return await ref.reader.read_window(offset=offset, max_bytes=max_bytes)


def _sync_filesystem_subject() -> None:
    global _subject_opener
    # Choosing a filesystem root is choosing to serve it.
    _subject_opener = None
    attach_subject(AttachedFilesystemSubject(paths_safe.ROOT_DIR))


register_root_callback(_sync_filesystem_subject)


__all__ = [
    "FILESYSTEM_CAPABILITIES",
    "MAX_CONTAINER_INNER_DEPTH",
    "AttachedFilesystemSubject",
    "ClosableRepositorySubject",
    "ContentHandle",
    "ContentReadError",
    "ContentReader",
    "ContentRef",
    "ContentSource",
    "ContentStat",
    "ContentUnavailableError",
    "ContentWindow",
    "FilesystemContentSource",
    "RepositorySubject",
    "RepositorySubjectKind",
    "SourceCapabilities",
    "SourceLease",
    "SourceSession",
    "SubjectOpener",
    "SubjectNotOpenError",
    "SubjectOpenError",
    "UnsupportedSourceCapabilityError",
    "attach_subject",
    "detach_session",
    "get_source_session",
    "lifespan_subject",
    "open_content",
    "read_artifact_window",
    "read_content_window",
    "require_filesystem_hooks",
    "require_filter_capabilities",
    "require_source_capability",
    "reset_source_session",
    "resolve_content",
    "resolve_content_container",
    "resolve_session_identity",
    "serve_subject_opener",
    "session_filesystem_root",
    "source_capabilities",
    "stat_content",
    "subject_open_failure",
    "unsupported_source_payload",
]
