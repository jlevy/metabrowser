"""Server half of the Quick File catalog feed.

* ``GET /api/catalog`` returns every non-gitignored file at
  ``all-known`` scope in the minimal ``{p, e}`` shape, with honest
  ``complete``/``truncated`` flags and a revision-backed ETag.
* Every ``fs.change`` emits a minimal ``catalog.change`` companion:
  file upserts shrink to ``{p, e}``, a gitignored upsert becomes an
  exact-file removal, filesystem removals retain subtree semantics,
  and directory-only upsert batches emit nothing.
* ``catalog.change`` passes the ``root-depth-2`` scope filter
  unchanged, so the depth-scoped tree stream carries complete
  catalog deltas.
* Walker completion emits ``capability.update`` with
  ``index.complete`` so stream clients can flip completeness
  without polling.
"""

from __future__ import annotations

import asyncio
import inspect
import json
from pathlib import Path
from typing import Any, cast

import pytest

from metabrowser import events_route
from metabrowser.events import CapabilityUpdate, CatalogChange, CatalogUpsert
from metabrowser.events_route import _filter_event_for_scope, api_catalog
from metabrowser.inventory_engine.contract import (
    CatalogQuery,
    CatalogRecord,
    ObservationKind,
    ReadRequest,
    RefreshObservation,
    RefreshRequest,
)
from tests.inventory_harness import inventory_harness, wait_until_settled


def _build_fixture(root: Path) -> None:
    (root / ".git").mkdir()
    (root / ".gitignore").write_text("ignored/\n*.tmp\n")
    (root / "README.md").write_text("readme")
    (root / "docs" / "deep" / "nested").mkdir(parents=True)
    (root / "docs" / "notes.md").write_text("notes")
    (root / "docs" / "deep" / "nested" / "leaf.txt").write_text("leaf")
    (root / "ignored").mkdir()
    (root / "ignored" / "secret.txt").write_text("secret")
    (root / "scratch.tmp").write_text("scratch")


class _FakeHeaders:
    def __init__(self, values: dict[str, str] | None = None) -> None:
        self._values = {key.lower(): value for key, value in (values or {}).items()}

    def get(self, key: str, default: str = "") -> str:
        return self._values.get(key.lower(), default)


class _FakeRequest:
    def __init__(self, app: object, headers: dict[str, str] | None = None) -> None:
        self.app = app
        self.headers = _FakeHeaders(headers)


def _body(response: Any) -> dict[str, Any]:
    return cast(dict[str, Any], json.loads(bytes(response.body)))


async def _catalog_event(queue: asyncio.Queue[Any]) -> CatalogChange:
    while True:
        envelope = await asyncio.wait_for(queue.get(), timeout=2.0)
        if isinstance(envelope.event, CatalogChange):
            return envelope.event


def test_api_catalog_lists_the_complete_nonignored_file_universe(tmp_path: Path) -> None:
    _build_fixture(tmp_path)

    async def run() -> dict[str, Any]:
        async with inventory_harness(tmp_path) as harness:
            response = await api_catalog(cast(Any, _FakeRequest(harness.app)))
            assert response.status_code == 200
            return _body(response)

    body = asyncio.run(run())
    paths = {file["p"] for file in body["files"]}
    assert {"README.md", "docs/notes.md", "docs/deep/nested/leaf.txt"} <= paths
    assert "ignored/secret.txt" not in paths
    assert "scratch.tmp" not in paths
    assert set(body["files"][0]) == {"p", "e"}
    assert body["complete"] is True
    assert body["truncated"] is False


def test_api_catalog_is_incomplete_while_discovery_is_blocked(
    tmp_path: Path,
    monkeypatch: Any,
) -> None:
    from metabrowser.inventory_engine.providers import python_inventory as python_provider

    started = asyncio.Event()
    release = asyncio.Event()
    original_walk = python_provider.walk_tree

    async def blocked_walk(*args: Any, **kwargs: Any):
        started.set()
        await release.wait()
        async for entry in original_walk(*args, **kwargs):
            yield entry

    monkeypatch.setattr(python_provider, "walk_tree", blocked_walk)

    async def run() -> dict[str, Any]:
        async with inventory_harness(tmp_path, settle=False) as harness:
            await asyncio.wait_for(started.wait(), timeout=1)
            try:
                response = await api_catalog(cast(Any, _FakeRequest(harness.app)))
                return _body(response)
            finally:
                release.set()

    body = asyncio.run(run())
    assert body["complete"] is False
    assert body["files"] == []


def test_catalog_etag_and_live_addition_converge(tmp_path: Path) -> None:
    _build_fixture(tmp_path)

    async def run() -> tuple[Any, Any, Any]:
        async with inventory_harness(tmp_path) as harness:
            first = await api_catalog(cast(Any, _FakeRequest(harness.app)))
            etag = first.headers["ETag"]
            cached = await api_catalog(
                cast(Any, _FakeRequest(harness.app, {"If-None-Match": etag}))
            )
            (tmp_path / "docs" / "new.txt").write_text("new")
            await harness.runtime.coordinator.refresh(
                RefreshRequest(
                    observations=(
                        RefreshObservation(
                            path="docs/new.txt",
                            kind=ObservationKind.CREATED,
                        ),
                    )
                )
            )
            changed = await api_catalog(
                cast(Any, _FakeRequest(harness.app, {"If-None-Match": etag}))
            )
            return first, cached, changed

    first, cached, changed = asyncio.run(run())
    assert cached.status_code == 304
    assert changed.status_code == 200
    assert changed.headers["ETag"] != first.headers["ETag"]
    assert "docs/new.txt" in {file["p"] for file in _body(changed)["files"]}


def test_catalog_identity_ignores_changes_the_catalog_does_not_carry(
    tmp_path: Path,
) -> None:
    """An mtime touch must not re-send the catalog.

    The engine version moves on every indexed change; the catalog carries a
    path and a logical extension per file and moves on far fewer. Keying the
    ETag on the engine version made an ordinary editor save invalidate the
    largest payload the server produces, for a body whose only differing byte
    was the revision claiming it had changed.

    The touched file is already indexed and keeps its name, so the wire content
    is identical and the client must be told so.
    """

    _build_fixture(tmp_path)

    async def run() -> tuple[Any, Any, Any]:
        async with inventory_harness(tmp_path) as harness:
            first = await api_catalog(cast(Any, _FakeRequest(harness.app)))
            etag = first.headers["ETag"]
            target = tmp_path / "docs" / "notes.md"
            target.write_text(target.read_text() + "more\n")
            await harness.runtime.coordinator.refresh(
                RefreshRequest(
                    observations=(
                        RefreshObservation(
                            path="docs/notes.md",
                            kind=ObservationKind.MODIFIED,
                        ),
                    )
                )
            )
            await wait_until_settled(harness.runtime)
            revalidated = await api_catalog(
                cast(Any, _FakeRequest(harness.app, {"If-None-Match": etag}))
            )
            fresh = await api_catalog(cast(Any, _FakeRequest(harness.app)))
            return first, revalidated, fresh

    first, revalidated, fresh = asyncio.run(run())
    assert revalidated.status_code == 304
    assert fresh.headers["ETag"] == first.headers["ETag"]
    # The revision is the count of distinct catalogs served, so it holds too.
    assert _body(fresh)["revision"] == _body(first)["revision"]
    assert _body(fresh)["files"] == _body(first)["files"]


def test_catalog_live_add_ignore_and_remove_deltas(tmp_path: Path) -> None:
    _build_fixture(tmp_path)

    async def run() -> tuple[CatalogChange, CatalogChange, CatalogChange]:
        async with inventory_harness(tmp_path) as harness:
            queue = harness.bus.attach_connection()
            try:
                (tmp_path / "docs" / "live.txt").write_text("live")
                await harness.runtime.coordinator.refresh(
                    RefreshRequest(
                        observations=(
                            RefreshObservation(
                                path="docs/live.txt",
                                kind=ObservationKind.CREATED,
                            ),
                        )
                    )
                )
                added = await _catalog_event(queue)

                (tmp_path / "ignored" / "other.txt").write_text("ignored")
                await harness.runtime.coordinator.refresh(
                    RefreshRequest(
                        observations=(
                            RefreshObservation(
                                path="ignored/other.txt",
                                kind=ObservationKind.CREATED,
                            ),
                        )
                    )
                )
                ignored = await _catalog_event(queue)

                (tmp_path / "docs" / "notes.md").unlink()
                await harness.runtime.coordinator.refresh(
                    RefreshRequest(
                        observations=(
                            RefreshObservation(
                                path="docs/notes.md",
                                kind=ObservationKind.DELETED,
                            ),
                        )
                    )
                )
                removed = await _catalog_event(queue)
                return added, ignored, removed
            finally:
                harness.bus.detach_connection(queue)

    added, ignored, removed = asyncio.run(run())
    assert [(upsert.p, upsert.e) for upsert in added.upserts] == [("docs/live.txt", ".txt")]
    assert added.removes == ()
    assert added.remove_files == ()
    assert ignored.upserts == ()
    assert ignored.removes == ()
    assert ignored.remove_files == ("ignored/other.txt",)
    assert removed.removes == ("docs/notes.md",)
    assert removed.remove_files == ()


def test_catalog_change_passes_depth_scope_filter() -> None:
    event = CatalogChange(
        upserts=(CatalogUpsert(p="very/deep/nested/path/file.txt", e=".txt"),),
        removes=(),
        remove_files=(),
    )
    assert _filter_event_for_scope(event, "root-depth-2") is event


def test_walker_completion_projects_capability_update(
    tmp_path: Path,
    monkeypatch: Any,
) -> None:
    from metabrowser.inventory_engine.providers import python_inventory as python_provider

    for index in range(30):
        (tmp_path / f"file-{index}.txt").write_text("x")
    original_walk = python_provider.walk_tree

    async def slow_walk(*args: Any, **kwargs: Any):
        async for entry in original_walk(*args, **kwargs):
            yield entry
            await asyncio.sleep(0.001)

    monkeypatch.setattr(python_provider, "walk_tree", slow_walk)

    async def run() -> CapabilityUpdate:
        async with inventory_harness(tmp_path, settle=False) as harness:
            queue = harness.bus.attach_connection()
            try:
                await wait_until_settled(harness.runtime)
                while True:
                    envelope = await asyncio.wait_for(queue.get(), timeout=2.0)
                    if (
                        isinstance(envelope.event, CapabilityUpdate)
                        and envelope.event.index.get("complete") is True
                    ):
                        return envelope.event
            finally:
                harness.bus.detach_connection(queue)

    update = asyncio.run(run())
    assert update.index["complete"] is True
    assert update.index["truncated"] is False


def test_catalog_encoding_is_off_loop_and_reused(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _build_fixture(tmp_path)
    calls: list[int] = []
    catalog_reads = 0
    real_encode = events_route._encode_catalog

    def counting_encode(
        pages: tuple[tuple[CatalogRecord, ...], ...],
        status: str,
        revision: int,
    ) -> bytes:
        calls.append(sum(len(page) for page in pages))
        return real_encode(pages, status, revision)

    async def run() -> tuple[Any, Any]:
        async with inventory_harness(tmp_path) as harness:
            events_route._CATALOG_BODY_CACHE.clear()
            events_route._encode_catalog = counting_encode  # type: ignore[assignment]
            real_read = harness.runtime.coordinator.read

            async def counting_read(
                request: ReadRequest,
                *,
                include_catalog_decorations: bool = False,
            ) -> Any:
                nonlocal catalog_reads
                if any(isinstance(query, CatalogQuery) for query in request.queries):
                    catalog_reads += 1
                return await real_read(
                    request,
                    include_catalog_decorations=include_catalog_decorations,
                )

            monkeypatch.setattr(harness.runtime.coordinator, "read", counting_read)
            try:
                first = await api_catalog(cast(Any, _FakeRequest(harness.app)))
                second = await api_catalog(cast(Any, _FakeRequest(harness.app)))
                conditional = await api_catalog(
                    cast(
                        Any,
                        _FakeRequest(harness.app, {"If-None-Match": first.headers["ETag"]}),
                    )
                )
                assert conditional.status_code == 304
                return first, second
            finally:
                events_route._encode_catalog = real_encode  # type: ignore[assignment]

    first, second = asyncio.run(run())
    assert first.body == second.body
    assert first.headers["ETag"] == second.headers["ETag"]
    assert len(calls) == 1
    assert catalog_reads == 1


def test_catalog_bulk_materialization_stays_in_the_worker() -> None:
    route_source = inspect.getsource(events_route.api_catalog)
    read_source = inspect.getsource(events_route._read_catalog)
    encode_source = inspect.getsource(events_route._encode_catalog)
    coordinator_source = inspect.getsource(events_route.InventoryCoordinator._returned_paths)

    assert '{"p": record.path, "e": record.logical_extension}' not in route_source
    assert '{"p": record.path, "e": record.logical_extension}' in encode_source
    assert "for record in projection.records" not in read_source
    assert "pages.append(projection.records)" in read_source
    assert "page_size = runtime.config.max_files" in read_source
    assert "if include_catalog:" in coordinator_source
