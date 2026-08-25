"""End-to-end tests for Python-inventory-backed API behavior.

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
from collections.abc import AsyncIterator
from pathlib import Path
from typing import Any, cast

from metabrowser import paths_safe
from metabrowser import server as proc_browser
from metabrowser.file_type_registry import load_file_type_registry
from metabrowser.inventory_engine.contract import (
    EntryPresence,
    EntryProjection,
    EntryQuery,
    InventoryEntry,
    ReadRequest,
)
from tests.inventory_harness import inventory_harness


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
        *,
        app: object | None = None,
    ) -> None:
        self.query_params = _FakeQuery(query or {})
        self.headers = _FakeHeaders(headers or {})
        self.app = app


# ── proc_browser.api_tree: route-level integration ────────────


def test_api_tree_uses_inventory_when_populated(tmp_path: Path) -> None:
    """When the inventory is populated, /api/tree's response carries the
    entries from the cache and the response envelope includes
    ``tally_cache_status``.

    The tallies are requested at ``depth=0``, which is the channel that is
    allowed to pay for them: they cost one visit per entry in the index and the
    rows do not, so a request carrying rows never waits for that pass. See
    explorations/performance-loop/experiments/exp-007.
    """

    _build_fixture(tmp_path)

    async def _run() -> dict[str, Any]:

        original_root = paths_safe.ROOT_DIR
        paths_safe._set_root_dir(tmp_path)
        try:
            async with inventory_harness(tmp_path) as harness:
                resp = await proc_browser.api_tree(cast(Any, _FakeRequest(app=harness.app)))
                tallies = await proc_browser.api_tree(
                    cast(
                        Any,
                        _FakeRequest({"depth": "0"}, app=harness.app),
                    )
                )
        finally:
            paths_safe._set_root_dir(original_root)
        rows = json.loads(bytes(resp.body))
        # Rows and tallies now come from different requests; merge them here so
        # the assertions below still read as one description of the surface.
        rows.update({k: v for k, v in json.loads(bytes(tallies.body)).items() if k != "tree"})
        return rows

    body = asyncio.run(_run())
    assert "tally_cache_status" in body
    assert body["tally_cache_status"] in ("idle", "scanning", "done", "truncated")
    assert "tree" in body
    assert [row[0] for row in body["type_presets"]] == [
        "code",
        "docs",
        "data",
        "archives",
        "media",
    ]
    assert body["file_type_registry"] == {
        "schema_version": 3,
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


def test_api_tree_tallies_share_one_provider_read(tmp_path: Path) -> None:
    _build_fixture(tmp_path)

    async def run() -> dict[str, Any]:
        original_root = paths_safe.ROOT_DIR
        paths_safe._set_root_dir(tmp_path)
        try:
            async with inventory_harness(tmp_path) as harness:
                response = await proc_browser.api_tree(
                    cast(Any, _FakeRequest({"depth": "0"}, app=harness.app))
                )
                return json.loads(bytes(response.body))
        finally:
            paths_safe._set_root_dir(original_root)

    body = asyncio.run(run())
    assert body["summary"]["files"] == 5
    assert body["tally_cache_status"] == "done"


def test_api_tree_uses_provider_presence_instead_of_parallel_filesystem_truth(
    tmp_path: Path,
) -> None:
    async def run() -> int:
        original_root = paths_safe.ROOT_DIR
        paths_safe._set_root_dir(tmp_path)
        try:
            async with inventory_harness(tmp_path) as harness:
                (tmp_path / "appeared-without-observation").mkdir()
                response = await proc_browser.api_tree(
                    cast(
                        Any,
                        _FakeRequest(
                            {"path": "appeared-without-observation", "depth": "1"},
                            app=harness.app,
                        ),
                    )
                )
                return response.status_code
        finally:
            paths_safe._set_root_dir(original_root)

    assert asyncio.run(run()) == 404


def test_api_tree_uses_pending_inventory_without_filesystem_fallback(
    tmp_path: Path,
    monkeypatch: Any,
) -> None:
    (tmp_path / "runs" / "local" / "known").mkdir(parents=True)
    blocker = asyncio.Event()

    async def partial_walk(
        *_args: object,
        **_kwargs: object,
    ) -> AsyncIterator[InventoryEntry]:
        yield InventoryEntry.for_observed_dir(path="", parent="", name=tmp_path.name)
        yield InventoryEntry.for_observed_dir(path="runs", parent="", name="runs")
        yield InventoryEntry.for_observed_dir(path="runs/local", parent="runs", name="local")
        yield InventoryEntry.for_observed_dir(
            path="runs/local/known", parent="runs/local", name="known"
        )
        await blocker.wait()

    monkeypatch.setattr(
        "metabrowser.inventory_engine.providers.python_inventory.walk_tree",
        partial_walk,
    )

    def fail_filesystem_walk(*_args: object, **_kwargs: object) -> list[dict[str, Any]]:
        raise AssertionError("api_tree must not use _dir_tree for pending inventory rows")

    monkeypatch.setattr(proc_browser, "_dir_tree", fail_filesystem_walk)

    async def run() -> dict[str, Any]:
        original_root = paths_safe.ROOT_DIR
        paths_safe._set_root_dir(tmp_path)
        try:
            async with inventory_harness(tmp_path, settle=False) as harness:
                while True:
                    read = await harness.runtime.coordinator.read(
                        ReadRequest(queries=(EntryQuery(query_id="parent", path="runs/local"),))
                    )
                    parent = read.result.projection("parent")
                    assert isinstance(parent, EntryProjection)
                    if parent.presence is EntryPresence.PRESENT:
                        break
                    await asyncio.sleep(0)
                response = await proc_browser.api_tree(
                    cast(
                        Any,
                        _FakeRequest(
                            {"path": "runs/local", "depth": "2"},
                            app=harness.app,
                        ),
                    )
                )
                return json.loads(bytes(response.body))
        finally:
            paths_safe._set_root_dir(original_root)

    body = asyncio.run(run())
    assert body["tally_cache_status"] == "scanning"
    assert [row["path"] for row in body["tree"]] == ["runs/local/known"]
    assert body["tree"][0]["total_files"] is None
    assert body["tree"][0]["total_size"] is None


def test_a_row_request_does_not_pay_for_the_tallies(tmp_path: Path) -> None:
    """The split H27 introduced, stated as a contract rather than a timing.

    Tallies cost one visit per entry in the index and rows do not. Sharing one
    response made a reader wait for the expensive half to see the cheap one --
    most of a second at 240,000 files, and worse, work that competes with the
    walker. A row request now carries tallies only if they happen to be
    memoized; ``depth=0`` is the channel that computes them.
    """

    _build_fixture(tmp_path)

    async def _run() -> tuple[dict[str, Any], dict[str, Any]]:
        original_root = paths_safe.ROOT_DIR
        paths_safe._set_root_dir(tmp_path)
        try:
            async with inventory_harness(tmp_path) as harness:
                rows = await proc_browser.api_tree(cast(Any, _FakeRequest(app=harness.app)))
                tallies = await proc_browser.api_tree(
                    cast(
                        Any,
                        _FakeRequest({"depth": "0"}, app=harness.app),
                    )
                )
        finally:
            paths_safe._set_root_dir(original_root)
        return json.loads(bytes(rows.body)), json.loads(bytes(tallies.body))

    rows, tallies = asyncio.run(_run())

    # The rows arrive either way, and so does the scan-state label the client
    # uses to decide whether to trust what it has.
    assert rows["tree"], "a row request must still carry rows"
    assert "tally_cache_status" in rows

    # And the tally channel answers with them.
    assert tallies["summary"] is not None
    assert tallies["type_presets"] is not None
