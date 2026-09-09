"""/api/file returns a folder envelope for directories.

Locks in the directory branch of _api_file_impl: kind/views come from
the merged folder plugin manifest, aggregates come from the inventory
(null-tolerant while scanning), README detection is case-insensitive
and scoped to direct children, and the envelope is no-store. Paths
outside the root still 404.
"""

from __future__ import annotations

import asyncio
import json
from collections.abc import AsyncIterator
from pathlib import Path
from typing import Any
from unittest.mock import Mock

import pytest

from metabrowser import server
from metabrowser.inventory_engine.contract import InventoryEntry
from tests.inventory_harness import inventory_harness


class _FakeQuery:
    def __init__(self, params: dict[str, str]) -> None:
        self._params = params

    def get(self, key: str, default: str = "") -> str:
        return self._params.get(key, default)


def _request(path: str, *, app: object) -> Mock:
    request = Mock(spec=["query_params", "headers", "app"])
    request.query_params = _FakeQuery({"path": path})
    request.headers = {}
    request.app = app
    return request


def _api_file(
    root: Path,
    path: str,
    *,
    settle: bool = True,
) -> tuple[dict[str, Any], Any]:
    async def run() -> tuple[dict[str, Any], Any]:
        async with inventory_harness(root, settle=settle) as harness:
            response = await server.api_file(_request(path, app=harness.app))
            return json.loads(bytes(response.body)), response

    return asyncio.run(run())


def test_directory_returns_folder_envelope(tmp_path: Path) -> None:
    server._set_root_dir(tmp_path)
    sub = tmp_path / "sub"
    sub.mkdir()
    (sub / "data.txt").write_text("x" * 32)
    body, response = _api_file(tmp_path, "sub")
    assert body["type"] == "folder"
    assert body["kind"] == "folder"
    assert body["path"] == "sub"
    assert body["name"] == "sub"
    view_ids = [v["id"] for v in body["views"]]
    assert view_ids == ["overview", "treemap"]
    defaults = [v["id"] for v in body["views"] if v.get("default")]
    assert defaults == ["overview"]
    assert response.headers["cache-control"] == "no-store"


def test_root_directory_envelope_and_pending_state(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def blocked_walk(
        *_args: object,
        **_kwargs: object,
    ) -> AsyncIterator[InventoryEntry]:
        if False:
            yield InventoryEntry.for_observed_dir(path="", parent="", name=tmp_path.name)
        await asyncio.Event().wait()

    monkeypatch.setattr(
        "metabrowser.inventory_engine.providers.python_inventory.walk_tree",
        blocked_walk,
    )
    server._set_root_dir(tmp_path)
    (tmp_path / "a.txt").write_text("hello")
    body, _ = _api_file(tmp_path, "", settle=False)
    assert body["kind"] == "folder"
    assert body["path"] == ""
    # No inventory has run: aggregates are pending, never fabricated.
    assert body["dir"]["total_files"] is None
    assert body["dir"]["state"] == "pending"


def test_envelope_aggregates_come_from_inventory(tmp_path: Path) -> None:
    server._set_root_dir(tmp_path)
    sub = tmp_path / "sub"
    sub.mkdir()
    (sub / "one.txt").write_text("x" * 10)
    (sub / "two.txt").write_text("y" * 30)

    body, _response = _api_file(tmp_path, "sub")
    assert body["dir"]["state"] == "complete"
    assert body["dir"]["total_files"] == 2
    assert body["dir"]["total_size"] == 40
    assert body["dir"]["unignored_files"] == 2
    assert body["dir"]["unignored_size"] == 40
    assert body["dir"]["mtime"] > 0


def test_readme_detection_direct_children_only(tmp_path: Path) -> None:
    server._set_root_dir(tmp_path)
    docs = tmp_path / "docs"
    docs.mkdir()
    (docs / "ReadMe.MD").write_text("# docs")
    nested = docs / "nested"
    nested.mkdir()
    (nested / "other.txt").write_text("no readme here")

    body, _ = _api_file(tmp_path, "docs")
    assert body["readme_path"] == "docs/ReadMe.MD"
    nested_body, _ = _api_file(tmp_path, "docs/nested")
    assert nested_body["readme_path"] == ""


def test_traversal_still_404(tmp_path: Path) -> None:
    server._set_root_dir(tmp_path)
    _, response = _api_file(tmp_path, "../outside")
    assert response.status_code == 404


def test_missing_path_still_404(tmp_path: Path) -> None:
    server._set_root_dir(tmp_path)
    _, response = _api_file(tmp_path, "nope")
    assert response.status_code == 404
