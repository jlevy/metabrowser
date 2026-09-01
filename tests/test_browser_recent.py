"""End-to-end coverage for the provider-backed Recent surface."""

from __future__ import annotations

import asyncio
import json
import os
import time
from pathlib import Path
from typing import Any, cast

from metabrowser import paths_safe
from metabrowser import server as proc_browser
from metabrowser.inventory_engine.contract import (
    CountKind,
    CountResult,
    ReadRequest,
    RecentProjection,
    RecentQuery,
)
from metabrowser.recent import DEFAULT_LIMIT, RecentResult, WindowKey, recent_result_from_projection
from metabrowser.settings import LIVE_FILE_WINDOW_S, RECENT_WINDOW_SECONDS
from tests.inventory_harness import inventory_harness


def _build_fixture(root: Path) -> None:
    (root / "runs" / "x").mkdir(parents=True)
    (root / "runs" / "x" / "a.jsonl").write_text('{"event":"a"}')
    (root / "runs" / "x" / "b.jsonl").write_text('{"event":"b"}')
    (root / "docs.md").write_text("docs")


def _recent(
    root: Path,
    *,
    window: WindowKey = "all",
    limit: int = 200,
    extensions: tuple[str, ...] = (),
    prefix: str = "",
    include_ignored: bool = True,
) -> RecentResult:
    async def run() -> RecentResult:
        async with inventory_harness(root) as harness:
            projection_read = await harness.runtime.coordinator.read(
                ReadRequest(
                    queries=(
                        RecentQuery(
                            query_id="recent",
                            max_rows=limit,
                            as_of_ns=time.time_ns(),
                            extensions=extensions,
                            prefix=prefix,
                            within_seconds=RECENT_WINDOW_SECONDS[window],
                            include_ignored=include_ignored,
                        ),
                    )
                )
            )
            projection = projection_read.result.projection("recent")
            assert isinstance(projection, RecentProjection)
            return recent_result_from_projection(projection, window=window, limit=limit)

    return asyncio.run(run())


def test_recent_projection_is_flat_complete_and_newest_first(tmp_path: Path) -> None:
    _build_fixture(tmp_path)
    result = _recent(tmp_path)
    assert result.total_matching == 3
    assert result.total_matching_exact
    assert not result.truncated
    assert {entry["path"] for entry in result.entries_flat} == {
        "docs.md",
        "runs/x/a.jsonl",
        "runs/x/b.jsonl",
    }
    mtimes = [entry["mtime"] for entry in result.entries_flat]
    assert mtimes == sorted(mtimes, reverse=True)
    assert all(entry["type"] == "file" for entry in result.entries_flat)


def test_recent_window_uses_mtime_for_every_file(tmp_path: Path) -> None:
    _build_fixture(tmp_path)
    assert LIVE_FILE_WINDOW_S == 90.0
    assert RECENT_WINDOW_SECONDS["live"] == LIVE_FILE_WINDOW_S
    now = time.time()
    os.utime(tmp_path / "docs.md", (now - 60, now - 60))
    os.utime(tmp_path / "runs" / "x" / "a.jsonl", (now - 120, now - 120))

    result = _recent(tmp_path, window="live")
    paths = {entry["path"] for entry in result.entries_flat}
    assert "docs.md" in paths
    assert "runs/x/a.jsonl" not in paths


def test_recent_limit_extension_and_prefix_filters(tmp_path: Path) -> None:
    _build_fixture(tmp_path)
    result = _recent(
        tmp_path,
        limit=1,
        extensions=(".jsonl",),
        prefix="runs/",
    )
    assert result.total_matching == 2
    assert result.truncated
    assert len(result.entries_flat) == 1
    assert result.entries_flat[0]["path"].endswith(".jsonl")


def test_recent_serializes_a_capped_count_without_claiming_exactness() -> None:
    projection = RecentProjection(
        query_id="recent",
        entries=(),
        total_matches=CountResult(CountKind.AT_LEAST, 10_000),
    )

    result = recent_result_from_projection(projection, window="all", limit=200)

    assert result.total_matching == 10_000
    assert not result.total_matching_exact
    assert result.truncated


def _gitignore_repo(root: Path, patterns: str) -> None:
    (root / ".git").mkdir()
    (root / ".gitignore").write_text(patterns)


def test_recent_carries_ignored_leaves_and_ancestor_directories(tmp_path: Path) -> None:
    _gitignore_repo(tmp_path, "__pycache__/\n")
    (tmp_path / "pkg" / "__pycache__").mkdir(parents=True)
    (tmp_path / "pkg" / "__pycache__" / "a.pyc").write_text("x")
    (tmp_path / "pkg" / "keep.py").write_text("x")

    result = _recent(tmp_path)
    by_path = {entry["path"]: entry for entry in result.entries_flat}
    assert by_path["pkg/__pycache__/a.pyc"]["gitignored"] is True
    assert "gitignored" not in by_path["pkg/keep.py"]
    assert result.gitignored_dirs == ["pkg/__pycache__"]


def _repo_with_ignored_bulk(root: Path, bulk: int) -> None:
    _gitignore_repo(root, "node_modules/\n")
    (root / "src").mkdir()
    for index in range(3):
        (root / "src" / f"mod{index}.py").write_text("x")
    vendor = root / "node_modules"
    vendor.mkdir()
    for index in range(bulk):
        (vendor / f"dep{index}.js").write_text("y")


def test_recent_cap_prioritizes_tracked_files_then_restores_mtime_order(
    tmp_path: Path,
) -> None:
    _repo_with_ignored_bulk(tmp_path, 40)
    result = _recent(tmp_path, limit=10)
    paths = [entry["path"] for entry in result.entries_flat]
    assert len(paths) == 10
    assert result.truncated
    assert sorted(path for path in paths if path.startswith("src/")) == [
        "src/mod0.py",
        "src/mod1.py",
        "src/mod2.py",
    ]
    mtimes = [entry["mtime"] for entry in result.entries_flat]
    assert mtimes == sorted(mtimes, reverse=True)


def test_recent_excluding_ignored_spends_no_rows_on_them(tmp_path: Path) -> None:
    _repo_with_ignored_bulk(tmp_path, 40)
    result = _recent(tmp_path, limit=10, include_ignored=False)
    assert sorted(entry["path"] for entry in result.entries_flat) == [
        "src/mod0.py",
        "src/mod1.py",
        "src/mod2.py",
    ]
    assert result.total_matching == 3
    assert not result.truncated


class _FakeQuery:
    def __init__(self, values: dict[str, str]) -> None:
        self._values = values

    def get(self, key: str, default: str = "") -> str:
        return self._values.get(key, default)

    def getlist(self, key: str) -> list[str]:
        value = self._values.get(key, "")
        return [item for item in value.split(",") if item]


class _FakeRequest:
    def __init__(self, app: object, query: dict[str, str] | None = None) -> None:
        self.app = app
        self.query_params = _FakeQuery(query or {})
        self.headers: dict[str, str] = {}


def test_api_recent_preserves_envelope_and_validation(tmp_path: Path) -> None:
    _build_fixture(tmp_path)

    async def run() -> tuple[dict[str, Any], int]:
        original_root = paths_safe.ROOT_DIR
        paths_safe._set_root_dir(tmp_path)
        try:
            async with inventory_harness(tmp_path) as harness:
                response = await proc_browser.api_recent(cast(Any, _FakeRequest(harness.app)))
                invalid = await proc_browser.api_recent(
                    cast(Any, _FakeRequest(harness.app, {"window": "garbage"}))
                )
        finally:
            paths_safe._set_root_dir(original_root)
        return json.loads(bytes(response.body)), invalid.status_code

    body, invalid_status = asyncio.run(run())
    assert invalid_status == 400
    assert body["window"] == "24h"
    assert body["limit"] == DEFAULT_LIMIT
    assert body["tally_cache_status"] == "done"
    assert "tree" not in body
    assert isinstance(body["entries_flat"], list)
    assert isinstance(body["gitignored_dirs"], list)
    assert [entry["mtime"] for entry in body["entries_flat"]] == sorted(
        (entry["mtime"] for entry in body["entries_flat"]),
        reverse=True,
    )
    assert all("mtime_ns" not in entry for entry in body["entries_flat"])
