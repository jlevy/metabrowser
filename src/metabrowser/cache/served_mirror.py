"""The published store a server serves, as the refresh jobs and the pin route use it.

:class:`StoreMirror` is the cache's side of :class:`metabrowser.mirror_refresh.ServedMirror`.
The CLI builds one from the source it acquired or reused and hands it to the server, so
the server reaches the store, its record, and its origin only through these methods.

The server learns one cache path from it, as text to show and never to open:
:attr:`StoreMirror.display` says where the mirror is kept, beside the repository's name
and its origin. A page that showed a commit ID where a folder shows its name, and said
nowhere that its files came out of ``~/.metabrowser``, hid both (decided 2026-10-01,
``mb-fndz``).
"""

from __future__ import annotations

import asyncio
import os
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Final
from urllib.parse import unquote_to_bytes

from metabrowser.cache import acquire
from metabrowser.cache.acquire import PublishedSource
from metabrowser.cache.atomic import RecordError, read_record
from metabrowser.cache.locks import LockBusyError, store_fetch_lock
from metabrowser.cache.paths import store_directory, store_record
from metabrowser.cache.providers import repository_context_for
from metabrowser.cache.records import REPOSITORY_STORE_STATE_CONTRACT_ID, RepositoryStoreState
from metabrowser.cache.repository_store import open_revision
from metabrowser.cache.resolve import list_mirror_refs, ref_tip, resolve_pin
from metabrowser.cache.update import update_store
from metabrowser.cache.urls import GitSource
from metabrowser.git.process import RepositoryStoreTarget, repository_store_target
from metabrowser.git.tree_source import GitRevisionSubject, display_segment
from metabrowser.home import PrivateStorageError
from metabrowser.mirror_refresh import (
    MirrorDisplay,
    MirrorRef,
    RecordedFreshness,
    RefKind,
    RefreshResult,
)
from metabrowser.paths_safe import tilde_path
from metabrowser.repository_context import RepositoryContext

# The longest repository name shown. A checkout is a directory, and a file system holds
# a name of at most 255 bytes, so no checkout is called anything longer; an origin's
# last path segment can run to the 2048 bytes an address may. The heading and the
# tooltip are the only readers, and a longer name ends in an ellipsis.
REPOSITORY_NAME_MAX_CHARS: Final = 255
# What a repository is called when its address names nothing: ``file:///.git``.
UNNAMED_REPOSITORY: Final = "repository"
_PORT: Final = re.compile(r":[0-9]+$")
# What is left of a segment that is no name once ``.git`` is taken off.
_NO_NAME: Final = frozenset({"", ".", ".."})


def repository_name(address: str) -> str:
    """The name a checkout of the repository at *address* would have, safe to show.

    The rule ``git clone`` names its directory by, for every address the cache holds:
    the last path segment, without a trailing ``/.git`` and without a ``.git`` suffix,
    so ``https://github.com/jlevy/squares``, ``file:///srv/squares.git``, and
    ``file:///srv/squares/.git`` are all ``squares``. An address whose path names
    nothing else is called by its host, and by :data:`UNNAMED_REPOSITORY` when it has
    none. A segment that is nothing but dots before ``.git``, such as ``..git``, keeps
    its suffix, since ``.`` and ``..`` are no names.

    *address* is a source's normalized address, which the origin's owner chose. A
    percent-escape is decoded, so a name reads as it is written, and the result goes
    through :func:`~metabrowser.git.tree_source.display_segment`: bytes that are not
    UTF-8, controls, and characters drawn as nothing become U+FFFD. It is cut at
    :data:`REPOSITORY_NAME_MAX_CHARS`. Text to show, never a path to open.
    """

    scheme, separator, rest = address.partition("://")
    if separator:
        authority, _, path = rest.partition("/")
    else:
        # The scp-like form, ``[user@]host:path``.
        authority, _, path = scheme.partition(":")
    segments = [segment for segment in path.split("/") if segment]
    if segments and segments[-1] == ".git":
        segments.pop()
    raw = segments[-1] if segments else _PORT.sub("", authority.rpartition("@")[2])
    # The suffix comes off only when a name is left: ``..git`` is not called ``.``,
    # which is no name and reads as the directory itself.
    if raw.removesuffix(".git") not in _NO_NAME:
        raw = raw.removesuffix(".git")
    name = display_segment(unquote_to_bytes(raw)) or UNNAMED_REPOSITORY
    if len(name) > REPOSITORY_NAME_MAX_CHARS:
        name = name[: REPOSITORY_NAME_MAX_CHARS - 1] + "\u2026"
    return name


def display_origin(address: str) -> str:
    """*address* as a page shows it: a ``file://`` address under the home directory with it as ``~``.

    The address of ``git/squares.git`` in the home directory is shown as
    ``file://~/git/squares.git``, by the rule :func:`display_directory` shows the
    mirror's own location by, so that no
    answer spells out the home directory when it can be abbreviated. The home directory
    is compared as spelled, segment by segment, each decoded as the address encodes it;
    what follows it is left as the address has it, escapes and all. Any other address
    is shown as it is. A control or invisible character is replaced, as in every name
    shown.
    """

    shown = address
    prefix = "file:///"
    if address.startswith(prefix):
        try:
            home = Path.home()
        except (OSError, RuntimeError):
            home = None
        segments = address.removeprefix(prefix).split("/")
        depth = len(home.parts) - 1 if home is not None else 0
        if home is not None and depth and len(segments) >= depth:
            leading = Path("/", *(os.fsdecode(unquote_to_bytes(part)) for part in segments[:depth]))
            if tilde_path(leading, home) == "~":
                shown = "file://" + "/".join(["~", *segments[depth:]])
    return display_segment(shown.encode("utf-8", "surrogateescape"))


def display_directory(directory: Path) -> str:
    """*directory* as a person would type it: the home directory as ``~``.

    Abbreviated only when it is under the home directory, and absolute otherwise, as a
    served folder's own path is. A control or invisible character in it is replaced, as
    in every name shown.
    """

    try:
        shown = tilde_path(directory, Path.home())
    except (OSError, RuntimeError):
        shown = str(directory)
    return display_segment(shown.encode("utf-8", "surrogateescape"))


@dataclass(frozen=True, slots=True)
class StoreMirror:
    """One published store: the home it lives in, its key, its identity, and its source.

    *source* is the source the store was acquired for; a refresh fetches from its URL.
    """

    home: Path
    store_key: str
    store_id: str
    source: GitSource

    @classmethod
    def from_published(cls, published: PublishedSource) -> StoreMirror:
        return cls(
            home=published.home,
            store_key=published.store_key,
            store_id=published.store_id,
            source=published.source,
        )

    @property
    def key(self) -> str:
        return self.store_key

    @property
    def _repository(self) -> Path:
        return self.home / store_directory(self.store_key) / "repository.git"

    def _target(self) -> RepositoryStoreTarget:
        return repository_store_target(git_dir=self._repository)

    @property
    def display(self) -> MirrorDisplay:
        """The repository's name, its origin, and where this mirror is kept.

        The location is the store's bare repository, not the source's directory under
        ``cache/sources``. That directory carries the repository's name, but it holds
        three small records and no Git object: ``du`` there measures a few kilobytes,
        and ``git -C`` there fails. The bare repository is what every page is read
        from, what a clone's size is, and where ``git -C <location> log --all`` works.
        The name it lacks is shown beside it.
        """

        origin = self.source.normalized
        return MirrorDisplay(
            name=repository_name(origin),
            origin=display_origin(origin),
            location=display_directory(self._repository),
        )

    async def open_selection(
        self, *, ref: str | None, oid: str | None, keep_refs: tuple[str, ...] = ()
    ) -> GitRevisionSubject:
        default_ref = await asyncio.to_thread(self._default_ref) if ref == "HEAD" else None
        resolved = await resolve_pin(
            self._target(), ref=ref, oid=oid, default_ref=default_ref, keep_refs=keep_refs
        )
        return await open_revision(
            home=self.home,
            store_key=self.store_key,
            commit_oid=resolved.commit_oid,
            store_identity=self.store_id,
            ref=resolved.ref,
        )

    async def refresh(self) -> RefreshResult:
        update = await update_store(
            self.home, self.store_key, remote_url=acquire.remote_url_for(self.source)
        )
        return RefreshResult(outcome=update.outcome.value, at=update.at)

    def _default_ref(self) -> str | None:
        try:
            state = read_record(
                self.home,
                store_record(self.store_key, "state.yml"),
                REPOSITORY_STORE_STATE_CONTRACT_ID,
                shared="keep",
            )
        except (RecordError, PrivateStorageError, OSError):
            return None
        return state.default_remote_ref if isinstance(state, RepositoryStoreState) else None

    async def recorded_freshness(self) -> RecordedFreshness:
        return await asyncio.to_thread(self._read_state)

    def _read_state(self) -> RecordedFreshness:
        # Stamped before the read: a rewrite between the two only makes the stamp older
        # than the content, which a later comparison still sees as a change.
        relative = store_record(self.store_key, "state.yml")
        try:
            status = (self.home / relative).stat()
            stamp: tuple[int, int] | None = (status.st_ino, status.st_mtime_ns)
        except OSError:
            stamp = None
        # "keep": a served store may live in a home this process cannot repair, and a
        # status read must never change it.
        state = read_record(
            self.home,
            store_record(self.store_key, "state.yml"),
            REPOSITORY_STORE_STATE_CONTRACT_ID,
            shared="keep",
        )
        if not isinstance(state, RepositoryStoreState):
            return RecordedFreshness(None, None, None, None)
        operation = state.last_operation
        return RecordedFreshness(
            last_fetch_at=state.last_fetch_at,
            last_operation=operation.kind,
            last_outcome=operation.outcome,
            last_outcome_at=operation.at,
            record_stamp=stamp,
        )

    async def ref_tip(self, ref: str) -> str | None:
        return await ref_tip(self._target(), ref)

    async def list_refs(self, kind: RefKind) -> tuple[MirrorRef, ...]:
        default_ref = await asyncio.to_thread(self._default_ref) if kind == "branch" else None
        return await list_mirror_refs(self._target(), kind, default_ref=default_ref)

    def repository_context(self, *, revision: str, branch: str | None) -> RepositoryContext | None:
        return repository_context_for(self.source.normalized, revision=revision, branch=branch)

    async def refresh_running_elsewhere(self) -> bool:
        return await asyncio.to_thread(self._fetch_lock_busy)

    def _fetch_lock_busy(self) -> bool:
        # Taken and dropped at once: a refresh that starts in that instant elsewhere
        # reports this process as refreshing, which is harmless and rare.
        try:
            with store_fetch_lock(self.home, self.store_key):
                return False
        except LockBusyError:
            return True


__all__ = [
    "REPOSITORY_NAME_MAX_CHARS",
    "UNNAMED_REPOSITORY",
    "StoreMirror",
    "display_directory",
    "display_origin",
    "repository_name",
]
