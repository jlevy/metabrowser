"""The store half of a served mirror, alone (``StoreSession`` in ``mirror_refresh.py``).

A folder's server keeps a store of its checkout's origin while its working tree is
served, so the fetch, the turn, the page's ask, and the last outcome have to work with no
pin at all, and a session has to leave alone a served revision that is not its store's.
These run on a fake store, with no Git; ``tests/test_source_refresh.py`` holds the same
rules on a real mirror, and ``tests/test_checkout_store.py`` on a real checkout.
"""

from __future__ import annotations

import asyncio
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

import pytest

from metabrowser import mirror_refresh
from metabrowser.mirror_refresh import (
    MirrorDisplay,
    MirrorRef,
    MirrorSession,
    RecordedFreshness,
    RefKind,
    RefreshCoordinator,
    RefreshResult,
    StoreSession,
    StoreTurn,
)
from metabrowser.repository_context import RepositoryContext

_LONG_AGO = "2020-01-01T00:00:00Z"
_BRANCH = "refs/remotes/origin/trunk"


def _now() -> str:
    return datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


class _Store:
    """A store that counts what is asked of it and fetches in no time."""

    key = "store"

    def __init__(self, *, fetched_at: str = _LONG_AGO) -> None:
        self.fetched_at = fetched_at
        self.fetches = 0
        self.probes: list[str] = []
        self.tips: list[str] = []

    async def open_selection(
        self, *, ref: str | None, oid: str | None, keep_refs: tuple[str, ...] = ()
    ) -> Any:
        raise AssertionError("not reached")

    async def refresh(self) -> RefreshResult:
        self.fetches += 1
        self.fetched_at = _now()
        return RefreshResult("succeeded", self.fetched_at)

    async def origin_tip(self, ref: str) -> str | None:
        self.probes.append(ref)
        return "a" * 40

    async def recorded_freshness(self) -> RecordedFreshness:
        return RecordedFreshness(self.fetched_at, "refresh", "succeeded", self.fetched_at)

    async def ref_tip(self, ref: str) -> str | None:
        self.tips.append(ref)
        return "a" * 40

    async def ref_tips(self, refs: Sequence[str]) -> dict[str, str]:
        self.tips.extend(refs)
        return dict.fromkeys(refs, "a" * 40)

    async def default_ref(self) -> str | None:
        return None

    async def list_refs(self, kind: RefKind, *, default_ref: str | None) -> tuple[MirrorRef, ...]:
        return ()

    async def refresh_running_elsewhere(self) -> bool:
        return False

    def repository_context(self, *, revision: str, branch: str | None) -> RepositoryContext | None:
        return None

    @property
    def display(self) -> MirrorDisplay:
        return MirrorDisplay(name="store", origin="https://example.com/o/r", location="/store")


@dataclass(frozen=True)
class _Revision:
    """What a session reads of a served revision."""

    ref: str | None
    commit_oid: str


def test_a_store_is_fetched_and_reported_without_reading_what_is_served(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The store's half reads no served subject: a stale store is fetched on a page's
    ask, its fields say so, and nothing more is due inside the window."""

    def never() -> None:
        raise AssertionError("the store's half read the served subject")

    monkeypatch.setattr(mirror_refresh, "_served_revision", never)

    async def scenario() -> tuple[list[str], dict[str, Any], int]:
        store = _Store()
        coordinator = RefreshCoordinator()
        session = StoreSession(store, coordinator)
        await session.observe()
        assert session.is_stale() and not session.refreshing()
        answers = [await session.page_ask()]
        await coordinator.drain(timeout_s=30)
        answers.append(await session.page_ask())
        fields = dict(session.store_fields())
        await coordinator.aclose()
        return answers, fields, store.fetches

    answers, fields, fetches = asyncio.run(scenario())
    assert answers == ["started", "not_due"]
    assert fetches == 1
    assert fields["last_fetch_at"] != _LONG_AGO and fields["refreshing"] is False
    assert fields["last_outcome"] == {
        "operation": "refresh",
        "outcome": "succeeded",
        "at": fields["last_fetch_at"],
    }


@pytest.mark.parametrize("owned", [True, False])
def test_a_session_follows_and_probes_only_a_revision_read_from_its_own_store(
    owned: bool, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A folder's server also serves revisions of its checkout. The store's session
    observes and probes a served branch only when the revision is its store's."""

    served = _Revision(_BRANCH, "a" * 40)
    monkeypatch.setattr(mirror_refresh, "_served_revision", lambda: served)

    async def scenario() -> tuple[str, _Store, bool]:
        store = _Store(fetched_at=_now())
        coordinator = RefreshCoordinator()
        session = MirrorSession(store, coordinator, owns=lambda _subject: owned)
        await session.observe()
        answer = await session.page_ask()
        is_served = session.served() is not None
        await coordinator.aclose()
        return answer, store, is_served

    answer, store, is_served = asyncio.run(scenario())
    assert is_served is owned
    assert answer == ("probed" if owned else "not_due")
    assert store.tips == ([_BRANCH] if owned else [])
    assert store.probes == ([_BRANCH] if owned else [])
    assert store.fetches == 0


def test_a_sessions_fetch_waits_its_turn_at_a_store_turn_made_elsewhere() -> None:
    """Whatever else fetches into the store in one server shares its turn: while another
    job holds it, the session's fetch has not begun, and it runs once the turn passes."""

    async def scenario() -> tuple[int, int]:
        store = _Store()
        turn = StoreTurn()
        coordinator = RefreshCoordinator()
        session = StoreSession(store, coordinator, store_turn=turn)
        await session.observe()
        async with turn(lambda: False):
            assert await session.page_ask() == "started"
            for _ in range(20):
                await asyncio.sleep(0)
            waiting = store.fetches
        await coordinator.drain(timeout_s=30)
        await coordinator.aclose()
        return waiting, store.fetches

    assert asyncio.run(scenario()) == (0, 1)
