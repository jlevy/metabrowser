"""Server half of the Quick File catalog feed.

* ``GET /api/catalog`` returns every non-gitignored file at
  ``all-known`` scope in the minimal ``{p, e}`` shape, with honest
  ``complete``/``truncated`` flags and a revision-backed ETag.
* Every ``fs.change`` emits a minimal ``catalog.change`` companion:
  file upserts shrink to ``{p, e}``, a gitignored upsert becomes a
  catalog remove, directory-only batches emit nothing.
* ``catalog.change`` passes the ``root-depth-2`` scope filter
  unchanged, so the depth-scoped tree stream carries complete
  catalog deltas.
* Walker completion emits ``capability.update`` with
  ``index.complete`` so stream clients can flip completeness
  without polling.
"""

from __future__ import annotations

import asyncio
import json
from pathlib import Path
from typing import Any, cast

from metabrowser import events_route
from metabrowser.events import (
    CapabilityUpdate,
    CatalogChange,
    FsChange,
    FsEntry,
)
from metabrowser.events_route import _filter_event_for_scope, api_catalog
from metabrowser.inventory import get_instance, reset_instance_for_tests


def _build_fixture(root: Path) -> None:
    # A bare .git marker makes build_gitignore_check treat the root
    # as a repo (it short-circuits when git_root is None). No `git
    # init` — a real init here is unnecessary and this tree's hooks
    # export repo-pinning GIT_* variables that make it dangerous.
    (root / ".git").mkdir()
    (root / ".gitignore").write_text("ignored/\n*.tmp\n")
    (root / "README.md").write_text("readme")
    (root / "docs").mkdir()
    (root / "docs" / "notes.md").write_text("notes")
    (root / "docs" / "deep").mkdir()
    (root / "docs" / "deep" / "nested").mkdir()
    (root / "docs" / "deep" / "nested" / "leaf.txt").write_text("leaf")
    (root / "ignored").mkdir()
    (root / "ignored" / "secret.txt").write_text("secret")
    (root / "scratch.tmp").write_text("scratch")


async def _drive_walker(root: Path) -> None:
    reset_instance_for_tests()
    inv = get_instance()
    inv.start(root)
    await inv.wait_until_done(timeout=5.0)


class _FakeHeaders:
    def __init__(self, data: dict[str, str] | None = None) -> None:
        self._data = {k.lower(): v for k, v in (data or {}).items()}

    def get(self, key: str, default: str = "") -> str:
        return self._data.get(key.lower(), default)


class _FakeRequest:
    def __init__(self, headers: dict[str, str] | None = None) -> None:
        self.headers = _FakeHeaders(headers)


def _file_entry(path: str, *, gitignored: bool = False) -> FsEntry:
    name = path.rsplit("/", 1)[-1]
    parent = path.rsplit("/", 1)[0] if "/" in path else ""
    return FsEntry(
        path=path,
        parent=parent,
        name=name,
        type="file",
        ext=".txt",
        kind="file",
        size=1,
        mtime_ns=1,
        mtime_hash="",
        active=False,
        gitignored=gitignored,
    )


def _catalog_body(response: Any) -> dict[str, Any]:
    return json.loads(bytes(response.body))


# ── GET /api/catalog ────────────────────────────────────────────


def test_api_catalog_lists_non_gitignored_files_only(tmp_path: Path) -> None:
    _build_fixture(tmp_path)

    async def _run() -> dict[str, Any]:
        await _drive_walker(tmp_path)
        response = await api_catalog(cast(Any, _FakeRequest()))
        assert response.status_code == 200
        return _catalog_body(response)

    body = asyncio.run(_run())
    paths = {f["p"] for f in body["files"]}
    assert "README.md" in paths
    assert "docs/notes.md" in paths
    # Depth-2+ paths are present — the whole point of the feed.
    assert "docs/deep/nested/leaf.txt" in paths
    # Gitignored files and directories never appear.
    assert "ignored/secret.txt" not in paths
    assert "scratch.tmp" not in paths
    assert all(f["p"] != "docs" for f in body["files"])
    # Minimal shape only.
    assert set(body["files"][0].keys()) == {"p", "e"}
    notes = next(f for f in body["files"] if f["p"] == "docs/notes.md")
    assert notes["e"] == ".md"
    assert body["complete"] is True
    assert body["truncated"] is False


def test_api_catalog_etag_roundtrip(tmp_path: Path) -> None:
    _build_fixture(tmp_path)

    async def _run() -> tuple[Any, Any, Any]:
        await _drive_walker(tmp_path)
        first = await api_catalog(cast(Any, _FakeRequest()))
        etag = first.headers["ETag"]
        second = await api_catalog(cast(Any, _FakeRequest({"If-None-Match": etag})))
        # A change bumps the catalog revision and invalidates the ETag.
        get_instance().apply_live_entry(_file_entry("docs/new.txt"))
        third = await api_catalog(cast(Any, _FakeRequest({"If-None-Match": etag})))
        return first, second, third

    first, second, third = asyncio.run(_run())
    assert second.status_code == 304
    assert third.status_code == 200
    assert third.headers["ETag"] != first.headers["ETag"]
    assert "docs/new.txt" in {f["p"] for f in _catalog_body(third)["files"]}


def test_api_catalog_incomplete_while_idle() -> None:
    reset_instance_for_tests()

    async def _run() -> dict[str, Any]:
        response = await api_catalog(cast(Any, _FakeRequest()))
        return _catalog_body(response)

    body = asyncio.run(_run())
    assert body["complete"] is False
    assert body["files"] == []


# ── catalog.change companions ───────────────────────────────────


def test_live_upsert_emits_catalog_companion(tmp_path: Path) -> None:
    _build_fixture(tmp_path)

    async def _run() -> list[Any]:
        await _drive_walker(tmp_path)
        inv = get_instance()
        queue = inv.subscribe()
        inv.apply_live_entry(_file_entry("docs/live.txt"))
        return [queue.get_nowait(), queue.get_nowait()]

    first, second = asyncio.run(_run())
    assert isinstance(first, FsChange)
    assert isinstance(second, CatalogChange)
    assert [(u.p, u.e) for u in second.upserts] == [("docs/live.txt", ".txt")]
    assert second.removes == ()


def test_gitignored_upsert_becomes_catalog_remove(tmp_path: Path) -> None:
    _build_fixture(tmp_path)

    async def _run() -> Any:
        await _drive_walker(tmp_path)
        inv = get_instance()
        queue = inv.subscribe()
        inv.apply_live_entry(_file_entry("ignored/other.txt", gitignored=True))
        events = [queue.get_nowait(), queue.get_nowait()]
        return events[1]

    companion = asyncio.run(_run())
    assert isinstance(companion, CatalogChange)
    assert companion.upserts == ()
    assert companion.removes == ("ignored/other.txt",)


def test_remove_emits_catalog_remove(tmp_path: Path) -> None:
    _build_fixture(tmp_path)

    async def _run() -> Any:
        await _drive_walker(tmp_path)
        inv = get_instance()
        queue = inv.subscribe()
        inv.remove("docs/notes.md")
        events = [queue.get_nowait(), queue.get_nowait()]
        return events[1]

    companion = asyncio.run(_run())
    assert isinstance(companion, CatalogChange)
    assert companion.removes == ("docs/notes.md",)


def test_catalog_change_passes_depth_scope_filter() -> None:
    from metabrowser.events import CatalogUpsert

    event = CatalogChange(
        upserts=(CatalogUpsert(p="very/deep/nested/path/file.txt", e=".txt"),),
        removes=(),
    )
    assert _filter_event_for_scope(event, "root-depth-2") is event


# ── completion signal ───────────────────────────────────────────


def test_walker_completion_emits_capability_update(tmp_path: Path) -> None:
    _build_fixture(tmp_path)

    async def _run() -> list[Any]:
        reset_instance_for_tests()
        inv = get_instance()
        queue = inv.subscribe()
        inv.start(tmp_path)
        await inv.wait_until_done(timeout=5.0)
        events = []
        while not queue.empty():
            events.append(queue.get_nowait())
        return events

    events = asyncio.run(_run())
    updates = [e for e in events if isinstance(e, CapabilityUpdate)]
    assert len(updates) == 1
    assert updates[0].index["complete"] is True
    assert updates[0].index["truncated"] is False


def test_api_catalog_encodes_off_loop_and_reuses_one_body(tmp_path: Path) -> None:
    """R12: only one O(N) pass may run on the event loop.

    ``catalog_files()`` takes the consistent snapshot; building the wire dicts
    and encoding both belong in the worker. A second request at the same
    revision must not repeat that work at all.
    """
    _build_fixture(tmp_path)
    calls: list[int] = []
    real_encode = events_route._encode_catalog

    def _counting_encode(files: list[tuple[str, str]], status: str, revision: int) -> bytes:
        calls.append(len(files))
        return real_encode(files, status, revision)

    async def _run() -> tuple[Any, Any]:
        await _drive_walker(tmp_path)
        events_route._CATALOG_BODY_CACHE.clear()
        events_route._encode_catalog = _counting_encode  # type: ignore[assignment]
        try:
            # No If-None-Match, so the ETag shortcut cannot serve either call.
            first = await api_catalog(cast(Any, _FakeRequest()))
            second = await api_catalog(cast(Any, _FakeRequest()))
            return first, second
        finally:
            events_route._encode_catalog = real_encode  # type: ignore[assignment]

    first, second = asyncio.run(_run())
    assert first.body == second.body
    assert first.headers["ETag"] == second.headers["ETag"]
    assert len(calls) == 1, f"encoded {len(calls)} times for one revision"


def test_catalog_wire_dicts_are_built_only_in_the_worker() -> None:
    """The route body must not materialize the wire list before its await."""
    source = Path(events_route.__file__).read_text()
    route_start = source.index("async def api_catalog(")
    route_body = source[route_start : source.index("async def api_index_meta(")]
    assert '{"p": p, "e": e}' not in route_body
    encode_start = source.index("def _encode_catalog(")
    assert '{"p": p, "e": e}' in source[encode_start:route_start]
