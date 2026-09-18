"""One active repository subject and its content-source ports.

Filesystem browsing keeps its current Path helpers. Non-filesystem subjects
arrive later; this module is the boundary they attach to. Git revision
subjects, GitPath, and blob batch readers stay out of this module.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from typing import Protocol

import metabrowser.paths_safe as paths_safe
from metabrowser.gz_io import ArtifactPath
from metabrowser.inventory_engine.contract import native_inventory_path
from metabrowser.paths_safe import _is_within, register_root_callback


class RepositorySubjectKind(StrEnum):
    attached_filesystem = "attached_filesystem"


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


class UnsupportedSourceCapabilityError(Exception):
    """The active subject does not implement the named capability."""

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

    `path` is set only for an attached filesystem. Blob reads stay on the
    later Git-tree subject.
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


class ContentSource(Protocol):
    def resolve(self, identity: str) -> ContentHandle | None:
        """Resolve a canonical inventory identity, or None when it escapes."""


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

    def _resolve_native(self, identity: str, native: str) -> ContentHandle | None:
        if not native:
            return ContentHandle.from_path(identity, self._root)
        target = (self._root / native).resolve()
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


_session: SourceSession | None = None
_generation = 0


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


def get_source_session() -> SourceSession:
    """Return the active session, wrapping `ROOT_DIR` if nothing is attached yet."""

    global _session
    if _session is None:
        return attach_subject(AttachedFilesystemSubject(paths_safe.ROOT_DIR))
    return _session


def reset_source_session() -> None:
    """Drop the process session. Tests restore a filesystem root afterwards."""

    global _session, _generation
    if _session is not None:
        _session.close()
    _session = None
    _generation = 0


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


def content_source() -> ContentSource:
    return get_source_session().content


def open_content(identity: str) -> ArtifactPath:
    """Gzip-aware reader for an identity on the active subject."""

    require_filesystem_hooks()
    handle = get_source_session().content.resolve(identity)
    if handle is None or handle.path is None:
        raise FileNotFoundError(identity)
    return ArtifactPath(handle.path)


def _sync_filesystem_subject() -> None:
    attach_subject(AttachedFilesystemSubject(paths_safe.ROOT_DIR))


register_root_callback(_sync_filesystem_subject)


__all__ = [
    "FILESYSTEM_CAPABILITIES",
    "AttachedFilesystemSubject",
    "ContentHandle",
    "ContentSource",
    "FilesystemContentSource",
    "RepositorySubject",
    "RepositorySubjectKind",
    "SourceCapabilities",
    "SourceLease",
    "SourceSession",
    "UnsupportedSourceCapabilityError",
    "attach_subject",
    "content_source",
    "get_source_session",
    "open_content",
    "require_filesystem_hooks",
    "require_filter_capabilities",
    "require_source_capability",
    "reset_source_session",
    "resolve_session_identity",
    "session_filesystem_root",
    "source_capabilities",
    "unsupported_source_payload",
]
