"""End-to-end tests for the Recent surface (server side).

The server is responsible for filtering, capping, and resolving
gitignore — clustering lives in the SPA (see
``test_browser_recent_ui.py`` for the JS-side rules). These
tests pin the server's wire contract: an unclustered newest-first
leaf list plus the set of gitignored ancestor directories.
"""

from __future__ import annotations

import asyncio
import json
from dataclasses import replace
from pathlib import Path
from typing import Any, cast

from metabrowser import paths_safe
from metabrowser import server as proc_browser
from metabrowser.inventory import get_instance, reset_instance_for_tests
from metabrowser.recent import (
    DEFAULT_LIMIT,
    RecentResult,
    collect_recent_entries,
)

# ── collect_recent_entries (integrated with InventoryIndex) ──


def _build_fixture(root: Path) -> None:
    (root / "runs").mkdir()
    (root / "runs" / "x").mkdir()
    (root / "runs" / "x" / "a.jsonl").write_text('{"event":"a"}')
    (root / "runs" / "x" / "b.jsonl").write_text('{"event":"b"}')
    (root / "docs.md").write_text("docs")


async def _drive_walker(root: Path) -> None:
    reset_instance_for_tests()
    inv = get_instance()
    inv.start(root)
    await inv.wait_until_done(timeout=5.0)


def test_collect_recent_entries_returns_recent_files(tmp_path: Path) -> None:
    _build_fixture(tmp_path)
    asyncio.run(_drive_walker(tmp_path))
    result = collect_recent_entries(root=tmp_path, window="all", limit=200)
    assert isinstance(result, RecentResult)
    assert result.total_matching == 3
    assert result.truncated is False
    assert len(result.entries_flat) == 3
    assert all(e["type"] == "file" for e in result.entries_flat)
    mtimes = [e["mtime"] for e in result.entries_flat]
    assert mtimes == sorted(mtimes, reverse=True)
    paths = {e["path"] for e in result.entries_flat}
    assert "runs/x/a.jsonl" in paths
    assert "runs/x/b.jsonl" in paths
    assert "docs.md" in paths


def test_collect_recent_entries_window_filters_by_mtime(tmp_path: Path) -> None:
    """Files older than the window are excluded. Backdate the
    inventory entries directly to simulate."""

    _build_fixture(tmp_path)
    asyncio.run(_drive_walker(tmp_path))
    inv = get_instance()

    old_ns = int((__import__("time").time() - 60 * 60 * 48) * 1_000_000_000)
    e = inv.get("docs.md")
    assert e is not None
    inv._entries["docs.md"] = replace(e, mtime_ns=old_ns)

    # 24h window excludes docs.md (now 48h old).
    result = collect_recent_entries(root=tmp_path, window="24h", limit=200)
    paths = [e["path"] for e in result.entries_flat]
    assert "docs.md" not in paths


def test_collect_recent_entries_limit_caps_results(tmp_path: Path) -> None:
    _build_fixture(tmp_path)
    asyncio.run(_drive_walker(tmp_path))
    result = collect_recent_entries(root=tmp_path, window="all", limit=2)
    assert result.total_matching == 3
    assert result.limit == 2
    assert result.truncated is True
    assert len(result.entries_flat) == 2


def test_collect_recent_entries_ext_filter(tmp_path: Path) -> None:
    _build_fixture(tmp_path)
    asyncio.run(_drive_walker(tmp_path))
    result = collect_recent_entries(root=tmp_path, window="all", limit=200, ext_filter=(".jsonl",))
    paths = [e["path"] for e in result.entries_flat]
    assert all(p.endswith(".jsonl") for p in paths)
    assert paths  # at least one survived


def test_collect_recent_entries_prefix_filter(tmp_path: Path) -> None:
    _build_fixture(tmp_path)
    asyncio.run(_drive_walker(tmp_path))
    result = collect_recent_entries(root=tmp_path, window="all", limit=200, prefix_filter="runs/")
    paths = [e["path"] for e in result.entries_flat]
    assert paths
    assert all(p.startswith("runs/") for p in paths)


def test_collect_recent_entries_invalid_window_raises(tmp_path: Path) -> None:
    invalid_window = cast(Any, "garbage")
    try:
        collect_recent_entries(root=tmp_path, window=invalid_window, limit=200)
    except ValueError:
        return
    raise AssertionError("expected ValueError for invalid window")


# ── Gitignore (backend-resolved) ──────────────────────────────


def _gitignore_repo(tmp_path: Path, patterns: str) -> Path:
    # build_gitignore_check walks up to find the enclosing .git dir
    # and rejects paths outside it; give the temp tree its own
    # marker so the checker scopes to tmp_path.
    (tmp_path / ".git").mkdir()
    (tmp_path / ".gitignore").write_text(patterns)
    return tmp_path


def test_gitignored_dirs_lists_ignored_ancestors(tmp_path: Path) -> None:
    # `__pycache__/.../*.pyc` leaves: their `__pycache__` ancestors
    # match gitignore and must appear in `gitignored_dirs`. The
    # parent (`pkg`) is tracked even though every recent leaf under
    # it is ignored — this is the bug the layering fixed.
    _gitignore_repo(tmp_path, "__pycache__/\n")
    (tmp_path / "pkg" / "__pycache__").mkdir(parents=True)
    (tmp_path / "pkg" / "__pycache__" / "a.pyc").write_text("x")
    (tmp_path / "pkg" / "sub" / "__pycache__").mkdir(parents=True)
    (tmp_path / "pkg" / "sub" / "__pycache__" / "b.pyc").write_text("x")

    asyncio.run(_drive_walker(tmp_path))
    result = collect_recent_entries(root=tmp_path, window="all", limit=200)

    assert "pkg/__pycache__" in result.gitignored_dirs
    assert "pkg/sub/__pycache__" in result.gitignored_dirs
    assert "pkg" not in result.gitignored_dirs
    assert "pkg/sub" not in result.gitignored_dirs


def test_gitignored_dirs_empty_when_nothing_matches(tmp_path: Path) -> None:
    _gitignore_repo(tmp_path, "__pycache__/\n")
    (tmp_path / "pkg").mkdir()
    (tmp_path / "pkg" / "a.py").write_text("x")

    asyncio.run(_drive_walker(tmp_path))
    result = collect_recent_entries(root=tmp_path, window="all", limit=200)

    assert result.gitignored_dirs == []


def test_gitignored_flag_set_on_leaves(tmp_path: Path) -> None:
    _gitignore_repo(tmp_path, "*.pyc\n")
    (tmp_path / "pkg").mkdir()
    (tmp_path / "pkg" / "keep.py").write_text("x")
    (tmp_path / "pkg" / "drop.pyc").write_text("x")

    asyncio.run(_drive_walker(tmp_path))
    result = collect_recent_entries(root=tmp_path, window="all", limit=200)

    by_path = {e["path"]: e for e in result.entries_flat}
    assert by_path["pkg/drop.pyc"].get("gitignored") is True
    assert "gitignored" not in by_path["pkg/keep.py"]


# ── /api/recent route ────────────────────────────────────────


class _FakeQuery:
    def __init__(self, data: dict[str, str]) -> None:
        self._data = data

    def get(self, key: str, default: str = "") -> str:
        return self._data.get(key, default)

    def getlist(self, key: str) -> list[str]:
        v = self._data.get(key, "")
        return [s for s in v.split(",") if s] if v else []


class _FakeRequest:
    def __init__(self, query: dict[str, str] | None = None) -> None:
        self.query_params = _FakeQuery(query or {})
        self.headers: dict[str, str] = {}


def test_api_recent_response_envelope_shape(tmp_path: Path) -> None:
    _build_fixture(tmp_path)

    async def _run() -> dict[str, Any]:

        original = paths_safe._resolved_root_dir
        paths_safe._resolved_root_dir = lambda: tmp_path  # type: ignore[assignment]
        try:
            await _drive_walker(tmp_path)
            resp = await proc_browser.api_recent(cast(Any, _FakeRequest()))
        finally:
            paths_safe._resolved_root_dir = original  # type: ignore[assignment]
        return json.loads(bytes(resp.body))

    body = asyncio.run(_run())
    for field in (
        "root",
        "entries_flat",
        "gitignored_dirs",
        "window",
        "limit",
        "total_matching",
        "truncated",
        "tally_cache_status",
    ):
        assert field in body, f"missing field {field!r}"
    # The clustered ``tree`` field is gone — clustering is a
    # rendering concern owned by the SPA.
    assert "tree" not in body
    assert body["window"] == "24h"
    assert body["limit"] == DEFAULT_LIMIT
    assert isinstance(body["entries_flat"], list)
    assert isinstance(body["gitignored_dirs"], list)
    for entry in body["entries_flat"]:
        assert entry["type"] == "file"
        assert isinstance(entry["mtime"], (int, float))
        assert "mtime_ns" not in entry  # client should never see ns here
    # Newest-first ordering invariant — the SPA cluster relies on it.
    mtimes = [e["mtime"] for e in body["entries_flat"]]
    assert mtimes == sorted(mtimes, reverse=True)


def test_api_recent_invalid_window_returns_400(tmp_path: Path) -> None:
    _build_fixture(tmp_path)

    async def _run() -> int:

        original = paths_safe._resolved_root_dir
        paths_safe._resolved_root_dir = lambda: tmp_path  # type: ignore[assignment]
        try:
            await _drive_walker(tmp_path)
            resp = await proc_browser.api_recent(cast(Any, _FakeRequest({"window": "garbage"})))
        finally:
            paths_safe._resolved_root_dir = original  # type: ignore[assignment]
        return resp.status_code

    assert asyncio.run(_run()) == 400


# ── Truncation priority ───────────────────────────────────────


def _repo_with_ignored_bulk(tmp_path: Path, bulk: int) -> None:
    """A handful of tracked files buried under a dependency install.

    The bulk is written *after* the tracked files, so a straight
    newest-first cap puts every ignored file ahead of every tracked
    one — the shape that made a day window on a real repository return
    2 000 ``node_modules`` entries and none of the user's own work.
    """

    _gitignore_repo(tmp_path, "node_modules/\n")
    (tmp_path / "src").mkdir()
    for i in range(3):
        (tmp_path / "src" / f"mod{i}.py").write_text("x")
    vendor = tmp_path / "node_modules"
    vendor.mkdir()
    for i in range(bulk):
        (vendor / f"dep{i}.js").write_text("y")


def test_truncation_drops_ignored_before_tracked(tmp_path: Path) -> None:
    _repo_with_ignored_bulk(tmp_path, bulk=40)
    asyncio.run(_drive_walker(tmp_path))

    result = collect_recent_entries(root=tmp_path, window="all", limit=10)

    paths = [e["path"] for e in result.entries_flat]
    tracked = [p for p in paths if p.startswith("src/")]
    assert len(paths) == 10
    assert result.truncated is True
    # Every tracked file survives the cap even though all 40 ignored
    # files are newer than all of them.
    assert sorted(tracked) == ["src/mod0.py", "src/mod1.py", "src/mod2.py"]
    # The rest of the cap still goes to ignored files, newest-first.
    assert len(paths) - len(tracked) == 7


def test_truncated_result_stays_newest_first(tmp_path: Path) -> None:
    """Prioritising tracked files must not leave the list out of order:
    the selection is re-sorted before it goes on the wire."""

    _repo_with_ignored_bulk(tmp_path, bulk=40)
    asyncio.run(_drive_walker(tmp_path))

    result = collect_recent_entries(root=tmp_path, window="all", limit=10)

    mtimes = [e["mtime"] for e in result.entries_flat]
    assert mtimes == sorted(mtimes, reverse=True)


def test_include_ignored_false_spends_the_cap_on_tracked_files(tmp_path: Path) -> None:
    """A caller that hides gitignored rows should not pay for them: the
    cap would otherwise be spent fetching rows dropped on arrival."""

    _repo_with_ignored_bulk(tmp_path, bulk=40)
    asyncio.run(_drive_walker(tmp_path))

    result = collect_recent_entries(root=tmp_path, window="all", limit=10, include_ignored=False)

    paths = [e["path"] for e in result.entries_flat]
    assert sorted(paths) == ["src/mod0.py", "src/mod1.py", "src/mod2.py"]
    # total_matching reports the filtered universe, so "3 of 3" rather
    # than a truncation the caller never hit.
    assert result.total_matching == 3
    assert result.truncated is False


def test_untruncated_results_are_unchanged_by_the_priority_rule(tmp_path: Path) -> None:
    _repo_with_ignored_bulk(tmp_path, bulk=4)
    asyncio.run(_drive_walker(tmp_path))

    result = collect_recent_entries(root=tmp_path, window="all", limit=200)

    assert result.truncated is False
    assert result.total_matching == 7
    mtimes = [e["mtime"] for e in result.entries_flat]
    assert mtimes == sorted(mtimes, reverse=True)
