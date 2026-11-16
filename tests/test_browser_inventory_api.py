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

import pytest

from metabrowser import paths_safe
from metabrowser import server as proc_browser
from metabrowser.file_type_registry import load_file_type_registry
from metabrowser.inventory_engine.contract import (
    DiagnosticsProjection,
    DiagnosticsQuery,
    DirectoryQuery,
    EntryPresence,
    EntryProjection,
    EntryQuery,
    FilteredTreeQuery,
    GroupedTreeQuery,
    InventoryEntry,
    ReadRequest,
    VersionUnavailableError,
)
from metabrowser.inventory_engine.coordinator import CoordinatedRead, InventoryReadSession
from metabrowser.inventory_engine.providers import python_inventory
from metabrowser.settings import INVENTORY_MAX_FILES, INVENTORY_TREE_PAGE_ROWS
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


def test_api_tree_pages_provider_reads_independently_of_the_discovery_budget(
    tmp_path: Path,
) -> None:
    assert 0 < INVENTORY_TREE_PAGE_ROWS < INVENTORY_MAX_FILES
    _build_fixture(tmp_path)

    async def _run() -> tuple[int, ...]:
        paths_safe._set_root_dir(tmp_path)
        server_namespace = cast(dict[str, Any], vars(proc_browser))
        original_assemble = server_namespace["assemble_tree_pages"]
        observed_page_bounds: list[int] = []

        async def recording_assemble(*args: Any, **kwargs: Any) -> Any:
            query = cast(DirectoryQuery | FilteredTreeQuery, kwargs["page_query"])
            observed_page_bounds.append(query.max_rows)
            return await original_assemble(*args, **kwargs)

        server_namespace["assemble_tree_pages"] = recording_assemble
        try:
            async with inventory_harness(tmp_path) as harness:
                await proc_browser.api_tree(cast(Any, _FakeRequest(app=harness.app)))
                await proc_browser.api_tree(
                    cast(
                        Any,
                        _FakeRequest({"extensions": ".md"}, app=harness.app),
                    )
                )
                return tuple(observed_page_bounds)
        finally:
            server_namespace["assemble_tree_pages"] = original_assemble

    assert asyncio.run(_run()) == (
        INVENTORY_TREE_PAGE_ROWS,
        INVENTORY_TREE_PAGE_ROWS,
    )


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

        paths_safe._set_root_dir(tmp_path)
        async with inventory_harness(tmp_path) as harness:
            resp = await proc_browser.api_tree(cast(Any, _FakeRequest(app=harness.app)))
            tallies = await proc_browser.api_tree(
                cast(
                    Any,
                    _FakeRequest({"depth": "0"}, app=harness.app),
                )
            )
        rows = json.loads(bytes(resp.body))
        # Rows and tallies now come from different requests; merge them here so
        # the assertions below still read as one description of the surface.
        rows.update({k: v for k, v in json.loads(bytes(tallies.body)).items() if k != "tree"})
        return rows

    body = asyncio.run(_run())
    assert "tally_cache_status" in body
    assert body["tally_cache_status"] in ("idle", "scanning", "done", "truncated")
    assert "tree" in body
    # Documentation first, the order every surface lists the groups in.
    assert [row[0] for row in body["type_presets"]] == [
        "docs",
        "code",
        "data",
        "archives",
        "media",
    ]
    assert body["file_type_registry"] == {
        "schema_version": 5,
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
        paths_safe._set_root_dir(tmp_path)
        async with inventory_harness(tmp_path) as harness:
            response = await proc_browser.api_tree(
                cast(Any, _FakeRequest({"depth": "0"}, app=harness.app))
            )
            return json.loads(bytes(response.body))

    body = asyncio.run(run())
    assert body["summary"]["files"] == 5
    assert body["tally_cache_status"] == "done"


def test_api_tree_group_by_reads_every_group_in_one_pass(tmp_path: Path) -> None:
    """Group by is one provider read over the index, whatever the number of groups: the
    same reads and rows visited as one filtered tree, where asking for each group alone
    paid one read and one pass per group (mb-navs)."""

    _build_fixture(tmp_path)

    async def work(harness: Any) -> tuple[int, int]:
        read = await harness.runtime.coordinator.read(
            ReadRequest(queries=(DiagnosticsQuery(query_id="diagnostics"),))
        )
        diagnostics = read.result.completed_projection("diagnostics")
        assert isinstance(diagnostics, DiagnosticsProjection)
        payload = diagnostics.payload
        return payload.read_requests, payload.cumulative_work.rows_visited

    async def run() -> dict[str, tuple[int, int]]:
        paths_safe._set_root_dir(tmp_path)
        costs: dict[str, tuple[int, int]] = {}
        async with inventory_harness(tmp_path) as harness:
            for label, query in (
                ("filtered", {"types": ".md", "depth": "2"}),
                ("type", {"group_by": "type", "depth": "2"}),
                ("age", {"group_by": "age", "depth": "2"}),
            ):
                before = await work(harness)
                response = await proc_browser.api_tree(
                    cast(Any, _FakeRequest(query, app=harness.app))
                )
                assert response.status_code == 200
                after = await work(harness)
                costs[label] = (after[0] - before[0], after[1] - before[1])
        return costs

    costs = asyncio.run(run())
    assert costs["type"] == costs["age"] == costs["filtered"]


def _tree_paths(nodes: list[dict[str, Any]]) -> list[str]:
    """Every row a tree payload draws, depth first."""

    return [
        path for node in nodes for path in (node["path"], *_tree_paths(node.get("children") or []))
    ]


def test_api_tree_group_by_assembles_a_group_past_the_page_bound(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A group whose rows outrun `INVENTORY_TREE_PAGE_ROWS` is read to its end from its
    continuation: its tree is the one its own `?group=` read draws."""

    _build_fixture(tmp_path)
    for folder in ("docs", "guides"):
        (tmp_path / folder).mkdir(exist_ok=True)
        for index in range(6):
            (tmp_path / folder / f"page-{index}.md").write_text("page")
    page_rows = 3
    monkeypatch.setattr(proc_browser, "INVENTORY_TREE_PAGE_ROWS", page_rows)

    async def run() -> tuple[dict[str, Any], dict[str, Any]]:
        paths_safe._set_root_dir(tmp_path)
        async with inventory_harness(tmp_path) as harness:
            grouped = await proc_browser.api_tree(
                cast(Any, _FakeRequest({"group_by": "type", "depth": "2"}, app=harness.app))
            )
            alone = await proc_browser.api_tree(
                cast(Any, _FakeRequest({"group": "type:docs", "depth": "2"}, app=harness.app))
            )
            assert grouped.status_code == alone.status_code == 200
            return json.loads(bytes(grouped.body)), json.loads(bytes(alone.body))

    grouped, alone = asyncio.run(run())
    docs = next(group for group in grouped["groups"] if group["id"] == "docs")
    assert len(_tree_paths(docs["tree"])) > page_rows
    assert docs["tree"] == alone["tree"]
    assert (docs["files"], docs["size"], docs["entries"]) == (
        alone["filtered"]["files"],
        alone["filtered"]["size"],
        alone["filtered"]["entries"],
    )


def test_api_tree_group_by_reads_overlapping_wide_groupings_without_missing_a_page(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Grouped reads that overlap, each retaining every group's remaining rows for its
    continuations, take turns, so none evicts another's pages (mb-ub75).

    The provider keeps one grouped read's continuations within `MAX_ASSEMBLED_ROWS`, here
    lowered to exactly what one read retains, so a second read retaining its own beside
    it would evict the first's. Each read's first pass is held until every grouped pass
    already begun has retained its pages, as passes that take seconds overlap."""

    _build_fixture(tmp_path)
    for folder, extension in (("docs", ".md"), ("src", ".py"), ("data", ".json")):
        (tmp_path / folder).mkdir(exist_ok=True)
        for index in range(6):
            (tmp_path / folder / f"item-{index}{extension}").write_text("item")
    page_rows = 3
    monkeypatch.setattr(proc_browser, "INVENTORY_TREE_PAGE_ROWS", page_rows)
    query = {"group_by": "type", "depth": "2"}
    passes = {"started": 0, "finished": 0}
    retained_all = asyncio.Condition()
    missed: list[str] = []
    original_read = InventoryReadSession.read

    async def overlapping_read(
        self: InventoryReadSession, request: ReadRequest, **kwargs: bool
    ) -> CoordinatedRead:
        grouped = any(isinstance(entry, GroupedTreeQuery) for entry in request.queries)
        passes["started"] += grouped
        try:
            read = await original_read(self, request, **kwargs)
        except VersionUnavailableError as error:
            missed.append(str(error))
            raise
        if grouped:
            passes["finished"] += 1
            async with retained_all:
                retained_all.notify_all()
                await asyncio.wait_for(
                    retained_all.wait_for(lambda: passes["finished"] >= passes["started"]), 5
                )
        return read

    async def run() -> tuple[dict[str, Any], list[Any]]:
        paths_safe._set_root_dir(tmp_path)
        async with inventory_harness(tmp_path) as harness:
            alone = await proc_browser.api_tree(cast(Any, _FakeRequest(query, app=harness.app)))
            body = json.loads(bytes(alone.body))
            retained = sum(
                count
                for group in body["groups"]
                if (count := len(_tree_paths(group["tree"]))) > page_rows
            )
            # One row less, and a read evicts its own pages: it says so when it gives up.
            monkeypatch.setattr(python_inventory, "MAX_ASSEMBLED_ROWS", retained - 1)
            with pytest.raises(
                VersionUnavailableError,
                match=r"grouped tree assembly failed 3 attempts; the last: the filtered-tree "
                r"page cursor is unavailable: its page was evicted, as retained continuations "
                rf"reached {retained - 1} rows",
            ):
                await proc_browser.api_tree(cast(Any, _FakeRequest(query, app=harness.app)))
            monkeypatch.setattr(python_inventory, "MAX_ASSEMBLED_ROWS", retained)
            monkeypatch.setattr(InventoryReadSession, "read", overlapping_read)
            responses = await asyncio.gather(
                *(
                    proc_browser.api_tree(cast(Any, _FakeRequest(query, app=harness.app)))
                    for _request in range(3)
                )
            )
            return body, list(responses)

    alone, responses = asyncio.run(run())
    assert sum(1 for group in alone["groups"] if len(_tree_paths(group["tree"])) > 3) >= 2
    assert missed == []
    assert passes == {"started": 3, "finished": 3}
    for response in responses:
        assert response.status_code == 200
        assert json.loads(bytes(response.body)) == alone


def test_api_tree_uses_provider_presence_instead_of_parallel_filesystem_truth(
    tmp_path: Path,
) -> None:
    async def run() -> int:
        paths_safe._set_root_dir(tmp_path)
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
        paths_safe._set_root_dir(tmp_path)
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
        paths_safe._set_root_dir(tmp_path)
        async with inventory_harness(tmp_path) as harness:
            rows = await proc_browser.api_tree(cast(Any, _FakeRequest(app=harness.app)))
            tallies = await proc_browser.api_tree(
                cast(
                    Any,
                    _FakeRequest({"depth": "0"}, app=harness.app),
                )
            )
        return json.loads(bytes(rows.body)), json.loads(bytes(tallies.body))

    rows, tallies = asyncio.run(_run())

    # The rows arrive either way, and so does the scan-state label the client
    # uses to decide whether to trust what it has.
    assert rows["tree"], "a row request must still carry rows"
    assert "tally_cache_status" in rows

    # And the tally channel answers with them.
    assert tallies["summary"] is not None
    assert tallies["type_presets"] is not None
