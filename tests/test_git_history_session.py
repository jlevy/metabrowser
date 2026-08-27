"""Bounded continuation sessions for deep Git history."""

from __future__ import annotations

import asyncio
import shutil
from pathlib import Path
from unittest import mock

import pytest

from devtools.git_history_benchmark import HistoryShape, build_history_corpus
from metabrowser.git.history import (
    ExpiredHistorySessionError,
    HistoryCursor,
    HistoryParserError,
    HistoryScope,
    HistorySession,
    HistorySessionRegistry,
    HistoryStorageError,
    InvalidHistoryCursorError,
    StaleHistorySessionError,
    decode_history_cursor,
    encode_history_cursor,
    resolve_history_scope,
)
from metabrowser.git.process import GitCommandError, run_git
from metabrowser.git.wire import validate_git_log_page

pytestmark = pytest.mark.skipif(
    shutil.which("git") is None,
    reason="git executable is required to build the fixture repositories",
)


def _history(root: Path, *, commits: int = 17) -> Path:
    build_history_corpus(root, shape="linear", commit_count=commits)
    return root


def test_history_cursor_round_trips_and_rejects_every_invalid_shape() -> None:
    cursor = HistoryCursor(
        session_id="abcdefghijklmnop",
        page=37,
        direction="previous",
        scope_fingerprint="a" * 64,
        page_size=250,
    )
    assert decode_history_cursor(encode_history_cursor(cursor)) == cursor

    for invalid in (
        "",
        "!!!",
        "Zm9v",
        encode_history_cursor(cursor) + "%",
        encode_history_cursor(cursor)[:-1],
    ):
        assert decode_history_cursor(invalid) is None


def test_one_walk_pages_are_contiguous_and_replayable(tmp_path: Path) -> None:
    root = _history(tmp_path / "history")

    async def scenario() -> None:
        registry = HistorySessionRegistry(idle_ttl_s=60)
        try:
            expected = (
                (await run_git(["rev-list", "--date-order", "--all"], cwd=root))
                .decode()
                .splitlines()
            )
            first = await registry.read_page(root, wants_all=True, limit=4, cursor=None)
            validate_git_log_page(dict(first))
            assert first.get("page") == 0
            assert first.get("previous_cursor") is None
            first_cursor = first["cursor"]
            first_page_cursor = first.get("page_cursor")
            assert first_cursor is not None
            assert first_page_cursor is not None

            decoded = decode_history_cursor(first_page_cursor)
            assert decoded is not None
            session = registry._sessions[decoded.session_id]
            assert "--skip" not in session.command_args
            assert session.command_args[-1] == "--stdin"
            assert not set(session.scope.arguments) & set(session.command_args)
            spool_path = session.spool_path
            assert spool_path is not None and spool_path.is_file()

            second = await registry.read_page(
                root,
                wants_all=True,
                limit=4,
                cursor=first_cursor,
            )
            third = await registry.read_page(
                root,
                wants_all=True,
                limit=4,
                cursor=second["cursor"],
            )
            replayed_first = await registry.read_page(
                root,
                wants_all=True,
                limit=4,
                cursor=first_page_cursor,
            )
            previous_cursor = third.get("previous_cursor")
            assert previous_cursor is not None
            replayed_second = await registry.read_page(
                root,
                wants_all=True,
                limit=4,
                cursor=previous_cursor,
            )

            combined = [
                commit["id"] for page in (first, second, third) for commit in page["commits"]
            ]
            assert combined == expected[:12]
            assert replayed_first["commits"] == first["commits"]
            assert replayed_second["commits"] == second["commits"]
        finally:
            await registry.close_all()

        assert not spool_path.exists()

    asyncio.run(scenario())


def test_ref_movement_expires_the_snapshot_instead_of_changing_order(tmp_path: Path) -> None:
    root = _history(tmp_path / "history", commits=8)

    async def scenario() -> None:
        registry = HistorySessionRegistry(idle_ttl_s=60)
        try:
            first = await registry.read_page(root, wants_all=True, limit=2, cursor=None)
            assert first["cursor"] is not None
            await run_git(["update-ref", "refs/heads/new-tip", "HEAD~3"], cwd=root)
            with pytest.raises(StaleHistorySessionError):
                await registry.read_page(
                    root,
                    wants_all=True,
                    limit=2,
                    cursor=first["cursor"],
                )
            assert registry.session_count == 0
        finally:
            await registry.close_all()

    asyncio.run(scenario())


def test_default_scope_expires_when_its_head_moves(tmp_path: Path) -> None:
    root = _history(tmp_path / "history", commits=8)

    async def scenario() -> None:
        registry = HistorySessionRegistry(idle_ttl_s=60)
        try:
            first = await registry.read_page(root, wants_all=False, limit=2, cursor=None)
            assert first["cursor"] is not None
            await run_git(["update-ref", "refs/heads/main", "HEAD~1"], cwd=root)
            with pytest.raises(StaleHistorySessionError):
                await registry.read_page(
                    root,
                    wants_all=None,
                    limit=2,
                    cursor=first["cursor"],
                )
            assert registry.session_count == 0
        finally:
            await registry.close_all()

    asyncio.run(scenario())


def test_registry_evicts_the_least_recent_session_at_its_entry_bound(tmp_path: Path) -> None:
    first_root = _history(tmp_path / "first", commits=8)
    second_root = _history(tmp_path / "second", commits=8)

    async def scenario() -> None:
        registry = HistorySessionRegistry(max_entries=1, max_walks=1, idle_ttl_s=60)
        try:
            first = await registry.read_page(first_root, wants_all=True, limit=2, cursor=None)
            assert first["cursor"] is not None
            await registry.read_page(second_root, wants_all=True, limit=2, cursor=None)
            assert registry.session_count == 1
            with pytest.raises(ExpiredHistorySessionError):
                await registry.read_page(
                    first_root,
                    wants_all=True,
                    limit=2,
                    cursor=first["cursor"],
                )
        finally:
            await registry.close_all()

    asyncio.run(scenario())


def test_parser_budget_expires_the_session(tmp_path: Path) -> None:
    root = _history(tmp_path / "history", commits=4)

    async def scenario() -> None:
        registry = HistorySessionRegistry(parser_max_bytes=64, idle_ttl_s=60)
        try:
            with pytest.raises(HistoryParserError, match="buffer budget"):
                await registry.read_page(root, wants_all=True, limit=2, cursor=None)
            assert registry.session_count == 0
        finally:
            await registry.close_all()

    asyncio.run(scenario())


def test_storage_exhaustion_deletes_the_private_spool(tmp_path: Path) -> None:
    root = _history(tmp_path / "history", commits=4)

    async def scenario() -> None:
        scope = await resolve_history_scope(root, wants_all=True)
        session = await HistorySession.start(
            root=root,
            scope=scope,
            page_size=2,
            parser_max_bytes=128 * 1024,
            storage_max_bytes=8,
            clock=lambda: 0.0,
        )
        spool_path = session.spool_path
        assert spool_path is not None
        cursor = HistoryCursor(
            session_id=session.id,
            page=0,
            direction="next",
            scope_fingerprint=scope.fingerprint,
            page_size=2,
        )
        with pytest.raises(HistoryStorageError):
            await session.page(cursor)
        assert session.closed is True
        assert not spool_path.exists()

    asyncio.run(scenario())


def test_idle_reaping_deletes_the_spool_and_expires_its_cursor(tmp_path: Path) -> None:
    root = _history(tmp_path / "history", commits=8)
    now = 10.0

    def clock() -> float:
        return now

    async def scenario() -> None:
        nonlocal now
        registry = HistorySessionRegistry(idle_ttl_s=5, clock=clock)
        try:
            first = await registry.read_page(root, wants_all=True, limit=2, cursor=None)
            assert first["cursor"] is not None
            decoded = decode_history_cursor(first["cursor"])
            assert decoded is not None
            spool_path = registry._sessions[decoded.session_id].spool_path
            assert spool_path is not None and spool_path.exists()

            now = 16.0
            await registry.reap_expired()
            assert registry.session_count == 0
            assert not spool_path.exists()
            with pytest.raises(ExpiredHistorySessionError):
                await registry.read_page(
                    root,
                    wants_all=True,
                    limit=2,
                    cursor=first["cursor"],
                )
        finally:
            await registry.close_all()

    asyncio.run(scenario())


def test_missing_replay_spool_expires_the_session(tmp_path: Path) -> None:
    root = _history(tmp_path / "history", commits=8)

    async def scenario() -> None:
        registry = HistorySessionRegistry(idle_ttl_s=60)
        try:
            first = await registry.read_page(root, wants_all=True, limit=2, cursor=None)
            page_cursor = first.get("page_cursor")
            assert page_cursor is not None
            decoded = decode_history_cursor(page_cursor)
            assert decoded is not None
            spool_path = registry._sessions[decoded.session_id].spool_path
            assert spool_path is not None
            spool_path.unlink()

            with pytest.raises(HistoryStorageError, match="spool read failed"):
                await registry.read_page(
                    root,
                    wants_all=True,
                    limit=2,
                    cursor=page_cursor,
                )
            assert registry.session_count == 0
        finally:
            await registry.close_all()

    asyncio.run(scenario())


def test_cursor_cannot_change_page_size_or_skip_unvisited_pages(tmp_path: Path) -> None:
    root = _history(tmp_path / "history", commits=8)

    async def scenario() -> None:
        registry = HistorySessionRegistry(idle_ttl_s=60)
        try:
            first = await registry.read_page(root, wants_all=True, limit=2, cursor=None)
            first_cursor = first["cursor"]
            assert first_cursor is not None
            with pytest.raises(InvalidHistoryCursorError):
                await registry.read_page(
                    root,
                    wants_all=True,
                    limit=3,
                    cursor=first_cursor,
                )

            decoded = decode_history_cursor(first_cursor)
            assert decoded is not None
            skipped = encode_history_cursor(
                HistoryCursor(
                    session_id=decoded.session_id,
                    page=decoded.page + 1,
                    direction="next",
                    scope_fingerprint=decoded.scope_fingerprint,
                    page_size=decoded.page_size,
                )
            )
            with pytest.raises(InvalidHistoryCursorError):
                await registry.read_page(
                    root,
                    wants_all=True,
                    limit=2,
                    cursor=skipped,
                )
        finally:
            await registry.close_all()

    asyncio.run(scenario())


@pytest.mark.parametrize("shape", ["linear", "branch-heavy", "merge-heavy"])
def test_every_measured_history_shape_matches_one_date_order_walk(
    tmp_path: Path,
    shape: HistoryShape,
) -> None:
    root = tmp_path / shape
    build_history_corpus(root, shape=shape, commit_count=73)

    async def scenario() -> None:
        registry = HistorySessionRegistry(idle_ttl_s=60)
        try:
            expected = (
                (await run_git(["rev-list", "--date-order", "--all"], cwd=root))
                .decode()
                .splitlines()
            )
            actual: list[str] = []
            cursor: str | None = None
            while True:
                page = await registry.read_page(
                    root,
                    wants_all=True,
                    limit=11,
                    cursor=cursor,
                )
                actual.extend(commit["id"] for commit in page["commits"])
                cursor = page["cursor"]
                if cursor is None:
                    break
            assert actual == expected
        finally:
            await registry.close_all()

    asyncio.run(scenario())


def test_deep_continuation_never_adds_skip_to_the_git_walk(tmp_path: Path) -> None:
    root = _history(tmp_path / "deep-history", commits=1_003)

    async def scenario() -> None:
        registry = HistorySessionRegistry(idle_ttl_s=60)
        try:
            cursor: str | None = None
            seen = 0
            session_id: str | None = None
            while True:
                page = await registry.read_page(
                    root,
                    wants_all=True if cursor is None else None,
                    limit=97,
                    cursor=cursor,
                )
                seen += len(page["commits"])
                page_cursor = page.get("page_cursor")
                assert page_cursor is not None
                decoded = decode_history_cursor(page_cursor)
                assert decoded is not None
                session_id = session_id or decoded.session_id
                assert decoded.session_id == session_id
                assert "--skip" not in registry._sessions[session_id].command_args
                cursor = page["cursor"]
                if cursor is None:
                    break
            assert seen == 1_003
        finally:
            await registry.close_all()

    asyncio.run(scenario())


def test_two_panels_hold_two_independent_sessions(tmp_path: Path) -> None:
    first_root = _history(tmp_path / "first", commits=101)
    second_root = _history(tmp_path / "second", commits=101)

    async def scenario() -> None:
        registry = HistorySessionRegistry(max_entries=2, max_walks=2, idle_ttl_s=60)
        try:
            first, second = await asyncio.gather(
                registry.read_page(first_root, wants_all=True, limit=2, cursor=None),
                registry.read_page(second_root, wants_all=True, limit=2, cursor=None),
            )
            assert first["cursor"] is not None
            assert second["cursor"] is not None
            assert registry.session_count == 2
            session_ids = {
                decoded.session_id
                for cursor in (first["cursor"], second["cursor"])
                if (decoded := decode_history_cursor(cursor)) is not None
            }
            assert len(session_ids) == 2
        finally:
            await registry.close_all()

    asyncio.run(scenario())


def test_subprocess_failure_discards_the_session(tmp_path: Path) -> None:
    root = _history(tmp_path / "history", commits=4)

    async def scenario() -> None:
        registry = HistorySessionRegistry(idle_ttl_s=60)
        invalid_scope = HistoryScope(
            name="default",
            arguments=("0" * 40,),
            display_refs=("HEAD",),
            fingerprint="f" * 64,
        )
        try:
            with (
                mock.patch(
                    "metabrowser.git.history.resolve_history_scope",
                    return_value=invalid_scope,
                ),
                pytest.raises(GitCommandError, match="git log"),
            ):
                await registry.read_page(root, wants_all=False, limit=2, cursor=None)
            assert registry.session_count == 0
        finally:
            await registry.close_all()

    asyncio.run(scenario())
