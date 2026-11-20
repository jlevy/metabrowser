"""A revision's file times in the routes: Group by age, Modified within, Recent, and the file
envelope, with the answer present, still being read, partial, and unavailable.

``tests/test_cli_git_pin_golden.py`` pins one transcript of each route on a five-commit
origin. This module pins what a transcript cannot show by itself: the bands partition the
files at one instant, a shallow history's files with no time are in Undated and nowhere
else, a read still running leaves every file undated rather than guessing, and a Git below
the minimum keeps the typed refusal. Every test here runs the real ``git last-modified``
(``file_ages_git``) except the unavailable one, which runs on every Git.
"""

from __future__ import annotations

import asyncio
import subprocess
from pathlib import Path
from typing import Any

import pytest

from metabrowser.git import content_routes
from metabrowser.git.file_ages_service import file_ages_service
from metabrowser.git.tree_source import GitPath
from metabrowser.tree_groups import UNDATED_GROUP_ID, groups_for
from tests.file_ages_git import service_is_idle, settled
from tests.git_pin_harness import pinned_client
from tests.test_git_file_ages import DAY, EPOCH, History, build_branchy

AS_OF = EPOCH + 7 * DAY + 3 * 3600


def _wire(*names: bytes) -> str:
    return GitPath.from_segments(*names).to_wire()


@pytest.fixture
def now(monkeypatch: pytest.MonkeyPatch) -> float:
    """The instant every window and band of a request is cut at."""

    monkeypatch.setattr(content_routes, "_request_instant", lambda: float(AS_OF))
    return float(AS_OF)


async def _settled(client: Any, subject: Any) -> None:
    await client.get("/api/index/progress")
    await settled(file_ages_service(), subject.command_target, subject.commit_oid)


def test_bands_partition_the_files_at_one_instant(
    tmp_path: Path, file_ages_git: tuple[int, int, int], now: float
) -> None:
    history = History(tmp_path / "repo")
    tip = build_branchy(history)

    async def run() -> None:
        async with pinned_client(history.root / ".git", tip) as (client, subject):
            await _settled(client, subject)
            answer = (await client.get("/api/tree?group_by=age&depth=1")).json()
            files = 0
            for group in answer["groups"]:
                assert group["files"] == group["entries"]
                files += group["files"]
            assert files == len(history.names(tip))
            ids = [group["id"] for group in answer["groups"]]
            # `doc/older` is 3 hours old at this instant, `shared`, `doc/guide`, and `only_side`
            # between 1 and 4 days, and `root_only` a week and 3 hours, which is past the week.
            assert ids == ["24h", "7d", "30d"]
            counts = {group["id"]: group["files"] for group in answer["groups"]}
            assert counts == {"24h": 1, "7d": 3, "30d": 1}
            assert answer["ages"]["state"] == "ready"
            one = (await client.get("/api/tree?group=age:24h&depth=2")).json()
            assert one["filtered"]["files"] == 1
            assert [node["name"] for node in one["tree"]] == ["doc"]

    asyncio.run(run())


def test_modified_within_keeps_only_files_changed_inside_the_window(
    tmp_path: Path, file_ages_git: tuple[int, int, int], now: float
) -> None:
    history = History(tmp_path / "repo")
    tip = build_branchy(history)

    async def run() -> None:
        async with pinned_client(history.root / ".git", tip) as (client, subject):
            await _settled(client, subject)
            tree = (await client.get("/api/tree?recency=7d&depth=3")).json()
            assert tree["filtered"]["files"] == 4
            # `root_only` is past the week and its folder-less row is not listed.
            assert "root_only" not in [node["name"] for node in tree["tree"]]
            recent = (await client.get("/api/recent?window=7d")).json()
            assert recent["total_matching"] == 4
            assert [row["name"] for row in recent["entries_flat"]] == [
                "older",
                "shared",
                "guide",
                "only_side",
            ]
            assert recent["entries_flat"][0]["mtime"] == EPOCH + 7 * DAY
            assert recent["undated"] == 0
            # The menu's counts, one row per window.
            rows = {row[0]: row[1] for row in tree["recency_tallies"]}
            assert rows == {"live": 0, "1h": 0, "24h": 1, "7d": 4, "30d": 5}

    asyncio.run(run())


def test_a_read_still_running_leaves_every_file_undated(
    tmp_path: Path, file_ages_git: tuple[int, int, int], now: float, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Until the answer lands a window holds nothing and Group by age has one group, Undated:
    nothing is placed by a time the page does not have."""

    history = History(tmp_path / "repo")
    tip = build_branchy(history)

    async def run() -> None:
        async with pinned_client(history.root / ".git", tip) as (client, subject):
            service = file_ages_service()
            with monkeypatch.context() as patch:
                # A read that never starts: the state every page is in for the first moment.
                patch.setattr(service, "_start", lambda *_args, **_kwargs: None)
                grouped = (await client.get("/api/tree?group_by=age&depth=1")).json()
                assert grouped["ages"]["state"] == "dating"
                assert "recency_tallies" not in grouped
                assert [group["id"] for group in grouped["groups"]] == [UNDATED_GROUP_ID]
                assert grouped["groups"][0]["label"] == "Undated"
                assert grouped["groups"][0]["files"] == len(history.names(tip))
                windowed = (await client.get("/api/tree?recency=30d&depth=1")).json()
                assert windowed["filtered"]["files"] == 0
                recent = (await client.get("/api/recent?window=30d")).json()
                assert recent["entries_flat"] == [] and recent["ages"]["state"] == "dating"
            await _settled(client, subject)
            ready = (await client.get("/api/tree?group_by=age&depth=1")).json()
            assert ready["ages"]["state"] == "ready"
            assert UNDATED_GROUP_ID not in [group["id"] for group in ready["groups"]]
            # The counts the Modified within menu shows come with the groups, as with the rows.
            plain = (await client.get("/api/tree?depth=0")).json()
            assert ready["recency_tallies"] == plain["recency_tallies"]

    asyncio.run(run())


def test_a_shallow_history_puts_the_files_it_cannot_date_in_undated(
    tmp_path: Path, file_ages_git: tuple[int, int, int], now: float
) -> None:
    history = History(tmp_path / "repo")
    tip = build_branchy(history)
    shallow = tmp_path / "shallow"
    subprocess.run(
        ["git", "clone", "-q", "--depth", "2", f"file://{history.root}", str(shallow)],
        check=True,
        capture_output=True,
        env=history.env,
    )

    async def run() -> None:
        async with pinned_client(shallow / ".git", tip) as (client, subject):
            await _settled(client, subject)
            answer = (await client.get("/api/tree?group_by=age&depth=1")).json()
            by_id = {group["id"]: group for group in answer["groups"]}
            assert UNDATED_GROUP_ID in by_id
            undated = by_id[UNDATED_GROUP_ID]
            # Older than the boundary commit, which is the oldest the clone holds: a day.
            assert undated["label"].startswith("Undated, older than 20")
            assert answer["ages"]["state"] == "partial"
            assert answer["ages"]["stop"] == "boundary"
            total = sum(group["files"] for group in answer["groups"])
            assert total == len(history.names(tip))
            # A window never holds a file with no time, and says how many it could not place,
            # whatever the window: they are older than the boundary and may be inside it.
            recent = (await client.get("/api/recent?window=all")).json()
            assert recent["undated"] == undated["files"]
            assert recent["total_matching"] + recent["undated"] == total
            for window in ("30d", "7d", "24h"):
                inside = (await client.get(f"/api/recent?window={window}")).json()
                assert inside["undated"] == undated["files"], window
                assert inside["total_matching"] <= recent["total_matching"], window
            # Only the files that pass the other filters are counted: the clone has no .md file
            # without a time, and the size floor is applied before a file is counted.
            typed = (await client.get("/api/recent?window=7d&types=.zzz")).json()
            assert (typed["total_matching"], typed["undated"]) == (0, 0)
            floored = (await client.get("/api/recent?window=7d&min_size=1000")).json()
            assert (floored["total_matching"], floored["undated"]) == (0, 0)
            file = (await client.get(f"/api/file?path={_wire(b'root_only')}")).json()
            assert "mtime" not in file

    asyncio.run(run())


def test_the_file_envelope_carries_the_time_of_its_last_commit(
    tmp_path: Path, file_ages_git: tuple[int, int, int]
) -> None:
    history = History(tmp_path / "repo")
    tip = build_branchy(history)

    async def run() -> None:
        async with pinned_client(history.root / ".git", tip) as (client, subject):
            # Nothing has asked for the times yet, and a file read starts no read of them.
            before = (await client.get(f"/api/file?path={_wire(b'shared')}")).json()
            assert "mtime" not in before
            assert service_is_idle(file_ages_service())
            await _settled(client, subject)
            shared = (await client.get(f"/api/file?path={_wire(b'shared')}")).json()
            assert shared["mtime"] == EPOCH + 6 * DAY
            folder = (await client.get(f"/api/file?path={_wire(b'doc')}")).json()
            assert folder["mtime"] == EPOCH + 7 * DAY

    asyncio.run(run())


def test_a_git_without_file_ages_keeps_the_typed_refusal(
    tmp_path: Path,
) -> None:
    """On the pretend Git 2.50.1 every test starts on, a revision has no recency."""

    history = History(tmp_path / "repo")
    tip = build_branchy(history)

    async def run() -> None:
        async with pinned_client(history.root / ".git", tip) as (client, subject):
            assert subject.capabilities.recency is False
            for route in (
                "/api/tree?group_by=age&depth=1",
                "/api/tree?recency=24h&depth=1",
                "/api/recent?window=24h",
            ):
                refused = await client.get(route)
                assert refused.status_code == 409, route
                assert refused.json()["capability"] == "recency"

    asyncio.run(run())


def test_the_undated_group_is_only_a_revisions() -> None:
    assert [group.id for group in groups_for("age")][-1] == "older"
    assert [group.id for group in groups_for("age", undated=True)][-1] == UNDATED_GROUP_ID


def test_a_grouped_answer_asks_for_the_state_of_the_ages_once(
    tmp_path: Path, file_ages_git: tuple[int, int, int], now: float, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Every group of one answer is cut from one state, so a read that lands between two
    groups cannot give an answer whose groups partition different things."""

    history = History(tmp_path / "repo")
    tip = build_branchy(history)
    asked: list[str] = []
    real = content_routes._git_ages_status  # pyright: ignore[reportPrivateUsage]

    async def counted(subject: Any) -> Any:
        asked.append(subject.commit_oid)
        return await real(subject)

    monkeypatch.setattr(content_routes, "_git_ages_status", counted)

    async def run() -> None:
        async with pinned_client(history.root / ".git", tip) as (client, subject):
            await _settled(client, subject)
            asked.clear()
            answer = (await client.get("/api/tree?group_by=age&depth=1")).json()
            assert len(answer["groups"]) == 3
            assert len(asked) == 1
            asked.clear()
            (await client.get("/api/tree?group_by=type&depth=1")).json()
            assert len(asked) == 1

    asyncio.run(run())


def test_a_folder_row_in_a_group_is_dated_by_the_files_that_put_it_there(
    tmp_path: Path, file_ages_git: tuple[int, int, int], now: float
) -> None:
    """`doc` holds `older` (3 hours old) and `guide` (2 days and 3 hours): in Past day it is
    3 hours old, in Past week 2 days, and unfiltered it is as old as its newest file."""

    history = History(tmp_path / "repo")
    tip = build_branchy(history)

    async def run() -> None:
        async with pinned_client(history.root / ".git", tip) as (client, subject):
            await _settled(client, subject)
            plain = (await client.get("/api/tree?depth=1")).json()
            assert _node(plain["tree"], "doc")["mtime"] == EPOCH + 7 * DAY
            grouped = (await client.get("/api/tree?group_by=age&depth=1")).json()
            seen = {
                group["id"]: _node(group["tree"], "doc")
                for group in grouped["groups"]
                if "doc" in [node["name"] for node in group["tree"]]
            }
            assert sorted(seen) == ["24h", "7d"]
            assert seen["24h"]["mtime"] == EPOCH + 7 * DAY
            assert seen["7d"]["mtime"] == EPOCH + 5 * DAY
            windowed = (await client.get("/api/tree?recency=7d&depth=1")).json()
            assert _node(windowed["tree"], "doc")["mtime"] == EPOCH + 7 * DAY
            # Nothing kept under a folder leaves it with no time rather than the whole
            # folder's: this is the Undated group of a revision that has one.
            only_old = (await client.get("/api/tree?group=age:30d&depth=1")).json()
            assert "doc" not in [node["name"] for node in only_old["tree"]]

    asyncio.run(run())


def _node(nodes: list[dict[str, Any]], name: str) -> dict[str, Any]:
    return next(node for node in nodes if node["name"] == name)


def test_recent_lists_the_newest_files_first_and_counts_the_rest(
    tmp_path: Path, file_ages_git: tuple[int, int, int], now: float
) -> None:
    history = History(tmp_path / "repo")
    tip = build_branchy(history)

    async def run() -> None:
        async with pinned_client(history.root / ".git", tip) as (client, subject):
            await _settled(client, subject)
            everything = (await client.get("/api/recent?window=all&limit=500")).json()
            names = [row["name"] for row in everything["entries_flat"]]
            stamps = [row["mtime"] for row in everything["entries_flat"]]
            assert stamps == sorted(stamps, reverse=True)
            assert len(names) == everything["total_matching"] == len(history.names(tip))
            top = (await client.get("/api/recent?window=all&limit=2")).json()
            assert [row["path"] for row in top["entries_flat"]] == [
                row["path"] for row in everything["entries_flat"][:2]
            ]
            assert top["truncated"] is True
            assert top["total_matching"] == everything["total_matching"]
            under = (await client.get(f"/api/recent?window=all&prefix={_wire(b'doc')}")).json()
            assert sorted(row["name"] for row in under["entries_flat"]) == ["guide", "older"]

    asyncio.run(run())


def test_a_command_waits_for_the_ages_only_where_it_prints_them() -> None:
    from metabrowser.cli.api_cli import _waits_for_ages  # pyright: ignore[reportPrivateUsage]

    for route in ("/api/tree?depth=1", "/api/recent?window=24h", "/api/index/progress"):
        assert _waits_for_ages(route), route
    # A file's envelope starts no read, so a command that prints its time asks for the wait.
    assert _waits_for_ages("/api/file?path=a&ages=1")
    for route in ("/api/file?path=a", "/api/file?path=a&ages=0", "/api/rollup", "/api/catalog"):
        assert not _waits_for_ages(route), route
