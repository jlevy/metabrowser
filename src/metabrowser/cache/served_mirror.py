"""The published store a server serves, as the refresh jobs and the pin route use it.

:class:`StoreMirror` is the cache's side of :class:`metabrowser.mirror_refresh.ServedMirror`.
The CLI builds one from the source it acquired or reused and hands it to the server, so
the server reaches the store, its record, and its origin only through these methods and
never learns a cache path.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from pathlib import Path

from metabrowser.cache import acquire
from metabrowser.cache.acquire import PublishedSource
from metabrowser.cache.atomic import RecordError, read_record
from metabrowser.cache.locks import LockBusyError, store_fetch_lock
from metabrowser.cache.paths import store_directory, store_record
from metabrowser.cache.providers import repository_context_for
from metabrowser.cache.records import REPOSITORY_STORE_STATE_CONTRACT_ID, RepositoryStoreState
from metabrowser.cache.repository_store import open_revision
from metabrowser.cache.resolve import ref_tip, resolve_pin
from metabrowser.cache.update import update_store
from metabrowser.cache.urls import GitSource
from metabrowser.git.process import RepositoryStoreTarget, repository_store_target
from metabrowser.git.tree_source import GitRevisionSubject
from metabrowser.home import PrivateStorageError
from metabrowser.mirror_refresh import RecordedFreshness, RefreshResult
from metabrowser.repository_context import RepositoryContext


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

    def _target(self) -> RepositoryStoreTarget:
        return repository_store_target(
            git_dir=self.home / store_directory(self.store_key) / "repository.git"
        )

    async def open_selection(self, *, ref: str | None, oid: str | None) -> GitRevisionSubject:
        default_ref = await asyncio.to_thread(self._default_ref) if ref == "HEAD" else None
        resolved = await resolve_pin(self._target(), ref=ref, oid=oid, default_ref=default_ref)
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
        )

    async def ref_tip(self, ref: str) -> str | None:
        return await ref_tip(self._target(), ref)

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


__all__ = ["StoreMirror"]
