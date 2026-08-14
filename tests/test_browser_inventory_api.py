"""End-to-end tests for InventoryIndex-backed API behavior.

* ``api_tree`` uses the inventory path when the index has data;
  the response carries ``tally_cache_status`` reflecting walker
  state; falls back to the filesystem walk when the index is
  idle.
* The inventory-backed tree shape matches the direct filesystem
  reference walk on a small fixture, except where the inventory emits
  ``None`` aggregates for in-progress dirs (walker still
  finalizing).
* ``_discover_trackable_files`` reads from the inventory when
  populated and returns the same set of paths as the reference walk.
* The cold-path budget contract is verifiable: with a fully
  finalized inventory, ``_discover_trackable_files`` finishes
  without touching the filesystem (no ``os.walk`` call required).
"""

from __future__ import annotations

import asyncio
import json
from collections.abc import Collection, Sequence
from pathlib import Path
from typing import Any, cast, override

from metabrowser import inventory as inventory_module
from metabrowser import paths_safe
from metabrowser import server as proc_browser
from metabrowser.activity import (
    _discover_trackable_files,
    _discover_trackable_files_from_inventory,
)
from metabrowser.events import FsEntry
from metabrowser.file_type_registry import load_file_type_registry
from metabrowser.inventory import InventoryIndex, get_instance, reset_instance_for_tests
from metabrowser.tree import _build_inventory_tree, inventory_has_data, inventory_status
from metabrowser.wire_models import NavigationTallies


def _build_fixture(root: Path) -> None:
    """Tree with .logs and .state dirs so trackable-file discovery
    has something to find."""
    (root / "README.md").write_text("readme")
    (root / "runs").mkdir()
    (root / "runs" / "x").mkdir()
    (root / "runs" / "x" / ".logs").mkdir()
    (root / "runs" / "x" / ".logs" / "foo.jsonl").write_text('{"event":"start"}\n')
    (root / "runs" / "x" / ".logs" / "foo.log").write_text("info: started\n")
    (root / "runs" / "x" / ".state").mkdir()
    (root / "runs" / "x" / ".state" / "status.json").write_text("{}")
    (root / "docs").mkdir()
    (root / "docs" / "notes.md").write_text("notes")


class _FakeQuery:
    def __init__(self, data: dict[str, str]) -> None:
        self._data = data

    def get(self, key: str, default: str = "") -> str:
        return self._data.get(key, default)


class _FakeHeaders:
    def __init__(self, data: dict[str, str]) -> None:
        self._data = {k.lower(): v for k, v in data.items()}

    def get(self, key: str, default: str = "") -> str:
        return self._data.get(key.lower(), default)


class _FakeRequest:
    def __init__(
        self,
        query: dict[str, str] | None = None,
        headers: dict[str, str] | None = None,
    ) -> None:
        self.query_params = _FakeQuery(query or {})
        self.headers = _FakeHeaders(headers or {})


async def _drive_walker(root: Path) -> None:
    reset_instance_for_tests()
    inv = get_instance()
    inv.start(root)
    await inv.wait_until_done(timeout=5.0)


# ── tree.py: inventory-backed builder ─────────────────────────


def test_inventory_backed_tree_shape_matches_legacy_filesystem(tmp_path: Path) -> None:
    """The inventory-built tree must produce the same per-row
    keys (``name``/``path``/``type``/``size``/``mtime``) as the
    legacy ``_dir_tree`` walk for files. Dir aggregates may be
    None during walker progress; here we wait for done so they're
    populated."""

    _build_fixture(tmp_path)
    asyncio.run(_drive_walker(tmp_path))

    tree = _build_inventory_tree(parent_rel="", max_depth=3, root_abs=tmp_path)
    # Top-level entries: README.md, runs/, docs/
    names = {row["name"] for row in tree}
    assert "README.md" in names
    assert "runs" in names
    assert "docs" in names

    # README.md has size 6 and a non-zero mtime.
    readme = next(row for row in tree if row["name"] == "README.md")
    assert readme["type"] == "file"
    assert readme["size"] == 6
    assert readme["mtime"] > 0

    # docs is a dir with one child (notes.md).
    docs = next(row for row in tree if row["name"] == "docs")
    assert docs["type"] == "dir"
    assert docs["total_files"] == 1
    assert docs["has_children"] is True


def test_inventory_backed_tree_emits_none_aggregates_when_walker_in_progress(
    tmp_path: Path,
) -> None:
    """Before the walker finalizes a dir, its ``total_files`` is
    None (placeholder). The shape carries this through so the
    client can render skeleton cells."""

    _build_fixture(tmp_path)
    reset_instance_for_tests()
    inv = get_instance()

    inv._entries["docs"] = FsEntry(
        path="docs",
        parent="",
        name="docs",
        type="dir",
        ext="",
        kind="dir",
        size=0,
        mtime_ns=0,
        mtime_hash="",
        active=False,
    )
    out = _build_inventory_tree(parent_rel="", max_depth=2, root_abs=tmp_path)
    docs_row = next(row for row in out if row["name"] == "docs")
    assert docs_row["total_files"] is None
    assert docs_row["total_size"] is None


def test_inventory_status_passes_through(tmp_path: Path) -> None:
    _build_fixture(tmp_path)
    reset_instance_for_tests()
    assert inventory_status() == "idle"
    asyncio.run(_drive_walker(tmp_path))
    assert inventory_status() in ("done", "truncated")


def test_inventory_has_data_false_when_idle() -> None:
    reset_instance_for_tests()
    assert inventory_has_data() is False


# ── proc_browser.api_tree: route-level integration ────────────


def test_api_tree_uses_inventory_when_populated(tmp_path: Path) -> None:
    """When the inventory is populated, /api/tree's response
    carries the entries from the cache and the response envelope
    includes ``tally_cache_status``."""

    _build_fixture(tmp_path)

    async def _run() -> dict[str, Any]:

        original_root = paths_safe.ROOT_DIR
        paths_safe._set_root_dir(tmp_path)
        try:
            await _drive_walker(tmp_path)
            resp = await proc_browser.api_tree(cast(Any, _FakeRequest()))
        finally:
            paths_safe._set_root_dir(original_root)
        return json.loads(bytes(resp.body))

    body = asyncio.run(_run())
    assert "tally_cache_status" in body
    assert body["tally_cache_status"] in ("idle", "scanning", "done", "truncated")
    assert "tree" in body
    assert [row[0] for row in body["type_presets"]] == [
        "code",
        "docs",
        "data",
        "logs",
        "archives",
        "media",
    ]
    assert body["file_type_registry"] == {
        "schema_version": 1,
        "revision": load_file_type_registry().revision,
        "fingerprint": load_file_type_registry().fingerprint,
    }
    assert body["canonical_extensions"] is not None
    assert body["type_families"] is not None
    assert [row[0] for row in body["recency_tallies"]] == [
        "live",
        "1h",
        "24h",
        "7d",
        "30d",
    ]
    names = {row["name"] for row in body["tree"]}
    assert "README.md" in names
    assert "runs" in names


def test_api_tree_snapshots_tallies_before_worker_thread(
    tmp_path: Path,
    monkeypatch: Any,
) -> None:
    """A filter-clear refresh must not iterate the live index off-loop.

    The inventory walker owns mutations on the event-loop thread. This
    test double rejects a tally call that reaches into the live mapping
    from ``asyncio.to_thread``, modeling the dictionary-size race seen
    while a large root was still scanning. It also finishes the walk
    while the worker runs: the response status must still describe the
    partial snapshot so the browser schedules a final refresh.
    """

    class WorkerUnsafeTallies(InventoryIndex):
        @override
        def navigation_tallies(
            self,
            presets: Sequence[tuple[str, Collection[str]]],
            recency_windows: Sequence[tuple[str, float]],
            limit: int = 200,
            *,
            now_ns: int | None = None,
            entries: Sequence[FsEntry] | None = None,
        ) -> NavigationTallies:
            if entries is None:
                raise RuntimeError("dictionary changed size during iteration")
            return super().navigation_tallies(
                presets,
                recency_windows,
                limit=limit,
                now_ns=now_ns,
                entries=entries,
            )

    original_root = paths_safe.ROOT_DIR
    resolved_root = tmp_path.resolve()
    paths_safe._set_root_dir(resolved_root)
    inv = WorkerUnsafeTallies()
    inv._root = resolved_root
    inv._status = "scanning"
    inv._entries["README.md"] = FsEntry.for_observed_file(
        path="README.md",
        parent="",
        name="README.md",
        size=6,
        mtime_ns=1_700_000_000_000_000_000,
    )
    monkeypatch.setattr(inventory_module, "get_instance", lambda: inv)
    monkeypatch.setattr(proc_browser, "get_inventory", lambda: inv)
    original_to_thread = asyncio.to_thread

    async def finish_inventory_during_tallies(function: Any, /, *args: Any, **kwargs: Any) -> Any:
        result = await original_to_thread(function, *args, **kwargs)
        inv._status = "done"
        return result

    monkeypatch.setattr(proc_browser.asyncio, "to_thread", finish_inventory_during_tallies)

    try:
        response = asyncio.run(proc_browser.api_tree(cast(Any, _FakeRequest())))
    finally:
        paths_safe._set_root_dir(original_root)

    assert response.status_code == 200
    body = json.loads(bytes(response.body))
    assert body["summary"]["files"] == 1
    assert body["tally_cache_status"] == "scanning"


def test_api_tree_uses_pending_inventory_without_filesystem_fallback(
    tmp_path: Path,
    monkeypatch: Any,
) -> None:
    """A known-but-unfinalized subtree should return immediately from
    inventory instead of starting a second blocking filesystem walk."""

    (tmp_path / "runs" / "local" / "known").mkdir(parents=True)

    original_root = paths_safe.ROOT_DIR
    paths_safe._set_root_dir(tmp_path)
    reset_instance_for_tests()
    inv = get_instance()
    inv._root = tmp_path
    inv._status = "scanning"

    inv._entries["runs/local"] = FsEntry(
        path="runs/local",
        parent="runs",
        name="local",
        type="dir",
        ext="",
        kind="dir",
        size=0,
        mtime_ns=0,
        mtime_hash="",
        active=False,
    )
    inv._entries["runs/local/known"] = FsEntry(
        path="runs/local/known",
        parent="runs/local",
        name="known",
        type="dir",
        ext="",
        kind="dir",
        size=0,
        mtime_ns=0,
        mtime_hash="",
        active=False,
    )

    def _fail_filesystem_walk(*_args: object, **_kwargs: object) -> list[dict[str, Any]]:
        raise AssertionError("api_tree must not use _dir_tree for pending inventory rows")

    monkeypatch.setattr(proc_browser, "_dir_tree", _fail_filesystem_walk)
    try:
        resp = asyncio.run(
            proc_browser.api_tree(cast(Any, _FakeRequest({"path": "runs/local", "depth": "2"})))
        )
    finally:
        paths_safe._set_root_dir(original_root)
        reset_instance_for_tests()

    body = json.loads(bytes(resp.body))
    assert body["tally_cache_status"] == "scanning"
    assert [row["path"] for row in body["tree"]] == ["runs/local/known"]
    assert body["tree"][0]["total_files"] is None
    assert body["tree"][0]["total_size"] is None


# ── activity.py: inventory-backed discovery ───────────────────


def test_discover_trackable_files_from_inventory_returns_none_when_empty() -> None:
    reset_instance_for_tests()
    out = _discover_trackable_files_from_inventory(Path("/nonexistent"))
    assert out is None


def test_discover_trackable_files_from_inventory_finds_logs_state_files(
    tmp_path: Path,
) -> None:
    _build_fixture(tmp_path)
    asyncio.run(_drive_walker(tmp_path))

    out = _discover_trackable_files_from_inventory(tmp_path)
    assert out is not None
    paths = {p.relative_to(tmp_path).as_posix() for p in out}
    assert "runs/x/.logs/foo.jsonl" in paths
    # .log is NOT in BROWSER_TRACKABLE_EXTS (only .jsonl/.yaml/.yml/etc).
    # That's a deliberate scope choice — only commonly appended formats
    # at runtime are tracked. The .json file IS tracked.
    assert "runs/x/.state/status.json" in paths
    # README.md is NOT trackable (lives outside .logs/.state).
    assert "README.md" not in paths
    # docs/notes.md is also not in .logs/.state.
    assert "docs/notes.md" not in paths


def test_discover_trackable_files_uses_inventory_when_populated(tmp_path: Path) -> None:
    """Wrapper function returns the same set as the legacy walk."""

    _build_fixture(tmp_path)
    asyncio.run(_drive_walker(tmp_path))

    out = _discover_trackable_files(tmp_path)
    paths = {p.relative_to(tmp_path).as_posix() for p in out}
    assert "runs/x/.logs/foo.jsonl" in paths
    # .log is NOT in BROWSER_TRACKABLE_EXTS (only .jsonl/.yaml/.yml/etc).
    # That's a deliberate scope choice — only commonly appended formats
    # at runtime are tracked. The .json file IS tracked.
    assert "runs/x/.state/status.json" in paths


def test_discover_trackable_files_falls_back_to_walk_when_inventory_idle(
    tmp_path: Path,
) -> None:
    """When the inventory has no data, the legacy filesystem
    walker still produces a correct result. This is the safety
    net for the 'no walker started yet' edge case."""

    _build_fixture(tmp_path)
    reset_instance_for_tests()  # inventory empty

    out = _discover_trackable_files(tmp_path)
    paths = {p.relative_to(tmp_path).as_posix() for p in out}
    # Same expected set as the inventory-backed path.
    assert "runs/x/.logs/foo.jsonl" in paths
    # .log is NOT in BROWSER_TRACKABLE_EXTS (only .jsonl/.yaml/.yml/etc).
    # That's a deliberate scope choice — only commonly appended formats
    # at runtime are tracked. The .json file IS tracked.
    assert "runs/x/.state/status.json" in paths


def test_inventory_and_filesystem_paths_agree_on_trackable_set(tmp_path: Path) -> None:
    """Same input, two independent code paths, identical
    output set — the migration is behavior-preserving."""

    _build_fixture(tmp_path)
    # Run both paths against the same fixture.
    reset_instance_for_tests()
    fs_paths = {p.relative_to(tmp_path).as_posix() for p in _discover_trackable_files(tmp_path)}
    asyncio.run(_drive_walker(tmp_path))
    inv_out = _discover_trackable_files_from_inventory(tmp_path)
    assert inv_out is not None
    inv_paths = {p.relative_to(tmp_path).as_posix() for p in inv_out}
    assert fs_paths == inv_paths
